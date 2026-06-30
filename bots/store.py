"""Persistência de bots — JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from config.data_paths import BOTS_FILE, ensure_data_dir
from bots.types import BotConfig

_MAX_BOTS = 40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_all() -> list[dict]:
    if not BOTS_FILE.exists():
        return []
    rows: list[dict] = []
    try:
        for line in BOTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows


def _write_all(rows: list[dict]) -> None:
    ensure_data_dir()
    with BOTS_FILE.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_bots(*, active_only: bool = False) -> list[BotConfig]:
    bots = [BotConfig.from_dict(r) for r in _read_all()]
    if active_only:
        bots = [b for b in bots if b.active]
    return sorted(bots, key=lambda b: b.updated_at, reverse=True)


def get_bot(bot_id: str) -> BotConfig | None:
    for row in _read_all():
        if str(row.get("id")) == bot_id:
            return BotConfig.from_dict(row)
    return None


def save_bot(bot: BotConfig, *, is_new: bool = False) -> BotConfig:
    rows = _read_all()
    if is_new and len(rows) >= _MAX_BOTS:
        raise ValueError(f"Limite de {_MAX_BOTS} bots atingido")
    bot.updated_at = _now()
    if is_new:
        bot.created_at = _now()
    payload = bot.to_dict()
    out: list[dict] = []
    replaced = False
    for existing in rows:
        if str(existing.get("id")) == bot.id:
            if not replaced:
                out.append(payload)
                replaced = True
        else:
            out.append(existing)
    if not replaced:
        out.append(payload)
    _write_all(out)
    return bot


def delete_bot(bot_id: str) -> bool:
    rows = _read_all()
    out = [r for r in rows if str(r.get("id")) != bot_id]
    if len(out) == len(rows):
        return False
    _write_all(out)
    return True


def toggle_bot(bot_id: str, active: bool | None = None) -> BotConfig | None:
    bot = get_bot(bot_id)
    if not bot:
        return None
    bot.active = (not bot.active) if active is None else bool(active)
    return save_bot(bot)