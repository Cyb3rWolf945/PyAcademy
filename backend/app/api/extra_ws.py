# WebSocket do poker: GET /ws/extra/poker/{table_id}?last_seq=N. Mesmo padrão do torneio (cookie, Origin, 8 KB, 3 sockets,
# replay por seq). As cartas fechadas (evento hole_cards) só chegam ao próprio jogador; o professor da turma só observa.
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from app.api.deps import COOKIE
from app.db import SessionLocal
from app.errors import ApiError
from app.models._base import utcnow
from app.models.extra import PokerSeat
from app.models.session import AuthSession
from app.models.user import User
from app.realtime.pg_bus import Conn, Hub
from app.services import extra_poker as poker, security

log = logging.getLogger("pyarena.ws.poker")
router = APIRouter()
poker_hub = Hub(channel=poker.channel, fetch=poker.events_after, visible=poker.visible_to)
MAX_MESSAGE_BYTES = 8 * 1024
MAX_SOCKETS_PER_USER = 3
IDLE_TIMEOUT_S = 60


async def _authorize(ws: WebSocket, table_id: int) -> User | None:
    if not security.origin_ok(ws.headers.get("origin"), None):
        return None
    token = ws.cookies.get(COOKIE)
    if not token:
        return None
    async with SessionLocal() as db:
        row = (await db.execute(select(AuthSession).where(AuthSession.token_hash == security.hash_token(token)))).scalar_one_or_none()
        if row is None or row.expires_at <= utcnow():
            return None
        user = await db.get(User, row.user_id)
        if user is None or user.must_change_password:
            return None
        try:
            await poker.get_table(db, table_id, user)
        except ApiError:
            return None
        return user


async def _set_presence(user_id: int, table_id: int, online: bool) -> None:
    """Ligar volta a pôr o lugar em jogo; desligar (último socket) marca-o away."""
    async with SessionLocal() as db:
        await poker.lock(db, table_id)
        seat = (await db.execute(select(PokerSeat).where(PokerSeat.table_id == table_id, PokerSeat.user_id == user_id))).scalars().first()
        if seat is None:
            return
        if online and seat.status == "away" and seat.away_hands == 0:
            seat.status = "sitting"
        elif not online and seat.status == "sitting":
            seat.status = "away"
        else:
            return
        await poker.emit(db, table_id, "seat_changed", {"seat": seat.seat, "user_id": user_id, "stack": seat.stack, "status": seat.status})
        await db.commit()


@router.websocket("/ws/extra/poker/{table_id}")
async def poker_socket(ws: WebSocket, table_id: int, last_seq: int | None = None):
    user = await _authorize(ws, table_id)
    if user is None or (last_seq is not None and last_seq < 0) or poker_hub.count_user(user.id) >= MAX_SOCKETS_PER_USER:
        await ws.close(code=1008)
        return
    await ws.accept()
    conn = Conn(ws=ws, user_id=user.id, tid=table_id)
    await poker_hub.subscribe(conn)
    try:
        async with conn.lock:
            async with SessionLocal() as db:
                if last_seq is None:
                    conn.sent_seq = await poker.last_seq(db, table_id)
                else:
                    evs = await poker.events_after(db, table_id, last_seq, 501)
                    if len(evs) > 500:
                        conn.sent_seq = await poker.last_seq(db, table_id)
                        await conn.send_json({"type": "resync"})
                    else:
                        conn.sent_seq = last_seq
                        for ev in evs:
                            if not poker.visible_to(ev, user.id):
                                conn.sent_seq = ev["seq"]
                                continue
                            if not await conn.send_json(ev):
                                return
                            conn.sent_seq = ev["seq"]
            conn.ready = True
        await poker_hub.fanout(table_id)
        await _set_presence(user.id, table_id, True)
        while not conn.dead:
            try:
                msg = await asyncio.wait_for(ws.receive(), IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                await ws.close(code=1001)
                break
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("text") or (msg["bytes"].decode("utf-8", "ignore") if msg.get("bytes") else None)
            if data is None:
                continue
            if len(data.encode("utf-8")) > MAX_MESSAGE_BYTES:
                await ws.close(code=1009)
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "ping":
                await conn.send_json({"type": "pong", "server_now": utcnow().isoformat(), "last_seq": conn.sent_seq})
    except Exception as exc:  # noqa: BLE001
        if exc.__class__.__name__ not in ("WebSocketDisconnect", "ConnectionClosed"):
            log.warning("socket do poker %s terminou com erro: %r", table_id, exc)
    finally:
        poker_hub.unsubscribe(conn)
        if poker_hub.count_user(user.id, table_id) == 0:
            try:
                await _set_presence(user.id, table_id, False)
            except Exception:  # noqa: BLE001
                pass
