# Testes das submissões: idempotência, limite de ritmo, tipos sem código, dispatcher (fila, recuperação,
# runner em baixo), pistas e geradores de testes. O runner é o código real, chamado em processo.
import json
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.config import settings
from app.db import SessionLocal
from app.models._base import utcnow
from app.models.problem import Problem
from app.models.submission import HintUse, Job, Submission
from app.services import dispatcher, runner_client
from app.services.problems import sync_problems
from tests.conftest import login
from tests.fakes import FUNCAO_GERADOR, QUIZ, local_post, write_problem

pytestmark = pytest.mark.asyncio
GOOD = 'a = int(input())\nb = int(input())\nf = a - b\nif f > 2:\n    print("Vai a andar")\nelif f >= 0:\n    print("Corre!")\nelse:\n    print("Pede boleia")\n'


async def _sync(root=None):
    async with SessionLocal() as db:
        return await sync_problems(db, root or settings.problems_dir)


async def _drain(post=local_post):
    while await dispatcher.run_once(post):
        pass


async def _student(client, make_user, name="aluno"):
    await make_user(name)
    return await login(client, name)


def body(code=GOOD, slug="autocarro-ainda-da", cid=None, **kw):
    return {"client_id": str(cid or uuid.uuid4()), "problem_slug": slug, "code": code, "hints_used": 0, **kw}


