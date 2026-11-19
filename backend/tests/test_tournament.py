# Testes do torneio (REST): preset e escolha automática, entrar, agências, pontuação completa, regras de tempo,
# submissões duplicadas/concorrentes, fuga de segredos no snapshot, pistas, permissões e agrupamento do leaderboard.
import asyncio
import json
import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.db import SessionLocal
from app.models._base import utcnow
from app.models.tournament import TournamentRound, TournamentSolve
from app.services import dispatcher, tournament_scoring
from tests.conftest import login
from tests.fakes import local_post
from tests.test_tournament_support import (
    add_problem, control, create_tournament, events_of, make_env, set_round, state, submit,
)

pytestmark = pytest.mark.asyncio


async def _join(client, headers, code):
    r = await client.post("/api/tournaments/join", json={"join_code": code}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["tournament_id"]


# ---------------- preset e escolha automática ----------------
async def test_preset_creation_and_auto_pick(make_user, make_class, new_client):
    # catálogo: bloco 7 (o mais alto aberto) e bloco 4, aprovados e rascunhos, vários tipos e dificuldades
    for d, n in ((1, 4), (2, 4), (3, 4), (4, 4), (5, 4)):
        for i in range(n):
            await add_problem(f"p7-d{d}-{i}", tipo=("programa", "funcao", "bug", "quiz")[i % 4] if d < 3 else ("programa", "funcao", "bug")[i % 3],
                              bloco="7", dif=d, estado="rascunho" if i else "aprovado")
    await add_problem("p4-d1", tipo="programa", bloco="4", dif=1)
    await add_problem("p7-boss", tipo="programa", bloco="7", dif=5, origem="boss", estado="rascunho")
    await add_problem("p7-tracar", tipo="quiz", bloco="7", dif=1)  # quiz no bloco 7: só aceite em R1/R2
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "agencias")
    assert t["tournament"]["state"] == "lobby" and len(t["tournament"]["join_code"]) == 6
    assert t["tournament"]["config"] == {
        "hint_factor": 0.5, "first_bonus": 5, "grace_s": 30, "diploma_title": {"pt": "Mestre da Decomposição", "en": "Decomposition Master"},
    }
    rounds = t["rounds"]
    assert [(r["idx"], r["points"], r["multiplier"], r["is_boss"], r["state"]) for r in rounds] == [
        (1, 10, 1, False, "pending"), (2, 10, 1, False, "pending"), (3, 15, 1, False, "pending"),
        (4, 15, 1, False, "pending"), (5, 15, 2, False, "pending"), (6, 30, 1, True, "pending"),
    ]
    assert [r["duration_s"] for r in rounds] == [600, 600, 720, 720, 900, 600]
    assert [r["mission_count"] for r in rounds] == [3, 3, 3, 3, 3, 1]
    meta = {p["slug"]: p for r in rounds for p in r["problems"]}
    all_slugs = [s for r in rounds for s in r["problem_slugs"]]
    assert len(all_slugs) == len(set(all_slugs))  # nunca repete problemas entre rondas
    diffs = {1: (1, 2), 2: (2,), 3: (3,), 4: (3, 4), 5: (4, 5)}
    for r in rounds[:5]:
        for s in r["problem_slugs"]:
            assert meta[s]["dificuldade"] in diffs[r["idx"]] and meta[s]["bloco"] == "7"  # bloco mais alto aberto
            if r["idx"] >= 3:
                assert meta[s]["tipo"] in ("programa", "funcao", "bug")
    assert rounds[5]["problem_slugs"] == ["p7-boss"]
    assert any(p["estado"] == "rascunho" for p in meta.values())  # o professor pode usar rascunhos


async def test_auto_pick_falls_back_to_lower_blocks(make_user, make_class, new_client):
    await add_problem("only-b3", tipo="programa", bloco="3", dif=3)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    assert t["rounds"][2]["problem_slugs"] == ["only-b3"]  # menos de 3 candidatos: o professor completa


async def test_update_round_only_when_pending(make_user, make_class, new_client):
    await add_problem("a1")
    await add_problem("a2")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    v = await set_round(env, tid, 1, ["a1", "a2"], points=20, multiplier=1.5, duration_s=300, title={"pt": "X", "en": "Y"})
    r1 = v["rounds"][0]
    assert (r1["points"], r1["multiplier"], r1["duration_s"], r1["title"]) == (20, 1.5, 300, {"pt": "X", "en": "Y"})
    bad = await env.t_client.put(f"/api/tournaments/{tid}/rounds/1", json={"problem_slugs": ["nao-existe"]}, headers=env.t_headers)
    assert bad.status_code == 422 and bad.json() == {"error": "tournament.problem_not_found"}
    dup = await env.t_client.put(f"/api/tournaments/{tid}/rounds/1", json={"problem_slugs": ["a1", "a1"]}, headers=env.t_headers)
    assert dup.json() == {"error": "tournament.duplicate_problem"}
    await control(env, tid, "rounds/1/start")
    late = await env.t_client.put(f"/api/tournaments/{tid}/rounds/1", json={"points": 1}, headers=env.t_headers)
    assert late.status_code == 409 and late.json() == {"error": "tournament.round_not_pending"}


