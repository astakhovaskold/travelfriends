"""Shared fixed-window limit for expensive, unauthenticated session endpoints."""

import hashlib
import time

from app.constants import AUTH_LOGIN_LIMIT, AUTH_REGISTER_LIMIT
from app.db.session import db
from app.repositories.auth_limits import AuthLimitsRepository


def allow_auth_attempt(address: str, path: str) -> bool:
    now = int(time.time())
    key = hashlib.sha256((address + "|" + path).encode()).hexdigest()
    limit = AUTH_REGISTER_LIMIT if path.endswith("/register") else AUTH_LOGIN_LIMIT

    with db(write=True) as transaction:
        attempts = AuthLimitsRepository(transaction).record_attempt(key, now)

    return attempts <= limit