async def test_idempotent_same_client_id(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    cid = uuid.uuid4()
    a = await client.post("/api/submissions", json=body(cid=cid), headers=h)
    b = await client.post("/api/submissions", json=body(cid=cid, code="print(1)"), headers=h)
    assert a.status_code == b.status_code == 202 and a.json()["id"] == b.json()["id"]
    assert a.json()["status"] == "queued" and a.json()["queue_position"] == 1
    async with SessionLocal() as db:
        assert len((await db.execute(select(Submission))).scalars().all()) == 1
        assert len((await db.execute(select(Job))).scalars().all()) == 1


async def test_rate_limit_6_per_minute(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    for _ in range(6):
        assert (await client.post("/api/submissions", json=body(), headers=h)).status_code == 202
    r = await client.post("/api/submissions", json=body(), headers=h)
    assert r.status_code == 429 and r.json() == {"error": "submission.rate_limited"}


async def test_validation_errors_and_ownership(client, new_client, make_user):
    await _sync()
    h = await _student(client, make_user)
    r = await client.post("/api/submissions", json=body(code=""), headers=h)
    assert r.status_code == 422 and r.json()["error"] == "submission.code_required"
    r = await client.post("/api/submissions", json=body(code="x = 1\n" * 4000), headers=h)
    assert r.json()["error"] == "submission.code_too_large"
    assert (await client.post("/api/submissions", json=body(slug="nao-existe"), headers=h)).json()["error"] == "problem.not_found"
    sid = (await client.post("/api/submissions", json=body(), headers=h)).json()["id"]
    await make_user("outro")
    async with new_client() as other:
        await login(other, "outro")
        r = await other.get(f"/api/submissions/{sid}")
        assert r.status_code == 404 and r.json()["error"] == "submission.not_found"
    assert (await client.get(f"/api/submissions/{sid}")).status_code == 200
    assert (await client.post("/api/submissions", json=body())).status_code in (401, 403)  # sem CSRF/sessão válida


async def test_end_to_end_accepted_and_no_hidden_leak(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    sid = (await client.post("/api/submissions", json=body(), headers=h)).json()["id"]
    await _drain()
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "accepted" and r["passed"] == r["total"] == 4 and r["finished_at"]
    # resposta errada: só estado nos escondidos
    wrong = (await client.post("/api/submissions", json=body(code='print("Corre!")'), headers=h)).json()["id"]
    await _drain()
    r = (await client.get(f"/api/submissions/{wrong}")).json()
    assert r["status"] == "wrong_answer" and r["passed"] < r["total"]
    blob = json.dumps(r)
    for secret in ("Pede boleia", "Hitch a ride", "7\\n5", '"stdin": "4'):
        assert secret not in blob
    hidden = [c for c in r["result"]["cases"] if not c["visible"]]
    assert hidden and all(set(c) == {"index", "visible", "status", "passed", "runtime_ms"} for c in hidden)
    assert r["result"]["cases"][0]["visible"] and r["result"]["cases"][0]["expected"]


async def test_classic_hint_key_for_runtime_error(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    sid = (await client.post("/api/submissions", json=body(code="print(1 / 0)"), headers=h)).json()["id"]
    await _drain()
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "runtime_error" and r["result"]["hint_key"] == "feedback.zero_division"


async def test_requirements_unmet_end_to_end(client, make_user, tmp_path):
    write_problem(tmp_path, "usa-while", """
        exemplos: [{stdin: "", stdout: "6"}]
        testes: [{stdin: "", stdout: "6"}]
        comparacao: numeros
        requisitos: {usa: [while]}
        solucao_referencia: |
          total = 0
          i = 1
          while i < 4:
              total = total + i
              i = i + 1
          print(total)
        """, bloco="5", regiao="rio")
    await _sync(tmp_path)
    h = await _student(client, make_user)
    sid = (await client.post("/api/submissions", json=body("print(sum(range(1, 4)))", "usa-while"), headers=h)).json()["id"]
    await _drain()
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "requirements_unmet" and r["passed"] == r["total"]
    assert r["result"]["requirement_keys"] == [{"kind": "usa", "value": "while", "key": "requirement.usa"}]


async def test_non_code_tipos_graded_in_app(client, make_user, tmp_path):
    write_problem(tmp_path, "quiz-x", QUIZ, tipo="quiz", bloco="3", regiao="mercado")
    await _sync(tmp_path)
    h = await _student(client, make_user)
    ok = await client.post("/api/submissions", json={"client_id": str(uuid.uuid4()), "problem_slug": "quiz-x", "answers": [[2, 0], " 3 "]}, headers=h)
    assert ok.status_code == 202 and ok.json()["status"] == "accepted"
    bad = await client.post("/api/submissions", json={"client_id": str(uuid.uuid4()), "problem_slug": "quiz-x", "answers": [[0], "4"]}, headers=h)
    r = (await client.get(f"/api/submissions/{bad.json()['id']}")).json()
    assert r["status"] == "wrong_answer" and r["passed"] == 0 and r["total"] == 2
    assert r["result"]["questions"] == [False, False]
    invalid = await client.post("/api/submissions", json={"client_id": str(uuid.uuid4()), "problem_slug": "quiz-x", "answers": [[9], "3"]}, headers=h)
    assert invalid.status_code == 422 and invalid.json()["error"] == "submission.answers_invalid"
    async with SessionLocal() as db:
        assert (await db.execute(select(Job))).scalars().all() == []  # nunca passam pelo runner


async def test_dispatcher_recovers_stale_job(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    sid = (await client.post("/api/submissions", json=body(), headers=h)).json()["id"]
    async with SessionLocal() as db:  # simula um worker que morreu a meio
        row = await dispatcher.claim_job(db)
        assert row.submission_id == sid
        await db.execute(update(Job).where(Job.id == row.id).values(locked_at=utcnow() - timedelta(seconds=120)))
        await db.commit()
        assert await dispatcher.claim_job(db) is None  # preso: ninguém o apanha
        assert await dispatcher.recover_stale(db) == 1
    await _drain()
    assert (await client.get(f"/api/submissions/{sid}")).json()["status"] == "accepted"


async def test_runner_down_requeues_then_fails_after_max_attempts(client, make_user, monkeypatch):
    await _sync()
    h = await _student(client, make_user)
    sid = (await client.post("/api/submissions", json=body(), headers=h)).json()["id"]

    async def down(path, req, timeout=None):
        raise runner_client.RunnerError("down")

    async def no_sleep(_):
        return None
    monkeypatch.setattr(dispatcher.asyncio, "sleep", no_sleep)
    assert await dispatcher.run_once(down)
    assert (await client.get(f"/api/submissions/{sid}")).json()["status"] == "queued"  # não se perdeu
    await dispatcher.run_once(down)
    await dispatcher.run_once(down)
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "error" and r["result"] == {"error": "submission.runner_unavailable"}


async def test_skip_locked_gives_each_job_to_one_claimer(client, make_user):
    await _sync()
    await make_user("aluno")
    h = await login(client, "aluno")
    for _ in range(3):
        await client.post("/api/submissions", json=body(), headers=h)
    async with SessionLocal() as a, SessionLocal() as b:
        ra, rb = await dispatcher.claim_job(a), await dispatcher.claim_job(b)
        assert ra.id != rb.id


async def test_hints_recorded_and_counted(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    r = await client.get("/api/problems/autocarro-ainda-da/hints/1")
    assert r.status_code == 200 and set(r.json()["hint"]) == {"pt", "en"}
    assert (await client.get("/api/problems/autocarro-ainda-da/hints/9")).json() == {"error": "problem.hint_not_found"}
    async with SessionLocal() as db:
        assert len((await db.execute(select(HintUse))).scalars().all()) == 1
    await client.get("/api/problems/autocarro-ainda-da/hints/1")  # repetir não duplica
    sid = (await client.post("/api/submissions", json=body(hints_used=0), headers=h)).json()["id"]
    assert (await client.get(f"/api/submissions/{sid}")).json()["hints_used"] == 1  # o servidor não deixa o cliente baixar


async def test_args_gerador_expected_computed_cached_and_private(client, make_user, tmp_path):
    write_problem(tmp_path, "soma-gerada", FUNCAO_GERADOR, tipo="funcao", bloco="7", regiao="cidadela")
    await _sync(tmp_path)
    h = await _student(client, make_user)
    pub = (await client.get("/api/problems/soma-gerada")).json()
    assert "5000" not in json.dumps(pub) and "args_gerador" not in json.dumps({k: v for k, v in pub.items() if k != "exemplos"})
    code = "def soma_lista(xs):\n    return sum(xs)\n"
    sid = (await client.post("/api/submissions", json=body(code, "soma-gerada"), headers=h)).json()["id"]
    await _drain()
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "accepted" and r["total"] == 4, r
    async with SessionLocal() as db:
        gen = (await db.get(Problem, "soma-gerada")).generated  # cache no registo, nunca na vista pública
        assert gen["items"]["1"]["devolve"] == sum(range(5000))
    wrong = (await client.post("/api/submissions", json=body("def soma_lista(xs):\n    return len(xs)\n", "soma-gerada"), headers=h)).json()["id"]
    await _drain()
    assert (await client.get(f"/api/submissions/{wrong}")).json()["status"] == "wrong_answer"
    # alterar a referência invalida a cache (hash)
    async with SessionLocal() as db:
        from app.services.problems import ProblemSpec
        spec = ProblemSpec.model_validate((await db.get(Problem, "soma-gerada")).data)
        assert runner_client.generated_hash(spec) == gen["hash"]


async def test_nul_bytes_in_output_do_not_block_the_submission(client, make_user):
    await _sync()
    h = await _student(client, make_user)
    code = 'print("\\x00abc\\x01 \\x1b[31m")\n'
    sid = (await client.post("/api/submissions", json=body(code=code), headers=h)).json()["id"]
    await _drain()
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "wrong_answer" and r["finished_at"]
    actual = r["result"]["cases"][0]["actual"]
    assert "\x00" not in actual and "\ufffdabc" in actual
    async with SessionLocal() as db:
        assert (await db.execute(select(Job))).scalar_one().state == "done"


async def test_persistence_failure_ends_in_internal_error(client, make_user, monkeypatch):
    await _sync()
    h = await _student(client, make_user)
    sid = (await client.post("/api/submissions", json=body(), headers=h)).json()["id"]

    def boom(_resp):
        raise RuntimeError("falha a gravar")

    async def no_sleep(_):
        return None
    monkeypatch.setattr(dispatcher.feedback, "sanitize_result", boom)
    monkeypatch.setattr(dispatcher.asyncio, "sleep", no_sleep)
    await dispatcher.run_once(local_post)
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "queued"  # 1.ª falha: volta à fila
    await dispatcher.run_once(local_post)
    await dispatcher.run_once(local_post)
    r = (await client.get(f"/api/submissions/{sid}")).json()
    assert r["status"] == "internal_error" and r["result"] == {"error": "submission.internal_error"} and r["finished_at"]
    async with SessionLocal() as db:
        assert (await db.execute(select(Job))).scalar_one().state == "failed"
    assert await dispatcher.run_once(local_post) is False  # nada fica preso nem a repetir
