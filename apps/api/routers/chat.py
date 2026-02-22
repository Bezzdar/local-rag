"""Роуты чата и потоковой выдачи ответов."""

# --- Imports ---
import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse, Citation, CitationLocation
from ..services.chat_modes import (
    CHAT_MODES_BY_CODE,
    RAG_NO_SOURCES_MESSAGE,
    SCORE_THRESHOLDS,
    build_answer,
    normalize_chat_mode,
)
from ..services.model_chat import build_chat_history, build_rag_context, generate_model_answer, stream_model_answer
from ..services.search_service import chunk_to_citation_fields, filter_chunks_by_threshold, normalize_chunk_scores, search
from ..store import store

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


# --- Основные блоки ---
def to_sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _to_citation(notebook_id: str, chunk: dict, source_order_map: dict[str, int]) -> Citation:
    filename, page, section = chunk_to_citation_fields(chunk)
    source_id = chunk.get("source_id", "unknown")
    doc_order = source_order_map.get(source_id, 0)
    # Используем нормализованный score из чанка (уже в диапазоне 0–1)
    score = min(1.0, max(0.0, float(chunk.get("score", 0.0))))
    return Citation(
        id=str(uuid4()),
        notebook_id=notebook_id,
        source_id=source_id,
        filename=filename,
        location=CitationLocation(page=page, sheet=section, paragraph=None),
        snippet=chunk.get("text", "")[:280],
        score=score,
        doc_order=doc_order,
    )


def _retrieve_and_filter(
    notebook_id: str,
    message: str,
    selected_ids: list[str],
    mode: str,
) -> tuple[list[dict], list[dict]]:
    """Выполняет поиск, нормализует оценки и фильтрует по порогу режима.

    Returns:
        (all_chunks_normalized, relevant_chunks) — все нормализованные чанки
        и только те, что прошли пороговый фильтр.
    """
    raw_chunks = search(notebook_id, message, selected_ids, top_n=5)
    normalized = normalize_chunk_scores(raw_chunks)
    threshold = SCORE_THRESHOLDS.get(mode, 0.0)
    relevant = filter_chunks_by_threshold(normalized, threshold)
    return normalized, relevant


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
    source_order_map = store.get_source_order_map(payload.notebook_id)

    if mode == "agent":
        response_text = build_answer(mode, payload.message, [], agent_id="")
        citations: list[Citation] = []

    else:  # "rag" или "model"
        _, relevant_chunks = _retrieve_and_filter(
            payload.notebook_id, payload.message, payload.selected_source_ids, mode
        )
        sources_found = bool(relevant_chunks)
        citations = [_to_citation(payload.notebook_id, c, source_order_map) for c in relevant_chunks]

        if mode == "rag" and not sources_found:
            # RAG-режим без источников: LLM не вызывается
            response_text = RAG_NO_SOURCES_MESSAGE
        else:
            history = build_chat_history(store.messages.get(payload.notebook_id, []))
            rag_context = build_rag_context(relevant_chunks, source_order_map) if sources_found else ""
            response_text = await generate_model_answer(
                provider=payload.provider,
                base_url=payload.base_url,
                model=payload.model,
                history=history,
                rag_context=rag_context,
                chat_mode=mode,
                sources_found=sources_found,
            )

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
        source_order_map = store.get_source_order_map(notebook_id)

        # --- Agent: заглушка без retrieval ---
        if normalized_mode == "agent":
            answer = build_answer(normalized_mode, message, [], agent_id=agent_id)
            citations: list[Citation] = []
            for word in answer.split(" "):
                token = f"{word} "
                sent_packets += 1
                sent_chars += len(token)
                yield to_sse("token", {"text": token})
                await asyncio.sleep(0.04)
            yield to_sse("citations", [])
            if store.get_chat_version(notebook_id) != stream_version:
                yield to_sse("done", {"message_id": ""})
                return
            assistant = store.add_message(notebook_id, "assistant", answer)
            yield to_sse("done", {"message_id": assistant.id})
            return

        # --- RAG / Model: retrieval + пороговая фильтрация ---
        _, relevant_chunks = _retrieve_and_filter(notebook_id, message, selected_ids, normalized_mode)
        sources_found = bool(relevant_chunks)
        citations = [_to_citation(notebook_id, c, source_order_map) for c in relevant_chunks]

        # RAG без источников: возвращаем сообщение без вызова LLM
        if normalized_mode == "rag" and not sources_found:
            answer = RAG_NO_SOURCES_MESSAGE
            for word in answer.split(" "):
                token = f"{word} "
                sent_packets += 1
                sent_chars += len(token)
                yield to_sse("token", {"text": token})
                await asyncio.sleep(0.04)
            yield to_sse("citations", [])
            if store.get_chat_version(notebook_id) != stream_version:
                yield to_sse("done", {"message_id": ""})
                return
            assistant = store.add_message(notebook_id, "assistant", answer)
            logger.info(
                "RAG stream: no relevant sources found",
                extra={"event": "chat.stream.completed", "details": f"mode=rag; sources_found=False"},
            )
            yield to_sse("done", {"message_id": assistant.id})
            return

        # RAG с источниками или Model (с источниками или без): вызываем LLM
        history = build_chat_history(store.messages.get(notebook_id, []), limit=max_history)
        rag_context = build_rag_context(relevant_chunks, source_order_map) if sources_found else ""

        assembled: list[str] = []
        try:
            async for token in stream_model_answer(
                provider=provider,
                base_url=base_url,
                model=model,
                history=history,
                rag_context=rag_context,
                chat_mode=normalized_mode,
                sources_found=sources_found,
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
                "details": (
                    f"mode={normalized_mode}; sources_found={sources_found}; "
                    f"packets_sent={sent_packets}; chars_sent={sent_chars}; citations={len(citations)}"
                ),
            },
        )
        yield to_sse("done", {"message_id": assistant.id})

    return StreamingResponse(stream(), media_type="text/event-stream")
