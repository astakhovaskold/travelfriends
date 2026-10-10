"""Atomic fixed-window counters shared by all API processes."""

from app.constants import AUTH_LIMIT_RETENTION, AUTH_LIMIT_WINDOW
from app.db.models import auth_limits
from app.db.session import Transaction
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


class AuthLimitsRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def record_attempt(self, key: str, now: int) -> int:
        insert_fn = (
            pg_insert if self.transaction.connection.dialect.name == "postgresql" else sqlite_insert
        )
        statement = insert_fn(auth_limits).values(
            key=key, attempts=1, window_end=now + AUTH_LIMIT_WINDOW
        )
        statement = statement.on_conflict_do_update(
            index_elements=[auth_limits.c.key],
            set_={
                "attempts": case(
                    (auth_limits.c.window_end <= now, 1), else_=auth_limits.c.attempts + 1
                ),
                "window_end": case(
                    (auth_limits.c.window_end <= now, now + AUTH_LIMIT_WINDOW),
                    else_=auth_limits.c.window_end,
                ),
            },
        ).returning(auth_limits.c.attempts)
        attempts = self.transaction.connection.execute(statement).scalar_one()
        self.transaction.connection.execute(
            auth_limits.delete().where(auth_limits.c.window_end < now - AUTH_LIMIT_RETENTION)
        )
        return attempts
