# Pontuação do torneio: regista cada missão resolvida UMA só vez (constraint única + lock por torneio),
# aplica pista 0,5×, multiplicador da ronda, bónus do primeiro e boss, e calcula/emite o ranking.
# O evento "leaderboard" é agrupado: no máximo 1 por segundo por torneio (porta na BD, vale para todos os workers).
import asyncio
import logging

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models._base import utcnow
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.tournament import (
    Tournament, TournamentBonus, TournamentHintUse, TournamentPlayer, TournamentRound, TournamentSolve,
    TournamentSubmission, TournamentTeam,
)
from app.models.user import User
from app.services import elimination, points as points_svc, tournament_events as events

log = logging.getLogger("pyarena.tournament")
COLORS = 8  # team-0 ... team-7


def num(x: float) -> float | int:
    x = round(float(x), 2)
    return int(x) if x == int(x) else x


async def participant_for(db: AsyncSession, t: Tournament, user_id: int) -> tuple[str, str, list[int]] | None:
    """(participant_key, nome, ids dos membros) de um aluno; None se não participa ou, em agências, não tem agência."""
    player = await db.get(TournamentPlayer, (t.id, user_id))
    if player is None:
        return None
    if t.mode == "agencias":
        if player.team_id is None:
            return None
        team = await db.get(TournamentTeam, player.team_id)
        members = (await db.execute(select(TournamentPlayer.user_id).where(TournamentPlayer.team_id == team.id))).scalars().all()
        return f"t:{team.id}", team.name, list(members)
    user = await db.get(User, user_id)
    return f"u:{user_id}", user.display_name, [user_id]


async def compute_leaderboard(db: AsyncSession, t: Tournament) -> list[dict]:
    rounds = (await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == t.id).order_by(TournamentRound.idx))).scalars().all()
    pos = {r.id: i for i, r in enumerate(rounds)}
    idx_of = {r.id: r.idx for r in rounds}
    parts: dict[str, dict] = {}
    if t.mode == "agencias":
        teams = (await db.execute(select(TournamentTeam).where(TournamentTeam.tournament_id == t.id))).scalars().all()
        counts = dict((await db.execute(
            select(TournamentPlayer.team_id, func.count()).where(TournamentPlayer.tournament_id == t.id, TournamentPlayer.team_id.is_not(None))
            .group_by(TournamentPlayer.team_id)
        )).all())
        for tm in teams:
            parts[f"t:{tm.id}"] = {"name": tm.name, "color_idx": tm.color_idx, "members": counts.get(tm.id, 0)}
    else:
        rows = (await db.execute(
            select(User.id, User.display_name).join(TournamentPlayer, TournamentPlayer.user_id == User.id).where(TournamentPlayer.tournament_id == t.id)
        )).all()
        for uid, name in rows:
            parts[f"u:{uid}"] = {"name": name, "color_idx": uid % COLORS, "members": 1}
    per: dict[str, list[float]] = {k: [0.0] * len(rounds) for k in parts}
    solved = {k: 0 for k in parts}
    for key, rid, pts in (await db.execute(
        select(TournamentSolve.participant_key, TournamentSolve.round_id, TournamentSolve.points).where(TournamentSolve.tournament_id == t.id)
    )).all():
        if key in per:
            per[key][pos[rid]] += pts
            solved[key] += 1
    for key, rid, pts in (await db.execute(
        select(TournamentBonus.participant_key, TournamentBonus.round_id, TournamentBonus.points)
        .join(TournamentRound, TournamentRound.id == TournamentBonus.round_id).where(TournamentRound.tournament_id == t.id)
    )).all():
        if key in per:
            per[key][pos[rid]] += pts
    # só entram agências com membros ou com pontos (uma agência esvaziada a meio do torneio mantém os pontos)
    keys = [k for k in parts if parts[k]["members"] > 0 or sum(per[k]) > 0]

    def ranks(points: dict[str, float]) -> dict[str, int]:
        return {k: 1 + sum(1 for o in keys if points[o] > points[k]) for k in keys}

    totals = {k: sum(per[k]) for k in keys}
    now_rank = ranks(totals)
    # delta_rank: posição antes da ronda atual/mais recente menos a posição agora (positivo = subiu)
    base_rank = None
    if t.current_round is not None:
        base = {k: sum(p for i, p in enumerate(per[k]) if rounds[i].idx < t.current_round) for k in keys}
        if any(v > 0 for v in base.values()):
            base_rank = ranks(base)
    order = sorted(keys, key=lambda k: (-totals[k], parts[k]["name"].lower(), k))
    return [{
        "participant_key": k, "name": parts[k]["name"], "color_idx": parts[k]["color_idx"], "points": num(totals[k]),
        "per_round": [num(p) for p in per[k]], "solved": solved[k], "rank": now_rank[k],
        "delta_rank": (base_rank[k] - now_rank[k]) if base_rank else 0,
    } for k in order]


