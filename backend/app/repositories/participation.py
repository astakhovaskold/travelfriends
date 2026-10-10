"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.session import Result, Row, Transaction


class ParticipationRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def review_summary(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select round(avg(stars),1) a, count(*) n from reviews where to_id=?", (user_id,)
        ).fetchone()

    def authored_trips(self, user_id: int) -> Result:
        return self.transaction.execute(
            """
            select t.*, (select count(*) from joins j where j.trip_id = t.id) as m
            from trips t
            where t.user_id = ?
            """,
            (user_id,),
        )

    def joined_trips(self, user_id: int) -> Result:
        return self.transaction.execute(
            "select t.* from joins j join trips t on t.id=j.trip_id where j.user_id=?", (user_id,)
        )

    def friend_count(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            """
            select count(distinct o)
            from (select j2.user_id o
                  from joins j
                           join joins j2 on j2.trip_id = j.trip_id and j2.user_id!=j.user_id
                  where j.user_id=?
                  union
                  select t.user_id
                  from joins j join trips t
                  on t.id=j.trip_id
                  where j.user_id=? and t.user_id!=?
                  union
                  select j.user_id
                  from trips t join joins j
                  on j.trip_id=t.id
                  where t.user_id=? and j.user_id!=?)
            """,
            (user_id, user_id, user_id, user_id, user_id),
        ).fetchone()

    def people(self, trip_id: int) -> list[Row]:
        return self.transaction.execute(
            """
            select u.id, u.lang, u.name
            from users u
            where u.id = (select user_id from trips where id = ?)
            union
            select u.id, u.lang, u.name
            from joins j
                     join users u on u.id = j.user_id
            where j.trip_id = ?
            """,
            (trip_id, trip_id),
        ).fetchall()

    def blocked_pair(self, user_id: int, other_user_id: int) -> Row | None:
        return self.transaction.execute(
            """
            select 1
            from blocks
            where (user_id = ? and blocked_id = ?)
               or (user_id = ? and blocked_id = ?)
            """,
            (user_id, other_user_id, other_user_id, user_id),
        ).fetchone()

    def system_message(self, trip_id: int, text: str, created_at: int) -> Result:
        return self.transaction.execute(
            "insert into messages(trip_id,user_id,text,created) values(?,0,?,?)",
            (trip_id, text, created_at),
        )

    def member_name(self, user_id: int) -> Row | None:
        return self.transaction.execute("select name from users where id=?", (user_id,)).fetchone()

    def add_member(self, trip_id: int, user_id: int, created_at: int) -> Result:
        return self.transaction.execute(
            "insert into joins values(?,?,?) on conflict do nothing", (trip_id, user_id, created_at)
        )

    def open_chat(self, trip_id: int) -> Result:
        return self.transaction.execute("update trips set chat_open=1 where id=?", (trip_id,))
