"""Heimdall memory service.

FastAPI app backing Heimdall's persistent cross-session memory (Task 8 /
M7). See README.md for the write-path design (explicit tool calls +
background poller, both landing here).

Storage is a single SQLite file — this is a household voice-assistant
memory store, not a multi-tenant system; a single file with two small
tables is the right amount of infrastructure for it.
"""

from __future__ import annotations

import os
import sqlite3
import textwrap
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("HEIMDALL_MEMORY_DB", "/data/memory.db"))
MEMORY_TOKEN = os.environ.get("HEIMDALL_MEMORY_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EXTRACTION_MODEL = os.environ.get("HEIMDALL_EXTRACTION_MODEL", "qwen2.5:7b-instruct")
DEFAULT_USER = "household"

app = FastAPI(title="Heimdall Memory Service")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                source TEXT NOT NULL DEFAULT 'tool',
                conversation_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject, predicate)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                user TEXT PRIMARY KEY,
                summary TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_runs (
                pipeline_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (pipeline_id, run_id)
            )
            """
        )


def _require_token(x_heimdall_memory_token: str = Header(default="")) -> None:
    if not MEMORY_TOKEN:
        # Fail closed: an unset token means auth is misconfigured, not open.
        raise HTTPException(status_code=500, detail="Memory service token not configured")
    if x_heimdall_memory_token != MEMORY_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing memory token")


class FactIn(BaseModel):
    subject: str
    predicate: str
    object: str
    language: str = "en"
    source: Literal["tool", "poller"] = "tool"
    conversation_id: str | None = None


class Fact(BaseModel):
    subject: str
    predicate: str
    object: str
    language: str
    source: str
    updated_at: str


class MemoryContext(BaseModel):
    summary: str
    facts: list[Fact]
    text: str


class TranscriptTurn(BaseModel):
    speaker: Literal["user", "assistant"]
    text: str


class ExtractIn(BaseModel):
    conversation_id: str
    language: str = "en"
    transcript: list[TranscriptTurn]


class ExtractOut(BaseModel):
    facts_upserted: int
    summary_updated: bool


@app.on_event("startup")
def on_startup() -> None:
    _init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/facts", dependencies=[Depends(_require_token)])
def upsert_fact(fact: FactIn) -> dict:
    now = _now()
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO facts (subject, predicate, object, language, source, conversation_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject, predicate) DO UPDATE SET
                object = excluded.object,
                language = excluded.language,
                source = excluded.source,
                conversation_id = excluded.conversation_id,
                updated_at = excluded.updated_at
            """,
            (
                fact.subject,
                fact.predicate,
                fact.object,
                fact.language,
                fact.source,
                fact.conversation_id,
                now,
                now,
            ),
        )
    return {"status": "ok", "subject": fact.subject, "predicate": fact.predicate}


