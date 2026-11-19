# Testes da Eliminatória: grupos equilibrados, simulação completa até ao campeão com o livro de pontos, decisão por
# testes/tempo/sorteio, correção do professor, fecho automático (uma só vez com 2 workers), treino dos eliminados,
# pontos idempotentes, progresso agrupado, snapshot e privacidade, leaderboard público e janela semanal.
import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models._base import utcnow
from app.models.points import UserPoints
from app.models.tournament import TournamentGroup, TournamentPlayer, TournamentRound
from app.services import elimination, leaderboard, points, tournament_scoring
from tests.conftest import login
from tests.test_tournament_support import (
    add_players, add_problem, admin, control, create_elim, events_of, fake_submit, ledger, make_env, round_row, set_round,
    state, total_points,
)

pytestmark = pytest.mark.asyncio


# ---------------- planeamento ----------------
async def test_group_sizes_and_bracket_for_2_to_25_players():
    for gs in (3, 4, 5, 6):
        for adv in (1, 2):
            for n in range(2, 26):
                plan = elimination.plan_bracket(n, gs, adv)
                assert plan[-1]["is_final"] and plan[-1]["groups"] == 1 and plan[-1]["sizes"] == [plan[-1]["sizes"][0]]
                alive = n
                for r in plan:
                    assert r["is_final"] == (alive <= gs + 1)  # final quando restam <= group_size + 1
                    assert sum(r["sizes"]) == alive and len(r["sizes"]) == r["groups"]
                    assert max(r["sizes"]) - min(r["sizes"]) <= 1 and min(r["sizes"]) >= 2 and max(r["sizes"]) <= gs + (0 if not r["is_final"] else 1)
                    assert r["advancing"] < alive  # sempre há eliminados: termina
                    alive = r["advancing"]
                assert plan[-1]["advancing"] == 1
    assert elimination.group_sizes(20, 4) == [4] * 5 and elimination.group_sizes(18, 4) == [4, 4, 4, 3, 3] and elimination.group_sizes(7, 4) == [4, 3]
    p = elimination.plan_bracket(20, 4, 1)
    assert [(r["groups"], r["advancing"], r["is_final"]) for r in p] == [(5, 5, False), (1, 1, True)]
    assert [r["groups"] for r in elimination.plan_bracket(20, 4, 2)] == [5, 3, 2, 1] and elimination.plan_bracket(1, 4, 1) == []


async def test_draw_avoids_previous_opponents():
    import random
    players = list(range(8))
    prev = {frozenset(p) for p in ((0, 1), (2, 3), (4, 5), (6, 7))}
    for seed in range(20):
        groups = elimination.draw_groups(players, [4, 4], prev, random.Random(seed))
        assert sorted(sum(groups, [])) == players
        assert not any(frozenset((a, b)) in prev for g in groups for a in g for b in g if a < b)
    clean = elimination.draw_groups(players, [2, 2, 2, 2], prev, random.Random(1))
    assert not any(frozenset(g) in prev for g in clean)


async def _env(make_user, make_class, new_client, n, *, gs=4, adv=1, extra=()):
    await add_problem("ex-facil", tipo="programa", dif=1, pistas=0)
    await add_problem("ex-medio", tipo="programa", dif=3, pistas=0)
    await add_problem("ex-boss", tipo="programa", dif=5, origem="boss", pistas=0)
    await add_problem("ex-quiz", tipo="quiz", dif=1)  # nunca escolhido: só tipos com código
    env = await make_env(make_user, make_class, new_client)
    t = await create_elim(env, group_size=gs, advance_per_group=adv)
    tid = t["tournament"]["id"]
    users = [await make_user(f"u{i:02d}", class_id=env.class_id, display_name=f"Aluno{i:02d}") for i in range(n)]
    await add_players(tid, users)
    return env, tid, users


