import pytest
from app.repositories.participation import ParticipationRepository

from conftest import signed


@pytest.mark.parametrize("approval", [0, 1])
def test_membership_and_system_message_roll_back_together(api, ready, trip, monkeypatch, approval):
    client, module = api
    trip_id = trip(approval=approval)
    headers = ready(202)
    if approval:
        assert client.post(f"/api/trips/{trip_id}/join", headers=headers).status_code == 200
    module.safe_send.reset_mock()

    def fail_message(*args, **kwargs):
        raise RuntimeError("Simulated failure after adding participant")

    monkeypatch.setattr(ParticipationRepository, "system_message", fail_message)
    url = f"/api/trips/{trip_id}/requests/202/accept" if approval else f"/api/trips/{trip_id}/join"
    with pytest.raises(RuntimeError, match="Simulated failure"):
        client.post(url, headers=signed() if approval else headers)

    with module.db() as transaction:
        assert (
                transaction.execute(
                    "select count(*) from joins where trip_id=?", (trip_id,)
                ).fetchone()[0]
                == 0
        )
        assert (
                transaction.execute("select chat_open from trips where id=?", (trip_id,)).fetchone()[0]
                == 0
        )
        assert (
                transaction.execute(
                    "select count(*) from messages where trip_id=?", (trip_id,)
                ).fetchone()[0]
                == 0
        )
        if approval:
            assert (
                    transaction.execute(
                        "select status from requests where trip_id=? and user_id=202", (trip_id,)
                    ).fetchone()[0]
                    == "pending"
            )
    module.safe_send.assert_not_awaited()


def test_notification_runs_after_membership_commit(api, ready, trip, monkeypatch):
    from app.services import trip_service

    client, module = api
    trip_id = trip()
    headers = ready(202)
    observed = []

    async def observe(*args, **kwargs):
        assert module.engine.pool.checkedout() == 0
        with module.db() as transaction:
            observed.append(
                transaction.execute(
                    "select count(*) from joins where trip_id=?", (trip_id,)
                ).fetchone()[0]
            )

    monkeypatch.setattr(trip_service, "safe_send", observe)
    assert client.post(f"/api/trips/{trip_id}/join", headers=headers).status_code == 200
    assert observed == [1]
