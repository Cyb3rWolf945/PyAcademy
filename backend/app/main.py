# Cria a app FastAPI: middleware, rotas /api e ficheiros estáticos do frontend em "/".
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api import admin, auth, health, problems, submissions
from app.config import settings
from app.errors import install_error_handlers
from app.services import dispatcher


class BodyLimitMiddleware:
    """Recusa corpos acima de max_body_bytes (por Content-Length e também em streaming)."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        too_big = JSONResponse({"error": "common.too_large"}, status_code=413)
        length = dict(scope["headers"]).get(b"content-length")
        if length and length.isdigit() and int(length) > self.max_bytes:
            return await too_big(scope, receive, send)
        seen = 0

        async def limited_receive():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max_bytes:
                    raise _TooLarge
            return msg

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await too_big(scope, receive, send)


class _TooLarge(Exception):
    pass


class Frontend(StaticFiles):
    """Estáticos com cache: html/js sem cache (revalida por ETag); /vendor longa; /dist 1 dia."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        resp = super().file_response(full_path, stat_result, scope, status_code)
        path = scope.get("path", "")
        if path.startswith("/vendor/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("/dist/"):
            resp.headers["Cache-Control"] = "public, max-age=86400"
        else:
            resp.headers["Cache-Control"] = "no-cache"
        return resp


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Arranca o dispatcher da fila do runner neste worker (se houver RUNNER_URL) e pára-o ao sair."""
    stop, tasks = asyncio.Event(), []
    if settings.runner_url:
        tasks = dispatcher.start(stop)
    yield
    stop.set()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def create_app() -> FastAPI:
    app = FastAPI(title="PyArena", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    install_error_handlers(app)
    for r in (health.router, auth.router, admin.router, problems.router, submissions.router):
        app.include_router(r)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def api_not_found(path: str):
        return JSONResponse({"error": "common.not_found"}, status_code=404)

    if settings.frontend_dir.is_dir():
        app.mount("/", Frontend(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
