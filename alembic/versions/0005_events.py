"""events and event_members tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE eventtype AS ENUM ('sport', 'creative', 'camp_wide', 'squad')")

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM("sport", "creative", "camp_wide", "squad", name="eventtype", create_type=False),
            nullable=False,
        ),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("responsible_id", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("copied_from", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["responsible_id"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["copied_from"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_start_time", "events", ["start_time"])

    op.create_table(
        "event_members",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "staff_id"),
    )


def downgrade() -> None:
    op.drop_table("event_members")
    op.drop_table("events")
    op.execute("DROP TYPE eventtype")
