"""`python -m app` — launch the single-process TV2MT5 engine."""
import asyncio
import logging

from app.engine import run_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> None:
    try:
        asyncio.run(run_engine())
    except KeyboardInterrupt:
        print("\n⛔ Shutdown requested...")


if __name__ == "__main__":
    main()
