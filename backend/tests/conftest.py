# Fixtures dos testes: BD de teste separada (pyarena_test), cliente HTTP e utilizadores de exemplo.
import os

# Tem de vir ANTES de importar a app: a config lê o ambiente na importação.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://pyarena:pyarena@db:5432/pyarena_test"
)
os.environ.update(
    PUBLIC_ORIGIN="https://testserver", COOKIE_SECURE="true", SESSION_SECRET="test-secret",
    TEACHER_USERNAME="prof", TEACHER_PASSWORD="temp-pass-123",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import app.models  # noqa: E402,F401
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Role, SchoolClass, User  # noqa: E402
from app.services import security  # noqa: E402

ORIGIN = "https://testserver"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    url = make_url(os.environ["DATABASE_URL"])
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = (await conn.execute(text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": url.database})).scalar()
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin.dispose()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean(_database):
    async with engine.begin() as conn:
        names = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers={"Origin": ORIGIN}
    )


@pytest_asyncio.fixture
async def client():
    async with make_client() as c:
        yield c


@pytest.fixture
def new_client():
    """Fábrica de clientes com cookie jar próprio (para vários utilizadores no mesmo teste)."""
    return make_client


@pytest_asyncio.fixture
async def make_user():
    async def _make(username, role=Role.student, password="password-1", class_id=None, must_change=False, display_name=None):
        async with SessionLocal() as db:
            u = User(
                username=username, display_name=display_name or username, role=role, class_id=class_id,
                password_hash=await security.hash_password(password), must_change_password=must_change,
            )
            db.add(u)
            await db.commit()
            return u
    return _make


@pytest_asyncio.fixture
async def make_class():
    async def _make(teacher_id, name="Turma A", code="ABC234"):
        async with SessionLocal() as db:
            c = SchoolClass(name=name, join_code=code, teacher_id=teacher_id)
            db.add(c)
            await db.commit()
            return c
    return _make


async def login(client, username, password="password-1"):
    """Faz login e devolve os cabeçalhos CSRF para os pedidos seguintes."""
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}
