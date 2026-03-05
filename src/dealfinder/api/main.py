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
from mangum import Mangum

from dealfinder.api.routes import deals, health, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    logger.info("Deal Finder API starting up")
    yield
    logger.info("Deal Finder API shutting down")


_is_dev = os.getenv("ENVIRONMENT", "dev") == "dev"

app = FastAPI(
    title="Deal Finder API",
    description="AI-powered deal discovery system — REST API",
    version="0.4.0",
    docs_url="/api/v1/docs" if _is_dev else None,
    redoc_url="/api/v1/redoc" if _is_dev else None,
    openapi_url="/api/v1/openapi.json" if _is_dev else None,
    lifespan=lifespan,
)

# Register routers under /api/v1
app.include_router(health.router, prefix="/api/v1")
app.include_router(deals.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


# AWS Lambda entry point — Mangum translates API Gateway events to ASGI
handler = Mangum(app, lifespan="auto")
