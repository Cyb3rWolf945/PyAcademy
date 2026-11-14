# Rotas de problemas: só devolvem a vista pública (sem testes escondidos nem soluções).
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, origin_guard
from app.db import get_db
from app.errors import ApiError
from app.models.problem import Problem
from app.models.user import Role
from app.services.problems import ProblemSpec

router = APIRouter(prefix="/api", dependencies=[Depends(origin_guard)])


def _visible(auth: Auth, p: Problem) -> bool:
    return p.estado == "aprovado" or auth.user.role == Role.teacher  # rascunhos só para o professor


@router.get("/problems")
async def list_problems(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Problem).order_by(Problem.bloco, Problem.slug))).scalars()
    return {"problems": [
        {"id": p.slug, "titulo": p.data["titulo"], "tipo": p.tipo, "bloco": p.bloco, "dificuldade": p.data["dificuldade"]}
        for p in rows if _visible(auth, p)
    ]}


@router.get("/problems/{slug}")
async def get_problem(slug: str, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    p = await db.get(Problem, slug)
    if p is None or not _visible(auth, p):
        raise ApiError(404, "problem.not_found")
    return ProblemSpec.model_validate(p.data).public()
