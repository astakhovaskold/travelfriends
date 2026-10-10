import time
from app import errors
from app.constants import REVIEW_MAX_LENGTH, TAGS
from app.db.session import db
from app.repositories.reviews import ReviewsRepository
from app.schemas import Review
from app.services.auth_service import ensure_ready
from app.services.chat_service import chat_access
from app.services.common import is_ended
from app.services.notification_service import safe_send
from app.services.participation_service import people
from app.texts import render_text
from fastapi import HTTPException


async def add_review(review: Review, user: dict):
    ensure_ready(user)
    if not 1 <= review.stars <= 5 or review.to_id == user["id"]:
        raise HTTPException(400, errors.BADREQ)
    tags = ",".join((t for t in dict.fromkeys(review.tags) if t in TAGS))

    with db(write=True) as transaction:
        repository = ReviewsRepository(transaction)
        transaction.lock_trip(review.trip_id)
        trip = chat_access(transaction, review.trip_id, user["id"])
        if not is_ended(trip):
            raise HTTPException(400, errors.NOTENDED)
        if review.to_id not in {p["id"] for p in people(transaction, review.trip_id)}:
            raise HTTPException(400, errors.BADREQ)
        if repository.exists(review.trip_id, user["id"], review.to_id):
            raise HTTPException(400, errors.DUP)
        repository.add(
            review.trip_id,
            user["id"],
            review.to_id,
            review.stars,
            tags,
            review.text.strip()[:REVIEW_MAX_LENGTH],
            int(time.time()),
        )
        lang = repository.recipient_language(review.to_id)["lang"]

    await safe_send(
        review.to_id,
        render_text("review.received", "ru" if lang == "ru" else "en", stars="★" * review.stars),
    )

    return {"ok": True}