def podium_of(leaderboard: list[dict]) -> list[dict]:
    return [{k: e[k] for k in ("participant_key", "name", "points", "rank", "color_idx")} for e in leaderboard[:3]]


async def emit_leaderboard_now(db: AsyncSession, t: Tournament) -> None:
    """Emite já (na transação do chamador) e reinicia a porta do agrupamento. Usado ao fechar rondas, etc."""
    await db.execute(text("UPDATE tournaments SET lb_emitted_at = clock_timestamp() WHERE id = :id"), {"id": t.id})
    await events.emit(db, t.id, "leaderboard", {"leaderboard": await compute_leaderboard(db, t)})


# ---------------- agrupamento do evento leaderboard (<= 1/s por torneio) ----------------
_GATE = text(
    """UPDATE tournaments SET lb_emitted_at = clock_timestamp()
       WHERE id = :id AND (lb_emitted_at IS NULL OR lb_emitted_at <= clock_timestamp() - interval '1 second')
       RETURNING id"""
)
_WAIT = text("SELECT extract(epoch from (lb_emitted_at + interval '1 second' - clock_timestamp())) FROM tournaments WHERE id = :id")
_pending: dict[int, asyncio.Task] = {}
_tasks: set[asyncio.Task] = set()


def schedule_leaderboard(tournament_id: int) -> None:
    """Pede um evento leaderboard. Se já houver um pedido à espera, este fica agrupado com ele."""
    if tournament_id in _pending:
        return
    task = asyncio.get_running_loop().create_task(_leaderboard_worker(tournament_id))
    _pending[tournament_id] = task
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _leaderboard_worker(tid: int) -> None:
    me = asyncio.current_task()
    try:
        while True:
            async with SessionLocal() as db:
                if (await db.execute(_GATE, {"id": tid})).first() is not None:
                    if _pending.get(tid) is me:
                        del _pending[tid]  # a partir daqui, uma nova alteração agenda outro evento
                    t = await db.get(Tournament, tid)
                    await events.emit(db, tid, "leaderboard", {"leaderboard": await compute_leaderboard(db, t)})
                    await db.commit()
                    return
                wait = (await db.execute(_WAIT, {"id": tid})).scalar()
                await db.rollback()
            if wait is None:
                return  # o torneio já não existe
            await asyncio.sleep(max(0.02, float(wait)) + 0.01)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("falha a emitir o leaderboard do torneio %s", tid)
    finally:
        if _pending.get(tid) is me:
            del _pending[tid]


