"""Persist pending campaign and stream name changes.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stream_drafts",
        sa.Column("original_name", sa.String(255), nullable=True),
    )
    op.execute(
        "UPDATE stream_drafts SET original_name = name "
        "WHERE is_new = 0 AND name != ''"
    )
    op.create_table(
        "campaign_name_drafts",
        sa.Column("campaign_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("campaign_name_drafts")
    op.drop_column("stream_drafts", "original_name")
