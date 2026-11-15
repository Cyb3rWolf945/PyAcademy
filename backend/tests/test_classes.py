# Testes das rotas do professor: permissões, isolamento entre professores e importação CSV.
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models.academy import AcademyProgress
from app.models.points import UserPoints
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


async def test_delete_class_orphans_students_and_allows_rejoining(client, new_client, make_user, make_class):
    teacher = await make_user("prof1", Role.teacher)
    class_a = await make_class(teacher.id, code="AAA234")
    student = await make_user("ana", class_id=class_a.id)
    async with SessionLocal() as db:
        db.add(AcademyProgress(user_id=student.id, section_id="m0-s1"))
        db.add(UserPoints(user_id=student.id, points=12, reason="academy_section", problem_slug="m0-s1"))
        await db.commit()
    teacher_headers = await login(client, "prof1")
    assert (await client.delete(f"/api/classes/{class_a.id}", headers=teacher_headers)).json() == {"ok": True}
    async with SessionLocal() as db:
        refreshed = await db.get(type(student), student.id)
        assert refreshed.class_id is None
        assert await db.get(AcademyProgress, (student.id, "m0-s1"))
        assert (await db.execute(select(UserPoints).where(UserPoints.user_id == student.id))).scalar_one().points == 12
    class_b = await make_class(teacher.id, code="BBB234")
    async with new_client() as student_client:
        student_headers = await login(student_client, "ana")
        joined = await student_client.post("/api/auth/join-class", json={"join_code": "BBB234"}, headers=student_headers)
        assert joined.status_code == 200 and joined.json()["user"]["class_id"] == class_b.id


async def test_teacher_can_bulk_delete_only_owned_classes(client, make_user, make_class):
    teacher = await make_user("prof1", Role.teacher)
    other = await make_user("prof2", Role.teacher)
    first = await make_class(teacher.id, code="AAA234")
    second = await make_class(teacher.id, code="BBB234")
    foreign = await make_class(other.id, code="CCC234")
    headers = await login(client, "prof1")
    result = await client.post("/api/classes/bulk-delete", json={"class_ids": [first.id, second.id]}, headers=headers)
    assert result.status_code == 200 and result.json() == {"deleted": 2}
    assert (await client.get("/api/classes")).json()["classes"] == []
    rejected = await client.post("/api/classes/bulk-delete", json={"class_ids": [foreign.id]}, headers=headers)
    assert rejected.status_code == 404 and rejected.json() == {"error": "class.not_found"}
