# Sessões de login (token guardado só como hash) e tentativas de login falhadas (rate limit).
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class AuthSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    token_hash: str = Field(unique=True, index=True, max_length=64)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False))
    csrf_token: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
    expires_at: datetime = Field(sa_column=ts_column())
    last_seen: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class LoginAttempt(SQLModel, table=True):
    __tablename__ = "login_attempts"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=64)
    ip: str = Field(max_length=64)
    at: datetime = Field(default_factory=utcnow, sa_column=ts_column(index=True))
