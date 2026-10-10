"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.session import Result, Row, Transaction


class PaymentsRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def payment_trip(self, trip_id: int, telegram_subject: str) -> Row | None:
        return self.transaction.execute(
            """
            select t.id, t.user_id
            from trips t
                     join auth_identities a on a.user_id = t.user_id
            where t.id = ?
              and a.provider = 'telegram'
              and a.subject = ?
            """,
            (trip_id, telegram_subject),
        ).fetchone()

    def owned_trip(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select * from trips where id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def telegram_identity(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from auth_identities where user_id=? and provider='telegram'", (user_id,)
        ).fetchone()

    def has_charge(self, charge: str) -> Row | None:
        return self.transaction.execute(
            "select 1 from payments where charge_id=?", (charge,)
        ).fetchone()

    def record(
            self, charge: str, trip_id: int, user_id: int, amount: int, currency: str, created_at: int
    ) -> Result:
        return self.transaction.execute(
            "insert into payments(charge_id,trip_id,user_id,amount,currency,created) values(?,?,?,?,?,?)",
            (charge, trip_id, user_id, amount, currency, created_at),
        )

    def boost(self, boosted_until: int, trip_id: int) -> Result:
        return self.transaction.execute(
            "update trips set boosted_until=? where id=?", (boosted_until, trip_id)
        )
