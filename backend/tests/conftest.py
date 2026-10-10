import hashlib
import hmac
import json
import os
import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from urllib.parse import urlencode

TOKEN = "123456:TEST_TOKEN_FOR_LOCAL_TESTS_ONLY"
os.environ["BOT_TOKEN"] = TOKEN
os.environ.setdefault("WEBAPP_URL", "https://example.test")


def signed(uid=101, *, timestamp=None):
    data = {
        "auth_date": str(int(time.time()) if timestamp is None else timestamp),
        "user": json.dumps({"id": uid, "first_name": f"User {uid}", "language_code": "en"}),
    }
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(
        secret, "\n".join(f"{k}={v}" for k, v in sorted(data.items())).encode(), hashlib.sha256
    ).hexdigest()
    return {"X-Init-Data": urlencode(data)}


@pytest.fixture
def api(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from sqlalchemy import insert

    from app.db import models, session
    from app.integrations.telegram import bot as worker
    from app.integrations.telegram import payments
    from app.main import app
    from app.services import (
        chat_service,
        notification_service,
        payment_service,
        review_service,
        trip_service,
        user_service,
    )

    url = os.getenv("TEST_DATABASE_URL") or "sqlite:///" + str(tmp_path / "test.db")
    from app import config

    monkeypatch.setattr(
        config, "_settings", config.get_settings().model_copy(update={"DATABASE_URL": url})
    )
    engine = session.get_engine(url)
    # A PostgreSQL test run receives its own schema, never drops application tables.
    if engine.dialect.name == "postgresql":
        import uuid

        schema = "test_" + uuid.uuid4().hex
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        from sqlalchemy import create_engine

        isolated = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
        original = session.get_engine
        monkeypatch.setattr(
            session,
            "get_engine",
            lambda target=None: isolated if target in (None, url) else original(target),
        )
        engine = isolated
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    # Existing Telegram users retain their IDs during migration. Exercise this
    # compatibility path; new independent identities are tested separately.
    with engine.begin() as conn:
        for uid in (101, 202, 303):
            conn.execute(insert(models.users).values(id=uid, name=f"User {uid}", lang="en"))
            conn.execute(
                insert(models.auth_identities).values(
                    user_id=uid, provider="telegram", subject=str(uid)
                )
            )
        if engine.dialect.name == "postgresql":
            from sqlalchemy import text

            conn.execute(text("SELECT setval(pg_get_serial_sequence('users','id'),303,true)"))
    real_sender = notification_service.safe_send
    sender = AsyncMock()
    for mod in (notification_service, trip_service, chat_service, user_service, review_service):
        if hasattr(mod, "safe_send"):
            monkeypatch.setattr(mod, "safe_send", sender)
    invoice = AsyncMock(return_value="https://example.test/invoice")
    fake_bot = SimpleNamespace(create_invoice_link=invoice)
    monkeypatch.setattr(
        payment_service,
        "get_bot",
        lambda: fake_bot,
    )
    notification_service.PINGED.clear()
    notification_service.FLOOD.clear()
    module = SimpleNamespace(
        db=session.db,
        bot=fake_bot,
        safe_send=sender,
        real_sender=real_sender,
        notification=notification_service,
        PINGED=notification_service.PINGED,
        FLOOD=notification_service.FLOOD,
        start=worker.start,
        cmd_ban=worker.cmd_ban,
        cmd_unban=worker.cmd_unban,
        cmd_stats=worker.cmd_stats,
        paid=payments.paid,
        pre_checkout=payments.pre_checkout,
        send_prompts=notification_service.send_prompts,
        worker=worker,
        engine=engine,
    )
    client = TestClient(app)
    yield client, module
    client.close()
    engine.dispose()
    if engine.dialect.name == "postgresql":
        with original(url).begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def ready(api):
    client, module = api

    def register(uid=101, gender="f"):
        headers = signed(uid)
        assert client.post("/api/rules", headers=headers).status_code == 200
        assert (
                client.post(
                    "/api/register", headers=headers, json={"birth": "1990-01-01", "gender": gender}
                ).status_code
                == 200
        )
        return headers

    return register


@pytest.fixture
def trip(api, ready):
    client, module = api

    def create(**values):
        headers = ready(101)
        assert (
                client.post(
                    "/api/trips", headers=headers, json={"dest": "Madrid", **values}
                ).status_code
                == 200
        )
        return client.get("/api/my", headers=headers).json()["mine"][0]["id"]

    return create
