# llm_generic.py — обёртка вокруг llama.cpp / Ollama HTTP API
from __future__ import annotations

import json
import logging
import subprocess
import time
from functools import lru_cache
from typing import Generator, Optional

import requests
from requests.adapters import HTTPAdapter, Retry

LOGGER = logging.getLogger(__name__)

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Singleton Session with retry logic (3×, 0.5‑1‑2s)."""
    global _session
    if _session is None:
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        sess = requests.Session()
        sess.mount("http://", HTTPAdapter(max_retries=retries))
        sess.mount("https://", HTTPAdapter(max_retries=retries))
        _session = sess
    return _session


def _normalize_base_url(server_url: str | None) -> str:
    raw = (server_url or "http://localhost:8000").strip()
    if raw.isdigit():
        raw = f"http://127.0.0.1:{raw}"
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    return raw.rstrip("/")


@lru_cache(maxsize=32)
def _detect_backend(base_url: str) -> str:
    """Detect backend by probing known health endpoints."""
    sess = _get_session()

    try:
        ping = sess.get(base_url + "/api/tags", timeout=2)
        if ping.status_code == 200:
            return "ollama"
    except Exception:
        pass

    return "llama_cpp"


def ask_llm(
    prompt: str,
    text: str | None = None,
    *,
    model: str = "",
    server_url: str | None = None,
    max_tokens: int = 128,
    stream: bool = False,
    timeout: int = 600,
) -> str | Generator[str, None, None]:
    """Синхронный запрос к llama.cpp / Ollama‑совместимому серверу."""
    base_url = _normalize_base_url(server_url)
    backend = _detect_backend(base_url)

    full_prompt = prompt.strip()
    if text:
        full_prompt += f"\n\n{text.strip()}\n"

    sess = _get_session()
    start = time.perf_counter()

    try:
        if backend == "ollama":
            url = base_url + "/api/generate"
            payload: dict[str, object] = {
                "model": model or "llama3.1:8b",
                "prompt": full_prompt,
                "stream": stream,
                "options": {"num_predict": max_tokens},
            }
            if stream:
                resp = sess.post(url, json=payload, timeout=timeout, stream=True)
                resp.raise_for_status()
                LOGGER.info("Ollama streaming started in %.2fs", time.perf_counter() - start)
                return _iter_ollama_stream(resp)

            resp = sess.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("response", "")
            LOGGER.info("Ollama answered in %.2fs (len=%d)", time.perf_counter() - start, len(answer))
            return answer

        url = base_url + "/completion"
        payload = {
            "prompt": full_prompt,
            "n_predict": max_tokens,
            "stream": stream,
        }
        if model:
            payload["model"] = model

        if stream:
            resp = sess.post(url, json=payload, timeout=timeout, stream=True)
            resp.raise_for_status()
            LOGGER.info("llama.cpp streaming started in %.2fs", time.perf_counter() - start)
            return _iter_llama_cpp_stream(resp)

        resp = sess.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("content") or data.get("response") or ""
        LOGGER.info("llama.cpp answered in %.2fs (len=%d)", time.perf_counter() - start, len(answer))
        return answer

    except requests.exceptions.ReadTimeout:
        return "❌ Timeout: Модель не ответила за %d сек." % timeout
    except requests.exceptions.ConnectionError:
        return f"❌ Ошибка подключения: не удалось связаться с LLM сервером на {base_url}"
    except Exception as exc:  # noqa: BLE001
        return f"❌ Ошибка при обращении к LLM: {exc}"


def _iter_llama_cpp_stream(resp: requests.Response) -> Generator[str, None, None]:
    """Yield chunks for llama.cpp SSE stream (data: ... lines)."""
    for raw in resp.iter_lines(decode_unicode=True):
        line = (raw or "").strip()
        if not line:
            continue
        if line.startswith("data: "):
            chunk = line.removeprefix("data: ")
            if chunk == "[DONE]":
                break
            yield chunk


def _iter_ollama_stream(resp: requests.Response) -> Generator[str, None, None]:
    """Yield chunks for Ollama NDJSON stream."""
    for raw in resp.iter_lines(decode_unicode=True):
        line = (raw or "").strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        token = item.get("response", "")
        if token:
            yield token
        if item.get("done"):
            break


def warmup_model(model_name: str) -> None:
    """Запускает Ollama модель в отдельном фоне, чтобы она загрузилась в память."""
    try:
        subprocess.Popen(
            ["ollama", "run", model_name, "-p", "Hello"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        LOGGER.info("Запущен предварительный прогрев модели: %s", model_name)
    except FileNotFoundError:
        LOGGER.error("Ollama CLI не найден. Установите ollama или проверьте PATH.")
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Ошибка прогрева модели %s: %s", model_name, exc)
