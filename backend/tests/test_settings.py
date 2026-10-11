import pytest

from app import config
from app.config import Settings, load_settings


def test_settings_defaults_and_database_normalization(tmp_path):
    settings = load_settings({"ENV_FILE": str(tmp_path / "missing.env")})
    assert settings.BOT_TOKEN == ""
    assert settings.ADMIN_ID == 0
    assert settings.BOOST_STARS == 50
    assert settings.SESSION_TTL == 2592000
    assert settings.DATABASE_URL == settings.MIGRATION_DATABASE_URL == "sqlite:///data.db"
    assert settings.CORS_ORIGINS == ()
    assert (
            Settings(DATABASE_URL="postgres://localhost/example").DATABASE_URL
            == "postgresql+psycopg://localhost/example"
    )
    assert (
            Settings(DATABASE_URL="postgresql://localhost/example").MIGRATION_DATABASE_URL
            == "postgresql+psycopg://localhost/example"
    )
    assert (
            Settings(MIGRATION_DATABASE_URL="postgres://localhost/migrations").MIGRATION_DATABASE_URL
            == "postgresql+psycopg://localhost/migrations"
    )


def test_environment_wins_without_mutating_process_environment(tmp_path, monkeypatch):
    dotenv = tmp_path / "settings.env"
    dotenv.write_text("BOOST_STARS=75\nADMIN_ID=42\nBOT_TOKEN=file-token\n")
    monkeypatch.delenv("BOOST_STARS", raising=False)
    settings = load_settings({"ENV_FILE": str(dotenv), "BOOST_STARS": "100"})
    assert settings.BOOST_STARS == 100
    assert settings.ADMIN_ID == 42
    assert settings.BOT_TOKEN == "file-token"
    assert "BOOST_STARS" not in config.os.environ
    assert load_settings({"ENV_FILE": str(dotenv), "ADMIN_ID": ""}).ADMIN_ID == 0


@pytest.mark.parametrize(
    "name,value",
    [
        ("BOOST_STARS", "0"),
        ("BOOST_STARS", "-1"),
        ("SESSION_TTL", "0"),
        ("SESSION_TTL", "-5"),
        ("ADMIN_ID", "not-a-number"),
    ],
)
def test_invalid_settings_name_is_reported_without_inputs(tmp_path, name, value):
    with pytest.raises(ValueError) as error:
        load_settings(
            {
                "ENV_FILE": str(tmp_path / "absent"),
                name: value,
                "BOT_TOKEN": "secret-bot-token",
                "DATABASE_URL": "postgres://secret-password@localhost/db",
            }
        )
    message = str(error.value)
    assert name in message
    assert "secret" not in message
    assert "input_value" not in message
    assert "secret" not in repr(
        Settings(BOT_TOKEN="secret", DATABASE_URL="postgres://secret@localhost/db")
    )


def test_settings_can_be_replaced_without_environment_changes(monkeypatch):
    replacement = Settings(ADMIN_ID=700, CORS_ORIGINS="https://frontend.example/")
    monkeypatch.setattr(config, "_settings", replacement)
    assert config.get_settings() is replacement
    assert config.get_settings().CORS_ORIGINS == ("https://frontend.example",)


def test_dotenv_interpolation_preserves_environment_priority(tmp_path, monkeypatch):
    dotenv = tmp_path / "settings.env"
    dotenv.write_text(
        "BOOST_STARS=75\nSESSION_TTL=${BOOST_STARS}\nBOT_USERNAME=${MISSING:-fallback}\nEMPTY\n"
    )
    monkeypatch.setenv("BOOST_STARS", "100")
    monkeypatch.delenv("SESSION_TTL", raising=False)
    monkeypatch.delenv("BOT_USERNAME", raising=False)
    monkeypatch.delenv("MISSING", raising=False)
    monkeypatch.setenv("ENV_FILE", str(dotenv))
    assert load_settings().SESSION_TTL == 100
    # Explicit mappings are isolated from process variables, including interpolation.
    settings = load_settings({"ENV_FILE": str(dotenv), "BOOST_STARS": "120"})
    assert settings.SESSION_TTL == 120
    assert settings.BOT_USERNAME == "fallback"
    assert load_settings({"ENV_FILE": str(dotenv)}).SESSION_TTL == 75


def test_default_dotenv_is_backend_local_even_from_repository_root(tmp_path, monkeypatch):
    backend = tmp_path / "backend"
    backend.mkdir()
    (tmp_path / ".env.local").write_text("BOOST_STARS=10\n")
    (backend / ".env.local").write_text("BOOST_STARS=75\n")
    monkeypatch.setattr(config, "BACKEND_ROOT", backend)
    monkeypatch.chdir(tmp_path)
    assert load_settings({}).BOOST_STARS == 75
