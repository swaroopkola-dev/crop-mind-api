from contextlib import asynccontextmanager
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings
from app.core.errors import http_exception_handler, validation_exception_handler
from app.db.client import close_client, get_database
from app.db.indexes import ensure_indexes
from app.routers import admin, auth, crops, health, live, recommendations

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(message)s")
logger = logging.getLogger("cropmind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_indexes(get_database())
    except PyMongoError as exc:
        logger.warning("MongoDB index setup unavailable (%s)", type(exc).__name__)
    yield
    close_client()


app = FastAPI(
    title="CropMind API",
    version="0.1.0",
    description="Explainable crop recommendation API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "If-None-Match", "X-Request-ID", "X-Seed-Token"],
    expose_headers=["ETag", "X-Request-ID"],
)
if settings.environment == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*.vercel.app", "localhost"])
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            '{"event":"request.failed","request_id":"%s","path":"%s"}',
            request_id,
            request.url.path,
        )
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred.",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    logger.info(
        '{"event":"request.completed","request_id":"%s","method":"%s","path":"%s","status":%s,"duration_ms":%.2f}',
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(crops.router, prefix="/api")
app.include_router(live.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/")
def root():
    return {"name": "CropMind API", "status": "ok", "docs": "/docs"}
