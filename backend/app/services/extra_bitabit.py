# Bit a Bit no servidor: cria a partida (seed), recalcula a sequência e a pontuação ao terminar, valida a plausibilidade
# do tempo, atribui `bitabit` ao livro (máximo 50/dia por aluno) e calcula recordes e ranking da turma.
import secrets
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models._base import utcnow
from app.models.extra import BitabitGame
from app.models.points import UserPoints
from app.models.user import Role, User
from app.services import bitabit as bb
from app.services import extra
from app.services.leaderboard import avatar_seed

MAX_GAME_MIN = 30


async def today_points(db: AsyncSession, user_id: int) -> int:
    return int((await db.execute(select(func.coalesce(func.sum(UserPoints.points), 0)).where(
        UserPoints.user_id == user_id, UserPoints.reason == "bitabit", UserPoints.created_at >= extra.day_start()))).scalar_one())


async def best_score(db: AsyncSession, user_id: int) -> int:
    return int((await db.execute(select(func.coalesce(func.max(BitabitGame.score), 0)).where(BitabitGame.user_id == user_id, BitabitGame.valid.is_(True)))).scalar_one())


async def daily_cap(db: AsyncSession, user: User) -> int:
    return (await extra.get_settings(db, user.class_id))["bitabit_daily_cap"] if user.class_id else bb_cap()


def bb_cap() -> int:
    return extra.DEFAULTS["bitabit_daily_cap"]


async def me(db: AsyncSession, user: User) -> dict:
    cap = await daily_cap(db, user)
    used = await today_points(db, user.id)
    games = int((await db.execute(select(func.count()).select_from(BitabitGame).where(
        BitabitGame.user_id == user.id, BitabitGame.started_at >= extra.day_start()))).scalar_one())
    return {"today_points": used, "daily_cap": cap, "today_remaining": max(0, cap - used), "best_score": await best_score(db, user.id), "games_today": games}


async def start(db: AsyncSession, user: User) -> dict:
    recent = int((await db.execute(select(func.count()).select_from(BitabitGame).where(
        BitabitGame.user_id == user.id, BitabitGame.started_at >= utcnow() - timedelta(seconds=60)))).scalar_one())
    if recent >= 30:
        raise ApiError(429, "extra.rate_limited")
    seed = secrets.randbits(32)
    g = BitabitGame(user_id=user.id, class_id=user.class_id, seed=seed, config=bb.config())
    db.add(g)
    await db.commit()
    return {"game_id": g.id, "seed": seed, "config": g.config, "started_at": g.started_at.isoformat(), **{k: v for k, v in (await me(db, user)).items() if k in ("today_remaining", "best_score")}}


async def finish(db: AsyncSession, user: User, game_id: int, answers: list, client_score: int | None) -> dict:
    await db.execute(text("SELECT pg_advisory_xact_lock(2025, :u)"), {"u": user.id})
    g = await db.get(BitabitGame, game_id, with_for_update=True)
    if g is None or g.user_id != user.id:
        raise ApiError(404, "extra.game_not_found")
    if g.finished_at is not None:
        raise ApiError(409, "extra.game_finished")
    now = utcnow()
    elapsed = int((now - g.started_at).total_seconds() * 1000)
    g.finished_at, g.answers = now, answers if isinstance(answers, list) else []
    if elapsed > MAX_GAME_MIN * 60_000:
        g.valid = False
        await db.commit()
        raise ApiError(422, "extra.bitabit_expired")
    try:
        score, right = bb.evaluate(g.seed, answers, elapsed)
    except bb.Implausible:
        g.valid = False
        await db.commit()
        raise ApiError(422, "extra.bitabit_implausible") from None
    g.valid, g.score = True, score  # o score enviado pelo cliente é ignorado: conta o recalculado
    cap = await daily_cap(db, user)
    used = await today_points(db, user.id)
    earned = max(0, min(score // bb.POINTS_DIV, cap - used))
    g.points = earned
    if earned and user.role == Role.student:
        await db.execute(text("""INSERT INTO user_points (user_id, points, reason, tournament_id, round_idx, problem_slug, created_at)
                                VALUES (:u, :p, 'bitabit', NULL, NULL, :s, now())
                                ON CONFLICT (user_id, COALESCE(tournament_id, 0), reason, COALESCE(round_idx, 0), COALESCE(problem_slug, '')) DO NOTHING"""),
                         {"u": user.id, "p": earned, "s": f"game-{g.id}"})
    await db.commit()
    return {"score": score, "rows_correct": right, "points_awarded": earned, "best": await best_score(db, user.id),
            "today_remaining": max(0, cap - used - earned), "client_score_ignored": client_score is not None and client_score != score}


async def leaderboard(db: AsyncSession, user: User, class_id: int | None, limit: int = 10) -> dict:
    cls = await extra.class_for(db, user, class_id)
    rows = (await db.execute(
        select(User.id, User.display_name, func.max(BitabitGame.score)).join(BitabitGame, BitabitGame.user_id == User.id)
        .where(User.class_id == cls.id, User.role == Role.student, BitabitGame.valid.is_(True)).group_by(User.id).order_by(func.max(BitabitGame.score).desc(), User.display_name))).all()
    entries = [{"rank": i, "display_name": n, "best": int(b), "avatar_seed": avatar_seed(u), "me": u == user.id} for i, (u, n, b) in enumerate(rows, 1) if b]
    mine = next((e for e in entries if e["me"]), None)
    return {"entries": entries[:limit], "me": {"best": mine["best"] if mine else 0, "rank": mine["rank"] if mine else None}}