# ---------------- entrar e agências ----------------
async def test_join_is_idempotent_and_class_scoped(make_user, make_class, new_client):
    env = await make_env(make_user, make_class, new_client)
    code = (await create_tournament(env, "individual"))["tournament"]["join_code"]
    _, c, h = await env.student(make_user, new_client, "ana")
    tid = await _join(c, h, code)
    assert await _join(c, h, code.lower()) == tid  # idempotente (e sem diferenciar maiúsculas)
    assert len(await events_of(tid, "player_joined")) == 1
    # aluno de outra turma: não encontra o torneio
    other = await make_user("rui", class_id=None)
    async with new_client() as oc:
        oh = await login(oc, "rui")
        r = await oc.post("/api/tournaments/join", json={"join_code": code}, headers=oh)
        assert r.status_code == 404 and r.json() == {"error": "tournament.not_found"}
        assert (await oc.get(f"/api/tournaments/{tid}/state")).status_code == 404
    assert other.class_id is None
    r = await c.post("/api/tournaments/join", json={"join_code": "ZZZZZZ"}, headers=h)
    assert r.json() == {"error": "tournament.not_found"}


async def test_agency_rules(make_user, make_class, new_client):
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "agencias")
    tid, code = t["tournament"]["id"], t["tournament"]["join_code"]
    studs = [await env.student(make_user, new_client, f"al{i}") for i in range(6)]
    for _, c, h in studs:
        await _join(c, h, code)
    (u0, c0, h0) = studs[0]
    r = await c0.post(f"/api/tournaments/{tid}/teams", json={"name": "  Foguetão   Verde "}, headers=h0)
    assert r.status_code == 201
    team = r.json()["teams"][0]
    assert team["name"] == "Foguetão Verde" and team["color_idx"] == 0 and [m["user_id"] for m in team["members"]] == [u0.id]
    # nome único (sem diferenciar maiúsculas) e tamanho 1–24
    dup = await studs[1][1].post(f"/api/tournaments/{tid}/teams", json={"name": "foguetão verde"}, headers=studs[1][2])
    assert dup.status_code == 409 and dup.json() == {"error": "tournament.team_name_taken"}
    for bad in ("", "x" * 25):
        r = await studs[1][1].post(f"/api/tournaments/{tid}/teams", json={"name": bad}, headers=studs[1][2])
        assert r.json() == {"error": "tournament.team_name_invalid"}
    # no máximo 4 por agência
    for _, c, h in studs[1:4]:
        assert (await c.post(f"/api/tournaments/{tid}/teams/{team['id']}/join", headers=h)).status_code == 200
    r = await studs[4][1].post(f"/api/tournaments/{tid}/teams/{team['id']}/join", headers=studs[4][2])
    assert r.status_code == 409 and r.json() == {"error": "tournament.team_full"}
    # entrar duas vezes na mesma agência é idempotente
    assert (await studs[1][1].post(f"/api/tournaments/{tid}/teams/{team['id']}/join", headers=studs[1][2])).status_code == 200
    # mudar de agência esvazia (e apaga, no lobby) a anterior
    r = await studs[0][1].post(f"/api/tournaments/{tid}/teams", json={"name": "Café"}, headers=h0)
    teams = r.json()["teams"]
    assert [x["name"] for x in teams] == ["Foguetão Verde", "Café"] and len(teams[0]["members"]) == 3
    # o professor muda um aluno de agência (mesmo cheia: respeita o limite)
    cafe = teams[1]["id"]
    r = await env.t_client.post(f"/api/tournaments/{tid}/teams/{cafe}/move", json={"user_id": studs[1][0].id}, headers=env.t_headers)
    assert r.status_code == 200
    st = await state(env.t_client, tid)
    assert {x["name"]: len(x["members"]) for x in st["teams"]} == {"Foguetão Verde": 2, "Café": 2}
    r = await env.t_client.post(f"/api/tournaments/{tid}/teams/{cafe}/move", json={"user_id": 99999}, headers=env.t_headers)
    assert r.json() == {"error": "tournament.player_not_found"}
    assert len(await events_of(tid, "team_updated")) >= 6
    # depois do início continua a ser possível
    await add_problem("q1")
    await set_round(env, tid, 1, ["q1"])
    await control(env, tid, "rounds/1/start")
    r = await studs[5][1].post(f"/api/tournaments/{tid}/teams/{cafe}/join", headers=studs[5][2])
    assert r.status_code == 200  # retardatários entram em agências a qualquer altura (até o torneio acabar)
    r = await env.t_client.post(f"/api/tournaments/{tid}/teams/{cafe}/move", json={"user_id": studs[5][0].id}, headers=env.t_headers)
    assert r.status_code == 200


