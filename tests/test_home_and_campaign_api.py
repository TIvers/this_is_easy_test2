from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import get_db
from app.deps import get_keitaro, get_keitaro_if_configured
from app.main import app
from app.models import Base, Campaign, StreamDraft


class FakeKeitaro:
    def __init__(self):
        self.deleted_campaigns = []

    def list_campaigns(self):
        return [{"id": 123, "name": "Renamed in Keitaro"}]

    def delete_campaign(self, campaign_id):
        self.deleted_campaigns.append(campaign_id)


def test_home_uses_live_campaign_name_and_campaign_delete_calls_api(monkeypatch):
    if hasattr(settings, "admin_username"):
        monkeypatch.setattr(settings, "admin_username", "admin")
        monkeypatch.setattr(
            settings,
            "admin_password_hash",
            PasswordHasher().hash("test-password"),
        )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)()
    session.add(
        Campaign(
            keitaro_id=123,
            name="Old saved name",
            geo="US",
            offer_id=34,
            domain_id=1,
            group_id=1,
            source_id=1,
        )
    )
    session.add(StreamDraft(stream_id=456, campaign_id=123))
    session.commit()
    campaign_pk = session.query(Campaign.id).filter_by(keitaro_id=123).scalar()

    fake = FakeKeitaro()
    previous_overrides = app.dependency_overrides.copy()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_keitaro] = lambda: fake
    app.dependency_overrides[get_keitaro_if_configured] = lambda: fake
    try:
        client = TestClient(app)
        if hasattr(settings, "admin_username"):
            login = client.post(
                "/login",
                json={"username": "admin", "password": "test-password"},
            )
            assert login.status_code == 200

        home = client.get("/")
        assert home.status_code == 200
        assert "Renamed in Keitaro" in home.text
        assert "Old saved name" not in home.text
        assert 'data-delete-campaign="123"' in home.text

        response = client.delete("/api/campaigns/123")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert fake.deleted_campaigns == [123]
        assert session.get(Campaign, campaign_pk) is None
        assert session.get(StreamDraft, 456) is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        session.close()
        engine.dispose()
