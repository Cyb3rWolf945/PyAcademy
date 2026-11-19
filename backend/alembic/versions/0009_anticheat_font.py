"""Anti-cheat dos torneios (incidentes à espera do professor) e tipo de letra preferido do utilizador."""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_font", sa.String(length=16), nullable=True))
    op.create_table(
        "tournament_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("round_idx", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("tournament_id", "user_id", "client_id", name="uq_incident_client"),
    )
    op.create_index("ix_tournament_incidents_tournament_id", "tournament_incidents", ["tournament_id"])
    # No máximo um incidente em aberto por aluno e por torneio
    op.create_index("uq_incident_open", "tournament_incidents", ["tournament_id", "user_id"], unique=True, postgresql_where=sa.text("released_at IS NULL"))


def downgrade() -> None:
    op.drop_table("tournament_incidents")
    op.drop_column("users", "preferred_font")
