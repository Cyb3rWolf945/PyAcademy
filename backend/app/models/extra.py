# Modelos das atividades extra: definições por turma, consentimento do poker, mesas/lugares/mãos/ações/eventos do poker
# e partidas do Bit a Bit. O estado de cada mão (baralho e cartas fechadas incluídos) só vive aqui, nunca sai tal e qual.
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


def _fk(target: str, **kw) -> Column:
    return Column(Integer, ForeignKey(target, ondelete="CASCADE"), nullable=False, **kw)


def _nullable_ts() -> Column:
    return Column(ts_column().type, nullable=True)


class ExtraSettings(SQLModel, table=True):
    """Definições do professor por turma (sem linha = valores por omissão)."""
    __tablename__ = "extra_settings"

    class_id: int = Field(sa_column=Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), primary_key=True))
    poker_enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    poker_source: str = Field(default="torneios", sa_column=Column(String(12), nullable=False, server_default="torneios"))  # torneios | todos
    students_can_create_tables: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))
    max_tables: int = Field(default=4, sa_column=Column(Integer, nullable=False, server_default="4"))
    buy_in_min: int = Field(default=10, sa_column=Column(Integer, nullable=False, server_default="10"))
    buy_in_max: int = Field(default=200, sa_column=Column(Integer, nullable=False, server_default="200"))
    buy_in_max_pct: int = Field(default=50, sa_column=Column(Integer, nullable=False, server_default="50"))
    daily_loss_limit: int = Field(default=100, sa_column=Column(Integer, nullable=False, server_default="100"))
    bitabit_daily_cap: int = Field(default=50, sa_column=Column(Integer, nullable=False, server_default="50"))


class PokerConsent(SQLModel, table=True):
    __tablename__ = "poker_consent"

    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    accepted_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class PokerTable(SQLModel, table=True):
    __tablename__ = "poker_tables"

    id: int | None = Field(default=None, primary_key=True)
    class_id: int = Field(sa_column=_fk("school_classes.id", index=True))
    name: str = Field(max_length=40)
    max_seats: int = Field(default=6)
    small_blind: int = Field(default=1)
    big_blind: int = Field(default=2)
    state: str = Field(default="open", max_length=8)  # open | closed
    created_by: int | None = Field(default=None, sa_column=Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    dealer_seat: int | None = None
    hand_no: int = Field(default=0)
    next_hand_at: datetime | None = Field(default=None, sa_column=_nullable_ts())  # fim da pausa entre mãos
    turn_deadline: datetime | None = Field(default=None, sa_column=_nullable_ts())  # prazo (servidor) da vez atual
    current_hand_id: int | None = None


class PokerSeat(SQLModel, table=True):
    __tablename__ = "poker_seats"
    __table_args__ = (UniqueConstraint("user_id", name="uq_poker_seat_user"),)  # um lugar de cada vez

    table_id: int = Field(sa_column=Column(Integer, ForeignKey("poker_tables.id", ondelete="CASCADE"), primary_key=True))
    seat: int = Field(primary_key=True)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    stack: int = Field(default=0)
    buy_in: int = Field(default=0)  # capital reservado do saldo (o ganho/perda vai para o livro mão a mão)
    status: str = Field(default="sitting", max_length=12)  # sitting | sitting_out | away
    away_hands: int = Field(default=0)
    joined_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class PokerHand(SQLModel, table=True):
    __tablename__ = "poker_hands"
    __table_args__ = (Index("ix_poker_hands_table", "table_id", "hand_no"),)

    id: int | None = Field(default=None, primary_key=True)
    table_id: int = Field(sa_column=_fk("poker_tables.id"))
    hand_no: int
    started_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    ended_at: datetime | None = Field(default=None, sa_column=_nullable_ts())
    dealer_seat: int
    state: dict = Field(sa_column=Column(JSONB, nullable=False))  # motor (baralho e cartas fechadas: segredo do servidor)
    results: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))


class PokerAction(SQLModel, table=True):
    __tablename__ = "poker_actions"
    __table_args__ = (UniqueConstraint("hand_id", "action_id", name="uq_poker_action_id"),)

    id: int | None = Field(default=None, primary_key=True)
    hand_id: int = Field(sa_column=_fk("poker_hands.id", index=True))
    seq: int
    user_id: int
    seat: int
    type: str = Field(max_length=10)
    amount: int = Field(default=0)
    street: str = Field(max_length=8)
    action_id: str | None = Field(default=None, max_length=64)
    auto: bool = Field(default=False)  # True: decidida pelo temporizador/ausência
    at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class PokerEvent(SQLModel, table=True):
    """Registo de eventos da mesa (replay por seq, como no torneio). user_id preenchido = evento privado desse jogador."""
    __tablename__ = "poker_events"
    __table_args__ = (Index("ix_poker_events_table_seq", "table_id", "seq"),)

    seq: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    table_id: int = Field(sa_column=_fk("poker_tables.id"))
    type: str = Field(max_length=16)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    user_id: int | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class BitabitGame(SQLModel, table=True):
    __tablename__ = "bitabit_games"
    __table_args__ = (Index("ix_bitabit_user", "user_id", "finished_at"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(sa_column=_fk("users.id"))
    class_id: int | None = None
    seed: int = Field(sa_column=Column(BigInteger, nullable=False))
    config: dict = Field(sa_column=Column(JSONB, nullable=False))
    started_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    finished_at: datetime | None = Field(default=None, sa_column=_nullable_ts())
    score: int = Field(default=0)
    points: int = Field(default=0)
    valid: bool | None = None
    answers: list | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
