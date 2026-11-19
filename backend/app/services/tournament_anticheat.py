# Anti-cheat do torneio: o browser do aluno avisa quando há um "colar" ou uma saída da janela durante a ronda; o servidor
# decide se conta, abre um incidente e bloqueia as submissões até o professor deixar voltar. Só o próprio e o professor sabem.
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models._base import utcnow
from app.models.tournament import Tournament, TournamentGroup, TournamentIncident, TournamentPlayer, TournamentRound
from app.models.user import User
from app.services import tournament_events as events

KINDS = ("paste", "drop", "blur", "hidden")


async def is_locked(db: AsyncSession, tid: int, user_id: int) -> bool:
    row = await db.execute(select(TournamentIncident.id).where(
        TournamentIncident.tournament_id == tid, TournamentIncident.user_id == user_id, TournamentIncident.released_at.is_(None)))
    return row.first() is not None


async def _current_round(db: AsyncSession, t: Tournament) -> TournamentRound | None:
    if t.current_round is None:
        return None
    return (await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == t.id, TournamentRound.idx == t.current_round))).scalars().first()


async def armed(db: AsyncSession, t: Tournament, user_id: int) -> bool:
    """Só vigia quem está mesmo a competir agora: ronda a decorrer e, na Eliminatória, num grupo ainda por decidir."""
    if t.state != "round_active":
        return False
    player = await db.get(TournamentPlayer, (t.id, user_id))
    if player is None:
        return False
    if t.format != "eliminatoria":
        return True
    rnd = await _current_round(db, t)
    if player.status != "alive" or rnd is None:
        return False
    groups = (await db.execute(select(TournamentGroup).where(TournamentGroup.round_id == rnd.id, TournamentGroup.decided.is_(False)))).scalars()
    return any(user_id in g.members for g in groups)


async def me_view(db: AsyncSession, t: Tournament, user_id: int) -> dict:
    """O que o ecrã do aluno precisa de saber. Com o torneio terminado já não há nada a bloquear."""
    row = (await db.execute(select(TournamentIncident.kind).where(
        TournamentIncident.tournament_id == t.id, TournamentIncident.user_id == user_id, TournamentIncident.released_at.is_(None)))).first()
    locked = row is not None and t.state != "finished"
    return {"armed": not locked and await armed(db, t, user_id), "locked": locked, "kind": row[0] if locked else None}


async def report(db: AsyncSession, t: Tournament, user: User, client_id: str, kind: str) -> dict:
    """Idempotente pelo client_id; fora de uma ronda a sério não faz nada."""
    if await db.get(TournamentPlayer, (t.id, user.id)) is None:
        raise ApiError(403, "tournament.not_participant")
    if await armed(db, t, user.id):
        res = await db.execute(insert(TournamentIncident).values(
            tournament_id=t.id, user_id=user.id, kind=kind, round_idx=t.current_round, client_id=client_id, created_at=utcnow(),
        ).on_conflict_do_nothing().returning(TournamentIncident.id))
        incident = res.scalar_one_or_none()
        if incident is not None:
            await events.emit(db, t.id, "anticheat_locked", {"user_id": user.id, "teacher_id": t.teacher_id, "kind": kind})
        await db.commit()
    return await me_view(db, t, user.id)


async def release(db: AsyncSession, t: Tournament, teacher: User, user_id: int) -> None:
    res = await db.execute(update(TournamentIncident).where(
        TournamentIncident.tournament_id == t.id, TournamentIncident.user_id == user_id, TournamentIncident.released_at.is_(None),
    ).values(released_at=utcnow(), released_by=teacher.id).returning(TournamentIncident.id))
    if res.scalar_one_or_none() is None:
        raise ApiError(404, "tournament.no_incident")
    await events.emit(db, t.id, "anticheat_released", {"user_id": user_id, "teacher_id": t.teacher_id})


async def pending_count(db: AsyncSession, tid: int) -> int:
    return (await db.execute(select(func.count()).select_from(TournamentIncident).where(
        TournamentIncident.tournament_id == tid, TournamentIncident.released_at.is_(None)))).scalar_one()


async def admin_view(db: AsyncSession, tid: int) -> list[dict]:
    """Alunos à espera de autorização, do mais antigo para o mais recente, com o total de vezes neste torneio."""
    totals = dict((await db.execute(select(TournamentIncident.user_id, func.count()).where(
        TournamentIncident.tournament_id == tid).group_by(TournamentIncident.user_id))).all())
    rows = (await db.execute(
        select(TournamentIncident, User.display_name).join(User, User.id == TournamentIncident.user_id)
        .where(TournamentIncident.tournament_id == tid, TournamentIncident.released_at.is_(None)).order_by(TournamentIncident.created_at)
    )).all()
    return [{"user_id": i.user_id, "display_name": name, "kind": i.kind, "round_idx": i.round_idx,
             "created_at": i.created_at.isoformat(), "offences": totals.get(i.user_id, 1)} for i, name in rows]
