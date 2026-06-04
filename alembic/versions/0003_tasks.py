"""Add tasks, task_templates, task_logs, task_photos tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reuse existing type, create new ones manually
_staffrole = sa.Enum(
    "admin", "senior_counselor", "counselor", "educator",
    "coach", "swim_coach", "music", "circle_leader",
    name="staffrole", create_type=False,
)
_taskpriority = sa.Enum("low", "medium", "high", name="taskpriority", create_type=False)
_taskstatus = sa.Enum("new", "accepted", "in_progress", "done", "overdue", name="taskstatus", create_type=False)
_recurrencetype = sa.Enum("daily", "weekly", name="recurrencetype", create_type=False)


def upgrade() -> None:
    # Create new enum types explicitly before tables
    op.execute("CREATE TYPE taskpriority AS ENUM ('low', 'medium', 'high')")
    op.execute("CREATE TYPE taskstatus AS ENUM ('new', 'accepted', 'in_progress', 'done', 'overdue')")
    op.execute("CREATE TYPE recurrencetype AS ENUM ('daily', 'weekly')")

    op.create_table(
        "task_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("group_role", _staffrole, nullable=True),
        sa.Column("priority", _taskpriority, nullable=False, server_default="medium"),
        sa.Column("recurrence_type", _recurrencetype, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("group_role", _staffrole, nullable=True),
        sa.Column("priority", _taskpriority, nullable=False, server_default="medium"),
        sa.Column("status", _taskstatus, nullable=False, server_default="new"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recurrence_type", _recurrencetype, nullable=True),
        sa.Column("paused_until", sa.Date(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["staff.id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["staff.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["task_templates.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "task_photos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("photo_url", sa.String(length=500), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("task_photos")
    op.drop_table("task_logs")
    op.drop_table("tasks")
    op.drop_table("task_templates")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS taskpriority")
    op.execute("DROP TYPE IF EXISTS recurrencetype")
