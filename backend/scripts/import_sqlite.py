"""Read-only SQLite import into an empty, migrated database.

Usage: python -m scripts.import_sqlite /path/to/backup.db
All inserts happen in one target transaction. Source is never modified.
"""

import argparse
import sqlite3
from app.db.models import auth_identities, metadata, users
from app.db.session import get_engine
from pathlib import Path
from sqlalchemy import func, insert, select, text

LEGACY_TABLES = (
    "users",
    "trips",
    "joins",
    "messages",
    "reports",
    "reviews",
    "blocks",
    "kicked",
    "requests",
    "reactions",
)


def validate_source(source):
    """Reject orphan relationships before touching the target; never discard data."""
    relations = {
        "trips": [("user_id", "users")],
        "joins": [("trip_id", "trips"), ("user_id", "users")],
        "messages": [("trip_id", "trips"), ("user_id", "users")],
        "reports": [("msg_id", "messages"), ("reporter", "users")],
        "reviews": [("trip_id", "trips"), ("from_id", "users"), ("to_id", "users")],
        "blocks": [("user_id", "users"), ("blocked_id", "users")],
        "kicked": [("trip_id", "trips"), ("user_id", "users")],
        "requests": [("trip_id", "trips"), ("user_id", "users")],
        "reactions": [("msg_id", "messages"), ("user_id", "users")],
    }
    problems = []
    for name, keys in relations.items():
        for column, parent in keys:
            system_exception = (
                f'AND child."{column}" != 0' if (name, column) == ("messages", "user_id") else ""
            )
            missing = source.execute(
                f'SELECT DISTINCT child."{column}" FROM "{name}" child LEFT JOIN "{parent}" parent ON parent.id=child."{column}" WHERE parent.id IS NULL {system_exception} LIMIT 10'
            ).fetchall()
            if missing:
                problems.append(
                    f"{name}.{column}: missing {parent} IDs {[row[0] for row in missing]}"
                )
    if problems:
        raise ValueError(
            "Legacy data contains orphan references. Repair a COPY of the backup and retry: "
            + "; ".join(problems)
        )


def import_sqlite(source_path, engine=None):
    engine = engine or get_engine()
    source_path = Path(source_path).resolve(strict=True)
    source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    counts = {}
    try:
        with engine.begin() as target:
            for table in metadata.sorted_tables:
                if target.execute(select(func.count()).select_from(table)).scalar_one():
                    raise ValueError(f"Target is not empty: {table.name}")
            existing = {
                r[0] for r in source.execute("select name from sqlite_master where type='table'")
            }
            missing = set(LEGACY_TABLES) - existing
            if missing:
                raise ValueError(f"Source tables missing: {sorted(missing)}")
            validate_source(source)
            for name in LEGACY_TABLES:
                table = metadata.tables[name]
                rows = []
                for source_row in source.execute(f'SELECT * FROM "{name}"'):
                    row = {k: v for k, v in dict(source_row).items() if k in table.c}
                    # Legacy nullable strings become explicit schema defaults.
                    row = {k: v for k, v in row.items() if v is not None or table.c[k].nullable}
                    rows.append(row)
                for row in rows:
                    target.execute(insert(table).values(**row))
                counts[name] = len(rows)
            identities = [
                {"user_id": r["id"], "provider": "telegram", "subject": str(r["id"])}
                for r in target.execute(select(users.c.id)).mappings()
            ]
            if identities:
                target.execute(insert(auth_identities), identities)
            if engine.dialect.name == "postgresql":
                # Explicit IDs do not move PostgreSQL sequences automatically.
                for name in ("users", "trips", "messages", "reviews", "auth_identities"):
                    target.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{name}','id'), COALESCE((SELECT max(id) FROM {name}),1), EXISTS(SELECT 1 FROM {name}))"
                        )
                    )
    finally:
        source.close()
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    print(import_sqlite(args.source))
