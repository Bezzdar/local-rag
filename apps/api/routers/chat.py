import asyncio
import json
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse, Citation, CitationLocation
from ..services.chat_modes import CHAT_MODES_BY_CODE, build_answer, normalize_chat_mode
from ..services.search_service import chunk_to_citation_fields, search
from ..store import store

router = APIRouter(prefix="/api", tags=["chat"])


def to_sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _to_citation(notebook_id: str, chunk: dict) -> Citation:
    filename, page, section = chunk_to_citation_fields(chunk)
    return Citation(
        id=str(uuid4()),
        notebook_id=notebook_id,
        source_id=chunk.get("source_id", "unknown"),
        filename=filename,
        location=CitationLocation(page=page, sheet=section, paragraph=None),
        snippet=chunk.get("text", "")[:280],
        score=0.9,
    )


@router.get("/notebooks/{notebook_id}/messages")
def list_messages(notebook_id: str):
    return store.messages.get(notebook_id, [])


@router.delete("/notebooks/{notebook_id}/messages", status_code=204)
def clear_messages(notebook_id: str):
    store.clear_messages(notebook_id)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    mode = normalize_chat_mode(payload.mode)
    store.add_message(payload.notebook_id, "user", payload.message)
    chunks = (
        search(payload.notebook_id, payload.message, payload.selected_source_ids, top_n=5)
        if CHAT_MODES_BY_CODE[mode].uses_retrieval
        else []
    )
    citations = [_to_citation(payload.notebook_id, item) for item in chunks]
    response_text = build_answer(mode, payload.message, citations)
    assistant_message = store.add_message(payload.notebook_id, "assistant", response_text)
    return ChatResponse(message=assistant_message, citations=citations)


@router.get("/chat/stream")
async def chat_stream(
    notebook_id: str,
    message: str,
    mode: str = "rag",
    selected_source_ids: str = Query(default=""),
):
    normalized_mode = normalize_chat_mode(mode)
    selected_ids = [chunk for chunk in selected_source_ids.split(",") if chunk]

    async def stream():
        store.add_message(notebook_id, "user", message)
        chunks = (
            search(notebook_id, message, selected_ids, top_n=5)
            if CHAT_MODES_BY_CODE[normalized_mode].uses_retrieval
            else []
        )
        citations = [_to_citation(notebook_id, item) for item in chunks]
        answer = build_answer(normalized_mode, message, citations)

        assembled = []
        for word in answer.split(" "):
            token = f"{word} "
            assembled.append(token)
            yield to_sse("token", {"text": token})
            await asyncio.sleep(0.04)

        assistant = store.add_message(notebook_id, "assistant", "".join(assembled).strip())
        yield to_sse("citations", [citation.model_dump() for citation in citations])
        yield to_sse("done", {"message_id": assistant.id})

    return StreamingResponse(stream(), media_type="text/event-stream")
