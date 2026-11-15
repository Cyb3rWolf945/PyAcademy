# Rotas REST do torneio. O professor (dono, verificado no servidor) cria e controla; os alunos da turma
# entram, formam agências e pedem pistas; todos leem o snapshot do estado. Erros: {"error": "tournament.<chave>"}.
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, audit, client_ip, origin_guard, teacher_auth
from app.db import get_db
from app.errors import ApiError
from app.models.user import Role
from app.services import tournament as svc
from app.services import tournament_events as events

router = APIRouter(prefix="/api/tournaments", dependencies=[Depends(origin_guard)])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bi(Strict):
    pt: str = Field(min_length=1, max_length=60)
    en: str = Field(min_length=1, max_length=60)


class CreateIn(Strict):
    class_id: int
    name: str = Field(min_length=1, max_length=80)
    mode: str


class RoundIn(Strict):
    title: Bi | None = None
    problem_slugs: list[str] | None = Field(default=None, max_length=20)
    points: int | None = Field(default=None, ge=0, le=1000)
    multiplier: float | None = Field(default=None, ge=0.1, le=10)
    duration_s: int | None = Field(default=None, ge=30, le=7200)


class ExtendIn(Strict):
    seconds: int = Field(ge=1, le=3600)


class MoveIn(Strict):
    user_id: int


class JoinIn(Strict):
    join_code: str = Field(min_length=1, max_length=12)


class TeamIn(Strict):
    name: str = Field(max_length=80)


def student_only(auth: Auth) -> None:
    if auth.user.role != Role.student:
        raise ApiError(403, "auth.forbidden")


async def _admin(db: AsyncSession, auth: Auth, t) -> dict:
    return await svc.admin_view(db, t, auth.user)


# ---------------- professor ----------------
@router.post("", status_code=201)
async def create(body: CreateIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    if body.mode not in svc.MODES:
        raise ApiError(422, "tournament.invalid_mode")
    name = " ".join(body.name.split())
    if not name:
        raise ApiError(422, "tournament.invalid_name")
    t = await svc.create(db, auth.user, body.class_id, name, body.mode)
    await audit(db, auth.user.id, "tournament.created", {"tournament_id": t.id})
    await db.commit()
    return await _admin(db, auth, t)


@router.get("")
async def list_tournaments(class_id: int | None = Query(default=None), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return {"tournaments": await svc.list_for(db, auth.user, class_id)}


@router.post("/join")
async def join(body: JoinIn, request: Request, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    student_only(auth)
    return {"tournament_id": await svc.join(db, auth.user, body.join_code, client_ip(request))}


@router.get("/{tid}/admin")
async def admin(tid: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.owned(db, tid, auth.user))


@router.put("/{tid}/rounds/{idx}")
async def update_round(tid: int, idx: int, body: RoundIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    await svc.update_round(db, auth.user, tid, idx, body.model_dump(exclude_none=True))
    return await _admin(db, auth, await svc.owned(db, tid, auth.user))


@router.post("/{tid}/rounds/{idx}/start")
async def start(tid: int, idx: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.start_round(db, auth.user, tid, idx))


@router.post("/{tid}/rounds/{idx}/pause")
async def pause(tid: int, idx: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.pause_round(db, auth.user, tid, idx))


@router.post("/{tid}/rounds/{idx}/resume")
async def resume(tid: int, idx: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.resume_round(db, auth.user, tid, idx))


@router.post("/{tid}/rounds/{idx}/extend")
async def extend(tid: int, idx: int, body: ExtendIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.extend_round(db, auth.user, tid, idx, body.seconds))


@router.post("/{tid}/rounds/{idx}/close")
async def close(tid: int, idx: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.close_round(db, auth.user, tid, idx))


@router.post("/{tid}/finish")
async def finish(tid: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await svc.finish(db, auth.user, tid))


@router.post("/{tid}/teams/{team_id}/move")
async def move(tid: int, team_id: int, body: MoveIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    await svc.move_player(db, auth.user, tid, team_id, body.user_id)
    return await _admin(db, auth, await svc.owned(db, tid, auth.user))


# ---------------- alunos ----------------
@router.post("/{tid}/teams", status_code=201)
async def create_team(tid: int, body: TeamIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    student_only(auth)
    return {"teams": await svc.create_team(db, auth.user, tid, body.name)}


@router.post("/{tid}/teams/{team_id}/join")
async def join_team(tid: int, team_id: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    student_only(auth)
    return {"teams": await svc.join_team(db, auth.user, tid, team_id)}


# ---------------- leitura (alunos da turma, projetor e professor) ----------------
@router.get("/{tid}/state")
async def state(tid: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await svc.snapshot(db, await svc.viewable(db, tid, auth.user), auth.user)


@router.get("/{tid}/events")
async def get_events(tid: int, after: int = Query(default=0, ge=0), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    await svc.viewable(db, tid, auth.user)
    evs, resync = await events.replay(db, tid, after)
    return {"events": evs, "resync": resync}


@router.get("/{tid}/hints/{slug}/{n}")
async def hint(tid: int, slug: str, n: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    student_only(auth)
    return await svc.open_hint(db, auth.user, tid, slug, n)
