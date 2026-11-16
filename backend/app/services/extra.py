# Atividades extra: definições por turma, saldo de poker (fonte "torneios" ou "todos"), perda diária (Europe/Lisbon),
# consentimento e limite diário do Bit a Bit. Tudo calculado a partir do livro único user_points.
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models._base import utcnow
from app.models.extra import ExtraSettings, PokerConsent, PokerSeat
from app.models.points import UserPoints
from app.models.user import Role, SchoolClass, User
from app.services.leaderboard import LISBON

TOURNAMENT_REASONS = ("group_win", "champion", "second", "third", "participation")
DEFAULTS = {
    "poker_enabled": True, "poker_source": "torneios", "students_can_create_tables": True, "max_tables": 4,
    "buy_in_min": 10, "buy_in_max": 200, "buy_in_max_pct": 50, "daily_loss_limit": 100, "bitabit_daily_cap": 50,
}


def day_start(now: datetime | None = None) -> datetime:
    """Meia-noite de hoje em Lisboa, em UTC."""
    local = (now or utcnow()).astimezone(LISBON)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


async def class_for(db: AsyncSession, user: User, class_id: int | None = None) -> SchoolClass:
    """A turma do aluno, ou uma turma do professor (class_id). Outra turma = não existe (privacidade entre turmas)."""
    if user.role == Role.teacher:
        cls = await db.get(SchoolClass, class_id) if class_id is not None else None
        if cls is None or cls.teacher_id != user.id:
            raise ApiError(404, "extra.class_not_found")
        return cls
    if user.class_id is None or (class_id is not None and class_id != user.class_id):
        raise ApiError(404, "extra.class_not_found")
    return await db.get(SchoolClass, user.class_id)


async def get_settings(db: AsyncSession, class_id: int) -> dict:
    row = await db.get(ExtraSettings, class_id)
    return {k: (getattr(row, k) if row else v) for k, v in DEFAULTS.items()} | {"class_id": class_id}


async def update_settings(db: AsyncSession, class_id: int, data: dict) -> dict:
    row = await db.get(ExtraSettings, class_id)
    if row is None:
        row = ExtraSettings(class_id=class_id)
        db.add(row)
    for k, v in data.items():
        setattr(row, k, v)
    await db.commit()
    return await get_settings(db, class_id)


async def ledger_balance(db: AsyncSession, user_id: int, source: str) -> int:
    q = select(func.coalesce(func.sum(UserPoints.points), 0)).where(UserPoints.user_id == user_id)
    if source != "todos":  # só pontos de torneios (+ o líquido do poker)
        q = q.where((UserPoints.reason.in_(TOURNAMENT_REASONS + ("poker_net",))) | ((UserPoints.reason == "exercise") & UserPoints.tournament_id.is_not(None)))
    return int((await db.execute(q)).scalar_one())


async def reserved(db: AsyncSession, user_id: int) -> int:
    return int((await db.execute(select(func.coalesce(func.sum(PokerSeat.buy_in), 0)).where(PokerSeat.user_id == user_id))).scalar_one())


async def available(db: AsyncSession, user_id: int, source: str) -> int:
    """Saldo para o poker: nunca abaixo de 0 e sem o que já está reservado nas mesas."""
    return max(0, await ledger_balance(db, user_id, source) - await reserved(db, user_id))


async def loss_today(db: AsyncSession, user_id: int) -> int:
    net = int((await db.execute(select(func.coalesce(func.sum(UserPoints.points), 0)).where(
        UserPoints.user_id == user_id, UserPoints.reason == "poker_net", UserPoints.created_at >= day_start()))).scalar_one())
    return max(0, -net)


def buyin_limits(settings: dict, avail: int) -> tuple[int, int]:
    """(mínimo, máximo) do buy-in: 10 .. min(200, 50% do saldo disponível)."""
    return settings["buy_in_min"], min(settings["buy_in_max"], avail * settings["buy_in_max_pct"] // 100)


async def has_consent(db: AsyncSession, user_id: int) -> bool:
    return await db.get(PokerConsent, user_id) is not None


async def accept_consent(db: AsyncSession, user_id: int) -> None:
    if await db.get(PokerConsent, user_id) is None:
        db.add(PokerConsent(user_id=user_id, accepted_at=utcnow()))
        await db.commit()


