from uuid import uuid4

from fastapi import APIRouter, HTTPException

from ..schemas import CreateNoteRequest, Note, UpdateNoteRequest, now_iso
from ..store import store

router = APIRouter(prefix="/api")


@router.get("/notebooks/{notebook_id}/notes", response_model=list[Note])
def list_notes(notebook_id: str) -> list[Note]:
    return store.notes.get(notebook_id, [])


@router.post("/notebooks/{notebook_id}/notes", response_model=Note)
def create_note(notebook_id: str, payload: CreateNoteRequest) -> Note:
    note = Note(id=str(uuid4()), notebook_id=notebook_id, title=payload.title, content=payload.content, created_at=now_iso())
    store.notes.setdefault(notebook_id, []).append(note)
    return note


@router.patch("/notes/{note_id}", response_model=Note)
def update_note(note_id: str, payload: UpdateNoteRequest) -> Note:
    for notes in store.notes.values():
        for note in notes:
            if note.id == note_id:
                note.title = payload.title
                note.content = payload.content
                return note
    raise HTTPException(status_code=404, detail="Note not found")
