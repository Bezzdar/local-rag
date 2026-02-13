# llm_generic.py — обёртка вокруг llama.cpp / Ollama HTTP API
# ---------------------------------------------------------------------------
# Обновлён 2025‑06‑04 | ChatGPT‑o3 clean‑up
#   • logging вместо print
#   • кэшированный requests.Session с retry/back‑off
#   • безопасный subprocess (без shell=True) для «прогрева»
#   • простая реализация стриминга (iter_lines)
#   • type hints + pathlib | PEP 8
# ---------------------------------------------------------------------------
from __future__ import annotations

import logging
import time
import subprocess
from pathlib import Path
from typing import Generator, Optional

import requests
from requests.adapters import HTTPAdapter, Retry

LOGGER = logging.getLogger(__name__)

#──────────────────────────────────────────────────────────────────────────────
# HTTP util ‑‑ единый Session с экспоненциальным back‑off                   ◆
#──────────────────────────────────────────────────────────────────────────────
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


#──────────────────────────────────────────────────────────────────────────────
# Public API                                                                 ◆
#──────────────────────────────────────────────────────────────────────────────

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
    """Синхронный запрос к llama.cpp / Ollama‑совместимому серверу.

    Args:
        prompt: Системное/главное сообщение.
        text: Дополнительный контекст, будет добавлен после двух переводов строки.
        model: Явное имя модели (если сервер поддерживает переключение model‑параметром).
        server_url: Базовый URL без `/completion`. По‑умолчанию `http://localhost:8000`.
        max_tokens: n_predict
        stream: если *True* — читаем SSE‑поток и отдаём генератор строк.
        timeout: сокет‑таймаут для запроса (сек).
    """
    url = (server_url or "http://localhost:8000").rstrip("/") + "/completion"

    full_prompt = prompt.strip()
    if text:
        full_prompt += f"\n\n{text.strip()}\n"

    payload: dict[str, object] = {
        "prompt": full_prompt,
        "n_predict": max_tokens,
        "stream": stream,
    }
    if model:
        payload["model"] = model

    LOGGER.debug("POST %s", url)
    start = time.perf_counter()
    sess = _get_session()

    try:
        if stream:
            resp = sess.post(url, json=payload, timeout=timeout, stream=True)
            resp.raise_for_status()
            LOGGER.info("Streaming response started in %.2fs", time.perf_counter() - start)
            return _iter_llm_stream(resp)
        else:
            resp = sess.post(url, json=payload, timeout=timeout)
            elapsed = time.perf_counter() - start
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("content") or data.get("response") or ""
            LOGGER.info("LLM answered in %.2fs (len=%d)", elapsed, len(answer))
            return answer

    except requests.exceptions.ReadTimeout:
        return "❌ Timeout: Модель не ответила за %d сек." % timeout
    except requests.exceptions.ConnectionError:
        return f"❌ Ошибка подключения: не удалось связаться с Llama.cpp на {url}"
    except Exception as exc:  # noqa: BLE001
        return f"❌ Ошибка при обращении к Llama.cpp: {exc}"


#──────────────────────────────────────────────────────────────────────────────
# Helpers                                                                    ◆
#──────────────────────────────────────────────────────────────────────────────

def _iter_llm_stream(resp: requests.Response) -> Generator[str, None, None]:
    """Построчный итератор по SSE‑потоку из llama.cpp."""
    buffer: list[str] = []
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue  # ping
        if line.startswith("data: "):
            chunk = line.removeprefix("data: ")
            if chunk == "[DONE]":
                break
            buffer.append(chunk)
            yield chunk
    # на случай, если вы хотели агрегированный текст
    if buffer:
        LOGGER.debug("Streaming finished (%d chunks)", len(buffer))


#──────────────────────────────────────────────────────────────────────────────
# Utility: модель‑прогрев                                                    ◆
#──────────────────────────────────────────────────────────────────────────────

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
