"""adicionar_recebido_por

Revision ID: a1b2c3d4e5f6
Revises: 5e111f28c934
Create Date: 2026-11-27 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "5e111f28c934"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "encomendas",
        sa.Column("recebido_por", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("encomendas", "recebido_por")