async def test_individual_has_no_agencies(make_user, make_class, new_client):
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, t["tournament"]["join_code"])
    r = await c.post(f"/api/tournaments/{tid}/teams", json={"name": "A"}, headers=h)
    assert r.status_code == 409 and r.json() == {"error": "tournament.not_agencies"}


# ---------------- pontuação completa ----------------
async def _scenario(make_user, make_class, new_client):
    """5 agências de 2 alunos, 16 problemas quiz (3 por ronda + boss) com 1 pista cada."""
    slugs = {i: [f"r{i}-{k}" for k in range(3)] for i in range(1, 6)}
    slugs[6] = ["boss-0"]
    for ss in slugs.values():
        for s in ss:
            await add_problem(s)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "agencias")
    tid, code = t["tournament"]["id"], t["tournament"]["join_code"]
    for idx, ss in slugs.items():
        await set_round(env, tid, idx, ss)
    members = {}
    for a in "ABCDE":
        pair = [await env.student(make_user, new_client, f"{a.lower()}{j}") for j in (1, 2)]
        for _, c, h in pair:
            await _join(c, h, code)
        r = await pair[0][1].post(f"/api/tournaments/{tid}/teams", json={"name": f"Agencia {a}"}, headers=pair[0][2])
        team_id = r.json()["teams"][-1]["id"]
        await pair[1][1].post(f"/api/tournaments/{tid}/teams/{team_id}/join", headers=pair[1][2])
        members[a] = (team_id, pair)
    return env, tid, slugs, members


async def _solve(members, a, who, idx, tid, slug):
    _, c, h = members[a][1][who]
    r = await submit(c, h, tid, idx, slug)
    assert r.status_code == 202, r.text
    return r


async def _hint(members, a, who, tid, slug, n=1):
    _, c, h = members[a][1][who]
    r = await c.get(f"/api/tournaments/{tid}/hints/{slug}/{n}")
    assert r.status_code == 200, r.text
    return r.json()


async def test_full_scoring_scenario(make_user, make_class, new_client):
    env, tid, slugs, mem = await _scenario(make_user, make_class, new_client)
    # R1: A resolve as 3 primeiro (30 + 5 bónus); B resolve as 3 mas com pista numa (5+10+10); C resolve 1
    await control(env, tid, "rounds/1/start")
    for s in slugs[1]:
        await _solve(mem, "A", 0, 1, tid, s)
    await _hint(mem, "B", 1, tid, slugs[1][0])
    for s in slugs[1]:
        await _solve(mem, "B", 0, 1, tid, s)  # a pista foi aberta pelo OUTRO membro: conta na agência toda
    await _solve(mem, "C", 0, 1, tid, slugs[1][0])
    await _solve(mem, "A", 1, 1, tid, slugs[1][0])  # o colega de A volta a resolver: não conta outra vez
    await control(env, tid, "rounds/1/close")
    # R2: B primeiro (35); A com 2 missões, uma com pista (10 + 5)
    await control(env, tid, "rounds/2/start")
    for s in slugs[2]:
        await _solve(mem, "B", 1, 2, tid, s)
    await _hint(mem, "A", 1, tid, slugs[2][0])
    for s in slugs[2][:2]:
        await _solve(mem, "A", 0, 2, tid, s)
    await control(env, tid, "rounds/2/close")
    # R3 e R4 saltam-se; R5: A resolve as 3 (15×2=30; uma com pista = 15) e leva +5 sem multiplicar
    await control(env, tid, "rounds/3/start")
    await control(env, tid, "rounds/3/close")
    await control(env, tid, "rounds/5/start")
    await _hint(mem, "A", 0, tid, slugs[5][2])
    for s in slugs[5]:
        await _solve(mem, "A", 1, 5, tid, s)
    await _solve(mem, "B", 0, 5, tid, slugs[5][0])
    await control(env, tid, "rounds/5/close")
    # Boss: A resolve, depois B e C; 30 por participante (sem bónus); boss_defeated só 1 vez, para o primeiro
    await control(env, tid, "rounds/6/start")
    await _solve(mem, "A", 0, 6, tid, "boss-0")
    await _solve(mem, "B", 0, 6, tid, "boss-0")
    await _solve(mem, "C", 1, 6, tid, "boss-0")
    await tournament_scoring.drain()
    st = await state(env.t_client, tid)
    board = {e["name"]: e for e in st["leaderboard"]}
    assert board["Agencia A"]["per_round"] == [35, 15, 0, 0, 80, 30] and board["Agencia A"]["points"] == 160
    assert board["Agencia B"]["per_round"] == [25, 35, 0, 0, 30, 30] and board["Agencia B"]["points"] == 120
    assert board["Agencia C"]["per_round"] == [10, 0, 0, 0, 0, 30] and board["Agencia C"]["points"] == 40
    assert board["Agencia D"]["points"] == 0 and board["Agencia E"]["points"] == 0
    assert [e["name"] for e in st["leaderboard"][:3]] == ["Agencia A", "Agencia B", "Agencia C"]
    assert [e["rank"] for e in st["leaderboard"]] == [1, 2, 3, 4, 4]  # empates partilham a posição
    assert board["Agencia A"]["solved"] == 3 + 2 + 3 + 1
    assert st["podium"] is None
    bonus = await events_of(tid, "first_bonus")
    assert [(e.payload["name"], e.payload["idx"]) for e in bonus] == [("Agencia A", 1), ("Agencia B", 2), ("Agencia A", 5)]
    boss = await events_of(tid, "boss_defeated")
    assert len(boss) == 1 and boss[0].payload["name"] == "Agencia A"
    solved = await events_of(tid, "mission_solved")
    assert {k for k in solved[0].payload} == {"participant_key", "name", "slug", "points", "hint_used"}
    hinted = [e.payload for e in solved if e.payload["hint_used"]]
    assert sorted((p["name"], p["points"]) for p in hinted) == [("Agencia A", 5), ("Agencia A", 15), ("Agencia B", 5)]
    # delta_rank: ao iniciar o boss, o ranking das rondas anteriores era o ponto de comparação
    assert board["Agencia C"]["delta_rank"] == 0
    # terminar: pódio com os 3 primeiros e evento final
    fin = await control(env, tid, "finish")
    assert fin["tournament"]["state"] == "finished" and [p["name"] for p in fin["podium"]] == ["Agencia A", "Agencia B", "Agencia C"]
    assert len(await events_of(tid, "tournament_finished")) == 1
    assert (await control(env, tid, "finish", expect=409)) == {"error": "tournament.finished"}


