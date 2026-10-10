"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.models import auth_identities, sessions, users
from app.db.session import Transaction
from collections.abc import Mapping
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.engine import Row as SQLAlchemyRow
from typing import Any


class AuthRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def telegram_identity(self, subject: str) -> Mapping[str, Any] | None:
        return (
            self.transaction.connection.execute(
                select(auth_identities).where(
                    auth_identities.c.provider == "telegram", auth_identities.c.subject == subject
                )
            )
            .mappings()
            .first()
        )

    def create_telegram_user(self, name: str, username: str | None, lang: str) -> int:
        return self.transaction.connection.execute(
            insert(users).values(name=name, username=username, lang=lang).returning(users.c.id)
        ).scalar_one()

    def attach_telegram_identity(self, user_id: int, subject: str) -> CursorResult:
        return self.transaction.connection.execute(
            insert(auth_identities).values(user_id=user_id, provider="telegram", subject=subject)
        )

    def update_telegram_user(
            self, name: str, username: str | None, lang: str, user_id: int
    ) -> CursorResult:
        return self.transaction.connection.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(name=name, username=username, lang=lang)
        )

    def get_user(self, user_id: int) -> Mapping[str, Any] | None:
        return (
            self.transaction.connection.execute(select(users).where(users.c.id == user_id))
            .mappings()
            .first()
        )

    def session_user(self, token_hash: str, expires_at: int) -> Mapping[str, Any] | None:
        return (
            self.transaction.connection.execute(
                select(users)
                .join(sessions)
                .where(sessions.c.token_hash == token_hash, sessions.c.expires_at > expires_at)
            )
            .mappings()
            .first()
        )

    def registration_state(self, user_id: int) -> Mapping[str, Any]:
        return (
            self.transaction.connection.execute(
                select(users.c.rules_ok, users.c.registered).where(users.c.id == user_id)
            )
            .mappings()
            .one()
        )

    def create_session(self, token_hash: str, user_id: int, expires_at: int) -> CursorResult:
        return self.transaction.connection.execute(
            insert(sessions).values(token_hash=token_hash, user_id=user_id, expires_at=expires_at)
        )

    def delete_session(self, token_hash: str, user_id: int) -> CursorResult:
        return self.transaction.connection.execute(
            delete(sessions).where(
                sessions.c.token_hash == token_hash, sessions.c.user_id == user_id
            )
        )

    def create_email_user(self, name: str) -> int:
        return self.transaction.connection.execute(
            insert(users).values(name=name).returning(users.c.id)
        ).scalar_one()

    def attach_email_identity(self, user_id: int, subject: str, password_hash: str) -> CursorResult:
        return self.transaction.connection.execute(
            insert(auth_identities).values(
                user_id=user_id, provider="email", subject=subject, password_hash=password_hash
            )
        )

    def email_identity(self, subject: str) -> Mapping[str, Any] | None:
        return (
            self.transaction.connection.execute(
                select(auth_identities).where(
                    auth_identities.c.provider == "email", auth_identities.c.subject == subject
                )
            )
            .mappings()
            .first()
        )

    def attached_telegram_identity(self, user_id: int) -> SQLAlchemyRow | None:
        return self.transaction.connection.execute(
            select(auth_identities.c.id).where(
                auth_identities.c.user_id == user_id, auth_identities.c.provider == "telegram"
            )
        ).first()
