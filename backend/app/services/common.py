import datetime, time
from app.config import VIBES

def today():
    return datetime.date.today().isoformat()


def trip_end(r):
    e = r["date_to"] or r["date_from"]
    if e:
        return e
    return (datetime.date.fromtimestamp(r["created"]) + datetime.timedelta(days=30)).isoformat()


def is_ended(r):
    return trip_end(r) < today()


def age_of(birth):
    if not birth:
        return None
    try:
        b = datetime.date.fromisoformat(birth)
    except ValueError:
        return None
    t = datetime.date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def clean_vibe(items):
    return ",".join(v for v in dict.fromkeys(items or []) if v in VIBES)


def lang_of(code):
    return "ru" if (code or "") in ("ru", "uk", "be", "kk") else "en"


def stats(c, uid):
    r = c.execute("select round(avg(stars),1) a, count(*) n from reviews where to_id=?", (uid,)).fetchone()
    done = 0
    for t in c.execute("""select t.*, (select count(*) from joins j where j.trip_id=t.id) as m
                          from trips t where t.user_id=?""", (uid,)):
        if t["m"] > 0 and is_ended(t):
            done += 1
    for t in c.execute("select t.* from joins j join trips t on t.id=j.trip_id where j.user_id=?", (uid,)):
        if is_ended(t):
            done += 1
    fr = c.execute("""select count(distinct o) from (
        select j2.user_id o from joins j join joins j2 on j2.trip_id=j.trip_id and j2.user_id!=j.user_id where j.user_id=?
        union select t.user_id from joins j join trips t on t.id=j.trip_id where j.user_id=? and t.user_id!=?
        union select j.user_id from trips t join joins j on j.trip_id=t.id where t.user_id=? and j.user_id!=?)""",
                   (uid, uid, uid, uid, uid)).fetchone()[0]
    return {"avg": r["a"], "cnt": r["n"], "trips": done, "friends": fr}


def people(c, trip_id):
    return c.execute("""select u.id, u.lang, u.name from users u
                        where u.id=(select user_id from trips where id=?)
                        union select u.id, u.lang, u.name from joins j join users u on u.id=j.user_id
                        where j.trip_id=?""", (trip_id, trip_id)).fetchall()


def blocked_pair(c, a, b):
    return c.execute("""select 1 from blocks where (user_id=? and blocked_id=?)
                        or (user_id=? and blocked_id=?)""", (a, b, b, a)).fetchone()


def sysmsg(c, trip_id, text):
    c.execute("insert into messages(trip_id,user_id,text,created) values(?,0,?,?)",
              (trip_id, text, int(time.time())))


def add_member(c, trip_id, uid):
    name = c.execute("select name from users where id=?", (uid,)).fetchone()["name"]
    c.execute("insert into joins values(?,?,?) on conflict do nothing", (trip_id, uid, int(time.time())))
    c.execute("update trips set chat_open=1 where id=?", (trip_id,))
    sysmsg(c, trip_id, f"join:{name}")
    return name