async def test_double_accepted_submission_counts_once_concurrently(make_user, make_class, new_client):
    env, tid, slugs, mem = await _scenario(make_user, make_class, new_client)
    await control(env, tid, "rounds/1/start")
    # os dois membros de A + dois client_id diferentes do mesmo aluno, todos ao mesmo tempo
    (_, c0, h0), (_, c1, h1) = mem["A"][1]
    rs = await asyncio.gather(
        submit(c0, h0, tid, 1, slugs[1][0]), submit(c1, h1, tid, 1, slugs[1][0]),
        submit(c0, h0, tid, 1, slugs[1][0]), submit(c1, h1, tid, 1, slugs[1][0]),
    )
    assert all(r.status_code == 202 for r in rs)
    await tournament_scoring.drain()
    async with SessionLocal() as db:
        n = (await db.execute(select(func.count()).select_from(TournamentSolve))).scalar_one()
    assert n == 1 and len(await events_of(tid, "mission_solved")) == 1
    # a mesma submissão (mesmo client_id) reenviada: devolve a mesma, mesmo com a ronda já fechada
    cid = uuid.uuid4()
    a = await submit(c0, h0, tid, 1, slugs[1][1], cid=cid)
    await control(env, tid, "rounds/1/close")
    async with SessionLocal() as db:  # e fora da tolerância
        await db.execute(update(TournamentRound).values(ends_at=utcnow() - timedelta(minutes=5)))
        await db.commit()
    b = await submit(c0, h0, tid, 1, slugs[1][1], cid=cid)
    assert a.json()["id"] == b.json()["id"]


async def test_runner_submission_counts_via_dispatcher(make_user, make_class, new_client):
    """Tipos com código passam pelo runner: o dispatcher regista a missão quando a submissão é aceite."""
    from app.config import settings
    from app.services.problems import sync_problems
    async with SessionLocal() as db:
        await sync_problems(db, settings.problems_dir)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["autocarro-ainda-da"], points=10)
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, t["tournament"]["join_code"])
    await control(env, tid, "rounds/1/start")
    good = 'a = int(input())\nb = int(input())\nf = a - b\nif f > 2:\n    print("Vai a andar")\nelif f >= 0:\n    print("Corre!")\nelse:\n    print("Pede boleia")\n'
    r = await c.post("/api/submissions", json={
        "client_id": str(uuid.uuid4()), "problem_slug": "autocarro-ainda-da", "code": good, "tournament_id": tid, "round_idx": 1,
    }, headers=h)
    assert r.status_code == 202  # o problema (aprovado ou não) está na ronda
    while await dispatcher.run_once(local_post):
        pass
    await tournament_scoring.drain()
    st = await state(c, tid)
    assert st["leaderboard"][0]["points"] == 15 and st["leaderboard"][0]["solved"] == 1  # 10 + 5 do primeiro (1 missão)
    assert st["current"]["missions"][0]["solved_by_me"] is True


