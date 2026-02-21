"""Роуты управления LLM-конфигурацией и диагностикой."""

# --- Imports ---
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

router = APIRouter(prefix='/api', tags=['llm'])

CHAT_BLOCKLIST_KEYWORDS = (
    'embed',
    'embedding',
    'rerank',
    'reranker',
    'bge-m3',
    'bge-large',
    'e5',
    'gte',
)

EMBEDDING_HINT_KEYWORDS = (
    'embed',
    'embedding',
    'bge',
    'e5',
    'gte',
    'nomic-embed',
    'mxbai-embed',
)


# --- Основные блоки ---
def _is_chat_model(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    if not normalized:
        return False
    return not any(keyword in normalized for keyword in CHAT_BLOCKLIST_KEYWORDS)


def _is_embedding_model(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    if not normalized:
        return False
    if 'rerank' in normalized:
        return False
    return any(keyword in normalized for keyword in EMBEDDING_HINT_KEYWORDS)


@router.get('/llm/models', response_model=list[str])
async def list_llm_models(
    provider: str = Query(default='none'),
    base_url: str = Query(default=''),
    purpose: str = Query(default='all'),
) -> list[str]:
    selected_provider = provider.strip().lower()
    endpoint = base_url.strip().rstrip('/')

    if selected_provider == 'none' or not endpoint:
        return []

    if selected_provider != 'ollama':
        raise HTTPException(status_code=400, detail=f'Unsupported provider: {provider}')

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f'{endpoint}/api/tags')
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to fetch Ollama models: {exc}') from exc

    payload = response.json()
    models = payload.get('models', []) if isinstance(payload, dict) else []
    model_names = [item.get('name', '') for item in models if isinstance(item, dict) and item.get('name')]

    normalized_purpose = purpose.strip().lower()
    if normalized_purpose == 'chat':
        return [name for name in model_names if _is_chat_model(name)]
    if normalized_purpose == 'embedding':
        return [name for name in model_names if _is_embedding_model(name)]
    return model_names


class EmbeddingConfigPayload(BaseModel):
    provider: str = "ollama"
    base_url: str = ""
    model: str = ""


@router.post('/settings/embedding')
async def update_embedding_settings(payload: EmbeddingConfigPayload) -> dict:
    """Применить выбранную пользователем конфигурацию эмбеддинг-модели."""
    from ..store import store
    store.reconfigure_embedding(
        provider=payload.provider.strip().lower() or "ollama",
        base_url=payload.base_url.strip().rstrip("/"),
        model_name=payload.model.strip(),
    )
    return {"ok": True}
