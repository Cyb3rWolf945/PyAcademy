# Registo de eventos do torneio: cada evento fica na tabela tournament_events (replay ao reconectar) e
# avisa os workers com NOTIFY no canal tournament_<id> (o payload é só o seq). Tudo na MESMA transação
# da alteração, por isso nunca há um evento sem estado nem estado sem evento.
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models._base import utcnow
from app.models.tournament import TournamentEvent

MAX_REPLAY = 500  # se faltarem mais eventos do que isto, o cliente pede o snapshot completo
LOCK_NS = 1952  # espaço de nomes dos advisory locks do torneio


def channel(tournament_id: int) -> str:
    return f"tournament_{int(tournament_id)}"


async def lock(db: AsyncSession, tournament_id: int) -> None:
    """Serializa quem escreve eventos do mesmo torneio até ao commit: assim o seq segue a ordem do commit
    e nenhum cliente salta um evento (um seq maior nunca é visível antes de um seq menor)."""
    await db.execute(text("SELECT pg_advisory_xact_lock(:ns, :t)"), {"ns": LOCK_NS, "t": tournament_id})


def _jsonable(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


async def emit(db: AsyncSession, tournament_id: int, type_: str, payload: dict | None = None) -> int:
    """Grava o evento e faz NOTIFY (entregue quando a transação fizer commit). Devolve o seq."""
    await lock(db, tournament_id)
    ev = TournamentEvent(tournament_id=tournament_id, type=type_, payload=_jsonable(payload or {}), created_at=utcnow())
    db.add(ev)
    await db.flush()
    await db.execute(text("SELECT pg_notify(:ch, :p)"), {"ch": channel(tournament_id), "p": str(ev.seq)})
    return ev.seq


def visible_to(ev: dict, user_id: int) -> bool:
    """points_awarded só vai para o próprio aluno; o anti-cheat vai para o próprio e para o professor (nunca para a turma)."""
    p = ev["payload"]
    if ev["type"] == "points_awarded":
        return p.get("user_id") == user_id
    if ev["type"] in ("anticheat_locked", "anticheat_released"):
        return user_id in (p.get("user_id"), p.get("teacher_id"))
    return True


def event_view(ev: TournamentEvent) -> dict:
    return {"seq": ev.seq, "type": ev.type, "payload": ev.payload}


async def last_seq(db: AsyncSession, tournament_id: int) -> int:
    return (await db.execute(
        select(func.coalesce(func.max(TournamentEvent.seq), 0)).where(TournamentEvent.tournament_id == tournament_id)
    )).scalar_one()


async def events_after(db: AsyncSession, tournament_id: int, after: int, limit: int = MAX_REPLAY) -> list[dict]:
    rows = (await db.execute(
        select(TournamentEvent).where(TournamentEvent.tournament_id == tournament_id, TournamentEvent.seq > after)
        .order_by(TournamentEvent.seq).limit(limit)
    )).scalars()
    return [event_view(e) for e in rows]


async def replay(db: AsyncSession, tournament_id: int, after: int) -> tuple[list[dict], bool]:
    """(eventos com seq > after, resync). resync=True se faltarem mais de MAX_REPLAY: nesse caso
    não se devolvem eventos e o cliente deve pedir o snapshot (GET /state)."""
    missing = (await db.execute(
        select(func.count()).select_from(TournamentEvent).where(TournamentEvent.tournament_id == tournament_id, TournamentEvent.seq > after)
    )).scalar_one()
    if missing > MAX_REPLAY:
        return [], True
    return await events_after(db, tournament_id, after), False
