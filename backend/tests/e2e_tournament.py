# Teste ponta a ponta MANUAL do torneio contra a stack real (passa pelo Caddy, por isso valida o upgrade do WebSocket).
# Cria turma + 6 alunos, um torneio em agências, 2 agências, inicia a R1, um aluno submete uma solução certa e
# verifica que os WebSockets (aluno e projetor) recebem round_started, mission_solved e leaderboard.
# Correr (dentro de um contentor da rede do compose):
#   docker compose run --rm -w /app -e E2E_BASE=http://proxy -e E2E_ORIGIN=http://localhost:8080 \
#     -e DEV_TEST_TEACHER_PASSWORD=<palavra-passe> app python backend/tests/e2e_tournament.py
# Do anfitrião (precisa de httpx + websockets instalados): E2E_BASE=http://localhost:8080 python e2e_tournament.py
import asyncio
import json
import os
import sys
import time
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


def step(msg):
    print(f"[e2e] {msg}", flush=True)


def check(cond, msg):
    if not cond:
        print(f"[e2e] FALHOU: {msg}", flush=True)
        sys.exit(1)
    step(f"ok: {msg}")


class User:
    def __init__(self, name):
        self.name, self.c, self.h = name, httpx.AsyncClient(base_url=BASE, headers={"Origin": ORIGIN}, timeout=20), {}

    async def login(self, username, password):
        r = await self.c.post("/api/auth/login", json={"username": username, "password": password})
        check(r.status_code == 200, f"login {username} ({r.status_code})")
        self.h = {"X-CSRF-Token": r.json()["csrf_token"]}
        return r.json()["user"]

    async def join_class(self, code, username):
        r = await self.c.post("/api/auth/join", json={"join_code": code, "username": username, "display_name": username.split("_")[-1].capitalize(), "password": "e2e-password-1"})
        check(r.status_code == 200, f"aluno {username} entrou na turma ({r.status_code} {r.text[:80]})")
        self.h = {"X-CSRF-Token": r.json()["csrf_token"]}
        return r.json()["user"]

    async def post(self, url, body=None):
        return await self.c.post(url, json=body or {}, headers=self.h)

    def ws(self, tid):
        cookie = "; ".join(f"{k}={v}" for k, v in self.c.cookies.items())
        return connect(f"{WS_BASE}/ws/tournaments/{tid}", additional_headers={"Origin": ORIGIN, "Cookie": cookie}, open_timeout=8)


async def collect(ws, sink, label):
    try:
        async for raw in ws:
            m = json.loads(raw)
            sink.append(m)
            if m.get("type") in ("round_started", "mission_solved", "leaderboard", "first_bonus"):
                step(f"{label} <- {m['type']} seq={m.get('seq')}")
    except Exception:  # noqa: BLE001
        pass


async def wait_for(sink, type_, timeout=15):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for m in sink:
            if m.get("type") == type_:
                return m
        await asyncio.sleep(0.1)
    return None


def reference_solution(slug):
    for p in PROBLEMS.rglob("*.yaml"):
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        if spec.get("id") == slug:
            sol = spec["solucao_referencia"]
            return sol if isinstance(sol, str) else sol["pt"]
    raise SystemExit(f"problema {slug} nao encontrado")


