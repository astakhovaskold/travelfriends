"""Shared fixed-window limit for expensive, unauthenticated session endpoints."""
import hashlib
import time
from sqlalchemy import case
from app.db.models import auth_limits
from app.db.session import db


def allow_auth_attempt(address, path):
    now = int(time.time())
    key = hashlib.sha256((address+'|'+path).encode()).hexdigest()
    limit = 5 if path.endswith('/register') else 10
    with db(write=True) as c:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert_fn = pg_insert if c.connection.dialect.name=='postgresql' else sqlite_insert
        stmt = insert_fn(auth_limits).values(key=key,attempts=1,window_end=now+60)
        stmt = stmt.on_conflict_do_update(index_elements=[auth_limits.c.key], set_={
            'attempts':case((auth_limits.c.window_end<=now,1),else_=auth_limits.c.attempts+1),
            'window_end':case((auth_limits.c.window_end<=now,now+60),else_=auth_limits.c.window_end),
        }).returning(auth_limits.c.attempts)
        attempts = c.connection.execute(stmt).scalar_one()
        # Expired rows may be removed by any process; keep storage bounded over time.
        c.connection.execute(auth_limits.delete().where(auth_limits.c.window_end<now-3600))
    return attempts<=limit
