# Submissões dos alunos, fila de trabalhos do runner (Job) e pistas usadas (HintUse).
# A fila é só uma tabela: os workers pedem trabalhos com SELECT ... FOR UPDATE SKIP LOCKED.
import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class Submission(SQLModel, table=True):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_submissions_user_client"),
        Index("ix_submissions_user_created", "user_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    client_id: uuid.UUID = Field(sa_column=Column(UUID(as_uuid=True), nullable=False))  # idempotência
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False))
    problem_slug: str = Field(index=True, max_length=80)
    code: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    locale: str = Field(default="pt-PT", max_length=8)
    mode: str = Field(default="practice", max_length=16)
    status: str = Field(default="queued", max_length=24)  # queued | running | <estado final do runner> | error
    passed: int | None = None
    total: int | None = None
    result: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    hints_used: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    finished_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_state_id", "state", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(sa_column=Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True))
    state: str = Field(default="queued", max_length=12)  # queued | running | done | failed
    attempts: int = Field(default=0)
    locked_at: datetime | None = Field(default=None, sa_column=Column(ts_column().type, nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class HintUse(SQLModel, table=True):
    __tablename__ = "hint_uses"

    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    problem_slug: str = Field(primary_key=True, max_length=80)
    n: int = Field(primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
