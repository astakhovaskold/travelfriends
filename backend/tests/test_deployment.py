import pytest
from app import config, main
from app.config import Settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


@pytest.mark.parametrize(
    "value",
    [
        "https://frontend.example",
        '"https://frontend.example\n\n"',
        '["https://frontend.example"]',
    ],
)
def test_real_app_cors_from_environment(value, monkeypatch):
    monkeypatch.setattr(config, "_settings", Settings(CORS_ORIGINS=value))
    client = TestClient(main.create_app())
    response = client.options(
        "/api/auth/register",
        headers={
            "Origin": "https://frontend.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-init-data,authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example"
    denied = client.options(
        "/api/auth/register",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_health_rejects_empty_database(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "empty.db"))
    monkeypatch.setattr(main, "get_engine", lambda: engine)
    assert TestClient(main.app).get("/health").status_code == 503
    engine.dispose()


def test_health_rejects_missing_auth_limits(api):
    client, state = api
    with state.engine.begin() as connection:
        connection.execute(text("DROP TABLE auth_limits"))
    assert client.get("/health").status_code == 503


def test_health_rejects_outdated_migration(api):
    client, state = api
    with state.engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='old'"))
    assert client.get("/health").status_code == 503


def test_registration_and_rate_limit_include_cors_headers(api, monkeypatch):
    monkeypatch.setattr(
        config,
        "_settings",
        config.get_settings().model_copy(update={"CORS_ORIGINS": ("https://frontend.example",)}),
    )
    client = TestClient(main.create_app())
    origin = {"Origin": "https://frontend.example"}
    response = client.post(
        "/api/auth/register",
        headers=origin,
        json={
            "email": "cors@example.test",
            "password": "a-test-password-123",
            "name": "Test",
        },
    )
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == origin["Origin"]
    from app.services import auth_limit_service

    monkeypatch.setattr(auth_limit_service, "allow_auth_attempt", lambda *_: False)
    response = client.post("/api/auth/register", headers=origin, json={})
    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == origin["Origin"]


@pytest.mark.parametrize("value", ["*", "frontend.example", "https://frontend.example/api"])
def test_invalid_cors_configuration_is_rejected(value):
    with pytest.raises(ValueError):
        Settings(CORS_ORIGINS=value)
