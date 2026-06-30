"""Armazenamento de subscrições Web Push (groundwork para alertas no servidor)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from config.data_paths import PUSH_SUBSCRIPTIONS, ensure_data_dir


def save_subscription(payload: dict) -> bool:
    endpoint = str(payload.get("endpoint") or "").strip()
    if not endpoint:
        return False

    ensure_data_dir()
    row = {
        "endpoint": endpoint,
        "keys": payload.get("keys") or {},
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    existing = {s["endpoint"] for s in load_subscriptions(limit=500)}
    if endpoint in existing:
        return True

    with PUSH_SUBSCRIPTIONS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True


def load_subscriptions(*, limit: int = 200) -> list[dict]:
    if not PUSH_SUBSCRIPTIONS.exists():
        return []
    rows: list[dict] = []
    try:
        lines = PUSH_SUBSCRIPTIONS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows