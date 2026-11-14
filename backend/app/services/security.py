# Segurança: Argon2id, tokens de sessão (guardados só como HMAC-SHA256), CSRF e limite de tentativas.
import hashlib
import hmac
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models._base import utcnow
from app.models.session import AuthSession, LoginAttempt

_hasher = PasswordHasher()  # Argon2id por omissão
_DUMMY_HASH = _hasher.hash("pyarena-dummy")  # para igualar o tempo quando o utilizador não existe
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # sem caracteres ambíguos


def _hash_sync(password: str) -> str:
    return _hasher.hash(password)


def _verify_sync(hashed: str, password: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hash_sync, password)  # Argon2 é pesado: fora do event loop


async def verify_password(hashed: str | None, password: str) -> bool:
    return await run_in_threadpool(_verify_sync, hashed or _DUMMY_HASH, password) and hashed is not None


def random_code(length: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length)).upper()


def random_password(length: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def hash_token(token: str) -> str:
    return hmac.new(settings.session_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


async def create_session(db: AsyncSession, user_id: int) -> tuple[str, AuthSession]:
    """Cria uma sessão nova. Devolve (token em claro para o cookie, linha da BD)."""
    token = secrets.token_urlsafe(32)  # 32 bytes aleatórios
    now = utcnow()
    row = AuthSession(
        token_hash=hash_token(token),
        user_id=user_id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now + timedelta(days=settings.session_days),
        last_seen=now,
    )
    db.add(row)
    await db.flush()
    return token, row


def origin_ok(origin: str | None, referer: str | None) -> bool:
    allowed = settings.public_origin.rstrip("/")
    if origin:
        return origin == allowed
    if referer:
        return referer == allowed or referer.startswith(allowed + "/")
    return False


def csrf_ok(expected: str, given: str | None) -> bool:
    return bool(given) and secrets.compare_digest(expected, given)


async def recent_failures(db: AsyncSession, username: str, ip: str) -> int:
    since = utcnow() - timedelta(minutes=settings.login_window_minutes)
    q = select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.username == username, LoginAttempt.ip == ip, LoginAttempt.at > since
    )
    return (await db.execute(q)).scalar_one()


async def record_failure(db: AsyncSession, username: str, ip: str) -> None:
    db.add(LoginAttempt(username=username[:64], ip=ip[:64]))
    await db.commit()
