# Arranque único (antes do servidor): cria o professor inicial e sincroniza os problemas.
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models.user import Role, User
from app.services import security
from app.services.problems import sync_problems

log = logging.getLogger("pyarena.bootstrap")


async def seed_teacher(db: AsyncSession) -> bool:
    """Cria o professor do .env se não existir; tem de mudar a palavra-passe no 1.º login."""
    name = settings.teacher_username.strip().lower()
    if not name or not settings.teacher_password:
        return False
    if (await db.execute(select(User).where(User.username == name))).scalar_one_or_none():
        return False
    db.add(User(
        username=name, display_name=name, role=Role.teacher, must_change_password=True,
        password_hash=await security.hash_password(settings.teacher_password),
    ))
    try:
        await db.commit()
    except IntegrityError:  # outro processo foi mais rápido
        await db.rollback()
        return False
    return True


async def precompute_generated(db: AsyncSession) -> int:
    """Calcula (no runner) os args/devolve dos `args_gerador`; falhar aqui não impede a app de arrancar."""
    from app.models.problem import Problem
    from app.services import dispatcher
    from app.services.problems import ProblemSpec
    from app.services.runner_client import generator_exprs

    n = 0
    for p in (await db.execute(select(Problem))).scalars():
        spec = ProblemSpec.model_validate(p.data)
        if not generator_exprs(spec):
            continue
        try:
            await dispatcher._ensure_generated(db, p, spec)
            n += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("geradores de %s adiados: %s", p.slug, exc)
    return n


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with SessionLocal() as db:
        log.info("professor criado: %s", await seed_teacher(db))
        log.info("problemas sincronizados: %s", await sync_problems(db, settings.problems_dir))
        if settings.runner_url:
            log.info("geradores pré-calculados: %s", await precompute_generated(db))


if __name__ == "__main__":
    asyncio.run(main())
