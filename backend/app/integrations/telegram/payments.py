import time
from aiogram import F
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice
from fastapi import APIRouter, Depends, HTTPException
from app.config import BOOST_STARS
from app.db.session import db
from app.api.auth import get_current_user, ensure_ready
from app.services.common import lang_of
from app.integrations.telegram.bot import dp, get_bot

router = APIRouter()

def payment_trip(payload, currency, amount, telegram_id, c):
    if currency!='XTR' or amount!=BOOST_STARS or not payload.startswith('boost:') or not payload[6:].isdigit():
        return None
    trip_id = int(payload[6:])
    c.lock_trip(trip_id)
    return c.execute('''select t.id, t.user_id from trips t join auth_identities a on a.user_id=t.user_id
        where t.id=? and a.provider='telegram' and a.subject=?''',(trip_id,str(telegram_id))).fetchone()

@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    with db() as c:
        trip = payment_trip(q.invoice_payload,q.currency,q.total_amount,q.from_user.id,c)
    await q.answer(ok=bool(trip), **({} if trip else {'error_message':'Invalid payment'}))

@dp.message(F.successful_payment)
async def paid(m: Message):
    payment = m.successful_payment
    with db(write=True) as c:
        trip = payment_trip(payment.invoice_payload,payment.currency,payment.total_amount,m.from_user.id,c)
        if trip is None: return
        charge = payment.telegram_payment_charge_id
        if c.execute('select 1 from payments where charge_id=?',(charge,)).fetchone(): return
        c.execute('insert into payments(charge_id,trip_id,user_id,amount,currency,created) values(?,?,?,?,?,?)',
                  (charge,trip['id'],trip['user_id'],payment.total_amount,payment.currency,int(time.time())))
        c.execute('update trips set boosted_until=? where id=?',(int(time.time())+7*86400,trip['id']))
    await m.answer('Готово: поездка неделю будет вверху табло.' if lang_of(m.from_user.language_code)=='ru'
                   else 'Done: your trip stays at the top of the board for a week.')

@router.post('/api/trips/{trip_id}/boost')
async def boost(trip_id: int, u: dict = Depends(get_current_user)):
    ensure_ready(u)
    with db() as c:
        trip = c.execute('select * from trips where id=? and user_id=?',(trip_id,u['id'])).fetchone()
        identity = c.execute("select 1 from auth_identities where user_id=? and provider='telegram'",(u['id'],)).fetchone()
    if not trip: raise HTTPException(404,'notfound')
    bot = get_bot()
    if bot is None or identity is None: raise HTTPException(503,'telegram_payments_unavailable')
    link = await bot.create_invoice_link(title='Поднять поездку / Boost trip',
        description=f"{trip['dest']}: 7 days on top / 7 дней вверху",payload=f'boost:{trip_id}',currency='XTR',
        prices=[LabeledPrice(label='7 days / 7 дней',amount=BOOST_STARS)])
    return {'link':link}
