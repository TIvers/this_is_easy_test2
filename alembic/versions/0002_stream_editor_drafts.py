"""Persist pending stream and offer changes for the campaign editor.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stream_drafts",
        sa.Column("is_new", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "stream_drafts",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "stream_drafts",
        sa.Column("name", sa.String(255), server_default="", nullable=False),
    )
    op.add_column(
        "stream_drafts",
        sa.Column("schema", sa.String(40), server_default="landings", nullable=False),
    )
    op.add_column(
        "stream_drafts",
        sa.Column("action_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "stream_drafts",
        sa.Column("action_payload", sa.String(2000), nullable=True),
    )
    op.add_column(
        "stream_drafts",
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "draft_offers",
        sa.Column("original_share", sa.Integer(), nullable=True),
    )
    op.add_column(
        "draft_offers",
        sa.Column("is_new", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "draft_offers",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute("UPDATE draft_offers SET original_share = share")


def downgrade() -> None:
    op.drop_column("draft_offers", "is_deleted")
    op.drop_column("draft_offers", "is_new")
    op.drop_column("draft_offers", "original_share")
    op.drop_column("stream_drafts", "position")
    op.drop_column("stream_drafts", "action_payload")
    op.drop_column("stream_drafts", "action_type")
    op.drop_column("stream_drafts", "schema")
    op.drop_column("stream_drafts", "name")
    op.drop_column("stream_drafts", "is_deleted")
    op.drop_column("stream_drafts", "is_new")
