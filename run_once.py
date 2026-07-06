"""Executa um ciclo único do radar (usado pelo GitHub Actions)."""
from __future__ import annotations

import asyncio
import logging
import sys

from storage import init_db, migrate_json_if_exists

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

if __name__ == "__main__":
    init_db()
    migrate_json_if_exists()

    from main import run_cycle
    asyncio.run(run_cycle())
