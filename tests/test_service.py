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
        self.remote_streams = [
            {"id": 10, "schema": "landings", "position": 1, "name": "Base offers"},
            {"id": 20, "schema": "landings", "position": 2, "name": "Other offers"},
        ]
        self.deleted = []
        self.deleted_streams = []
        self.updated = []
        self.hidden_offers = set()
        self.offer_list_calls = 0
        self.stream_offers = {
            10: [{"offer_id": 1, "share": 50}, {"offer_id": 2, "share": 50}],
            20: [{"offer_id": 1, "share": 100}],
        }

    def list_offers(self):
        self.offer_list_calls += 1
        return [
            {"id": i, "name": f"Offer {i}"}
            for i in (1, 2, 3, 4)
            if i not in self.hidden_offers
        ]

    def create_campaign(self, payload):
        self.campaigns.append(payload)
        return {"id": 777}

    def get_campaign(self, campaign_id):
        return {"id": campaign_id, "name": "Test"}

    def create_stream(self, payload):
        if self.fail_second_stream and len(self.streams) == 1:
            raise KeitaroError("boom")
        self.streams.append(payload)
        stream_id = 100 + len(self.streams)
        self.remote_streams.append(
            {
                "id": stream_id,
                "schema": payload["schema"],
                "position": payload["position"],
                "name": payload["name"],
            }
        )
        self.stream_offers[stream_id] = list(payload.get("offers", []))
        return {"id": stream_id}

    def delete_campaign(self, campaign_id):
        self.deleted.append(campaign_id)

    def get_stream(self, stream_id):
        remote = next(stream for stream in self.remote_streams if stream["id"] == stream_id)
        return {
            "id": stream_id,
            "schema": remote["schema"],
            "name": remote["name"],
            "position": remote["position"],
            "offers": list(self.stream_offers.get(stream_id, [])),
        }

    def list_streams(self, campaign_id):
        return list(self.remote_streams)

    def report_by_stream_offer(self, campaign_id, interval):
        return []

    def update_stream(self, stream_id, payload):
        self.updated.append((stream_id, payload))
        self.stream_offers[stream_id] = payload["offers"]

    def delete_stream(self, stream_id):
        self.deleted_streams.append(stream_id)
        self.remote_streams = [
            stream for stream in self.remote_streams if stream["id"] != stream_id
        ]


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
    assert kt.campaigns[0]["alias"].startswith("test-")
    assert kt.campaigns[0]["domain_id"] == 1
    assert kt.campaigns[0]["group_id"] == 2
    assert kt.campaigns[0]["traffic_source_id"] == 3

    geo_stream, offer_stream = kt.streams
    assert geo_stream["position"] == 1
    assert geo_stream["filters"][0]["payload"] == ["PL"]
    assert geo_stream["action_payload"].startswith("https://")
    assert offer_stream["position"] == 2
    assert offer_stream["action_type"] == "http"
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


def test_new_stream_and_offer_changes_wait_for_explicit_push(db):
    kt = FakeKeitaro()
    draft = editor.create_stream_draft(db, kt, 777, "Additional")
    editor.add_offer(db, kt, 777, draft.stream_id, 3)

    view = editor.get_view(db, kt, 777)
    new_stream = next(stream for stream in view["streams"] if stream["is_new"])
    assert new_stream["name"] == "Additional"
    assert new_stream["total"] == 100
    assert new_stream["changed"] is True
    assert kt.streams == []
    assert kt.updated == []

    assert editor.push_all_drafts(db, kt, 777) == 1
    assert len(kt.streams) == 1
    assert kt.streams[0]["name"] == "Additional"
    assert kt.streams[0]["offers"] == [
        {"offer_id": 3, "share": 100, "state": "active"}
    ]


def test_base_stream_cannot_be_removed_and_other_deletions_wait_for_push(db):
    kt = FakeKeitaro()
    with pytest.raises(ValueError, match="Базовый"):
        editor.delete_stream_draft(db, kt, 777, 10)

    editor.delete_stream_draft(db, kt, 777, 20)
    view = editor.get_view(db, kt, 777)
    assert next(stream for stream in view["streams"] if stream["id"] == 20)["is_deleted"]
    assert kt.deleted_streams == []

    editor.push_all_drafts(db, kt, 777)
    assert kt.deleted_streams == [20]


def test_restore_removed_offer_does_not_require_it_in_offer_catalog(db):
    kt = FakeKeitaro()
    editor.remove_offer(db, kt, 777, 10, 1)
    calls_before_restore = kt.offer_list_calls
    kt.hidden_offers.add(1)

    editor.add_offer(db, kt, 777, 10, 1)
    assert kt.offer_list_calls == calls_before_restore

    restored = next(
        offer
        for offer in editor.get_view(db, kt, 777)["streams"][0]["offers"]
        if offer["offer_id"] == 1
    )
    assert restored["is_deleted"] is False
    assert restored["name"] == "Offer 1"
    assert kt.updated == []

