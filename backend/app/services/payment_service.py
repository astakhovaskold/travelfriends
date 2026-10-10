import time
from aiogram.types import LabeledPrice
from app import errors
from app.config import get_settings
from app.constants import BOOST_DURATION
from app.db.session import Row, Transaction, db
from app.integrations.telegram.bot import get_bot
from app.repositories.payments import PaymentsRepository
from app.services.auth_service import ensure_ready
from app.texts import render_text
from fastapi import HTTPException


def payment_trip(
        payload: str, currency: str, amount: int, telegram_id: int, transaction: Transaction
) -> Row | None:
    if (
            currency != "XTR"
            or amount != get_settings().BOOST_STARS
            or (not payload.startswith("boost:"))
            or (not payload[6:].isdigit())
    ):
        return None
    trip_id = int(payload[6:])
    transaction.lock_trip(trip_id)

    return PaymentsRepository(transaction).payment_trip(trip_id, str(telegram_id))


async def boost(trip_id: int, user: dict):
    ensure_ready(user)

    with db() as transaction:
        repository = PaymentsRepository(transaction)
        trip = repository.owned_trip(trip_id, user["id"])
        identity = repository.telegram_identity(user["id"])
    if not trip:
        raise HTTPException(404, errors.NOTFOUND)
    bot = get_bot()
    if bot is None or identity is None:
        raise HTTPException(503, errors.TELEGRAM_PAYMENTS_UNAVAILABLE)
    link = await bot.create_invoice_link(
        title=render_text("payment.title", "en"),
        description=render_text("payment.description", "en", dest=trip["dest"]),
        payload=f"boost:{trip_id}",
        currency="XTR",
        prices=[
            LabeledPrice(
                label=render_text("payment.label", "en"), amount=get_settings().BOOST_STARS
            )
        ],
    )

    return {"link": link}


def record_payment(payload: str, currency: str, amount: int, telegram_id: int, charge: str) -> bool:
    with db(write=True) as transaction:
        repository = PaymentsRepository(transaction)
        trip = payment_trip(payload, currency, amount, telegram_id, transaction)
        if trip is None:
            return False
        if repository.has_charge(charge):
            return False
        repository.record(charge, trip["id"], trip["user_id"], amount, currency, int(time.time()))
        repository.boost(int(time.time()) + BOOST_DURATION, trip["id"])

    return True


def validate_payment(payload: str, currency: str, amount: int, telegram_id: int) -> bool:
    with db() as transaction:
        return bool(payment_trip(payload, currency, amount, telegram_id, transaction))
