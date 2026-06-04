"""Add educator_id_2 to squads

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("squads", sa.Column("educator_id_2", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_squad_educator_2", "squads", "staff", ["educator_id_2"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_squad_educator_2", "squads", type_="foreignkey")
    op.drop_column("squads", "educator_id_2")
