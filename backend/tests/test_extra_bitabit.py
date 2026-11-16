# Testes do Bit a Bit: gerador mulberry32 igual ao vetor partilhado com o JS, partida/fim com recálculo no servidor,
# respostas forjadas e tempos impossíveis recusados, limite diário de 50 pontos, recordes e ranking da turma.
import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models._base import utcnow
from app.models.extra import BitabitGame
from app.models.points import UserPoints
from app.models.user import Role
from app.services import bitabit as bb
from tests.conftest import login

pytestmark = pytest.mark.asyncio
VECTORS = Path(__file__).parent / "fixtures" / "bitabit_vectors.json"


def test_generator_matches_shared_vectors():
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert data["rows_per_level"] == bb.ROWS_PER_LEVEL and data["max_rows"] == bb.MAX_ROWS
    for v in data["vectors"]:
        rng = bb.mulberry32(v["seed"])
        assert [rng() for _ in v["rng"]] == v["rng"]  # os doubles são IDÊNTICOS (divisão exata por 2^32)
        assert bb.rows(v["seed"], len(v["rows"])) == v["rows"]
    for c in data["score"]["cases"]:
        assert bb.row_score(c["bits"], c["level"], c["t_ms"]) == c["score"]
    assert bb.mulberry32(1)() == 0.6270739405881613  # valor clássico do mulberry32
    r = bb.rows(7, 40)
    assert [x["bits"] for x in r[:10]] == [4] * 10 and {x["bits"] for x in r[10:20]} == {6} and {x["bits"] for x in r[20:]} == {8}
    assert all(1 <= x["value"] < 2 ** x["bits"] for x in r) and {x["kind"] for x in r} == {"b2d", "d2b"}
    assert bb.rows(7, 40) == r and bb.rows(8, 40) != r


async def _student(make_user, make_class, new_client, name="ana", code="BIT001", teacher="profa"):
    t = await make_user(teacher, Role.teacher)
    cls = await make_class(t.id, code=code)
    u = await make_user(name, class_id=cls.id, display_name=name.capitalize())
    c = new_client()
    return u, c, await login(c, name), cls


