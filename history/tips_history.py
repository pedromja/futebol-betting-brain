"""Histórico público de tips — performance e resultados."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from history.predictions import DEFAULT_LOG


@dataclass
class TipsPerformance:
    total: int
    wins: int
    losses: int
    pending: int
    voids: int
    hit_rate_pct: float | None
    total_pnl: float
    roi_pct: float | None
    resolved: int


def load_tips(log_path: Path | None = None, *, limit: int = 100) -> list[dict]:
    path = log_path or DEFAULT_LOG
    if not path.exists():
        return []

    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    rows.reverse()
    return rows[:limit]


def compute_performance(tips: list[dict]) -> TipsPerformance:
    wins = losses = pending = voids = 0
    total_pnl = 0.0
    stake_sum = 0.0

    for row in tips:
        outcome = str(row.get("outcome") or "pending").lower()
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        elif outcome == "void":
            voids += 1
        else:
            pending += 1

        pnl = row.get("pnl")
        if pnl is not None:
            try:
                total_pnl += float(pnl)
            except (TypeError, ValueError):
                pass

        if outcome in ("win", "loss"):
            stake = row.get("stake_amount") or row.get("kelly_stake")
            if stake is not None:
                try:
                    stake_sum += float(stake)
                except (TypeError, ValueError):
                    pass

    resolved = wins + losses
    hit_rate = round(100 * wins / resolved, 1) if resolved else None
    roi = round(100 * total_pnl / stake_sum, 1) if stake_sum > 0 else None

    return TipsPerformance(
        total=len(tips),
        wins=wins,
        losses=losses,
        pending=pending,
        voids=voids,
        hit_rate_pct=hit_rate,
        total_pnl=round(total_pnl, 2),
        roi_pct=roi,
        resolved=resolved,
    )


def tip_to_public(row: dict) -> dict:
    outcome = str(row.get("outcome") or "pending").lower()
    stake = row.get("stake_amount") or row.get("kelly_stake")
    return {
        "id": row.get("signature") or f"{row.get('home')}|{row.get('away')}|{row.get('logged_at')}",
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
    }


def build_history_payload(
    log_path: Path | None = None,
    *,
    limit: int = 50,
) -> dict:
    tips = load_tips(log_path, limit=limit)
    perf = compute_performance(tips)
    return {
        "performance": {
            "total": perf.total,
            "wins": perf.wins,
            "losses": perf.losses,
            "pending": perf.pending,
            "voids": perf.voids,
            "hit_rate_pct": perf.hit_rate_pct,
            "total_pnl": perf.total_pnl,
            "roi_pct": perf.roi_pct,
            "resolved": perf.resolved,
        },
        "tips": [tip_to_public(t) for t in tips],
    }