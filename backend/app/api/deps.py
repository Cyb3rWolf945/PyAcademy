# Dependências comuns das rotas: sessão atual, CSRF/Origin, papéis e auditoria.
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models._base import utcnow
from app.models.audit import AuditLog
from app.models.session import AuthSession
from app.models.user import Role, User
from app.services import security

COOKIE = "pyarena_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def origin_guard(request: Request) -> None:
    """Em pedidos que alteram dados, o Origin (ou Referer) tem de ser o PUBLIC_ORIGIN."""
    if request.method not in SAFE_METHODS and not security.origin_ok(
        request.headers.get("origin"), request.headers.get("referer")
    ):
        raise ApiError(403, "auth.csrf")


class Auth:
    """Utilizador autenticado + a sua sessão."""

    def __init__(self, user: User, session: AuthSession):
        self.user, self.session = user, session


async def current_auth(request: Request, db: AsyncSession = Depends(get_db)) -> Auth:
    token = request.cookies.get(COOKIE)
    if not token:
        raise ApiError(401, "auth.not_authenticated")
    row = (await db.execute(select(AuthSession).where(AuthSession.token_hash == security.hash_token(token)))).scalar_one_or_none()
    now = utcnow()
    if row is None or row.expires_at <= now:
        raise ApiError(401, "auth.not_authenticated")
    if request.method not in SAFE_METHODS and not security.csrf_ok(row.csrf_token, request.headers.get("x-csrf-token")):
        raise ApiError(403, "auth.csrf")
    user = await db.get(User, row.user_id)
    if user is None:
        raise ApiError(401, "auth.not_authenticated")
    # expiração deslizante (atualiza no máximo 1x/minuto para não escrever em todos os pedidos)
    if now - row.last_seen > timedelta(minutes=1):
        row.last_seen = now
        row.expires_at = now + timedelta(days=settings.session_days)
        await db.commit()
    return Auth(user, row)


async def active_auth(auth: Auth = Depends(current_auth)) -> Auth:
    """Como current_auth, mas bloqueia enquanto a palavra-passe temporária não for mudada."""
    if auth.user.must_change_password:
        raise ApiError(403, "auth.must_change_password")
    return auth


async def teacher_auth(auth: Auth = Depends(active_auth)) -> Auth:
    if auth.user.role != Role.teacher:
        raise ApiError(403, "auth.forbidden")
    return auth


async def audit(db: AsyncSession, actor_id: int | None, action: str, payload: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, payload=payload or {}))


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
