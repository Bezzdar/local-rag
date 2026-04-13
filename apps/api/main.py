"""Точка входа FastAPI-приложения и регистрация middleware/роутеров."""

# --- Imports ---
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .logging_setup import setup_logging
from .services.auth_articles_db import init_content_db, seed_admin_if_missing
from .routers import agents, auth_articles, chat, citations, client_events, global_notes, llm, notebooks, sources

app = FastAPI(title="Local RAG Assistant API")
logger = logging.getLogger(__name__)

cors_origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://46.17.102.10:3000").split(",") if item.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notebooks.router)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(citations.router)
app.include_router(global_notes.router)
app.include_router(llm.router)
app.include_router(client_events.router)
app.include_router(agents.router)
app.include_router(auth_articles.router)


# --- Основные блоки ---
@app.on_event("startup")
def on_startup() -> None:
    app_log, ui_log = setup_logging()
    init_content_db()
    seed_admin_if_missing()
    logger.info(
        "Application startup completed",
        extra={"event": "app.ready", "details": f"app_log={app_log} | ui_log={ui_log}"},
    )


@app.middleware("http")
async def http_logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    client_ip = request.client.host if request.client else "-"
    logger.info(
        "HTTP request started",
        extra={
            "event": "http.request.start",
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
        },
    )
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "HTTP request completed",
        extra={
            "event": "http.request.end",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        },
    )
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Local RAG Assistant API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
