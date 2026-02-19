from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat, llm, notebooks, notes, sources

app = FastAPI(title="Local RAG Assistant API")

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
app.include_router(llm.router)


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
