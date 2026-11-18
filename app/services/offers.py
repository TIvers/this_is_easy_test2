"""Local campaign-editor drafts and explicit synchronization with Keitaro."""
from __future__ import annotations

from sqlalchemy import select
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


def _remote_streams(client: KeitaroClient, campaign_id: int) -> list[dict]:
    return sorted(
        client.list_streams(campaign_id),
        key=lambda stream: (stream.get("position") or 0, int(stream["id"])),
    )


def _find_remote_stream(
    client: KeitaroClient, campaign_id: int, stream_id: int
) -> dict:
    stream = next(
        (item for item in _remote_streams(client, campaign_id) if int(item["id"]) == stream_id),
        None,
    )
    if stream is None:
        raise ValueError(f"Поток {stream_id} не найден в кампании {campaign_id}")
    return client.get_stream(stream_id)


def _active_offers(draft: StreamDraft) -> list[DraftOffer]:
    return [offer for offer in draft.offers if not offer.is_deleted]


def _renumber(draft: StreamDraft) -> None:
    for position, offer in enumerate(_active_offers(draft)):
        offer.position = position


def _load_stream_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> StreamDraft:
    draft = db.get(StreamDraft, stream_id)
    if draft is not None:
        if draft.campaign_id != campaign_id:
            raise ValueError(f"Поток {stream_id} не принадлежит кампании {campaign_id}")
        return draft
    if stream_id < 0:
        raise ValueError(f"Черновик потока {stream_id} не найден")

    stream = _find_remote_stream(client, campaign_id, stream_id)
    draft = StreamDraft(
        stream_id=stream_id,
        campaign_id=campaign_id,
        name=stream.get("name", f"Stream {stream_id}"),
        schema=stream.get("schema", "landings"),
        action_type=stream.get("action_type"),
        action_payload=stream.get("action_payload"),
        position=stream.get("position") or 0,
    )
    offer_names = _offers_map(client)
    remote_offers = stream.get("offers") or []
    pins = shares.initial_pins([int(offer.get("share") or 0) for offer in remote_offers])
    for position, (offer, pinned) in enumerate(zip(remote_offers, pins)):
        offer_id = int(offer["offer_id"])
        share = int(offer.get("share") or 0)
        draft.offers.append(
            DraftOffer(
                offer_id=offer_id,
                name=offer_names.get(offer_id, f"Offer {offer_id}"),
                share=share,
                original_share=share,
                pinned=pinned,
                position=position,
            )
        )
    db.add(draft)
    db.flush()
    return draft


def _ensure_offer_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> StreamDraft:
    draft = _load_stream_draft(db, client, campaign_id, stream_id)
    if draft.is_deleted:
        raise ValueError("Сначала восстановите поток, чтобы редактировать его офферы")
    if draft.schema != "landings":
        raise ValueError("Редактировать офферы можно только в потоке со схемой landings")
    return draft


def _offer_data(
    offer: DraftOffer,
    stream_id: int,
    stats: dict[tuple[int, int], dict],
) -> dict:
    return {
        "offer_id": offer.offer_id,
        "name": offer.name,
        "share": offer.share,
        "original_share": offer.original_share,
        "pinned": offer.pinned,
        "is_new": offer.is_new,
        "is_deleted": offer.is_deleted,
        "changed": (
            offer.is_new
            or offer.is_deleted
            or offer.original_share != offer.share
        ),
        "stats": stats.get(
            (stream_id, offer.offer_id),
            {"clicks": 0, "conversions": 0, "revenue": 0, "cr": 0},
        ),
    }


def _draft_changed(draft: StreamDraft) -> bool:
    return draft.is_new or draft.is_deleted or any(
        offer.is_new or offer.is_deleted or offer.original_share != offer.share
        for offer in draft.offers
    )


def _stream_data(
    stream_id: int,
    name: str,
    position: int,
    schema: str,
    action_payload: str | None,
    draft: StreamDraft | None,
    base_stream_id: int | None,
    stats: dict[tuple[int, int], dict],
    remote_offers: list[dict] | None = None,
    offer_names: dict[int, str] | None = None,
) -> dict:
    editable = schema == "landings"
    if draft is not None:
        offers = [
            _offer_data(offer, stream_id, stats)
            for offer in sorted(draft.offers, key=lambda item: item.position)
        ] if editable else []
        is_new = draft.is_new
        is_deleted = draft.is_deleted
        changed = _draft_changed(draft)
        name = draft.name or name
        position = draft.position or position
        action_payload = draft.action_payload or action_payload
    elif editable:
        remote_offers = remote_offers or []
        offer_names = offer_names or {}
        pinned = shares.initial_pins(
            [int(offer.get("share") or 0) for offer in remote_offers]
        )
        offers = []
        for offer, is_pinned in zip(remote_offers, pinned):
            offer_id = int(offer["offer_id"])
            share = int(offer.get("share") or 0)
            offers.append(
                {
                    "offer_id": offer_id,
                    "name": offer_names.get(offer_id, f"Offer {offer_id}"),
                    "share": share,
                    "original_share": share,
                    "pinned": is_pinned,
                    "is_new": False,
                    "is_deleted": False,
                    "changed": False,
                    "stats": stats.get(
                        (stream_id, offer_id),
                        {"clicks": 0, "conversions": 0, "revenue": 0, "cr": 0},
                    ),
                }
            )
        is_new = False
        is_deleted = False
        changed = False
    else:
        offers = []
        is_new = False
        is_deleted = False
        changed = False

    return {
        "id": stream_id,
        "name": name,
        "position": position,
        "schema": schema,
        "editable": editable,
        "action_payload": action_payload,
        "offers": offers,
        "total": sum(offer["share"] for offer in offers if not offer["is_deleted"]),
        "drafted": draft is not None,
        "changed": changed,
        "is_new": is_new,
        "is_deleted": is_deleted,
        "is_base": stream_id == base_stream_id,
    }


