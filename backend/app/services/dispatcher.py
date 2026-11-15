# Dispatcher: tarefa de fundo em cada worker da app que tira trabalhos da fila (jobs) com
# FOR UPDATE SKIP LOCKED, chama o runner, guarda o resultado e recupera trabalhos "presos".
# Se o runner estiver em baixo, o trabalho volta à fila (a submissão não se perde).
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models._base import utcnow
from app.models.problem import Problem
from app.models.submission import Job, Submission
from app.services import feedback, runner_client, tournament_scoring
from app.services.problems import ProblemSpec

log = logging.getLogger("pyarena.dispatcher")
CLAIM_SQL = text(
    """UPDATE jobs SET state='running', locked_at=now(), attempts=attempts+1
       WHERE id = (SELECT id FROM jobs WHERE state='queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
       RETURNING id, submission_id, attempts"""
)
wake = asyncio.Event()  # acorda os ciclos locais quando este worker cria uma submissão


async def recover_stale(db: AsyncSession, older_than_s: int | None = None) -> int:
    """Trabalhos 'running' há demasiado tempo (worker morreu) voltam à fila; sem tentativas, falham."""
    cutoff = utcnow() - timedelta(seconds=older_than_s if older_than_s is not None else settings.job_stale_s)
    stale = (Job.state == "running") & (Job.locked_at < cutoff)
    failed = await db.execute(
        update(Job).where(stale, Job.attempts >= settings.job_max_attempts).values(state="failed").returning(Job.submission_id)
    )
    for (sid,) in failed.all():
        await db.execute(update(Submission).where(Submission.id == sid).values(
            status="error", result={"error": "submission.runner_unavailable"}, finished_at=utcnow()))
    res = await db.execute(update(Job).where(stale).values(state="queued", locked_at=None))
    await db.commit()
    return res.rowcount or 0


async def claim_job(db: AsyncSession):
    row = (await db.execute(CLAIM_SQL)).first()
    await db.commit()
    return row


async def _ensure_generated(db: AsyncSession, problem: Problem, spec: ProblemSpec, post=None) -> dict | None:
    if not runner_client.generator_exprs(spec):
        return None
    gen = problem.generated
    if gen and gen.get("hash") == runner_client.generated_hash(spec):
        return gen
    resp = await (post or runner_client.post)("/generate", runner_client.build_generate_request(spec))
    if resp.get("status") != "ok":
        raise ValueError(f"geradores falharam em {spec.id}: {resp.get('status')}")
    gen = runner_client.items_to_generated(spec, resp["items"])
    await db.execute(update(Problem).where(Problem.slug == problem.slug).values(generated=gen))
    await db.commit()
    return gen


async def process_job(job_id: int, submission_id: int, attempts: int, post=None) -> None:
    """Corre uma submissão e guarda o resultado. Qualquer falha inesperada (incl. ao gravar) volta a pôr o
    trabalho na fila e, ao fim de job_max_attempts, marca-o `failed` e a submissão `internal_error`:
    nada fica preso para sempre. `post` permite injetar um runner falso nos testes."""
    try:
        await _process(job_id, submission_id, attempts, post or runner_client.post)
    except Exception:  # noqa: BLE001
        log.exception("falha a processar a submissao %s (tentativa %s)", submission_id, attempts)
        retry = attempts < settings.job_max_attempts
        async with SessionLocal() as db:  # sessão nova: a anterior pode estar num estado de erro
            await db.execute(update(Job).where(Job.id == job_id).values(state="queued" if retry else "failed", locked_at=None))
            await db.execute(update(Submission).where(Submission.id == submission_id).values(
                **({"status": "queued"} if retry else
                   {"status": "internal_error", "result": {"error": "submission.internal_error"}, "finished_at": utcnow()})))
            await db.commit()
        if retry:
            await asyncio.sleep(1)


async def _process(job_id: int, submission_id: int, attempts: int, post) -> None:
    async with SessionLocal() as db:
        sub = await db.get(Submission, submission_id)
        problem = await db.get(Problem, sub.problem_slug) if sub else None
        if sub is None or problem is None:
            await db.execute(update(Job).where(Job.id == job_id).values(state="failed"))
            await db.commit()
            return
        await db.execute(update(Submission).where(Submission.id == sub.id).values(status="running"))
        await db.commit()
        try:
            spec = ProblemSpec.model_validate(problem.data)
            gen = await _ensure_generated(db, problem, spec, post)
            req = runner_client.build_run_request(spec, sub.code, sub.locale, gen)
            resp = await post("/run", req)
        except runner_client.RunnerError as exc:
            retry = attempts < settings.job_max_attempts
            log.warning("runner indisponivel (tentativa %s): %s", attempts, exc)
            await db.execute(update(Job).where(Job.id == job_id).values(state="queued" if retry else "failed", locked_at=None))
            await db.execute(update(Submission).where(Submission.id == sub.id).values(
                **({"status": "queued"} if retry else {"status": "error", "result": {"error": "submission.runner_unavailable"}, "finished_at": utcnow()})))
            await db.commit()
            if retry:
                await asyncio.sleep(1)
            return
        result = feedback.sanitize_result(resp)
        await db.execute(update(Submission).where(Submission.id == sub.id).values(
            status=resp["status"], passed=resp["passed"], total=resp["total"], result=result, finished_at=utcnow()))
        await db.execute(update(Job).where(Job.id == job_id).values(state="done"))
        await db.commit()
    if resp["status"] == "accepted":  # torneio: regista a missão resolvida (no-op se não for de torneio)
        await tournament_scoring.on_submission_finished(submission_id)


async def run_once(post=None) -> bool:
    """Reclama e processa um trabalho. Devolve False se a fila estava vazia."""
    async with SessionLocal() as db:
        row = await claim_job(db)
    if row is None:
        return False
    await process_job(row.id, row.submission_id, row.attempts, post)
    return True


async def _loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            if not await run_once():
                wake.clear()
                try:
                    await asyncio.wait_for(wake.wait(), timeout=0.25)
                except asyncio.TimeoutError:
                    pass
        except Exception:  # noqa: BLE001
            log.exception("erro no dispatcher")
            await asyncio.sleep(1)


async def _janitor(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            async with SessionLocal() as db:
                if n := await recover_stale(db):
                    log.warning("%s trabalhos presos recolocados na fila", n)
        except Exception:  # noqa: BLE001
            log.exception("erro a recuperar trabalhos")
        await asyncio.sleep(5)


def start(stop: asyncio.Event) -> list[asyncio.Task]:
    tasks = [asyncio.create_task(_loop(stop)) for _ in range(settings.dispatch_concurrency)]
    tasks.append(asyncio.create_task(_janitor(stop)))
    return tasks