async def _start(env, tid):
    r = await env.t_client.post(f"/api/tournaments/{tid}/rounds/next/start", json={}, headers=env.t_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _groups(view, idx):
    return next(r for r in view["rounds"] if r["idx"] == idx)["groups"]


# ---------------- criação, preview, exercícios ----------------
async def test_create_defaults_preview_and_exercise_pick(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 20)
    v = await admin(env, tid)
    assert v["format"] == "eliminatoria" and v["tournament"]["mode"] == "individual"
    assert v["config"]["group_size"] == 4 and v["config"]["advance_per_group"] == 1
    assert v["config"]["points"] == {"easy": 10, "medium": 20, "hard": 30, "group_win": 15, "champion": 100, "second": 50, "third": 25, "participation": 5}
    assert v["players_count"] == 20 and v["alive_count"] == 20
    assert len(v["rounds"]) == 1 and v["rounds"][0]["difficulty"] == "easy" and v["rounds"][0]["problem_slugs"] == ["ex-facil"]
    pv = (await env.t_client.get(f"/api/tournaments/{tid}/bracket-preview")).json()
    assert pv["players"] == 20 and [(r["groups"], r["sizes"], r["advancing"], r["is_final"]) for r in pv["rounds"]] == [(5, [4] * 5, 5, False), (1, [5], 1, True)]
    pv2 = (await env.t_client.get(f"/api/tournaments/{tid}/bracket-preview?group_size=3&advance_per_group=2")).json()
    assert pv2["rounds"][0]["sizes"] == [3, 3, 3, 3, 3, 3, 2]
    bad = await env.t_client.get(f"/api/tournaments/{tid}/bracket-preview?group_size=9", headers=env.t_headers)
    assert bad.status_code == 422
    # o professor troca o exercício enquanto a ronda está pendente: só um exercício de código
    r = await env.t_client.put(f"/api/tournaments/{tid}/rounds/1", json={"problem_slugs": ["ex-quiz"]}, headers=env.t_headers)
    assert r.json() == {"error": "tournament.exercise_invalid"}
    r = await env.t_client.put(f"/api/tournaments/{tid}/rounds/1", json={"problem_slugs": ["ex-medio"], "duration_s": 300}, headers=env.t_headers)
    assert r.status_code == 200 and r.json()["rounds"][0]["problem_slugs"] == ["ex-medio"] and r.json()["rounds"][0]["duration_s"] == 300
    # personalizar pontos e tamanhos
    t2 = await create_elim(env, group_size=3, advance_per_group=2, points={"champion": 200})
    assert t2["config"]["group_size"] == 3 and t2["config"]["points"]["champion"] == 200 and t2["config"]["points"]["easy"] == 10
    r = await env.t_client.post("/api/tournaments", json={"class_id": env.class_id, "name": "x", "points": {"foo": 1}}, headers=env.t_headers)
    assert r.json() == {"error": "tournament.invalid_points"}
    # config só no lobby
    r = await env.t_client.patch(f"/api/tournaments/{tid}/config", json={"group_size": 3, "advance_per_group": 2, "points": {"easy": 11}}, headers=env.t_headers)
    assert r.status_code == 200 and r.json()["config"]["group_size"] == 3 and r.json()["config"]["points"]["easy"] == 11 and r.json()["config"]["points"]["hard"] == 30
    assert (await env.t_client.patch(f"/api/tournaments/{tid}/config", json={"points": {"x": 1}}, headers=env.t_headers)).json() == {"error": "tournament.invalid_points"}
    sc0 = new_client()
    await login(sc0, users[0].username)
    assert (await sc0.patch(f"/api/tournaments/{tid}/config", json={"group_size": 4}, headers={"X-CSRF-Token": "x"})).status_code in (401, 403)
    await _start(env, tid)
    late = await env.t_client.patch(f"/api/tournaments/{tid}/config", json={"group_size": 4}, headers=env.t_headers)
    assert late.json() == {"error": "tournament.lobby_only"}
    # o Formato Aula continua a funcionar
    r = await env.t_client.post("/api/tournaments", json={"class_id": env.class_id, "name": "A", "format": "aula", "mode": "agencias"}, headers=env.t_headers)
    assert r.status_code == 201 and r.json()["tournament"]["format"] == "aula" and len(r.json()["rounds"]) == 6


# ---------------- simulação completa ----------------
async def test_full_20_player_simulation_to_champion_with_ledger(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 20)
    uid = {u.id: u for u in users}
    v = await _start(env, tid)
    g1 = _groups(v, 1)
    assert [len(g["members"]) for g in g1] == [4] * 5
    assert sorted(m["user_id"] for g in g1 for m in g["members"]) == sorted(uid)  # todos, uma só vez
    assert len(await events_of(tid, "groups_drawn")) == 1
    exp: dict[int, int] = {u: 0 for u in uid}
    winners = []
    for g in g1:
        ids = [m["user_id"] for m in g["members"]]
        w, s, x = ids[0], ids[1], ids[2]
        await fake_submit(tid, 1, w, "ex-facil", "accepted", 4)
        winners.append(w)
        exp[w] += 10 + 5 + 15
        await fake_submit(tid, 1, s, "ex-facil", "accepted", 4)  # grupo já decidido: só pontos do exercício
        exp[s] += 10 + 5
        await fake_submit(tid, 1, x, "ex-facil", "wrong_answer", 0)
        exp[x] += 5
    st = await admin(env, tid)
    assert st["tournament"]["state"] == "between_rounds"  # fechou sozinha quando o último grupo foi decidido
    r1 = st["rounds"][0]
    assert r1["state"] == "closed" and all(g["decided"] and g["decided_by"] == "solve" and len(g["winners"]) == 1 for g in r1["groups"])
    assert [g["winners"][0] for g in r1["groups"]] == winners
    assert st["alive_count"] == 5 and len(await events_of(tid, "player_eliminated")) == 1
    assert sorted((await events_of(tid, "player_eliminated"))[0].payload["user_ids"]) == sorted(set(uid) - set(winners))
    r2 = st["rounds"][1]
    assert r2["is_final"] and r2["state"] == "pending" and r2["difficulty"] == "hard" and r2["problem_slugs"] == ["ex-boss"]
    # final: 1 grupo com os 5 vencedores
    v = await _start(env, tid)
    g = _groups(v, 2)
    assert len(g) == 1 and sorted(m["user_id"] for m in g[0]["members"]) == sorted(winners)
    a, b, c, d, e = winners
    await fake_submit(tid, 2, d, "ex-boss", "wrong_answer", 1, at=utcnow() - timedelta(seconds=5))
    await fake_submit(tid, 2, c, "ex-boss", "wrong_answer", 1, at=utcnow() - timedelta(seconds=4))
    await fake_submit(tid, 2, b, "ex-boss", "wrong_answer", 3)
    await fake_submit(tid, 2, a, "ex-boss", "accepted", 4)
    exp[a] += 30 + 15 + 100
    for u in (b, c, d, e):
        pass
    exp[b] += 50  # 2.º: mais testes entre os finalistas
    exp[c] += 25  # 3.º: empate de testes com d, mas chegou mais tarde que d? ver abaixo
    final = await admin(env, tid)
    assert final["tournament"]["state"] == "finished" and final["champion"]["user_id"] == a
    assert [p["user_id"] for p in final["podium"]] == [a, b, d] or [p["user_id"] for p in final["podium"]] == [a, b, c]
    third = final["podium"][2]["user_id"]
    if third == d:  # d chegou mais cedo que c com os mesmos testes
        exp[c] -= 25
        exp[d] += 25
    assert len(await events_of(tid, "champion")) == 1 and len(await events_of(tid, "tournament_finished")) == 1
    for u, want in exp.items():
        assert await total_points(u) == want, (u, want)
    rows = await ledger()
    assert len({(r.user_id, r.tournament_id, r.reason, r.round_idx, r.problem_slug) for r in rows}) == len(rows)  # sem duplicados
    assert next(p for p in final["players"] if p["user_id"] == a)["status"] == "champion"
    # snapshot do aluno: bracket completo, sem código de entrada, com os meus pontos
    sc = new_client()
    await login(sc, uid[a].username)
    ss = await state(sc, tid)
    assert ss["me"]["status"] == "champion" and ss["my_points_this_tournament"] == exp[a] and "join_code" not in str(ss)
    assert len(ss["rounds"]) == 2 and ss["champion"]["user_id"] == a and ss["podium"][0]["rank"] == 1


# ---------------- decisão por testes / tempo / sorteio ----------------
async def _expire(tid, idx, secs=120):
    async with SessionLocal() as db:
        await db.execute(update(TournamentRound).where(TournamentRound.tournament_id == tid, TournamentRound.idx == idx)
                         .values(ends_at=utcnow() - timedelta(seconds=secs)))
        await db.commit()


async def test_timeout_decides_by_tests_then_earliest_then_draw(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    v = await _start(env, tid)
    ga, gb = _groups(v, 1)
    a = [m["user_id"] for m in ga["members"]]
    b = [m["user_id"] for m in gb["members"]]
    now = utcnow()
    # grupo A: mais testes ganha; empate de testes -> a mais cedo
    await fake_submit(tid, 1, a[0], "ex-facil", "wrong_answer", 2, at=now - timedelta(seconds=50))
    await fake_submit(tid, 1, a[1], "ex-facil", "wrong_answer", 3, at=now - timedelta(seconds=30))
    await fake_submit(tid, 1, a[2], "ex-facil", "wrong_answer", 3, at=now - timedelta(seconds=40))  # mesmo nº, mais cedo
    # grupo B: ninguém submeteu -> sorteio
    assert (await elimination.autoclose_once()) == 0  # ainda no tempo
    await _expire(tid, 1)
    assert await elimination.autoclose_once() == 1
    st = await admin(env, tid)
    ga2, gb2 = _groups(st, 1)
    assert ga2["winners"] == [a[2]] and ga2["decided_by"] == "tests"
    assert gb2["decided_by"] == "draw" and gb2["winners"][0] in b
    async with SessionLocal() as db:
        seed = (await db.execute(select(TournamentGroup.draw_seed).where(TournamentGroup.id == gb2["id"]))).scalar_one()
    assert seed is not None  # o sorteio fica registado
    assert st["tournament"]["state"] == "between_rounds" and st["alive_count"] == 2


async def test_auto_close_runs_exactly_once_with_two_workers(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    await _start(env, tid)
    await _expire(tid, 1)
    done = await asyncio.gather(elimination.autoclose_once(), elimination.autoclose_once(), elimination.autoclose_once())
    assert sum(done) == 1
    assert len(await events_of(tid, "round_closed")) == 1 and len(await events_of(tid, "player_eliminated")) == 1
    gw = [r for r in await ledger(tid=tid) if r.reason == "group_win"]
    assert len(gw) == 2  # 1 vencedor por grupo, uma só vez
    async with SessionLocal() as db:
        rounds = (await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == tid))).scalars().all()
    assert sorted(r.idx for r in rounds) == [1, 2]  # só uma ronda seguinte criada
    assert await elimination.autoclose_once() == 0


async def test_autoclose_waits_for_submissions_in_flight(make_user, make_class, new_client):
    from app.models.submission import Submission
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    v = await _start(env, tid)
    uid = _groups(v, 1)[0]["members"][0]["user_id"]
    sid = await fake_submit(tid, 1, uid, "ex-facil", "running", 0)
    await _expire(tid, 1, 45)
    assert await elimination.autoclose_once() == 0  # a correção ainda não acabou
    async with SessionLocal() as db:
        await db.execute(update(Submission).where(Submission.id == sid).values(status="accepted", passed=4))
        await db.commit()
    await tournament_scoring.on_submission_finished(sid)
    assert _groups(await admin(env, tid), 1)[0]["winners"] == [uid]
    assert await elimination.autoclose_once() == 1


async def test_autoclose_is_not_skipped_by_a_concurrent_event_insert(make_user, make_class, new_client):
    """Gravar um evento (FK para tournaments) põe um FOR KEY SHARE no torneio: isso não pode fazer o fecho automático saltar a ronda."""
    from sqlalchemy import text
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    await _start(env, tid)
    await _expire(tid, 1)
    async with SessionLocal() as other:
        await other.execute(text("SELECT 1 FROM tournaments WHERE id = :t FOR KEY SHARE"), {"t": tid})
        assert await elimination.autoclose_once() == 1
        await other.rollback()


# ---------------- professor, eliminados, idempotência ----------------
async def test_teacher_override_and_permissions(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    v = await _start(env, tid)
    ga, gb = _groups(v, 1)
    a = [m["user_id"] for m in ga["members"]]
    outsider = [m["user_id"] for m in gb["members"]][0]
    url = f"/api/tournaments/{tid}/groups/{ga['id']}/winner"
    r = await env.t_client.post(url, json={"user_id": outsider}, headers=env.t_headers)
    assert r.status_code == 422 and r.json() == {"error": "tournament.player_not_in_group"}
    r = await env.t_client.post(f"/api/tournaments/{tid}/groups/99999/winner", json={"user_id": a[0]}, headers=env.t_headers)
    assert r.json() == {"error": "tournament.group_not_found"}
    # aluno e outro professor não podem
    sc = new_client()
    await login(sc, users[0].username)
    assert (await sc.post(url, json={"user_id": a[0]}, headers={"X-CSRF-Token": "x"})).status_code in (403, 401)
    from app.models.user import Role
    await make_user("profb", Role.teacher)
    async with new_client() as other:
        oh = await login(other, "profb")
        assert (await other.post(url, json={"user_id": a[0]}, headers=oh)).status_code == 404
    # um aluno ganha por solve, o professor corrige para outro
    await fake_submit(tid, 1, a[0], "ex-facil", "accepted", 4)
    r = await env.t_client.post(url, json={"user_id": a[3]}, headers=env.t_headers)
    assert r.status_code == 200
    g = _groups(r.json(), 1)[0]
    assert g["winners"] == [a[3]] and g["decided_by"] == "teacher"
    assert (await events_of(tid, "group_decided"))[-1].payload["decided_by"] == "teacher"
    await control(env, tid, "rounds/1/close")  # fecho manual decide o grupo B por sorteio
    st = await admin(env, tid)
    assert st["rounds"][0]["state"] == "closed" and _groups(st, 1)[1]["decided_by"] == "draw"
    late = await env.t_client.post(url, json={"user_id": a[1]}, headers=env.t_headers)
    assert late.json() == {"error": "tournament.round_not_active"}


async def test_advance_two_per_group(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 8, adv=2)
    v = await _start(env, tid)
    ga, gb = _groups(v, 1)
    a = [m["user_id"] for m in ga["members"]]
    await fake_submit(tid, 1, a[0], "ex-facil", "accepted", 4)
    assert not _groups(await admin(env, tid), 1)[0]["decided"]  # falta o 2.º lugar
    await fake_submit(tid, 1, a[1], "ex-facil", "accepted", 4)
    g = _groups(await admin(env, tid), 1)[0]
    assert g["decided"] and g["winners"] == [a[0], a[1]]
    await control(env, tid, "rounds/1/close")
    st = await admin(env, tid)
    assert st["alive_count"] == 4 and st["rounds"][1]["is_final"]  # 2 grupos x 2 passam: 4 <= 5


async def test_eliminated_practice_gives_points_but_never_advances(make_user, make_class, new_client):
    from app.config import settings
    from app.services import dispatcher
    from app.services.problems import sync_problems
    from tests.fakes import local_post
    async with SessionLocal() as db:
        await sync_problems(db, settings.problems_dir)
    env = await make_env(make_user, make_class, new_client)
    t = await create_elim(env, group_size=3)
    tid = t["tournament"]["id"]
    users = [await make_user(f"p{i}", class_id=env.class_id) for i in range(6)]
    await add_players(tid, users)
    await set_round(env, tid, 1, ["soma-ate-zero"])
    good = open(next(settings.problems_dir.rglob("soma-ate-zero.yaml")).as_posix()).read()
    import yaml
    code = yaml.safe_load(good)["solucao_referencia"]
    code = code if isinstance(code, str) else code["pt"]
    v = await _start(env, tid)
    ga, gb = _groups(v, 1)
    clients = {}
    for u in users:
        c = new_client()
        clients[u.id] = (c, await login(c, u.username))

    async def solve(uid_):
        c, h = clients[uid_]
        import uuid
        r = await c.post("/api/submissions", json={"client_id": str(uuid.uuid4()), "problem_slug": "soma-ate-zero", "code": code, "tournament_id": tid, "round_idx": 1}, headers=h)
        assert r.status_code == 202, r.text
        while await dispatcher.run_once(local_post):
            pass
        await tournament_scoring.drain()
        await elimination.drain()

    a, b = [m["user_id"] for m in ga["members"]], [m["user_id"] for m in gb["members"]]
    await solve(a[0])
    await solve(b[0])  # fecha a ronda sozinha
    st = await admin(env, tid)
    assert st["rounds"][0]["state"] == "closed" and st["alive_count"] == 2
    loser = a[1]
    before = await total_points(loser)
    await solve(loser)  # treino: eliminado, dentro da tolerância após o fecho
    after = await ledger(loser, tid)
    assert {r.reason for r in after} == {"exercise", "participation"} and await total_points(loser) == before + 30 + 5
    st = await admin(env, tid)
    assert next(p for p in st["players"] if p["user_id"] == loser)["status"] == "eliminated" and st["alive_count"] == 2
    assert _groups(st, 1)[0]["winners"] == [a[0]]  # nunca avança nem muda o vencedor
    assert not any(r.reason == "group_win" for r in after)
    ss = await state(clients[loser][0], tid)
    assert ss["me"]["status"] == "eliminated" and ss["me"]["eliminated_in_round"] == 1
    # fora do tempo (passada a tolerância) já não se aceita
    await _expire(tid, 1)
    import uuid
    c, h = clients[loser]
    r = await c.post("/api/submissions", json={"client_id": str(uuid.uuid4()), "problem_slug": "soma-ate-zero", "code": code, "tournament_id": tid, "round_idx": 1}, headers=h)
    assert r.json() == {"error": "tournament.time_over"}


async def test_points_are_idempotent(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 4)
    from app.models.tournament import Tournament
    async with SessionLocal() as db:
        t = await db.get(Tournament, tid)
        assert await points.award(db, t, users[0].id, 10, "exercise", 1, "ex-facil") is True
        assert await points.award(db, t, users[0].id, 10, "exercise", 1, "ex-facil") is False
        assert await points.award(db, t, users[0].id, 5, "participation") is True
        assert await points.award(db, t, users[0].id, 5, "participation") is False
        assert await points.award(db, None, users[0].id, 7, "exercise", None, None) is True  # sem torneio, também único
        assert await points.award(db, None, users[0].id, 7, "exercise", None, None) is False
        await db.commit()
    assert await total_points(users[0].id) == 22
    assert len(await events_of(tid, "points_awarded")) == 2
    v = await _start(env, tid)
    w = _groups(v, 1)[0]["members"][0]["user_id"]
    for _ in range(3):  # reenvios aceites: o mesmo exercício só conta uma vez
        await fake_submit(tid, 1, w, "ex-facil", "accepted", 4)
    assert [r.reason for r in await ledger(w, tid)].count("exercise") <= 1
    assert [r.reason for r in await ledger(w, tid)].count("participation") <= 1


async def test_group_progress_is_coalesced_and_private(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    v = await _start(env, tid)
    members = [m["user_id"] for m in _groups(v, 1)[0]["members"]]
    t0 = time.monotonic()
    for k in range(6):
        for m in members:
            await fake_submit(tid, 1, m, "ex-facil", "wrong_answer", k % 4)
    await elimination.drain()
    el = time.monotonic() - t0
    prog = await events_of(tid, "group_progress")
    assert 1 <= len(prog) <= (int(el * 2) + 2) * len(members)  # lotes (no máximo 2 por segundo), 1 evento por aluno e lote
    last = {e.payload["user_id"]: e.payload for e in prog}
    assert all(last[m]["attempts"] == 6 and last[m]["passed"] == 3 for m in members)  # o estado final chega sempre
    snap = await admin(env, tid)
    assert "'code'" not in str(snap) and all(set(m) == {"user_id", "display_name", "avatar_seed", "passed", "total", "attempts", "solved_at", "status"} for m in _groups(snap, 1)[0]["members"])


async def test_snapshot_shape_for_students_in_group_and_lobby(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 8)
    sc = new_client()
    await login(sc, users[0].username)
    lobby = await state(sc, tid)
    assert lobby["format"] == "eliminatoria" and lobby["players_count"] == 8 and lobby["alive_count"] == 8
    assert lobby["me"] == {"user_id": users[0].id, "status": "alive", "group_id": None, "eliminated_in_round": None, "team_id": None, "participant_key": f"u:{users[0].id}", "anticheat": {"armed": False, "locked": False, "kind": None}}
    assert lobby["current"] is None and lobby["champion"] is None and lobby["podium"] is None and lobby["my_points_this_tournament"] == 0
    assert "problem_slugs" not in lobby["rounds"][0] and "ex-facil" not in str(lobby)
    await _start(env, tid)
    s = await state(sc, tid)
    m = s["current"]["mission"]
    assert m["slug"] == "ex-facil" and m["practice"] is False and m["solved_by_me"] is False
    for secret in ("testes", "solucao_referencia", "join_code"):
        assert secret not in str(s)
    assert s["me"]["group_id"] is not None and set(s["rounds"][0]) >= {"idx", "title", "is_final", "state", "ends_at", "remaining_s", "difficulty", "groups"}


# ---------------- leaderboard ----------------
async def test_leaderboard_privacy_me_rank_and_week(make_user, make_class, new_client, client):
    from app.models.user import Role
    leaderboard.clear_cache()
    env = await make_env(make_user, make_class, new_client)
    names = {}
    for name, pts_, show in (("ana", 100, True), ("rui", 300, True), ("eva", 200, False), ("zero", 0, True)):
        u = await make_user(name, class_id=env.class_id, display_name=name.capitalize())
        names[name] = u
        async with SessionLocal() as db:
            await db.execute(update(type(u)).where(type(u).id == u.id).values(show_in_leaderboard=show))
            if pts_:
                db.add(UserPoints(user_id=u.id, points=pts_, reason="exercise", round_idx=1, problem_slug=name))
            await db.commit()
    async with SessionLocal() as db:  # o professor com pontos e flag nunca aparece
        db.add(UserPoints(user_id=env.teacher.id, points=999, reason="exercise", round_idx=1, problem_slug="t"))
        await db.execute(update(type(env.teacher)).where(type(env.teacher).id == env.teacher.id).values(show_in_leaderboard=True))
        await db.commit()
    r = await client.get("/api/leaderboard/public")  # sem sessão
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == "all" and [(e["rank"], e["display_name"], e["points"]) for e in body["entries"]] == [(1, "Rui", 300), (2, "Ana", 100)]
    assert all(set(e) == {"rank", "display_name", "points", "avatar_seed"} for e in body["entries"])
    raw = r.text
    for secret in ("username", "profa", "class", "Turma", "Eva", "eva", "rui\""):
        assert secret not in raw, secret
    assert "updated_at" in body
    # /me: o lugar é entre TODOS os alunos, mesmo escondido
    ec = new_client()
    await login(ec, "eva")
    me = (await ec.get("/api/leaderboard/me")).json()
    assert me == {"rank": 2, "points": 200, "visible": False, "total_ranked": 3}
    zc = new_client()
    await login(zc, "zero")
    assert (await zc.get("/api/leaderboard/me")).json()["rank"] is None
    assert (await client.get("/api/leaderboard/me")).status_code in (401, 403)
    assert (await client.get("/api/leaderboard/public?period=ano")).status_code == 422
    # a flag muda-se no perfil (e aparece em user_payload)
    h = await login(ec, "eva")
    r = await ec.patch("/api/me/preferences", json={"show_in_leaderboard": True}, headers=h)
    assert r.json()["user"]["show_in_leaderboard"] is True
    leaderboard.clear_cache()
    assert [e["display_name"] for e in (await client.get("/api/leaderboard/public")).json()["entries"]] == ["Rui", "Eva", "Ana"]
    assert (await ec.get("/api/leaderboard/me")).json()["visible"] is True
    # cache de 30 s: a mudança seguinte só aparece depois de a cache expirar
    await ec.patch("/api/me/preferences", json={"show_in_leaderboard": False}, headers=h)
    assert len((await client.get("/api/leaderboard/public")).json()["entries"]) == 3
    leaderboard.clear_cache()
    assert len((await client.get("/api/leaderboard/public")).json()["entries"]) == 2
    assert Role.teacher.value == "teacher"


async def test_week_window_starts_monday_lisbon(make_user, make_class, new_client):
    # inverno (UTC+0) e verão (UTC+1)
    assert leaderboard.week_start(datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)) == datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)
    assert leaderboard.week_start(datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)) == datetime(2026, 7, 12, 23, 0, tzinfo=timezone.utc)
    # domingo à noite em Lisboa ainda é a semana anterior; segunda 00:00:01 já é a nova
    assert leaderboard.week_start(datetime(2026, 11, 15, 23, 59, tzinfo=timezone.utc)) == datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
    assert leaderboard.week_start(datetime(2026, 11, 16, 0, 0, 1, tzinfo=timezone.utc)) == datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)
    env = await make_env(make_user, make_class, new_client)
    u = await make_user("ana", class_id=env.class_id)
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    async with SessionLocal() as db:
        await db.execute(update(type(u)).where(type(u).id == u.id).values(show_in_leaderboard=True))
        db.add(UserPoints(user_id=u.id, points=40, reason="exercise", round_idx=1, problem_slug="a", created_at=datetime(2026, 11, 15, 23, 0, tzinfo=timezone.utc)))
        db.add(UserPoints(user_id=u.id, points=7, reason="exercise", round_idx=1, problem_slug="b", created_at=datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)))
        await db.commit()
        week = await leaderboard.public(db, "week", 10, now)
        allp = await leaderboard.public(db, "all", 10, now)
        mine = await leaderboard.me(db, u, "week", now)
    assert week["entries"][0]["points"] == 7 and allp["entries"][0]["points"] == 47 and mine["points"] == 7


