from aiogram import F
from aiogram.types import Message, PreCheckoutQuery
from app.api.auth import get_current_user
from app.integrations.telegram.bot import dp
from app.services import payment_service as service
from app.services.common import lang_of
from app.texts import render_text
from fastapi import APIRouter, Depends

router = APIRouter()


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    valid = service.validate_payment(q.invoice_payload, q.currency, q.total_amount, q.from_user.id)
    await q.answer(
        ok=valid, **{} if valid else {"error_message": render_text("payment.invalid", "en")}
    )


@dp.message(F.successful_payment)
async def paid(m: Message):
    payment = m.successful_payment
    recorded = service.record_payment(
        payment.invoice_payload,
        payment.currency,
        payment.total_amount,
        m.from_user.id,
        payment.telegram_payment_charge_id,
    )
    if recorded:
        await m.answer(
            render_text(
                "payment.completed", "ru" if lang_of(m.from_user.language_code) == "ru" else "en"
            )
        )


@router.post("/api/trips/{trip_id}/boost")
async def boost(trip_id: int, u: dict = Depends(get_current_user)):
    return await service.boost(trip_id, u)
