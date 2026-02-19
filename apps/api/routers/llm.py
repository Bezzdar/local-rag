from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix='/api', tags=['llm'])


@router.get('/llm/models', response_model=list[str])
async def list_llm_models(
    provider: str = Query(default='none'),
    base_url: str = Query(default=''),
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
    return [item.get('name', '') for item in models if isinstance(item, dict) and item.get('name')]
