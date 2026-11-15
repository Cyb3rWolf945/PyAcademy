# Testes da Academia: validador de conteúdos, desbloqueio híbrido, vista pública sem respostas, correção de cada tipo,
# pontos idempotentes (pista = metade, badge e streak uma só vez), rate limit e slides (sessão, path traversal).
import asyncio
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models.academy import SlideDeck
from app.models.points import UserPoints
from app.services import academy, academy_content, leaderboard
from app.tools import validate_academy
from tests.conftest import login

pytestmark = pytest.mark.asyncio
FIX = Path(__file__).parent / "fixtures" / "academy"
REAL = Path(__file__).resolve().parents[1] / "content" / "academy"


@pytest.fixture(autouse=True)
def _content(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "academy_dir", FIX)
    monkeypatch.setattr(settings, "slides_dir", tmp_path / "slides")
    monkeypatch.setattr(academy, "open_blocks", lambda: set())
    monkeypatch.setattr(academy, "today_lisbon", lambda: date(2026, 11, 16))
    academy._recent.clear()


async def _user(make_user, new_client, name="ana", class_id=None):
    await make_user(name, class_id=class_id)
    c = new_client()
    return c, await login(c, name)


async def _points(name_or_id) -> dict:
    async with SessionLocal() as db:
        rows = (await db.execute(select(UserPoints))).scalars().all()
    out: dict = {}
    for r in rows:
        out.setdefault(r.reason, []).append((r.problem_slug, r.points))
    return out


CORRECT = {
    "m0-01-primeira": [
        {"pares": {"s2": "s2", "s3": "s3", "s4": "s4"}}, {"ordem": ["s1", "s2", "s3", "s4"]}, {"ordem": ["s2", "s3", "s4"]},
    ],
    "m0-02-segunda": [{"valores": ["2"]}, {"escolha": [2, 0]}],
    "m0-03-terceira": [{"ordem": ["a", "b", "c"]}],
}


