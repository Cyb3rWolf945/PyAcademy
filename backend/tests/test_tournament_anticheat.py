# Testes do anti-cheat do torneio: só conta durante a ronda, bloqueia submissões e pistas até o professor autorizar,
# é idempotente, não se revela aos colegas e o professor é o único que pode deixar voltar.
import pytest

from tests.test_tournament_support import add_problem, control, create_tournament, events_of, make_env, set_round, state, submit

pytestmark = pytest.mark.asyncio


async def _setup(make_user, make_class, new_client):
    await add_problem("ac-q1")
    env = await make_env(make_user, make_class, new_client)
    t = await create_tournament(env, "individual")
    tid = t["tournament"]["id"]
    ana = await env.student(make_user, new_client, "ana")
    rui = await env.student(make_user, new_client, "rui")
    for _, c, h in (ana, rui):
        r = await c.post("/api/tournaments/join", json={"join_code": t["tournament"]["join_code"]}, headers=h)
        assert r.status_code == 200, r.text
    await set_round(env, tid, 1, ["ac-q1"])
    return env, tid, ana, rui


async def _report(student, tid, client_id="cliente-0001", kind="paste"):
    _, c, h = student
    return await c.post(f"/api/tournaments/{tid}/anticheat/report", json={"client_id": client_id, "kind": kind}, headers=h)


async def test_nothing_counts_outside_a_running_round(make_user, make_class, new_client):
    env, tid, ana, _ = await _setup(make_user, make_class, new_client)
    r = await _report(ana, tid)
    assert r.status_code == 200 and r.json() == {"armed": False, "locked": False, "kind": None}
    await control(env, tid, "rounds/1/start")
    await control(env, tid, "rounds/1/pause")
    assert (await _report(ana, tid, "cliente-0002")).json()["locked"] is False
    assert await events_of(tid, "anticheat_locked") == []


async def test_lock_blocks_submissions_until_teacher_releases(make_user, make_class, new_client):
    env, tid, ana, rui = await _setup(make_user, make_class, new_client)
    await control(env, tid, "rounds/1/start")
    assert (await state(ana[1], tid))["me"]["anticheat"]["armed"] is True
    r = await _report(ana, tid, kind="blur")
    assert r.json() == {"armed": False, "locked": True, "kind": "blur"}

    blocked = await submit(ana[1], ana[2], tid, 1, "ac-q1")
    assert blocked.status_code == 403 and blocked.json()["error"] == "tournament.locked"
    assert (await ana[1].get(f"/api/tournaments/{tid}/hints/ac-q1/1")).status_code == 403
    assert (await submit(rui[1], rui[2], tid, 1, "ac-q1")).status_code < 300  # os colegas continuam a jogar
    assert (await state(ana[1], tid))["me"]["anticheat"]["locked"] is True  # recarregar a página não liberta

    admin = await control(env, tid, f"anticheat/{ana[0].id}/release")
    assert admin["incidents"] == []
    assert (await state(ana[1], tid))["me"]["anticheat"] == {"armed": True, "locked": False, "kind": None}
    assert (await submit(ana[1], ana[2], tid, 1, "ac-q1")).status_code < 300


async def test_report_is_idempotent_and_counts_offences(make_user, make_class, new_client):
    env, tid, ana, _ = await _setup(make_user, make_class, new_client)
    await control(env, tid, "rounds/1/start")
    await _report(ana, tid, "cliente-0001")
    await _report(ana, tid, "cliente-0001")
    await _report(ana, tid, "cliente-0002", "hidden")  # já bloqueado: não abre outro
    assert len(await events_of(tid, "anticheat_locked")) == 1
    await control(env, tid, f"anticheat/{ana[0].id}/release")
    assert (await _report(ana, tid, "cliente-0001")).json()["locked"] is False  # um reenvio atrasado não volta a bloquear
    await _report(ana, tid, "cliente-0003")
    admin = (await env.t_client.get(f"/api/tournaments/{tid}/admin")).json()
    assert [(i["user_id"], i["kind"], i["offences"]) for i in admin["incidents"]] == [(ana[0].id, "paste", 2)]
    assert admin["tournament"]["incidents_pending"] == 1


async def test_only_the_student_and_teacher_hear_about_it(make_user, make_class, new_client):
    env, tid, ana, rui = await _setup(make_user, make_class, new_client)
    await control(env, tid, "rounds/1/start")
    await _report(ana, tid)
    types = lambda res: [e["type"] for e in res.json()["events"]]
    assert "anticheat_locked" in types(await ana[1].get(f"/api/tournaments/{tid}/events?after=0"))
    assert "anticheat_locked" in types(await env.t_client.get(f"/api/tournaments/{tid}/events?after=0"))
    assert "anticheat_locked" not in types(await rui[1].get(f"/api/tournaments/{tid}/events?after=0"))
    assert "incidents_pending" not in (await state(rui[1], tid))["tournament"]


async def test_students_cannot_release_and_finish_unlocks(make_user, make_class, new_client):
    env, tid, ana, rui = await _setup(make_user, make_class, new_client)
    await control(env, tid, "rounds/1/start")
    await _report(ana, tid)
    r = await rui[1].post(f"/api/tournaments/{tid}/anticheat/{ana[0].id}/release", json={}, headers=rui[2])
    assert r.status_code == 403
    await control(env, tid, f"anticheat/{rui[0].id}/release", expect=404)
    await control(env, tid, "finish")
    assert (await state(ana[1], tid))["me"]["anticheat"]["locked"] is False


async def test_invalid_kind_is_rejected(make_user, make_class, new_client):
    env, tid, ana, _ = await _setup(make_user, make_class, new_client)
    await control(env, tid, "rounds/1/start")
    assert (await _report(ana, tid, kind="outro")).status_code == 422


async def test_font_preference(make_user, new_client):
    from tests.conftest import login
    await make_user("leitora")
    c = new_client()
    h = await login(c, "leitora")
    r = await c.patch("/api/me/preferences", json={"preferred_font": "leitura"}, headers=h)
    assert r.status_code == 200 and r.json()["user"]["preferred_font"] == "leitura"
    assert (await c.patch("/api/me/preferences", json={"preferred_font": "comic"}, headers=h)).status_code == 422
    r = await c.patch("/api/me/preferences", json={"preferred_font": None}, headers=h)
    assert r.json()["user"]["preferred_font"] is None
