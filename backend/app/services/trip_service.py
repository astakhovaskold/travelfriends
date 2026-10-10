import datetime
import time
from app import errors
from app.constants import (
    BUDGET_MAX_LENGTH,
    COUNTRY_MAX_LENGTH,
    DEST_MAX_LENGTH,
    KINDS,
    MAX_ACTIVE,
    NOTE_MAX_LENGTH,
    TRIP_MAX_AGE,
    TRIP_MAX_PEOPLE,
)
from app.db.session import db
from app.repositories.trips import TripsRepository
from app.schemas import KickReq, Trip
from app.services.auth_service import ensure_ready
from app.services.chat_service import chat_access
from app.services.common import age_of, is_ended, today
from app.services.notification_service import open_kb, safe_send
from app.services.participation_service import add_member, blocked_pair, people, sysmsg
from app.texts import render_text
from fastapi import HTTPException


def shape(row, user_id):
    data = dict(row)
    data["mine"] = row["user_id"] == user_id
    data["ended"] = is_ended(row)
    if not data["mine"]:
        data["pending"] = 0

    return data


def trips(user: dict):
    ensure_ready(user)

    with db() as transaction:
        rows = TripsRepository(transaction).catalog(user["id"], int(time.time()), today())

    return [shape(row, user["id"]) for row in rows]


def one_trip(trip_id: int, user: dict):
    ensure_ready(user)

    with db() as transaction:
        row = TripsRepository(transaction).detail(user["id"], int(time.time()), trip_id)
        if not row:
            raise HTTPException(404, errors.NOTFOUND)
        data = shape(row, user["id"])
        if is_ended(row) and (data["mine"] or data["joined"]):
            data["to_rate"] = unrated(transaction, trip_id, user["id"])

    return data


def unrated(transaction, trip_id, user_id):
    ids = {p["id"] for p in people(transaction, trip_id)}
    done = {row["to_id"] for row in TripsRepository(transaction).rated_users(trip_id, user_id)}

    return len([i for i in ids if i != user_id and i not in done])


def my(user: dict):
    ensure_ready(user)

    now = int(time.time())

    with db() as transaction:
        repository = TripsRepository(transaction)
        mine = repository.owned(user["id"], now)
        joined = repository.joined(user["id"], now)
        result = {"mine": [], "joined": []}
        for key, rows in (("mine", mine), ("joined", joined)):
            for row in rows:
                data = shape(row, user["id"])
                data["requests"] = data["members"]
                data["to_rate"] = (
                    unrated(transaction, row["id"], user["id"])
                    if data["ended"] and data["members"] > 0
                    else 0
                )
                result[key].append(data)

    return result


def create_trip(request: Trip, user: dict):
    ensure_ready(user)
    try:
        for value in (request.date_from, request.date_to):
            if value and datetime.date.fromisoformat(value).isoformat() != value:
                raise ValueError()
    except ValueError:
        raise HTTPException(400, errors.BADDATE)
    if not request.dest.strip():
        raise HTTPException(400, errors.NODEST)
    if request.audience not in ("all", "f", "m"):
        raise HTTPException(400, errors.BADREQ)
    if request.kind == "plan" and (not request.date_from):
        raise HTTPException(400, errors.BADDATE)
    min_age, max_age = (
        max(0, min(request.min_age, TRIP_MAX_AGE)),
        max(0, min(request.max_age, TRIP_MAX_AGE)),
    )
    if min_age and max_age and (max_age < min_age):
        raise HTTPException(400, errors.BADREQ)
    if (
            request.date_to
            and request.date_to < today()
            or (request.date_from and request.date_to and (request.date_to < request.date_from))
    ):
        raise HTTPException(400, errors.BADDATE)

    with db(write=True) as transaction:
        repository = TripsRepository(transaction)
        transaction.lock_user(user["id"])
        active_count = repository.active_count(user["id"], today())[0]
        if active_count >= MAX_ACTIVE:
            raise HTTPException(400, errors.LIMIT)
        repository.create(
            user["id"],
            request.dest.strip()[:DEST_MAX_LENGTH],
            request.date_from,
            request.date_to,
            max(1, min(request.people, TRIP_MAX_PEOPLE)),
            request.budget.strip()[:BUDGET_MAX_LENGTH],
            request.note.strip()[:NOTE_MAX_LENGTH],
            int(time.time()),
            request.kind if request.kind in KINDS else "other",
            request.country[:COUNTRY_MAX_LENGTH],
            request.lat,
            request.lon,
            request.audience,
            min_age,
            max_age,
            1 if request.approval else 0,
        )

    return {"ok": True}


