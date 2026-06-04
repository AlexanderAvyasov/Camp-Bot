"""Initial schema: staff, squads, action_logs

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "squads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("counselor_id", sa.Integer(), nullable=True),
        sa.Column("educator_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "staff",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "admin",
                "senior_counselor",
                "counselor",
                "educator",
                "coach",
                "swim_coach",
                "music",
                "circle_leader",
                name="staffrole",
            ),
            nullable=False,
        ),
        sa.Column("squad_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["squad_id"], ["squads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index(op.f("ix_staff_telegram_id"), "staff", ["telegram_id"], unique=True)

    op.create_foreign_key(
        "fk_squad_counselor", "squads", "staff", ["counselor_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_squad_educator", "squads", "staff", ["educator_id"], ["id"]
    )

    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("action_logs")
    op.drop_constraint("fk_squad_counselor", "squads", type_="foreignkey")
    op.drop_constraint("fk_squad_educator", "squads", type_="foreignkey")
    op.drop_index(op.f("ix_staff_telegram_id"), table_name="staff")
    op.drop_table("staff")
    op.drop_table("squads")
    op.execute("DROP TYPE IF EXISTS staffrole")
