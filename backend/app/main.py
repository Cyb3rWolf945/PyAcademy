# Cria a app FastAPI: middleware, rotas /api e ficheiros estáticos do frontend em "/".
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api import academy, documents, extra as extra_api, extra_ws, admin, auth, health, leaderboard, problems, submissions, tournament, ws
from app.config import settings
from app.errors import install_error_handlers
from app.realtime.pg_bus import hub
from app.services import dispatcher, elimination, extra_poker, tournament_scoring


class BodyLimitMiddleware:
    """Recusa corpos acima de max_body_bytes (por Content-Length e também em streaming)."""

    def __init__(self, app: ASGIApp, max_bytes: int, big: dict[str, int] | None = None):
        self.app, self.default, self.big = app, max_bytes, big or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.big.get(scope["path"], self.default) if scope.get("method") == "POST" else self.default
        too_big = JSONResponse({"error": "common.too_large"}, status_code=413)
        length = dict(scope["headers"]).get(b"content-length")
        if length and length.isdigit() and int(length) > limit:
            return await too_big(scope, receive, send)
        seen = 0

        async def limited_receive():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > limit:
                    raise _TooLarge
            return msg

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await too_big(scope, receive, send)


class _TooLarge(Exception):
    pass


class Frontend(StaticFiles):
    """Estáticos com cache: html/js sem cache (revalida por ETag); /vendor longa; /dist e /i18n sem cache (ETag)."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        resp = super().file_response(full_path, stat_result, scope, status_code)
        path = scope.get("path", "")
        if path.startswith("/vendor/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("/dist/") or path.startswith("/i18n/"):
            resp.headers["Cache-Control"] = "no-cache"  # revalida por ETag: nunca CSS/textos velhos depois de uma atualização
        else:
            resp.headers["Cache-Control"] = "no-cache"
        return resp


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Arranca o dispatcher da fila do runner neste worker (se houver RUNNER_URL) e pára-o ao sair."""
    stop, tasks = asyncio.Event(), []
    if settings.runner_url:
        tasks = dispatcher.start(stop)
    tasks.append(asyncio.create_task(elimination.autoclose_loop(stop)))
    tasks.append(asyncio.create_task(extra_poker.loop(stop)))  # temporizadores e início de mãos do poker
    yield
    await extra_ws.poker_hub.stop()
    await hub.stop()  # fecha os WebSockets deste worker (os clientes reconectam)
    await tournament_scoring.cancel_all()
    await elimination.cancel_all()
    stop.set()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    app = FastAPI(title="PyArena", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes, big={"/api/academy/documents": settings.docs_max_bytes})
    install_error_handlers(app)
    for r in (health.router, auth.router, admin.router, problems.router, submissions.router, tournament.router, ws.router, leaderboard.router, academy.router, documents.router, extra_api.router, extra_ws.router):
        app.include_router(r)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def api_not_found(path: str):
        return JSONResponse({"error": "common.not_found"}, status_code=404)

    if settings.frontend_dir.is_dir():
        app.mount("/", Frontend(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
