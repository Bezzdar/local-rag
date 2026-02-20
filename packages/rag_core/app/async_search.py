"""Асинхронные помощники retrieval-поиска."""

# --- Imports ---
import asyncio
from typing import Any, Sequence

import aiohttp

# --- Основные блоки ---
class RemoteLibraryAsync:
    def __init__(self, api_url: str, token: str | None = None, timeout_s: float = 10.0):
        self.api_url = api_url
        self.token = token
        self.timeout_s = timeout_s
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        session = await self._get_session()
        try:
            async with session.get(
                f"{self.api_url}/search",
                params={"q": query, "k": top_k},
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    return payload.get("results", [])
                return []
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return []


async def aggregated_search(
    query: str,
    local_lib: Any,
    remote_lib_async: RemoteLibraryAsync,
    top_k: int = 5,
) -> Sequence[dict[str, Any]]:
    loop = asyncio.get_running_loop()
    local_task = loop.run_in_executor(None, local_lib.search, query, top_k)
    remote_task = remote_lib_async.search(query, top_k)

    local_results, remote_results = await asyncio.gather(local_task, remote_task)
    return (local_results + remote_results)[:top_k]
