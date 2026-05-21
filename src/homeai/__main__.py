from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from homeai.agent_brain import Memory, run_pipeline
from homeai.config import settings


def _setup_logging() -> None:
    """Configure the root logger from settings."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.log_file, encoding="utf-8"),
        ],
    )


async def _run() -> None:
    """Interactive REPL loop that processes user input through the ReAct pipeline."""
    memory = Memory(settings.memory_db_path, settings.memory_window)
    print("HomeAI ready. Type in Polish or English. Ctrl+C or Ctrl+D to exit.\n")
    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break
            if not user_input:
                continue
            response = await run_pipeline(user_input, memory)
            print(f"HomeAI: {response}\n")
    finally:
        memory.close()


def main() -> None:
    """Entry point for the homeai console script."""
    _setup_logging()

    def _handle_sigterm(signum: int, frame: Any) -> None:
        """Translate SIGTERM into KeyboardInterrupt for uniform graceful shutdown."""
        raise KeyboardInterrupt

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nGoodbye / Do widzenia.")


if __name__ == "__main__":
    main()
