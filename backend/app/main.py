"""FastAPI application factory."""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import chat, feedback, files, meta
from app.container import Container, build_container
from app.core.config import Settings, get_settings
from app.core.errors import AppError, PayloadTooLarge, error_body
from app.core.logging import configure_logging, request_id_var
from app.db.repositories import FileRepository

logger = logging.getLogger("app")

API_PREFIX = "/api/v1"
PURGE_INTERVAL_SECONDS = 3600


async def _purge_loop(container: Container) -> None:
    while True:
        try:
            async with container.db.session_factory() as session:
                purged = await FileRepository(session).purge_expired()
            if purged:
                logger.info("purged %s expired uploads", purged)
        except Exception:
            logger.exception("upload purge failed")
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or build_container(settings)
        if settings.app_env == "development" and settings.database_url.startswith("sqlite"):
            # Zero-setup local dev; Postgres/production schemas are managed by Alembic.
            await app.state.container.db.create_all()
        purge_task = asyncio.create_task(_purge_loop(app.state.container))
        logger.info(
            "started env=%s llm=%s search=%s",
            settings.app_env,
            app.state.container.llm.name,
            app.state.container.search.name,
        )
        yield
        purge_task.cancel()
        with suppress(asyncio.CancelledError):
            await purge_task
        await app.state.container.db.dispose()

    app = FastAPI(
        title="Nexa AI Assistant API",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    if container is not None:
        app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Client-Id", "Authorization"],
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Reject oversized bodies from Content-Length before they are buffered."""
        if request.method in ("POST", "PUT", "PATCH"):
            limit = settings.max_request_bytes
            if request.url.path == f"{API_PREFIX}/files":
                limit = settings.upload_max_bytes + 64 * 1024  # multipart overhead
            length = request.headers.get("content-length")
            if length is None and request.headers.get("transfer-encoding", "").lower() == "chunked":
                return await _app_error(request, PayloadTooLarge("Chunked request bodies are not accepted."))
            if length is not None and (not length.isdigit() or int(length) > limit):
                return await _app_error(request, PayloadTooLarge("The request is too large."))
        return await call_next(request)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = (request.headers.get("x-request-id") or uuid.uuid4().hex)[:64]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            duration = int((time.perf_counter() - started) * 1000)
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if not request.url.path.startswith(API_PREFIX):
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
                    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
                )
            if request.url.path.startswith(API_PREFIX) and request.url.path != f"{API_PREFIX}/health":
                # For SSE responses this is time-to-headers; generation latency is in chat_requests.
                logger.info(
                    "%s %s -> %s (%sms)",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration,
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": duration,
                    },
                )
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, request_id_var.get(), exc.details), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(err.get("loc", [])), "msg": err.get("msg", "")} for err in exc.errors()]
        return JSONResponse(
            error_body("validation_error", "The request is invalid.", request_id_var.get(), details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(error_body(code, str(exc.detail), request_id_var.get()), status_code=exc.status_code)

    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(OSError)
    async def _dependency_unavailable(_request: Request, exc: Exception) -> JSONResponse:
        # Database/network outage: a known operational condition, not a bug -> one-line log, 503.
        logger.warning("dependency unavailable: %s: %s", type(exc).__name__, str(exc)[:200])
        return JSONResponse(
            error_body(
                "service_unavailable",
                "The service is temporarily unavailable. Please try again shortly.",
                request_id_var.get(),
            ),
            status_code=503,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(
            error_body("internal_error", "Something went wrong. Please try again.", request_id_var.get()),
            status_code=500,
        )

    for module in (meta, chat, files, feedback):
        app.include_router(module.router, prefix=API_PREFIX)

    if settings.static_dir and Path(settings.static_dir).is_dir():
        _mount_spa(app, Path(settings.static_dir))
    return app


def _mount_spa(app: FastAPI, root: Path) -> None:
    """Serve the built frontend with client-side routing fallback (single-container deploys)."""
    root = root.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        if path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