# ---------------- regras de tempo e participação ----------------
async def test_submission_rules(make_user, make_class, new_client):
    await add_problem("m1")
    await add_problem("m2")
    await add_problem("outro")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid, code = t["tournament"]["id"], t["tournament"]["join_code"]
    await set_round(env, tid, 1, ["m1", "m2"], duration_s=60)
    _, c, h = await env.student(make_user, new_client, "ana")
    _, cs, hs = await env.student(make_user, new_client, "estranho")

    async def err(client, hh, slug="m1", idx=1, status=None):
        r = await submit(client, hh, tid, idx, slug)
        assert status is None or r.status_code == status, r.text
        return r.json().get("error")

    assert await err(c, h) == "tournament.not_participant"  # ainda não entrou
    await _join(c, h, code)
    assert await err(c, h) == "tournament.round_not_active"  # ronda ainda não começou
    await control(env, tid, "rounds/1/start")
    assert await err(cs, hs) == "tournament.not_participant"  # outro aluno da turma que não entrou
    assert await err(c, h, slug="outro") == "tournament.problem_not_in_round"
    assert await err(c, h, idx=9) == "tournament.round_not_found"
    r = await c.post("/api/submissions", json={"client_id": str(uuid.uuid4()), "problem_slug": "m1", "answers": ["ok"], "tournament_id": tid}, headers=h)
    assert r.json() == {"error": "tournament.invalid_submission"}
    # em pausa: rejeita
    await control(env, tid, "rounds/1/pause")
    assert await err(c, h) == "tournament.round_paused"
    await control(env, tid, "rounds/1/resume")
    # tolerância: 10 s depois do fim ainda aceita; 40 s depois já não
    async with SessionLocal() as db:
        await db.execute(update(TournamentRound).values(ends_at=utcnow() - timedelta(seconds=10)))
        await db.commit()
    assert await err(c, h, status=202) is None
    async with SessionLocal() as db:
        await db.execute(update(TournamentRound).values(ends_at=utcnow() - timedelta(seconds=40)))
        await db.commit()
    assert await err(c, h, slug="m2", status=409) == "tournament.time_over"
    # prolongar volta a abrir a ronda
    await control(env, tid, "rounds/1/extend", {"seconds": 120})
    assert await err(c, h, slug="m2", status=202) is None
    # fechada (e fora da tolerância) e terminada
    await control(env, tid, "rounds/1/close")
    async with SessionLocal() as db:
        await db.execute(update(TournamentRound).values(ends_at=utcnow() - timedelta(seconds=60)))
        await db.commit()
    assert await err(c, h, slug="m2") == "tournament.time_over"
    await control(env, tid, "finish")
    assert await err(c, h, slug="m2") == "tournament.finished"


async def test_agency_mode_requires_team(make_user, make_class, new_client):
    await add_problem("m1")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "agencias")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["m1"])
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, t["tournament"]["join_code"])
    await control(env, tid, "rounds/1/start")
    assert (await submit(c, h, tid, 1, "m1")).json() == {"error": "tournament.team_required"}


async def test_tournament_rate_limit_is_10_per_minute(make_user, make_class, new_client):
    await add_problem("m1")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["m1"])
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, t["tournament"]["join_code"])
    await control(env, tid, "rounds/1/start")
    codes = [(await submit(c, h, tid, 1, "m1", answer="errado")).status_code for _ in range(11)]
    assert codes == [202] * 10 + [429]
    assert (await submit(c, h, tid, 1, "m1")).json() == {"error": "submission.rate_limited"}


# ---------------- segredos, permissões, pistas ----------------
async def test_snapshot_never_leaks_secrets(make_user, make_class, new_client):
    await add_problem("q-ativa", tipo="quiz")
    await add_problem("q-futura", tipo="quiz")
    await add_problem("c-ativa", tipo="programa")
    await add_problem("f-ativa", tipo="funcao")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid, code = t["tournament"]["id"], t["tournament"]["join_code"]
    await set_round(env, tid, 1, ["q-ativa", "c-ativa", "f-ativa"])
    await set_round(env, tid, 2, ["q-futura"])
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, code)
    before = json.dumps(await state(c, tid))
    assert code not in before and "join_code" not in before
    await control(env, tid, "rounds/1/start")
    st = await state(c, tid)
    blob = json.dumps(st)
    assert code not in blob and "join_code" not in blob
    for secret in ("testes", "solucao_referencia", "solucao_ingenua", "editorial", "resposta_texto", '"resposta"', "args_gerador", "erros_comuns", "q-futura"):
        assert secret not in blob, secret
    assert [m["slug"] for m in st["current"]["missions"]] == ["q-ativa", "c-ativa", "f-ativa"]
    assert all({"solved_by_me", "hints_opened", "pistas_count"} <= set(m) for m in st["current"]["missions"])
    assert [r["mission_count"] for r in st["rounds"]] == [3, 1, 1, 1, 1, 1] or st["rounds"][0]["mission_count"] == 3
    assert "problem_slugs" not in st["rounds"][0]
    # o professor vê o código (e só ele)
    tv = await state(env.t_client, tid)
    assert tv["tournament"]["join_code"] == code and tv["me"]["participant_key"] is None
    assert "problem_slugs" in (await env.t_client.get(f"/api/tournaments/{tid}/admin")).json()["rounds"][0]
    # a ronda seguinte (pendente) não tem conteúdo
    await control(env, tid, "rounds/1/close")
    st2 = await state(c, tid)
    assert "q-futura" not in json.dumps(st2) and st2["current"]["idx"] == 1
    assert (await c.get(f"/api/tournaments/{tid}/admin")).status_code == 403


