"""Тесты сервисов с подменой Keitaro (нужны установленные sqlalchemy и pydantic-settings)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.keitaro.client import KeitaroError
from app.models import Base, Campaign, StreamDraft
from app.services import campaigns as campaigns_service
from app.services import offers as editor


class FakeKeitaro:
    def __init__(self, fail_second_stream=False):
        self.fail_second_stream = fail_second_stream
        self.campaigns = []
        self.streams = []
        self.deleted = []
        self.updated = []
        self.stream_offers = {10: [{"offer_id": 1, "share": 50}, {"offer_id": 2, "share": 50}]}

    def list_offers(self):
        return [{"id": i, "name": f"Offer {i}"} for i in (1, 2, 3, 4)]

    def create_campaign(self, payload):
        self.campaigns.append(payload)
        return {"id": 777}

    def get_campaign(self, campaign_id):
        return {"id": campaign_id, "name": "Test"}

    def create_stream(self, payload):
        if self.fail_second_stream and len(self.streams) == 1:
            raise KeitaroError("boom")
        self.streams.append(payload)
        return {"id": 100 + len(self.streams)}

    def delete_campaign(self, campaign_id):
        self.deleted.append(campaign_id)

    def get_stream(self, stream_id):
        return {
            "id": stream_id,
            "schema": "landings",
            "offers": list(self.stream_offers[stream_id]),
        }

    def list_streams(self, campaign_id):
        return [{"id": 10, "schema": "landings", "position": 1, "name": "Offers"}]

    def report_by_stream_offer(self, campaign_id, interval):
        return []

    def update_stream(self, stream_id, payload):
        self.updated.append((stream_id, payload))


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)()
    yield session
    session.close()


def test_create_campaign_builds_two_streams(db):
    kt = FakeKeitaro()
    c = campaigns_service.create_campaign(
        db, kt, name=" Test ", geo="pl", offer_id=3, domain_id=1, group_id=2, source_id=3
    )
    assert c.keitaro_id == 777 and c.geo == "PL" and c.name == "Test"
    assert kt.campaigns[0]["domain_id"] == 1
    assert kt.campaigns[0]["group_id"] == 2
    assert kt.campaigns[0]["traffic_source_id"] == 3

    geo_stream, offer_stream = kt.streams
    assert geo_stream["position"] == 1
    assert geo_stream["filters"][0]["payload"] == ["PL"]
    assert geo_stream["action_payload"].startswith("https://")
    assert offer_stream["position"] == 2
    assert offer_stream["offers"] == [{"offer_id": 3, "share": 100, "state": "active"}]


def test_create_campaign_rolls_back_on_stream_error(db):
    kt = FakeKeitaro(fail_second_stream=True)
    with pytest.raises(KeitaroError):
        campaigns_service.create_campaign(
            db, kt, name="X", geo="PL", offer_id=1, domain_id=1, group_id=1, source_id=1
        )
    assert kt.deleted == [777]
    assert db.query(Campaign).count() == 0


@pytest.mark.parametrize("geo", ["", "P", "PLX", "1A"])
def test_create_campaign_rejects_bad_geo(db, geo):
    with pytest.raises(ValueError):
        campaigns_service.create_campaign(
            db, FakeKeitaro(), name="X", geo=geo, offer_id=1, domain_id=1, group_id=1, source_id=1
        )


def test_offer_edits_push_balanced_draft_to_keitaro(db):
    kt = FakeKeitaro()
    editor.add_offer(db, kt, 777, 10, 3)
    view = editor.get_view(db, kt, 777)
    stream = view["streams"][0]
    assert stream["drafted"] is True
    assert [offer["share"] for offer in stream["offers"]] == [34, 33, 33]

    editor.push_draft(db, kt, 777, 10)
    assert kt.updated[0][0] == 10
    assert [offer["share"] for offer in kt.updated[0][1]["offers"]] == [34, 33, 33]
    assert editor.get_view(db, kt, 777)["streams"][0]["drafted"] is False

