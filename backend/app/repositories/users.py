"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.session import Result, Row, Transaction


class UsersRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def get(self, user_id: int) -> Row | None:
        return self.transaction.execute("select * from users where id=?", (user_id,)).fetchone()

    def accept_rules(self, user_id: int) -> Result:
        return self.transaction.execute("update users set rules_ok=1 where id=?", (user_id,))

    def registration_state(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select rules_ok from users where id=?", (user_id,)
        ).fetchone()

    def mark_minor(self, user_id: int) -> Result:
        return self.transaction.execute("update users set minor=1 where id=?", (user_id,))

    def register(
            self, birth: str, gender: str, vibe: str, city: str, about: str, user_id: int
    ) -> Result:
        return self.transaction.execute(
            "update users set birth=?, gender=?, vibe=?, city=?, about=?, rules_ok=1, registered=1 where id=?",
            (birth, gender, vibe, city, about, user_id),
        )

    def update_profile(self, city: str, about: str, vibe: str, user_id: int) -> Result:
        return self.transaction.execute(
            "update users set city=?, about=?, vibe=? where id=?", (city, about, vibe, user_id)
        )

    def public_profile(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select * from users where id=? and registered=1 and banned=0", (user_id,)
        ).fetchone()

    def profile_reviews(self, user_id: int) -> list[Row]:
        return self.transaction.execute(
            """
            select r.stars, r.tags, r.text, r.created, u.name, t.dest
            from reviews r
                     join users u on u.id = r.from_id
                     join trips t on t.id = r.trip_id
            where r.to_id = ?
            order by r.id desc limit 20
            """,
            (user_id,),
        ).fetchall()

    def review_tags(self, user_id: int) -> Result:
        return self.transaction.execute("select tags from reviews where to_id=?", (user_id,))

    def is_blocked(self, user_id: int, author_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from blocks where user_id=? and blocked_id=?", (user_id, author_id)
        ).fetchone()

    def exists(self, user_id: int) -> Row | None:
        return self.transaction.execute("select 1 from users where id=?", (user_id,)).fetchone()

    def block(self, user_id: int, author_id: int) -> Result:
        return self.transaction.execute(
            "insert into blocks values(?,?) on conflict do nothing", (user_id, author_id)
        )

    def unblock(self, user_id: int, author_id: int) -> Result:
        return self.transaction.execute(
            "delete from blocks where user_id=? and blocked_id=?", (user_id, author_id)
        )

    def report_subject(self, user_id: int) -> Row | None:
        return self.transaction.execute("select name from users where id=?", (user_id,)).fetchone()