@app.get("/facts/search", response_model=list[Fact], dependencies=[Depends(_require_token)])
def search_facts(q: str = Query(..., min_length=1)) -> list[Fact]:
    like = f"%{q.lower()}%"
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT subject, predicate, object, language, source, updated_at FROM facts
            WHERE lower(subject) LIKE ? OR lower(predicate) LIKE ? OR lower(object) LIKE ?
            ORDER BY updated_at DESC
            LIMIT 25
            """,
            (like, like, like),
        ).fetchall()
    return [Fact(**dict(row)) for row in rows]


def _load_context(conn: sqlite3.Connection) -> tuple[str, list[sqlite3.Row]]:
    summary_row = conn.execute(
        "SELECT summary FROM summaries WHERE user = ?", (DEFAULT_USER,)
    ).fetchone()
    summary = summary_row["summary"] if summary_row else ""
    facts = conn.execute(
        "SELECT subject, predicate, object, language, source, updated_at FROM facts "
        "ORDER BY updated_at DESC LIMIT 50"
    ).fetchall()
    return summary, facts


@app.get("/memory/context", response_model=MemoryContext, dependencies=[Depends(_require_token)])
def get_context() -> MemoryContext:
    with _db() as conn:
        summary, facts = _load_context(conn)
    fact_objs = [Fact(**dict(row)) for row in facts]

    lines = []
    if summary:
        lines.append(summary.strip())
    if fact_objs:
        lines.append("Known facts:")
        for f in fact_objs[:20]:
            lines.append(f"- {f.subject} {f.predicate} {f.object}")
    text = "\n".join(lines)

    return MemoryContext(summary=summary, facts=fact_objs, text=text)


_EXTRACTION_SYSTEM_PROMPT = textwrap.dedent(
    """\
    You extract durable facts and update a rolling household summary from a
    voice-assistant conversation transcript. Respond with ONLY a JSON object,
    no prose, matching this schema exactly:
    {"facts": [{"subject": str, "predicate": str, "object": str}], "summary": str}

    Rules:
    - Only extract facts worth remembering across sessions (preferences,
      schedules, names, ongoing situations). Ignore one-off device commands
      like turning on a light or reading a sensor.
    - "summary" is a short (<= 5 sentences) rolling narrative of durable
      household context, written to replace the previous summary in full —
      merge in anything new, drop anything now stale or clearly one-off.
    - If nothing durable was said, return {"facts": [], "summary": "<previous summary unchanged>"}.
    - Never include anything related to alarm systems, security codes, or
      arm/disarm state.
    """
)


async def _run_extraction(transcript: list[TranscriptTurn], previous_summary: str) -> dict:
    convo_text = "\n".join(f"{turn.speaker}: {turn.text}" for turn in transcript)
    user_prompt = f"Previous summary: {previous_summary or '(none yet)'}\n\nTranscript:\n{convo_text}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": EXTRACTION_MODEL,
                "messages": [
                    {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "format": "json",
            },
        )
        response.raise_for_status()
        payload = response.json()

    import json

    content = payload.get("message", {}).get("content", "{}")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"facts": [], "summary": previous_summary}


@app.post("/extract", response_model=ExtractOut, dependencies=[Depends(_require_token)])
async def extract(extract_in: ExtractIn) -> ExtractOut:
    with _db() as conn:
        previous_summary, _ = _load_context(conn)

    result = await _run_extraction(extract_in.transcript, previous_summary)
    facts = result.get("facts") or []
    new_summary = result.get("summary") or previous_summary
    now = _now()

    with _db() as conn:
        for item in facts:
            subject = str(item.get("subject", "")).strip()
            predicate = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()
            if not subject or not predicate or not obj:
                continue
            conn.execute(
                """
                INSERT INTO facts (subject, predicate, object, language, source, conversation_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'poller', ?, ?, ?)
                ON CONFLICT(subject, predicate) DO UPDATE SET
                    object = excluded.object,
                    language = excluded.language,
                    source = excluded.source,
                    conversation_id = excluded.conversation_id,
                    updated_at = excluded.updated_at
                """,
                (subject, predicate, obj, extract_in.language, extract_in.conversation_id, now, now),
            )
        conn.execute(
            """
            INSERT INTO summaries (user, summary, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(user) DO UPDATE SET summary = excluded.summary, updated_at = excluded.updated_at
            """,
            (DEFAULT_USER, new_summary, now),
        )

    return ExtractOut(facts_upserted=len(facts), summary_updated=bool(new_summary))


class ProcessedRunCheck(BaseModel):
    pipeline_id: str
    run_id: str


@app.get("/processed_runs/{pipeline_id}/{run_id}", dependencies=[Depends(_require_token)])
def is_run_processed(pipeline_id: str, run_id: str) -> dict:
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_runs WHERE pipeline_id = ? AND run_id = ?",
            (pipeline_id, run_id),
        ).fetchone()
    return {"processed": row is not None}


@app.post("/processed_runs/{pipeline_id}/{run_id}", dependencies=[Depends(_require_token)])
def mark_run_processed(pipeline_id: str, run_id: str) -> dict:
    with _db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_runs (pipeline_id, run_id, processed_at) VALUES (?, ?, ?)",
            (pipeline_id, run_id, _now()),
        )
    return {"status": "ok"}
