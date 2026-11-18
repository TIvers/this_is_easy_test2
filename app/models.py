from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
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


class StreamDraft(Base):
    """Локальный черновик офферов потока. Есть запись -> есть несохранённые изменения."""

    __tablename__ = "stream_drafts"

    stream_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    campaign_id: Mapped[int] = mapped_column(index=True)
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
    pinned: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(default=0)

    draft: Mapped[StreamDraft] = relationship(back_populates="offers")