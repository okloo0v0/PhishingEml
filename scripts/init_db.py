"""Create all SQLite tables from the frozen database contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.database import init_db


if __name__ == "__main__":
    init_db()
    print("database initialized")
