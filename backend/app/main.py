"""Spendly API - FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, anomalies, auth, categories, settings, statements, transactions
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.database import mongo
from app.services.statements import resume_interrupted_deletions

log = logging.getLogger("spendly")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = await mongo.connect()
    await resume_interrupted_deletions(db)
    yield
    await mongo.disconnect()


def create_app(use_lifespan: bool = True) -> FastAPI:
    setup_logging()
    s = get_settings()
    app = FastAPI(
        title=s.app_name, version="1.0.0", lifespan=lifespan if use_lifespan else None,
        docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"  # financial data should not be cached
        return resp

    register_error_handlers(app)
    for r in (auth, statements, transactions, categories, analytics, anomalies, settings):
        app.include_router(r.router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    async def health():
        await mongo.get_db().command("ping") if not s.mongodb_url.startswith("mongomock") else None
        return {"status": "ok"}

    return app


app = create_app()