async def _start(c, h):
    r = await c.post("/api/extra/bitabit/start", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _answers(seed, n, ms=900, wrong=()):
    rows = bb.rows(seed, n)
    return [{"row": r["k"], "value": r["value"] + (1 if r["k"] in wrong else 0), "t_ms": ms} for r in rows]


async def _backdate(game_id, seconds):
    async with SessionLocal() as db:
        await db.execute(update(BitabitGame).where(BitabitGame.id == game_id).values(started_at=utcnow() - timedelta(seconds=seconds)))
        await db.commit()


async def test_start_and_finish_recomputes_score_and_awards(make_user, make_class, new_client):
    u, c, h, _ = await _student(make_user, make_class, new_client)
    g = await _start(c, h)
    assert set(g) >= {"game_id", "seed", "config"} and 0 <= g["seed"] < 2 ** 32 and g["config"]["max_rows"] == 80 and g["config"]["min_ms_per_row"] == 300
    await _backdate(g["game_id"], 120)
    ans = _answers(g["seed"], 30, 900, wrong={3})
    expected = sum(bb.row_score(r["bits"], r["level"], 900) for r in bb.rows(g["seed"], 30) if r["k"] != 3)
    r = await c.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": ans, "score": 999999}, headers=h)  # o score do cliente é ignorado
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["score"] == expected and out["rows_correct"] == 29 and out["points_awarded"] == expected // 100
    assert out["best"] == expected and out["today_remaining"] == 50 - expected // 100 and out["client_score_ignored"] is True
    me = (await c.get("/api/extra/bitabit/me")).json()
    assert me == {"today_points": expected // 100, "daily_cap": 50, "today_remaining": 50 - expected // 100, "best_score": expected, "games_today": 1}
    async with SessionLocal() as db:
        rows = (await db.execute(select(UserPoints).where(UserPoints.reason == "bitabit"))).scalars().all()
    assert [(x.user_id, x.points) for x in rows] == [(u.id, expected // 100)]
    assert (await c.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": ans}, headers=h)).json() == {"error": "extra.game_finished"}
    assert (await c.post("/api/extra/bitabit/9999/finish", json={"answers": []}, headers=h)).json() == {"error": "extra.game_not_found"}


async def test_forged_and_impossible_answers_rejected(make_user, make_class, new_client):
    u, c, h, _ = await _student(make_user, make_class, new_client)
    cases = {
        "too_fast": lambda s: _answers(s, 10, 100),  # < 300 ms por linha
        "more_time_than_elapsed": lambda s: _answers(s, 10, 60000),
        "duplicate_row": lambda s: [{"row": 0, "value": 1, "t_ms": 900}, {"row": 0, "value": 1, "t_ms": 900}],
        "row_out_of_range": lambda s: [{"row": 500, "value": 1, "t_ms": 900}],
        "bad_shape": lambda s: [{"row": 0, "value": "x", "t_ms": 900}],
    }
    for name, make in cases.items():
        g = await _start(c, h)
        await _backdate(g["game_id"], 20)
        r = await c.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": make(g["seed"])}, headers=h)
        assert r.status_code == 422 and r.json() == {"error": "extra.bitabit_implausible"}, name
    g = await _start(c, h)  # partida demasiado antiga
    await _backdate(g["game_id"], 31 * 60)
    r = await c.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": []}, headers=h)
    assert r.json() == {"error": "extra.bitabit_expired"}
    async with SessionLocal() as db:
        assert (await db.execute(select(UserPoints).where(UserPoints.reason == "bitabit"))).first() is None
    # respostas erradas valem 0 (mas é uma partida válida)
    g = await _start(c, h)
    await _backdate(g["game_id"], 60)
    r = await c.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": _answers(g["seed"], 10, 900, wrong=set(range(10)))}, headers=h)
    assert r.json()["score"] == 0 and r.json()["points_awarded"] == 0
    # outro aluno não pode terminar a partida alheia
    g = await _start(c, h)
    await make_user("rui")
    oc = new_client()
    oh = await login(oc, "rui")
    assert (await oc.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": []}, headers=oh)).status_code == 404


async def test_daily_cap_50_and_best_still_counts(make_user, make_class, new_client):
    u, c, h, cls = await _student(make_user, make_class, new_client)
    async with SessionLocal() as db:
        db.add(UserPoints(user_id=u.id, points=48, reason="bitabit", problem_slug="game-old"))
        await db.commit()
    g = await _start(c, h)
    await _backdate(g["game_id"], 200)
    ans = _answers(g["seed"], 40, 500)
    score = sum(bb.row_score(r["bits"], r["level"], 500) for r in bb.rows(g["seed"], 40))
    assert score // 100 > 2
    out = (await c.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": ans}, headers=h)).json()
    assert out["points_awarded"] == 2 and out["today_remaining"] == 0 and out["best"] == score  # só 2 pontos; o recorde conta na mesma
    g2 = await _start(c, h)
    await _backdate(g2["game_id"], 200)
    out2 = (await c.post(f"/api/extra/bitabit/{g2['game_id']}/finish", json={"answers": _answers(g2["seed"], 40, 500)}, headers=h)).json()
    assert out2["points_awarded"] == 0 and out2["today_remaining"] == 0
    me = (await c.get("/api/extra/bitabit/me")).json()
    assert me["today_points"] == 50 and me["games_today"] == 2
    # o professor pode alterar o teto da turma
    tc = new_client()
    th = await login(tc, "profa")
    assert (await tc.patch("/api/extra/settings", json={"class_id": cls.id, "bitabit_daily_cap": 60}, headers=th)).json()["bitabit_daily_cap"] == 60


async def test_class_leaderboard_and_start_rate_limit(make_user, make_class, new_client):
    u, c, h, cls = await _student(make_user, make_class, new_client)
    other = await make_user("rui", class_id=cls.id, display_name="Rui")
    oc = new_client()
    oh = await login(oc, "rui")
    third_teacher = await make_user("profz", Role.teacher)
    cls2 = await make_class(third_teacher.id, code="BIT002")
    stranger = await make_user("zé", class_id=cls2.id) if False else await make_user("ze", class_id=cls2.id, display_name="Ze")
    zc = new_client()
    zh = await login(zc, "ze")
    scores = {}
    for who, (cl, hd, n) in {"ana": (c, h, 20), "rui": (oc, oh, 35), "ze": (zc, zh, 30)}.items():
        g = await _start(cl, hd)
        await _backdate(g["game_id"], 100)
        out = (await cl.post(f"/api/extra/bitabit/{g['game_id']}/finish", json={"answers": _answers(g["seed"], n, 900)}, headers=hd)).json()
        scores[who] = out["score"]
    lb = (await c.get("/api/extra/bitabit/leaderboard")).json()
    assert [(e["display_name"], e["best"]) for e in lb["entries"]] == [("Rui", scores["rui"]), ("Ana", scores["ana"])]  # só a minha turma
    assert lb["me"] == {"best": scores["ana"], "rank": 2} and all(set(e) == {"rank", "display_name", "best", "avatar_seed", "me"} for e in lb["entries"])
    assert "ze" not in json.dumps(lb) and "username" not in json.dumps(lb)
    for _ in range(30):
        await _start(c, h)
    assert (await c.post("/api/extra/bitabit/start", headers=h)).json() == {"error": "extra.rate_limited"}
    assert other.id != u.id and other is not None
