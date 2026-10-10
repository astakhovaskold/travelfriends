from fastapi.testclient import TestClient
from app.main import app


def test_api_lifecycle_does_not_start_telegram(api,monkeypatch):
    _,m=api
    def forbidden(): raise AssertionError('API must not initialize Telegram')
    monkeypatch.setattr(m.worker,'get_bot',forbidden)
    with TestClient(app) as client:
        assert client.get('/health').json()=={'status':'ok'}
        assert client.get('/').status_code==200
        assert 'Trips start with people' in client.get('/').text or '<html' in client.get('/').text
        assert client.get('/api/config').status_code==200