async def drain() -> None:
    """Espera pelos leaderboards agendados (para os testes)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def cancel_all() -> None:
    for t in list(_tasks):
        t.cancel()
    await asyncio.gather(*list(_tasks), return_exceptions=True)
    _pending.clear()


# ---------------- registo das missões resolvidas ----------------
async def on_submission_finished(submission_id: int) -> None:
    """Chamado quando uma submissão termina (dispatcher, ou logo na criação nos tipos sem código).
    Se for de torneio e aceite, regista a missão. Repete algumas vezes se a BD falhar de forma transitória."""
    for attempt in range(3):
        try:
            async with SessionLocal() as db:
                link = await db.get(TournamentSubmission, submission_id)
                if link is None:
                    return
                sub = await db.get(Submission, submission_id)
                if sub is None or sub.status in ("queued", "running"):
                    return
                t = await db.get(Tournament, link.tournament_id)
                if t is not None and t.format == "eliminatoria":
                    await elimination.handle_finished(db, link, sub)
                elif sub.status == "accepted":
                    await record_solve(db, link, sub)
                return
        except Exception:  # noqa: BLE001
            log.exception("falha a registar a missão da submissão %s (tentativa %s)", submission_id, attempt + 1)
            await asyncio.sleep(0.5 * (attempt + 1))


async def record_solve(db: AsyncSession, link: TournamentSubmission, sub: Submission) -> bool:
    """Regista a missão uma única vez por participante. True se foi esta chamada a registar."""
    tid = link.tournament_id
    await events.lock(db, tid)  # tudo o que segue é serializado por torneio (e a constraint única é a rede de segurança)
    t = await db.get(Tournament, tid)
    rnd = await db.get(TournamentRound, link.round_id)
    if t is None or rnd is None or sub.problem_slug not in rnd.problem_slugs:
        await db.rollback()
        return False
    who = await participant_for(db, t, sub.user_id)
    if who is None:
        await db.rollback()
        return False
    key, name, members = who
    cfg = t.config
    hint_used = (await db.execute(
        select(func.count()).select_from(TournamentHintUse).where(
            TournamentHintUse.round_id == rnd.id, TournamentHintUse.problem_slug == sub.problem_slug, TournamentHintUse.user_id.in_(members)
        )
    )).scalar_one() > 0
    points = round(rnd.points * rnd.multiplier * (cfg.get("hint_factor", 0.5) if hint_used else 1), 2)
    inserted = (await db.execute(
        insert(TournamentSolve).values(
            tournament_id=tid, round_id=rnd.id, problem_slug=sub.problem_slug, participant_key=key, points=points,
            hint_used=hint_used, submission_id=sub.id, solved_at=utcnow(),
        ).on_conflict_do_nothing(constraint="uq_solve_once").returning(TournamentSolve.id)
    )).scalar_one_or_none()
    if inserted is None:  # já estava resolvida (colega da agência, reenvio): não conta outra vez
        await db.rollback()
        return False
    await events.emit(db, tid, "mission_solved", {
        "participant_key": key, "name": name, "slug": sub.problem_slug, "points": num(points), "hint_used": hint_used,
    })
    if rnd.is_boss:
        total = (await db.execute(select(func.count()).select_from(TournamentSolve).where(TournamentSolve.round_id == rnd.id))).scalar_one()
        if total == 1:
            await events.emit(db, tid, "boss_defeated", {"participant_key": key, "name": name})
    else:
        mine = (await db.execute(select(func.count()).select_from(TournamentSolve).where(
            TournamentSolve.round_id == rnd.id, TournamentSolve.participant_key == key))).scalar_one()
        bonus_pts = cfg.get("first_bonus", 5)
        if mine >= len(rnd.problem_slugs) and bonus_pts:
            got = (await db.execute(
                insert(TournamentBonus).values(round_id=rnd.id, participant_key=key, points=bonus_pts, kind="first")
                .on_conflict_do_nothing(constraint="uq_bonus_round_kind").returning(TournamentBonus.id)
            )).scalar_one_or_none()
            if got is not None:
                await events.emit(db, tid, "first_bonus", {"participant_key": key, "name": name, "idx": rnd.idx})
    if t.mode == "individual":  # pontos pessoais (livro): o Formato Aula individual também conta
        prob = await db.get(Problem, sub.problem_slug)
        stars = prob.data.get("dificuldade", 1) if prob else 1
        await points_svc.award(db, t, sub.user_id, points_svc.config_points(t)[points_svc.difficulty_key(stars)], "exercise", rnd.idx, sub.problem_slug)
    await db.commit()
    schedule_leaderboard(tid)
    return True


