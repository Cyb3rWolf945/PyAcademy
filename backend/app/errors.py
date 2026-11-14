# Erros da API: respondem sempre com {"error": "<chave.i18n>"}, nunca com frases.
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, key: str):
        self.status = status
        self.key = key


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse({"error": exc.key}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError):
        return JSONResponse({"error": "common.invalid_request"}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        key = {404: "common.not_found", 405: "common.method_not_allowed"}.get(
            exc.status_code, "common.error"
        )
        return JSONResponse({"error": key}, status_code=exc.status_code)
