# Automated test matrix + soak-test logging — Task 7 (M6)

This doc records what Task 7 actually built and found. The two code
deliverables are `heimdall/tests/test_matrix.py` (a live regression suite,
run on demand) and `heimdall/scripts/ntfy_failure_logger.py` (a long-running
poller for slower-cadence soak testing). Both are standalone scripts, not
pytest-collected — `pyproject.toml`'s `testpaths = ["tests"]` only covers
the repo-root offline unit tests, and these two need real, live
infrastructure (a running HA instance, Ollama, ntfy) to mean anything.

## `heimdall/tests/test_matrix.py`

Implements one row per entity-domain from the brief, each run for every
language (EN/PL) × conversation agent (Gemini, qwen2.5:7b-instruct) where
that combination makes sense, via HA's `conversation.process` REST API.

```bash
HEIMDALL_HA_TOKEN=<HA long-lived access token> \
HEIMDALL_NTFY_TOKEN=<ntfy heimdall_bot token, optional> \
python heimdall/tests/test_matrix.py
```

`HEIMDALL_HA_URL` (default `http://192.168.0.108:8123`), `HEIMDALL_HA_WS_URL`
(default `ws://192.168.0.108:8123/api/websocket`), `HEIMDALL_NTFY_URL`
(default `https://ntfy.kamilonet.win` — see `ntfy_failure_logger.py`'s
docstring for the exact host) and `HEIMDALL_NTFY_TOPIC` (default
`heimdall-failures`) can all be overridden. Pass `--allow-calendar-write` to
also exercise a real Gemini calendar write (see below for why this is
opt-in). Pass `--allow-physical-actuation` to also actually toggle the
office light/aquarium filter and change the bedroom radiator setpoint (see
below — also opt-in, off by default since 2026-08-20).

### Documented deviations from the original brief

- **`gate`**: exposure-check only (confirms
  `switch.brama_sonoff_100254194e_1` is still `should_expose: true` via HA's
  WebSocket `homeassistant/expose_entity/list`), not live physical
  actuation, and language-agnostic (a single check, not one per language).
  The user explicitly rejected repeatedly cycling a real gate unattended for
  soak testing.
- **`calendar_write_other`**: marked N/A / not implementable. Only one
  Google Calendar account is connected (confirmed live via `/api/states`)
  — Task 5 never set up a second one, and the brief's two-account
  assumption doesn't match what's actually deployed. Confirmed with the
  user to leave this out rather than fake a second account.
- **`calendar_write_own`**: Gemini's half is **skipped by default**. There
  is no `calendar.delete_event` service in this HA version (confirmed via
  `GET /api/services`), so a real Gemini write leaves a permanent event on
  the real calendar with no automated cleanup path — only runs with
  `--allow-calendar-write`, and the resulting event then needs manual
  deletion via Google Calendar's own UI. qwen's half always runs (no
  opt-in needed) since qwen is expected to **honestly refuse** rather than
  write anything — verified by checking the calendar for the *absence* of a
  uniquely-tagged marker event, not by string-matching the refusal wording
  (HA's `response_type` stays `"action_done"` even for an honest refusal, so
  text-matching would be fragile).
- **`ambiguous_mixed_language`**: a single soft check per agent (not
  multiplied by language, since the row is inherently about mixed-language
  input).
- Write-type rows (`light_switch`, `climate`, `aquarium_write`) are
  **skipped by default** (added 2026-08-20, once the daily systemd timer
  made unattended real toggling of the office light/radiator/aquarium
  filter an actual nuisance rather than a one-off manual run). Pass
  `--allow-physical-actuation` to exercise them for real - when they do run,
  they still capture state before speaking the command, verify the change,
  then restore the original value directly via REST (not via voice) so
  repeated runs stay idempotent regardless of which state they started in.

### Real bugs found and fixed by this test's first live run (2026-08-20)

Running the matrix for the first time surfaced two genuine, previously
unknown entity-naming regressions — not test-code bugs. Full detail (exact
entity IDs, root causes, and the fix) is in `HA_CONFIG_CHANGES.md` section
9; summary:

1. **A phantom Tuya light/fan pair was winning fuzzy voice-matching over
   the real relay it's wired behind**, silently "succeeding" against an
   unreachable entity for both agents and both languages. Fixed by hiding
   both from Assist exposure in `expose_entities.py`.
2. **The bedroom radiator has no English name**, only a Polish compound
   word — Gemini already handled this fine via its fuzzier matching; qwen
   did not. An alias was tried (see below) but ultimately didn't fix it.

