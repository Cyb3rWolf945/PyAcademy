# Teste ponta a ponta MANUAL da Eliminatória com 20 alunos, contra a stack real (passa pelo Caddy: valida o upgrade WS).
# 20 alunos -> 5 grupos de 4 -> 5 vencedores -> final -> campeão; confere eventos WS, pontos e leaderboard público.
# Correr:  docker compose run --rm -w /app -e E2E_BASE=http://proxy -e E2E_ORIGIN=http://localhost:8080 \
#            -e DEV_TEST_TEACHER_PASSWORD=<palavra-passe> app python backend/tests/e2e_eliminatoria.py
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import yaml
from websockets.asyncio.client import connect

BASE = os.environ.get("E2E_BASE", "http://localhost:8080")
ORIGIN = os.environ.get("E2E_ORIGIN", "http://localhost:8080")
TEACHER = os.environ.get("DEV_TEST_TEACHER_USERNAME", "prof_teste")
PASSWORD = os.environ.get("DEV_TEST_TEACHER_PASSWORD", "")
PROBLEMS = Path(os.environ.get("E2E_PROBLEMS", Path(__file__).resolve().parents[1] / "problems"))
WS_BASE = BASE.replace("http", "ws", 1)
RUN = str(int(time.time()))[-6:]
N = 20


def step(m):
    print(f"[e2e] {m}", flush=True)


def check(cond, m):
    if not cond:
        print(f"[e2e] FALHOU: {m}", flush=True)
        sys.exit(1)
    step(f"ok: {m}")


class U:
    def __init__(self):
        self.c, self.h, self.id, self.events = httpx.AsyncClient(base_url=BASE, headers={"Origin": ORIGIN}, timeout=30), {}, None, []

    async def auth(self, path, body):
        r = await self.c.post(path, json=body)
        check(r.status_code == 200, f"{path} ({r.status_code})")
        self.h, self.id = {"X-CSRF-Token": r.json()["csrf_token"]}, r.json()["user"]["id"]

    async def post(self, url, body=None):
        return await self.c.post(url, json=body or {}, headers=self.h)

    def ws(self, tid):
        cookie = "; ".join(f"{k}={v}" for k, v in self.c.cookies.items())
        return connect(f"{WS_BASE}/ws/tournaments/{tid}", additional_headers={"Origin": ORIGIN, "Cookie": cookie}, open_timeout=8)


async def collect(ws, sink):
    try:
        async for raw in ws:
            sink.append(json.loads(raw))
    except Exception:  # noqa: BLE001
        pass


def reference_solution(slug):
    for p in PROBLEMS.rglob("*.yaml"):
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        if spec.get("id") == slug:
            sol = spec["solucao_referencia"]
            return sol if isinstance(sol, str) else sol["pt"]
    raise SystemExit(f"problema {slug} nao encontrado")


async def wait_for(sink, type_, timeout=30, pred=lambda m: True):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for m in sink:
            if m.get("type") == type_ and pred(m):
                return m
        await asyncio.sleep(0.1)
    return None


async def solve(u, tid, idx, slug):
    r = await u.post("/api/submissions", {"client_id": str(uuid.uuid4()), "problem_slug": slug, "code": reference_solution(slug), "tournament_id": tid, "round_idx": idx})
    check(r.status_code == 202, f"submissão aceite para correção ({r.status_code} {r.text[:80]})")
    for _ in range(120):
        sub = (await u.c.get(f"/api/submissions/{r.json()['id']}")).json()
        if sub["status"] not in ("queued", "running"):
            return sub["status"]
        await asyncio.sleep(0.5)
    return "timeout"


