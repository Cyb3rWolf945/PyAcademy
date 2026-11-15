# Testes de problemas: vista pública sem segredos, rascunhos escondidos e sincronização YAML -> BD.
import json
import shutil

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models.user import Role
from app.services.problems import sync_problems
from tests.conftest import login
from tests.fakes import FUNCAO_GERADOR, QUIZ, write_problem

pytestmark = pytest.mark.asyncio
FORBIDDEN = ("testes", "solucao_referencia", "solucao_ingenua", "editorial", "erros_comuns", "resposta", "resposta_texto", "args_gerador")


async def _sync(root=None):
    async with SessionLocal() as db:
        return await sync_problems(db, root or settings.problems_dir)


async def test_sync_loads_samples():
    assert await _sync() >= 2


async def test_public_view_never_leaks_secrets(client, make_user):
    await _sync()
    await make_user("aluno")
    await login(client, "aluno")
    for slug in ("autocarro-ainda-da", "calcular-media"):
        r = await client.get(f"/api/problems/{slug}")
        assert r.status_code == 200
        body = r.json()
        for key in FORBIDDEN:
            assert key not in body and f'"{key}"' not in json.dumps(body)
        assert body["exemplos"] and set(body["titulo"]) == {"pt", "en"}
        assert "minutos_autocarro = 0" not in json.dumps(body)  # texto da solução
    # o teste escondido "7\n5\n" -> "Corre!" não aparece nos exemplos
    ex = (await client.get("/api/problems/autocarro-ainda-da")).json()["exemplos"]
    assert all(e["stdin"] != "7\n5\n" for e in ex)


async def test_listing_and_not_found(client, make_user):
    await _sync()
    await make_user("aluno")
    await login(client, "aluno")
    ids = {p["id"] for p in (await client.get("/api/problems")).json()["problems"]}
    assert {"autocarro-ainda-da", "calcular-media"} <= ids
    r = await client.get("/api/problems/nao-existe")
    assert r.status_code == 404 and r.json() == {"error": "problem.not_found"}


async def test_draft_hidden_from_students_visible_to_teacher(new_client, make_user, tmp_path):
    src = settings.problems_dir / "block4" / "autocarro-ainda-da.yaml"
    text = src.read_text(encoding="utf-8").replace("id: autocarro-ainda-da", "id: rascunho-x").replace("estado: aprovado", "estado: rascunho")
    (tmp_path / "rascunho.yaml").write_text(text, encoding="utf-8")
    await _sync(tmp_path)
    await make_user("aluno")
    await make_user("prof1", Role.teacher)
    async with new_client() as s, new_client() as t:
        await login(s, "aluno")
        await login(t, "prof1")
        assert (await s.get("/api/problems/rascunho-x")).status_code == 404
        assert (await t.get("/api/problems/rascunho-x")).status_code == 200
        assert "rascunho-x" not in {p["id"] for p in (await s.get("/api/problems")).json()["problems"]}


async def test_problems_require_login(client):
    assert (await client.get("/api/problems/calcular-media")).status_code == 401


async def test_sync_skips_invalid_yaml(tmp_path):
    shutil.copy(settings.problems_dir / "block6" / "calcular-media.yaml", tmp_path / "ok.yaml")
    (tmp_path / "bad.yaml").write_text("id: x\n", encoding="utf-8")
    assert await _sync(tmp_path) == 1


async def test_public_view_of_questions_strips_answers(client, make_user, tmp_path):
    write_problem(tmp_path, "quiz-y", QUIZ, tipo="quiz", bloco="3", regiao="mercado")
    await _sync(tmp_path)
    await make_user("aluno")
    await login(client, "aluno")
    body = (await client.get("/api/problems/quiz-y")).json()
    assert len(body["perguntas"]) == 2 and body["exemplos"] == []
    assert body["perguntas"][0]["opcoes"] and body["perguntas"][1]["codigo"] == "soma = 1 + 2"
    blob = json.dumps(body)
    for key in ("resposta", "resposta_texto", "solucao_referencia", "testes"):
        assert f'"{key}"' not in blob
    assert '"3"' not in blob.replace('"bloco": "3"', "")  # o texto da resposta certa não sai


def _spec(tmp_path, name, body, **kw):
    from app.services.problems import parse_yaml
    return parse_yaml(write_problem(tmp_path, name, body, **kw))


FUNCAO_OK = FUNCAO_GERADOR.replace("  - {args: [[]], devolve: 0}\n", "  - {args: [[]], devolve: 0}\n")


async def test_schema_rules(tmp_path):
    import pytest
    from pydantic import ValidationError

    def bad(body, **kw):
        with pytest.raises(ValidationError):
            _spec(tmp_path, "x-x", body, **kw)

    ex = 'exemplos: [{stdin: "", stdout: "1"}]\ntestes: [{stdin: "", stdout: "1"}]\nsolucao_referencia: "print(1)"\n'
    assert _spec(tmp_path, "ok-ok", ex).bloco == "2"
    bad(ex, bloco="9")  # bloco fora do curriculum.yaml
    bad(ex, regiao="oficina")  # região inexistente
    bad(ex, tipo="bug")  # bug sem codigo_inicial
    assert _spec(tmp_path, "bug-ok", ex + "codigo_inicial: print(2)\n", tipo="bug")
    bad(QUIZ + ex, tipo="quiz")  # quiz não leva exemplos/testes/solução
    bad("", tipo="quiz")  # quiz sem perguntas
    bad(ex + QUIZ)  # programa não leva perguntas
    bad(QUIZ.replace("resposta: [0, 2]", "resposta: [0, 7]"), tipo="quiz")  # índice fora das opções
    bad(QUIZ.replace('    resposta_texto: "3"\n', '    resposta_texto: "3"\n    resposta: [0]\n    opcoes: [a]\n'), tipo="quiz")
    assert _spec(tmp_path, "mais-ok", ex, bloco="mais_alem", regiao="ilhas")
    bad(ex + "requisitos: {inventado: 1}\n")
    # algoritmia
    algo = FUNCAO_GERADOR + "nivel_algo: hard\n"
    bad(algo, tipo="funcao", bloco="mais_alem", regiao="ilhas")  # falta ingénua + editorial
    ok = algo + "solucao_ingenua: 'def soma_lista(xs):\\n    return 0'\neditorial: {pt: a, en: b}\n"
    assert _spec(tmp_path, "algo-ok", ok, tipo="funcao", bloco="mais_alem", regiao="ilhas").nivel_algo == "hard"
    bad(ok.replace("assinatura: soma_lista(xs)\n", ""), tipo="programa")
    # geradores: nunca nos exemplos, nunca com args/devolve
    bad(FUNCAO_GERADOR.replace("{args: [[1, 2, 3]], devolve: 6}", '{args_gerador: "[[1]]"}'), tipo="funcao", bloco="7", regiao="cidadela")
    bad(FUNCAO_GERADOR.replace('args_gerador: "[list(range(5000))]"', 'args_gerador: "[[1]]"\n    devolve: 1'), tipo="funcao", bloco="7", regiao="cidadela")