### Known, accepted qwen-only limitations (not fixed further)

After the fix above, two more qwen-specific gaps were found and discussed
with the user rather than unilaterally patched further (three fix attempts
in a row revealing new distinct issues each time triggered this project's
"stop and discuss" escalation rule):

- **`light_switch` (qwen, both languages)**: qwen resolves "office light" to
  `switch.office_led` — a real, separate TP-Link device (a lamp/LED strip,
  confirmed by the user, genuinely controllable) — instead of the intended
  relay. Gemini correctly resolves the relay in both languages. Accepted as
  a permanent qwen limitation: `office_led` is a real, wanted device with a
  legitimately similar name, so there's no more hiding/renaming to do here
  without breaking something else.
- **`climate` (qwen, both languages)**: adding an English alias to the
  radiator entity didn't fix qwen's resolution — with two aliases, qwen
  garbled them into one malformed search string; with the alias reverted to
  a single one, qwen still failed to resolve it. Aliases appear to only
  feed HA's built-in intent matcher (which Gemini's built-in tools use),
  not whatever tool schema qwen's Ollama-based conversation agent actually
  queries.

Both are reported as `KNOWN-LIM` in the test matrix's output — visibly
distinct from `PASS`/`FAIL`, not silently hidden, and **not** counted toward
the suite's exit code or published to `ntfy` — since silently marking a real
resolution failure as a pass would hide a genuine regression if the
underlying cause ever changed. See `KNOWN_QWEN_LIMITATIONS` in
`test_matrix.py` for the exact wording kept in sync with this doc.

### Gemini free-tier rate limit (observed, not a bug in this code)

A full run makes ~13 Gemini calls in quick succession, close to the
free-tier ceiling (`generate_content_free_tier_requests`, 15
requests/minute for `gemini-3.1-flash-lite`) — one run hit an explicit `429
RESOURCE_EXHAUSTED` on a single row. A retry after a short wait passed
cleanly. This is a real constraint on how quickly the matrix can be re-run
back-to-back, not something the code can silently work around (adding
retries/backoff was considered unnecessary complexity for what's an
on-demand diagnostic script — the poller-based soak path below runs at a
far slower, non-rate-limiting cadence).

### Final verified result (2026-08-20)

```
25/25 implementable checks passed (1 N/A, 2 skipped-by-default, 4 known-limitation)
```

## `heimdall/scripts/ntfy_failure_logger.py`

A long-running poller for slower-cadence soak testing, independent of the
on-demand `test_matrix.py` run above (though `test_matrix.py` publishes to
the same topic when `HEIMDALL_NTFY_TOKEN` is set).

```bash
HEIMDALL_NTFY_TOKEN=<ntfy heimdall_bot token> \
python heimdall/scripts/ntfy_failure_logger.py
```

Polls ntfy's `since=<last-seen message id>&poll=1` endpoint (a
point-in-time poll, not a long-lived stream connection — verified against
ntfy's own docs before implementing, since a dropped stream connection would
otherwise silently lose messages) at
`HEIMDALL_NTFY_POLL_INTERVAL_SECONDS` (default 60s), persists the last-seen
message ID to `HEIMDALL_NTFY_STATE_PATH`, and appends every failure to
`heimdall/SOAK_LOG.md` (`HEIMDALL_SOAK_LOG_PATH`).

### ntfy provisioning (`nemo-ntfy`, on vesemir)

`nemo-ntfy` runs with `auth-default-access: deny-all` (confirmed in
`ProjectNemo`'s `ntfy/server.yml`) — no users or tokens existed at all
before this task. Provisioned live via SSH:

```bash
ntfy user add --role=user heimdall_bot
ntfy access heimdall_bot heimdall-failures rw
ntfy token add heimdall_bot > /tmp/heimdall_ntfy_token.txt   # never printed to a terminal directly
```

The token file was copied to a local temp file and then deleted from
`vesemir`, matching this project's established secret-handling pattern (the
long-lived HA token used the same technique). One token had to be revoked
and regenerated after an earlier attempt printed the plaintext value
directly in tool output — `ntfy token add`'s output is not auto-redacted
the way some other secrets are.

## Outstanding manual item

The real Google Calendar still has a stray test event, **"Gemini regression
check"** (2026-08-20, 20:00–21:00), left over from earlier Task 5 testing.
No `calendar.delete_event` service exists in this HA version, so it needs
manual deletion via Google Calendar's own UI — flagged here rather than
silently left for the next person to be confused by.
