from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_login_protects_pages_and_api(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(
        settings,
        "admin_password_hash",
        PasswordHasher().hash("test-password"),
    )
    client = TestClient(app, follow_redirects=False)

    assert client.get("/campaigns/777").status_code == 303
    assert client.get("/api/campaigns").status_code == 401

    response = client.post(
        "/login",
        json={"username": "admin", "password": "test-password", "next": "/campaigns/777"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "next": "/campaigns/777"}
    assert client.get("/campaigns/777").status_code == 200
    assert client.get("/docs").status_code == 200

    assert client.post("/logout").status_code == 200
    assert client.get("/campaigns/777").status_code == 303


def test_login_rejects_bad_password_and_external_redirect(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(
        settings,
        "admin_password_hash",
        PasswordHasher().hash("test-password"),
    )
    client = TestClient(app, follow_redirects=False)

    invalid = client.post(
        "/login",
        json={"username": "admin", "password": "wrong", "next": "https://example.com"},
    )
    assert invalid.status_code == 401

    valid = client.post(
        "/login",
        json={"username": "admin", "password": "test-password", "next": "https://example.com"},
    )
    assert valid.status_code == 200
    assert valid.json()["next"] == "/"
