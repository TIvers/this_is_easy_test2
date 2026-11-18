"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keitaro_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("geo", sa.String(2), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_campaigns_keitaro_id", "campaigns", ["keitaro_id"], unique=True)

    op.create_table(
        "stream_drafts",
        sa.Column("stream_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stream_drafts_campaign_id", "stream_drafts", ["campaign_id"])

    op.create_table(
        "draft_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stream_id", sa.Integer(), sa.ForeignKey("stream_drafts.stream_id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("stream_id", "offer_id"),
    )


def downgrade() -> None:
    op.drop_table("draft_offers")
    op.drop_index("ix_stream_drafts_campaign_id", table_name="stream_drafts")
    op.drop_table("stream_drafts")
    op.drop_index("ix_campaigns_keitaro_id", table_name="campaigns")
    op.drop_table("campaigns")