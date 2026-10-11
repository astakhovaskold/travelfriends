import datetime
from app import errors
from app.config import get_settings
from app.constants import ABOUT_MAX_LENGTH, CITY_MAX_LENGTH, GENDERS, PROFILE_MAX_AGE
from app.db.session import db
from app.repositories.users import UsersRepository
from app.schemas import BlockReq, Profile, Reg
from app.services.auth_service import ensure_ready
from app.services.common import age_of, clean_vibe
from app.services.notification_service import notify_admin
from app.services.participation_service import stats
from app.texts import render_text
from fastapi import HTTPException


def me(user: dict):
    with db() as transaction:
        data = dict(UsersRepository(transaction).get(user["id"]))
        data.update(stats(transaction, user["id"]))
    data["age"] = age_of(data.pop("birth", None))
    data.pop("username", None)

    return data


def accept_rules(user: dict):
    with db() as transaction:
        UsersRepository(transaction).accept_rules(user["id"])

    return {"ok": True}


def register(request: Reg, user: dict):
    with db() as transaction:
        row = UsersRepository(transaction).registration_state(user["id"])
    if not row["rules_ok"] and not request.rules_accepted:
        raise HTTPException(403, errors.RULES)
    try:
        birth_date = datetime.date.fromisoformat(request.birth)
    except ValueError:
        raise HTTPException(400, errors.BADDATE)

    age = age_of(request.birth)
    if birth_date > datetime.date.today() or age is None or age > PROFILE_MAX_AGE:
        raise HTTPException(400, errors.BADDATE)
    if age < 18:
        with db() as transaction:
            UsersRepository(transaction).mark_minor(user["id"])
        raise HTTPException(403, errors.MINOR)
    if request.gender not in GENDERS:
        raise HTTPException(400, errors.BADREQ)

    with db() as transaction:
        UsersRepository(transaction).register(
            request.birth,
            request.gender,
            clean_vibe(request.vibe),
            request.city.strip()[:CITY_MAX_LENGTH],
            request.about.strip()[:ABOUT_MAX_LENGTH],
            user["id"],
        )

    return {"ok": True}


def save_profile(request: Profile, user: dict):
    ensure_ready(user)

    with db() as transaction:
        UsersRepository(transaction).update_profile(
            request.city.strip()[:CITY_MAX_LENGTH],
            request.about.strip()[:ABOUT_MAX_LENGTH],
            clean_vibe(request.vibe),
            user["id"],
        )

    return {"ok": True}


def profile(user_id: int, user: dict):
    ensure_ready(user)

    with db() as transaction:
        repository = UsersRepository(transaction)
        profile = repository.public_profile(user_id)
        if not profile:
            raise HTTPException(404, errors.NOTFOUND)
        statistics = stats(transaction, user_id)
        reviews = repository.profile_reviews(user_id)
        tags = {}
        for review in repository.review_tags(user_id):
            for tag in filter(None, review["tags"].split(",")):
                tags[tag] = tags.get(tag, 0) + 1
        blocked = bool(repository.is_blocked(user["id"], user_id))

    return {
        "id": user_id,
        "name": profile["name"],
        "age": age_of(profile["birth"]),
        "city": profile["city"],
        "about": profile["about"],
        "vibe": [v for v in (profile["vibe"] or "").split(",") if v],
        **statistics,
        "tags": tags,
        "me": user_id == user["id"],
        "blocked": blocked,
        "reviews": [
            {**dict(review), "tags": [t for t in review["tags"].split(",") if t]}
            for review in reviews
        ],
    }


def block(request: BlockReq, user: dict):
    if request.user_id == user["id"]:
        raise HTTPException(400, errors.OWN)

    with db() as transaction:
        repository = UsersRepository(transaction)
        if request.on:
            if not repository.exists(request.user_id):
                raise HTTPException(404, errors.NOTFOUND)
            repository.block(user["id"], request.user_id)
        else:
            repository.unblock(user["id"], request.user_id)

    return {"ok": True}


async def report_user(user_id: int, user: dict):
    with db() as transaction:
        profile = UsersRepository(transaction).report_subject(user_id)
    if not profile:
        raise HTTPException(404, errors.NOTFOUND)

    if get_settings().ADMIN_ID:
        await notify_admin(
            render_text(
                "admin.profile_report",
                "en",
                user_id=user_id,
                name=profile["name"],
                reporter_id=user["id"],
            )
        )

    return {"ok": True}
