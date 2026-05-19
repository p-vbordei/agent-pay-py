"""LRU-ish cache to reject replayed preimages within their invoice's TTL."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable


def _default_now_ms() -> int:
    return int(time.time() * 1000)


class ReplayCache:
    def __init__(
        self,
        *,
        max_entries: int = 100_000,
        now: Callable[[], int] | None = None,
    ) -> None:
        self._max_entries = max_entries
        self._now = now or _default_now_ms
        self._map: OrderedDict[str, int] = OrderedDict()

    def mark_used(self, key: str, expires_at_ms: int) -> None:
        if len(self._map) >= self._max_entries:
            self._map.popitem(last=False)
        self._map[key] = expires_at_ms

    def is_used(self, key: str) -> bool:
        exp = self._map.get(key)
        if exp is None:
            return False
        if exp <= self._now():
            del self._map[key]
            return False
        return True
