# Saúde: /api/health (liveness, sem BD) e /api/ready (BD acessível).
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "common.not_ready"}, status_code=503)
    return {"status": "ready"}