async def _complete(c, h, sec, escolha=(1,)):
    r = await c.post(f"/api/academy/sections/{sec}/verify", json={"resposta": {"escolha": list(escolha)}}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- validador ----------------
async def test_validator_accepts_fixture_and_real_content():
    errors, warnings = validate_academy.validate(FIX, settings.slides_dir)
    assert errors == []
    assert any("aula-2" in w for w in warnings)  # deck ainda não importado: só aviso
    if REAL.exists():
        errors, _ = validate_academy.validate(REAL, Path("/nonexistent"))
        assert errors == []


async def test_validator_reports_defects(tmp_path):
    root = tmp_path / "acad"
    shutil.copytree(FIX, root)
    sec = (root / "m0" / "01-primeira.yaml").read_text(encoding="utf-8")
    (root / "m0" / "10-dup.yaml").write_text(sec, encoding="utf-8")  # id repetido
    (root / "m0" / "11-resp.yaml").write_text(sec.replace("id: m0-01-primeira", "id: x1").replace("resposta: [1]", "resposta: [7]"), encoding="utf-8")
    (root / "m0" / "12-en.yaml").write_text(sec.replace("id: m0-01-primeira", "id: x2").replace("{pt: Primeira, en: First}", "{pt: Primeira}"), encoding="utf-8")
    (root / "m0" / "13-mod.yaml").write_text(sec.replace("id: m0-01-primeira", "id: x3").replace("modulo: m0", "modulo: nope"), encoding="utf-8")
    (root / "m0" / "14-slides.yaml").write_text(
        sec.replace("id: m0-01-primeira", "id: x4").replace("{deck: aula-2, de: 1, ate: 2}", "{deck: aula-2, de: 1, ate: 99}, {deck: ausente, de: 1, ate: 1}"), encoding="utf-8")
    c2 = (root / "m0" / "02-segunda.yaml").read_text(encoding="utf-8")
    (root / "m0" / "15-stmt.yaml").write_text(c2.replace("id: m0-02-segunda", "id: x5").replace("stmt: s3", "stmt: zz"), encoding="utf-8")
    (root / "m0" / "16-nopy.yaml").write_text(c2.replace("id: m0-02-segunda", "id: x6").replace("stmt: s3", "stmt: s1"), encoding="utf-8")  # s1 não tem py
    deck = tmp_path / "slides" / "aula-2"
    deck.mkdir(parents=True)
    (deck / "manifest.json").write_text(json.dumps({"id": "aula-2", "titulo": "x", "n_slides": 5}), encoding="utf-8")
    errors, warnings = validate_academy.validate(root, tmp_path / "slides")
    text = "\n".join(errors)
    for needle in ("id de secção repetido", "resposta: índices inválidos", "10-dup.yaml", "12-en.yaml", "13-mod.yaml", "fora do deck", "15-stmt.yaml", "16-nopy.yaml"):
        assert needle in text, needle
    assert any("ausente" in w for w in warnings) and not any("ausente" in e for e in errors)


# ---------------- desbloqueio ----------------
async def test_unlock_sections_and_modules(make_user, new_client, monkeypatch):
    c, h = await _user(make_user, new_client)
    ov = (await c.get("/api/academy")).json()
    m = {x["id"]: x for x in ov["modules"]}
    assert m["m0"]["estado"] == "open" and m["m0"]["motivo"] == "always" and m["m0"]["n_secoes"] == 3 and m["m0"]["em_breve"] is False
    assert m["m1"]["estado"] == "locked" and m["m1"]["motivo"] is None and m["m2"]["estado"] == "locked"
    assert m["m3"]["em_breve"] is True and m["m3"]["estado"] == "locked" and m["m3"]["n_secoes"] == 0
    assert ov["resumo"] == {"modulos_concluidos": 0, "pontos_academia": 0, "sequencia_dias": 0} and ov["missao"] is None
    assert m["m0"]["pontos_possiveis"] == 3 * 3 + 25 and m["m2"]["pontos_possiveis"] == 5 + 25
    mod = (await c.get("/api/academy/modules/m0")).json()
    assert [s["estado"] for s in mod["secoes"]] == ["current", "locked", "locked"]
    # secções sequenciais
    assert (await c.get("/api/academy/sections/m0-02-segunda")).json() == {"error": "academy.locked"}
    assert (await c.get("/api/academy/sections/m0-03-terceira")).status_code == 403
    assert (await c.get("/api/academy/sections/m1-01-m1")).json() == {"error": "academy.locked"}  # módulo bloqueado
    assert (await c.get("/api/academy/sections/nao-existe")).json() == {"error": "academy.section_not_found"}
    assert (await c.get("/api/academy/modules/nao")).json() == {"error": "academy.module_not_found"}
    assert (await c.get("/api/academy/sections/m0-01-primeira")).status_code == 200
    await _complete(c, h, "m0-01-primeira")
    mod = (await c.get("/api/academy/modules/m0")).json()
    assert [s["estado"] for s in mod["secoes"]] == ["done", "current", "locked"] and mod["estado"] == "in_progress"
    assert (await c.get("/api/academy/sections/m0-01-primeira")).status_code == 200  # rever é livre
    await _complete(c, h, "m0-02-segunda")
    await _complete(c, h, "m0-03-terceira")
    m = {x["id"]: x for x in (await c.get("/api/academy")).json()["modules"]}
    assert m["m0"]["estado"] == "done" and m["m0"]["pct"] == 100
    assert m["m1"]["estado"] == "open" and m["m1"]["motivo"] == "prev_done"  # o anterior concluído abre o seguinte
    assert m["m2"]["estado"] == "locked"
    # o bloco aberto no currículo abre o módulo (motivo teacher)
    monkeypatch.setattr(academy, "open_blocks", lambda: {"2"})
    m = {x["id"]: x for x in (await c.get("/api/academy")).json()["modules"]}
    assert m["m2"]["estado"] == "open" and m["m2"]["motivo"] == "teacher"
    assert (await c.get("/api/academy/sections/m2-01-m2")).status_code == 200
    # outro aluno novo: com o bloco 1 aberto, M1 abre mesmo sem concluir M0
    monkeypatch.setattr(academy, "open_blocks", lambda: {"1"})
    c2, _ = await _user(make_user, new_client, "rui")
    m = {x["id"]: x for x in (await c2.get("/api/academy")).json()["modules"]}
    assert m["m1"]["estado"] == "open" and m["m1"]["motivo"] == "teacher"


# ---------------- vista pública ----------------
async def test_public_view_never_reveals_answers_or_order(make_user, new_client):
    c, _ = await _user(make_user, new_client)
    sec = (await c.get("/api/academy/sections/m0-01-primeira")).json()
    blob = json.dumps(sec)
    for secret in ("resposta", "respostas", "explicacao"):
        assert secret not in blob, secret
    a_lig, a_fluxo, a_py = sec["atividades"]
    assert a_lig["ids"] == ["s2", "s3", "s4"] and sorted(a_lig["linhas"]) == ["s2", "s3", "s4"] and a_lig["linhas"] != a_lig["ids"]
    assert sorted(a_fluxo["itens"]) == ["s1", "s2", "s3", "s4"] and a_fluxo["itens"] != ["s1", "s2", "s3", "s4"]
    assert sorted(a_py["itens"]) == ["s2", "s3", "s4"] and a_py["itens"] != ["s2", "s3", "s4"]  # só stmts com py
    assert sec["exemplo"]["corpo"][0].get("py") is None and sec["slides"] == [{"deck": "aula-2", "de": 1, "ate": 2}]
    assert sec["estado"] == "current" and sec["pontos"] == 3 and sec["n_pistas"] == 1 and sec["proxima"] == "m0-02-segunda"
    assert sec["verificacao"] == {"pergunta": {"pt": "Qual?", "en": "Which?"}, "opcoes": [{"pt": "A", "en": "A"}, {"pt": "B", "en": "B"}, {"pt": "C", "en": "C"}], "multipla": False, "mostrar_exemplo": True}
    again = (await c.get("/api/academy/sections/m0-01-primeira")).json()
    assert again["atividades"] == sec["atividades"]  # ordem baralhada estável para o mesmo aluno
    await _complete(c, (await _hdr(c)), "m0-01-primeira")
    s2 = (await c.get("/api/academy/sections/m0-02-segunda")).json()
    comp, perg = s2["atividades"]
    assert comp["lacunas"] == [{"stmt": "s3", "lado": "py", "modelo": {"pt": "dobro = nota * ___", "en": "dobro = nota * ___"}}]
    assert perg["multipla"] is True and perg["mostrar_exemplo"] is True and "resposta" not in json.dumps(s2)
    await _complete(c, await _hdr(c), "m0-02-segunda")
    s3 = (await c.get("/api/academy/sections/m0-03-terceira")).json()
    it = s3["atividades"][0]["itens"]
    assert sorted(i["id"] for i in it) == ["a", "b", "c"] and [i["id"] for i in it] != ["a", "b", "c"]
    assert s3["exemplo"] is None and s3["verificacao"]["mostrar_exemplo"] is False


async def _hdr(c):
    r = await c.get("/api/me")
    return {"X-CSRF-Token": r.json()["csrf_token"]}


# ---------------- correção ----------------
async def test_each_activity_type_is_corrected_on_the_server(make_user, new_client):
    c, h = await _user(make_user, new_client)

    async def ans(sec, idx, body):
        r = await c.post(f"/api/academy/sections/{sec}/activities/{idx}/answer", json={"resposta": body}, headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    s = "m0-01-primeira"
    r = await ans(s, 0, {"pares": {"s2": "s3", "s3": "s2", "s4": "s4"}})
    assert r["correta"] is False and r["detalhe"] == {"erradas": ["s2", "s3"]} and "explicacao" not in r  # 1.ª tentativa
    r = await ans(s, 0, {"pares": {"s2": "s3", "s3": "s2", "s4": "s4"}})
    assert r["explicacao"] == {"pt": "Porque sim", "en": "Because"}  # à 2.ª errada mostra a explicação
    r = await ans(s, 0, CORRECT[s][0])
    assert r["correta"] is True and "detalhe" not in r and r["explicacao"]
    assert (await ans(s, 0, {"pares": {"s2": "s2"}}))["correta"] is False  # incompleto
    r = await ans(s, 1, {"ordem": ["s1", "s3", "s2", "s4"]})
    assert r["correta"] is False and r["detalhe"] == {"erradas": [1, 2]}
    assert (await ans(s, 1, CORRECT[s][1]))["correta"] is True
    assert (await ans(s, 2, {"ordem": ["s4", "s3", "s2"]}))["detalhe"] == {"erradas": [0, 2]}
    assert (await ans(s, 2, CORRECT[s][2]))["correta"] is True
    await _complete(c, h, s)
    s = "m0-02-segunda"
    r = await ans(s, 0, {"valores": ["3"]})
    assert r["correta"] is False and r["detalhe"] == {"erradas": [0]}
    for ok in ("2", " 2.0 ", "2,0", "2.00"):  # tolerante a espaços e a 2 = 2.0
        assert (await ans(s, 0, {"valores": [ok]}))["correta"] is True, ok
    assert (await ans(s, 1, {"escolha": [0]}))["correta"] is False
    assert (await ans(s, 1, {"escolha": [2, 0]}))["correta"] is True
    await _complete(c, h, s)
    s = "m0-03-terceira"
    assert (await ans(s, 0, {"ordem": ["b", "a", "c"]}))["detalhe"] == {"erradas": [0, 1]}
    assert (await ans(s, 0, {"ordem": ["a", "b", "c"]}))["correta"] is True
    # formas inválidas e atividade inexistente
    for bad in ({"ordem": "abc"}, {"x": 1}, {"ordem": [1, 2]}):
        r = await c.post(f"/api/academy/sections/{s}/activities/0/answer", json={"resposta": bad}, headers=h)
        assert r.status_code == 422 and r.json() == {"error": "academy.invalid_answer"}
    assert (await c.post(f"/api/academy/sections/{s}/activities/9/answer", json={"resposta": {}}, headers=h)).json() == {"error": "academy.activity_not_found"}
    # o progresso das atividades fica registado
    assert (await c.get(f"/api/academy/sections/{s}")).json()["atividades_resolvidas"] == [0]


# ---------------- pontos ----------------
async def test_points_idempotent_hint_halves_badge_and_streak_once(make_user, new_client):
    c, h = await _user(make_user, new_client)
    s1, s2, s3 = "m0-01-primeira", "m0-02-segunda", "m0-03-terceira"
    await c.get(f"/api/academy/sections/{s1}")
    r = await c.post(f"/api/academy/sections/{s1}/verify", json={"resposta": {"escolha": [0]}}, headers=h)
    assert r.json()["correta"] is False and r.json()["pontos"] == 0 and r.json()["concluida"] is False
    r = await _complete(c, h, s1)
    assert r["correta"] and r["concluida"] and r["pontos"] == 3 and r["streak"] == 2 and "badge" not in r and r["proxima"] == s2
    again = await _complete(c, h, s1)  # idempotente
    assert again["pontos"] == 0 and again["concluida"] is True and "streak" not in again
    # pista aberta antes de concluir: metade, com mínimo 1 (3 -> 1)
    h1 = await c.get(f"/api/academy/sections/{s2}/hints/1")
    assert h1.status_code == 200 and h1.json() == {"n": 1, "texto": {"pt": "P1", "en": "P1"}}
    assert (await c.get(f"/api/academy/sections/{s2}/hints/3")).json() == {"error": "academy.hint_not_found"}
    assert (await c.get(f"/api/academy/sections/{s2}")).json()["hints_used"] == 1
    r = await _complete(c, h, s2)
    assert r["pontos"] == 1 and "streak" not in r  # mesmo dia: sem 2.º streak
    r = await _complete(c, h, s3)
    assert r["pontos"] == 3 and r["badge"] == {"modulo": "m0", "pontos": 25} and r["proxima"] is None
    assert "badge" not in await _complete(c, h, s3)
    led = await _points(None)
    assert sorted(led["academy_section"]) == [(s1, 3), (s2, 1), (s3, 3)] and led["academy_badge"] == [("m0", 25)] and led["academy_streak"] == [("2026-11-16", 2)]
    ov = (await c.get("/api/academy")).json()
    m0 = next(x for x in ov["modules"] if x["id"] == "m0")
    assert m0["pontos_ganhos"] == 3 + 1 + 3 + 25 and ov["resumo"] == {"modulos_concluidos": 1, "pontos_academia": 7 + 25 + 2, "sequencia_dias": 1}
    # conta no leaderboard pessoal
    async with SessionLocal() as db:
        from app.models.user import User
        me = (await db.execute(select(User).where(User.username == "ana"))).scalar_one()
        assert (await leaderboard.me(db, me, "all"))["points"] == 34


async def test_streak_counts_consecutive_days_and_points_per_module_tier(make_user, new_client, monkeypatch):
    c, h = await _user(make_user, new_client)
    monkeypatch.setattr(academy, "open_blocks", lambda: {"2"})
    await _complete(c, h, "m0-01-primeira")
    monkeypatch.setattr(academy, "today_lisbon", lambda: date(2026, 11, 17))
    r = await _complete(c, h, "m0-02-segunda")
    assert r["streak"] == 2  # novo dia: novo streak
    assert (await c.get("/api/academy")).json()["resumo"]["sequencia_dias"] == 2
    monkeypatch.setattr(academy, "today_lisbon", lambda: date(2026, 11, 20))  # dias em falta: a sequência quebra
    assert (await c.get("/api/academy")).json()["resumo"]["sequencia_dias"] == 0
    r = await _complete(c, h, "m2-01-m2")
    assert r["pontos"] == 5 and r["badge"]["modulo"] == "m2"  # M2–M3 valem 5; módulo de 1 secção dá badge


async def test_concurrent_verify_awards_once(make_user, new_client):
    c, h = await _user(make_user, new_client)
    rs = await asyncio.gather(*[_complete(c, h, "m0-01-primeira") for _ in range(4)])
    assert sorted(r["pontos"] for r in rs) == [0, 0, 0, 3]
    assert len((await _points(None))["academy_section"]) == 1


async def test_rate_limit_30_per_minute(make_user, new_client):
    c, h = await _user(make_user, new_client)
    codes = []
    for _ in range(31):
        r = await c.post("/api/academy/sections/m0-01-primeira/activities/2/answer", json={"resposta": {"ordem": ["s2"]}}, headers=h)
        codes.append(r.status_code)
    assert codes == [200] * 30 + [429]
    assert r.json() == {"error": "academy.rate_limited"}


async def test_academy_requires_session(client):
    for url in ("/api/academy", "/api/academy/modules/m0", "/api/academy/sections/m0-01-primeira", "/api/academy/slides", "/api/academy/slides/aula-1/1"):
        assert (await client.get(url)).status_code == 401


# ---------------- slides ----------------
async def _deck(tmp_path_dir: Path, deck="aula-9", n=2):
    d = tmp_path_dir / deck
    d.mkdir(parents=True)
    for i in range(1, n + 1):
        (d / f"{i}.png").write_bytes(b"\x89PNG\r\n\x1a\nfake" + bytes([i]))
    async with SessionLocal() as db:
        db.add(SlideDeck(id=deck, titulo="Aula 9", n_slides=n))
        await db.commit()
    (tmp_path_dir / "segredo.png").write_bytes(b"secret")


async def test_slides_need_session_and_block_traversal(client, make_user, make_class, new_client):
    await _deck(settings.slides_dir)
    assert (await client.get("/api/academy/slides/aula-9/1")).status_code == 401  # sem sessão
    prof = await make_user("prof", __import__("app.models.user", fromlist=["Role"]).Role.teacher)
    cls = await make_class(prof.id)
    c, _ = await _user(make_user, new_client, "ana", class_id=cls.id)
    r = await c.get("/api/academy/slides/aula-9/1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.headers["cache-control"] == "private, max-age=3600"
    assert r.content.startswith(b"\x89PNG")
    assert (await c.get("/api/academy/slides")).json() == {"decks": [{"id": "aula-9", "titulo": "Aula 9", "n_slides": 2}]}
    for url in ("/api/academy/slides/aula-9/0", "/api/academy/slides/aula-9/3", "/api/academy/slides/outro/1", "/api/academy/slides/..%2f/1",
                "/api/academy/slides/%2e%2e/1", "/api/academy/slides/aula-9%2f..%2fsegredo/1", "/api/academy/slides/aula-9/-1"):
        got = await c.get(url)
        assert got.status_code in (404, 422) and b"secret" not in got.content, url
    # um deck cujo diretório saiu do sítio (symlink) nunca é servido
    (settings.slides_dir / "aula-9" / "2.png").unlink()
    (settings.slides_dir / "aula-9" / "2.png").symlink_to(settings.slides_dir / "segredo.png")
    got = await c.get("/api/academy/slides/aula-9/2")
    assert got.status_code == 404 and b"secret" not in got.content
    # aluno sem turma não vê slides; professor vê
    c0, _ = await _user(make_user, new_client, "solto")
    assert (await c0.get("/api/academy/slides/aula-9/1")).json() == {"error": "academy.slides_forbidden"}
    pc = new_client()
    await login(pc, "prof")
    assert (await pc.get("/api/academy/slides/aula-9/1")).status_code == 200


async def test_import_slides_registers_manifest(tmp_path):
    from app.tools import import_slides
    d = tmp_path / "deck-x"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"id": "deck-x", "titulo": "X", "n_slides": 2}), encoding="utf-8")
    (d / "1.png").write_bytes(b"1")
    with pytest.raises(SystemExit):  # falta o PNG 2
        import_slides.read_manifest("deck-x", tmp_path)
    (d / "2.png").write_bytes(b"2")
    row = await import_slides.register("deck-x", "Titulo", tmp_path)
    again = await import_slides.register("deck-x", "Outro", tmp_path)  # idempotente (atualiza)
    assert row["n_slides"] == 2 and again["titulo"] == "Outro"
    async with SessionLocal() as db:
        assert (await db.get(SlideDeck, "deck-x")).titulo == "Outro"
    with pytest.raises(SystemExit):
        import_slides.read_manifest("../x", tmp_path)


async def test_content_cache_reloads_on_change(tmp_path, monkeypatch):
    root = tmp_path / "acad"
    shutil.copytree(FIX, root)
    monkeypatch.setattr(settings, "academy_dir", root)
    assert len(academy_content.get_content().sections) == 6
    (root / "m2" / "01-m2.yaml").unlink()
    assert len(academy_content.get_content().sections) == 5
