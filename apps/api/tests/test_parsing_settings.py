from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from apps.api.config import CHUNKS_DIR
from apps.api.main import app

client = TestClient(app)


def _first_notebook_id() -> str:
    response = client.get('/api/notebooks')
    response.raise_for_status()
    return response.json()[0]['id']


def _wait_source(source_id: str, timeout_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        notebooks = client.get('/api/notebooks').json()
        for notebook in notebooks:
            for source in client.get(f"/api/notebooks/{notebook['id']}/sources").json():
                if source['id'] == source_id and source['status'] in {'indexed', 'failed'}:
                    return source
        time.sleep(0.2)
    raise AssertionError('timeout')


def test_global_and_individual_settings_are_applied() -> None:
    notebook_id = _first_notebook_id()
    current = client.get(f'/api/notebooks/{notebook_id}/parsing-settings').json()
    current['chunk_size'] = 9
    current['chunk_overlap'] = 3
    updated = client.patch(f'/api/notebooks/{notebook_id}/parsing-settings', json=current)
    assert updated.status_code == 200

    upload = client.post(
        f'/api/notebooks/{notebook_id}/sources/upload',
        files={'file': ('settings.txt', b' '.join([b'x'] * 120), 'text/plain')},
    )
    assert upload.status_code == 200
    source_id = upload.json()['id']
    source = _wait_source(source_id)
    assert source['status'] == 'indexed'

    initial_json = CHUNKS_DIR / notebook_id / f"{source_id}.json"
    assert initial_json.exists()
    payload_json = json.loads(initial_json.read_text(encoding='utf-8'))
    assert payload_json['metadata']['individual_config']['chunk_size'] is None

    patch = client.patch(
        f'/api/sources/{source_id}',
        json={
            'individual_config': {
                'chunk_size': 5,
                'chunk_overlap': 1,
                'ocr_enabled': None,
                'ocr_language': None,
            },
        },
    )
    assert patch.status_code == 200

    reparse = client.post(f'/api/sources/{source_id}/reparse')
    assert reparse.status_code == 200
    source = _wait_source(source_id)
    assert source['status'] == 'indexed'

    payload_json = json.loads((CHUNKS_DIR / notebook_id / f"{source_id}.json").read_text(encoding='utf-8'))
    assert payload_json['metadata']['individual_config']['chunk_size'] == 5