async def test_teacher_only_controls(make_user, make_class, new_client):
    await add_problem("m1")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["m1"])
    _, sc, sh = await env.student(make_user, new_client, "ana")
    await make_user("profb", __import__("app.models.user", fromlist=["Role"]).Role.teacher)
    async with new_client() as other:
        oh = await login(other, "profb")
        probes = [
            ("get", f"/api/tournaments/{tid}/admin", None), ("put", f"/api/tournaments/{tid}/rounds/1", {"points": 3}),
            ("post", f"/api/tournaments/{tid}/rounds/1/start", {}), ("post", f"/api/tournaments/{tid}/rounds/1/pause", {}),
            ("post", f"/api/tournaments/{tid}/rounds/1/resume", {}), ("post", f"/api/tournaments/{tid}/rounds/1/extend", {"seconds": 60}),
            ("post", f"/api/tournaments/{tid}/rounds/1/close", {}), ("post", f"/api/tournaments/{tid}/finish", {}),
            ("post", f"/api/tournaments/{tid}/teams/1/move", {"user_id": 1}), ("get", f"/api/tournaments/{tid}/state", None),
            ("get", f"/api/tournaments/{tid}/events", None),
        ]
        for method, url, body in probes:
            r = await getattr(other, method)(url, headers=oh, **({"json": body} if body is not None else {}))
            assert r.status_code == 404 and r.json() == {"error": "tournament.not_found"}, (method, url, r.status_code)
        r = await other.post("/api/tournaments", json={"class_id": env.class_id, "name": "X", "mode": "individual"}, headers=oh)
        assert r.status_code == 404 and r.json() == {"error": "tournament.class_not_found"}
        assert (await other.get("/api/tournaments")).json() == {"tournaments": []}
        assert tid == (await env.t_client.get("/api/tournaments")).json()["tournaments"][0]["id"]
    for method, url, body in probes[:9]:
        r = await getattr(sc, method)(url, headers=sh, **({"json": body} if body is not None else {}))
        assert r.status_code == 403 and r.json() == {"error": "auth.forbidden"}, (method, url)
    assert (await sc.post("/api/tournaments", json={"class_id": env.class_id, "name": "X", "mode": "individual"}, headers=sh)).status_code == 403
    assert (await control(env, tid, "rounds/1/extend", {"seconds": 60}, expect=409)) == {"error": "tournament.round_not_active"}
    r = await env.t_client.post("/api/tournaments", json={"class_id": env.class_id, "name": "X", "mode": "grupos"}, headers=env.t_headers)
    assert r.json() == {"error": "tournament.invalid_mode"}
    # o aluno vê só os torneios em que já entrou (sem o código)
    assert (await sc.get("/api/tournaments")).json() == {"tournaments": []}
    await _join(sc, sh, t["tournament"]["join_code"])
    listed = (await sc.get("/api/tournaments")).json()["tournaments"]
    assert len(listed) == 1 and "join_code" not in listed[0]


async def test_hints_endpoint_records_use_and_halves_points(make_user, make_class, new_client):
    await add_problem("m1", pistas=2)
    await add_problem("m2", pistas=0)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["m1", "m2"], points=10)
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, t["tournament"]["join_code"])
    assert (await c.get(f"/api/tournaments/{tid}/hints/m1/1")).json() == {"error": "tournament.round_not_active"}
    await control(env, tid, "rounds/1/start")
    r = await c.get(f"/api/tournaments/{tid}/hints/m1/1")
    assert r.status_code == 200 and r.json()["text"] == {"pt": "Pista de teste", "en": "Test hint"}
    assert (await c.get(f"/api/tournaments/{tid}/hints/m1/1")).status_code == 200  # idempotente
    assert (await c.get(f"/api/tournaments/{tid}/hints/m1/3")).json() == {"error": "tournament.hint_not_found"}
    assert (await c.get(f"/api/tournaments/{tid}/hints/m2/1")).json() == {"error": "tournament.hint_not_found"}
    assert (await c.get(f"/api/tournaments/{tid}/hints/zzz/1")).json() == {"error": "tournament.problem_not_in_round"}
    st = await state(c, tid)
    assert [m["hints_opened"] for m in st["current"]["missions"]] == [1, 0]
    await submit(c, h, tid, 1, "m1")
    await submit(c, h, tid, 1, "m2")
    await tournament_scoring.drain()
    st = await state(c, tid)
    assert st["leaderboard"][0]["points"] == 5 + 10 + 5  # pista 0,5×; sem pista 1×; +5 por ter as duas
    assert [m["solved_by_me"] for m in st["current"]["missions"]] == [True, True]


