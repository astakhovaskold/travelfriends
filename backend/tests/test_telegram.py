import asyncio
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from conftest import signed


def test_bot_start_and_admin(api, ready, monkeypatch):
    c, m = api
    ready()
    msg = NS(from_user=NS(id=101, language_code="en"), answer=AsyncMock())
    asyncio.run(m.start(msg, NS(args="trip_7")))
    assert (
        msg.answer.call_args.kwargs["reply_markup"]
        .inline_keyboard[0][0]
        .web_app.url.endswith("?trip=7")
    )
    from app import config

    monkeypatch.setattr(
        config, "_settings", config.get_settings().model_copy(update={"ADMIN_ID": 101})
    )
    asyncio.run(m.cmd_ban(msg, NS(args="101")))
    assert c.get("/api/me", headers=signed()).json()["detail"] == "banned"
    asyncio.run(m.cmd_unban(msg, NS(args="101")))
    assert c.get("/api/me", headers=signed()).status_code == 200
    asyncio.run(m.cmd_stats(msg))
    assert "Users: 1" in msg.answer.call_args.args[0]
    asyncio.run(m.cmd_ban(msg, NS(args="bad")))
    assert msg.answer.call_args.args[0] == "/ban <user id>"


def test_payment_and_review_prompts(api, ready, trip):
    c, m = api
    tid = trip()
    h = ready(202)
    c.post(f"/api/trips/{tid}/join", headers=h)
    payment = NS(
        invoice_payload=f"boost:{tid}",
        currency="XTR",
        total_amount=50,
        telegram_payment_charge_id="test-charge",
    )
    msg = NS(
        from_user=NS(id=101, language_code="en"), successful_payment=payment, answer=AsyncMock()
    )
    asyncio.run(m.paid(msg))
    with m.db() as db:
        assert (
                db.execute("select boosted_until from trips where id=?", (tid,)).fetchone()[0]
                > time.time()
        )
        db.execute("update trips set date_to=? where id=?", ("2000-01-01", tid))
    m.safe_send.reset_mock()
    asyncio.run(m.send_prompts())
    assert m.safe_send.call_count == 2
    assert {call.args[0] for call in m.safe_send.call_args_list} == {101, 202}
    count = m.safe_send.call_count
    asyncio.run(m.send_prompts())
    assert m.safe_send.call_count == count


def test_pre_checkout(api, trip):
    _, m = api
    tid = trip()
    q = NS(
        answer=AsyncMock(),
        invoice_payload=f"boost:{tid}",
        currency="XTR",
        total_amount=50,
        from_user=NS(id=101),
    )
    asyncio.run(m.pre_checkout(q))
    q.answer.assert_awaited_once_with(ok=True)


def test_payment_validation_and_idempotency(api, trip):
    c, m = api
    tid = trip()
    payment = NS(
        invoice_payload=f"boost:{tid}",
        currency="XTR",
        total_amount=50,
        telegram_payment_charge_id="unique",
    )
    msg = NS(
        from_user=NS(id=101, language_code="en"), successful_payment=payment, answer=AsyncMock()
    )
    for currency, amount, payload in [
        ("USD", 50, f"boost:{tid}"),
        ("XTR", 49, f"boost:{tid}"),
        ("XTR", 50, "bad"),
    ]:
        payment.currency = currency
        payment.total_amount = amount
        payment.invoice_payload = payload
        asyncio.run(m.paid(msg))
        assert msg.answer.call_count == 0
    payment.currency = "XTR"
    payment.total_amount = 50
    payment.invoice_payload = f"boost:{tid}"
    asyncio.run(m.paid(msg))
    with m.db() as db:
        first = db.execute("select boosted_until from trips where id=?", (tid,)).fetchone()[0]
    asyncio.run(m.paid(msg))
    with m.db() as db:
        assert db.execute("select count(*) from payments").fetchone()[0] == 1
        assert (
                db.execute("select boosted_until from trips where id=?", (tid,)).fetchone()[0] == first
        )
    assert msg.answer.call_count == 1
    q = NS(
        answer=AsyncMock(),
        invoice_payload=f"boost:{tid}",
        currency="XTR",
        total_amount=50,
        from_user=NS(id=202),
    )
    asyncio.run(m.pre_checkout(q))
    assert q.answer.call_args.kwargs["ok"] is False


def test_notification_uses_linked_telegram_id_and_admin_raw_id(api, monkeypatch):
    _, m = api
    fake = NS(send_message=AsyncMock())
    monkeypatch.setattr(m.worker, "get_bot", lambda: fake)
    with m.db() as db:
        db.execute(
            "update auth_identities set subject='909090' where user_id=101 and provider='telegram'"
        )
    asyncio.run(m.real_sender(101, "hello"))
    fake.send_message.assert_awaited_once_with(909090, "hello", reply_markup=None)
    from app import config

    monkeypatch.setattr(
        config, "_settings", config.get_settings().model_copy(update={"ADMIN_ID": 818181})
    )
    asyncio.run(m.notification.notify_admin("report"))
    assert fake.send_message.call_args.args == (818181, "report")


def test_worker_polling_and_cleanup(api, monkeypatch):
    _, m = api
    fake = NS(set_chat_menu_button=AsyncMock(), session=NS(close=AsyncMock()))
    monkeypatch.setattr(m.worker, "get_bot", lambda: fake)
    monkeypatch.setattr(m.worker.dp, "start_polling", AsyncMock())
    monkeypatch.setattr(m.notification, "prompt_loop", AsyncMock())
    asyncio.run(m.worker.run())
    m.worker.dp.start_polling.assert_awaited_once_with(fake)
    fake.session.close.assert_awaited_once()
    assert len(m.worker.dp.pre_checkout_query.handlers) == 1
    assert any(
        "successful_payment" in str(h.filters) or h.callback.__name__ == "paid"
        for h in m.worker.dp.message.handlers
    )
