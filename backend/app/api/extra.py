# Rotas REST das atividades extra: definições da turma, poker (mesas, lugares, ações, estado, saldo, consentimento,
# auditoria do professor) e Bit a Bit (partida, fim, recordes). Erros: {"error": "extra.<chave>"}.

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Auth, active_auth, origin_guard, teacher_auth
from app.db import get_db
from app.errors import ApiError
from app.models.extra import PokerSeat
from app.models.user import Role, SchoolClass
from app.services import extra, extra_bitabit, extra_poker as poker

router = APIRouter(prefix="/api/extra", dependencies=[Depends(origin_guard)])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SettingsIn(Strict):
    class_id: int | None = None
    poker_enabled: bool | None = None
    poker_source: str | None = Field(default=None, pattern="^(torneios|todos)$")
    daily_loss_limit: int | None = Field(default=None, ge=1, le=10000)
    buy_in_min: int | None = Field(default=None, ge=1, le=1000)
    buy_in_max: int | None = Field(default=None, ge=1, le=10000)
    buy_in_max_pct: int | None = Field(default=None, ge=1, le=100)
    students_can_create_tables: bool | None = None
    max_tables: int | None = Field(default=None, ge=0, le=20)
    bitabit_daily_cap: int | None = Field(default=None, ge=0, le=500)


class TableIn(Strict):
    class_id: int | None = None
    name: str = Field(min_length=1, max_length=40)
    max_seats: int = Field(default=6, ge=2, le=10)


class SitIn(Strict):
    seat: int
    buy_in: int


class ActionIn(Strict):
    action_id: str = Field(min_length=8, max_length=64)
    type: str = Field(max_length=10)
    amount: int | None = Field(default=None, ge=0, le=10_000_000)


class FinishIn(Strict):
    answers: list[dict] = Field(max_length=100)
    score: int | None = None


async def _default_class(db: AsyncSession, auth: Auth, class_id: int | None) -> int | None:
    if class_id is not None or auth.user.role != Role.teacher:
        return class_id
    first = (await db.execute(select(SchoolClass.id).where(SchoolClass.teacher_id == auth.user.id).order_by(SchoolClass.id).limit(1))).scalar()
    return first


# ---------------- definições ----------------
@router.get("/settings")
async def get_settings(class_id: int | None = Query(default=None), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    cls = await extra.class_for(db, auth.user, await _default_class(db, auth, class_id))
    return await extra.get_settings(db, cls.id)


@router.patch("/settings")
async def patch_settings(body: SettingsIn, auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    cls = await extra.class_for(db, auth.user, await _default_class(db, auth, body.class_id))
    data = body.model_dump(exclude_none=True, exclude={"class_id"})
    cur = await extra.get_settings(db, cls.id)
    if data.get("buy_in_min", cur["buy_in_min"]) > data.get("buy_in_max", cur["buy_in_max"]):
        raise ApiError(422, "extra.invalid_settings")
    return await extra.update_settings(db, cls.id, data)


# ---------------- poker ----------------
@router.get("/poker/me")
async def poker_me(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    u = auth.user
    if u.role != Role.student or u.class_id is None:
        return {"balance": 0, "source": None, "today_lost": 0, "daily_loss_limit": 0, "consented": False, "can_play": False, "reason": "students_only"}
    st = await extra.get_settings(db, u.class_id)
    avail = await extra.available(db, u.id, st["poker_source"])
    lost = await extra.loss_today(db, u.id)
    consent = await extra.has_consent(db, u.id)
    lo, hi = extra.buyin_limits(st, avail)
    reason = ("poker_disabled" if not st["poker_enabled"] else "consent_required" if not consent else "loss_limit_reached" if lost >= st["daily_loss_limit"]
              else "insufficient_balance" if avail < st["buy_in_min"] or hi < lo else None)
    seat = (await db.execute(select(PokerSeat).where(PokerSeat.user_id == u.id))).scalars().first()
    out = {"balance": avail, "source": st["poker_source"], "today_lost": lost, "daily_loss_limit": st["daily_loss_limit"], "consented": consent,
           "can_play": reason is None, "reserved": await extra.reserved(db, u.id), "buy_in_min": lo, "buy_in_max": max(lo, hi) if reason is None else hi,
           "seated_table_id": seat.table_id if seat else None}
    if reason:
        out["reason"] = reason
    return out


@router.post("/poker/consent")
async def poker_consent(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    if auth.user.role != Role.student:
        raise ApiError(403, "extra.students_only")
    await extra.accept_consent(db, auth.user.id)
    return {"consented": True}


@router.get("/poker/tables")
async def poker_tables(class_id: int | None = Query(default=None), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return {"tables": await poker.list_tables(db, auth.user, await _default_class(db, auth, class_id))}


@router.post("/poker/tables", status_code=201)
async def poker_create(body: TableIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    name = " ".join(body.name.split())
    if not name:
        raise ApiError(422, "extra.invalid_name")
    t = await poker.create_table(db, auth.user, await _default_class(db, auth, body.class_id), name, body.max_seats)
    return poker.table_view(t)


@router.get("/poker/tables/{table_id}/state")
async def poker_state(table_id: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await poker.snapshot(db, await poker.get_table(db, table_id, auth.user), auth.user)


@router.get("/poker/tables/{table_id}/events")
async def poker_events(table_id: int, after: int = Query(default=0, ge=0), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    await poker.get_table(db, table_id, auth.user)
    evs = await poker.events_after(db, table_id, after, 501)
    return {"events": [e for e in evs[:500] if poker.visible_to(e, auth.user.id)], "resync": len(evs) > 500}


@router.post("/poker/tables/{table_id}/sit")
async def poker_sit(table_id: int, body: SitIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    t = await poker.sit(db, auth.user, table_id, body.seat, body.buy_in)
    return await poker.snapshot(db, t, auth.user)


@router.post("/poker/tables/{table_id}/leave")
async def poker_leave(table_id: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return {"ok": True, "stack": await poker.leave(db, auth.user, table_id)}


@router.post("/poker/tables/{table_id}/back")
async def poker_back(table_id: int, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await poker.snapshot(db, await poker.back(db, auth.user, table_id), auth.user)


@router.post("/poker/tables/{table_id}/action")
async def poker_action(table_id: int, body: ActionIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    t, dup = await poker.act(db, auth.user, table_id, body.action_id, body.type, body.amount)
    return {**await poker.snapshot(db, t, auth.user), "duplicate": dup}


@router.get("/poker/hands")
async def poker_hands(table: int, limit: int = Query(default=50, ge=1, le=200), auth: Auth = Depends(teacher_auth), db: AsyncSession = Depends(get_db)):
    """Auditoria do professor: todas as mãos com TODAS as cartas."""
    return {"hands": await poker.hands_for_audit(db, auth.user, table, limit)}


# ---------------- Bit a Bit ----------------
@router.get("/bitabit/me")
async def bitabit_me(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await extra_bitabit.me(db, auth.user)


@router.post("/bitabit/start")
async def bitabit_start(auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await extra_bitabit.start(db, auth.user)


@router.post("/bitabit/{game_id}/finish")
async def bitabit_finish(game_id: int, body: FinishIn, auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await extra_bitabit.finish(db, auth.user, game_id, body.answers, body.score)


@router.get("/bitabit/leaderboard")
async def bitabit_leaderboard(class_id: int | None = Query(default=None), auth: Auth = Depends(active_auth), db: AsyncSession = Depends(get_db)):
    return await extra_bitabit.leaderboard(db, auth.user, await _default_class(db, auth, class_id))


