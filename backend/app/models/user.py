# Modelos de utilizador (aluno/professor) e de turma.
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel

from app.models._base import ts_column, utcnow


class Role(str, Enum):
    teacher = "teacher"
    student = "student"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=32)
    email: str | None = Field(default=None, unique=True, index=True, max_length=254)
    display_name: str = Field(max_length=40)
    password_hash: str
    role: Role = Field(default=Role.student)
    locale: str = Field(default="pt-PT", max_length=8)
    preferred_theme: str | None = Field(default=None, max_length=32)
    preferred_font: str | None = Field(default=None, max_length=16)  # None = letra pixel; ver FONTS em api/auth.py
    # FK circular com school_classes -> use_alter (criada num ALTER TABLE)
    class_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer, ForeignKey("school_classes.id", ondelete="SET NULL", use_alter=True, name="fk_users_class_id"), nullable=True
        ),
    )
    must_change_password: bool = Field(default=False)
    # Aparecer no leaderboard público (só o display_name). Desligado por omissão (RGPD).
    show_in_leaderboard: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    is_guest: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))
    guest_tournament_id: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())


class SchoolClass(SQLModel, table=True):
    __tablename__ = "school_classes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=60)
    join_code: str = Field(unique=True, index=True, min_length=6, max_length=6)
    teacher_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=utcnow, sa_column=ts_column())