def get_view(db: Session, client: KeitaroClient, campaign_id: int, interval: str = "today") -> dict:
    campaign = client.get_campaign(campaign_id)
    remote_streams = _remote_streams(client, campaign_id)
    offer_names = _offers_map(client)
    stats = _stats_map(client, campaign_id, interval)
    drafts = db.scalars(
        select(StreamDraft).where(StreamDraft.campaign_id == campaign_id)
    ).all()
    drafts_by_id = {draft.stream_id: draft for draft in drafts}
    base_stream_id = int(remote_streams[0]["id"]) if remote_streams else None
    output = []

    for stream in remote_streams:
        stream_id = int(stream["id"])
        draft = drafts_by_id.get(stream_id)
        output.append(
            _stream_data(
                stream_id=stream_id,
                name=stream.get("name", f"Stream {stream_id}"),
                position=stream.get("position") or 0,
                schema=stream.get("schema", ""),
                action_payload=stream.get("action_payload"),
                draft=draft,
                base_stream_id=base_stream_id,
                stats=stats,
                remote_offers=stream.get("offers") or [],
                offer_names=offer_names,
            )
        )

    for draft in sorted(
        (item for item in drafts if item.is_new),
        key=lambda item: (item.position, item.stream_id),
    ):
        output.append(
            _stream_data(
                stream_id=draft.stream_id,
                name=draft.name or f"Stream {draft.position}",
                position=draft.position,
                schema=draft.schema,
                action_payload=draft.action_payload,
                draft=draft,
                base_stream_id=base_stream_id,
                stats=stats,
            )
        )
    output.sort(key=lambda item: (item["position"], item["id"]))

    return {
        "campaign": campaign,
        "interval": interval,
        "streams": output,
        "has_drafts": bool(drafts),
        "has_changes": any(stream["changed"] for stream in output),
        "all_offers": [
            {"id": offer_id, "name": name}
            for offer_id, name in sorted(offer_names.items())
        ],
    }


def create_stream_draft(
    db: Session, client: KeitaroClient, campaign_id: int, name: str | None = None
) -> StreamDraft:
    client.get_campaign(campaign_id)
    remote_streams = _remote_streams(client, campaign_id)
    existing_drafts = db.scalars(select(StreamDraft.stream_id)).all()
    stream_id = min([0, *(item for item in existing_drafts if item < 0)]) - 1
    draft_positions = db.scalars(
        select(StreamDraft.position).where(StreamDraft.campaign_id == campaign_id)
    ).all()
    position = max(
        [int(stream.get("position") or 0) for stream in remote_streams]
        + [int(value or 0) for value in draft_positions]
        + [0]
    ) + 1
    name = (name or f"Stream {position}").strip()
    if not name:
        raise ValueError("Название потока не может быть пустым")
    draft = StreamDraft(
        stream_id=stream_id,
        campaign_id=campaign_id,
        is_new=True,
        name=name[:255],
        schema="landings",
        action_type="http",
        position=position,
    )
    db.add(draft)
    db.commit()
    return draft


def _base_stream_id(client: KeitaroClient, campaign_id: int) -> int | None:
    streams = _remote_streams(client, campaign_id)
    return int(streams[0]["id"]) if streams else None


def delete_stream_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> None:
    try:
        draft = db.get(StreamDraft, stream_id)
        if draft is not None and draft.campaign_id != campaign_id:
            raise ValueError(f"Поток {stream_id} не принадлежит кампании {campaign_id}")
        if draft is not None and draft.is_new:
            db.delete(draft)
            db.commit()
            return
        if stream_id == _base_stream_id(client, campaign_id):
            raise ValueError("Базовый первый поток нельзя удалить")
        draft = _load_stream_draft(db, client, campaign_id, stream_id)
        draft.is_deleted = True
        db.commit()
    except Exception:
        db.rollback()
        raise


def restore_stream_draft(db: Session, campaign_id: int, stream_id: int) -> None:
    draft = db.get(StreamDraft, stream_id)
    if draft is None or draft.campaign_id != campaign_id:
        raise ValueError(f"Черновик потока {stream_id} не найден")
    draft.is_deleted = False
    db.commit()


