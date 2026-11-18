from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.auth import require_login
from app.db import get_db
from app.deps import get_keitaro
from app.keitaro.client import KeitaroClient
from app.models import Campaign
from app.services import campaigns as campaigns_service

router = APIRouter(prefix="/api", dependencies=[Depends(require_login)])


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo: str = Field(pattern=r"^[A-Za-z]{2}$")
    offer_id: int = Field(gt=0)
    domain_id: int | None = Field(default=None, gt=0)
    group_id: int | None = Field(default=None, gt=0)
    source_id: int | None = Field(default=None, gt=0)


def _short(items: list[dict]) -> list[dict]:
    return [{"id": item["id"], "name": item.get("name", str(item["id"]))} for item in items]


@router.get("/meta")
def meta(client: KeitaroClient = Depends(get_keitaro)):
    return {
        "domains": _short(client.list_domains()),
        "groups": _short(client.list_groups()),
        "sources": _short(client.list_traffic_sources()),
        "offers": _short(client.list_offers()),
        "defaults": {
            "domain_id": settings.default_domain_id,
            "group_id": settings.default_group_id,
            "source_id": settings.default_source_id,
        },
    }


@router.post("/campaigns", status_code=201)
def create_campaign(
    body: CampaignIn,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    campaign = campaigns_service.create_campaign(db, client, **body.model_dump())
    return {
        "id": campaign.id,
        "keitaro_id": campaign.keitaro_id,
        "name": campaign.name,
        "geo": campaign.geo,
        "offer_id": campaign.offer_id,
    }


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return list(db.scalars(select(Campaign).order_by(Campaign.created_at.desc())))


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, client: KeitaroClient = Depends(get_keitaro)):
    return client.get_campaign(campaign_id)
