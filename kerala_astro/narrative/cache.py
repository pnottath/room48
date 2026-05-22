"""
Response cache — avoids re-generating the same reading twice.

Same chart + same options = same output. We hash the canonical chart digest
plus the narrative options (language, sections, model) and store results
on disk. Default TTL is 30 days; configurable.

This sits on top of Anthropic's prompt cache (which has a 5-minute TTL).
The response cache catches repeat-visit scenarios: a user views their
horoscope today, comes back next week — we serve the same prose without
hitting the LLM at all.
"""

from __future__ import annotations
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional


DEFAULT_CACHE_DIR = Path(os.getenv(
    "ROOM48_CACHE_DIR",
    str(Path.home() / ".room48" / "narrative_cache"),
))
DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 30   # 30 days


class NarrativeCache:
    """Tiny SHA256-keyed JSON cache on disk."""

    def __init__(self,
                 cache_dir: Optional[Path] = None,
                 ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    # ----- key building --------------------------------------------------
    @staticmethod
    def make_key(*parts: str) -> str:
        h = hashlib.sha256()
        for p in parts:
            h.update(p.encode("utf-8"))
            h.update(b"\x00")  # separator so parts can't run together
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        # Shard by first 2 hex chars to keep directories small at scale
        return self.cache_dir / key[:2] / f"{key}.json"

    # ----- public API ----------------------------------------------------
    def get(self, key: str) -> Optional[dict]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
        except Exception:
            return None
        if time.time() - data.get("created_at", 0) > self.ttl_seconds:
            try: p.unlink()
            except Exception: pass
            return None
        return data.get("payload")

    def put(self, key: str, payload: dict) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        record = {"created_at": time.time(), "payload": payload}
        p.write_text(json.dumps(record))

    def clear(self) -> int:
        """Remove all cache entries. Returns count removed."""
        count = 0
        for f in self.cache_dir.rglob("*.json"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        return count

    def stats(self) -> dict:
        files = list(self.cache_dir.rglob("*.json"))
        total_bytes = sum(f.stat().st_size for f in files if f.exists())
        return {
            "entries": len(files),
            "size_bytes": total_bytes,
            "cache_dir": str(self.cache_dir),
        }
