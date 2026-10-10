"""Queries only: transaction lifecycle and business checks belong to services."""

from app.db.session import Result, Row, Transaction, age_expression, expiry_expression


def trip_select() -> str:
    return f"""
        select t.*, u.name, u.city, u.about, u.vibe as a_vibe, t.user_id as author_id,
        (select status from requests q where q.trip_id=t.id and q.user_id=:me) as req,
        (select count(*) from requests q2 where q2.trip_id=t.id and q2.status='pending') as pending,
        {age_expression("u.birth")} as age,
        (select round(avg(stars),1) from reviews r where r.to_id=t.user_id) as a_avg,
        (select count(*) from reviews r where r.to_id=t.user_id) as a_cnt,
        (select count(*) from joins j2 where j2.trip_id=t.id) as members,
        (select count(*) from joins j where j.trip_id=t.id and j.user_id=:me) as joined,
        cast((t.boosted_until > :now) as integer) as boosted
        from trips t join users u on u.id=t.user_id
        """


class TripsRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def catalog(self, user_id: int, now: int, today: str) -> list[Row]:
        return self.transaction.execute(
            trip_select()
            + f"""
            where t.closed=0 and u.banned=0
            and {expiry_expression()} >= :today
            and t.user_id not in (select blocked_id from blocks where user_id=:me)
            and t.user_id not in (select user_id from blocks where blocked_id=:me)
            order by boosted desc, t.id desc limit 200
            """,
            {"me": user_id, "now": now, "today": today},
        ).fetchall()

    def detail(self, user_id: int, now: int, trip_id: int) -> Row | None:
        return self.transaction.execute(
            trip_select() + "where t.id=:id and u.banned=0",
            {"me": user_id, "now": now, "id": trip_id},
        ).fetchone()

    def rated_users(self, trip_id: int, user_id: int) -> Result:
        return self.transaction.execute(
            "select to_id from reviews where trip_id=? and from_id=?", (trip_id, user_id)
        )

    def owned(self, user_id: int, now: int) -> list[Row]:
        return self.transaction.execute(
            trip_select() + "where t.user_id=:me order by t.id desc", {"me": user_id, "now": now}
        ).fetchall()

    def joined(self, user_id: int, now: int) -> list[Row]:
        return self.transaction.execute(
            trip_select()
            + """
            join joins jj on jj.trip_id=t.id
            where jj.user_id=:me order by jj.created desc
            """,
            {"me": user_id, "now": now},
        ).fetchall()

    def active_count(self, user_id: int, today: str) -> Row | None:
        return self.transaction.execute(
            f"""
            select count(*) from trips t where t.user_id=? and t.closed=0 and
            {expiry_expression()} >= ?
            """,
            (user_id, today),
        ).fetchone()

    def create(
            self,
            user_id: int,
            dest: str,
            date_from: str,
            date_to: str,
            people: int,
            budget: str,
            note: str,
            created_at: int,
            kind: str,
            country: str,
            lat: float | None,
            lon: float | None,
            audience: str,
            min_age: int,
            max_age: int,
            approval: int,
    ) -> Result:
        return self.transaction.execute(
            """
            insert into trips(user_id, dest, date_from, date_to, people, budget, note, created, kind, country, lat, lon,
                              audience, min_age, max_age, approval)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                dest,
                date_from,
                date_to,
                people,
                budget,
                note,
                created_at,
                kind,
                country,
                lat,
                lon,
                audience,
                min_age,
                max_age,
                approval,
            ),
        )

    def with_author(self, trip_id: int) -> Row | None:
        return self.transaction.execute(
            """
            select t.*, a.banned as ab, a.lang as alang
            from trips t
                     join users a on a.id = t.user_id
            where t.id = ?
            """,
            (trip_id,),
        ).fetchone()

    def member_count(self, trip_id: int) -> Row | None:
        return self.transaction.execute(
            "select count(*) from joins where trip_id=?", (trip_id,)
        ).fetchone()

    def is_member(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from joins where trip_id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def is_kicked(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from kicked where trip_id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def participant_profile(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select name, gender, birth from users where id=?", (user_id,)
        ).fetchone()

    def request(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select status from requests where trip_id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def request_join(self, trip_id: int, user_id: int, created_at: int) -> Result:
        return self.transaction.execute(
            "insert into requests(trip_id,user_id,status,created) values(?,?,'pending',?)",
            (trip_id, user_id, created_at),
        )

    def is_owner(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from trips where id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def pending_requests(self, trip_id: int) -> list[Row]:
        return self.transaction.execute(
            f"""
            select u.id, u.name, u.vibe,
            {age_expression("u.birth")} as age,
            (select round(avg(stars),1) from reviews r where r.to_id=u.id) as a_avg,
            (select count(*) from reviews r where r.to_id=u.id) as a_cnt
            from requests q join users u on u.id=q.user_id
            where q.trip_id=? and q.status='pending' order by q.created
            """,
            (trip_id,),
        ).fetchall()

    def owned_trip(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select * from trips where id=? and user_id=?", (trip_id, user_id)
        ).fetchone()

    def pending_request(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select 1 from requests where trip_id=? and user_id=? and status='pending'",
            (trip_id, user_id),
        ).fetchone()

    def recipient_language(self, user_id: int) -> Row | None:
        return self.transaction.execute("select lang from users where id=?", (user_id,)).fetchone()

    def participant_state(self, user_id: int) -> Row | None:
        return self.transaction.execute(
            "select banned, minor, registered from users where id=?", (user_id,)
        ).fetchone()

    def accept_request(self, trip_id: int, user_id: int) -> Result:
        return self.transaction.execute(
            "update requests set status='accepted' where trip_id=? and user_id=?",
            (trip_id, user_id),
        )

    def decline_request(self, trip_id: int, user_id: int) -> Result:
        return self.transaction.execute(
            "update requests set status='declined' where trip_id=? and user_id=?",
            (trip_id, user_id),
        )

    def leaving_name(self, user_id: int) -> Row | None:
        return self.transaction.execute("select name from users where id=?", (user_id,)).fetchone()

    def remove_member(self, trip_id: int, user_id: int) -> Result:
        return self.transaction.execute(
            "delete from joins where trip_id=? and user_id=?", (trip_id, user_id)
        )

    def kick_member(self, trip_id: int, user_id: int) -> Row | None:
        return self.transaction.execute(
            """
            select u.name, u.lang
            from joins j
                     join users u on u.id = j.user_id
            where j.trip_id = ?
              and j.user_id = ?
            """,
            (trip_id, user_id),
        ).fetchone()

    def record_kick(self, trip_id: int, user_id: int) -> Result:
        return self.transaction.execute(
            "insert into kicked values(?,?) on conflict do nothing", (trip_id, user_id)
        )

    def close(self, trip_id: int) -> Result:
        return self.transaction.execute("update trips set closed=1 where id=?", (trip_id,))
