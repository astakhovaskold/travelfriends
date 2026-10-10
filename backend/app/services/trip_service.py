import time
from fastapi import HTTPException
from app.db.session import db
from app.schemas import Trip, KickReq
from app.services.common import today, is_ended, age_of, people, blocked_pair, sysmsg, add_member
from app.config import KINDS, MAX_ACTIVE
from app.services.notification_service import safe_send, open_kb
from app.api.auth import ensure_ready

from app.services.chat_service import chat_access
from app.db.session import age_expression, expiry_expression
def trip_select():
    return f"""select t.*, u.name, u.city, u.about, u.vibe as a_vibe, t.user_id as author_id,
    (select status from requests q where q.trip_id=t.id and q.user_id=:me) as req,
    (select count(*) from requests q2 where q2.trip_id=t.id and q2.status='pending') as pending,
    {age_expression("u.birth")} as age,
    (select round(avg(stars),1) from reviews r where r.to_id=t.user_id) as a_avg,
    (select count(*) from reviews r where r.to_id=t.user_id) as a_cnt,
    (select count(*) from joins j2 where j2.trip_id=t.id) as members,
    (select count(*) from joins j where j.trip_id=t.id and j.user_id=:me) as joined,
    cast((t.boosted_until > :now) as integer) as boosted
    from trips t join users u on u.id=t.user_id """


def shape(r, uid):
    d = dict(r)
    d["mine"] = r["user_id"] == uid
    d["ended"] = is_ended(r)
    if not d["mine"]:
        d["pending"] = 0
    return d


def trips(u: dict):
    ensure_ready(u)
    with db() as c:
        rows = c.execute(trip_select() + f"""where t.closed=0 and u.banned=0
            and {expiry_expression()} >= :today
            and t.user_id not in (select blocked_id from blocks where user_id=:me)
            and t.user_id not in (select user_id from blocks where blocked_id=:me)
            order by boosted desc, t.id desc limit 200""",
                         {"me": u["id"], "now": int(time.time()), "today": today()}).fetchall()
    return [shape(r, u["id"]) for r in rows]


def one_trip(trip_id: int, u: dict):
    ensure_ready(u)
    with db() as c:
        r = c.execute(trip_select() + "where t.id=:id and u.banned=0",
                      {"me": u["id"], "now": int(time.time()), "id": trip_id}).fetchone()
        if not r:
            raise HTTPException(404, "notfound")
        d = shape(r, u["id"])
        if is_ended(r) and (d["mine"] or d["joined"]):
            d["to_rate"] = unrated(c, trip_id, u["id"])
    return d


def unrated(c, trip_id, uid):
    ids = {p["id"] for p in people(c, trip_id)}
    done = {r["to_id"] for r in c.execute("select to_id from reviews where trip_id=? and from_id=?", (trip_id, uid))}
    return len([i for i in ids if i != uid and i not in done])


def my(u: dict):
    ensure_ready(u)
    prm = {"me": u["id"], "now": int(time.time())}
    with db() as c:
        mine = c.execute(trip_select() + "where t.user_id=:me order by t.id desc", prm).fetchall()
        joined = c.execute(trip_select() + f"""join joins jj on jj.trip_id=t.id
                                         where jj.user_id=:me order by jj.created desc""", prm).fetchall()
        out = {"mine": [], "joined": []}
        for key, rows in (("mine", mine), ("joined", joined)):
            for r in rows:
                d = shape(r, u["id"])
                d["requests"] = d["members"]
                d["to_rate"] = unrated(c, r["id"], u["id"]) if d["ended"] and d["members"] > 0 else 0
                out[key].append(d)
    return out


