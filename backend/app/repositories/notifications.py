from app.db.models import auth_identities
from app.db.session import Result, Row, Transaction
from sqlalchemy import select


class NotificationsRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def telegram_identity(self, user_id: int) -> str | None:
        return self.transaction.connection.execute(
            select(auth_identities.c.subject).where(
                auth_identities.c.user_id == user_id, auth_identities.c.provider == "telegram"
            )
        ).scalar_one_or_none()

    def unprompted_trips(self) -> list[Row]:
        return self.transaction.execute("""
                                        select t.*, (select count(*) from joins j where j.trip_id = t.id) as m
                                        from trips t
                                        where t.prompted = 0
                                        """).fetchall()

    def mark_prompted(self, trip_id: int) -> Result:
        return self.transaction.execute("update trips set prompted=1 where id=?", (trip_id,))
