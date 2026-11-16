# Testes do WebSocket do poker contra um servidor uvicorn real: autenticação/Origin/turma, eventos em tempo real,
# cartas fechadas só para o dono (também no replay), showdown público e replay com last_seq.
import asyncio
import json

import pytest
import pytest_asyncio
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from app.api.extra_ws import poker_hub
from app.main import app
from tests.conftest import ORIGIN
from tests.test_extra_poker import act, mk_table, play_all_in, sit, start, state, to_act_index, world

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def server():
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off"))
    task = asyncio.create_task(srv.serve())
    while not srv.started:
        await asyncio.sleep(0.02)
    yield f"ws://127.0.0.1:{srv.servers[0].sockets[0].getsockname()[1]}"
    await poker_hub.stop()
    srv.should_exit = True
    await task


def ws(base, tid, client, last_seq=None, origin=ORIGIN, cookie=True):
    headers = {"Origin": origin} if origin else {}
    if cookie:
        headers["Cookie"] = f"pyarena_session={client.cookies.get('pyarena_session')}"
    qs = "" if last_seq is None else f"?last_seq={last_seq}"
    return connect(f"{base}/ws/extra/poker/{tid}{qs}", additional_headers=headers, open_timeout=5)


async def drain(sock, quiet=0.6):
    out = []
    while True:
        try:
            out.append(json.loads(await asyncio.wait_for(sock.recv(), quiet)))
        except asyncio.TimeoutError:
            return out


async def test_ws_auth_origin_and_class(server, make_user, make_class, new_client):
    a = await world(make_user, make_class, new_client, n=1, class_code="CLSAAA", teacher="profa")
    b = await world(make_user, make_class, new_client, n=1, class_code="CLSBBB", teacher="profb")
    tid = await mk_table(a)
    c = a.students[0][1]
    for kw in ({"cookie": False}, {"origin": "https://evil.example"}, {"origin": None}):
        with pytest.raises(InvalidStatus) as e:
            async with ws(server, tid, c, **kw):
                pass
        assert e.value.response.status_code == 403
    with pytest.raises(InvalidStatus) as e:  # outra turma
        async with ws(server, tid, b.students[0][1]):
            pass
    assert e.value.response.status_code == 403
    with pytest.raises(InvalidStatus):
        async with ws(server, tid, b.tc):
            pass
    async with ws(server, tid, c) as s:
        await s.send(json.dumps({"type": "ping"}))
        assert json.loads(await asyncio.wait_for(s.recv(), 3))["type"] == "pong"


async def test_hole_cards_only_to_owner_and_showdown_is_public(server, make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=3, points=400)
    tid = await mk_table(w)
    for i in range(3):
        await sit(w, tid, i, i, 100)
    async with ws(server, tid, w.students[0][1]) as s0, ws(server, tid, w.students[1][1]) as s1, ws(server, tid, w.students[2][1]) as s2, ws(server, tid, w.tc) as st:
        socks = [s0, s1, s2, st]
        await start(tid)
        holes = {i: (await state(w.students[i][1], tid))["me"]["hole"] for i in range(3)}
        await play_all_in(w, tid)
        msgs = [await drain(s) for s in socks]
    for i in range(3):
        types = [m["type"] for m in msgs[i]]
        own = [m for m in msgs[i] if m["type"] == "hole_cards"]
        assert len(own) == 1 and own[0]["payload"]["cards"] == holes[i] and own[0]["payload"]["user_id"] == w.students[i][0].id
        assert {"hand_started", "turn", "action", "street", "showdown", "pot_awarded", "seat_changed"} & set(types) >= {"hand_started", "turn", "action", "pot_awarded"}
        seqs = [m["seq"] for m in msgs[i]]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert not [m for m in msgs[3] if m["type"] == "hole_cards"]  # o professor/espectador nunca as vê
    # antes do showdown, nenhuma carta fechada alheia viaja; depois do showdown vão em `showdown.hands`
    for i in range(3):
        for m in msgs[i]:
            if m["type"] in ("showdown", "hole_cards"):
                continue
            txt = json.dumps(m)
            assert not any(c in txt for j in range(3) if j != i for c in holes[j]) or m["type"] in ("street",), (i, m["type"])
    sd = [m for m in msgs[0] if m["type"] == "showdown"]
    assert sd and all({"user_id", "cards", "rank_name"} <= set(h) for h in sd[0]["payload"]["hands"]) and sd[0]["payload"]["board"]
    pa = [m for m in msgs[3] if m["type"] == "pot_awarded"][0]["payload"]
    assert pa["awards"] and sum(a["amount"] for a in pa["awards"]) == 300 and all({"user_id", "amount"} <= set(a) for a in pa["awards"])
    act_ev = [m for m in msgs[3] if m["type"] == "action"][0]["payload"]
    assert {"seat", "user_id", "type", "amount"} <= set(act_ev)
    turn = [m for m in msgs[3] if m["type"] == "turn"][0]["payload"]
    assert {"seat", "deadline", "server_now"} <= set(turn)
    street = [m for m in msgs[3] if m["type"] == "street"]
    assert [m["payload"]["street"] for m in street] == ["flop", "turn", "river"] and len(street[-1]["payload"]["board"]) == 5


async def test_replay_with_last_seq_keeps_private_cards_private(server, make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=2, points=400)
    tid = await mk_table(w)
    await sit(w, tid, 0, 0, 100)
    await sit(w, tid, 1, 1, 100)
    await start(tid)
    holes = {i: (await state(w.students[i][1], tid))["me"]["hole"] for i in range(2)}
    async with ws(server, tid, w.students[1][1], last_seq=0) as s:
        msgs = await drain(s)
    types = [m["type"] for m in msgs]
    assert "hand_started" in types and types.count("hole_cards") == 1
    assert [m for m in msgs if m["type"] == "hole_cards"][0]["payload"]["cards"] == holes[1]
    assert not any(c in json.dumps(msgs) for c in holes[0])
    last = msgs[-1]["seq"]
    cur = await to_act_index(w, tid)
    async with ws(server, tid, w.students[1][1], last_seq=last) as s:
        await act(w, cur, tid, "call")
        new = await drain(s)
    assert new and all(m["seq"] > last for m in new) and "action" in [m["type"] for m in new]
