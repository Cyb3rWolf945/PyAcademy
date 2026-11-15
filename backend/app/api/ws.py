# WebSocket do torneio: GET /ws/tournaments/{id}?last_seq=N. Autenticado pelo cookie de sessão, com verificação
# do Origin, mensagens até 8 KB e no máximo 3 ligações por utilizador. Ao ligar reenvia os eventos com seq > last_seq
# (ou manda {"type":"resync"} se faltarem mais de 500). O cliente envia {"type":"ping","last_seq":N} de 15 em 15 s.
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket
from sqlalchemy import select

from app.api.deps import COOKIE
from app.db import SessionLocal
from app.errors import ApiError
from app.models._base import utcnow
from app.models.session import AuthSession
from app.models.user import User
from app.realtime import presence
from app.realtime.pg_bus import Conn, hub
from app.services import security, tournament as svc, tournament_events as events

log = logging.getLogger("pyarena.ws")
router = APIRouter()
MAX_MESSAGE_BYTES = 8 * 1024
MAX_SOCKETS_PER_USER = 3
IDLE_TIMEOUT_S = 60  # sem ping há 60 s (o normal são 15 s): ligação morta


async def _authorize(ws: WebSocket, tid: int) -> User | None:
    """Origin certo + sessão válida + torneio visível para este utilizador; senão None."""
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
            await svc.viewable(db, tid, user)
        except ApiError:
            return None
        return user


@router.websocket("/ws/tournaments/{tid}")
async def tournament_socket(ws: WebSocket, tid: int, last_seq: int | None = None):
    user = await _authorize(ws, tid)
    if user is None or (last_seq is not None and last_seq < 0) or hub.count_user(user.id) >= MAX_SOCKETS_PER_USER:
        await ws.close(code=1008)  # antes de aceitar: o cliente recebe 403
        return
    await ws.accept()
    conn = Conn(ws=ws, user_id=user.id, tid=tid)
    await hub.subscribe(conn)
    try:
        async with conn.lock:
            async with SessionLocal() as db:
                if last_seq is None:  # sem histórico pedido: só o que vier daqui para a frente
                    conn.sent_seq = await events.last_seq(db, tid)
                else:
                    evs, resync = await events.replay(db, tid, last_seq)
                    if resync:
                        conn.sent_seq = await events.last_seq(db, tid)
                        await conn.send_json({"type": "resync"})
                    else:
                        conn.sent_seq = last_seq
                        for ev in evs:
                            if not events.visible_to(ev, user.id):
                                conn.sent_seq = ev["seq"]
                                continue
                            if not await conn.send_json(ev):
                                return
                            conn.sent_seq = ev["seq"]
            conn.ready = True
        await hub.fanout(tid)  # o que tenha chegado entre a leitura do replay e o ready
        async with SessionLocal() as db:
            await presence.touch(db, tid, user.id, conn.sent_seq)
        while not conn.dead:
            try:
                msg = await asyncio.wait_for(ws.receive(), IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                await ws.close(code=1001)
                break
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("text")
            if data is None and msg.get("bytes") is not None:
                data = msg["bytes"].decode("utf-8", "ignore")
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
                seen = obj.get("last_seq")
                async with SessionLocal() as db:
                    await presence.touch(db, tid, user.id, seen if isinstance(seen, int) and seen >= 0 else conn.sent_seq)
                await conn.send_json({"type": "pong", "server_now": utcnow().isoformat(), "last_seq": conn.sent_seq})
    except Exception as exc:  # noqa: BLE001 - desligar nunca pode rebentar o worker
        if exc.__class__.__name__ not in ("WebSocketDisconnect", "ConnectionClosed"):
            log.warning("socket do torneio %s terminou com erro: %r", tid, exc)
    finally:
        hub.unsubscribe(conn)
        if hub.count_user(user.id, tid) == 0:
            try:
                async with SessionLocal() as db:
                    await presence.mark_offline(db, tid, user.id)
            except Exception:  # noqa: BLE001
                pass
