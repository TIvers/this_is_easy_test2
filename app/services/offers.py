"""Campaign stream offer editing with locally persisted drafts."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.keitaro.client import KeitaroClient
from app.models import DraftOffer, StreamDraft
from app.services import shares


def _offers_map(client: KeitaroClient) -> dict[int, str]:
    return {
        int(offer["id"]): offer.get("name", f"Offer {offer['id']}")
        for offer in client.list_offers()
    }


def _stats_map(client: KeitaroClient, campaign_id: int, interval: str) -> dict[tuple[int, int], dict]:
    result = {}
    for row in client.report_by_stream_offer(campaign_id, interval):
        try:
            key = (int(row["stream_id"]), int(row["offer_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        result[key] = {
            "clicks": row.get("clicks") or 0,
            "conversions": row.get("conversions") or 0,
            "revenue": row.get("revenue") or 0,
            "cr": row.get("cr") or 0,
        }
    return result


def _stream_for_campaign(client: KeitaroClient, campaign_id: int, stream_id: int) -> dict:
    if not any(int(stream["id"]) == stream_id for stream in client.list_streams(campaign_id)):
        raise ValueError(f"Поток {stream_id} не найден в кампании {campaign_id}")
    stream = client.get_stream(stream_id)
    if stream.get("schema") != "landings":
        raise ValueError("Редактировать офферы можно только в потоке со схемой landings")
    return stream


def _ensure_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> StreamDraft:
    draft = db.get(StreamDraft, stream_id)
    if draft:
        if draft.campaign_id != campaign_id:
            raise ValueError(f"Поток {stream_id} не принадлежит кампании {campaign_id}")
        return draft

    stream = _stream_for_campaign(client, campaign_id, stream_id)
    names = _offers_map(client)
    kt_offers = stream.get("offers") or []
    pins = shares.initial_pins([int(offer.get("share") or 0) for offer in kt_offers])
    draft = StreamDraft(stream_id=stream_id, campaign_id=campaign_id)
    for position, (offer, pinned) in enumerate(zip(kt_offers, pins)):
        offer_id = int(offer["offer_id"])
        draft.offers.append(
            DraftOffer(
                offer_id=offer_id,
                name=names.get(offer_id, f"Offer {offer_id}"),
                share=int(offer.get("share") or 0),
                pinned=pinned,
                position=position,
            )
        )
    db.add(draft)
    db.flush()
    return draft


def _renumber(draft: StreamDraft) -> None:
    for position, offer in enumerate(draft.offers):
        offer.position = position


def get_view(db: Session, client: KeitaroClient, campaign_id: int, interval: str = "today") -> dict:
    campaign = client.get_campaign(campaign_id)
    streams = client.list_streams(campaign_id)
    names = _offers_map(client)
    stats = _stats_map(client, campaign_id, interval)
    output = []

    for stream in sorted(streams, key=lambda item: item.get("position") or 0):
        stream_id = int(stream["id"])
        editable = stream.get("schema") == "landings"
        draft = db.get(StreamDraft, stream_id)
        if draft and draft.campaign_id != campaign_id:
            raise ValueError(f"Поток {stream_id} не принадлежит кампании {campaign_id}")

        if draft:
            source_offers = [
                {
                    "offer_id": offer.offer_id,
                    "name": offer.name,
                    "share": offer.share,
                    "pinned": offer.pinned,
                }
                for offer in draft.offers
            ]
        else:
            keitaro_offers = stream.get("offers") or []
            pins = shares.initial_pins(
                [int(offer.get("share") or 0) for offer in keitaro_offers]
            )
            source_offers = [
                {
                    "offer_id": int(offer["offer_id"]),
                    "name": names.get(int(offer["offer_id"]), f"Offer {offer['offer_id']}"),
                    "share": int(offer.get("share") or 0),
                    "pinned": pinned,
                }
                for offer, pinned in zip(keitaro_offers, pins)
            ]

        for offer in source_offers:
            offer["stats"] = stats.get(
                (stream_id, offer["offer_id"]),
                {"clicks": 0, "conversions": 0, "revenue": 0, "cr": 0},
            )
        output.append(
            {
                "id": stream_id,
                "name": stream.get("name", f"Stream {stream_id}"),
                "position": stream.get("position") or 0,
                "schema": stream.get("schema"),
                "editable": editable,
                "action_payload": stream.get("action_payload"),
                "offers": source_offers if editable else [],
                "total": sum(offer["share"] for offer in source_offers) if editable else 0,
                "drafted": draft is not None,
            }
        )

    return {
        "campaign": campaign,
        "interval": interval,
        "streams": output,
        "all_offers": [
            {"id": offer_id, "name": name} for offer_id, name in names.items()
        ],
    }


def add_offer(db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int) -> None:
    names = _offers_map(client)
    if offer_id not in names:
        raise ValueError(f"Оффер {offer_id} не найден в Keitaro")
    try:
        draft = _ensure_draft(db, client, campaign_id, stream_id)
        shares.add_item(
            draft.offers,
            DraftOffer(offer_id=offer_id, name=names[offer_id], share=0, position=len(draft.offers)),
        )
        _renumber(draft)
        db.commit()
    except Exception:
        db.rollback()
        raise


def remove_offer(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int
) -> None:
    try:
        draft = _ensure_draft(db, client, campaign_id, stream_id)
        shares.remove_item(draft.offers, offer_id)
        _renumber(draft)
        db.commit()
    except Exception:
        db.rollback()
        raise


def set_share(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int, share: int
) -> None:
    try:
        draft = _ensure_draft(db, client, campaign_id, stream_id)
        shares.set_share(draft.offers, offer_id, share)
        db.commit()
    except Exception:
        db.rollback()
        raise


def unpin_offer(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int
) -> None:
    try:
        draft = _ensure_draft(db, client, campaign_id, stream_id)
        shares.unpin(draft.offers, offer_id)
        db.commit()
    except Exception:
        db.rollback()
        raise


def push_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> None:
    try:
        draft = _ensure_draft(db, client, campaign_id, stream_id)
        shares.validate_for_push(draft.offers)
        _stream_for_campaign(client, campaign_id, stream_id)
        client.update_stream(
            stream_id,
            {
                "offers": [
                    {"offer_id": offer.offer_id, "share": offer.share, "state": "active"}
                    for offer in sorted(draft.offers, key=lambda item: item.position)
                ]
            },
        )
        db.delete(draft)
        db.commit()
    except Exception:
        db.rollback()
        raise


def cancel_draft(db: Session, campaign_id: int, stream_id: int) -> None:
    draft = db.get(StreamDraft, stream_id)
    if draft is None:
        return
    if draft.campaign_id != campaign_id:
        raise ValueError(f"Поток {stream_id} не принадлежит кампании {campaign_id}")
    db.delete(draft)
    db.commit()
