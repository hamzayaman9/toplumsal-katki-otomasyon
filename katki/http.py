"""Nazik HTTP istemcisi: host başına sıralı istek + gecikme, toplamda sınırlı eşzamanlılık."""

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlsplit

import httpx

from .config import settings


class Fetcher:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent, "Accept-Language": "tr,en;q=0.5"},
            timeout=httpx.Timeout(30, connect=15),
            follow_redirects=True,
        )
        self._global = asyncio.Semaphore(settings.concurrency)
        self._host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request: dict[str, float] = {}
        self._host_delay: dict[str, float] = {}

    def set_host_delay(self, host: str, crawl_delay: float | None) -> None:
        delay = max(settings.min_host_delay, min(crawl_delay or 0, settings.max_crawl_delay))
        self._host_delay[host] = delay

    async def get(self, url: str, **kwargs) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        async with self._host_locks[host]:
            delay = self._host_delay.get(host, settings.min_host_delay)
            wait = self._last_request.get(host, 0) + delay - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                async with self._global:
                    return await self.client.get(url, **kwargs)
            finally:
                self._last_request[host] = time.monotonic()

    async def aclose(self) -> None:
        await self.client.aclose()
