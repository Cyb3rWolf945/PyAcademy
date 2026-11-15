"""Identidades temporárias limitadas a um torneio."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_guest", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("users", sa.Column("guest_tournament_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "guest_tournament_id")
    op.drop_column("users", "is_guest")
