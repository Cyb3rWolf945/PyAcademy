# Testes do WebSocket do torneio contra um servidor uvicorn real (no mesmo loop dos testes): autenticação,
# Origin, receção de eventos, replay com last_seq, resync, limites (3 sockets, 8 KB), presença, pong,
# eventos agrupados e recuperação quando a ligação LISTEN à BD cai.
import asyncio
import json

import pytest
import pytest_asyncio
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.db import SessionLocal
from app.main import app
from app.models.tournament import TournamentEvent
from app.realtime.pg_bus import hub
from app.services import tournament_scoring
from tests.conftest import ORIGIN
from tests.test_tournament_support import add_problem, control, create_tournament, make_env, set_round, submit

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def server():
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
    srv = uvicorn.Server(config)
    task = asyncio.create_task(srv.serve())
    while not srv.started:
        await asyncio.sleep(0.02)
    port = srv.servers[0].sockets[0].getsockname()[1]
    yield f"ws://127.0.0.1:{port}"
    await tournament_scoring.drain()
    await hub.stop()
    srv.should_exit = True
    await task


def _cookie(client) -> str:
    return f"pyarena_session={client.cookies.get('pyarena_session')}"


def ws_connect(base, tid, client, last_seq=None, origin=ORIGIN, cookie=True):
    headers = {"Origin": origin} if origin else {}
    if cookie:
        headers["Cookie"] = _cookie(client)
    qs = "" if last_seq is None else f"?last_seq={last_seq}"
    return connect(f"{base}/ws/tournaments/{tid}{qs}", additional_headers=headers, open_timeout=5)


async def recv(ws, timeout=5):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def recv_until(ws, type_, timeout=6):
    while True:
        m = await recv(ws, timeout)
        if m.get("type") == type_:
            return m


async def setup(make_user, make_class, new_client, mode="individual", students=1, slugs=("m1",)):
    for s in slugs:
        await add_problem(s)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, mode)
    tid, code = t["tournament"]["id"], t["tournament"]["join_code"]
    await set_round(env, tid, 1, list(slugs))
    studs = []
    for i in range(students):
        u, c, h = await env.student(make_user, new_client, f"ana{i}")
        assert (await c.post("/api/tournaments/join", json={"join_code": code}, headers=h)).status_code == 200
        studs.append((u, c, h))
    return env, tid, studs


async def test_auth_and_origin_required(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client)
    _, c, _ = studs[0]
    with pytest.raises(InvalidStatus) as e:
        async with ws_connect(server, tid, c, cookie=False):
            pass
    assert e.value.response.status_code == 403
    with pytest.raises(InvalidStatus) as e:
        async with ws_connect(server, tid, c, origin="https://evil.example"):
            pass
    assert e.value.response.status_code == 403
    with pytest.raises(InvalidStatus) as e:  # sem Origin (não é um browser)
        async with ws_connect(server, tid, c, origin=None):
            pass
    assert e.value.response.status_code == 403
    await make_user("fora", class_id=None)
    async with new_client() as other:
        from tests.conftest import login
        await login(other, "fora")
        with pytest.raises(InvalidStatus) as e:  # aluno de outra turma
            async with ws_connect(server, tid, other):
                pass
        assert e.value.response.status_code == 403
    async with ws_connect(server, tid, c) as ws:  # o certo liga
        await ws.send(json.dumps({"type": "ping", "last_seq": 0}))
        assert (await recv(ws))["type"] == "pong"


async def test_receives_round_started_and_mission_solved_and_leaderboard(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client)
    _, c, h = studs[0]
    async with ws_connect(server, tid, c) as ws, ws_connect(server, tid, env.t_client) as wt:
        await control(env, tid, "rounds/1/start")
        for sock in (ws, wt):
            m = await recv_until(sock, "round_started")
            assert m["payload"]["idx"] == 1 and "ends_at" in m["payload"] and "server_now" in m["payload"] and isinstance(m["seq"], int)
        assert (await submit(c, h, tid, 1, "m1")).status_code == 202
        solved = await recv_until(ws, "mission_solved")
        assert solved["payload"]["slug"] == "m1" and solved["payload"]["points"] == 10  # 10 pontos da ronda
        board = await recv_until(ws, "leaderboard")
        assert board["payload"]["leaderboard"][0]["solved"] >= 0
        await control(env, tid, "rounds/1/pause")
        assert (await recv_until(ws, "round_paused"))["payload"]["idx"] == 1
        await control(env, tid, "rounds/1/resume")
        assert (await recv_until(ws, "round_resumed"))["payload"]["idx"] == 1
        await control(env, tid, "rounds/1/extend", {"seconds": 30})
        assert "ends_at" in (await recv_until(ws, "round_extended"))["payload"]
        await control(env, tid, "rounds/1/close")
        assert (await recv_until(ws, "round_closed"))["payload"] == {"idx": 1}
        await control(env, tid, "finish")
        fin = await recv_until(ws, "tournament_finished")
        assert fin["payload"]["podium"][0]["rank"] == 1


