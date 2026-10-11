from app import main
from fastapi.testclient import TestClient


def test_api_does_not_serve_frontend():
    client = TestClient(main.app)
    for path in ("/", "/next/", "/legacy/", "/assets-app/assets/app.js"):
        assert client.get(path).status_code == 404
    assert client.get("/api/config").status_code == 200
    assert client.get("/docs").status_code == 200
