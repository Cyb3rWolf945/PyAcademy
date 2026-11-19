# Testes de login, sessão, rate limit, CSRF, join, preferências, palavra-passe e RGPD.
import pytest

from app.bootstrap import seed_teacher
from app.db import SessionLocal
from app.models.user import Role
from tests.conftest import login, make_client

pytestmark = pytest.mark.asyncio


async def test_login_ok_and_me(client, make_user):
    await make_user("ana", display_name="Ana")
    r = await client.post("/api/auth/login", json={"username": "ANA", "password": "password-1"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "ana" and r.json()["csrf_token"]
    me = await client.get("/api/me")
    assert me.status_code == 200 and me.json()["user"]["display_name"] == "Ana"
    assert "password_hash" not in me.text


async def test_login_fail_is_a_key_not_a_sentence(client, make_user):
    await make_user("ana")
    r = await client.post("/api/auth/login", json={"username": "ana", "password": "errada"})
    assert r.status_code == 401 and r.json() == {"error": "auth.invalid_credentials"}
    r = await client.post("/api/auth/login", json={"username": "ninguem", "password": "x"})
    assert r.status_code == 401 and r.json() == {"error": "auth.invalid_credentials"}


async def test_me_requires_session(client):
    r = await client.get("/api/me")
    assert r.status_code == 401 and r.json() == {"error": "auth.not_authenticated"}


async def test_login_rate_limit(client, make_user):
    await make_user("ana")
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"username": "ana", "password": "errada"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"})
    assert r.status_code == 429 and r.json() == {"error": "auth.too_many_attempts"}


async def test_session_cookie_flags_and_rotation(client, make_user):
    await make_user("ana")
    r1 = await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"})
    flags = r1.headers["set-cookie"].lower()
    assert "pyarena_session=" in flags and "httponly" in flags and "secure" in flags
    assert "samesite=lax" in flags and "path=/" in flags
    old = client.cookies.get("pyarena_session")
    await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"})
    new = client.cookies.get("pyarena_session")
    assert old != new
    async with make_client() as other:
        other.cookies.set("pyarena_session", old)  # token antigo já não vale
        assert (await other.get("/api/me")).status_code == 401


async def test_logout(client, make_user):
    await make_user("ana")
    h = await login(client, "ana")
    assert (await client.post("/api/auth/logout", headers=h)).status_code == 200
    assert (await client.get("/api/me")).status_code == 401


async def test_csrf_header_missing_or_wrong(client, make_user):
    await make_user("ana")
    await login(client, "ana")
    r = await client.post("/api/auth/logout")
    assert r.status_code == 403 and r.json() == {"error": "auth.csrf"}
    r = await client.patch("/api/me/preferences", json={"locale": "en"}, headers={"X-CSRF-Token": "errado"})
    assert r.status_code == 403 and r.json() == {"error": "auth.csrf"}


async def test_bad_origin_rejected(client, make_user):
    await make_user("ana")
    h = await login(client, "ana")
    r = await client.patch("/api/me/preferences", json={"locale": "en"}, headers={**h, "Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json() == {"error": "auth.csrf"}
    # também o login (CSRF de login) e a ausência de Origin/Referer
    r = await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"}, headers={"Origin": ""})
    assert r.status_code == 403
    # Referer válido serve quando não há Origin
    r = await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"},
                          headers={"Origin": "", "Referer": "https://testserver/x"})
    assert r.status_code == 200


async def test_ngrok_origin_and_local_aliases_are_allowed(client, make_user):
    await make_user("ana")
    headers = await login(client, "ana")
    from app.config import settings

    original = settings.public_origin
    settings.public_origin = "https://testserver,http://localhost:8080,http://127.0.0.1:8080,https://*.ngrok-free.app"
    try:
        for origin in ("http://localhost:8080", "http://127.0.0.1:8080", "https://abc123.ngrok-free.app"):
            response = await client.patch(
                "/api/me/preferences",
                json={"locale": "en"},
                headers={**headers, "Origin": origin},
            )
            assert response.status_code == 200
    finally:
        settings.public_origin = original


async def test_join_with_class_code(client, make_user, make_class):
    t = await make_user("prof1", Role.teacher)
    await make_class(t.id, code="ABC234")
    r = await client.post("/api/auth/join", json={"join_code": "abc234", "email": "rui@ipt.pt", "username": "Rui", "display_name": "Rui P.", "password": "password-9"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "rui" and r.json()["user"]["class_id"] is not None
    assert (await client.get("/api/me")).status_code == 200
    r = await client.post("/api/auth/join", json={"join_code": "ABC234", "email": "outro@ipt.pt", "username": "rui", "display_name": "x", "password": "password-9"})
    assert r.status_code == 409 and r.json() == {"error": "auth.username_taken"}


async def test_join_bad_code_and_rate_limit(client):
    body = {"join_code": "ZZZZZZ", "email": "rui@ipt.pt", "username": "rui", "display_name": "Rui", "password": "password-9"}
    for _ in range(30):
        r = await client.post("/api/auth/join", json=body)
        assert r.status_code == 404 and r.json() == {"error": "class.invalid_code"}
    assert (await client.post("/api/auth/join", json=body)).status_code == 429


async def test_join_requires_ipt_email(client, make_user, make_class):
    teacher = await make_user("prof1", Role.teacher)
    await make_class(teacher.id, code="ABC234")
    body = {"join_code": "ABC234", "email": "aluno@example.com", "username": "aluno", "display_name": "Aluno", "password": "password-9"}
    assert (await client.post("/api/auth/join", json=body)).status_code == 422
    valid = await client.post("/api/auth/join", json={**body, "email": " Aluno@IPT.PT "})
    assert valid.status_code == 200 and valid.json()["user"]["username"] == "aluno"
    duplicate = await client.post("/api/auth/join", json={**body, "username": "outro", "email": "aluno@ipt.pt"})
    assert duplicate.status_code == 409 and duplicate.json() == {"error": "auth.email_taken"}


async def test_join_limit_does_not_block_a_classroom(client, make_user, make_class):
    t = await make_user("prof1", Role.teacher)
    await make_class(t.id, code="ABC234")
    bad = {"join_code": "ZZZZZZ", "email": "rui@ipt.pt", "username": "rui", "display_name": "Rui", "password": "password-9"}
    for _ in range(10):  # 10 códigos errados do mesmo IP (NAT da sala) não bloqueiam
        assert (await client.post("/api/auth/join", json=bad)).status_code == 404
    ok = await client.post("/api/auth/join", json={**bad, "join_code": "ABC234"})
    assert ok.status_code == 200


async def test_must_change_password_gating(client):
    async with SessionLocal() as db:
        assert await seed_teacher(db) is True
        assert await seed_teacher(db) is False  # idempotente
    h = await login(client, "prof", "temp-pass-123")
    me = await client.get("/api/me")
    assert me.json()["user"]["must_change_password"] is True and me.json()["user"]["role"] == "teacher"
    r = await client.get("/api/classes")
    assert r.status_code == 403 and r.json() == {"error": "auth.must_change_password"}
    r = await client.patch("/api/me/preferences", json={"locale": "en"}, headers=h)
    assert r.json() == {"error": "auth.must_change_password"}
    r = await client.post("/api/auth/change-password", json={"current_password": "x", "new_password": "nova-pass-123"}, headers=h)
    assert r.status_code == 400 and r.json() == {"error": "auth.wrong_password"}
    r = await client.post("/api/auth/change-password", json={"current_password": "temp-pass-123", "new_password": "nova-pass-123"}, headers=h)
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is False
    assert (await client.get("/api/classes")).status_code == 200


async def test_preferences_validation(client, make_user):
    await make_user("ana")
    h = await login(client, "ana")
    r = await client.patch("/api/me/preferences", json={"locale": "fr"}, headers=h)
    assert r.status_code == 422 and r.json() == {"error": "prefs.invalid_locale"}
    r = await client.patch("/api/me/preferences", json={"preferred_theme": "neon"}, headers=h)
    assert r.status_code == 422 and r.json() == {"error": "prefs.invalid_theme"}
    r = await client.patch("/api/me/preferences", json={"locale": "en", "preferred_theme": "floresta"}, headers=h)
    assert r.status_code == 200 and r.json()["user"]["locale"] == "en" and r.json()["user"]["preferred_theme"] == "floresta"
    r = await client.patch("/api/me/preferences", json={"preferred_theme": None}, headers=h)
    assert r.json()["user"]["preferred_theme"] is None and r.json()["user"]["locale"] == "en"
    r = await client.patch("/api/me/preferences", json={"is_admin": True}, headers=h)  # campos desconhecidos recusados
    assert r.status_code == 422 and r.json() == {"error": "common.invalid_request"}


async def test_xss_display_name_is_plain_data(client, make_user, make_class):
    t = await make_user("prof1", Role.teacher)
    await make_class(t.id)
    payload = "<script>alert(1)</script>"
    r = await client.post("/api/auth/join", json={"join_code": "ABC234", "email": "xss@ipt.pt", "username": "xss", "display_name": payload, "password": "password-9"})
    assert r.status_code == 200
    me = await client.get("/api/me")
    assert me.headers["content-type"].startswith("application/json")
    assert me.json()["user"]["display_name"] == payload  # guardado tal e qual, devolvido como dados


async def test_export_and_delete_account(client, make_user):
    await make_user("ana", display_name="Ana")
    h = await login(client, "ana")
    r = await client.get("/api/me/export")
    assert r.status_code == 200 and r.json()["username"] == "ana" and "password_hash" not in r.text
    assert (await client.request("DELETE", "/api/me", json={"password": "password-1"})).status_code == 403  # sem CSRF
    r = await client.request("DELETE", "/api/me", json={"password": "errada"}, headers=h)
    assert r.status_code == 400 and r.json() == {"error": "auth.wrong_password"}
    assert (await client.get("/api/me")).status_code == 200  # nada foi apagado
    assert (await client.request("DELETE", "/api/me", json={"password": "password-1"}, headers=h)).status_code == 200
    assert (await client.get("/api/me")).status_code == 401
    r = await client.post("/api/auth/login", json={"username": "ana", "password": "password-1"})
    assert r.status_code == 401


async def test_body_size_limit(client):
    r = await client.post("/api/auth/login", content=b"x" * (300 * 1024), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json() == {"error": "common.too_large"}


async def test_unknown_api_route_is_json_404(client):
    r = await client.get("/api/nao-existe")
    assert r.status_code == 404 and r.json() == {"error": "common.not_found"}


async def test_health_and_ready(client):
    assert (await client.get("/api/health")).json() == {"status": "ok"}
    assert (await client.get("/api/ready")).status_code == 200


async def test_session_endpoint_and_all_themes(client, make_user):
    assert (await client.get("/api/session")).json() == {"user": None}
    await make_user("ana")
    h = await login(client, "ana")
    r = (await client.get("/api/session")).json()
    assert r["user"]["username"] == "ana" and r["csrf_token"] == h["X-CSRF-Token"]
    for th in ("floresta", "masmorra", "oceano", "deserto", "neve", "noite", "tropico"):
        assert (await client.patch("/api/me/preferences", json={"preferred_theme": th}, headers=h)).status_code == 200
