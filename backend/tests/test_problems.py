# Testes de problemas: vista pública sem segredos, rascunhos escondidos e sincronização YAML -> BD.
import json
import shutil

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models.user import Role
from app.services.problems import sync_problems
from tests.conftest import login

pytestmark = pytest.mark.asyncio
FORBIDDEN = ("testes", "solucao_referencia", "solucao_ingenua", "editorial", "erros_comuns")


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
