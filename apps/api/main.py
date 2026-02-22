"""Точка входа FastAPI-приложения и регистрация middleware/роутеров."""

# --- Imports ---
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .logging_setup import setup_logging
from .routers import agents, chat, citations, client_events, global_notes, llm, notebooks, notes, sources

app = FastAPI(title="Local RAG Assistant API")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notebooks.router)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(notes.router)
app.include_router(citations.router)
app.include_router(global_notes.router)
app.include_router(llm.router)
app.include_router(client_events.router)
app.include_router(agents.router)


# --- Основные блоки ---
@app.on_event("startup")
def on_startup() -> None:
    app_log, ui_log = setup_logging()
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
