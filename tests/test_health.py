from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_explain_contract():
    payload = {
        "selected_text": "горе от ума",
        "context": "Чацкий произносит монолог...",
        "book_title": "Горе от ума",
    }
    response = client.post("/api/v1/explain", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "translation",
        "context_meaning",
        "slang_or_etymology",
        "image_prompt",
    }


def test_explain_requires_context():
    response = client.post("/api/v1/explain", json={"selected_text": "x"})
    assert response.status_code == 422