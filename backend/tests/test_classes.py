# Testes das rotas do professor: permissões, isolamento entre professores e importação CSV.
import pytest

from app.models.user import Role
from tests.conftest import login

pytestmark = pytest.mark.asyncio


async def test_student_cannot_use_teacher_endpoints(client, make_user):
    await make_user("aluno")
    h = await login(client, "aluno")
    assert (await client.get("/api/classes")).json() == {"error": "auth.forbidden"}
    r = await client.post("/api/classes", json={"name": "X"}, headers=h)
    assert r.status_code == 403 and r.json() == {"error": "auth.forbidden"}


async def test_teacher_creates_and_lists_class(client, make_user):
    await make_user("prof1", Role.teacher)
    h = await login(client, "prof1")
    r = await client.post("/api/classes", json={"name": "10.º A"}, headers=h)
    assert r.status_code == 201 and len(r.json()["join_code"]) == 6
    assert [c["name"] for c in (await client.get("/api/classes")).json()["classes"]] == ["10.º A"]


async def test_teacher_cannot_see_other_teachers_class(new_client, make_user):
    await make_user("profa", Role.teacher)
    await make_user("profb", Role.teacher)
    async with new_client() as a, new_client() as b:
        ha, hb = await login(a, "profa"), await login(b, "profb")
        cid = (await a.post("/api/classes", json={"name": "Turma A"}, headers=ha)).json()["id"]
        assert (await a.get(f"/api/classes/{cid}/students")).status_code == 200
        r = await b.get(f"/api/classes/{cid}/students")
        assert r.status_code == 404 and r.json() == {"error": "class.not_found"}
        r = await b.post(f"/api/classes/{cid}/students/import", json={"csv": "x,y"}, headers=hb)
        assert r.status_code == 404
        assert (await b.get("/api/classes")).json()["classes"] == []


async def test_import_students_csv(new_client, make_user):
    await make_user("prof1", Role.teacher)
    async with new_client() as t, new_client() as s:
        h = await login(t, "prof1")
        cid = (await t.post("/api/classes", json={"name": "A"}, headers=h)).json()["id"]
        csv = "username,display_name\nana,Ana Silva\nbad user!,X\nana,Duplicada\n"
        r = await t.post(f"/api/classes/{cid}/students/import", json={"csv": csv}, headers=h)
        assert r.status_code == 200
        body = r.json()
        assert [c["username"] for c in body["created"]] == ["ana"]
        assert {e["error"] for e in body["errors"]} == {"import.invalid_row", "import.username_taken"}
        temp = body["created"][0]["temp_password"]
        listing = (await t.get(f"/api/classes/{cid}/students")).json()["students"]
        assert listing[0]["username"] == "ana" and listing[0]["must_change_password"] is True
        assert "temp_password" not in str(listing)  # só é devolvida uma vez
        # o aluno entra com a temporária e fica bloqueado até mudar
        await login(s, "ana", temp)
        assert (await s.get("/api/problems")).json() == {"error": "auth.must_change_password"}
