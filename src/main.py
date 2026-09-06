"""FastAPI application entrypoint: `uvicorn src.main:app`."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api import (
    routes_analysis,
    routes_blacklist,
    routes_history,
    routes_knowledge,
    routes_statistics,
)
from src.api.responses import error_body, ok
from src.config import PROJECT_ROOT
from src.db.database import init_db
from src.domain.errors import DomainError, ErrorCode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PhishingEml API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, exc.code.value, exc.message),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=error_body(request, ErrorCode.VALIDATION_ERROR.value, "请求参数校验失败"),
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    code = (
        ErrorCode.RECORD_NOT_FOUND.value
        if exc.status_code == 404
        else ErrorCode.INTERNAL_ERROR.value
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, code, str(exc.detail)),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error")
    return JSONResponse(
        status_code=500,
        content=error_body(request, ErrorCode.INTERNAL_ERROR.value, "服务内部错误"),
    )


app.include_router(routes_analysis.router, prefix="/api")
app.include_router(routes_history.router, prefix="/api")
app.include_router(routes_blacklist.router, prefix="/api")
app.include_router(routes_statistics.router, prefix="/api")
app.include_router(routes_knowledge.router, prefix="/api")

WEB_DIR = PROJECT_ROOT / "src" / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def web_app():
    """Serve the local single-page interface for the course demo."""

    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health(request: Request):
    return ok(request, {"status": "ok"})
