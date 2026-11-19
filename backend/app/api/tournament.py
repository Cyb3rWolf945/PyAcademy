# Rotas REST do torneio. O professor (dono, verificado no servidor) cria e controla; os alunos da turma
# entram, formam agências e pedem pistas; todos leem o snapshot do estado. Erros: {"error": "tournament.<chave>"}.
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, audit, client_ip, origin_guard, teacher_auth
from app.db import get_db
from app.errors import ApiError
from app.models.user import Role
from app.services import elimination, points as points_svc, tournament as svc
from app.services import tournament_anticheat as anticheat
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
    format: str = "eliminatoria"
    mode: str | None = None
    group_size: int | None = Field(default=None, ge=3, le=6)
    advance_per_group: int | None = Field(default=None, ge=1, le=2)
    points: dict[str, int] | None = None


class WinnerIn(Strict):
    user_id: int


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


class IncidentIn(Strict):
    client_id: str = Field(min_length=8, max_length=64)
    kind: Literal["paste", "drop", "blur", "hidden"]


def student_only(auth: Auth) -> None:
    if auth.user.role != Role.student:
        raise ApiError(403, "auth.forbidden")


async def _admin(db: AsyncSession, auth: Auth, t) -> dict:
    return await svc.admin_view(db, t, auth.user)


# ---------------- professor ----------------
@router.post("", status_code=201)
async def create(body: CreateIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    if body.format not in ("eliminatoria", "aula"):
        raise ApiError(422, "tournament.invalid_format")
    mode = body.mode or "individual"
    if mode not in svc.MODES:
        raise ApiError(422, "tournament.invalid_mode")
    if body.points is not None and (set(body.points) - set(points_svc.DEFAULT_POINTS) or any(not 0 <= v <= 1000 for v in body.points.values())):
        raise ApiError(422, "tournament.invalid_points")
    name = " ".join(body.name.split())
    if not name:
        raise ApiError(422, "tournament.invalid_name")
    t = await svc.create(db, auth.user, body.class_id, name, mode, body.format, body.group_size, body.advance_per_group, body.points)
    await audit(db, auth.user.id, "tournament.created", {"tournament_id": t.id})
    await db.commit()
    return await _admin(db, auth, t)


@router.get("")
async def list_tournaments(class_id: int | None = Query(default=None), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return {"tournaments": await svc.list_for(db, auth.user, class_id)}


@router.get("/lookup")
async def lookup(join_code: str = Query(min_length=1, max_length=12), auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    code = join_code.strip().upper()[:12]
    tournament = await svc.owned_by_code(db, code, auth.user)
    return {"tournament_id": tournament.id}


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


@router.post("/{tid}/rounds/{idx}/random")
async def random_round(tid: int, idx: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    """Sugere problemas aleatórios para a ronda (o professor revê e grava com PUT)."""
    return {"problem_slugs": await svc.random_problems(db, auth.user, tid, idx)}


@router.post("/{tid}/rounds/next/start")
async def start_next(tid: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    """Eliminatória: sorteia os grupos com os jogadores em jogo e começa a ronda pendente."""
    return await _admin(db, auth, await elimination.start_next(db, auth.user, tid))


@router.get("/{tid}/bracket-preview")
async def bracket_preview(
    tid: int, group_size: int | None = Query(default=None, ge=3, le=6), advance_per_group: int | None = Query(default=None, ge=1, le=2),
    auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db),
):
    t = await svc.owned(db, tid, auth.user)
    n = len(await elimination.alive_ids(db, tid))
    return elimination.bracket_preview(n, t.config, group_size, advance_per_group)


class ConfigIn(Strict):
    group_size: int | None = Field(default=None, ge=3, le=6)
    advance_per_group: int | None = Field(default=None, ge=1, le=2)
    points: dict[str, int] | None = None


@router.patch("/{tid}/config")
async def update_config(tid: int, body: ConfigIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    """Eliminatória, só no lobby: group_size, advance_per_group e pontos."""
    if body.points is not None and (set(body.points) - set(points_svc.DEFAULT_POINTS) or any(not 0 <= v <= 1000 for v in body.points.values())):
        raise ApiError(422, "tournament.invalid_points")
    return await _admin(db, auth, await elimination.update_config(db, auth.user, tid, body.model_dump(exclude_none=True)))


@router.post("/{tid}/groups/{gid}/winner")
async def group_winner(tid: int, gid: int, body: WinnerIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    return await _admin(db, auth, await elimination.set_winner(db, auth.user, tid, gid, body.user_id))


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


@router.post("/{tid}/anticheat/{user_id}/release")
async def anticheat_release(tid: int, user_id: int, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    """O professor deixa o aluno voltar ao torneio."""
    t = await svc.owned(db, tid, auth.user)
    await anticheat.release(db, t, auth.user, user_id)
    await audit(db, auth.user.id, "tournament.anticheat_released", {"tournament_id": tid, "user_id": user_id})
    await db.commit()
    return await _admin(db, auth, t)


# ---------------- alunos ----------------
@router.post("/{tid}/anticheat/report")
async def anticheat_report(tid: int, body: IncidentIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    student_only(auth)
    return await anticheat.report(db, await svc.viewable(db, tid, auth.user), auth.user, body.client_id, body.kind)


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
    return {"events": [e for e in evs if events.visible_to(e, auth.user.id)], "resync": resync}


@router.get("/{tid}/hints/{slug}/{n}")
async def hint(tid: int, slug: str, n: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    student_only(auth)
    return await svc.open_hint(db, auth.user, tid, slug, n)
