# Submissões: criar (idempotente por client_id), limitar o ritmo, corrigir tipos sem código na app e
# enfileirar os de código (tabela jobs). O dispatcher (dispatcher.py) é quem fala com o runner.
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import ApiError
from app.models._base import utcnow
from app.models.problem import Problem
from app.models.submission import HintUse, Job, Submission
from app.models.user import Role, User
from app.services import grading
from app.services.problems import CODE_TIPOS, ProblemSpec


async def queue_position(db: AsyncSession, submission: Submission) -> int:
    """1 = a próxima a correr; 0 = já não está na fila."""
    job = (await db.execute(select(Job).where(Job.submission_id == submission.id))).scalar_one_or_none()
    if job is None or job.state != "queued":
        return 0
    return (await db.execute(select(func.count()).select_from(Job).where(Job.state == "queued", Job.id <= job.id))).scalar_one()


async def _existing(db: AsyncSession, user_id: int, client_id: uuid.UUID) -> Submission | None:
    return (await db.execute(select(Submission).where(Submission.user_id == user_id, Submission.client_id == client_id))).scalar_one_or_none()


async def create_submission(
    db: AsyncSession, user: User, client_id: uuid.UUID, problem: Problem, code: str | None, answers: list | None, hints_used: int,
) -> Submission:
    # idempotência: o mesmo client_id devolve a submissão que já existe (não conta para o limite)
    if (prev := await _existing(db, user.id, client_id)) is not None:
        return prev
    if problem.estado != "aprovado" and user.role != Role.teacher:
        raise ApiError(404, "problem.not_found")
    spec = ProblemSpec.model_validate(problem.data)

    recent = (await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.user_id == user.id, Submission.created_at > utcnow() - timedelta(seconds=60)
        )
    )).scalar_one()
    if recent >= settings.submissions_per_minute:
        raise ApiError(429, "submission.rate_limited")

    is_code = spec.tipo in CODE_TIPOS
    if is_code:
        if not code or not code.strip():
            raise ApiError(422, "submission.code_required")
        if len(code.encode("utf-8")) > settings.max_code_bytes:
            raise ApiError(422, "submission.code_too_large")
    elif not grading.valid_answers(spec, answers):
        raise ApiError(422, "submission.answers_invalid")

    server_hints = (await db.execute(
        select(func.count()).select_from(HintUse).where(HintUse.user_id == user.id, HintUse.problem_slug == problem.slug)
    )).scalar_one()
    sub = Submission(
        client_id=client_id, user_id=user.id, problem_slug=problem.slug, code=code or "", locale=user.locale,
        hints_used=max(server_hints, min(hints_used, len(spec.pistas))),  # o servidor nunca desce o que registou
    )
    if not is_code:
        graded = grading.grade(spec, answers, user.locale)
        sub.status, sub.passed, sub.total, sub.result, sub.finished_at = (
            graded["status"], graded["passed"], graded["total"], graded["result"], utcnow()
        )
    db.add(sub)
    try:
        await db.flush()
        if is_code:
            db.add(Job(submission_id=sub.id))
        await db.commit()
    except IntegrityError:  # pedido repetido em paralelo: ganhou o outro
        await db.rollback()
        prev = await _existing(db, user.id, client_id)
        if prev is None:
            raise
        return prev
    return sub
