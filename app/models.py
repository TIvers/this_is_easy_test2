from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Campaign(Base):
    """Кампания, созданная через наш создаватор (для списка на главной)."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    geo: Mapped[str] = mapped_column(String(2))
    offer_id: Mapped[int]
    domain_id: Mapped[int | None]
    group_id: Mapped[int | None]
    source_id: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CampaignNameDraft(Base):
    """Pending name change for any campaign managed by Keitaro."""

    __tablename__ = "campaign_name_drafts"

    campaign_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    original_name: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))


class StreamDraft(Base):
    """Local changes to a Keitaro stream, including streams not yet created remotely."""

    __tablename__ = "stream_drafts"

    stream_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    campaign_id: Mapped[int] = mapped_column(index=True)
    is_new: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())
    name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema: Mapped[str] = mapped_column(String(40), default="landings", server_default="landings")
    action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_payload: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    offers: Mapped[list["DraftOffer"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="DraftOffer.position",
    )


class DraftOffer(Base):
    __tablename__ = "draft_offers"
    __table_args__ = (UniqueConstraint("stream_id", "offer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("stream_drafts.stream_id", ondelete="CASCADE"))
    offer_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(500), default="")
    share: Mapped[int] = mapped_column(default=0)
    original_share: Mapped[int | None] = mapped_column(nullable=True)
    is_new: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())
    pinned: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(default=0)

    draft: Mapped[StreamDraft] = relationship(back_populates="offers")