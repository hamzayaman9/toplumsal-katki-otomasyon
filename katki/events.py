"""Canlı izleme için basit olay yayını (tarama/sınıflandırma -> panel).

Tarama ve sınıflandırma fonksiyonları isteğe bağlı bir `on_event(tip, **veri)` alır;
web sunucusu bu olayları SSE ile tarayıcıya iletir.
"""

import asyncio
import json
from typing import Any, Callable

EventFn = Callable[..., None]


def noop(_type: str, **_data: Any) -> None:
    pass


class Bus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self.history: list[dict] = []  # sonradan bağlanan izleyici son durumu görebilsin

    def emit(self, type_: str, **data: Any) -> None:
        event = {"tip": type_, **data}
        if type_ in ("tarama_basladi", "tekrar_basladi"):
            self.history.clear()
        self.history.append(event)
        del self.history[:-2000]
        for q in list(self._subscribers):
            q.put_nowait(event)

    async def stream(self):
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        try:
            for event in list(self.history):
                yield _sse(event)
            yield _sse({"tip": "gecmis_bitti"})  # bundan sonrası canlı: arayüz animasyonu açar
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield _sse(event)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # bağlantıyı canlı tut
        finally:
            self._subscribers.discard(q)


class Forwarder:
    """Komut satırından çalışan tarama/sınıflandırma olaylarını açık paneldeki canlı sayfaya iletir.

    Panel kapalıysa olaylar sessizce düşer; panel sonradan açılırsa en son `tarama_basladi`
    olayı yeniden gönderilir ki sayfa kaynak ızgarasını kurabilsin.
    """

    def __init__(self, url: str = "http://127.0.0.1:8000/api/olay") -> None:
        import queue
        import threading

        self.url = url
        self.q: queue.Queue = queue.Queue()
        self.start_event: dict | None = None
        self.connected = False
        threading.Thread(target=self._loop, daemon=True).start()

    def __call__(self, type_: str, **data: Any) -> None:
        event = {"tip": type_, **data}
        if type_ == "tarama_basladi":
            self.start_event = event
        self.q.put(event)

    def _loop(self) -> None:
        import httpx

        with httpx.Client(timeout=3) as client:
            while True:
                batch = [self.q.get()]
                while not self.q.empty() and len(batch) < 200:
                    batch.append(self.q.get())
                if not self.connected and self.start_event and batch[0] is not self.start_event:
                    batch.insert(0, self.start_event)
                try:
                    client.post(self.url, content=json.dumps(batch, ensure_ascii=False, default=str),
                                headers={"Content-Type": "application/json"}).raise_for_status()
                    self.connected = True
                except Exception:
                    self.connected = False

    def flush(self, timeout: float = 5) -> None:
        import time

        end = time.monotonic() + timeout
        while not self.q.empty() and time.monotonic() < end:
            time.sleep(0.1)
        time.sleep(0.3)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
