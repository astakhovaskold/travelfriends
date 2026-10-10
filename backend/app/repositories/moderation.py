from app.db.session import Transaction


class ModerationRepository:
    def __init__(self, transaction: Transaction) -> None:
        self.transaction = transaction

    def set_banned(self, user_id: int, banned: bool) -> None:
        self.transaction.execute("update users set banned=? where id=?", (int(banned), user_id))

    def statistics(self) -> dict[str, int]:
        queries = {
            "users": "select count(*) from users where registered=1",
            "trips": "select count(*) from trips",
            "joins": "select count(*) from joins",
            "messages": "select count(*) from messages where user_id>0",
            "reviews": "select count(*) from reviews",
            "reports": "select count(*) from reports",
        }
        return {name: self.transaction.execute(sql).fetchone()[0] for name, sql in queries.items()}
