import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest, ChatResponse
from ..store import store

router = APIRouter(prefix="/api")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/notebooks/{notebook_id}/messages")
def list_messages(notebook_id: str):
    return store.messages.get(notebook_id, [])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    store.add_message(payload.notebook_id, "user", payload.message)
    answer = store.build_mock_answer(payload.message, payload.mode)
    msg = store.add_message(payload.notebook_id, "assistant", answer)
    citations = store.pick_citations(payload.notebook_id, payload.selected_source_ids)
    return ChatResponse(message=msg, citations=citations)


@router.get("/chat/stream")
async def chat_stream(
    notebook_id: str,
    message: str,
    mode: str = "qa",
    selected_source_ids: str = Query(default=""),
):
    ids = [x for x in selected_source_ids.split(",") if x]

    async def gen():
        store.add_message(notebook_id, "user", message)
        answer = store.build_mock_answer(message, mode)
        chunks = answer.split(" ")
        composed = ""
        for c in chunks:
            token = c + " "
            composed += token
            yield _sse("token", {"text": token})
            await asyncio.sleep(0.07)
        assistant = store.add_message(notebook_id, "assistant", composed.strip())
        citations = [c.model_dump() for c in store.pick_citations(notebook_id, ids)]
        yield _sse("citations", citations)
        yield _sse("done", {"message_id": assistant.id})

    return StreamingResponse(gen(), media_type="text/event-stream")
