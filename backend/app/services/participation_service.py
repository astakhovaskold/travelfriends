import time

from app.db.session import Row, Transaction
from app.repositories.participation import ParticipationRepository
from app.services.common import is_ended


def stats(transaction: Transaction, user_id: int) -> dict:
    summary = ParticipationRepository(transaction).review_summary(user_id)
    completed_trips = 0
    for trip in ParticipationRepository(transaction).authored_trips(user_id):
        if trip["m"] > 0 and is_ended(trip):
            completed_trips += 1
    for trip in ParticipationRepository(transaction).joined_trips(user_id):
        if is_ended(trip):
            completed_trips += 1
    friends = ParticipationRepository(transaction).friend_count(user_id)[0]

    return {"avg": summary["a"], "cnt": summary["n"], "trips": completed_trips, "friends": friends}


def people(transaction: Transaction, trip_id: int) -> list[Row]:
    return ParticipationRepository(transaction).people(trip_id)


def blocked_pair(transaction: Transaction, user_id: int, other_user_id: int) -> Row | None:
    return ParticipationRepository(transaction).blocked_pair(user_id, other_user_id)


def sysmsg(transaction: Transaction, trip_id: int, text: str) -> None:
    ParticipationRepository(transaction).system_message(trip_id, text, int(time.time()))


def add_member(transaction: Transaction, trip_id: int, user_id: int) -> str:
    # Caller owns the trip lock and transaction: membership and event commit together.
    repository = ParticipationRepository(transaction)
    name = repository.member_name(user_id)["name"]
    repository.add_member(trip_id, user_id, int(time.time()))
    repository.open_chat(trip_id)
    sysmsg(transaction, trip_id, f"join:{name}")

    return name
