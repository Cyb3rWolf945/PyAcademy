# Livro de pontos pessoais (persistentes): uma linha por pontuação ganha. O total de um aluno é a soma das suas
# linhas; o semanal é a soma desde segunda-feira às 00:00 (Lisboa). Um índice único impede pontos duplicados.
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, Integer, text
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class UserPoints(SQLModel, table=True):
    __tablename__ = "user_points"
    __table_args__ = (
        Index(
            "uq_user_points_key", "user_id", text("COALESCE(tournament_id, 0)"), "reason", text("COALESCE(round_idx, 0)"),
            text("COALESCE(problem_slug, '')"), unique=True,
        ),
        Index("ix_user_points_created", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True))
    points: int
    reason: str = Field(max_length=16)  # exercise | group_win | champion | second | third | participation
    tournament_id: int | None = Field(default=None, sa_column=Column(Integer, ForeignKey("tournaments.id", ondelete="SET NULL"), nullable=True))
    round_idx: int | None = None
    problem_slug: str | None = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
