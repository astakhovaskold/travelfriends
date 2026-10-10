from app import config, main
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient


def test_frontend_preview_and_rollback(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.html"
    legacy.write_text("<h1>Legacy</h1>")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<script src="/assets-app/assets/app.js"></script>')
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text('console.log("Solid")')
    monkeypatch.setattr(
        config,
        "_settings",
        config.get_settings().model_copy(
            update={"FRONTEND_PATH": legacy, "FRONTEND_DIST": dist, "FRONTEND_RELEASE": False}
        ),
    )
    mount = next(
        route for route in main.app.routes if getattr(route, "name", None) == "frontend-assets"
    )
    monkeypatch.setattr(mount, "app", StaticFiles(directory=dist))
    client = TestClient(main.app)
    assert client.get("/").text == "<h1>Legacy</h1>"
    assert "/assets-app/assets/app.js" in client.get("/next/").text
    assert client.get("/assets-app/assets/app.js").status_code == 200
    assert client.get("/assets-app/assets/missing.js").status_code == 404
    assert client.get("/legacy/").text == "<h1>Legacy</h1>"
    monkeypatch.setattr(
        config, "_settings", config.get_settings().model_copy(update={"FRONTEND_RELEASE": True})
    )
    assert client.get("/").text == client.get("/next/").text
    assert client.get("/legacy/").text == "<h1>Legacy</h1>"
    assert client.get("/api/config").status_code == 200
    assert client.get("/docs").status_code == 200


def test_missing_build_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "_settings", config.get_settings().model_copy(update={"FRONTEND_DIST": tmp_path})
    )
    response = TestClient(main.app).get("/next/")
    assert response.status_code == 503
    assert "Frontend build missing" in response.json()["detail"]
