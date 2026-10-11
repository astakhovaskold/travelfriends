"""Validated deployment settings, loaded without modifying the process environment."""

import json
import os
from collections.abc import Mapping
from dotenv import dotenv_values
from dotenv.variables import parse_variables
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from urllib.parse import urlsplit

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def database_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore", hide_input_in_errors=True)

    BOT_USERNAME: str = ""
    BOT_TOKEN: str = Field(default="", repr=False)
    WEBAPP_URL: str = "http://localhost:5173"
    BOOST_STARS: int = Field(default=50, gt=0)
    ADMIN_ID: int = 0
    DATABASE_URL: str = Field(default="sqlite:///data.db", repr=False)
    MIGRATION_DATABASE_URL: str | None = Field(default=None, repr=False)
    SESSION_TTL: int = Field(default=2592000, gt=0)
    CORS_ORIGINS: tuple[str, ...] = ()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                value = json.loads(value)
            else:
                value = value.split(",")
        if not isinstance(value, (list, tuple)):
            raise ValueError("Use comma-separated HTTP(S) origins or a JSON array")
        origins = []
        for item in value:
            origin = item.strip().strip("\"'").strip().rstrip("/")
            if not origin:
                continue
            parsed = urlsplit(origin)
            if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                    or any(char.isspace() for char in origin)
            ):
                raise ValueError("Each CORS origin must be an HTTP(S) URL without a path")
            origins.append(origin)
        return tuple(origins)

    @field_validator("ADMIN_ID", mode="before")
    @classmethod
    def empty_admin_id(cls, value: object) -> object:
        return 0 if value == "" else value

    @field_validator("DATABASE_URL", "MIGRATION_DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        return database_url(value) if value is not None else None

    @model_validator(mode="after")
    def migration_fallback(self) -> "Settings":
        if self.MIGRATION_DATABASE_URL is None:
            object.__setattr__(self, "MIGRATION_DATABASE_URL", self.DATABASE_URL)
        return self


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Environment wins over the selected dotenv file; tests may supply their own mapping."""
    environment = dict(os.environ if environ is None else environ)
    path = environment.get("ENV_FILE", str(BACKEND_ROOT / ".env.local"))
    values: dict[str, str | None] = {}
    for key, value in dotenv_values(path, interpolate=False).items():
        # Match load_dotenv(override=False), including ${VAR:-default} expansion.
        resolution = {**values, **environment}
        values[key] = (
            "".join(atom.resolve(resolution) for atom in parse_variables(value))
            if value is not None
            else None
        )
    values = {key: value for key, value in values.items() if value is not None}
    values.update(environment)

    try:
        return Settings.model_validate(values)
    except ValidationError as error:
        # Never interpolate inputs: database URLs and tokens can contain secrets.
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        raise ValueError(f"Invalid application settings: {details}") from None


_settings = load_settings()


def get_settings() -> Settings:
    """Single runtime accessor; replace _settings in tests without touching os.environ."""
    return _settings
