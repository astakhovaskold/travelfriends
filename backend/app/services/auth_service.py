"""Account and session scenarios; transport dependencies live in the API."""

import base64
import hashlib
import hmac
import re
import secrets
import time
from app import errors
from app.config import get_settings
from app.db.session import db
from app.integrations.telegram.auth import verify_init_data
from app.repositories.auth import AuthRepository
from app.schemas.auth import EmailLogin, EmailRegister, TelegramLogin
from app.services.common import lang_of
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from threading import BoundedSemaphore


def check_user(row):
    if row is None:
        raise HTTPException(401, errors.UNAUTHORIZED)
    if row["banned"]:
        raise HTTPException(403, errors.BANNED)
    if row["minor"]:
        raise HTTPException(403, errors.MINOR)

    return dict(row)


def telegram_user(init_data: str) -> dict:
    info = verify_init_data(init_data)

    with db(write=True) as transaction:
        repository = AuthRepository(transaction)
        identity = repository.telegram_identity(str(info["id"]))
        if identity:
            user_id = identity["user_id"]
        else:
            user_id = repository.create_telegram_user(
                info.get("first_name", ""), info.get("username"), lang_of(info.get("language_code"))
            )
            repository.attach_telegram_identity(user_id, str(info["id"]))
        repository.update_telegram_user(
            info.get("first_name", ""),
            info.get("username"),
            lang_of(info.get("language_code")),
            user_id,
        )
        return check_user(repository.get_user(user_id))


def get_current_user(authorization: str = "", x_init_data: str = "") -> dict:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, errors.UNAUTHORIZED)
        with db() as transaction:
            row = AuthRepository(transaction).session_user(
                hashlib.sha256(token.encode()).hexdigest(), int(time.time())
            )
        return check_user(row)
    if x_init_data:
        try:
            return telegram_user(x_init_data)
        except IntegrityError:
            return telegram_user(x_init_data)
    raise HTTPException(401, errors.UNAUTHORIZED)


def ensure_ready(user: dict) -> None:
    with db() as transaction:
        row = AuthRepository(transaction).registration_state(user["id"])
    if not row["rules_ok"]:
        raise HTTPException(403, errors.RULES)
    if not row["registered"]:
        raise HTTPException(403, errors.REGISTER)


def issue_session(user: dict) -> dict:
    token = secrets.token_urlsafe(32)
    expires = int(time.time()) + get_settings().SESSION_TTL

    with db() as transaction:
        AuthRepository(transaction).create_session(
            hashlib.sha256(token.encode()).hexdigest(), user["id"], expires
        )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires,
        "user_id": user["id"],
    }


def exchange_telegram(body: TelegramLogin):
    try:
        user = telegram_user(body.init_data)
    except IntegrityError:
        user = telegram_user(body.init_data)

    return issue_session(user)


def logout(user: dict, authorization: str = "") -> dict:
    _, _, token = authorization.partition(" ")
    if token:
        with db() as transaction:
            AuthRepository(transaction).delete_session(
                hashlib.sha256(token.encode()).hexdigest(), user["id"]
            )

    return {"ok": True}


_hash_slots = BoundedSemaphore(2)


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch("[^\\s@]+@[^\\s@]+\\.[^\\s@]+", value):
        raise HTTPException(422, errors.INVALID_EMAIL)

    return value


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    if not _hash_slots.acquire(blocking=False):
        raise HTTPException(429, errors.SLOW)
    try:
        digest = hashlib.scrypt(
            password.encode(), salt=salt, n=2 ** 17, r=8, p=1, maxmem=256 * 1024 * 1024
        )
    finally:
        _hash_slots.release()

    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def email_register(body: EmailRegister):
    email = normalize_email(body.email)
    if not body.name.strip():
        raise HTTPException(422, errors.INVALID_NAME)
    encoded = password_hash(body.password)
    try:
        with db(write=True) as transaction:
            repository = AuthRepository(transaction)
            user_id = repository.create_email_user(body.name.strip())
            repository.attach_email_identity(user_id, email, encoded)
    except IntegrityError:
        raise HTTPException(409, errors.EMAIL_IN_USE)

    return issue_session({"id": user_id})


def email_login(body: EmailLogin):
    email = normalize_email(body.email)

    with db() as transaction:
        row = AuthRepository(transaction).email_identity(email)

    salt = base64.b64decode(row["password_hash"].split("$")[1]) if row else b"\x00" * 16
    actual = password_hash(body.password, salt)
    if row is None or not hmac.compare_digest(actual, row["password_hash"]):
        raise HTTPException(401, errors.INVALID_CREDENTIALS)

    with db() as transaction:
        user = check_user(AuthRepository(transaction).get_user(row["user_id"]))

    return issue_session(user)


def link_telegram(body: TelegramLogin, user: dict) -> dict:
    info = verify_init_data(body.init_data)
    try:
        with db(write=True) as transaction:
            repository = AuthRepository(transaction)
            transaction.lock_user(user["id"])
            existing = repository.telegram_identity(str(info["id"]))
            if existing and existing["user_id"] != user["id"]:
                raise HTTPException(409, errors.IDENTITY_IN_USE)
            if not existing:
                attached = repository.attached_telegram_identity(user["id"])
                if attached:
                    raise HTTPException(409, errors.TELEGRAM_ALREADY_LINKED)
                repository.attach_telegram_identity(user["id"], str(info["id"]))
    except IntegrityError:
        raise HTTPException(409, errors.IDENTITY_IN_USE)

    return {"ok": True}
