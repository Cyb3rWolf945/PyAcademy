# Teste de carga manual: N submissões simultâneas de um programa certo, de ponta a ponta
# (API -> fila Postgres -> dispatcher -> runner -> resultado). Mede o tempo até ao resultado (p50/p95).
# Uso (dentro do contentor da app, com a stack a correr):
#   docker compose run --rm app python -m tests.perf.submit_load [N] [rondas]
# Cria N utilizadores temporários "perf-*" e apaga-os no fim.
import asyncio
import statistics
import sys
import time
import uuid

import httpx
from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal
from app.models.user import User
from app.services import security

BASE = "http://app:8000"
CODE = 'a = int(input())\nb = int(input())\nf = a - b\nif f > 2:\n    print("Vai a andar")\nelif f >= 0:\n    print("Corre!")\nelse:\n    print("Pede boleia")\n'


async def one(user: str):
    c = httpx.AsyncClient(base_url=BASE, headers={"Origin": settings.public_origin}, timeout=30)
    r = await c.post("/api/auth/login", json={"username": user, "password": "perf-password-1"})
    return c, {"X-CSRF-Token": r.json()["csrf_token"]}


async def fire(c, h, start_evt) -> float:
    await start_evt.wait()
    t0 = time.perf_counter()
    r = await c.post("/api/submissions", headers=h, json={"client_id": str(uuid.uuid4()), "problem_slug": "autocarro-ainda-da", "code": CODE})
    sid = r.json()["id"]
    while True:
        s = (await c.get(f"/api/submissions/{sid}", headers=h)).json()
        if s["status"] not in ("queued", "running"):
            assert s["status"] == "accepted", s
            return time.perf_counter() - t0
        await asyncio.sleep(0.05)


async def main(n: int, rounds: int) -> None:
    names = [f"perf-{i}" for i in range(n)]
    async with SessionLocal() as db:
        pw = await security.hash_password("perf-password-1")
        for name in names:
            db.add(User(username=name, display_name=name, password_hash=pw))
        await db.commit()
    try:
        sessions = [await one(name) for name in names]
        times: list[float] = []
        for _ in range(rounds):
            evt = asyncio.Event()
            tasks = [asyncio.create_task(fire(c, h, evt)) for c, h in sessions]
            await asyncio.sleep(0.2)
            evt.set()
            times += await asyncio.gather(*tasks)
            await asyncio.sleep(1)
        times.sort()
        q = statistics.quantiles(times, n=100, method="inclusive")
        print(f"{len(times)} submissões ({n} em simultâneo x {rounds}): p50={q[49]:.3f}s p95={q[94]:.3f}s max={times[-1]:.3f}s")
        for c, _ in sessions:
            await c.aclose()
    finally:
        async with SessionLocal() as db:
            await db.execute(delete(User).where(User.username.like("perf-%")))
            await db.commit()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20, int(sys.argv[2]) if len(sys.argv) > 2 else 3))
