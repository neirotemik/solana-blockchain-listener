from __future__ import annotations

from collections import OrderedDict
from threading import Lock


class LRUDeduper:
    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._seen

    def add(self, key: str) -> bool:
        with self._lock:
            if key in self._seen:
                self._seen.move_to_end(key)
                return False
            self._seen[key] = None
            if len(self._seen) > self._capacity:
                self._seen.popitem(last=False)
            return True

    def __len__(self) -> int:
        with self._lock:
            return len(self._seen)

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()