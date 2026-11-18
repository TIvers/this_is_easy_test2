from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_keitaro
from app.keitaro.client import KeitaroClient
from app.services import offers as offers_service

router = APIRouter(prefix="/api/campaigns")


class OfferIn(BaseModel):
    offer_id: int = Field(gt=0)


class ShareIn(BaseModel):
    share: int = Field(ge=0, le=100)


@router.get("/{campaign_id}/editor")
def editor_view(
    campaign_id: int,
    interval: str = Query(
        "today",
        pattern="^(today|yesterday|last_7_days|last_30_days|this_month|all_time)$",
    ),
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    return offers_service.get_view(db, client, campaign_id, interval)


@router.post("/{campaign_id}/streams/{stream_id}/offers")
def add_offer(
    campaign_id: int,
    stream_id: int,
    body: OfferIn,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.add_offer(db, client, campaign_id, stream_id, body.offer_id)
    return {"ok": True}


@router.delete("/{campaign_id}/streams/{stream_id}/offers/{offer_id}")
def remove_offer(
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.remove_offer(db, client, campaign_id, stream_id, offer_id)
    return {"ok": True}


@router.put("/{campaign_id}/streams/{stream_id}/offers/{offer_id}/share")
def set_share(
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    body: ShareIn,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.set_share(db, client, campaign_id, stream_id, offer_id, body.share)
    return {"ok": True}


@router.post("/{campaign_id}/streams/{stream_id}/offers/{offer_id}/unpin")
def unpin_offer(
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.unpin_offer(db, client, campaign_id, stream_id, offer_id)
    return {"ok": True}


@router.post("/{campaign_id}/streams/{stream_id}/push")
def push_draft(
    campaign_id: int,
    stream_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.push_draft(db, client, campaign_id, stream_id)
    return {"ok": True}


@router.delete("/{campaign_id}/streams/{stream_id}/draft")
def cancel_draft(campaign_id: int, stream_id: int, db: Session = Depends(get_db)):
    offers_service.cancel_draft(db, campaign_id, stream_id)
    return {"ok": True}
