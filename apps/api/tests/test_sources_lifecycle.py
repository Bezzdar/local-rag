"""Тесты жизненного цикла источников."""

# --- Imports ---
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.config import CHUNKS_DIR

client = TestClient(app)


# --- Основные блоки ---
def _first_notebook_id() -> str:
    response = client.get('/api/notebooks')
    response.raise_for_status()
    return response.json()[0]['id']


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


def test_source_lifecycle_lamps() -> None:
    notebook_id = _first_notebook_id()
    upload = client.post(
        f'/api/notebooks/{notebook_id}/sources/upload',
        files={'file': ('lifecycle.txt', b'hello lifecycle', 'text/plain')},
    )
    assert upload.status_code == 200
    source = upload.json()
    _wait_source_status(source['id'], 'indexed')

    listed = client.get(f'/api/notebooks/{notebook_id}/sources').json()
    source_state = next(item for item in listed if item['id'] == source['id'])
    assert source_state['has_docs'] is True
    assert source_state['has_parsing'] is True
    assert (CHUNKS_DIR / notebook_id / f"{source['id']}.json").exists()

    delete = client.delete(f"/api/sources/{source['id']}")
    assert delete.status_code == 204
    listed = client.get(f'/api/notebooks/{notebook_id}/sources').json()
    source_state = next(item for item in listed if item['id'] == source['id'])
    assert source_state['has_docs'] is False
    assert source_state['has_parsing'] is True
    assert (CHUNKS_DIR / notebook_id / f"{source['id']}.json").exists()

    erase = client.delete(f"/api/sources/{source['id']}/erase")
    assert erase.status_code == 204
    listed = client.get(f'/api/notebooks/{notebook_id}/sources').json()
    source_state = next(item for item in listed if item['id'] == source['id'])
    assert source_state['has_parsing'] is False
    assert not (CHUNKS_DIR / notebook_id / f"{source['id']}.json").exists()


def test_parsing_settings_endpoints() -> None:
    notebook_id = _first_notebook_id()
    settings = client.get(f'/api/notebooks/{notebook_id}/parsing-settings')
    assert settings.status_code == 200
    payload = settings.json()
    payload['chunk_size'] = 333

    updated = client.patch(f'/api/notebooks/{notebook_id}/parsing-settings', json=payload)
    assert updated.status_code == 200
    assert updated.json()['chunk_size'] == 333
