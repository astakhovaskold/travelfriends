from fastapi import HTTPException
from app.db.session import db
from app.schemas import Profile, Reg, BlockReq
from app.services.common import age_of, clean_vibe, stats
from app.config import GENDERS, ADMIN_ID
from app.services.notification_service import notify_admin
from app.api.auth import ensure_ready

import datetime
def me(u: dict):
    with db() as c:
        d = dict(c.execute("select * from users where id=?", (u["id"],)).fetchone())
        d.update(stats(c, u["id"]))
    d["age"] = age_of(d.pop("birth", None))
    d.pop("username", None)
    return d


def accept_rules(u: dict):
    with db() as c:
        c.execute("update users set rules_ok=1 where id=?", (u["id"],))
    return {"ok": True}


def register(r: Reg, u: dict):
    with db() as c:
        row = c.execute("select rules_ok from users where id=?", (u["id"],)).fetchone()
    if not row["rules_ok"]:
        raise HTTPException(403, "rules")
    try:
        b = datetime.date.fromisoformat(r.birth)
    except ValueError:
        raise HTTPException(400, "baddate")
    age = age_of(r.birth)
    if b > datetime.date.today() or age is None or age > 100:
        raise HTTPException(400, "baddate")
    if age < 18:
        with db() as c:  # дату рождения несовершеннолетнего не сохраняем, только запрет
            c.execute("update users set minor=1 where id=?", (u["id"],))
        raise HTTPException(403, "minor")
    if r.gender not in GENDERS:
        raise HTTPException(400, "badreq")
    with db() as c:
        c.execute("update users set birth=?, gender=?, vibe=?, city=?, about=?, registered=1 where id=?",
                  (r.birth, r.gender, clean_vibe(r.vibe), r.city.strip()[:60], r.about.strip()[:500], u["id"]))
    return {"ok": True}


def save_profile(p: Profile, u: dict):
    ensure_ready(u)
    with db() as c:
        c.execute("update users set city=?, about=?, vibe=? where id=?",
                  (p.city.strip()[:60], p.about.strip()[:500], clean_vibe(p.vibe), u["id"]))
    return {"ok": True}


def profile(user_id: int, u: dict):
    ensure_ready(u)
    with db() as c:
        p = c.execute("select * from users where id=? and registered=1 and banned=0", (user_id,)).fetchone()
        if not p:
            raise HTTPException(404, "notfound")
        st = stats(c, user_id)
        revs = c.execute("""select r.stars, r.tags, r.text, r.created, u.name, t.dest
                            from reviews r join users u on u.id=r.from_id join trips t on t.id=r.trip_id
                            where r.to_id=? order by r.id desc limit 20""", (user_id,)).fetchall()
        tags = {}
        for r in c.execute("select tags from reviews where to_id=?", (user_id,)):
            for tg in filter(None, r["tags"].split(",")):
                tags[tg] = tags.get(tg, 0) + 1
        blocked = bool(c.execute("select 1 from blocks where user_id=? and blocked_id=?", (u["id"], user_id)).fetchone())
    return {"id": user_id, "name": p["name"], "age": age_of(p["birth"]), "city": p["city"], "about": p["about"],
            "vibe": [v for v in (p["vibe"] or "").split(",") if v],
            **st, "tags": tags, "me": user_id == u["id"], "blocked": blocked,
            "reviews": [{**dict(r), "tags": [t for t in r["tags"].split(",") if t]} for r in revs]}


def block(b: BlockReq, u: dict):
    if b.user_id == u["id"]:
        raise HTTPException(400, "own")
    with db() as c:
        if b.on:
            if not c.execute('select 1 from users where id=?', (b.user_id,)).fetchone():
                raise HTTPException(404, 'notfound')
            c.execute("insert into blocks values(?,?) on conflict do nothing", (u["id"], b.user_id))
        else:
            c.execute("delete from blocks where user_id=? and blocked_id=?", (u["id"], b.user_id))
    return {"ok": True}


async def report_user(user_id: int, u: dict):
    with db() as c:
        p = c.execute("select name from users where id=?", (user_id,)).fetchone()
    if not p:
        raise HTTPException(404, "notfound")
    if ADMIN_ID:
        await notify_admin( f"Profile report: user {user_id} ({p['name']}) by {u['id']}\n/ban {user_id}")
    return {"ok": True}