async def join(trip_id: int, user: dict):
    ensure_ready(user)
    pending = False

    with db(write=True) as transaction:
        repository = TripsRepository(transaction)
        # Join and request acceptance share this lock, including capacity checks.
        transaction.lock_trip(trip_id)
        trip = repository.with_author(trip_id)
        if not trip or trip["ab"]:
            raise HTTPException(404, errors.NOTFOUND)
        if trip["user_id"] == user["id"]:
            raise HTTPException(400, errors.OWN)
        member_count = repository.member_count(trip_id)[0]
        if repository.is_member(trip_id, user["id"]):
            return {"ok": True, "full": member_count >= trip["people"]}
        if trip["closed"]:
            raise HTTPException(400, errors.TRIPCLOSED)
        if is_ended(trip):
            raise HTTPException(400, errors.TRIPENDED)
        if blocked_pair(transaction, user["id"], trip["user_id"]):
            raise HTTPException(403, errors.BLOCKED)
        if repository.is_kicked(trip_id, user["id"]):
            raise HTTPException(403, errors.KICKED)
        participant = repository.participant_profile(user["id"])
        if trip["audience"] in ("f", "m") and participant["gender"] != trip["audience"]:
            raise HTTPException(403, errors.AUDIENCE)
        age = age_of(participant["birth"])
        if age is not None and (
                trip["min_age"] and age < trip["min_age"] or (trip["max_age"] and age > trip["max_age"])
        ):
            raise HTTPException(403, errors.AGERANGE)
        if member_count >= trip["people"]:
            raise HTTPException(400, errors.FULL)
        name = participant["name"]
        if trip["approval"]:
            existing_request = repository.request(trip_id, user["id"])
            if existing_request and existing_request["status"] == "declined":
                raise HTTPException(403, errors.DECLINED)
            if existing_request:
                return {"ok": True, "pending": True}
            repository.request_join(trip_id, user["id"], int(time.time()))
            pending = True
        else:
            add_member(transaction, trip_id, user["id"])

    ru = trip["alang"] == "ru"
    who = name or render_text("person.someone", "ru" if ru else "en")
    if pending:
        await safe_send(
            trip["user_id"],
            render_text("trip.request_join", "ru" if ru else "en", who=who, dest=trip["dest"]),
            open_kb(trip_id, ru, "req"),
        )
        return {"ok": True, "pending": True}
    member_count += 1

    await safe_send(
        trip["user_id"],
        render_text(
            "trip.joined",
            "ru" if ru else "en",
            who=who,
            dest=trip["dest"],
            members=member_count,
            people=trip["people"],
        ),
        open_kb(trip_id, ru),
    )

    return {"ok": True, "full": member_count >= trip["people"]}


def list_requests(trip_id: int, user: dict):
    with db() as transaction:
        repository = TripsRepository(transaction)
        if not repository.is_owner(trip_id, user["id"]):
            raise HTTPException(404, errors.NOTFOUND)
        rows = repository.pending_requests(trip_id)

    return [dict(row) for row in rows]


async def answer_request(trip_id: int, user_id: int, act: str, user: dict):
    if act not in ("accept", "decline"):
        raise HTTPException(400, errors.BADREQ)

    with db(write=True) as transaction:
        repository = TripsRepository(transaction)
        # Join and request acceptance share this lock, including capacity checks.
        transaction.lock_trip(trip_id)
        trip = repository.owned_trip(trip_id, user["id"])
        if not trip:
            raise HTTPException(404, errors.NOTFOUND)
        request = repository.pending_request(trip_id, user_id)
        if not request:
            raise HTTPException(404, errors.NOTFOUND)
        lang = repository.recipient_language(user_id)["lang"]
        if act == "accept":
            if trip["closed"]:
                raise HTTPException(400, errors.TRIPCLOSED)
            if is_ended(trip):
                raise HTTPException(400, errors.TRIPENDED)
            if blocked_pair(transaction, user["id"], user_id):
                raise HTTPException(403, errors.BLOCKED)
            participant = repository.participant_state(user_id)
            if participant["banned"]:
                raise HTTPException(403, errors.BANNED)
            if participant["minor"]:
                raise HTTPException(403, errors.MINOR)
            if not participant["registered"]:
                raise HTTPException(403, errors.REGISTER)
            member_count = repository.member_count(trip_id)[0]
            if member_count >= trip["people"]:
                raise HTTPException(400, errors.FULL)
            add_member(transaction, trip_id, user_id)
            repository.accept_request(trip_id, user_id)
        else:
            repository.decline_request(trip_id, user_id)

    ru = lang == "ru"
    if act == "accept":
        await safe_send(
            user_id,
            render_text("trip.accepted", "ru" if ru else "en", dest=trip["dest"]),
            open_kb(trip_id, ru),
        )
    else:
        await safe_send(
            user_id, render_text("trip.declined", "ru" if ru else "en", dest=trip["dest"])
        )

    return {"ok": True}


def leave(trip_id: int, user: dict):
    with db(write=True) as transaction:
        repository = TripsRepository(transaction)
        transaction.lock_trip(trip_id)
        trip = chat_access(transaction, trip_id, user["id"])
        if trip["user_id"] == user["id"]:
            raise HTTPException(400, errors.OWN)
        name = repository.leaving_name(user["id"])["name"]
        repository.remove_member(trip_id, user["id"])
        sysmsg(transaction, trip_id, f"leave:{name}")

    return {"ok": True}


async def kick(trip_id: int, request: KickReq, user: dict):
    with db(write=True) as transaction:
        repository = TripsRepository(transaction)
        transaction.lock_trip(trip_id)
        trip = repository.owned_trip(trip_id, user["id"])
        if not trip:
            raise HTTPException(404, errors.NOTFOUND)
        member = repository.kick_member(trip_id, request.user_id)
        if not member:
            raise HTTPException(404, errors.NOTFOUND)
        repository.remove_member(trip_id, request.user_id)
        repository.record_kick(trip_id, request.user_id)
        sysmsg(transaction, trip_id, f"kick:{member['name']}")

    ru = member["lang"] == "ru"

    await safe_send(
        request.user_id, render_text("trip.removed", "ru" if ru else "en", dest=trip["dest"])
    )

    return {"ok": True}


def close_trip(trip_id: int, user: dict):
    with db(write=True) as transaction:
        repository = TripsRepository(transaction)
        transaction.lock_trip(trip_id)
        trip = repository.owned_trip(trip_id, user["id"])
        if not trip:
            raise HTTPException(404, errors.NOTFOUND)
        repository.close(trip_id)
        if trip["chat_open"]:
            sysmsg(transaction, trip_id, "closed:")

    return {"ok": True}
