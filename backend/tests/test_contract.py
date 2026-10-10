import datetime
import pytest

from conftest import signed


def test_authentication(api):
    c, _ = api
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/me", headers=signed(timestamp=0)).status_code == 401
    h = signed()
    h["X-Init-Data"] += "tamper"
    assert c.get("/api/me", headers=h).status_code == 401
    r = c.get("/api/me", headers=signed())
    assert r.status_code == 200
    assert r.json()["registered"] == 0
    assert "birth" not in r.json() and "username" not in r.json()


def test_registration_gates(api):
    c, _ = api
    h = signed()
    assert c.get("/api/trips", headers=h).json()["detail"] == "rules"
    assert (
            c.post("/api/register", headers=h, json={"birth": "1990-01-01", "gender": "f"}).json()[
                "detail"
            ]
            == "rules"
    )
    c.post("/api/rules", headers=h)
    assert c.get("/api/trips", headers=h).json()["detail"] == "register"
    assert c.post("/api/register", headers=h, json={"birth": "bad"}).json()["detail"] == "baddate"
    assert (
            c.post(
                "/api/register", headers=h, json={"birth": "1990-01-01", "gender": "bad"}
            ).status_code
            == 400
    )
    birth = (datetime.date.today() - datetime.timedelta(days=3650)).isoformat()
    assert c.post("/api/register", headers=h, json={"birth": birth}).json()["detail"] == "minor"
    assert c.get("/api/me", headers=h).json()["detail"] == "minor"


def test_profile(api, ready):
    c, _ = api
    h = ready()
    assert (
            c.post(
                "/api/profile",
                headers=h,
                json={"city": " Madrid ", "about": " Hi ", "vibe": ["food", "food", "bad"]},
            ).status_code
            == 200
    )
    p = c.get("/api/users/101", headers=h).json()
    assert p["city"] == "Madrid" and p["vibe"] == ["food"]
    assert c.get("/api/users/999", headers=h).status_code == 404


@pytest.mark.parametrize(
    "body,error",
    [
        ({"dest": " "}, "nodest"),
        ({"dest": "X", "audience": "bad"}, "badreq"),
        ({"dest": "X", "kind": "plan"}, "baddate"),
        ({"dest": "X", "min_age": 50, "max_age": 30}, "badreq"),
        ({"dest": "X", "date_to": "2000-01-01"}, "baddate"),
    ],
)
def test_trip_validation(api, ready, body, error):
    c, _ = api
    assert c.post("/api/trips", headers=ready(), json=body).json()["detail"] == error


def test_trip_limit_and_listing(api, ready, trip):
    c, _ = api
    for _ in range(5):
        trip()
    assert (
            c.post("/api/trips", headers=signed(), json={"dest": "Sixth"}).json()["detail"] == "limit"
    )
    rows = c.get("/api/trips", headers=ready(202)).json()
    assert len(rows) == 5 and rows[0]["mine"] is False
    assert c.get("/api/trips/999", headers=signed()).status_code == 404


def test_join_capacity_idempotency_leave(api, ready, trip):
    c, _ = api
    tid = trip(people=1)
    h = ready(202)
    assert c.post(f"/api/trips/{tid}/join", headers=signed()).json()["detail"] == "own"
    assert c.post(f"/api/trips/{tid}/join", headers=h).json() == {"ok": True, "full": True}
    assert c.post(f"/api/trips/{tid}/join", headers=h).status_code == 200
    assert c.post(f"/api/trips/{tid}/join", headers=ready(303)).json()["detail"] == "full"
    assert len(c.get(f"/api/trips/{tid}/people", headers=h).json()["members"]) == 2
    assert c.post(f"/api/trips/{tid}/leave", headers=h).status_code == 200
    assert c.get(f"/api/trips/{tid}/chat", headers=h).json()["detail"] == "notmember"


@pytest.mark.parametrize(
    "options,gender,error",
    [({"audience": "f"}, "m", "audience"), ({"min_age": 80}, "f", "agerange")],
)
def test_join_restrictions(api, ready, trip, options, gender, error):
    c, _ = api
    tid = trip(**options)
    assert c.post(f"/api/trips/{tid}/join", headers=ready(202, gender)).json()["detail"] == error


