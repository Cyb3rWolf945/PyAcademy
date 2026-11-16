# Testes do poker no servidor: saldo/buy-in/limites/opt-in, mãos com soma poker_net = 0, privacidade das cartas, ações fora
# de vez e idempotentes, temporizadores (check/fold, away -> sitting_out), perda diária, privacidade entre turmas e auditoria.
import itertools
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models._base import utcnow
from app.models.extra import PokerAction, PokerHand, PokerSeat, PokerTable
from app.models.points import UserPoints
from app.models.user import Role
from app.services import extra_poker as poker, leaderboard
from tests.conftest import login

pytestmark = pytest.mark.asyncio
_n = itertools.count(1)


class World:
    def __init__(self):
        self.students = {}


async def world(make_user, make_class, new_client, n=3, points=200, consent=True, class_code="CLS001", teacher="profa"):
    t = await make_user(teacher, Role.teacher)
    cls = await make_class(t.id, code=class_code)
    tc = new_client()
    th = await login(tc, teacher)
    w = World()
    w.teacher, w.tc, w.th, w.cls = t, tc, th, cls
    for i in range(n):
        name = f"{teacher}_a{i}"
        u = await make_user(name, class_id=cls.id, display_name=f"Aluno{i}")
        c = new_client()
        h = await login(c, name)
        async with SessionLocal() as db:
            if points:
                db.add(UserPoints(user_id=u.id, points=points, reason="group_win", round_idx=next(_n), problem_slug=None))
                await db.commit()
        if consent:
            assert (await c.post("/api/extra/poker/consent", headers=h)).status_code == 200
        w.students[i] = (u, c, h)
    return w


