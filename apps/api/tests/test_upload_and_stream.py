import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import UPLOAD_MAX_BYTES
from apps.api.main import app
from apps.api.config import DOCS_DIR

client = TestClient(app)


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
        params={'notebook_id': notebook_id, 'message': 'Section and page', 'mode': 'qa'},
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
