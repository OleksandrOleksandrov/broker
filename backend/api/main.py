import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# This module is the ASGI app, but it is reachable as `api.main` when uvicorn
# is started from backend/ and as a top-level `main` when it is started from
# backend/api/ (which is what scripts/run_local.py does). The `api` package
# itself is only importable from backend/, so put that on the path first
# rather than failing with ModuleNotFoundError depending on the cwd.
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from api.routers import (  # noqa: E402
    invoice_router,
    application_router,
    cmr_router,
    transport_router,
    export_router,
    pdf_router,
)
from api.utils.logging_config import setup_logging  # noqa: E402

load_dotenv()

logger = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_group=os.getenv("CLOUDWATCH_LOG_GROUP"),
    stream_name=os.getenv("CLOUDWATCH_LOG_STREAM"),
    region_name=os.getenv("AWS_REGION"),
)

app = FastAPI(
    title="Broker AI Assistant",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Дозволяємо запити з Node.js фронтенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """Log every API request and its response status."""
    started_at = time.perf_counter()
    logger.info("Request started: %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "Request failed: %s %s (%.1f ms)",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# Include routers
app.include_router(invoice_router)
app.include_router(application_router)
app.include_router(cmr_router)
app.include_router(transport_router)
app.include_router(export_router)
app.include_router(pdf_router)