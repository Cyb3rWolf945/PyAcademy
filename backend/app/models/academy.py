# Modelos da Academia: progresso por secção, registo das tentativas das atividades e os decks de slides importados.
from datetime import datetime

from sqlalchemy import Boolean, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class AcademyProgress(SQLModel, table=True):
    __tablename__ = "academy_progress"

    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    section_id: str = Field(primary_key=True, max_length=80)
    started_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    completed_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))
    verify_attempts: int = Field(default=0)
    hints_used: int = Field(default=0)
    first_try: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))


class AcademyActivityLog(SQLModel, table=True):
    __tablename__ = "academy_activity_log"

    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    section_id: str = Field(primary_key=True, max_length=80)
    activity_idx: int = Field(primary_key=True)
    attempts: int = Field(default=0)
    solved_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))


class SlideDeck(SQLModel, table=True):
    __tablename__ = "slide_decks"

    id: str = Field(primary_key=True, max_length=40)
    titulo: str = Field(max_length=120)
    n_slides: int
    imported_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
