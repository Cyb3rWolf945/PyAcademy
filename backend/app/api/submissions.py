# Rotas de submissões: criar (202, idempotente por client_id) e consultar (só o dono).
import uuid

from fastapi import APIRouter, Depends
from pydantic import ConfigDict, BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, origin_guard
from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.models.problem import Problem
from app.models.submission import Submission
from app.services import dispatcher, submissions
from app.services import tournament as tournament_svc
from app.services import tournament_scoring

router = APIRouter(prefix="/api", dependencies=[Depends(origin_guard)])


class SubmissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: uuid.UUID
    problem_slug: str = Field(max_length=80)
    code: str | None = Field(default=None, max_length=40000)  # o limite a sério (20 KB em bytes) está no serviço
    answers: list | None = Field(default=None, max_length=50)
    hints_used: int = Field(default=0, ge=0, le=10)
    tournament_id: int | None = None  # submissão de torneio: os dois campos vão juntos
    round_idx: int | None = None


async def _view(db: AsyncSession, sub: Submission) -> dict:
    return {
        "id": sub.id, "problem_slug": sub.problem_slug, "status": sub.status, "passed": sub.passed, "total": sub.total,
        "result": sub.result, "hints_used": sub.hints_used, "created_at": sub.created_at, "finished_at": sub.finished_at,
        "queue_position": await submissions.queue_position(db, sub) if sub.status == "queued" else 0,
    }


@router.post("/submissions", status_code=202)
async def create(body: SubmissionIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    problem = await db.get(Problem, body.problem_slug)
    if problem is None:
        raise ApiError(404, "problem.not_found")
    if (body.tournament_id is None) != (body.round_idx is None):
        raise ApiError(422, "tournament.invalid_submission")
    if body.tournament_id is None:
        sub = await submissions.create_submission(db, auth.user, body.client_id, problem, body.code, body.answers, body.hints_used)
    else:
        # reenvio com o mesmo client_id (fila offline): devolve a submissão que já existe, sem revalidar o tempo
        sub = await submissions.find_existing(db, auth.user.id, body.client_id)
        if sub is None:
            t, rnd = await tournament_svc.validate_submission(db, auth.user, body.tournament_id, body.round_idx, body.problem_slug)
            sub = await submissions.create_submission(
                db, auth.user, body.client_id, problem, body.code, body.answers, body.hints_used,
                mode="tournament", rate_per_minute=settings.tournament_submissions_per_minute, allow_draft=True,
            )
            await tournament_svc.link_submission(db, sub, t, rnd)
            if sub.status == "accepted":  # tipos sem código já vêm corrigidos: regista a missão já
                await tournament_scoring.on_submission_finished(sub.id)
    dispatcher.wake.set()
    view = await _view(db, sub)
    return {"id": sub.id, "status": sub.status, "queue_position": view["queue_position"]}


@router.get("/submissions/{submission_id}")
async def get_one(submission_id: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    sub = await db.get(Submission, submission_id)
    if sub is None or sub.user_id != auth.user.id:
        raise ApiError(404, "submission.not_found")
    return await _view(db, sub)
