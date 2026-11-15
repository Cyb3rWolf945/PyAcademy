# Pontos pessoais: regista cada pontuação no livro `user_points` (idempotente por chave única) e avisa o próprio
# aluno com o evento points_awarded (que o WebSocket só entrega ao sockets desse utilizador).
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tournament import Tournament
from app.services import tournament_events as events

DEFAULT_POINTS = {
    "easy": 10, "medium": 20, "hard": 30, "group_win": 15, "champion": 100, "second": 50, "third": 25, "participation": 5,
}

_INSERT = text(
    """INSERT INTO user_points (user_id, points, reason, tournament_id, round_idx, problem_slug, created_at)
       VALUES (:u, :p, :r, :t, :i, :s, now())
       ON CONFLICT (user_id, COALESCE(tournament_id, 0), reason, COALESCE(round_idx, 0), COALESCE(problem_slug, ''))
       DO NOTHING RETURNING id"""
)


def difficulty_key(stars: int) -> str:
    return "easy" if stars <= 2 else "medium" if stars == 3 else "hard"


def config_points(t: Tournament) -> dict:
    return {**DEFAULT_POINTS, **(t.config.get("points") or {})}


async def award(
    db: AsyncSession, t: Tournament | None, user_id: int, points: int, reason: str,
    round_idx: int | None = None, slug: str | None = None, *, notify: bool = True,
) -> bool:
    """True se foi registado agora (False = já existia, nada muda). Na transação do chamador."""
    if points <= 0:
        return False
    got = (await db.execute(_INSERT, {
        "u": user_id, "p": points, "r": reason, "t": t.id if t else None, "i": round_idx, "s": slug,
    })).scalar_one_or_none()
    if got is None:
        return False
    if notify and t is not None:
        await events.emit(db, t.id, "points_awarded", {"user_id": user_id, "points": points, "reason": reason})
    return True
