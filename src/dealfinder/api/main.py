"""Deal Finder FastAPI application.

Creates the FastAPI application and registers all route modules.
The ``handler`` variable wraps the app with the Mangum ASGI adapter
for execution as an AWS Lambda function behind API Gateway.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from dealfinder.api.routes import deals, health, search, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    logger.info("Deal Finder API starting up")
    yield
    logger.info("Deal Finder API shutting down")


_is_dev = os.getenv("ENVIRONMENT", "dev") == "dev"

# CORS_ALLOWED_ORIGINS is a comma-separated list of allowed origins.
# Defaults to wildcard for local dev; set explicitly in prod Lambda env.
_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app = FastAPI(
    title="Deal Finder API",
    description="AI-powered deal discovery system — REST API",
    version="0.4.0",
    docs_url="/api/v1/docs" if _is_dev else None,
    redoc_url="/api/v1/redoc" if _is_dev else None,
    openapi_url="/api/v1/openapi.json" if _is_dev else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api/v1
app.include_router(health.router, prefix="/api/v1")
app.include_router(deals.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")


# AWS Lambda entry point — Mangum translates API Gateway events to ASGI
handler = Mangum(app, lifespan="auto")
