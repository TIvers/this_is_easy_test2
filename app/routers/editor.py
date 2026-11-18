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


class StreamIn(BaseModel):
    name: str | None = Field(default=None, max_length=255)


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


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


@router.put("/{campaign_id}/name")
def set_campaign_name(
    campaign_id: int,
    body: NameIn,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.set_campaign_name(db, client, campaign_id, body.name)
    return {"ok": True}


@router.post("/{campaign_id}/streams")
def create_stream(
    campaign_id: int,
    body: StreamIn,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    draft = offers_service.create_stream_draft(db, client, campaign_id, body.name)
    return {"id": draft.stream_id, "name": draft.name, "position": draft.position}


@router.put("/{campaign_id}/streams/{stream_id}/name")
def set_stream_name(
    campaign_id: int,
    stream_id: int,
    body: NameIn,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.set_stream_name(
        db, client, campaign_id, stream_id, body.name
    )
    return {"ok": True}


@router.delete("/{campaign_id}/streams/{stream_id}")
def delete_stream(
    campaign_id: int,
    stream_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    offers_service.delete_stream_draft(db, client, campaign_id, stream_id)
    return {"ok": True}


@router.post("/{campaign_id}/streams/{stream_id}/restore")
def restore_stream(
    campaign_id: int,
    stream_id: int,
    db: Session = Depends(get_db),
):
    offers_service.restore_stream_draft(db, campaign_id, stream_id)
    return {"ok": True}


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


@router.post("/{campaign_id}/push")
def push_all_drafts(
    campaign_id: int,
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_keitaro),
):
    saved_streams = offers_service.push_all_drafts(db, client, campaign_id)
    saved_campaign_name = offers_service.push_campaign_name_draft(
        db, client, campaign_id
    )
    return {
        "saved_streams": saved_streams,
        "saved_campaign_name": saved_campaign_name,
    }


@router.delete("/{campaign_id}/draft")
def cancel_all_drafts(campaign_id: int, db: Session = Depends(get_db)):
    offers_service.cancel_all_drafts(db, campaign_id)
    return {"ok": True}