def test_approval_accept_decline(api, ready, trip):
    c, _ = api
    tid = trip(approval=1, people=2)
    h = ready(202)
    assert c.post(f"/api/trips/{tid}/join", headers=h).json()["pending"]
    assert c.get(f"/api/trips/{tid}/chat", headers=h).status_code == 403
    assert c.get(f"/api/trips/{tid}/requests", headers=h).status_code == 404
    assert c.get(f"/api/trips/{tid}/requests", headers=signed()).json()[0]["id"] == 202
    assert c.post(f"/api/trips/{tid}/requests/202/accept", headers=signed()).status_code == 200
    assert c.get(f"/api/trips/{tid}/chat", headers=h).status_code == 200
    h2 = ready(303)
    c.post(f"/api/trips/{tid}/join", headers=h2)
    assert c.post(f"/api/trips/{tid}/requests/303/decline", headers=signed()).status_code == 200
    assert c.post(f"/api/trips/{tid}/join", headers=h2).json()["detail"] == "declined"


def test_kick_close_block(api, ready, trip):
    c, _ = api
    tid = trip()
    h = ready(202)
    c.post(f"/api/trips/{tid}/join", headers=h)
    assert c.post(f"/api/trips/{tid}/kick", headers=h, json={"user_id": 101}).status_code == 404
    assert (
            c.post(f"/api/trips/{tid}/kick", headers=signed(), json={"user_id": 202}).status_code == 200
    )
    assert c.post(f"/api/trips/{tid}/join", headers=h).json()["detail"] == "kicked"
    c.post("/api/block", headers=h, json={"user_id": 101})
    assert c.get("/api/trips", headers=h).json() == []
    assert c.post(f"/api/trips/{tid}/join", headers=h).json()["detail"] == "blocked"
    c.post("/api/block", headers=h, json={"user_id": 101, "on": False})
    assert c.post(f"/api/trips/{tid}/close", headers=signed()).status_code == 200
    assert c.post(f"/api/trips/{tid}/join", headers=ready(303)).json()["detail"] == "tripclosed"


def test_chat_reactions_reports(api, ready, trip):
    c, _ = api
    tid = trip()
    h = ready(202)
    assert c.get(f"/api/trips/{tid}/chat", headers=signed()).json()["detail"] == "closed"
    c.post(f"/api/trips/{tid}/join", headers=h)
    assert (
            c.post(f"/api/trips/{tid}/messages", headers=h, json={"text": " "}).json()["detail"]
            == "empty"
    )
    assert (
            c.post(f"/api/trips/{tid}/messages", headers=h, json={"text": " Hello "}).status_code == 200
    )
    data = c.get(f"/api/trips/{tid}/chat", headers=h).json()
    mid = data["messages"][-1]["id"]
    assert data["messages"][-1]["text"] == "Hello"
    assert c.get(f"/api/trips/{tid}/chat?since={mid}", headers=h).json()["messages"] == []
    assert (
            c.post(f"/api/messages/{mid}/react", headers=signed(), json={"emoji": "👍"}).status_code
            == 200
    )
    assert c.get(f"/api/trips/{tid}/chat", headers=signed()).json()["reactions"][str(mid)][
               "👍"
           ] == [1, 1]
    c.post(f"/api/messages/{mid}/react", headers=signed(), json={"emoji": "👍"})
    assert c.get(f"/api/trips/{tid}/chat", headers=h).json()["reactions"] == {}
    assert c.post(f"/api/messages/{mid}/report", headers=signed()).status_code == 200
    assert c.post("/api/users/202/report", headers=signed()).status_code == 200
    outsider = ready(303)
    assert (
            c.post(f"/api/messages/{mid}/react", headers=outsider, json={"emoji": "👍"}).status_code
            == 403
    )
    for _ in range(14):
        c.post(f"/api/trips/{tid}/messages", headers=h, json={"text": "x"})
    assert c.post(f"/api/trips/{tid}/messages", headers=h, json={"text": "x"}).status_code == 429


def test_reviews(api, ready, trip):
    c, module = api
    tid = trip()
    h = ready(202)
    c.post(f"/api/trips/{tid}/join", headers=h)
    body = {"trip_id": tid, "to_id": 101, "stars": 5, "tags": ["fun", "bad", "fun"]}
    assert c.post("/api/reviews", headers=h, json=body).json()["detail"] == "notended"
    with module.db() as db:
        db.execute("update trips set date_to=? where id=?", ("2000-01-01", tid))
    assert c.post("/api/reviews", headers=h, json=body).status_code == 200
    assert c.post("/api/reviews", headers=h, json=body).json()["detail"] == "dup"
    p = c.get("/api/users/101", headers=h).json()
    assert p["avg"] == 5 and p["cnt"] == 1 and p["tags"] == {"fun": 1}