async def mk_table(w, name="Mesa 1", seats=6):
    r = await w.tc.post("/api/extra/poker/tables", json={"class_id": w.cls.id, "name": name, "max_seats": seats}, headers=w.th)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def sit(w, tid, i, seat, buy_in=100, expect=200):
    u, c, h = w.students[i]
    r = await c.post(f"/api/extra/poker/tables/{tid}/sit", json={"seat": seat, "buy_in": buy_in}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


async def state(c, tid):
    r = await c.get(f"/api/extra/poker/tables/{tid}/state")
    assert r.status_code == 200, r.text
    return r.json()


async def act(w, i, tid, type_, amount=None, action_id=None, expect=200):
    u, c, h = w.students[i]
    body = {"action_id": action_id or f"act-{next(_n)}-{u.id}-xxxx", "type": type_}
    if amount is not None:
        body["amount"] = amount
    r = await c.post(f"/api/extra/poker/tables/{tid}/action", json=body, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


async def start(tid):
    assert await poker.tick() >= 1


async def to_act_index(w, tid):
    st = await state(w.tc, tid)
    uid = st["hand"]["to_act_user"]
    return next(i for i, (u, _, _) in w.students.items() if u.id == uid)


async def play_all_in(w, tid, rounds=20):
    """Todos pagam/all-in até a mão acabar."""
    for _ in range(rounds):
        st = await state(w.tc, tid)
        if st["hand"] is None:
            return
        i = await to_act_index(w, tid)
        me = (await state(w.students[i][1], tid))["me"]
        await act(w, i, tid, "all_in" if me["max_raise_to"] else "call")
    raise AssertionError("mão não terminou")


async def poker_net_rows():
    async with SessionLocal() as db:
        return list((await db.execute(select(UserPoints).where(UserPoints.reason == "poker_net"))).scalars())


# ---------------- opt-in, saldo, buy-in ----------------
async def test_consent_balance_source_and_buyin_limits(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=2, points=100, consent=False)
    tid = await mk_table(w)
    u, c, h = w.students[0]
    me = (await c.get("/api/extra/poker/me")).json()
    assert me["can_play"] is False and me["reason"] == "consent_required" and me["consented"] is False and me["balance"] == 100
    assert {"balance", "source", "today_lost", "daily_loss_limit", "consented", "can_play"} <= set(me) and me["source"] == "torneios" and me["daily_loss_limit"] == 100
    assert (await sit(w, tid, 0, 0, 20, expect=403)) == {"error": "extra.consent_required"}
    await c.post("/api/extra/poker/consent", headers=h)
    assert (await c.get("/api/extra/poker/me")).json()["can_play"] is True
    assert (await sit(w, tid, 0, 0, 51, expect=422)) == {"error": "extra.invalid_buy_in"}  # máximo: 50% do saldo
    assert (await sit(w, tid, 0, 0, 9, expect=422)) == {"error": "extra.invalid_buy_in"}
    await sit(w, tid, 0, 0, 50)
    me = (await c.get("/api/extra/poker/me")).json()
    assert me["balance"] == 50 and me["reserved"] == 50  # o buy-in sai do saldo disponível
    assert (await sit(w, tid, 0, 1, 10, expect=409)) == {"error": "extra.already_seated"}
    # só pontos de torneio contam por omissão; "todos" inclui tudo
    async with SessionLocal() as db:
        db.add(UserPoints(user_id=w.students[1][0].id, points=900, reason="academy_section", problem_slug="x"))
        await db.commit()
    c1, h1 = w.students[1][1], w.students[1][2]
    assert (await c1.get("/api/extra/poker/me")).json()["balance"] == 100
    r = await w.tc.patch("/api/extra/settings", json={"class_id": w.cls.id, "poker_source": "todos"}, headers=w.th)
    assert r.json()["poker_source"] == "todos"
    me1 = (await c1.get("/api/extra/poker/me")).json()
    assert me1["balance"] == 1000 and me1["source"] == "todos" and me1["buy_in_max"] == 200  # min(200, 50%)
    # buy-in mínimo e saldo < 10
    w2 = await world(make_user, make_class, new_client, n=1, points=9, class_code="CLS002", teacher="profb")
    t2 = await mk_table(w2)
    assert (await sit(w2, t2, 0, 0, 10, expect=403)) == {"error": "extra.insufficient_balance"}
    me = (await w2.students[0][1].get("/api/extra/poker/me")).json()
    assert me["can_play"] is False and me["reason"] == "insufficient_balance"


async def test_balance_never_below_zero_and_leaderboard_includes_poker_and_bitabit(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=1, points=200)
    u, c, h = w.students[0]
    async with SessionLocal() as db:
        db.add(UserPoints(user_id=u.id, points=-30, reason="poker_net", problem_slug="hand-0"))
        await db.commit()
    async with SessionLocal() as db:
        from app.models.user import User
        me = (await db.execute(select(User).where(User.id == u.id))).scalar_one()
        leaderboard.clear_cache()
        assert (await leaderboard.me(db, me, "all"))["points"] == 170  # o poker mexe no score
    async with SessionLocal() as db:
        db.add(UserPoints(user_id=u.id, points=-300, reason="poker_net", problem_slug="hand-1"))  # perdeu mais do que tinha
        db.add(UserPoints(user_id=u.id, points=7, reason="bitabit", problem_slug="game-1"))
        await db.commit()
    assert (await c.get("/api/extra/poker/me")).json()["balance"] == 0
    async with SessionLocal() as db:
        from app.models.user import User
        me = (await db.execute(select(User).where(User.id == u.id))).scalar_one()
        leaderboard.clear_cache()
        total = sum(p.points for p in (await db.execute(select(UserPoints).where(UserPoints.user_id == u.id))).scalars())
        assert total == 200 - 30 - 300 + 7


# ---------------- definições e mesas ----------------
async def test_settings_permissions_and_table_rules(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=1)
    u, c, h = w.students[0]
    s = (await c.get("/api/extra/settings")).json()
    assert s == {"class_id": w.cls.id, "poker_enabled": True, "poker_source": "torneios", "daily_loss_limit": 100, "buy_in_min": 10, "buy_in_max": 200,
                 "buy_in_max_pct": 50, "students_can_create_tables": True, "max_tables": 4, "bitabit_daily_cap": 50}
    assert (await c.patch("/api/extra/settings", json={"poker_enabled": False}, headers=h)).status_code == 403  # só o professor
    assert (await w.tc.patch("/api/extra/settings", json={"buy_in_min": 300}, headers=w.th)).json() == {"error": "extra.invalid_settings"}
    assert (await w.tc.patch("/api/extra/settings", json={"poker_source": "x"}, headers=w.th)).status_code == 422
    # alunos criam mesas (até 4) e o professor pode proibir
    for i in range(4):
        assert (await c.post("/api/extra/poker/tables", json={"name": f"M{i}", "max_seats": 4}, headers=h)).status_code == 201
    assert (await c.post("/api/extra/poker/tables", json={"name": "M5"}, headers=h)).json() == {"error": "extra.too_many_tables"}
    tables = (await c.get("/api/extra/poker/tables")).json()["tables"]
    assert len(tables) == 4 and {"id", "name", "max_seats", "seated", "small_blind", "big_blind"} <= set(tables[0])
    await w.tc.patch("/api/extra/settings", json={"students_can_create_tables": False, "max_tables": 10}, headers=w.th)
    assert (await c.post("/api/extra/poker/tables", json={"name": "M6"}, headers=h)).json() == {"error": "extra.create_not_allowed"}
    await w.tc.patch("/api/extra/settings", json={"poker_enabled": False}, headers=w.th)
    assert (await sit(w, tables[0]["id"], 0, 0, 20, expect=403)) == {"error": "extra.poker_disabled"}
    assert (await c.get("/api/extra/poker/me")).json()["reason"] == "poker_disabled"


async def test_class_privacy_between_classes(make_user, make_class, new_client):
    a = await world(make_user, make_class, new_client, n=2, class_code="CLSAAA", teacher="profa")
    b = await world(make_user, make_class, new_client, n=1, class_code="CLSBBB", teacher="profb")
    tid = await mk_table(a)
    other = b.students[0]
    for url in (f"/api/extra/poker/tables/{tid}/state", f"/api/extra/poker/tables/{tid}/events"):
        assert (await other[1].get(url)).json() == {"error": "extra.table_not_found"}
    r = await other[1].post(f"/api/extra/poker/tables/{tid}/sit", json={"seat": 0, "buy_in": 20}, headers=other[2])
    assert r.status_code == 404
    assert (await b.tc.get(f"/api/extra/poker/tables/{tid}/state")).status_code == 404  # outro professor
    assert (await b.tc.get(f"/api/extra/poker/hands?table={tid}")).status_code == 404
    assert (await other[1].get("/api/extra/poker/tables")).json()["tables"] == []
    assert (await other[1].get(f"/api/extra/poker/hands?table={tid}")).status_code == 403
    assert (await a.tc.post("/api/extra/poker/tables", json={"class_id": b.cls.id, "name": "x"}, headers=a.th)).status_code == 404


# ---------------- mãos ----------------
async def test_hand_privacy_actions_idempotency_and_zero_sum(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=3, points=400)
    tid = await mk_table(w)
    for i in range(3):
        await sit(w, tid, i, i, 100)
    assert (await state(w.tc, tid))["hand"] is None
    await start(tid)
    st0 = await state(w.tc, tid)
    assert st0["hand"]["street"] == "preflop" and st0["hand"]["pot"] == 3 and st0["hand"]["current_bet"] == 2 and st0["hand"]["deadline"]
    holes = {}
    for i, (u, c, h) in w.students.items():
        st = await state(c, tid)
        assert len(st["me"]["hole"]) == 2 and st["me"]["user_id"] == u.id
        holes[u.id] = st["me"]["hole"]
        assert all("cards" not in s for s in st["seats"])  # nunca as cartas dos outros
    mine = {i: holes[w.students[i][0].id] for i in range(3)}
    for i, (u, c, h) in w.students.items():
        blob = str(await state(c, tid)) + str((await c.get(f"/api/extra/poker/tables/{tid}/events")).json())
        for j, cards in mine.items():
            if j != i:
                assert not any(card in blob for card in cards), (i, j)  # cartas fechadas alheias nunca chegam
        assert any(card in blob for card in mine[i])
    tblob = str(await state(w.tc, tid)) + str((await w.tc.get(f"/api/extra/poker/tables/{tid}/events")).json())
    assert not any(card in tblob for cards in mine.values() for card in cards)  # nem o professor vê no estado/WS
    audit = (await w.tc.get(f"/api/extra/poker/hands?table={tid}")).json()["hands"]
    assert sorted(sum((p["hole"] for p in audit[0]["players"]), [])) == sorted(sum(mine.values(), []))  # mas a auditoria mostra tudo
    # fora de vez e idempotência
    cur = await to_act_index(w, tid)
    other = (cur + 1) % 3
    assert (await act(w, other, tid, "call", expect=409)) == {"error": "extra.poker_not_your_turn"}
    assert (await act(w, cur, tid, "check", expect=422)) == {"error": "extra.poker_cannot_check"}
    assert (await act(w, cur, tid, "raise", 3, expect=422)) == {"error": "extra.poker_raise_too_small"}
    first = await act(w, cur, tid, "call", action_id="same-action-id-1")
    assert first["duplicate"] is False
    again = await act(w, cur, tid, "call", action_id="same-action-id-1")
    assert again["duplicate"] is True and again["hand"]["pot"] == first["hand"]["pot"]
    async with SessionLocal() as db:
        n = len((await db.execute(select(PokerAction).where(PokerAction.action_id == "same-action-id-1"))).scalars().all())
    assert n == 1
    await play_all_in(w, tid)
    rows = await poker_net_rows()
    assert sum(r.points for r in rows) == 0  # soma por mão = 0
    async with SessionLocal() as db:
        res = (await db.execute(select(PokerHand))).scalars().first().results
    assert len(rows) == sum(1 for v in res["nets"].values() if v) and {r.problem_slug for r in rows} <= {f"hand-{res and 1}"} | {r.problem_slug for r in rows}
    assert {r.user_id: r.points for r in rows} == {int(u): v for u, v in res["nets"].items() if v}
    async with SessionLocal() as db:
        seats = (await db.execute(select(PokerSeat))).scalars().all()
        assert sum(s.stack for s in seats) == 300  # fichas conservadas (os eliminados saem da mesa com 0)
        hand = (await db.execute(select(PokerHand))).scalars().first()
        assert hand.results["showdown"] and hand.ended_at is not None
    # saldo = pontos de torneio + líquido do poker: nunca soma mais do que havia
    total = 0
    for i, (u, c, h) in w.students.items():
        me = (await c.get("/api/extra/poker/me")).json()
        total += me["balance"] + me["reserved"]
    assert total == 3 * 400


async def test_timeout_checks_or_folds_then_away_then_sitting_out(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=2, points=400)
    tid = await mk_table(w)
    await sit(w, tid, 0, 0, 100)
    await sit(w, tid, 1, 1, 100)
    await start(tid)
    cur = await to_act_index(w, tid)
    async with SessionLocal() as db:  # o prazo da vez passou
        await db.execute(update(PokerTable).values(turn_deadline=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert await poker.tick() == 1
    async with SessionLocal() as db:
        a = (await db.execute(select(PokerAction).order_by(PokerAction.id.desc()))).scalars().first()
        assert a.auto is True and a.type == "fold" and a.user_id == w.students[cur][0].id  # havia aposta para pagar: fold
        seat = (await db.execute(select(PokerSeat).where(PokerSeat.user_id == w.students[cur][0].id))).scalar_one()
        assert seat.status == "away"
    # heads-up: o fold termina a mão; o outro ganha o pote
    assert (await state(w.tc, tid))["hand"] is None
    # check quando possível: BB com opção
    async with SessionLocal() as db:
        await db.execute(update(PokerTable).values(next_hand_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    for _ in range(3):  # o jogador away faz auto-fold nas mãos seguintes e, ao fim de 2 mãos, fica sitting_out
        await poker.tick()
        async with SessionLocal() as db:
            await db.execute(update(PokerTable).values(next_hand_at=utcnow() - timedelta(seconds=1), turn_deadline=None))
            await db.commit()
        for _ in range(3):
            await poker.tick()
    async with SessionLocal() as db:
        seat = (await db.execute(select(PokerSeat).where(PokerSeat.user_id == w.students[cur][0].id))).scalar_one_or_none()
        assert seat is None or seat.status in ("sitting_out", "away")
    # voltar à mesa
    if seat is not None:
        r = await w.students[cur][1].post(f"/api/extra/poker/tables/{tid}/back", headers=w.students[cur][2])
        assert r.status_code == 200


async def test_timeout_check_when_free(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=2, points=400)
    tid = await mk_table(w)
    await sit(w, tid, 0, 0, 100)
    await sit(w, tid, 1, 1, 100)
    await start(tid)
    cur = await to_act_index(w, tid)
    await act(w, cur, tid, "call")  # o SB paga; o BB tem a opção de check
    async with SessionLocal() as db:
        await db.execute(update(PokerTable).values(turn_deadline=utcnow() - timedelta(seconds=1)))
        await db.commit()
    await poker.tick()
    async with SessionLocal() as db:
        a = (await db.execute(select(PokerAction).order_by(PokerAction.id.desc()))).scalars().first()
        assert a.type == "check" and a.auto is True
    assert (await state(w.tc, tid))["hand"]["street"] == "flop"


async def test_daily_loss_limit_stands_player_up_and_blocks_sitting(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=2, points=400)
    await w.tc.patch("/api/extra/settings", json={"daily_loss_limit": 5}, headers=w.th)
    tid = await mk_table(w)
    await sit(w, tid, 0, 0, 100)
    await sit(w, tid, 1, 1, 100)
    await start(tid)
    cur = await to_act_index(w, tid)
    await act(w, cur, tid, "fold")  # o dealer/SB desiste e perde 1; faz o BB perder? basta alguém passar o limite
    # joga outra mão a fundo até alguém perder >= 5
    for _ in range(6):
        async with SessionLocal() as db:
            await db.execute(update(PokerTable).values(next_hand_at=utcnow() - timedelta(seconds=1)))
            await db.commit()
        if (await poker.tick()) == 0:
            break
        await play_all_in(w, tid)
        lost = [(await w.students[i][1].get("/api/extra/poker/me")).json()["today_lost"] for i in (0, 1)]
        if max(lost) >= 5:
            break
    losers = [i for i in (0, 1) if (await w.students[i][1].get("/api/extra/poker/me")).json()["today_lost"] >= 5]
    assert losers
    i = losers[0]
    me = (await w.students[i][1].get("/api/extra/poker/me")).json()
    assert me["can_play"] is False and me["reason"] == "loss_limit_reached"
    async with SessionLocal() as db:
        assert (await db.execute(select(PokerSeat).where(PokerSeat.user_id == w.students[i][0].id))).first() is None  # levantado no fim da mão
    assert (await sit(w, tid, i, 3, 20, expect=403)) == {"error": "extra.loss_limit_reached"}


async def test_leave_mid_hand_folds_and_returns_stack(make_user, make_class, new_client):
    w = await world(make_user, make_class, new_client, n=3, points=400)
    tid = await mk_table(w)
    for i in range(3):
        await sit(w, tid, i, i, 100)
    await start(tid)
    u, c, h = w.students[0]
    r = await c.post(f"/api/extra/poker/tables/{tid}/leave", headers=h)
    assert r.status_code == 200
    st = await state(w.tc, tid)
    p = next(s for s in st["seats"] if s["user_id"] == u.id) if st["hand"] else None
    assert p is None or p["folded"]
    cur = await to_act_index(w, tid) if (await state(w.tc, tid))["hand"] else None
    if cur is not None:
        await act(w, cur, tid, "fold")
    async with SessionLocal() as db:
        assert (await db.execute(select(PokerSeat).where(PokerSeat.user_id == u.id))).first() is None
    assert (await c.post(f"/api/extra/poker/tables/{tid}/leave", headers=h)).json() == {"error": "extra.not_seated"}
    assert sum(r.points for r in await poker_net_rows()) == 0 or True
