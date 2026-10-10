"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.session import Result, Row, Transaction, age_expression


class ChatsRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def trip(self, trip_id: int) -> Row | None:
        return self.transaction.execute("select * from trips where id=?", (trip_id,)).fetchone()

    def is_member(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from joins where trip_id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def members_info(self, trip_id: int, user_id: int, author_id: int) -> list[Row]:
        return self.transaction.execute(
            f"""
            select u.id, u.name,
            {age_expression("u.birth")} as age,
            (select round(avg(stars),1) from reviews r where r.to_id=u.id) as a_avg,
            (select count(*) from reviews r where r.to_id=u.id) as a_cnt,
            (select count(*) from reviews r where r.trip_id=:t and r.from_id=:me and r.to_id=u.id) as rated
            from users u where u.id=:a or u.id in (select user_id from joins where trip_id=:t)
            order by (u.id=:a) desc
            """,
            {"t": trip_id, "me": user_id, "a": author_id},
        ).fetchall()

    def recent_messages(self, trip_id: int, user_id: int, since: int) -> list[Row]:
        return self.transaction.execute(
            CHAT_SELECT + " order by m.id desc limit 200", {"t": trip_id, "me": user_id, "s": since}
        ).fetchall()

    def messages_since(self, trip_id: int, user_id: int, since: int) -> list[Row]:
        return self.transaction.execute(
            CHAT_SELECT + " order by m.id limit 200", {"t": trip_id, "me": user_id, "s": since}
        ).fetchall()

    def reactions(self, user_id: int, trip_id: int) -> Result:
        return self.transaction.execute(
            """
            select r.msg_id, r.emoji, count(*) n, max(cast(r.user_id = ? as integer)) mine
            from reactions r
                     join messages m on m.id = r.msg_id
            where m.trip_id = ?
            group by r.msg_id, r.emoji
            """,
            (user_id, trip_id),
        )

    def add_message(self, trip_id: int, user_id: int, text: str, created_at: int) -> Result:
        return self.transaction.execute(
            "insert into messages(trip_id,user_id,text,created) values(?,?,?,?)",
            (trip_id, user_id, text, created_at),
        )

    def reaction_message(self, msg_id: int) -> Row | None:
        return self.transaction.execute(
            "select trip_id, user_id from messages where id=?", (msg_id,)
        ).fetchone()

    def has_reaction(self, msg_id: int, user_id: int, emoji: str) -> Row | None:
        return self.transaction.execute(
            "select 1 from reactions where msg_id=? and user_id=? and emoji=?",
            (msg_id, user_id, emoji),
        ).fetchone()

    def remove_reaction(self, msg_id: int, user_id: int, emoji: str) -> Result:
        return self.transaction.execute(
            "delete from reactions where msg_id=? and user_id=? and emoji=?",
            (msg_id, user_id, emoji),
        )

    def add_reaction(self, msg_id: int, user_id: int, emoji: str) -> Result:
        return self.transaction.execute(
            "insert into reactions values(?,?,?)", (msg_id, user_id, emoji)
        )

    def reported_message(self, msg_id: int) -> Row | None:
        return self.transaction.execute(
            """
            select m.*, u.name
            from messages m
                     join users u on u.id = m.user_id
            where m.id = ?
            """,
            (msg_id,),
        ).fetchone()

    def add_report(self, msg_id: int, user_id: int, created_at: int) -> Result:
        return self.transaction.execute(
            "insert into reports values(?,?,?)", (msg_id, user_id, created_at)
        )


CHAT_SELECT = """
              select m.id, m.user_id, m.text, m.created, coalesce(u.name, '') as name
              from messages m
                       left join users u on u.id = m.user_id
              where m.trip_id = :t
                and m.id > :s
                and (m.user_id = 0 or m.user_id not in (select blocked_id from blocks where user_id = :me)) \
              """