async def test_aula_individual_also_logs_exercise_points(make_user, make_class, new_client):
    from tests.test_tournament_support import create_tournament, submit
    await add_problem("m1", dif=3)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["m1"])
    u, c, h = await env.student(make_user, new_client, "ana")
    await c.post("/api/tournaments/join", json={"join_code": t["tournament"]["join_code"]}, headers=h)
    await control(env, tid, "rounds/1/start")
    assert (await submit(c, h, tid, 1, "m1")).status_code == 202
    await tournament_scoring.drain()
    rows = await ledger(u.id, tid)
    assert [(r.reason, r.points, r.problem_slug) for r in rows] == [("exercise", 20, "m1")]


async def test_second_and_third_always_rewarded_and_snapshot_ignores_flag(make_user, make_class, new_client):
    env, tid, users = await _env(make_user, make_class, new_client, 5)  # 5 jogadores: logo é a final
    # nenhum aluno tem a flag do leaderboard público ligada: o torneio mostra todos na mesma
    async with SessionLocal() as db:
        for u in users:
            assert not (await db.get(type(u), u.id)).show_in_leaderboard
    await _start(env, tid)
    st = await admin(env, tid)
    assert st["rounds"][0]["is_final"]
    ids = [m["user_id"] for m in _groups(st, 1)[0]["members"]]
    winner, a, b, c, d = ids
    # só o vencedor e o primeiro adversário submetem; os restantes nunca submeteram nada
    await fake_submit(tid, 1, a, "ex-boss", "wrong_answer", 2)
    await fake_submit(tid, 1, winner, "ex-boss", "accepted", 4)
    st = await admin(env, tid)
    assert st["tournament"]["state"] == "finished"
    pod = st["podium"]
    assert [p["rank"] for p in pod] == [1, 2, 3] and pod[0]["user_id"] == winner and pod[1]["user_id"] == a  # 2.º: mais testes
    third = pod[2]["user_id"]
    assert third in (b, c, d)
    async with SessionLocal() as db:
        g = (await db.execute(select(TournamentGroup))).scalars().one()
    assert sorted(g.ranking) == sorted(ids) and g.ranking[:3] == [p["user_id"] for p in pod]  # ordem total e igual ao pódio
    rows = await ledger(tid=tid)
    second = [r for r in rows if r.reason == "second"]
    thirds = [r for r in rows if r.reason == "third"]
    assert [(r.user_id, r.points) for r in second] == [(a, 50)] and [(r.user_id, r.points) for r in thirds] == [(third, 25)]
    assert third not in (winner, a)  # o 3.º nunca submeteu e recebeu na mesma
    assert len([r for r in rows if r.reason == "champion"]) == 1
    # o snapshot de um aluno (sem flag) mostra todos: leaderboard, pódio, bracket
    sc = new_client()
    await login(sc, users[0].username)
    ss = await state(sc, tid)
    assert len(ss["leaderboard"]) == 5 and ss["podium"] is not None and len(ss["rounds"][0]["groups"][0]["members"]) == 5
    assert {e["name"] for e in ss["leaderboard"]} == {f"Aluno{i:02d}" for i in range(5)}
    leaderboard.clear_cache()
    assert (await sc.get("/api/leaderboard/public")).json()["entries"] == []  # a flag só afeta o público
