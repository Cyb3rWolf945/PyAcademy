# Pub/sub do torneio sem Redis: LISTEN/NOTIFY do PostgreSQL. Cada worker da app tem UMA ligação dedicada
# (asyncpg) que escuta os canais tournament_<id> dos torneios com sockets neste worker. O NOTIFY só leva o seq;
# o worker lê os eventos novos da tabela tournament_events e envia-os aos seus sockets.
# Robustez: se a ligação à BD cair, religa com backoff, volta a escutar tudo e recupera o que se perdeu;
# um poll de segurança (3 s) cobre qualquer NOTIFY perdido. A interface é pequena para facilitar trocar por Redis.
import asyncio
import json
import logging
from dataclasses import dataclass, field

import asyncpg
from fastapi import WebSocket

from app.config import settings
from app.db import SessionLocal
from app.services import tournament_events as events

log = logging.getLogger("pyarena.bus")
SEND_TIMEOUT_S = 5
POLL_S = 3


@dataclass(eq=False)
class Conn:
    """Um WebSocket aberto neste worker."""
    ws: WebSocket
    user_id: int
    tid: int
    sent_seq: int = 0  # último seq enviado a este socket (protege contra duplicados e desordem)
    ready: bool = False  # só recebe eventos "ao vivo" depois do replay inicial
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    dead: bool = False

    async def send_json(self, data: dict) -> bool:
        try:
            await asyncio.wait_for(self.ws.send_text(json.dumps(data, separators=(",", ":"))), SEND_TIMEOUT_S)
            return True
        except Exception:  # noqa: BLE001 - cliente lento ou caído: fecha-se e o cliente reconecta com last_seq
            self.dead = True
            try:
                await self.ws.close(code=1011)
            except Exception:  # noqa: BLE001
                pass
            return False

    async def send_events(self, evs: list[dict]) -> None:
        async with self.lock:
            for ev in evs:
                if ev["seq"] <= self.sent_seq or self.dead:
                    continue
                if not await self.send_json(ev):
                    return
                self.sent_seq = ev["seq"]


class Hub:
    def __init__(self) -> None:
        self.sockets: dict[int, set[Conn]] = {}
        self._pg: asyncpg.Connection | None = None
        self._listening: set[int] = set()
        self._lk: asyncio.Lock | None = None
        self._tasks: list[asyncio.Task] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._fan: dict[int, str] = {}  # tid -> "running" | "again"

    # ---- ciclo de vida ----
    def ensure_started(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is loop and self._tasks and not all(t.done() for t in self._tasks):
            return
        self._loop, self._lk, self._pg = loop, asyncio.Lock(), None
        self._listening.clear()
        self._fan.clear()
        self._tasks = [loop.create_task(self._supervisor()), loop.create_task(self._poller())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        for conns in list(self.sockets.values()):
            for c in list(conns):
                try:
                    await c.ws.close(code=1001)
                except Exception:  # noqa: BLE001
                    pass
        self.sockets.clear()

    # ---- sockets ----
    def count_user(self, user_id: int, tid: int | None = None) -> int:
        return sum(1 for tid_, cs in self.sockets.items() if tid is None or tid_ == tid for c in cs if c.user_id == user_id)

    async def subscribe(self, conn: Conn) -> None:
        self.ensure_started()
        self.sockets.setdefault(conn.tid, set()).add(conn)
        async with self._lk:
            if self._pg is not None and conn.tid not in self._listening:
                try:
                    await self._listen(conn.tid)
                except Exception:  # noqa: BLE001 - o supervisor trata de reconectar; o poll cobre entretanto
                    log.warning("LISTEN falhou para o torneio %s", conn.tid)

    def unsubscribe(self, conn: Conn) -> None:
        group = self.sockets.get(conn.tid)
        if group:
            group.discard(conn)
            if not group:
                del self.sockets[conn.tid]  # o UNLISTEN fica para o supervisor (inofensivo: sem sockets não faz nada)

    # ---- entrega ----
    async def fanout(self, tid: int) -> None:
        """Lê da BD os eventos novos e envia-os aos sockets prontos. Pedidos em simultâneo agrupam-se."""
        if self._fan.get(tid):
            self._fan[tid] = "again"
            return
        self._fan[tid] = "running"
        try:
            while True:
                ready = [c for c in self.sockets.get(tid, ()) if c.ready and not c.dead]
                if ready:
                    async with SessionLocal() as db:
                        evs = await events.events_after(db, tid, min(c.sent_seq for c in ready), limit=1000)
                    if evs:
                        await asyncio.gather(*(c.send_events(evs) for c in ready))
                if self._fan.get(tid) == "again":
                    self._fan[tid] = "running"
                    continue
                break
        except Exception:  # noqa: BLE001
            log.exception("falha a distribuir eventos do torneio %s", tid)
        finally:
            self._fan.pop(tid, None)

    # ---- ligação LISTEN ----
    async def _listen(self, tid: int) -> None:
        await self._pg.add_listener(events.channel(tid), self._on_notify)
        self._listening.add(tid)

    def _on_notify(self, _conn, _pid, channel: str, _payload: str) -> None:
        try:
            tid = int(channel.rsplit("_", 1)[1])
        except ValueError:
            return
        self._loop.create_task(self.fanout(tid))

    async def _supervisor(self) -> None:
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        backoff = 0.5
        while True:
            pg = None
            try:
                lost = asyncio.Event()
                async with self._lk:
                    pg = await asyncpg.connect(dsn, timeout=10)
                    pg.add_termination_listener(lambda _c: lost.set())
                    self._pg, self._listening = pg, set()
                    for tid in list(self.sockets):
                        await self._listen(tid)
                for tid in list(self.sockets):  # recupera o que passou enquanto a ligação esteve em baixo
                    self._loop.create_task(self.fanout(tid))
                backoff = 0.5
                while not lost.is_set():
                    try:
                        await asyncio.wait_for(lost.wait(), 10)
                    except asyncio.TimeoutError:
                        await asyncio.wait_for(pg.execute("SELECT 1"), 5)  # deteta ligações meio mortas
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("ligacao LISTEN perdida (%s); a religar em %.1fs", exc, backoff)
            finally:
                self._pg = None
                if pg is not None:
                    try:
                        await asyncio.wait_for(pg.close(), 3)
                    except Exception:  # noqa: BLE001
                        pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5)

    async def _poller(self) -> None:
        while True:
            await asyncio.sleep(POLL_S)
            for tid in list(self.sockets):
                self._loop.create_task(self.fanout(tid))


hub = Hub()
