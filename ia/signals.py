"""Persistência de sinais IA live."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from config.data_paths import IA_LIVE_SIGNALS, ensure_data_dir
from history.tips_history import _read_all_rows


def append_ia_signals(rows: list[dict]) -> int:
    if not rows:
        return 0
    ensure_data_dir()
    IA_LIVE_SIGNALS.parent.mkdir(parents=True, exist_ok=True)
    with IA_LIVE_SIGNALS.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def recent_signals_for_game(
    espn_event_id: str,
    *,
    limit: int = 40,
) -> list[dict]:
    eid = str(espn_event_id or "").strip()
    if not eid:
        return []
    rows = [r for r in _read_all_rows(IA_LIVE_SIGNALS) if str(r.get("espn_event_id") or "") == eid]
    rows.reverse()
    return rows[:limit]


def build_signal_record(tip: dict, *, fixture: dict, commentary_meta: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "id": str(uuid.uuid4()),
        "logged_at": now,
        "espn_event_id": fixture.get("espn_event_id"),
        "espn_league_code": fixture.get("espn_league_code"),
        "home": fixture.get("home"),
        "away": fixture.get("away"),
        "league": fixture.get("league"),
        "minute": tip.get("minute"),
        "phase_window": tip.get("phase_window"),
        "market": tip.get("market"),
        "odd": tip.get("book_odd") or tip.get("odd"),
        "book_odd": tip.get("book_odd") or tip.get("odd"),
        "odds_source": tip.get("odds_source"),
        "model_prob": tip.get("model_prob"),
        "implied_prob": tip.get("implied_prob"),
        "ev_pct": tip.get("ev_pct"),
        "confidence_pct": tip.get("confidence_pct"),
        "stake_raw": tip.get("stake_raw"),
        "bankroll_pct": tip.get("bankroll_pct"),
        "prematch_alignment": tip.get("prematch_alignment"),
        "reasoning_pt": tip.get("reasoning_pt"),
        "quote_en": tip.get("quote_en"),
        "timing_note": tip.get("timing_note"),
        "outcome": "pending",
        "commentary_minute": commentary_meta.get("minute"),
        "llm_status": commentary_meta.get("llm_status"),
    }