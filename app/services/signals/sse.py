from __future__ import annotations

import json
from queue import Empty, Queue
from threading import Lock
from typing import Any


def encode_sse(event: str, data: dict[str, Any], *, event_id: int | None = None) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


class SignalBroadcaster:
    def __init__(self) -> None:
        self._clients: set[Queue[dict[str, Any]]] = set()
        self._lock = Lock()

    def subscribe(self) -> Queue[dict[str, Any]]:
        queue: Queue[dict[str, Any]] = Queue(maxsize=100)
        with self._lock:
            self._clients.add(queue)
        return queue

    def unsubscribe(self, queue: Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._clients.discard(queue)

    def publish(self, payload: dict[str, Any]) -> None:
        with self._lock:
            clients = list(self._clients)
        for queue in clients:
            try:
                queue.put_nowait(payload)
            except Exception:
                pass

    @staticmethod
    def poll(queue: Queue[dict[str, Any]]) -> dict[str, Any] | None:
        try:
            return queue.get_nowait()
        except Empty:
            return None


broadcaster = SignalBroadcaster()
