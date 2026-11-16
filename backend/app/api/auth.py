# Autenticação e conta do próprio utilizador: login, logout, join, preferências, RGPD.
import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import COOKIE, Auth, audit, client_ip, current_auth, origin_guard
from app.api.schemas import ChangePasswordIn, ClassJoinIn, DeleteAccountIn, GuestJoinIn, JoinIn, LoginIn, PreferencesIn
from app.config import LOCALES, THEMES, settings
from app.db import get_db
from app.errors import ApiError
from app.models.session import AuthSession
from app.models.tournament import Tournament
from app.models.user import Role, SchoolClass, User
from app.services import security, tournament as tournament_service

router = APIRouter(prefix="/api", dependencies=[Depends(origin_guard)])
JOIN_KEY = "__join__"


def user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
        "locale": user.locale,
        "preferred_theme": user.preferred_theme,
        "show_in_leaderboard": user.show_in_leaderboard,
        "class_id": user.class_id,
        "must_change_password": user.must_change_password,
    }


def set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
        secure=settings.cookie_secure, samesite="lax", path="/",
    )


async def start_session(db: AsyncSession, user: User, request: Request) -> JSONResponse:
    """Rotação: apaga a sessão antiga (se existir) e cria uma nova a cada login/join."""
    old = request.cookies.get(COOKIE)
    if old:
        await db.execute(delete(AuthSession).where(AuthSession.token_hash == security.hash_token(old)))
    return await issue_session(db, user)


async def issue_session(db: AsyncSession, user: User, extra: dict | None = None) -> JSONResponse:
    token, row = await security.create_session(db, user.id)
    await db.commit()
    resp = JSONResponse({"user": user_payload(user), "csrf_token": row.csrf_token, **(extra or {})})
    set_cookie(resp, token)
    return resp


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    if await security.recent_failures(db, body.username, ip) >= settings.login_max_failures:
        raise ApiError(429, "auth.too_many_attempts")
    user = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if not await security.verify_password(user.password_hash if user else None, body.password) or user is None:
        await security.record_failure(db, body.username, ip)
        raise ApiError(401, "auth.invalid_credentials")
    return await start_session(db, user, request)


@router.post("/auth/join")
async def join(body: JoinIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    if await security.recent_failures(db, JOIN_KEY, ip) >= settings.join_max_failures:
        raise ApiError(429, "auth.too_many_attempts")
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.join_code == body.join_code))).scalar_one_or_none()
    if cls is None:
        await security.record_failure(db, JOIN_KEY, ip)
        raise ApiError(404, "class.invalid_code")
    user = User(
        username=body.username, email=body.email, display_name=body.display_name, role=Role.student,
        password_hash=await security.hash_password(body.password), class_id=cls.id,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing_username = (await db.execute(select(User.id).where(User.username == body.username))).scalar_one_or_none()
        if existing_username is not None:
            raise ApiError(409, "auth.username_taken")
        existing_email = (await db.execute(select(User.id).where(User.email == body.email))).scalar_one_or_none()
        if existing_email is not None:
            raise ApiError(409, "auth.email_taken")
        raise ApiError(409, "common.invalid_request")
    return await start_session(db, user, request)


@router.post("/auth/tournament-guest")
async def tournament_guest(body: GuestJoinIn, request: Request, db: AsyncSession = Depends(get_db)):
    """Cria uma identidade descartável limitada ao torneio indicado pelo código."""
    tournament = (await db.execute(select(Tournament).where(Tournament.join_code == body.join_code))).scalar_one_or_none()
    if tournament is None or tournament.state == "finished":
        raise ApiError(404, "tournament.not_found")
    guest = User(
        username=f"guest_{security.random_code(16).lower()}",
        display_name=body.display_name,
        role=Role.student,
        password_hash=await security.hash_password(security.random_password(32)),
        is_guest=True,
        guest_tournament_id=tournament.id,
    )
    db.add(guest)
    await db.flush()
    await tournament_service.join(db, guest, tournament.join_code, client_ip(request))
    return await _guest_session(db, guest, tournament.id, request)


async def _guest_session(db: AsyncSession, user: User, tournament_id: int, request: Request) -> JSONResponse:
    old = request.cookies.get(COOKIE)
    if old:
        await db.execute(delete(AuthSession).where(AuthSession.token_hash == security.hash_token(old)))
    return await issue_session(db, user, {"tournament_id": tournament_id})


@router.post("/auth/logout")
async def logout(response: Response, auth: Auth = Depends(current_auth), db: AsyncSession = Depends(get_db)):
    await db.delete(auth.session)
    await db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.post("/auth/join-class")
async def join_class(body: ClassJoinIn, auth: Auth = Depends(current_auth), db: AsyncSession = Depends(get_db)):
    if auth.user.role != Role.student or auth.user.is_guest:
        raise ApiError(403, "class.join_forbidden")
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.join_code == body.join_code))).scalar_one_or_none()
    if cls is None:
        raise ApiError(404, "class.invalid_code")
    if auth.user.class_id is not None:
        raise ApiError(409, "class.already_joined")
    auth.user.class_id = cls.id
    await db.commit()
    return {"user": user_payload(auth.user)}


