import datetime

from app.constants import VIBES


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
    return ",".join((v for v in dict.fromkeys(items or []) if v in VIBES))


def lang_of(code):
    return "ru" if (code or "") in ("ru", "uk", "be", "kk") else "en"
