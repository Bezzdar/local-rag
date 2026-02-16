from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from ..config import DOCS_DIR, UPLOAD_MAX_BYTES
from ..schemas import AddPathRequest, Source
from ..store import store

router = APIRouter(prefix="/api", tags=["sources"])
HAS_MULTIPART = importlib.util.find_spec("multipart") is not None


def _sanitize_filename(filename: str) -> str:
    cleaned = Path(filename or "upload.bin").name
    return cleaned or "upload.bin"


def _extract_filename(headers: str) -> str:
    filename = "upload.bin"
    for header_line in headers.split("\r\n"):
        if "filename=" in header_line:
            raw = header_line.split("filename=", maxsplit=1)[1].strip()
            filename = raw.strip('"') or filename
            break
    return _sanitize_filename(filename)


def _force_fallback() -> bool:
    return os.getenv("FORCE_FALLBACK_MULTIPART", "0") == "1"


async def _persist_content(notebook_id: str, filename: str, content: bytes) -> Source:
    if len(content) > UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Upload too large")
    return await store.save_upload(notebook_id, _sanitize_filename(filename), content)


async def _save_multipart_file_stream(request: Request, notebook_id: str) -> tuple[str, Path]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type or "boundary=" not in content_type:
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")

    boundary = content_type.split("boundary=", maxsplit=1)[1].strip().strip('"')
    marker = f"\r\n--{boundary}".encode()
    header_done = False
    buffer = bytearray()
    total = 0
    output_file = None
    output_path: Path | None = None

    def _cleanup_partial_file() -> None:
        nonlocal output_file, output_path
        if output_file:
            output_file.close()
            output_file = None
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)

    async for chunk in request.stream():
        if not chunk:
            continue

        total += len(chunk)
        if total > UPLOAD_MAX_BYTES:
            _cleanup_partial_file()
            raise HTTPException(status_code=413, detail="Upload too large")

        buffer.extend(chunk)

        if not header_done and b"\r\n\r\n" in buffer:
            header_blob, body = bytes(buffer).split(b"\r\n\r\n", maxsplit=1)
            headers = header_blob.decode("utf-8", errors="ignore")
            if 'name="file"' not in headers:
                _cleanup_partial_file()
                raise HTTPException(status_code=400, detail="Multipart file field 'file' not found")
            filename = _extract_filename(headers)
            output_path = (DOCS_DIR / notebook_id) / f"{uuid4()}-{filename}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_file = output_path.open("wb")
            header_done = True
            buffer = bytearray(body)

        if header_done and output_file:
            boundary_index = buffer.find(marker)
            if boundary_index != -1:
                output_file.write(buffer[:boundary_index])
                output_file.close()
                return _sanitize_filename(output_path.name.split("-", maxsplit=1)[1]), output_path

            keep_tail = len(marker) + 4
            if len(buffer) > keep_tail:
                writable = len(buffer) - keep_tail
                output_file.write(buffer[:writable])
                buffer = buffer[writable:]

    _cleanup_partial_file()
    raise HTTPException(status_code=400, detail="Malformed multipart payload")


@router.get("/notebooks/{notebook_id}/sources", response_model=list[Source])
def list_sources(notebook_id: str) -> list[Source]:
    return [source for source in store.sources.values() if source.notebook_id == notebook_id]


@router.post("/notebooks/{notebook_id}/sources/upload", response_model=Source)
async def upload_source(notebook_id: str, request: Request) -> Source:
    if HAS_MULTIPART and not _force_fallback():
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Multipart file field 'file' not found")
        content = await file.read()
        return await _persist_content(notebook_id, file.filename or "upload.bin", content)

    _, file_path = await _save_multipart_file_stream(request, notebook_id)
    return store.add_source_from_path(notebook_id, str(file_path), indexed=False)


@router.post("/notebooks/{notebook_id}/sources/add-path", response_model=Source)
def add_path(notebook_id: str, payload: AddPathRequest) -> Source:
    return store.add_source_from_path(notebook_id, payload.path)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str) -> None:
    if source_id not in store.sources:
        raise HTTPException(status_code=404, detail="Source not found")
    store.sources.pop(source_id)


@router.get("/files")
def get_file(path: str):
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
