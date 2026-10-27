"""Bounded process-local TTL cache; never stores failed or unvalidated output."""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
from threading import RLock
import time
from typing import Callable

from app.schemas.ai_analysis import AIAnalysis


def request_hash(selected_text: str, context: str) -> str:
    pair = (selected_text.lower(), context[:100])
    return hashlib.sha256(json.dumps(pair, ensure_ascii=False).encode()).hexdigest()


def context_guard(context: str, book_title: str | None) -> str:
    return hashlib.sha256(json.dumps((context, book_title), ensure_ascii=False).encode()).hexdigest()


@dataclass
class _Entry:
    guard: str
    expires_at: float
    result: AIAnalysis


class AnalysisCache:
    def __init__(self, max_entries: int = 256, clock: Callable[[], float] = time.monotonic):
        self._entries: OrderedDict[tuple[str, str], _Entry] = OrderedDict()
        self._max_entries = max_entries
        self._clock = clock
        self._lock = RLock()

    def get(self, namespace: str, key: str, guard: str) -> AIAnalysis | None:
        with self._lock:
            entry = self._entries.get((namespace, key))
            if entry is None:
                return None
            if entry.expires_at <= self._clock():
                del self._entries[(namespace, key)]
                return None
            if entry.guard != guard:
                return None
            self._entries.move_to_end((namespace, key))
            return entry.result.model_copy(deep=True)

    def put(self, namespace: str, key: str, guard: str, result: AIAnalysis, ttl: float) -> None:
        if ttl <= 0:
            return
        with self._lock:
            now = self._clock()
            for old_key, entry in list(self._entries.items()):
                if entry.expires_at <= now:
                    del self._entries[old_key]
            self._entries[(namespace, key)] = _Entry(guard, now + ttl, result.model_copy(deep=True))
            self._entries.move_to_end((namespace, key))
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
