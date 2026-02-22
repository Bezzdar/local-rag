"""Роуты загрузки, удаления и индексации источников."""

# --- Imports ---
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from ..config import DOCS_DIR, UPLOAD_MAX_BYTES
from ..schemas import AddPathRequest, ReorderSourcesRequest, Source, UpdateSourceRequest
from ..store import store

router = APIRouter(prefix="/api", tags=["sources"])
HAS_MULTIPART = importlib.util.find_spec("multipart") is not None


# --- Основные блоки ---
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


def _ensure_notebook_exists(notebook_id: str) -> None:
    if notebook_id not in store.notebooks:
        raise HTTPException(status_code=404, detail="Notebook not found")


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
            output_path = store._next_available_path(notebook_id, filename)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_file = output_path.open("wb")
            header_done = True
            buffer = bytearray(body)

        if header_done and output_file:
            boundary_index = buffer.find(marker)
            if boundary_index != -1:
                output_file.write(buffer[:boundary_index])
                output_file.close()
                return output_path.name, output_path

            keep_tail = len(marker) + 4
            if len(buffer) > keep_tail:
                writable = len(buffer) - keep_tail
                output_file.write(buffer[:writable])
                buffer = buffer[writable:]

    _cleanup_partial_file()
    raise HTTPException(status_code=400, detail="Malformed multipart payload")


@router.get("/notebooks/{notebook_id}/sources", response_model=list[Source])
def list_sources(notebook_id: str) -> list[Source]:
    _ensure_notebook_exists(notebook_id)
    sources = [source for source in store.sources.values() if source.notebook_id == notebook_id]
    return sorted(sources, key=lambda s: (s.sort_order, s.added_at))


@router.post("/notebooks/{notebook_id}/sources/upload", response_model=Source)
async def upload_source(notebook_id: str, request: Request) -> Source:
    _ensure_notebook_exists(notebook_id)
    if HAS_MULTIPART and not _force_fallback():
        try:
            form = await request.form()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Malformed multipart payload") from exc

        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=400, detail="Multipart file field 'file' not found")
        content = await file.read()
        return await _persist_content(notebook_id, file.filename or "upload.bin", content)

    _, file_path = await _save_multipart_file_stream(request, notebook_id)
    return store.add_source_from_path(notebook_id, str(file_path), indexed=False)


@router.post("/notebooks/{notebook_id}/sources/add-path", response_model=Source)
def add_path(notebook_id: str, payload: AddPathRequest) -> Source:
    _ensure_notebook_exists(notebook_id)
    return store.add_source_from_path(notebook_id, payload.path)


@router.patch("/notebooks/{notebook_id}/sources/reorder", status_code=204, response_class=Response)
def reorder_sources(notebook_id: str, payload: ReorderSourcesRequest) -> Response:
    _ensure_notebook_exists(notebook_id)
    if not store.reorder_sources(notebook_id, payload.ordered_ids):
        raise HTTPException(status_code=400, detail="Invalid source IDs for reorder")
    return Response(status_code=204)


@router.patch("/sources/{source_id}", response_model=Source)
def update_source(source_id: str, payload: UpdateSourceRequest) -> Source:
    source = store.sources.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if payload.is_enabled is not None:
        source.is_enabled = payload.is_enabled
        store.sync_source_enabled(source_id, payload.is_enabled)
    if payload.individual_config is not None:
        source.individual_config = {
            "chunk_size": payload.individual_config.get("chunk_size"),
            "chunk_overlap": payload.individual_config.get("chunk_overlap"),
            "ocr_enabled": payload.individual_config.get("ocr_enabled"),
            "ocr_language": payload.individual_config.get("ocr_language"),
            "chunking_method": payload.individual_config.get("chunking_method"),
            "context_window": payload.individual_config.get("context_window"),
            "use_llm_summary": payload.individual_config.get("use_llm_summary"),
            "doc_type": payload.individual_config.get("doc_type"),
            "parent_chunk_size": payload.individual_config.get("parent_chunk_size"),
            "child_chunk_size": payload.individual_config.get("child_chunk_size"),
            "symbol_separator": payload.individual_config.get("symbol_separator"),
        }
    store.persist_source(source_id)
    return source


@router.delete("/sources/{source_id}", status_code=204, response_class=Response)
def delete_source(source_id: str) -> Response:
    if not store.delete_source_fully(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return Response(status_code=204)


@router.post("/sources/{source_id}/reparse", response_model=Source)
def reparse_source(source_id: str) -> Source:
    source = store.reparse_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("/sources/{source_id}/open", status_code=204, response_class=Response)
def open_source(source_id: str) -> Response:
    """Open the source file using the OS default application."""
    source = store.sources.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    file_path = Path(source.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    try:
        if sys.platform == "win32":
            os.startfile(str(file_path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(file_path)])
        else:
            subprocess.Popen(["xdg-open", str(file_path)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {exc}") from exc
    return Response(status_code=204)


@router.delete("/sources/{source_id}/erase", status_code=204, response_class=Response)
def erase_source(source_id: str) -> Response:
    if not store.erase_source_data(source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    return Response(status_code=204)


@router.delete("/notebooks/{notebook_id}/sources/files", status_code=204, response_class=Response)
def delete_all_files(notebook_id: str) -> Response:
    _ensure_notebook_exists(notebook_id)
    store.delete_all_source_files(notebook_id)
    return Response(status_code=204)


@router.get("/files")
def get_file(path: str):
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
