"""Create all SQLite tables from the frozen database contract."""

from src.db.database import init_db


if __name__ == "__main__":
    init_db()
    print("database initialized")
