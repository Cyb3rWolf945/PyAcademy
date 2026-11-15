# Rotas da Academia (sessão iniciada): módulos, secções, atividades, pistas, verificação e slides das aulas.
# Erros: {"error": "academy.<chave>"}. As respostas certas nunca saem do servidor.
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, origin_guard
from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models.academy import SlideDeck
from app.models.user import Role
from app.services import academy as svc

router = APIRouter(prefix="/api/academy", dependencies=[Depends(origin_guard)])
DECK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: dict


@router.get("")
async def overview(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await svc.overview(db, auth.user)


@router.get("/modules/{module_id}")
async def module(module_id: str, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await svc.module_view(db, auth.user, module_id)


@router.get("/sections/{section_id}")
async def section(section_id: str, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await svc.section_view(db, auth.user, section_id)


@router.post("/sections/{section_id}/activities/{idx}/answer")
async def answer(section_id: str, idx: int, body: AnswerIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    svc.rate_limit(auth.user.id, settings.academy_answers_per_minute)
    return await svc.answer_activity(db, auth.user, section_id, idx, body.resposta)


@router.get("/sections/{section_id}/hints/{n}")
async def hint(section_id: str, n: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await svc.open_hint(db, auth.user, section_id, n)


@router.post("/sections/{section_id}/verify")
async def verify(section_id: str, body: AnswerIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    svc.rate_limit(auth.user.id, settings.academy_answers_per_minute)
    return await svc.verify(db, auth.user, section_id, body.resposta)


# ---------------- slides (só com sessão: aluno com turma ou professor) ----------------
def _slides_user(auth: Auth) -> None:
    if auth.user.role != Role.teacher and auth.user.class_id is None:
        raise ApiError(403, "academy.slides_forbidden")


@router.get("/slides")
async def slides(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    _slides_user(auth)
    rows = (await db.execute(select(SlideDeck).order_by(SlideDeck.id))).scalars()
    return {"decks": [{"id": d.id, "titulo": d.titulo, "n_slides": d.n_slides} for d in rows]}


@router.get("/slides/{deck}/{n}")
async def slide(deck: str, n: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    _slides_user(auth)
    row = await db.get(SlideDeck, deck) if DECK_RE.fullmatch(deck) else None
    if row is None or not 1 <= n <= row.n_slides:
        raise ApiError(404, "academy.slide_not_found")
    root = settings.slides_dir.resolve()
    path = (root / row.id / f"{n}.png").resolve()
    if path.parent != root / row.id or not path.is_file():  # nunca sai da pasta do deck (nem por links simbólicos)
        raise ApiError(404, "academy.slide_not_found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})
