# Modelos do torneio "Formato Aula": torneio, agências, jogadores, rondas, pontuações, pistas, bónus,
# registo de eventos (replay do WebSocket) e presença (tabela UNLOGGED, mais rápida e que se perde num crash).
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, String, Float, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow

TOURNAMENT_STATES = ("lobby", "round_active", "round_paused", "between_rounds", "finished")
ROUND_STATES = ("pending", "active", "paused", "closed")

DEFAULT_CONFIG = {
    "hint_factor": 0.5,
    "first_bonus": 5,
    "grace_s": 30,
    "diploma_title": {"pt": "Mestre da Decomposição", "en": "Decomposition Master"},
}


def _fk(target: str, **kw) -> Column:
    return Column(Integer, ForeignKey(target, ondelete="CASCADE"), nullable=False, **kw)


class Tournament(SQLModel, table=True):
    __tablename__ = "tournaments"

    id: int | None = Field(default=None, primary_key=True)
    class_id: int = Field(sa_column=_fk("school_classes.id", index=True))
    teacher_id: int = Field(sa_column=_fk("users.id", index=True))
    name: str = Field(max_length=80)
    mode: str = Field(max_length=12)  # individual | agencias
    format: str = Field(default="aula", max_length=14)  # aula | eliminatoria
    join_code: str = Field(unique=True, index=True, min_length=6, max_length=6)
    state: str = Field(default="lobby", max_length=16)
    current_round: int | None = None
    config: dict = Field(default_factory=lambda: dict(DEFAULT_CONFIG), sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    # Quando foi emitido o último evento "leaderboard": serve de porta para o agrupar a 1 por segundo.
    lb_emitted_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))
    gp_emitted_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))  # idem, para group_progress


class TournamentTeam(SQLModel, table=True):
    __tablename__ = "tournament_teams"
    __table_args__ = (Index("uq_tournament_team_name", "tournament_id", text("lower(name)"), unique=True),)

    id: int | None = Field(default=None, primary_key=True)
    tournament_id: int = Field(sa_column=_fk("tournaments.id", index=True))
    name: str = Field(max_length=24)
    color_idx: int = Field(default=0)


class TournamentPlayer(SQLModel, table=True):
    __tablename__ = "tournament_players"

    tournament_id: int = Field(sa_column=Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True))
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True))
    team_id: int | None = Field(default=None, sa_column=Column(Integer, ForeignKey("tournament_teams.id", ondelete="SET NULL"), nullable=True))
    joined_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    # Eliminatória: alive | eliminated | champion
    status: str = Field(default="alive", sa_column=Column(String(12), nullable=False, server_default="alive"))
    eliminated_in_round: int | None = None


class TournamentRound(SQLModel, table=True):
    __tablename__ = "tournament_rounds"
    __table_args__ = (UniqueConstraint("tournament_id", "idx", name="uq_round_idx"),)

    id: int | None = Field(default=None, primary_key=True)
    tournament_id: int = Field(sa_column=_fk("tournaments.id", index=True))
    idx: int  # 1..5 = R1..R5, 6 = boss
    title: dict = Field(sa_column=Column(JSONB, nullable=False))
    points: int
    multiplier: float = Field(default=1.0, sa_column=Column(Float, nullable=False, server_default="1"))
    duration_s: int
    is_boss: bool = False
    problem_slugs: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    state: str = Field(default="pending", max_length=10)
    started_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))
    ends_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))
    remaining_s: int | None = None  # só enquanto pausada
    is_final: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    difficulty: str | None = Field(default=None, max_length=8)  # easy | medium | hard (Eliminatória)
    edited: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))  # o professor trocou o exercício


class TournamentSolve(SQLModel, table=True):
    __tablename__ = "tournament_solves"
    __table_args__ = (
        UniqueConstraint("tournament_id", "round_id", "problem_slug", "participant_key", name="uq_solve_once"),
    )

    id: int | None = Field(default=None, primary_key=True)
    tournament_id: int = Field(sa_column=_fk("tournaments.id", index=True))
    round_id: int = Field(sa_column=_fk("tournament_rounds.id"))
    problem_slug: str = Field(max_length=80)
    participant_key: str = Field(max_length=24)  # u:<id> | t:<id>
    points: float = Field(sa_column=Column(Float, nullable=False))
    hint_used: bool = False
    submission_id: int | None = Field(default=None, sa_column=Column(Integer, ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True))
    solved_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class TournamentHintUse(SQLModel, table=True):
    __tablename__ = "tournament_hint_uses"

    round_id: int = Field(sa_column=Column(Integer, ForeignKey("tournament_rounds.id", ondelete="CASCADE"), primary_key=True))
    problem_slug: str = Field(primary_key=True, max_length=80)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    n: int = Field(primary_key=True)


class TournamentBonus(SQLModel, table=True):
    __tablename__ = "tournament_bonus"
    # só existe um bónus "first" por ronda: a constraint decide quem foi o primeiro, mesmo em concorrência
    __table_args__ = (UniqueConstraint("round_id", "kind", name="uq_bonus_round_kind"),)

    id: int | None = Field(default=None, primary_key=True)
    round_id: int = Field(sa_column=_fk("tournament_rounds.id"))
    participant_key: str = Field(max_length=24)
    points: float = Field(sa_column=Column(Float, nullable=False))
    kind: str = Field(default="first", max_length=12)


class TournamentEvent(SQLModel, table=True):
    __tablename__ = "tournament_events"
    __table_args__ = (Index("ix_tournament_events_tid_seq", "tournament_id", "seq"),)

    seq: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    tournament_id: int = Field(sa_column=_fk("tournaments.id"))
    type: str = Field(max_length=24)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class Presence(SQLModel, table=True):
    """Quem está ligado (ping de 15 s). UNLOGGED: sem WAL, perde-se num crash, o que não importa."""
    __tablename__ = "presence"
    __table_args__ = {"prefixes": ["UNLOGGED"]}

    tournament_id: int = Field(sa_column=Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True))
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    last_seen: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    last_seq: int = Field(default=0, sa_column=Column(BigInteger, nullable=False, server_default="0"))


class TournamentSubmission(SQLModel, table=True):
    """Liga uma submissão ao torneio/ronda onde foi feita e à hora (do servidor) a que foi recebida."""
    __tablename__ = "tournament_submissions"

    submission_id: int = Field(sa_column=Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True))
    tournament_id: int = Field(sa_column=_fk("tournaments.id", index=True))
    round_id: int = Field(sa_column=_fk("tournament_rounds.id"))
    received_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())



class TournamentGroup(SQLModel, table=True):
    """Grupo de uma ronda da Eliminatória. members/winners/ranking são listas de user_id."""
    __tablename__ = "tournament_groups"
    __table_args__ = (UniqueConstraint("round_id", "idx", name="uq_group_idx"),)

    id: int | None = Field(default=None, primary_key=True)
    tournament_id: int = Field(sa_column=_fk("tournaments.id", index=True))
    round_id: int = Field(sa_column=_fk("tournament_rounds.id", index=True))
    idx: int
    members: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    winners: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    decided: bool = False
    decided_by: str | None = Field(default=None, max_length=8)  # solve | tests | draw | teacher
    ranking: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))  # ordem final (preenchida ao fechar)
    draw_seed: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))  # semente do sorteio, se houve
