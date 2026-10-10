import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from conftest import TOKEN, signed


def test_telegram_exchange_and_logout(api):
    c, m = api
    result = c.post("/api/auth/telegram", json={"init_data": signed()["X-Init-Data"]})
    assert result.status_code == 200
    data = result.json()
    assert data["user_id"] == 101
    h = {"Authorization": "Bearer " + data["access_token"]}
    assert c.get("/api/me", headers=h).json()["id"] == 101
    with m.db() as db:
        stored = db.execute("select token_hash from sessions").fetchone()[0]
        assert stored == hashlib.sha256(data["access_token"].encode()).hexdigest()
    assert c.post("/api/auth/logout", headers=h).status_code == 200
    assert c.get("/api/me", headers=h).status_code == 401


def test_new_telegram_identity_has_internal_id(api):
    c, _ = api
    r = c.post("/api/auth/telegram", json={"init_data": signed(999999)["X-Init-Data"]})
    assert r.status_code == 200 and r.json()["user_id"] != 999999
    again = c.post("/api/auth/telegram", json={"init_data": signed(999999)["X-Init-Data"]})
    assert again.json()["user_id"] == r.json()["user_id"]


def test_email_signup_login_and_registration(api):
    c, _ = api
    body = {"email": "Test@example.test", "password": "a-test-password-123", "name": "Astrid"}
    r = c.post("/api/auth/register", json=body)
    assert r.status_code == 201
    assert c.post("/api/auth/register", json=body).status_code == 409
    login = c.post("/api/auth/login", json=body)
    assert login.status_code == 200 and login.json()["user_id"] == r.json()["user_id"]
    assert (
            c.post("/api/auth/login", json={**body, "password": "wrong-password-123"}).status_code
            == 401
    )
    h = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert c.get("/api/trips", headers=h).status_code == 403
    assert c.post("/api/rules", headers=h).status_code == 200
    assert (
            c.post("/api/register", headers=h, json={"birth": "1990-01-01", "gender": "f"}).status_code
            == 200
    )
    assert c.get("/api/trips", headers=h).status_code == 200


def test_expired_session_and_no_invalid_bearer_fallback(api):
    c, m = api
    data = c.post("/api/auth/telegram", json={"init_data": signed()["X-Init-Data"]}).json()
    h = {"Authorization": "Bearer " + data["access_token"]}
    with m.db() as db:
        db.execute("update sessions set expires_at=0")
    assert c.get("/api/me", headers=h).status_code == 401
    assert c.get("/api/me", headers={**signed(), "Authorization": "Bearer bad"}).status_code == 401


def test_malformed_signed_init_data(api):
    c, _ = api
    cases = [
        {"auth_date": "bad", "user": json.dumps({"id": 101})},
        {"auth_date": str(int(time.time()) + 3600), "user": json.dumps({"id": 101})},
        {"auth_date": str(int(time.time())), "user": "bad"},
        {"auth_date": str(int(time.time())), "user": "{}"},
    ]
    for data in cases:
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        data["hash"] = hmac.new(
            secret, "\n".join(f"{k}={v}" for k, v in sorted(data.items())).encode(), hashlib.sha256
        ).hexdigest()
        assert c.get("/api/me", headers={"X-Init-Data": urlencode(data)}).status_code == 401


def test_auth_attempt_limit(api):
    c, _ = api
    for _ in range(10):
        assert c.post("/api/auth/telegram", json={"init_data": "invalid"}).status_code == 401
    r = c.post("/api/auth/telegram", json={"init_data": "invalid"})
    assert r.status_code == 429 and r.headers["Retry-After"] == "60"


def test_password_hash_concurrency_is_bounded(api):
    import pytest
    from fastapi import HTTPException

    from app.services import auth_service as auth

    assert auth._hash_slots.acquire(blocking=False)
    assert auth._hash_slots.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as failure:
            auth.password_hash("valid-password-123")
        assert failure.value.status_code == 429
    finally:
        auth._hash_slots.release()
        auth._hash_slots.release()


def test_link_telegram_requires_ownership(api):
    c, _ = api
    data = c.post(
        "/api/auth/register",
        json={"email": "link@example.test", "password": "test-password-123", "name": "Web user"},
    ).json()
    h = {"Authorization": "Bearer " + data["access_token"]}
    assert (
            c.post(
                "/api/auth/link/telegram", headers=h, json={"init_data": signed()["X-Init-Data"]}
            ).status_code
            == 409
    )
    assert (
            c.post(
                "/api/auth/link/telegram", headers=h, json={"init_data": signed(777777)["X-Init-Data"]}
            ).status_code
            == 200
    )
    linked = c.post("/api/auth/telegram", json={"init_data": signed(777777)["X-Init-Data"]}).json()
    assert linked["user_id"] == data["user_id"]
