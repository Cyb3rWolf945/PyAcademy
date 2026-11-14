# Registo de auditoria das ações do professor (e eventos sensíveis).
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    actor_id: int | None = Field(
        default=None, sa_column=Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    )
    action: str = Field(max_length=64)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
