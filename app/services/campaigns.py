import logging
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.keitaro.client import KeitaroClient
from app.models import Campaign

log = logging.getLogger(__name__)
GEO_RE = re.compile(r"^[A-Z]{2}$")


def build_geo_stream(campaign_id: int, geo: str, redirect_url: str) -> dict:
    return {
        "campaign_id": campaign_id,
        "name": f"{geo} -> Google",
        "type": "regular",
        "position": 1,
        "weight": 100,
        "schema": "redirect",
        "action_type": "http",
        "action_payload": redirect_url,
        "collect_clicks": True,
        "filter_or": False,
        "filters": [{"name": "country", "mode": "accept", "payload": [geo]}],
        "state": "active",
    }


def build_offer_stream(campaign_id: int, offer_id: int) -> dict:
    return {
        "campaign_id": campaign_id,
        "name": "Offer",
        "type": "regular",
        "position": 2,
        "weight": 100,
        "schema": "landings",
        "collect_clicks": True,
        "filter_or": False,
        "filters": [],
        "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
        "state": "active",
    }


def create_campaign(
    db: Session,
    client: KeitaroClient,
    *,
    name: str,
    geo: str,
    offer_id: int,
    domain_id: int | None = None,
    group_id: int | None = None,
    source_id: int | None = None,
) -> Campaign:
    name = name.strip()
    geo = geo.strip().upper()
    if not name:
        raise ValueError("Название кампании не может быть пустым")
    if not GEO_RE.fullmatch(geo):
        raise ValueError("Гео-код должен состоять из двух латинских букв (например, PL)")

    domain_id = domain_id if domain_id is not None else settings.default_domain_id
    group_id = group_id if group_id is not None else settings.default_group_id
    source_id = source_id if source_id is not None else settings.default_source_id
    for label, value in (("домен", domain_id), ("группа", group_id), ("источник", source_id)):
        if value is None:
            raise ValueError(f"Не выбран {label} (выберите в форме или задайте DEFAULT_* в .env)")

    if offer_id not in {int(offer["id"]) for offer in client.list_offers()}:
        raise ValueError(f"Оффер {offer_id} не найден в Keitaro")

    created = client.create_campaign(
        {
            "name": name,
            "type": "position",
            "state": "active",
            "domain_id": domain_id,
            "group_id": group_id,
            "traffic_source_id": source_id,
        }
    )
    keitaro_id = int(created["id"])
    try:
        client.create_stream(build_geo_stream(keitaro_id, geo, settings.redirect_url))
        client.create_stream(build_offer_stream(keitaro_id, offer_id))
        campaign = Campaign(
            keitaro_id=keitaro_id,
            name=name,
            geo=geo,
            offer_id=offer_id,
            domain_id=domain_id,
            group_id=group_id,
            source_id=source_id,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign
    except Exception:
        db.rollback()
        try:
            client.delete_campaign(keitaro_id)
        except Exception:
            log.exception("Could not clean up Keitaro campaign %s after failed creation", keitaro_id)
        raise
