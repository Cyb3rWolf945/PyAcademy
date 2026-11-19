# Modelos da Academia: progresso por secção, registo das tentativas das atividades, decks de slides importados
# e os PDFs carregados pelo professor (abertos ao tocar na "Leitura recomendada").
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


class Document(SQLModel, table=True):
    """PDF carregado pelo professor (fica no volume "docs"; as páginas são servidas como imagens, nunca o ficheiro)."""
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    teacher_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True))
    titulo: str = Field(max_length=120)
    pages: int
    size_bytes: int
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())

