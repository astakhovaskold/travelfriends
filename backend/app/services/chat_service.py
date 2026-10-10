from app.db.session import age_expression
import time
from fastapi import HTTPException
from app.db.session import db
from app.schemas import Msg, React
from app.services.common import is_ended, people
from app.config import ADMIN_ID
from app.services.notification_service import safe_send, notify_admin, open_kb, PINGED, FLOOD
from app.api.auth import ensure_ready

def chat_access(c, trip_id, uid):
    trip = c.execute("select * from trips where id=?", (trip_id,)).fetchone()
    if not trip:
        raise HTTPException(404, "notfound")
    is_member = trip["user_id"] == uid or c.execute(
        "select 1 from joins where trip_id=? and user_id=?", (trip_id, uid)).fetchone()
    if not is_member:
        raise HTTPException(403, "notmember")
    return trip


def members_info(c, trip, uid):
    rows = c.execute(f"""select u.id, u.name,
        {age_expression("u.birth")} as age,
        (select round(avg(stars),1) from reviews r where r.to_id=u.id) as a_avg,
        (select count(*) from reviews r where r.to_id=u.id) as a_cnt,
        (select count(*) from reviews r where r.trip_id=:t and r.from_id=:me and r.to_id=u.id) as rated
        from users u where u.id=:a or u.id in (select user_id from joins where trip_id=:t)
        order by (u.id=:a) desc""", {"t": trip["id"], "me": uid, "a": trip["user_id"]}).fetchall()
    return [{**dict(r), "is_author": r["id"] == trip["user_id"]} for r in rows]


def trip_people(trip_id: int, u: dict):
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        return {"dest": trip["dest"], "me": u["id"], "author_id": trip["user_id"],
                "ended": is_ended(trip), "closed": bool(trip["closed"]), "members": members_info(c, trip, u["id"])}


def get_chat(trip_id: int, since: int, u: dict):
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        if not trip["chat_open"]:
            raise HTTPException(400, "closed")
        base = """select m.id, m.user_id, m.text, m.created, coalesce(u.name,'') as name
                  from messages m left join users u on u.id = m.user_id
                  where m.trip_id=:t and m.id>:s
                  and (m.user_id=0 or m.user_id not in (select blocked_id from blocks where user_id=:me))"""
        prm = {"t": trip_id, "s": since, "me": u["id"]}
        if since == 0:
            msgs = list(reversed(c.execute(base + " order by m.id desc limit 200", prm).fetchall()))
        else:
            msgs = c.execute(base + " order by m.id limit 200", prm).fetchall()
        info = members_info(c, trip, u["id"])
        rx = {}
        for r in c.execute(f"""select r.msg_id, r.emoji, count(*) n, max(cast(r.user_id=? as integer)) mine
                              from reactions r join messages m on m.id=r.msg_id where m.trip_id=?
                              group by r.msg_id, r.emoji""", (u["id"], trip_id)):
            rx.setdefault(r["msg_id"], {})[r["emoji"]] = [r["n"], r["mine"]]
    return {"dest": trip["dest"], "me": u["id"], "author_id": trip["user_id"], "ended": is_ended(trip),
            "closed": bool(trip["closed"]), "members": info, "messages": [dict(r) for r in msgs], "reactions": rx}


async def post_message(trip_id: int, m: Msg, u: dict):
    ensure_ready(u)
    text = m.text.strip()[:1000]
    if not text:
        raise HTTPException(400, "empty")
    now = time.time()
    recent = [t for t in FLOOD.get(u["id"], []) if now - t < 30]
    if len(recent) >= 15:
        raise HTTPException(429, "slow")
    FLOOD[u["id"]] = recent + [now]
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        if not trip["chat_open"]:
            raise HTTPException(400, "closed")
        c.execute("insert into messages(trip_id,user_id,text,created) values(?,?,?,?)",
                  (trip_id, u["id"], text, int(time.time())))
        others = people(c, trip_id)
    for r in others:
        key = (trip_id, r["id"])
        if r["id"] != u["id"] and now - PINGED.get(key, 0) > 600:
            PINGED[key] = now
            ru = r["lang"] == "ru"
            await safe_send(r["id"], (f"Новое сообщение в чате «{trip['dest']}»" if ru
                                      else f"New message in the “{trip['dest']}” chat"), open_kb(trip_id, ru))
    return {"ok": True}


def react(msg_id: int, r: React, u: dict):
    ensure_ready(u)
    if r.emoji not in ("👍", "❤️", "😂", "🔥", "😮"):
        raise HTTPException(400, "badreq")
    with db() as c:
        msg = c.execute("select trip_id, user_id from messages where id=?", (msg_id,)).fetchone()
        if not msg or msg["user_id"] == 0:
            raise HTTPException(404, "notfound")
        chat_access(c, msg["trip_id"], u["id"])
        if c.execute("select 1 from reactions where msg_id=? and user_id=? and emoji=?", (msg_id, u["id"], r.emoji)).fetchone():
            c.execute("delete from reactions where msg_id=? and user_id=? and emoji=?", (msg_id, u["id"], r.emoji))
        else:
            c.execute("insert into reactions values(?,?,?)", (msg_id, u["id"], r.emoji))
    return {"ok": True}


async def report(msg_id: int, u: dict):
    with db() as c:
        msg = c.execute(f"""select m.*, u.name from messages m join users u on u.id=m.user_id
                           where m.id=?""", (msg_id,)).fetchone()
        if not msg:
            raise HTTPException(404, "notfound")
        chat_access(c, msg["trip_id"], u["id"])
        c.execute("insert into reports values(?,?,?)", (msg_id, u["id"], int(time.time())))
    if ADMIN_ID:
        await notify_admin( f"Report: trip {msg['trip_id']}, user {msg['user_id']} ({msg['name']}): "
                                  f"{msg['text']}\n/ban {msg['user_id']}")
    return {"ok": True}


