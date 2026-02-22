"""Роуты глобальных заметок (persistent, cross-notebook)."""

# --- Imports ---
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from ..schemas import CreateGlobalNoteRequest, GlobalNote
from ..store import store

router = APIRouter(prefix="/api", tags=["global_notes"])


# --- Основные блоки ---
@router.get("/notes", response_model=list[GlobalNote])
def list_global_notes() -> list[GlobalNote]:
    return store.list_global_notes()


@router.post("/notes", response_model=GlobalNote)
def create_global_note(payload: CreateGlobalNoteRequest) -> GlobalNote:
    return store.save_global_note(
        content=payload.content,
        source_notebook_id=payload.source_notebook_id,
        source_notebook_title=payload.source_notebook_title,
        source_refs=payload.source_refs,
    )


@router.delete("/notes/{note_id}", status_code=204, response_class=Response)
def delete_global_note(note_id: str) -> Response:
    if not store.delete_global_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return Response(status_code=204)