async def test_replay_with_last_seq_and_no_duplicates(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client, students=2)
    _, c, _ = studs[0]
    await control(env, tid, "rounds/1/start")
    async with ws_connect(server, tid, c, last_seq=0) as ws:  # reenvia tudo desde o início, por ordem
        seen = []
        while len(seen) < 4:
            seen.append(await recv(ws))
        assert [m["type"] for m in seen] == ["player_joined", "player_joined", "round_started", "leaderboard"]
        assert [m["seq"] for m in seen] == sorted(m["seq"] for m in seen)
        last = seen[-1]["seq"]
        # o cliente "perde a rede": fecha, entretanto passam eventos e reconecta com o último seq
    await control(env, tid, "rounds/1/pause")
    await control(env, tid, "rounds/1/resume")
    async with ws_connect(server, tid, c, last_seq=last) as ws:
        first = await recv(ws)
        second = await recv(ws)
        assert [first["type"], second["type"]] == ["round_paused", "round_resumed"] and first["seq"] > last
        await control(env, tid, "rounds/1/close")
        third = await recv_until(ws, "round_closed")  # e continua a receber ao vivo, sem repetir os anteriores
        assert third["seq"] > second["seq"]


async def test_resync_when_too_far_behind(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client)
    _, c, _ = studs[0]
    async with SessionLocal() as db:
        db.add_all([TournamentEvent(tournament_id=tid, type="leaderboard", payload={}) for _ in range(501)])
        await db.commit()
    async with ws_connect(server, tid, c, last_seq=0) as ws:
        assert await recv(ws) == {"type": "resync"}
        await control(env, tid, "rounds/1/start")  # depois do resync segue ao vivo
        assert (await recv_until(ws, "round_started"))["payload"]["idx"] == 1


async def test_limits_3_sockets_and_8kb_messages(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client)
    _, c, _ = studs[0]
    async with ws_connect(server, tid, c) as a, ws_connect(server, tid, c) as b, ws_connect(server, tid, c) as d:
        with pytest.raises(InvalidStatus) as e:
            async with ws_connect(server, tid, c):
                pass
        assert e.value.response.status_code == 403
        await a.send("x" * (8 * 1024 + 1))
        with pytest.raises(ConnectionClosed) as cc:
            await asyncio.wait_for(a.recv(), 5)
        assert cc.value.rcvd.code == 1009
        await b.send(json.dumps({"type": "ping", "last_seq": 0}))
        assert (await recv(b))["type"] == "pong"  # os outros continuam
        await d.send("not json")  # lixo é ignorado
        await d.send(json.dumps({"type": "ping"}))
        assert (await recv(d))["type"] == "pong"
    async with ws_connect(server, tid, c):  # fechados os anteriores, volta a haver lugar
        pass


async def test_presence_via_ping(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client, students=2)
    _, c, _ = studs[0]
    async with ws_connect(server, tid, c) as ws:
        await ws.send(json.dumps({"type": "ping", "last_seq": 7}))
        assert (await recv(ws))["type"] == "pong"
        players = (await env.t_client.get(f"/api/tournaments/{tid}/admin")).json()["players"]
        assert {p["display_name"]: p["online"] for p in players} == {"Ana0": True, "Ana1": False}
    await asyncio.sleep(0.3)
    players = (await env.t_client.get(f"/api/tournaments/{tid}/admin")).json()["players"]
    assert not any(p["online"] for p in players)  # fechou: já não aparece como online


async def test_leaderboard_coalescing_over_ws(server, make_user, make_class, new_client):
    slugs = [f"m{i}" for i in range(8)]
    env, tid, studs = await setup(make_user, make_class, new_client, students=4, slugs=slugs)
    await control(env, tid, "rounds/1/start")
    async with ws_connect(server, tid, env.t_client) as wt:
        await asyncio.gather(*(submit(c, h, tid, 1, slugs[i * 2 + j]) for i, (_, c, h) in enumerate(studs) for j in range(2)))
        got, loop = [], asyncio.get_running_loop()
        t0 = loop.time()
        while loop.time() - t0 < 3:
            try:
                m = await recv(wt, 3 - (loop.time() - t0))
            except asyncio.TimeoutError:
                break
            got.append(m)
        solved = [m for m in got if m["type"] == "mission_solved"]
        boards = [m for m in got if m["type"] == "leaderboard"]
        assert len(solved) == 8 and 1 <= len(boards) <= 3  # 8 resoluções, o ranking vem agrupado
        assert sum(e["solved"] for e in boards[-1]["payload"]["leaderboard"]) == 8


async def test_listen_connection_drop_recovers(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client)
    _, c, _ = studs[0]
    async with ws_connect(server, tid, c) as ws:
        await ws.send(json.dumps({"type": "ping"}))
        await recv(ws)
        old_pid = hub._pg.get_server_pid()
        async with SessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT pg_terminate_backend(:p)"), {"p": old_pid})
            await db.commit()
        await control(env, tid, "rounds/1/start")  # evento durante a queda: chega pelo poll/recuperação
        assert (await recv_until(ws, "round_started", timeout=10))["payload"]["idx"] == 1
        for _ in range(50):  # e a ligação LISTEN volta com outro backend
            if hub._pg is not None and hub._pg.get_server_pid() != old_pid:
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("LISTEN nao religou")
        await control(env, tid, "rounds/1/pause")
        assert (await recv_until(ws, "round_paused", timeout=5))["payload"]["idx"] == 1


async def test_two_students_get_same_events(server, make_user, make_class, new_client):
    env, tid, studs = await setup(make_user, make_class, new_client, students=2)
    async with ws_connect(server, tid, studs[0][1]) as a, ws_connect(server, tid, studs[1][1]) as b:
        await control(env, tid, "rounds/1/start")
        ma, mb = await recv_until(a, "round_started"), await recv_until(b, "round_started")
        assert ma == mb
