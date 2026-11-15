# Leaderboard público (sem login; só quem ativou a opção, só o nome a mostrar) e a posição do próprio aluno.
import time

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, client_ip
from app.db import get_db
from app.errors import ApiError
from app.services import leaderboard

router = APIRouter(prefix="/api/leaderboard")
RATE_PER_MIN = 120  # leve: uma turma inteira partilha o IP e a página atualiza de 60 em 60 s
_hits: dict[str, list[float]] = {}


def _rate_limit(ip: str) -> None:
    now = time.monotonic()
    recent = [t for t in _hits.get(ip, []) if now - t < 60]
    if len(recent) >= RATE_PER_MIN:
        _hits[ip] = recent
        raise ApiError(429, "leaderboard.rate_limited")
    recent.append(now)
    _hits[ip] = recent
    if len(_hits) > 5000:  # não crescer sem fim
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
            del _hits[k]


def _period(period: str) -> str:
    if period not in ("all", "week"):
        raise ApiError(422, "common.invalid_request")
    return period


@router.get("/public")
async def public(request: Request, period: str = "all", limit: int = Query(default=10), db: AsyncSession = Depends(get_db)):
    _rate_limit(client_ip(request))
    return await leaderboard.public(db, _period(period), max(10, min(limit, 50)))


@router.get("/me")
async def my_rank(period: str = "all", auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await leaderboard.me(db, auth.user, _period(period))