def test_boost(api, ready, trip):
    c, module = api
    tid = trip()
    assert c.post(f"/api/trips/{tid}/boost", headers=ready(202)).status_code == 404
    assert (
            c.post(f"/api/trips/{tid}/boost", headers=signed()).json()["link"]
            == "https://example.test/invoice"
    )
    args = module.bot.create_invoice_link.call_args.kwargs
    assert args["currency"] == "XTR" and args["payload"] == f"boost:{tid}"


def test_trip_response_contract_and_pending_visibility(api, ready, trip):
    c, _ = api
    tid = trip(approval=1, people=1)
    h = ready(202)
    c.post(f"/api/trips/{tid}/join", headers=h)
    d = c.get(f"/api/trips/{tid}", headers=signed()).json()
    assert d["pending"] == 1 and d["members"] == 0 and d["mine"] is True and d["ended"] is False
    assert d["author_id"] == 101 and d["name"] == "User 101" and d["a_cnt"] == 0
    assert d["joined"] == 0 and d["req"] is None and isinstance(d["boosted"], int)
    guest = c.get(f"/api/trips/{tid}", headers=h).json()
    assert guest["pending"] == 0 and guest["req"] == "pending"
    assert c.post(f"/api/trips/{tid}/requests/202/accept", headers=h).status_code == 404
    assert c.post(f"/api/trips/{tid}/requests/202/accept", headers=signed()).status_code == 200
    assert c.post(f"/api/trips/{tid}/requests/202/accept", headers=signed()).status_code == 404
    mine = c.get("/api/my", headers=h).json()
    assert mine["mine"] == [] and mine["joined"][0]["joined"] == 1
    assert mine["joined"][0]["requests"] == 1 and mine["joined"][0]["to_rate"] == 0


def test_pending_request_survives_full_accept(api, ready, trip):
    c, _ = api
    tid = trip(approval=1)
    h1 = ready(202)
    h2 = ready(303)
    for h in [h1, h2]:
        assert c.post(f"/api/trips/{tid}/join", headers=h).status_code == 200
    c.post(f"/api/trips/{tid}/requests/202/accept", headers=signed())
    r = c.post(f"/api/trips/{tid}/requests/303/accept", headers=signed())
    assert r.status_code == 400 and r.json()["detail"] == "full"
    assert c.get(f"/api/trips/{tid}/requests", headers=signed()).json()[0]["id"] == 303


def test_expired_closed_and_reverse_block_filter(api, ready, trip):
    c, m = api
    tid = trip()
    h = ready(202)
    c.post("/api/block", headers=signed(), json={"user_id": 202})
    assert c.get("/api/trips", headers=h).json() == []
    c.post("/api/block", headers=signed(), json={"user_id": 202, "on": False})
    with m.db() as db:
        db.execute("update trips set date_to=? where id=?", ("2000-01-01", tid))
    assert c.get("/api/trips", headers=h).json() == []
    assert c.get(f"/api/trips/{tid}", headers=signed()).json()["ended"] is True


def test_block_nonexistent_target(api, ready):
    c, _ = api
    r = c.post("/api/block", headers=ready(), json={"user_id": 999})
    assert r.status_code == 404 and r.json()["detail"] == "notfound"


@pytest.mark.parametrize(
    "change,error,status",
    [("closed=1", "tripclosed", 400), ("date_to='2000-01-01'", "tripended", 400)],
)
def test_accept_rejects_closed_or_expired(api, ready, trip, change, error, status):
    c, m = api
    tid = trip(approval=1)
    h = ready(202)
    c.post(f"/api/trips/{tid}/join", headers=h)
    with m.db() as db:
        db.execute(f"update trips set {change} where id=?", (tid,))
    r = c.post(f"/api/trips/{tid}/requests/202/accept", headers=signed())
    assert r.status_code == status and r.json()["detail"] == error
    assert len(c.get(f"/api/trips/{tid}/requests", headers=signed()).json()) == 1
