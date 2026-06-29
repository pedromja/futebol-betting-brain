"""
Cache em disco — evita repetir pedidos e respeita limites das APIs gratuitas.
"""

import hashlib
import json
import time
from pathlib import Path

_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "api_cache"


def _key(namespace: str, identifier: str) -> Path:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:24]
    safe_ns = "".join(c if c.isalnum() else "_" for c in namespace)[:40]
    return _CACHE_DIR / safe_ns / f"{digest}.json"


def get(namespace: str, identifier: str, ttl_seconds: int) -> dict | list | str | None:
    path = _key(namespace, identifier)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() - entry.get("ts", 0) > ttl_seconds:
            return None
        return entry.get("data")
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def set(namespace: str, identifier: str, data: dict | list | str) -> None:
    path = _key(namespace, identifier)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)