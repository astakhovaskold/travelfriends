import time
from fastapi import HTTPException
from app.db.session import db
from app.schemas import Review
from app.services.common import is_ended, people
from app.config import TAGS
from app.services.notification_service import safe_send
from app.api.auth import ensure_ready

from app.services.chat_service import chat_access
async def add_review(r: Review, u: dict):
    ensure_ready(u)
    if not 1 <= r.stars <= 5 or r.to_id == u["id"]:
        raise HTTPException(400, "badreq")
    tags = ",".join(t for t in dict.fromkeys(r.tags) if t in TAGS)
    with db(write=True) as c:
        c.lock_trip(r.trip_id)
        trip = chat_access(c, r.trip_id, u["id"])
        if not is_ended(trip):
            raise HTTPException(400, "notended")
        if r.to_id not in {p["id"] for p in people(c, r.trip_id)}:
            raise HTTPException(400, "badreq")
        if c.execute("select 1 from reviews where trip_id=? and from_id=? and to_id=?",
                     (r.trip_id, u["id"], r.to_id)).fetchone():
            raise HTTPException(400, "dup")
        c.execute("insert into reviews(trip_id,from_id,to_id,stars,tags,text,created) values(?,?,?,?,?,?,?)",
                  (r.trip_id, u["id"], r.to_id, r.stars, tags, r.text.strip()[:300], int(time.time())))
        lang = c.execute("select lang from users where id=?", (r.to_id,)).fetchone()["lang"]
    await safe_send(r.to_id, f"⭐ Тебе оставили отзыв: {'★' * r.stars}" if lang == "ru"
                    else f"⭐ You got a new review: {'★' * r.stars}")
    return {"ok": True}


