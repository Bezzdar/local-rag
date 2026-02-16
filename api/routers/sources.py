from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..schemas import AddPathRequest, Source
from ..store import store

router = APIRouter(prefix="/api")


@router.get("/notebooks/{notebook_id}/sources", response_model=list[Source])
def list_sources(notebook_id: str) -> list[Source]:
    return [s for s in store.sources.values() if s.notebook_id == notebook_id]


@router.post("/notebooks/{notebook_id}/sources/upload", response_model=Source)
async def upload_source(notebook_id: str, file: UploadFile = File(...)) -> Source:
    content = await file.read()
    return await store.save_upload(notebook_id, file.filename or "unknown.bin", content)


@router.post("/notebooks/{notebook_id}/sources/add-path", response_model=Source)
def add_source_path(notebook_id: str, payload: AddPathRequest) -> Source:
    return store.add_source_from_path(notebook_id, payload.path)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str) -> None:
    if source_id not in store.sources:
        raise HTTPException(status_code=404, detail="Source not found")
    del store.sources[source_id]


@router.get("/files")
def get_file(path: str):
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)
