# Presença: quem está ligado a cada torneio. O cliente envia um ping a cada 15 s e a linha da tabela
# `presence` (UNLOGGED) guarda a hora do último sinal; "online" = visto nos últimos 40 s.
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models._base import utcnow
from app.models.tournament import Presence

ONLINE_WINDOW_S = 40


async def touch(db: AsyncSession, tournament_id: int, user_id: int, last_seq: int = 0) -> None:
    now = utcnow()
    stmt = insert(Presence).values(tournament_id=tournament_id, user_id=user_id, last_seen=now, last_seq=last_seq)
    await db.execute(stmt.on_conflict_do_update(
        index_elements=["tournament_id", "user_id"], set_={"last_seen": now, "last_seq": last_seq}
    ))
    await db.commit()


async def mark_offline(db: AsyncSession, tournament_id: int, user_id: int) -> None:
    """Ao fechar o último socket deste utilizador neste worker, deixa de aparecer como online."""
    row = await db.get(Presence, (tournament_id, user_id))
    if row is not None:
        row.last_seen = utcnow() - timedelta(seconds=ONLINE_WINDOW_S + 1)
        await db.commit()


async def snapshot(db: AsyncSession, tournament_id: int) -> dict[int, dict]:
    """user_id -> {online, last_seen, last_seq}."""
    cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_S)
    rows = (await db.execute(select(Presence).where(Presence.tournament_id == tournament_id))).scalars()
    return {p.user_id: {"online": p.last_seen > cutoff, "last_seen": p.last_seen.isoformat(), "last_seq": p.last_seq} for p in rows}