@router.post("/auth/change-password")
async def change_password(
    body: ChangePasswordIn, auth: Auth = Depends(current_auth), db: AsyncSession = Depends(get_db)
):
    user = auth.user
    if not await security.verify_password(user.password_hash, body.current_password):
        raise ApiError(400, "auth.wrong_password")
    if body.new_password == body.current_password:
        raise ApiError(400, "auth.password_unchanged")
    user.password_hash = await security.hash_password(body.new_password)
    user.must_change_password = False
    # revoga as outras sessões e roda a atual
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    await db.flush()
    return await issue_session(db, user)


@router.get("/me")
async def me(auth: Auth = Depends(current_auth)):
    return {"user": user_payload(auth.user), "csrf_token": auth.session.csrf_token}


@router.patch("/me/preferences")
async def preferences(body: PreferencesIn, auth: Auth = Depends(current_auth), db: AsyncSession = Depends(get_db)):
    if auth.user.must_change_password:
        raise ApiError(403, "auth.must_change_password")
    sent = body.model_fields_set
    if "locale" in sent:
        if body.locale not in LOCALES:
            raise ApiError(422, "prefs.invalid_locale")
        auth.user.locale = body.locale
    if "preferred_theme" in sent:
        if body.preferred_theme is not None and body.preferred_theme not in THEMES:
            raise ApiError(422, "prefs.invalid_theme")
        auth.user.preferred_theme = body.preferred_theme
    if "show_in_leaderboard" in sent:
        if body.show_in_leaderboard is None:
            raise ApiError(422, "common.invalid_request")
        auth.user.show_in_leaderboard = body.show_in_leaderboard
    if "display_name" in sent:
        name = " ".join((body.display_name or "").split())
        if not 1 <= len(name) <= 40:
            raise ApiError(422, "prefs.invalid_display_name")
        auth.user.display_name = name
    await db.commit()
    return {"user": user_payload(auth.user)}


@router.get("/me/export")
async def export_me(auth: Auth = Depends(current_auth), db: AsyncSession = Depends(get_db)):
    u = auth.user
    cls = await db.get(SchoolClass, u.class_id) if u.class_id else None
    data = {**user_payload(u), "created_at": u.created_at.isoformat(), "class_name": cls.name if cls else None}
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="pyarena-dados.json"'},
    )


@router.delete("/me")
async def delete_me(
    body: DeleteAccountIn, response: Response, auth: Auth = Depends(current_auth), db: AsyncSession = Depends(get_db)
):
    u = auth.user
    if not await security.verify_password(u.password_hash, body.password):
        raise ApiError(400, "auth.wrong_password")
    if u.role == Role.teacher:
        raise ApiError(409, "account.teacher_cannot_delete")
    await audit(db, None, "account.deleted")
    await db.delete(u)  # sessões apagadas em cascata
    await db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/session")
async def session_info(request: Request, db: AsyncSession = Depends(get_db)):
    """Como /me, mas sem sessão devolve 200 {"user": null} (não faz ruído de 401 na consola das páginas públicas)."""
    try:
        auth = await current_auth(request, db)
    except ApiError:
        return {"user": None}
    return {"user": user_payload(auth.user), "csrf_token": auth.session.csrf_token}
