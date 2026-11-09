"""Process-local cache for generated images based on prompt and style."""
import hashlib
from collections import OrderedDict
from dataclasses import dataclass
import time
from threading import RLock

@dataclass
class _ImageEntry:
    expires_at: float
    image_url: str
    prompt_used: str

class ImageCache:
    def __init__(self, max_entries: int = 100, ttl_seconds: float = 3600.0):
        self._entries: OrderedDict[str, _ImageEntry] = OrderedDict()
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._lock = RLock()

    def _make_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def get(self, prompt: str) -> _ImageEntry | None:
        key = self._make_key(prompt)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.time():
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry

    def put(self, prompt: str, image_url: str, prompt_used: str) -> None:
        key = self._make_key(prompt)
        with self._lock:
            self._entries[key] = _ImageEntry(time.time() + self._ttl, image_url, prompt_used)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

_IMAGE_CACHE = ImageCache()