def create_trip(t: Trip, u: dict):
    ensure_ready(u)
    import datetime
    try:
        for value in (t.date_from, t.date_to):
            if value and datetime.date.fromisoformat(value).isoformat() != value:
                raise ValueError()
    except ValueError:
        raise HTTPException(400, 'baddate')
    if not t.dest.strip():
        raise HTTPException(400, "nodest")
    if t.audience not in ("all", "f", "m"):
        raise HTTPException(400, "badreq")
    if t.kind == "plan" and not t.date_from:
        raise HTTPException(400, "baddate")
    mn, mx = max(0, min(t.min_age, 99)), max(0, min(t.max_age, 99))
    if mn and mx and mx < mn:
        raise HTTPException(400, "badreq")
    if (t.date_to and t.date_to < today()) or (t.date_from and t.date_to and t.date_to < t.date_from):
        raise HTTPException(400, "baddate")
    with db(write=True) as c:
        c.lock_user(u["id"])
        n = c.execute(f"""select count(*) from trips t where t.user_id=? and t.closed=0 and
            {expiry_expression()} >= ?""",
                      (u["id"], today())).fetchone()[0]
        if n >= MAX_ACTIVE:
            raise HTTPException(400, "limit")
        c.execute(f"""insert into trips(user_id,dest,date_from,date_to,people,budget,note,created,kind,country,lat,lon,
                     audience,min_age,max_age,approval) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (u["id"], t.dest.strip()[:80], t.date_from, t.date_to,
                   max(1, min(t.people, 20)), t.budget.strip()[:40], t.note.strip()[:500], int(time.time()),
                   t.kind if t.kind in KINDS else "other", t.country[:60], t.lat, t.lon,
                   t.audience, mn, mx, 1 if t.approval else 0))
    return {"ok": True}


async def join(trip_id: int, u: dict):
    ensure_ready(u)
    pending = False
    with db(write=True) as c:
        c.lock_trip(trip_id)
        trip = c.execute(f"""select t.*, a.banned as ab, a.lang as alang from trips t
                            join users a on a.id=t.user_id where t.id=?""", (trip_id,)).fetchone()
        if not trip or trip["ab"]:
            raise HTTPException(404, "notfound")
        if trip["user_id"] == u["id"]:
            raise HTTPException(400, "own")
        n = c.execute("select count(*) from joins where trip_id=?", (trip_id,)).fetchone()[0]
        if c.execute("select 1 from joins where trip_id=? and user_id=?", (trip_id, u["id"])).fetchone():
            return {"ok": True, "full": n >= trip["people"]}
        if trip["closed"]:
            raise HTTPException(400, "tripclosed")
        if is_ended(trip):
            raise HTTPException(400, "tripended")
        if blocked_pair(c, u["id"], trip["user_id"]):
            raise HTTPException(403, "blocked")
        if c.execute("select 1 from kicked where trip_id=? and user_id=?", (trip_id, u["id"])).fetchone():
            raise HTTPException(403, "kicked")
        me_ = c.execute("select name, gender, birth from users where id=?", (u["id"],)).fetchone()
        if trip["audience"] in ("f", "m") and me_["gender"] != trip["audience"]:
            raise HTTPException(403, "audience")
        age = age_of(me_["birth"])
        if age is not None and ((trip["min_age"] and age < trip["min_age"]) or (trip["max_age"] and age > trip["max_age"])):
            raise HTTPException(403, "agerange")
        if n >= trip["people"]:
            raise HTTPException(400, "full")
        name = me_["name"]
        if trip["approval"]:
            old = c.execute("select status from requests where trip_id=? and user_id=?", (trip_id, u["id"])).fetchone()
            if old and old["status"] == "declined":
                raise HTTPException(403, "declined")
            if old:
                return {"ok": True, "pending": True}
            c.execute("insert into requests(trip_id,user_id,status,created) values(?,?,'pending',?)",
                      (trip_id, u["id"], int(time.time())))
            pending = True
        else:
            add_member(c, trip_id, u["id"])
    ru = trip["alang"] == "ru"
    who = name or ("Кто-то" if ru else "Someone")
    if pending:
        await safe_send(trip["user_id"],
                        (f"{who} хочет поехать с тобой: {trip['dest']}. Посмотри заявку." if ru
                         else f"{who} wants to join your trip: {trip['dest']}. Review the request."),
                        open_kb(trip_id, ru, "req"))
        return {"ok": True, "pending": True}
    n += 1
    await safe_send(trip["user_id"],
                    (f"{who} едет с тобой: {trip['dest']} ({n}/{trip['people']})" if ru
                     else f"{who} joined your trip: {trip['dest']} ({n}/{trip['people']})"),
                    open_kb(trip_id, ru))
    return {"ok": True, "full": n >= trip["people"]}


def list_requests(trip_id: int, u: dict):
    with db() as c:
        if not c.execute("select 1 from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone():
            raise HTTPException(404, "notfound")
        rows = c.execute(f"""select u.id, u.name, u.vibe,
            {age_expression("u.birth")} as age,
            (select round(avg(stars),1) from reviews r where r.to_id=u.id) as a_avg,
            (select count(*) from reviews r where r.to_id=u.id) as a_cnt
            from requests q join users u on u.id=q.user_id
            where q.trip_id=? and q.status='pending' order by q.created""", (trip_id,)).fetchall()
    return [dict(r) for r in rows]


async def answer_request(trip_id: int, uid: int, act: str, u: dict):
    if act not in ("accept", "decline"):
        raise HTTPException(400, "badreq")
    with db(write=True) as c:
        c.lock_trip(trip_id)
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
        if not trip:
            raise HTTPException(404, "notfound")
        req = c.execute("select 1 from requests where trip_id=? and user_id=? and status='pending'",
                        (trip_id, uid)).fetchone()
        if not req:
            raise HTTPException(404, "notfound")
        lang = c.execute("select lang from users where id=?", (uid,)).fetchone()["lang"]
        if act == "accept":
            if trip['closed']: raise HTTPException(400, 'tripclosed')
            if is_ended(trip): raise HTTPException(400, 'tripended')
            if blocked_pair(c, u['id'], uid): raise HTTPException(403, 'blocked')
            participant = c.execute('select banned, minor, registered from users where id=?', (uid,)).fetchone()
            if participant['banned']: raise HTTPException(403, 'banned')
            if participant['minor']: raise HTTPException(403, 'minor')
            if not participant['registered']: raise HTTPException(403, 'register')
            n = c.execute("select count(*) from joins where trip_id=?", (trip_id,)).fetchone()[0]
            if n >= trip["people"]:
                raise HTTPException(400, "full")
            add_member(c, trip_id, uid)
            c.execute("update requests set status='accepted' where trip_id=? and user_id=?", (trip_id, uid))
        else:
            c.execute("update requests set status='declined' where trip_id=? and user_id=?", (trip_id, uid))
    ru = lang == "ru"
    if act == "accept":
        await safe_send(uid, f"Тебя приняли в поездку «{trip['dest']}»! Чат открыт." if ru
                        else f"You are in! “{trip['dest']}” — the chat is open.", open_kb(trip_id, ru))
    else:
        await safe_send(uid, f"Автор не смог взять тебя в поездку «{trip['dest']}». Найди другую, их много." if ru
                        else f"The author couldn’t take you on “{trip['dest']}”. Many other trips are waiting.")
    return {"ok": True}


def leave(trip_id: int, u: dict):
    with db(write=True) as c:
        c.lock_trip(trip_id)
        trip = chat_access(c, trip_id, u["id"])
        if trip["user_id"] == u["id"]:
            raise HTTPException(400, "own")
        name = c.execute("select name from users where id=?", (u["id"],)).fetchone()["name"]
        c.execute("delete from joins where trip_id=? and user_id=?", (trip_id, u["id"]))
        sysmsg(c, trip_id, f"leave:{name}")
    return {"ok": True}


async def kick(trip_id: int, k: KickReq, u: dict):
    with db(write=True) as c:
        c.lock_trip(trip_id)
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
        if not trip:
            raise HTTPException(404, "notfound")
        t = c.execute(f"""select u.name, u.lang from joins j join users u on u.id=j.user_id
                         where j.trip_id=? and j.user_id=?""", (trip_id, k.user_id)).fetchone()
        if not t:
            raise HTTPException(404, "notfound")
        c.execute("delete from joins where trip_id=? and user_id=?", (trip_id, k.user_id))
        c.execute("insert into kicked values(?,?) on conflict do nothing", (trip_id, k.user_id))
        sysmsg(c, trip_id, f"kick:{t['name']}")
    ru = t["lang"] == "ru"
    await safe_send(k.user_id, f"Автор исключил тебя из группы «{trip['dest']}»." if ru
                    else f"The author removed you from the “{trip['dest']}” group.")
    return {"ok": True}


def close_trip(trip_id: int, u: dict):
    with db(write=True) as c:
        c.lock_trip(trip_id)
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
        if not trip:
            raise HTTPException(404, "notfound")
        c.execute("update trips set closed=1 where id=?", (trip_id,))
        if trip["chat_open"]:
            sysmsg(c, trip_id, "closed:")
    return {"ok": True}


