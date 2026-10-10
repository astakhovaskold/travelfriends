import time
from app import errors
from app.config import get_settings
from app.constants import (
    CHAT_FLOOD_LIMIT,
    CHAT_FLOOD_WINDOW,
    CHAT_PING_INTERVAL,
    MESSAGE_MAX_LENGTH,
    REACTIONS,
)
from app.db.session import db
from app.repositories.chats import ChatsRepository
from app.schemas import Msg, React
from app.services.auth_service import ensure_ready
from app.services.common import is_ended
from app.services.notification_service import FLOOD, PINGED, notify_admin, open_kb, safe_send
from app.services.participation_service import people
from app.texts import render_text
from fastapi import HTTPException


def chat_access(transaction, trip_id, user_id):
    trip = ChatsRepository(transaction).trip(trip_id)
    if not trip:
        raise HTTPException(404, errors.NOTFOUND)
    is_member = trip["user_id"] == user_id or ChatsRepository(transaction).is_member(
        trip_id, user_id
    )
    if not is_member:
        raise HTTPException(403, errors.NOTMEMBER)

    return trip


def members_info(transaction, trip, user_id):
    rows = ChatsRepository(transaction).members_info(trip["id"], user_id, trip["user_id"])

    return [
        {**dict(participant), "is_author": participant["id"] == trip["user_id"]}
        for participant in rows
    ]


def trip_people(trip_id: int, user: dict):
    with db() as transaction:
        trip = chat_access(transaction, trip_id, user["id"])
        return {
            "dest": trip["dest"],
            "me": user["id"],
            "author_id": trip["user_id"],
            "ended": is_ended(trip),
            "closed": bool(trip["closed"]),
            "members": members_info(transaction, trip, user["id"]),
        }


def get_chat(trip_id: int, since: int, user: dict):
    with db() as transaction:
        repository = ChatsRepository(transaction)
        trip = chat_access(transaction, trip_id, user["id"])
        if not trip["chat_open"]:
            raise HTTPException(400, errors.CLOSED)
        if since == 0:
            messages = list(reversed(repository.recent_messages(trip_id, user["id"], since)))
        else:
            messages = repository.messages_since(trip_id, user["id"], since)
        info = members_info(transaction, trip, user["id"])
        reactions = {}
        for participant in repository.reactions(user["id"], trip_id):
            reactions.setdefault(participant["msg_id"], {})[participant["emoji"]] = [
                participant["n"],
                participant["mine"],
            ]

    return {
        "dest": trip["dest"],
        "me": user["id"],
        "author_id": trip["user_id"],
        "ended": is_ended(trip),
        "closed": bool(trip["closed"]),
        "members": info,
        "messages": [dict(participant) for participant in messages],
        "reactions": reactions,
    }


async def post_message(trip_id: int, message: Msg, user: dict):
    ensure_ready(user)
    text = message.text.strip()[:MESSAGE_MAX_LENGTH]
    if not text:
        raise HTTPException(400, errors.EMPTY)

    now = time.time()
    recent = [t for t in FLOOD.get(user["id"], []) if now - t < CHAT_FLOOD_WINDOW]
    if len(recent) >= CHAT_FLOOD_LIMIT:
        raise HTTPException(429, errors.SLOW)
    FLOOD[user["id"]] = recent + [now]

    with db() as transaction:
        trip = chat_access(transaction, trip_id, user["id"])
        if not trip["chat_open"]:
            raise HTTPException(400, errors.CLOSED)
        ChatsRepository(transaction).add_message(trip_id, user["id"], text, int(time.time()))
        others = people(transaction, trip_id)

    for participant in others:
        key = (trip_id, participant["id"])
        if participant["id"] != user["id"] and now - PINGED.get(key, 0) > CHAT_PING_INTERVAL:
            PINGED[key] = now
            ru = participant["lang"] == "ru"
            await safe_send(
                participant["id"],
                render_text("chat.new_message", "ru" if ru else "en", dest=trip["dest"]),
                open_kb(trip_id, ru),
            )

    return {"ok": True}


def react(msg_id: int, reaction: React, user: dict):
    ensure_ready(user)
    if reaction.emoji not in REACTIONS:
        raise HTTPException(400, errors.BADREQ)

    with db() as transaction:
        repository = ChatsRepository(transaction)
        msg = repository.reaction_message(msg_id)
        if not msg or msg["user_id"] == 0:
            raise HTTPException(404, errors.NOTFOUND)
        chat_access(transaction, msg["trip_id"], user["id"])
        if repository.has_reaction(msg_id, user["id"], reaction.emoji):
            repository.remove_reaction(msg_id, user["id"], reaction.emoji)
        else:
            repository.add_reaction(msg_id, user["id"], reaction.emoji)

    return {"ok": True}


async def report(msg_id: int, user: dict):
    with db() as transaction:
        repository = ChatsRepository(transaction)
        msg = repository.reported_message(msg_id)
        if not msg:
            raise HTTPException(404, errors.NOTFOUND)
        chat_access(transaction, msg["trip_id"], user["id"])
        repository.add_report(msg_id, user["id"], int(time.time()))

    if get_settings().ADMIN_ID:
        await notify_admin(
            render_text(
                "admin.message_report",
                "en",
                trip_id=msg["trip_id"],
                user_id=msg["user_id"],
                name=msg["name"],
                text=msg["text"],
            )
        )

    return {"ok": True}
