"""children and parents tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "children",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(300), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("squad_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("dormitory", sa.String(100), nullable=True),
        sa.Column("food_type", sa.String(100), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("medications", sa.Text(), nullable=True),
        sa.Column("raw_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["squad_id"], ["squads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_children_full_name", "children", ["full_name"])

    op.create_table(
        "parents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(300), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("relation", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("parents")
    op.drop_table("children")
