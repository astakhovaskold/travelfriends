from app.db.session import db
from app.repositories.moderation import ModerationRepository


def set_banned(user_id: int, banned: bool) -> None:
    with db() as transaction:
        ModerationRepository(transaction).set_banned(user_id, banned)


def statistics() -> dict[str, int]:
    with db() as transaction:
        return ModerationRepository(transaction).statistics()
