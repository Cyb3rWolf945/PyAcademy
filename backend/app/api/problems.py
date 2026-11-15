# Rotas de problemas: só devolvem a vista pública (sem testes escondidos nem soluções).
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, origin_guard
from app.db import get_db
from app.models._base import utcnow
from app.errors import ApiError
from app.models.problem import Problem
from app.models.submission import HintUse
from app.models.user import Role
from app.services.problems import ProblemSpec

router = APIRouter(prefix="/api", dependencies=[Depends(origin_guard)])


def _visible(auth: Auth, p: Problem) -> bool:
    return p.estado == "aprovado" or auth.user.role == Role.teacher  # rascunhos só para o professor


@router.get("/problems")
async def list_problems(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Problem).order_by(Problem.bloco, Problem.slug))).scalars()
    return {"problems": [
        {"id": p.slug, "titulo": p.data["titulo"], "tipo": p.tipo, "bloco": p.bloco, "dificuldade": p.data["dificuldade"],
         **({"estado": p.estado} if auth.user.role == Role.teacher else {})}
        for p in rows if _visible(auth, p)
    ]}


@router.get("/problems/{slug}")
async def get_problem(slug: str, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    p = await db.get(Problem, slug)
    if p is None or not _visible(auth, p):
        raise ApiError(404, "problem.not_found")
    return ProblemSpec.model_validate(p.data).public()


@router.get("/problems/{slug}/hints/{n}")
async def get_hint(slug: str, n: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    """Devolve a pista n (1, 2...) e regista o uso (cada pista usada vale 0,5x mais tarde)."""
    p = await db.get(Problem, slug)
    if p is None or not _visible(auth, p):
        raise ApiError(404, "problem.not_found")
    pistas = p.data.get("pistas") or []
    if not 1 <= n <= len(pistas):
        raise ApiError(404, "problem.hint_not_found")
    await db.execute(insert(HintUse).values(user_id=auth.user.id, problem_slug=slug, n=n, created_at=utcnow()).on_conflict_do_nothing())
    await db.commit()
    return {"n": n, "hint": pistas[n - 1]}