def add_offer(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int
) -> None:
    offer_names = _offers_map(client)
    if offer_id not in offer_names:
        raise ValueError(f"Оффер {offer_id} не найден в Keitaro")
    try:
        draft = _ensure_offer_draft(db, client, campaign_id, stream_id)
        existing = next((offer for offer in draft.offers if offer.offer_id == offer_id), None)
        active = _active_offers(draft)
        if existing is not None and not existing.is_deleted:
            raise shares.ShareError("Этот оффер уже есть в потоке")
        if existing is not None:
            existing.is_deleted = False
            existing.is_new = existing.original_share is None
            existing.name = offer_names[offer_id]
            existing.share = 0
            existing.pinned = False
            item = existing
        else:
            item = DraftOffer(
                offer_id=offer_id,
                name=offer_names[offer_id],
                share=0,
                original_share=None,
                is_new=True,
                position=len(active),
            )
            draft.offers.append(item)
        active = [offer for offer in _active_offers(draft) if offer is not item]
        shares.add_item(active, item)
        _renumber(draft)
        db.commit()
    except Exception:
        db.rollback()
        raise


def remove_offer(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int
) -> None:
    try:
        draft = _ensure_offer_draft(db, client, campaign_id, stream_id)
        offer = next(
            (
                item for item in draft.offers
                if item.offer_id == offer_id and not item.is_deleted
            ),
            None,
        )
        if offer is None:
            raise shares.ShareError("Оффера нет в потоке")
        if offer.is_new:
            draft.offers.remove(offer)
        else:
            offer.is_deleted = True
        shares.rebalance(_active_offers(draft))
        _renumber(draft)
        db.commit()
    except Exception:
        db.rollback()
        raise


def set_share(
    db: Session,
    client: KeitaroClient,
    campaign_id: int,
    stream_id: int,
    offer_id: int,
    share: int,
) -> None:
    try:
        draft = _ensure_offer_draft(db, client, campaign_id, stream_id)
        shares.set_share(_active_offers(draft), offer_id, share)
        db.commit()
    except Exception:
        db.rollback()
        raise


def unpin_offer(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int, offer_id: int
) -> None:
    try:
        draft = _ensure_offer_draft(db, client, campaign_id, stream_id)
        shares.unpin(_active_offers(draft), offer_id)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _stream_payload(draft: StreamDraft) -> dict:
    active = sorted(_active_offers(draft), key=lambda offer: offer.position)
    shares.validate_for_push(active)
    return {
        "campaign_id": draft.campaign_id,
        "name": draft.name,
        "type": "regular",
        "position": draft.position,
        "weight": 100,
        "schema": draft.schema,
        "action_type": draft.action_type or "http",
        "collect_clicks": True,
        "filter_or": False,
        "filters": [],
        "offers": [
            {"offer_id": offer.offer_id, "share": offer.share, "state": "active"}
            for offer in active
        ],
        "state": "active",
    }


def _push_stream_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> None:
    draft = db.get(StreamDraft, stream_id)
    if draft is None or draft.campaign_id != campaign_id:
        raise ValueError(f"Черновик потока {stream_id} не найден")
    try:
        if draft.is_deleted:
            client.delete_stream(stream_id)
        elif draft.is_new:
            client.create_stream(_stream_payload(draft))
        elif _draft_changed(draft):
            _find_remote_stream(client, campaign_id, stream_id)
            shares.validate_for_push(_active_offers(draft))
            client.update_stream(
                stream_id,
                {
                    "offers": [
                        {"offer_id": offer.offer_id, "share": offer.share, "state": "active"}
                        for offer in sorted(_active_offers(draft), key=lambda item: item.position)
                    ]
                },
            )
        else:
            db.delete(draft)
            db.commit()
            return
        db.delete(draft)
        db.commit()
    except Exception:
        db.rollback()
        raise


def push_draft(
    db: Session, client: KeitaroClient, campaign_id: int, stream_id: int
) -> None:
    _push_stream_draft(db, client, campaign_id, stream_id)


def push_all_drafts(db: Session, client: KeitaroClient, campaign_id: int) -> int:
    drafts = db.scalars(
        select(StreamDraft)
        .where(StreamDraft.campaign_id == campaign_id)
        .order_by(StreamDraft.position, StreamDraft.stream_id)
    ).all()
    for draft in drafts:
        _push_stream_draft(db, client, campaign_id, draft.stream_id)
    return len(drafts)


def cancel_draft(db: Session, campaign_id: int, stream_id: int) -> None:
    draft = db.get(StreamDraft, stream_id)
    if draft is None:
        return
    if draft.campaign_id != campaign_id:
        raise ValueError(f"Поток {stream_id} не принадлежит кампании {campaign_id}")
    db.delete(draft)
    db.commit()


def cancel_all_drafts(db: Session, campaign_id: int) -> None:
    drafts = db.scalars(
        select(StreamDraft).where(StreamDraft.campaign_id == campaign_id)
    ).all()
    for draft in drafts:
        db.delete(draft)
    db.commit()
