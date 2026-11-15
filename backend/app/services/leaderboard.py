# Leaderboard de pontos pessoais (livro user_points): público (só quem ativou a flag, só o display_name) e
# "o meu lugar" (entre TODOS os alunos, mesmo escondido). Semana = desde segunda-feira 00:00 (hora de Lisboa).
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models._base import utcnow
from app.models.points import UserPoints
from app.models.user import Role, User

LISBON = ZoneInfo("Europe/Lisbon")
CACHE_S = 30
_cache: dict[tuple, tuple[float, dict]] = {}


def week_start(now: datetime | None = None) -> datetime:
    """Segunda-feira às 00:00 de Lisboa que abre a semana atual, em UTC."""
    local = (now or utcnow()).astimezone(LISBON)
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.astimezone(timezone.utc)


def avatar_seed(user_id: int) -> str:
    """Semente estável para o avatar, sem revelar o id."""
    return hmac.new(settings.session_secret.encode(), f"avatar:{user_id}".encode(), hashlib.sha256).hexdigest()[:10]


async def totals(db: AsyncSession, period: str, now: datetime | None = None) -> list[tuple[User, int]]:
    """[(aluno, pontos)] com pontos > 0, ordenado por pontos desc e nome. Professores e convidados não entram."""
    q = (select(User, func.sum(UserPoints.points)).join(UserPoints, UserPoints.user_id == User.id)
         .where(User.role == Role.student, User.is_guest.is_(False)).group_by(User.id))
    if period == "week":
        q = q.where(UserPoints.created_at >= week_start(now))
    rows = [(u, int(p)) for u, p in (await db.execute(q)).all() if p and p > 0]
    rows.sort(key=lambda r: (-r[1], r[0].display_name.lower(), r[0].id))
    return rows


async def score_breakdown(db: AsyncSession, user_id: int, period: str, now: datetime | None = None) -> tuple[int, int]:
    """Devolve (MUNDO, torneios), mantendo as duas fontes explícitas no score pessoal."""
    filters = [UserPoints.user_id == user_id]
    if period == "week":
        filters.append(UserPoints.created_at >= week_start(now))
    mundo, tournaments = (await db.execute(
        select(
            func.coalesce(func.sum(UserPoints.points).filter(UserPoints.tournament_id.is_(None)), 0),
            func.coalesce(func.sum(UserPoints.points).filter(UserPoints.tournament_id.is_not(None)), 0),
        ).where(*filters)
    )).one()
    return int(mundo), int(tournaments)


async def public(db: AsyncSession, period: str, limit: int, now: datetime | None = None) -> dict:
    key = (period, limit)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_S and now is None:
        return hit[1]
    shown = [(u, p) for u, p in await totals(db, period, now) if u.show_in_leaderboard][:limit]
    data = {
        "period": period, "updated_at": utcnow().isoformat(),
        "entries": [{"rank": i, "display_name": u.display_name, "points": p, "avatar_seed": avatar_seed(u.id)} for i, (u, p) in enumerate(shown, 1)],
    }
    if now is None:
        _cache[key] = (time.monotonic(), data)
    return data


async def me(db: AsyncSession, user: User, period: str, now: datetime | None = None) -> dict:
    ranked = await totals(db, period, now)
    mundo, tournaments = await score_breakdown(db, user.id, period, now)
    mine = mundo + tournaments
    rank = 1 + sum(1 for _, p in ranked if p > mine) if mine > 0 else None
    return {"rank": rank, "points": mine, "visible": bool(user.show_in_leaderboard) and mine > 0, "total_ranked": len(ranked)}


def clear_cache() -> None:
    _cache.clear()
