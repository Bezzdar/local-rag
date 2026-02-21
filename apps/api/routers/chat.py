"""Роуты чата и потоковой выдачи ответов."""

# --- Imports ---
import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse, Citation, CitationLocation
from ..services.chat_modes import CHAT_MODES_BY_CODE, build_answer, normalize_chat_mode
from ..services.model_chat import build_chat_history, build_rag_context, generate_model_answer, stream_model_answer
from ..services.search_service import chunk_to_citation_fields, search
from ..store import store

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


# --- Основные блоки ---
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
async def chat(payload: ChatRequest) -> ChatResponse:
    mode = normalize_chat_mode(payload.mode)
    store.add_message(payload.notebook_id, "user", payload.message)

    # В model-режиме тоже выполняем retrieval для RAG-контекста
    do_retrieval = CHAT_MODES_BY_CODE[mode].uses_retrieval or mode == "model"
    chunks = (
        search(payload.notebook_id, payload.message, payload.selected_source_ids, top_n=5)
        if do_retrieval
        else []
    )
    citations = [_to_citation(payload.notebook_id, item) for item in chunks]

    if mode == "model":
        history = build_chat_history(store.messages.get(payload.notebook_id, []))
        rag_context = build_rag_context(chunks)
        response_text = await generate_model_answer(
            provider=payload.provider,
            base_url=payload.base_url,
            model=payload.model,
            history=history,
            rag_context=rag_context,
        )
    else:
        response_text = build_answer(mode, payload.message, citations)

    assistant_message = store.add_message(payload.notebook_id, "assistant", response_text)
    return ChatResponse(message=assistant_message, citations=citations)


@router.get("/chat/stream")
async def chat_stream(
    notebook_id: str,
    message: str,
    mode: str = "rag",
    agent_id: str = Query(default=""),
    selected_source_ids: str = Query(default=""),
    provider: str = Query(default="none"),
    model: str = Query(default=""),
    base_url: str = Query(default=""),
    max_history: int = Query(default=5, ge=1, le=50),
):
    normalized_mode = normalize_chat_mode(mode)
    selected_ids = [chunk for chunk in selected_source_ids.split(",") if chunk]
    logger.info(
        "CHAT STREAM opened mode=%s normalized_mode=%s agent_id=%s provider=%s model=%s notebook_id=%s max_history=%s",
        mode,
        normalized_mode,
        agent_id or "none",
        provider,
        model,
        notebook_id,
        max_history,
        extra={"event": "chat.stream.open", "details": f"agent_id={agent_id}; selected_source_ids={selected_ids}; message_len={len(message)}"},
    )

    async def stream():
        store.add_message(notebook_id, "user", message)
        stream_version = store.get_chat_version(notebook_id)
        sent_packets = 0
        sent_chars = 0
        # В model-режиме тоже выполняем retrieval для RAG-контекста
        do_retrieval = CHAT_MODES_BY_CODE[normalized_mode].uses_retrieval or normalized_mode == "model"
        chunks = (
            search(notebook_id, message, selected_ids, top_n=5)
            if do_retrieval
            else []
        )
        citations = [_to_citation(notebook_id, item) for item in chunks]

        if normalized_mode == "model":
            history = build_chat_history(store.messages.get(notebook_id, []), limit=max_history)
            rag_context = build_rag_context(chunks)
            assembled = []
            try:
                async for token in stream_model_answer(
                    provider=provider,
                    base_url=base_url,
                    model=model,
                    history=history,
                    rag_context=rag_context,
                ):
                    assembled.append(token)
                    sent_packets += 1
                    sent_chars += len(token)
                    yield to_sse("token", {"text": token})
            except RuntimeError as exc:
                logger.warning(
                    "LLM stream interrupted",
                    extra={"event": "chat.stream.error", "details": f"provider={provider}; model={model}; error={exc}"},
                )
                yield to_sse("error", {"detail": str(exc)})
                yield to_sse("done", {"message_id": ""})
                return

            yield to_sse("citations", [citation.model_dump(exclude_none=True) for citation in citations])

            if store.get_chat_version(notebook_id) != stream_version:
                yield to_sse("done", {"message_id": ""})
                return

            assistant = store.add_message(notebook_id, "assistant", "".join(assembled).strip())
            logger.info(
                "LLM stream completed",
                extra={
                    "event": "chat.stream.completed",
                    "details": f"mode=model; packets_sent={sent_packets}; chars_sent={sent_chars}; citations={len(citations)}",
                },
            )
            yield to_sse("done", {"message_id": assistant.id})
            return
        else:
            answer = build_answer(normalized_mode, message, citations, agent_id=agent_id)

        assembled = []
        for word in answer.split(" "):
            token = f"{word} "
            assembled.append(token)
            sent_packets += 1
            sent_chars += len(token)
            yield to_sse("token", {"text": token})
            await asyncio.sleep(0.04)

        yield to_sse("citations", [citation.model_dump(exclude_none=True) for citation in citations])

        if store.get_chat_version(notebook_id) != stream_version:
            yield to_sse("done", {"message_id": ""})
            return

        assistant = store.add_message(notebook_id, "assistant", "".join(assembled).strip())
        logger.info(
            "Template stream completed",
            extra={
                "event": "chat.stream.completed",
                "details": f"mode={normalized_mode}; packets_sent={sent_packets}; chars_sent={sent_chars}; citations={len(citations)}",
            },
        )
        yield to_sse("done", {"message_id": assistant.id})

    return StreamingResponse(stream(), media_type="text/event-stream")
