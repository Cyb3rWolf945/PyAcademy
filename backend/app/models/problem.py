# Problema sincronizado a partir dos YAML (data = spec completa, só lida no servidor).
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class Problem(SQLModel, table=True):
    __tablename__ = "problems"

    slug: str = Field(primary_key=True, max_length=80)
    data: dict = Field(sa_column=Column(JSONB, nullable=False))
    estado: str = Field(index=True, max_length=16)
    bloco: str = Field(index=True, max_length=4)
    tipo: str = Field(max_length=16)
    updated_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
