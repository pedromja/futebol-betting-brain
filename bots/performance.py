"""Performance e histórico por bot — ROI, hit rate, PnL."""

from __future__ import annotations

from pathlib import Path

from config.data_paths import BOT_SIGNALS_LOG
from history.manual_outcome import manual_correction_to_public
from history.tips_history import (
    TipsPerformance,
    _read_all_rows,
    _review_to_public,
    compute_performance,
    performance_to_dict,
)


def signal_to_public(row: dict) -> dict:
    outcome = str(row.get("outcome") or "pending").lower()
    stake = row.get("stake_amount")
    return {
        "id": row.get("signature") or f"{row.get('bot_id')}|{row.get('logged_at')}",
        "bot_id": row.get("bot_id"),
        "bot_name": row.get("bot_name"),
        "logged_at": row.get("logged_at") or row.get("scanned_at"),
        "mode": row.get("mode") or "prematch",
        "home": row.get("home"),
        "away": row.get("away"),
        "league": row.get("league"),
        "market": row.get("market"),
        "odd": row.get("odd"),
        "ev_pct": row.get("ev_pct"),
        "score": row.get("score"),
        "stake_level": row.get("stake_level"),
        "stake_label": row.get("stake_label"),
        "stake_amount": stake,
        "outcome": outcome,
        "final_score": row.get("final_score"),
        "score_at_tip": row.get("score_at_tip"),
        "minute": row.get("minute"),
        "pnl": row.get("pnl"),
        "resolved_at": row.get("resolved_at"),
        "kickoff": row.get("kickoff"),
        "review": _review_to_public(row),
        "manual_correction": manual_correction_to_public(row),
    }


def load_bot_signals(
    log_path: Path | None = None,
    *,
    bot_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    rows = _read_all_rows(log_path or BOT_SIGNALS_LOG)
    if bot_id:
        rows = [r for r in rows if str(r.get("bot_id")) == bot_id]
    rows.reverse()
    return rows[:limit]


def compute_bot_performance(
    rows: list[dict],
    *,
    bot_id: str | None = None,
    mode: str | None = None,
) -> TipsPerformance:
    filtered = rows
    if bot_id:
        filtered = [r for r in filtered if str(r.get("bot_id")) == bot_id]
    return compute_performance(filtered, mode=mode)


def build_all_bots_summary(log_path: Path | None = None) -> dict:
    rows = _read_all_rows(log_path or BOT_SIGNALS_LOG)
    by_bot: dict[str, list[dict]] = {}
    for row in rows:
        bid = str(row.get("bot_id") or "")
        if not bid:
            continue
        by_bot.setdefault(bid, []).append(row)

    summary: dict[str, dict] = {}
    for bot_id, bot_rows in by_bot.items():
        perf = compute_performance(bot_rows)
        summary[bot_id] = {
            **performance_to_dict(perf),
            "bot_name": bot_rows[-1].get("bot_name") or bot_id,
            "last_signal_at": bot_rows[-1].get("logged_at"),
        }
    return summary


def build_bot_history_payload(
    bot_id: str,
    *,
    log_path: Path | None = None,
    limit: int = 40,
) -> dict:
    path = log_path or BOT_SIGNALS_LOG
    all_rows = _read_all_rows(path)
    bot_rows = [r for r in all_rows if str(r.get("bot_id")) == bot_id]
    perf = compute_performance(bot_rows)
    signals = load_bot_signals(path, bot_id=bot_id, limit=limit)
    bot_name = signals[0].get("bot_name") if signals else bot_id
    if bot_rows:
        bot_name = bot_rows[-1].get("bot_name") or bot_name
    return {
        "bot_id": bot_id,
        "bot_name": bot_name,
        "performance": performance_to_dict(perf),
        "performance_by_mode": {
            "prematch": performance_to_dict(compute_performance(bot_rows, mode="prematch")),
            "live": performance_to_dict(compute_performance(bot_rows, mode="live")),
        },
        "signals": [signal_to_public(s) for s in signals],
    }


def build_performance_payload(log_path: Path | None = None) -> dict:
    path = log_path or BOT_SIGNALS_LOG
    rows = _read_all_rows(path)
    return {
        "performance": performance_to_dict(compute_performance(rows)),
        "by_bot": build_all_bots_summary(path),
        "total_signals": len(rows),
    }