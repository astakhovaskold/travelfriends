from app.main import app
from fastapi.testclient import TestClient


def test_api_lifecycle_does_not_start_telegram(api, monkeypatch):
    _, m = api

    def forbidden():
        raise AssertionError("API must not initialize Telegram")

    monkeypatch.setattr(m.worker, "get_bot", forbidden)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/config").status_code == 200
        assert client.get("/").status_code == 404
        assert client.get("/api/config").status_code == 200


def test_standalone_worker_requires_token_and_registers_payment_handlers(monkeypatch):
    import runpy

    import pytest

    from app import config
    from app.integrations.telegram.bot import dp

    monkeypatch.setattr(
        config, "_settings", config.get_settings().model_copy(update={"BOT_TOKEN": ""})
    )
    with pytest.raises(RuntimeError, match="BOT_TOKEN is required"):
        runpy.run_module("app.worker", run_name="__main__")
    assert dp.pre_checkout_query.handlers
    assert any(handler.callback.__name__ == "paid" for handler in dp.message.handlers)
