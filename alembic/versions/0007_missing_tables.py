"""Add announcements, incidents, duties, circles, checklists, event_ratings, reminders

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_staffrole = sa.Enum(
    "admin", "senior_counselor", "counselor", "educator",
    "coach", "swim_coach", "music", "circle_leader",
    name="staffrole", create_type=False,
)


def upgrade() -> None:
    # ── Enums ──────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE dutystatus AS ENUM ('scheduled', 'active', 'completed')")
    op.execute("CREATE TYPE dutytype AS ENUM ('dining', 'territory', 'dormitory', 'night')")
    op.execute("CREATE TYPE checklisttype AS ENUM ('pre_event', 'lights_out')")

    # ── Announcements ──────────────────────────────────────────────────────────
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["staff.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "announcement_reads",
        sa.Column("announcement_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("announcement_id", "staff_id"),
    )

    # ── Incidents ──────────────────────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reported_by", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reported_by"], ["staff.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Duties ────────────────────────────────────────────────────────────────
    op.create_table(
        "duties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.Enum("dining", "territory", "dormitory", "night", name="dutytype", create_type=False), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("scheduled", "active", "completed", name="dutystatus", create_type=False), nullable=False, server_default="scheduled"),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "duty_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("duty_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["duty_id"], ["duties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Reminders ─────────────────────────────────────────────────────────────
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Event Ratings ─────────────────────────────────────────────────────────
    op.create_table(
        "event_ratings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Circles ───────────────────────────────────────────────────────────────
    op.create_table(
        "circles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("leader_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["leader_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "circle_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("circle_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(["circle_id"], ["circles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "circle_members",
        sa.Column("circle_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["circle_id"], ["circles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("circle_id", "child_id"),
    )
    op.create_table(
        "circle_attendance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("circle_id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["circle_id"], ["circles.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("circle_id", "child_id", "date", name="uq_circle_attendance"),
    )

    # ── Checklists ────────────────────────────────────────────────────────────
    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.Enum("pre_event", "lights_out", name="checklisttype", create_type=False), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checklist_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checklist_item_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["checklist_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["checklist_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("checklist_item_results")
    op.drop_table("checklist_runs")
    op.drop_table("checklist_items")
    op.drop_table("checklist_templates")
    op.drop_table("circle_attendance")
    op.drop_table("circle_members")
    op.drop_table("circle_schedules")
    op.drop_table("circles")
    op.drop_table("event_ratings")
    op.drop_table("reminders")
    op.drop_table("duty_checkpoints")
    op.drop_table("duties")
    op.drop_table("incidents")
    op.drop_table("announcement_reads")
    op.drop_table("announcements")
    op.execute("DROP TYPE IF EXISTS checklisttype")
    op.execute("DROP TYPE IF EXISTS dutytype")
    op.execute("DROP TYPE IF EXISTS dutystatus")
