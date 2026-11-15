# Ajudantes partilhados pelos testes do torneio: problemas de teste (quiz = corrigidos na app, sem runner),
# criação de professor + turma + alunos com sessões próprias, e pequenos atalhos para a API.
import itertools
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select

from app.db import SessionLocal
from app.models.problem import Problem
from app.models.user import Role
from app.services.problems import ProblemSpec
from tests.conftest import login

_codes = itertools.count(1)
PISTA = {"pt": "Pista de teste", "en": "Test hint"}


def spec_dict(slug, *, tipo="quiz", bloco="7", dif=1, estado="aprovado", origem="novo", pistas=1) -> dict:
    base = {
        "id": slug, "titulo": {"pt": "Teste", "en": "Test"}, "tipo": tipo, "bloco": bloco,
        "regiao": "floresta", "dificuldade": dif, "origem": origem, "estado": estado,
        "enunciado": {"pt": "Enunciado", "en": "Statement"}, "pistas": [PISTA] * pistas,
    }
    if tipo == "quiz":
        base["perguntas"] = [{"pergunta": {"pt": "Qual?", "en": "Which?"}, "resposta_texto": "ok"}]
    elif tipo == "funcao":
        base.update(
            assinatura="f(x)", exemplos=[{"args": [1], "devolve": 1}], testes=[{"args": [2], "devolve": 2}],
            solucao_referencia="def f(x):\n    return x\n",
        )
    else:  # programa / bug
        base.update(
            exemplos=[{"stdin": "1\n", "stdout": "1"}], testes=[{"stdin": "2\n", "stdout": "2"}],
            solucao_referencia="print(input())\n",
        )
        if tipo == "bug":
            base["codigo_inicial"] = "print(input())\n"
    return base


async def add_problem(slug, **kw) -> None:
    data = ProblemSpec.model_validate(spec_dict(slug, **kw)).model_dump(mode="json")
    async with SessionLocal() as db:
        db.add(Problem(slug=slug, data=data, estado=data["estado"], bloco=data["bloco"], tipo=data["tipo"]))
        await db.commit()


@dataclass
class Env:
    teacher: object
    t_client: object
    t_headers: dict
    class_id: int
    students: list = field(default_factory=list)  # [(user, client, headers)]

    async def student(self, make_user, new_client, name, class_id=None):
        u = await make_user(name, class_id=class_id or self.class_id, display_name=name.capitalize())
        c = new_client()
        h = await login(c, name)
        self.students.append((u, c, h))
        return u, c, h


async def make_env(make_user, make_class, new_client, teacher="profa") -> Env:
    t = await make_user(teacher, Role.teacher)
    cls = await make_class(t.id, code=f"C{next(_codes):05d}".replace("0", "A"))
    c = new_client()
    h = await login(c, teacher)
    return Env(t, c, h, cls.id)


async def create_tournament(env: Env, mode="agencias", name="Torneio") -> dict:
    r = await env.t_client.post("/api/tournaments", json={"class_id": env.class_id, "name": name, "mode": mode, "format": "aula"}, headers=env.t_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def set_round(env: Env, tid: int, idx: int, slugs: list[str], **kw) -> dict:
    r = await env.t_client.put(f"/api/tournaments/{tid}/rounds/{idx}", json={"problem_slugs": slugs, **kw}, headers=env.t_headers)
    assert r.status_code == 200, r.text
    return r.json()


async def control(env: Env, tid: int, path: str, body: dict | None = None, expect=200) -> dict:
    r = await env.t_client.post(f"/api/tournaments/{tid}/{path}", json=body or {}, headers=env.t_headers)
    assert r.status_code == expect, (path, r.status_code, r.text)
    return r.json()


async def submit(client, headers, tid, idx, slug, answer="ok", cid=None):
    return await client.post("/api/submissions", json={
        "client_id": str(cid or uuid.uuid4()), "problem_slug": slug, "answers": [answer],
        "tournament_id": tid, "round_idx": idx,
    }, headers=headers)


async def state(client, tid) -> dict:
    r = await client.get(f"/api/tournaments/{tid}/state")
    assert r.status_code == 200, r.text
    return r.json()


async def events_of(tid: int, type_: str | None = None) -> list:
    from app.models.tournament import TournamentEvent
    async with SessionLocal() as db:
        q = select(TournamentEvent).where(TournamentEvent.tournament_id == tid).order_by(TournamentEvent.seq)
        rows = (await db.execute(q)).scalars().all()
    return [e for e in rows if type_ is None or e.type == type_]


# ---------------- Eliminatória ----------------
async def create_elim(env: Env, name="Elim", **kw) -> dict:
    r = await env.t_client.post("/api/tournaments", json={"class_id": env.class_id, "name": name, **kw}, headers=env.t_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def add_players(tid: int, users) -> None:
    from app.models.tournament import TournamentPlayer
    async with SessionLocal() as db:
        db.add_all(TournamentPlayer(tournament_id=tid, user_id=u.id) for u in users)
        await db.commit()


async def round_row(tid: int, idx: int):
    from app.models.tournament import TournamentRound
    async with SessionLocal() as db:
        return (await db.execute(select(TournamentRound).where(TournamentRound.tournament_id == tid, TournamentRound.idx == idx))).scalar_one()


async def fake_submit(tid: int, idx: int, user_id: int, slug: str, status: str, passed: int, total: int = 4, at=None) -> int:
    """Cria uma submissão de torneio já corrigida (sem runner) e corre o hook de pontuação."""
    from app.models._base import utcnow
    from app.models.submission import Submission
    from app.models.tournament import TournamentSubmission
    from app.services import tournament_scoring
    rnd = await round_row(tid, idx)
    at = at or utcnow()
    async with SessionLocal() as db:
        s = Submission(client_id=uuid.uuid4(), user_id=user_id, problem_slug=slug, code="print(1)", mode="tournament", status=status,
                       passed=passed, total=total, created_at=at, finished_at=at)
        db.add(s)
        await db.flush()
        db.add(TournamentSubmission(submission_id=s.id, tournament_id=tid, round_id=rnd.id, received_at=at))
        await db.commit()
        sid = s.id
    await tournament_scoring.on_submission_finished(sid)
    return sid


async def ledger(user_id: int | None = None, tid: int | None = None) -> list:
    from app.models.points import UserPoints
    async with SessionLocal() as db:
        q = select(UserPoints)
        if user_id is not None:
            q = q.where(UserPoints.user_id == user_id)
        if tid is not None:
            q = q.where(UserPoints.tournament_id == tid)
        return list((await db.execute(q)).scalars())


async def total_points(user_id: int) -> int:
    return sum(p.points for p in await ledger(user_id))


async def admin(env: Env, tid: int) -> dict:
    r = await env.t_client.get(f"/api/tournaments/{tid}/admin")
    assert r.status_code == 200, r.text
    return r.json()
