import asyncio
import aiohttp

class RemoteLibraryAsync:
    def __init__(self, api_url, token=None):
        self.api_url = api_url
        self.token = token

    async def search(self, query, top_k=5):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/search", params={"q": query, "k": top_k}, headers=headers) as resp:
                if resp.status == 200:
                    return (await resp.json())["results"]
                else:
                    return []

async def aggregated_search(query, local_lib, remote_lib_async, top_k=5):
    loop = asyncio.get_event_loop()
    local_results = await loop.run_in_executor(None, local_lib.search, query, top_k)
    remote_results = await remote_lib_async.search(query, top_k)
    return (local_results + remote_results)[:top_k]
