"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.session import Result, Row, Transaction


class ReviewsRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def exists(self, trip_id: int, user_id: int, to_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from reviews where trip_id=? and from_id=? and to_id=?",
            (trip_id, user_id, to_id),
        ).fetchone()

    def add(
            self,
            trip_id: int,
            user_id: int,
            to_id: int,
            stars: int,
            tags: str,
            text: str,
            created_at: int,
    ) -> Result:
        return self.transaction.execute(
            "insert into reviews(trip_id,from_id,to_id,stars,tags,text,created) values(?,?,?,?,?,?,?)",
            (trip_id, user_id, to_id, stars, tags, text, created_at),
        )

    def recipient_language(self, to_id: int) -> Row | None:
        return self.transaction.execute("select lang from users where id=?", (to_id,)).fetchone()
