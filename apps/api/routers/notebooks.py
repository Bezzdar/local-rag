"""Роуты жизненного цикла notebook-сущностей."""

# --- Imports ---
from fastapi import APIRouter, HTTPException

from ..schemas import CreateNotebookRequest, IndexStatus, Notebook, ParsingSettings, UpdateNotebookRequest
from ..store import store

router = APIRouter(prefix="/api", tags=["notebooks"])


# --- Основные блоки ---
@router.get("/notebooks", response_model=list[Notebook])
def list_notebooks() -> list[Notebook]:
    return list(store.notebooks.values())


@router.post("/notebooks", response_model=Notebook)
def create_notebook(payload: CreateNotebookRequest) -> Notebook:
    return store.create_notebook(payload.title)


@router.get("/notebooks/{notebook_id}", response_model=Notebook)
def get_notebook(notebook_id: str) -> Notebook:
    notebook = store.notebooks.get(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


@router.patch("/notebooks/{notebook_id}", response_model=Notebook)
def update_notebook(notebook_id: str, payload: UpdateNotebookRequest) -> Notebook:
    notebook = store.update_notebook_title(notebook_id, payload.title)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


@router.post("/notebooks/{notebook_id}/duplicate", response_model=Notebook)
def duplicate_notebook(notebook_id: str) -> Notebook:
    notebook = store.duplicate_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


@router.delete("/notebooks/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: str) -> None:
    if not store.delete_notebook(notebook_id):
        raise HTTPException(status_code=404, detail="Notebook not found")


@router.get("/notebooks/{notebook_id}/index/status", response_model=IndexStatus)
def index_status(notebook_id: str) -> IndexStatus:
    items = [source for source in store.sources.values() if source.notebook_id == notebook_id]
    return IndexStatus(
        total=len(items),
        indexed=sum(1 for source in items if source.status == "indexed"),
        indexing=sum(1 for source in items if source.status == "indexing"),
        failed=sum(1 for source in items if source.status == "failed"),
    )


@router.get("/notebooks/{notebook_id}/parsing-settings", response_model=ParsingSettings)
def get_parsing_settings(notebook_id: str) -> ParsingSettings:
    notebook = store.notebooks.get(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return store.get_parsing_settings(notebook_id)


@router.patch("/notebooks/{notebook_id}/parsing-settings", response_model=ParsingSettings)
def update_parsing_settings(notebook_id: str, payload: ParsingSettings) -> ParsingSettings:
    notebook = store.notebooks.get(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return store.update_parsing_settings(notebook_id, payload)
