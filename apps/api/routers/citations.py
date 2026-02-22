"""Роуты сохранённых цитат (persistent per-notebook)."""

# --- Imports ---
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from ..schemas import SaveCitationRequest, SavedCitation
from ..store import store

router = APIRouter(prefix="/api", tags=["citations"])


# --- Основные блоки ---
@router.get("/notebooks/{notebook_id}/saved-citations", response_model=list[SavedCitation])
def list_saved_citations(notebook_id: str) -> list[SavedCitation]:
    if notebook_id not in store.notebooks:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return store.list_saved_citations(notebook_id)


@router.post("/notebooks/{notebook_id}/saved-citations", response_model=SavedCitation)
def save_citation(notebook_id: str, payload: SaveCitationRequest) -> SavedCitation:
    if notebook_id not in store.notebooks:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return store.save_citation(
        notebook_id=notebook_id,
        source_id=payload.source_id,
        filename=payload.filename,
        doc_order=payload.doc_order,
        chunk_text=payload.chunk_text,
        page=payload.page,
        sheet=payload.sheet,
        source_notebook_id=payload.source_notebook_id,
        source_type=payload.source_type,
    )


@router.delete("/notebooks/{notebook_id}/saved-citations/{citation_id}", status_code=204, response_class=Response)
def delete_saved_citation(notebook_id: str, citation_id: str) -> Response:
    if not store.delete_saved_citation(notebook_id, citation_id):
        raise HTTPException(status_code=404, detail="Citation not found")
    return Response(status_code=204)