async def main():
    check(bool(PASSWORD), "DEV_TEST_TEACHER_PASSWORD definido")
    teacher = User("prof")
    await teacher.login(TEACHER, PASSWORD)
    r = await teacher.post("/api/classes", {"name": f"E2E {RUN}"})
    check(r.status_code == 201, "turma criada")
    code = r.json()["join_code"]
    students = [User(f"s{i}") for i in range(6)]
    for i, s in enumerate(students):
        await s.join_class(code, f"e2e{RUN}_aluno{i}")
    r = await teacher.post("/api/tournaments", {"class_id": r.json()["id"], "name": f"E2E {RUN}", "mode": "agencias"})
    check(r.status_code == 201, f"torneio criado: {r.status_code}")
    admin = r.json()
    tid, jcode = admin["tournament"]["id"], admin["tournament"]["join_code"]
    check(len(admin["rounds"]) == 6, "5 rondas + boss")
    step("rondas: " + ", ".join(f"R{x['idx']}={x['problem_slugs']}" for x in admin["rounds"]))
    for s in students:
        r = await s.post("/api/tournaments/join", {"join_code": jcode})
        check(r.status_code == 200 and r.json()["tournament_id"] == tid, "aluno entrou no torneio")
    r = await students[0].post(f"/api/tournaments/{tid}/teams", {"name": "Gatos"})
    gatos = r.json()["teams"][0]["id"]
    for s in students[1:3]:
        check((await s.post(f"/api/tournaments/{tid}/teams/{gatos}/join")).status_code == 200, "aluno entrou na agência Gatos")
    r = await students[3].post(f"/api/tournaments/{tid}/teams", {"name": "Foguetoes"})
    fog = [t for t in r.json()["teams"] if t["name"] == "Foguetoes"][0]["id"]
    for s in students[4:]:
        check((await s.post(f"/api/tournaments/{tid}/teams/{fog}/join")).status_code == 200, "aluno entrou na agência Foguetoes")

    got_student, got_proj = [], []
    async with students[0].ws(tid) as ws_s, teacher.ws(tid) as ws_p:
        check(True, "WebSockets abertos através do proxy")
        tasks = [asyncio.create_task(collect(ws_s, got_student, "aluno")), asyncio.create_task(collect(ws_p, got_proj, "projetor"))]
        await ws_s.send(json.dumps({"type": "ping", "last_seq": 0}))
        await asyncio.sleep(0.5)
        r = await teacher.post(f"/api/tournaments/{tid}/rounds/1/start")
        check(r.status_code == 200, "R1 iniciada")
        check(await wait_for(got_student, "round_started") is not None, "aluno recebeu round_started")
        check(await wait_for(got_proj, "round_started") is not None, "projetor recebeu round_started")
        st = (await students[0].c.get(f"/api/tournaments/{tid}/state")).json()
        missions = [m for m in st["current"]["missions"] if m["tipo"] in ("programa", "funcao", "bug")]
        check(bool(missions), "ronda tem missões de código")
        slug = missions[0]["slug"]
        import uuid
        r = await students[0].post("/api/submissions", {
            "client_id": str(uuid.uuid4()), "problem_slug": slug, "code": reference_solution(slug), "tournament_id": tid, "round_idx": 1,
        })
        check(r.status_code == 202, f"submissão aceite para correção ({r.status_code} {r.text[:80]})")
        sid = r.json()["id"]
        for _ in range(60):
            sub = (await students[0].c.get(f"/api/submissions/{sid}")).json()
            if sub["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(0.5)
        check(sub["status"] == "accepted", f"solução correta de {slug}: {sub['status']} {sub.get('passed')}/{sub.get('total')}")
        for label, sink in (("aluno", got_student), ("projetor", got_proj)):
            ms = await wait_for(sink, "mission_solved")
            check(ms is not None and ms["payload"]["slug"] == slug, f"{label} recebeu mission_solved ({ms and ms['payload']})")
        await asyncio.sleep(1.5)
        boards = [m for m in got_proj if m["type"] == "leaderboard"]
        check(bool(boards) and boards[-1]["payload"]["leaderboard"][0]["points"] > 0, "projetor recebeu leaderboard com pontos")
        r = await students[1].c.get(f"/api/tournaments/{tid}/state")
        check("join_code" not in r.text and jcode not in r.text, "snapshot do aluno não tem o código de entrada")
        await teacher.post(f"/api/tournaments/{tid}/finish")
        check(await wait_for(got_student, "tournament_finished") is not None, "aluno recebeu tournament_finished")
        for t in tasks:
            t.cancel()
    for u in [teacher, *students]:
        await u.c.aclose()
    step("TUDO OK")


asyncio.run(main())