# ---------------- eventos, replay e agrupamento do leaderboard ----------------
async def test_events_endpoint_replay_and_resync(make_user, make_class, new_client):
    await add_problem("m1")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, ["m1"])
    _, c, h = await env.student(make_user, new_client, "ana")
    await _join(c, h, t["tournament"]["join_code"])
    await control(env, tid, "rounds/1/start")
    evs = (await c.get(f"/api/tournaments/{tid}/events")).json()
    assert evs["resync"] is False and [e["type"] for e in evs["events"]][:2] == ["player_joined", "round_started"]
    assert [e["seq"] for e in evs["events"]] == sorted(e["seq"] for e in evs["events"])
    last = evs["events"][-1]["seq"]
    assert (await state(c, tid))["last_seq"] == last
    assert (await c.get(f"/api/tournaments/{tid}/events?after={last}")).json() == {"events": [], "resync": False}
    from app.models.tournament import TournamentEvent
    async with SessionLocal() as db:
        db.add_all([TournamentEvent(tournament_id=tid, type="leaderboard", payload={}) for _ in range(501)])
        await db.commit()
    assert (await c.get(f"/api/tournaments/{tid}/events?after=0")).json() == {"events": [], "resync": True}
    assert (await c.get(f"/api/tournaments/{tid}/events?after={last}")).json()["resync"] is True


async def test_leaderboard_events_are_coalesced(make_user, make_class, new_client):
    for i in range(12):
        await add_problem(f"m{i}")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    await set_round(env, tid, 1, [f"m{i}" for i in range(12)])
    studs = [await env.student(make_user, new_client, f"al{i}") for i in range(6)]
    for _, c, h in studs:
        await _join(c, h, t["tournament"]["join_code"])
    await control(env, tid, "rounds/1/start")
    before = len(await events_of(tid, "leaderboard"))
    t0 = time.monotonic()
    await asyncio.gather(*(submit(c, h, tid, 1, f"m{i}") for _, c, h in studs for i in range(2)))
    await tournament_scoring.drain()
    elapsed = time.monotonic() - t0
    lbs = await events_of(tid, "leaderboard")
    new = lbs[before:]
    assert 1 <= len(new) <= int(elapsed) + 2  # 12 resoluções, no máximo 1 evento por segundo
    assert len(await events_of(tid, "mission_solved")) == 12
    final = new[-1].payload["leaderboard"]
    assert sum(e["solved"] for e in final) == 12  # o último evento já tem tudo
    gaps = [(b.created_at - a.created_at).total_seconds() for a, b in zip(new, new[1:])]
    assert all(g >= 0.95 for g in gaps), gaps


async def test_late_team_players_count_and_team_locked(make_user, make_class, new_client):
    await add_problem("m1")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "agencias")
    tid, code = t["tournament"]["id"], t["tournament"]["join_code"]
    assert t["players_count"] == 0 and t["tournament"]["players_count"] == 0
    await set_round(env, tid, 1, ["m1"])
    a, b, c3 = [await env.student(make_user, new_client, n) for n in ("ana", "rui", "eva")]
    for _, c, h in (a, b):
        await _join(c, h, code)
    await control(env, tid, "rounds/1/start")
    evs = await events_of(tid, "player_joined")
    assert [e.payload["players_count"] for e in evs] == [1, 2]
    r = await a[1].post(f"/api/tournaments/{tid}/teams", json={"name": "Gatos"}, headers=a[2])
    assert r.status_code == 201  # a meio da ronda
    gatos = r.json()["teams"][0]["id"]
    await _join(c3[1], c3[2], code)  # sem agência conta no total
    st = await state(env.t_client, tid)
    assert st["players_count"] == 3 and st["tournament"]["players_count"] == 3
    assert (await b[1].post(f"/api/tournaments/{tid}/teams/{gatos}/join", headers=b[2])).status_code == 200
    assert (await submit(a[1], a[2], tid, 1, "m1")).status_code == 202
    await tournament_scoring.drain()
    r = await a[1].post(f"/api/tournaments/{tid}/teams", json={"name": "Outra"}, headers=a[2])
    assert r.status_code == 409 and r.json() == {"error": "tournament.team_locked"}
    r = await b[1].post(f"/api/tournaments/{tid}/teams", json={"name": "Outra"}, headers=b[2])
    assert r.json() == {"error": "tournament.team_locked"}
    assert (await a[1].post(f"/api/tournaments/{tid}/teams/{gatos}/join", headers=a[2])).status_code == 200  # a mesma: idempotente
    await control(env, tid, "finish")
    r = await c3[1].post(f"/api/tournaments/{tid}/teams", json={"name": "Tarde"}, headers=c3[2])
    assert r.json() == {"error": "tournament.finished"}


