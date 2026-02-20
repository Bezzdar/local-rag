"""Тесты загрузки источников и SSE-стриминга."""

# --- Imports ---
import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import UPLOAD_MAX_BYTES
from apps.api.main import app
from apps.api.config import DOCS_DIR
from apps.api.services.index_service import get_notebook_blocks

client = TestClient(app)


# --- Основные блоки ---
def _first_notebook_id() -> str:
    response = client.get('/api/notebooks')
    response.raise_for_status()
    return response.json()[0]['id']


def _wait_until_notebook_idle(notebook_id: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        stats = client.get(f'/api/notebooks/{notebook_id}/index/status')
        stats.raise_for_status()
        payload = stats.json()
        if payload['indexing'] == 0:
            return
        time.sleep(0.2)
    raise AssertionError('Indexing timeout exceeded')


def _wait_source_status(source_id: str, status: str, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        notebooks = client.get('/api/notebooks').json()
        for notebook in notebooks:
            sources = client.get(f"/api/notebooks/{notebook['id']}/sources").json()
            for source in sources:
                if source['id'] == source_id and source['status'] == status:
                    return
        time.sleep(0.2)
    raise AssertionError(f'Status timeout for source={source_id}, expected={status}')


def test_upload_index_and_chat_citations_for_pdf_docx_xlsx() -> None:
    notebook_id = _first_notebook_id()
    fixtures = [
        ('sample.pdf', b'%PDF-1.4\nLegacy core indexed PDF block\n## Section PDF', 'application/pdf'),
        ('sample.docx', b'PK\x03\x04docx-content', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        ('sample.xlsx', b'PK\x03\x04xlsx-content', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    ]

    for filename, payload, content_type in fixtures:
        upload = client.post(
            f'/api/notebooks/{notebook_id}/sources/upload',
            files={'file': (filename, payload, content_type)},
        )
        assert upload.status_code == 200
        source = upload.json()

        download = client.get('/api/files', params={'path': source['file_path']})
        assert download.status_code == 200
        assert download.content == payload

    _wait_until_notebook_idle(notebook_id)

    chat = client.get(
        '/api/chat/stream',
        params={'notebook_id': notebook_id, 'message': 'Section and page', 'mode': 'rag'},
    )
    assert chat.status_code == 200
    body = chat.text

    token_idx = body.find('event: token')
    citations_idx = body.find('event: citations')
    done_idx = body.find('event: done')
    assert token_idx != -1
    assert citations_idx != -1
    assert done_idx != -1
    assert token_idx < citations_idx < done_idx

    citations_marker = 'event: citations\ndata: '
    start = body.find(citations_marker)
    assert start != -1
    start += len(citations_marker)
    end = body.find('\n\n', start)
    citations = json.loads(body[start:end])

    assert citations
    for item in citations:
        assert item['filename']
        location = item['location']
        assert location.get('page') is not None or location.get('sheet')


def test_upload_without_file_returns_400() -> None:
    notebook_id = _first_notebook_id()
    response = client.post(
        f'/api/notebooks/{notebook_id}/sources/upload',
        data='--x--\r\n',
        headers={'Content-Type': 'multipart/form-data; boundary=x'},
    )
    assert response.status_code == 400


def test_too_large_upload_in_fallback_returns_413_and_cleans_partial() -> None:
    notebook_id = _first_notebook_id()
    previous = os.environ.get('FORCE_FALLBACK_MULTIPART')
    os.environ['FORCE_FALLBACK_MULTIPART'] = '1'
    try:
        notebook_dir = DOCS_DIR / notebook_id
        notebook_dir.mkdir(parents=True, exist_ok=True)
        before = {p.name for p in notebook_dir.glob('*') if p.is_file()}

        boundary = 'BOUNDARY'
        head = (
            f'--{boundary}\r\n'
            'Content-Disposition: form-data; name="file"; filename="big.pdf"\r\n'
            'Content-Type: application/pdf\r\n\r\n'
        ).encode('utf-8')
        raw = head + (b'A' * (UPLOAD_MAX_BYTES + 1024))

        response = client.post(
            f'/api/notebooks/{notebook_id}/sources/upload',
            data=raw,
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
        )
        assert response.status_code == 413

        after = {p.name for p in notebook_dir.glob('*') if p.is_file()}
        assert after == before
    finally:
        if previous is None:
            os.environ.pop('FORCE_FALLBACK_MULTIPART', None)
        else:
            os.environ['FORCE_FALLBACK_MULTIPART'] = previous


def test_unsupported_format_marks_source_failed() -> None:
    notebook_id = _first_notebook_id()
    upload = client.post(
        f'/api/notebooks/{notebook_id}/sources/upload',
        files={'file': ('unsupported.bin', b'\x00\x01\x02', 'application/octet-stream')},
    )
    assert upload.status_code == 200
    source_id = upload.json()['id']

    _wait_source_status(source_id, 'failed')


def test_force_fallback_small_upload_works() -> None:
    notebook_id = _first_notebook_id()
    previous = os.environ.get('FORCE_FALLBACK_MULTIPART')
    os.environ['FORCE_FALLBACK_MULTIPART'] = '1'
    try:
        upload = client.post(
            f'/api/notebooks/{notebook_id}/sources/upload',
            files={'file': ('fallback.pdf', b'fallback content', 'application/pdf')},
        )
        assert upload.status_code == 200
        source = upload.json()
        _wait_source_status(source['id'], 'indexed')
    finally:
        if previous is None:
            os.environ.pop('FORCE_FALLBACK_MULTIPART', None)
        else:
            os.environ['FORCE_FALLBACK_MULTIPART'] = previous


def test_delete_source_removes_only_docs_file() -> None:
    notebook_id = _first_notebook_id()
    upload = client.post(
        f'/api/notebooks/{notebook_id}/sources/upload',
        files={'file': ('cleanup.txt', b'cleanup-content', 'text/plain')},
    )
    assert upload.status_code == 200
    source = upload.json()

    _wait_source_status(source['id'], 'indexed')
    assert any(item.get('source_id') == source['id'] for item in get_notebook_blocks(notebook_id))

    delete = client.delete(f"/api/sources/{source['id']}")
    assert delete.status_code == 204

    assert not Path(source['file_path']).exists()
    assert any(item.get('source_id') == source['id'] for item in get_notebook_blocks(notebook_id))


def test_erase_source_removes_parsing_and_index_blocks() -> None:
    notebook_id = _first_notebook_id()
    upload = client.post(
        f'/api/notebooks/{notebook_id}/sources/upload',
        files={'file': ('erase.txt', b'erase-content', 'text/plain')},
    )
    assert upload.status_code == 200
    source = upload.json()

    _wait_source_status(source['id'], 'indexed')
    erase = client.delete(f"/api/sources/{source['id']}/erase")
    assert erase.status_code == 204
    assert all(item.get('source_id') != source['id'] for item in get_notebook_blocks(notebook_id))


def test_sources_endpoints_for_unknown_notebook_return_404() -> None:
    missing = '00000000-0000-0000-0000-000000000099'
    listing = client.get(f'/api/notebooks/{missing}/sources')
    assert listing.status_code == 404

    upload = client.post(
        f'/api/notebooks/{missing}/sources/upload',
        files={'file': ('sample.txt', b'text', 'text/plain')},
    )
    assert upload.status_code == 404

    add_path = client.post(f'/api/notebooks/{missing}/sources/add-path', json={'path': '/tmp/file.txt'})
    assert add_path.status_code == 404


def test_clear_messages_endpoint_resets_chat_history() -> None:
    notebook_id = _first_notebook_id()
    before = client.get(f'/api/notebooks/{notebook_id}/messages')
    assert before.status_code == 200

    chat = client.get('/api/chat/stream', params={'notebook_id': notebook_id, 'message': 'hello', 'mode': 'model'})
    assert chat.status_code == 200

    populated = client.get(f'/api/notebooks/{notebook_id}/messages')
    assert populated.status_code == 200
    assert len(populated.json()) >= 2

    cleared = client.delete(f'/api/notebooks/{notebook_id}/messages')
    assert cleared.status_code == 204

    after = client.get(f'/api/notebooks/{notebook_id}/messages')
    assert after.status_code == 200
    assert after.json() == []



def test_clear_during_stream_does_not_restore_history(monkeypatch) -> None:
    notebook_id = _first_notebook_id()
    client.delete(f'/api/notebooks/{notebook_id}/messages')

    import apps.api.routers.chat as chat_router

    called = {'value': False}

    async def fake_sleep(_delay: float) -> None:
        if not called['value']:
            called['value'] = True
            client.delete(f'/api/notebooks/{notebook_id}/messages')

    monkeypatch.setattr(chat_router.asyncio, 'sleep', fake_sleep)

    response = client.get('/api/chat/stream', params={'notebook_id': notebook_id, 'message': 'slow', 'mode': 'rag'})
    assert response.status_code == 200

    messages = client.get(f'/api/notebooks/{notebook_id}/messages')
    assert messages.status_code == 200
    assert messages.json() == []


def test_model_mode_uses_llm_and_chat_history(monkeypatch) -> None:
    notebook_id = _first_notebook_id()

    client.delete(f'/api/notebooks/{notebook_id}/messages')
    client.get('/api/chat/stream', params={'notebook_id': notebook_id, 'message': 'Привет', 'mode': 'rag'})

    captured: dict[str, object] = {}

    async def fake_stream_model_answer(*, provider: str, base_url: str, model: str, history: list[dict[str, str]], timeout_s: float = 60.0):
        captured['provider'] = provider
        captured['base_url'] = base_url
        captured['model'] = model
        captured['history'] = history
        for token in ('Ответ ', 'модели ', 'с учетом ', 'истории'):
            yield token

    from apps.api.routers import chat as chat_router

    monkeypatch.setattr(chat_router, 'stream_model_answer', fake_stream_model_answer)

    response = client.get(
        '/api/chat/stream',
        params={
            'notebook_id': notebook_id,
            'message': 'И как дела?',
            'mode': 'model',
            'provider': 'ollama',
            'base_url': 'http://localhost:11434',
            'model': 'qwen:latest',
        },
    )

    assert response.status_code == 200
    assert 'event: token' in response.text
    assert 'Ответ ' in response.text
    assert 'истории' in response.text
    assert captured['provider'] == 'ollama'
    assert captured['base_url'] == 'http://localhost:11434'
    assert captured['model'] == 'qwen:latest'

    history = captured['history']
    assert isinstance(history, list)
    assert any(item['role'] == 'assistant' for item in history)
    assert history[-1] == {'role': 'user', 'content': 'И как дела?'}


def test_model_mode_via_post_chat_returns_llm_answer(monkeypatch) -> None:
    notebook_id = _first_notebook_id()

    async def fake_generate_model_answer(*, provider: str, base_url: str, model: str, history: list[dict[str, str]], timeout_s: float = 60.0) -> str:
        return f'LLM:{provider}:{model}:{len(history)}'

    from apps.api.routers import chat as chat_router

    monkeypatch.setattr(chat_router, 'generate_model_answer', fake_generate_model_answer)

    response = client.post(
        '/api/chat',
        json={
            'notebook_id': notebook_id,
            'message': 'Тест запроса',
            'selected_source_ids': [],
            'mode': 'model',
            'provider': 'ollama',
            'base_url': 'http://localhost:11434',
            'model': 'llama3.1:8b',
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['message']['content'].startswith('LLM:ollama:llama3.1:8b:')
    assert payload['citations'] == []
