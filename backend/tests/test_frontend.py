from app import main
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


def test_api_does_not_serve_frontend():
    client = TestClient(main.app)
    for path in ("/", "/next/", "/legacy/", "/assets-app/assets/app.js"):
        assert client.get(path).status_code == 404
    assert client.get("/api/config").status_code == 200
    assert client.get("/docs").status_code == 200


def test_cross_origin_telegram_request():
    app = CORSMiddleware(
        main.app,
        allow_origins=["https://frontend.example"],
        allow_methods=["POST"],
        allow_headers=["Content-Type", "Authorization", "X-Init-Data"],
    )
    client = TestClient(app)
    headers = {
        "Origin": "https://frontend.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-init-data,authorization",
    }
    response = client.options("/api/auth/telegram", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://untrusted.example"
    response = client.options("/api/auth/telegram", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