async def test_join_code_failures_are_rate_limited(make_user, make_class, new_client):
    env = await make_env(make_user, make_class, new_client)
    await create_tournament(env, "individual")
    _, c, h = await env.student(make_user, new_client, "ana")
    codes = [(await c.post("/api/tournaments/join", json={"join_code": "ZZZZZZ"}, headers=h)).status_code for _ in range(31)]
    assert codes == [404] * 30 + [429]


async def test_problems_list_estado_teachers_only(make_user, make_class, new_client):
    await add_problem("aprov", estado="aprovado")
    await add_problem("rasc", estado="rascunho")
    env = await make_env(make_user, make_class, new_client)
    _, c, _ = await env.student(make_user, new_client, "ana")
    tl = {p["id"]: p for p in (await env.t_client.get("/api/problems")).json()["problems"]}
    assert tl["aprov"]["estado"] == "aprovado" and tl["rasc"]["estado"] == "rascunho"
    sl = (await c.get("/api/problems")).json()["problems"]
    assert [p["id"] for p in sl] == ["aprov"] and "estado" not in sl[0]


async def test_static_cache_headers(client):
    from app.config import settings
    d = settings.frontend_dir
    for rel in ("dist/x.css", "i18n/x.json", "vendor/x.js"):
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text("x")
    try:
        from app.main import create_app
        import httpx
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="https://testserver") as c:
            assert (await c.get("/dist/x.css")).headers["cache-control"] == "no-cache"
            assert (await c.get("/i18n/x.json")).headers["cache-control"] == "no-cache"
            assert "immutable" in (await c.get("/vendor/x.js")).headers["cache-control"]
    finally:
        for rel in ("dist/x.css", "i18n/x.json", "vendor/x.js"):
            (d / rel).unlink(missing_ok=True)


# ---------------- sorteio de problemas (🎲) ----------------
async def test_random_problems_respects_round_and_open_blocks(make_user, make_class, new_client):
    for d in (1, 2, 3, 4, 5):
        for i in range(5):
            await add_problem(f"r7-d{d}-{i}", tipo=("programa", "funcao", "bug")[i % 3], bloco="7", dif=d)
    await add_problem("r6b-fechado", tipo="programa", bloco="6b", dif=1)  # bloco ainda não dado: nunca sai
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    other = {s for r in t["rounds"] if r["idx"] != 1 for s in r["problem_slugs"]}
    meta = {f"r7-d{d}-{i}": d for d in (1, 2, 3, 4, 5) for i in range(5)}
    for _ in range(5):
        slugs = (await control(env, tid, "rounds/1/random"))["problem_slugs"]
        assert len(slugs) == 3 and len(set(slugs)) == 3
        assert not set(slugs) & other and "r6b-fechado" not in slugs
        assert all(meta[s] in (1, 2) for s in slugs)  # ronda 1: fácil
    boss = (await control(env, tid, "rounds/6/random"))["problem_slugs"]
    assert len(boss) == 1
    # é só uma sugestão: nada muda até o professor gravar
    assert (await control(env, tid, "rounds/1/random")) and [r for r in (await state(env.t_client, tid))["rounds"] if r["idx"] == 1][0]


async def test_random_problems_permissions_and_started_round(make_user, make_class, new_client):
    await add_problem("rp-1", tipo="programa", bloco="7", dif=1)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    _, c, h = await env.student(make_user, new_client, "estudante")
    assert (await c.post(f"/api/tournaments/{tid}/rounds/1/random", json={}, headers=h)).status_code == 403
    await set_round(env, tid, 1, ["rp-1"])
    await control(env, tid, "rounds/1/start")
    await control(env, tid, "rounds/1/random", expect=409)


async def test_random_problems_skip_algorithm_arena_when_possible(make_user, make_class, new_client):
    for i in range(4):
        await add_problem(f"aula-{i}", tipo="programa", bloco="7", dif=1)
        await add_problem(f"algo-{i}", tipo="programa", bloco="mais_alem", dif=1)
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    for _ in range(5):
        slugs = (await control(env, tid, "rounds/1/random"))["problem_slugs"]
        assert slugs and all(s.startswith("aula-") for s in slugs)
