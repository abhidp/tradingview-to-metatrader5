"""`python -m app` — launch the single-process TV2MT5 engine."""
import asyncio
import sys

from app.engine import run_engine
from app.logging_setup import setup_logging


setup_logging()


def main() -> None:
    try:
        asyncio.run(run_engine())
    except KeyboardInterrupt:
        print("\n⛔ Shutdown requested...")


if __name__ == "__main__":
    main()
