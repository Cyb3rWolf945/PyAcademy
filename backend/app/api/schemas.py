# Corpos de pedido/resposta da API (pydantic) e validadores partilhados.
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")


def clean_username(v: str) -> str:
    v = v.strip().lower()
    if not USERNAME_RE.match(v):
        raise ValueError("invalid username")
    return v


def clean_display_name(v: str) -> str:
    v = " ".join(v.split())
    if not 1 <= len(v) <= 40:
        raise ValueError("invalid display name")
    return v


def check_password(v: str) -> str:
    if not 8 <= len(v) <= 128:
        raise ValueError("invalid password length")
    return v


def clean_student_email(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or v.count("@") != 1 or not v.split("@", 1)[0] or not v.endswith("@ipt.pt"):
        raise ValueError("invalid student email")
    return v


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(Strict):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _u(cls, v):
        return v.strip().lower()[:64]

    @field_validator("password")
    @classmethod
    def _p(cls, v):
        return v[:256]


class JoinIn(Strict):
    join_code: str
    email: str
    username: str
    display_name: str
    password: str

    _u = field_validator("username")(clean_username)
    _e = field_validator("email")(clean_student_email)
    _d = field_validator("display_name")(clean_display_name)
    _p = field_validator("password")(check_password)

    @field_validator("join_code")
    @classmethod
    def _j(cls, v):
        return v.strip().upper()[:12]


class GuestJoinIn(Strict):
    join_code: str
    display_name: str

    _d = field_validator("display_name")(clean_display_name)

    @field_validator("join_code")
    @classmethod
    def _j(cls, v):
        return v.strip().upper()[:12]


class ChangePasswordIn(Strict):
    current_password: str
    new_password: str

    _n = field_validator("new_password")(check_password)


class DeleteAccountIn(Strict):
    password: str


class PreferencesIn(Strict):
    locale: str | None = None
    preferred_theme: str | None = None
    show_in_leaderboard: bool | None = None
    display_name: str | None = None


class ClassIn(Strict):
    name: str

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        v = " ".join(v.split())
        if not 1 <= len(v) <= 60:
            raise ValueError("invalid class name")
        return v


class ClassJoinIn(Strict):
    join_code: str

    @field_validator("join_code")
    @classmethod
    def _j(cls, v):
        return v.strip().upper()[:12]


class ClassBulkDeleteIn(Strict):
    class_ids: list[int] = Field(min_length=1, max_length=100)


class ImportIn(Strict):
    csv: str