async def main():
    check(bool(PASSWORD), "DEV_TEST_TEACHER_PASSWORD definido")
    teacher = U()
    await teacher.auth("/api/auth/login", {"username": TEACHER, "password": PASSWORD})
    cls = (await teacher.post("/api/classes", {"name": f"E2E elim {RUN}"})).json()
    students = [U() for _ in range(N)]
    for i, s in enumerate(students):
        await s.auth("/api/auth/join", {"join_code": cls["join_code"], "username": f"el{RUN}_a{i:02d}", "display_name": f"Aluno{i:02d}", "password": "e2e-password-1"})
    by_id = {s.id: s for s in students}
    r = await teacher.post("/api/tournaments", {"class_id": cls["id"], "name": f"Elim {RUN}"})  # formato por omissão
    check(r.status_code == 201 and r.json()["format"] == "eliminatoria", "torneio Eliminatória criado por omissão")
    tid, code = r.json()["tournament"]["id"], r.json()["tournament"]["join_code"]
    for s in students:
        check((await s.post("/api/tournaments/join", {"join_code": code})).status_code == 200, "aluno entrou") if s is students[0] else await s.post("/api/tournaments/join", {"join_code": code})
    pv = (await teacher.c.get(f"/api/tournaments/{tid}/bracket-preview")).json()
    check([(x["groups"], x["advancing"], x["is_final"]) for x in pv["rounds"]] == [(5, 5, False), (1, 1, True)], f"pré-visualização: {pv['rounds']}")
    r = await teacher.c.get(f"/api/tournaments/{tid}/state")
    check(r.json()["players_count"] == N, f"{N} alunos no lobby")
    sinks = {s.id: [] for s in students}
    tsink = []
    stack = []
    tasks = []
    for s in students:
        w = s.ws(tid)
        sock = await w.__aenter__()
        stack.append(w)
        tasks.append(asyncio.create_task(collect(sock, sinks[s.id])))
    tw = teacher.ws(tid)
    tsock = await tw.__aenter__()
    tasks.append(asyncio.create_task(collect(tsock, tsink)))
    check(True, "21 WebSockets abertos através do proxy")
    admin = (await teacher.post(f"/api/tournaments/{tid}/rounds/next/start")).json()
    g1 = admin["rounds"][0]["groups"]
    slug1 = admin["rounds"][0]["problem_slugs"][0]
    check([len(g["members"]) for g in g1] == [4] * 5, "5 grupos de 4")
    check(await wait_for(tsink, "groups_drawn") is not None, "projetor recebeu groups_drawn")
    winners = []
    for g in g1:
        w = g["members"][0]["user_id"]
        winners.append(w)
        check(await solve(by_id[w], tid, 1, slug1) == "accepted", f"R1 {slug1} resolvido por {w}")
    check(await wait_for(tsink, "round_closed", 20) is not None, "R1 fechou sozinha (todos os grupos decididos)")
    check(len([m for m in tsink if m["type"] == "group_decided"]) == 5, "5 eventos group_decided")
    check(await wait_for(sinks[winners[0]], "points_awarded", 10) is not None, "vencedor recebeu points_awarded")
    loser = next(s for s in students if s.id not in winners)
    await asyncio.sleep(0.5)
    check(not any(m["type"] == "points_awarded" and m["payload"]["user_id"] != loser.id for m in sinks[loser.id]), "eliminado não vê pontos alheios")
    st = (await teacher.c.get(f"/api/tournaments/{tid}/admin")).json()
    check(st["alive_count"] == 5 and st["rounds"][1]["is_final"], "5 em jogo e a final está preparada")
    slug2 = st["rounds"][1]["problem_slugs"][0]
    admin = (await teacher.post(f"/api/tournaments/{tid}/rounds/next/start")).json()
    check(len(admin["rounds"][1]["groups"]) == 1 and len(admin["rounds"][1]["groups"][0]["members"]) == 5, "final com 5")
    # um eliminado treina o exercício da R1? (R1 fechada: dentro da tolerância de 30 s)
    check(await solve(loser, tid, 1, slug1) in ("accepted", "wrong_answer"), "eliminado treina (modo treino)")
    champ = winners[2]
    check(await solve(by_id[champ], tid, 2, slug2) == "accepted", f"final {slug2} resolvida")
    check(await wait_for(tsink, "champion", 20) is not None, "campeão anunciado")
    m = await wait_for(sinks[champ], "points_awarded", 10, lambda m: m["payload"]["reason"] == "champion")
    check(m is not None and m["payload"]["points"] == 100, "campeão recebeu +100")
    fin = (await teacher.c.get(f"/api/tournaments/{tid}/admin")).json()
    check(fin["tournament"]["state"] == "finished" and fin["champion"]["user_id"] == champ and fin["podium"][0]["user_id"] == champ, "estado final e pódio")
    ss = (await by_id[champ].c.get(f"/api/tournaments/{tid}/state")).json()
    check(ss["me"]["status"] == "champion" and ss["my_points_this_tournament"] > 100 and code not in json.dumps(ss), "snapshot do campeão (sem código de entrada)")
    await by_id[champ].c.patch("/api/me/preferences", json={"show_in_leaderboard": True}, headers=by_id[champ].h)
    lb = (await httpx.AsyncClient(base_url=BASE).get("/api/leaderboard/public?period=week")).json()
    check(any(e["display_name"] == f"Aluno{students.index(by_id[champ]):02d}" for e in lb["entries"]) and "username" not in json.dumps(lb), "leaderboard público mostra o campeão (sem username)")
    me = (await by_id[champ].c.get("/api/leaderboard/me")).json()
    check(me["visible"] and me["rank"] >= 1, f"/leaderboard/me: {me}")
    for t in tasks:
        t.cancel()
    for w in stack:
        await w.__aexit__(None, None, None)
    await tw.__aexit__(None, None, None)
    step("TUDO OK")


asyncio.run(main())
