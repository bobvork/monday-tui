"""Disk-based JSON cache in ~/.cache/mui/."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "mui"

# TTL in seconds per query type
TTL_BOARDS = 300  # 5 minutes
TTL_BOARD_DETAIL = 120  # 2 minutes
TTL_GROUP_ITEMS = 60  # 1 minute
TTL_ITEM_DETAIL = 60  # 1 minute
TTL_USERS = 600  # 10 minutes


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _make_key(prefix: str, params: str = "") -> str:
    raw = f"{prefix}:{params}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get(prefix: str, params: str = "", ttl: int = 60) -> Any | None:
    key = _make_key(prefix, params)
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - entry.get("timestamp", 0) > ttl:
        path.unlink(missing_ok=True)
        return None
    return entry.get("data")


def set(prefix: str, params: str, data: Any, ttl: int = 60) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _make_key(prefix, params)
    entry = {"timestamp": time.time(), "ttl": ttl, "data": data}
    _cache_path(key).write_text(json.dumps(entry))


def invalidate(prefix: str, params: str = "") -> None:
    key = _make_key(prefix, params)
    _cache_path(key).unlink(missing_ok=True)


def invalidate_all() -> None:
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink(missing_ok=True)
