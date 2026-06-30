"""Análise de greens/reds — calibração e auto-tuning do motor."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from history.predictions import DEFAULT_LOG

RECENT_HALF_LIFE_DAYS = 30.0


def _iter_rows(path: Path) -> list[dict]:
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
    return rows


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _decay_weight(logged_at: str, *, half_life_days: float = RECENT_HALF_LIFE_DAYS) -> float:
    """Peso exponencial — tips recentes contam mais no auto-tune."""
    ts = _parse_ts(logged_at)
    if ts is None:
        return 1.0
    age_days = max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0)
    return math.pow(0.5, age_days / half_life_days)


def _bucket_score(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.70:
        return "high"
    if score >= 0.55:
        return "mid"
    return "low"


def _rate(wins: float, losses: float) -> float | None:
    total = wins + losses
    if total <= 0:
        return None
    return round(100 * wins / total, 1)


def _agg() -> dict:
    return {"win": 0.0, "loss": 0.0, "pnl": 0.0, "stake": 0.0, "ev_win": [], "ev_loss": []}


def _add_sample(bucket: dict, row: dict, weight: float) -> None:
    outcome = str(row.get("outcome") or "").lower()
    if outcome not in ("win", "loss"):
        return
    bucket[outcome] += weight
    try:
        pnl = float(row.get("pnl") or 0)
    except (TypeError, ValueError):
        pnl = 0.0
    try:
        stake = float(row.get("stake_amount") or row.get("kelly_stake") or 0)
    except (TypeError, ValueError):
        stake = 0.0
    bucket["pnl"] += pnl
    bucket["stake"] += stake
    try:
        ev = float(row.get("ev_pct"))
    except (TypeError, ValueError):
        ev = None
    if ev is not None:
        (bucket["ev_win"] if outcome == "win" else bucket["ev_loss"]).append(ev)


def _row_from_bucket(name_key: str, name: str, bucket: dict) -> dict:
    w, l = bucket.get("win", 0.0), bucket.get("loss", 0.0)
    wins_i, losses_i = int(round(w)), int(round(l))
    stake = bucket.get("stake", 0.0)
    pnl = bucket.get("pnl", 0.0)
    roi = round(100 * pnl / stake, 1) if stake > 0 else None
    ev_w = bucket.get("ev_win") or []
    ev_l = bucket.get("ev_loss") or []
    return {
        name_key: name,
        "wins": wins_i,
        "losses": losses_i,
        "weighted_wins": round(w, 2),
        "weighted_losses": round(l, 2),
        "hit_rate_pct": _rate(wins_i, losses_i),
        "weighted_hit_rate_pct": _rate(w, l),
        "total_pnl": round(pnl, 2),
        "roi_pct": roi,
        "avg_ev_win_pct": round(sum(ev_w) / len(ev_w), 1) if ev_w else None,
        "avg_ev_loss_pct": round(sum(ev_l) / len(ev_l), 1) if ev_l else None,
    }


def build_tune_dataset(log_path: Path | None = None) -> dict:
    """
    Dataset rico para auto-tune: decaimento temporal, modo, combos e EV.
    """
    rows = _iter_rows(log_path or DEFAULT_LOG)
    totals = {"win": 0, "loss": 0, "pending": 0, "void": 0}
    by_market: dict[str, dict] = defaultdict(_agg)
    by_league: dict[str, dict] = defaultdict(_agg)
    by_mode: dict[str, dict] = defaultdict(_agg)
    by_combo: dict[str, dict] = defaultdict(_agg)
    by_score: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    recent = _agg()
    ev_win: list[float] = []
    ev_loss: list[float] = []

    for row in rows:
        outcome = str(row.get("outcome") or "pending").lower()
        totals[outcome] = totals.get(outcome, 0) + 1
        if outcome not in ("win", "loss"):
            continue

        market = str(row.get("market") or "—")
        league = str(row.get("league") or "—")
        mode = str(row.get("mode") or "prematch").lower()
        if mode not in ("prematch", "live"):
            mode = "prematch"
        combo = f"{market}|{league}"
        weight = _decay_weight(str(row.get("logged_at") or ""))
        bucket = _bucket_score(row.get("score"))

        _add_sample(by_market[market], row, weight)
        _add_sample(by_league[league], row, weight)
        _add_sample(by_mode[mode], row, weight)
        _add_sample(by_combo[combo], row, weight)
        _add_sample(recent, row, weight)

        by_score[bucket][outcome] += 1
        try:
            ev = float(row.get("ev_pct"))
        except (TypeError, ValueError):
            ev = None
        if ev is not None:
            (ev_win if outcome == "win" else ev_loss).append(ev)

    decided = totals.get("win", 0) + totals.get("loss", 0)
    avg_ev_win = round(sum(ev_win) / len(ev_win), 1) if ev_win else None
    avg_ev_loss = round(sum(ev_loss) / len(ev_loss), 1) if ev_loss else None
    ev_gap = (
        round(avg_ev_loss - avg_ev_win, 1)
        if avg_ev_win is not None and avg_ev_loss is not None
        else None
    )

    market_rows = sorted(
        [_row_from_bucket("market", k, v) for k, v in by_market.items()],
        key=lambda r: r["wins"] + r["losses"],
        reverse=True,
    )
    league_rows = sorted(
        [_row_from_bucket("league", k, v) for k, v in by_league.items()],
        key=lambda r: r["wins"] + r["losses"],
        reverse=True,
    )
    mode_rows = sorted(
        [_row_from_bucket("mode", k, v) for k, v in by_mode.items()],
        key=lambda r: r["wins"] + r["losses"],
        reverse=True,
    )
    combo_rows = sorted(
        [_row_from_bucket("combo", k, v) for k, v in by_combo.items()],
        key=lambda r: r["wins"] + r["losses"],
        reverse=True,
    )
    score_rows = [
        {
            "bucket": bucket,
            "wins": counts.get("win", 0),
            "losses": counts.get("loss", 0),
            "hit_rate_pct": _rate(counts.get("win", 0), counts.get("loss", 0)),
        }
        for bucket, counts in sorted(by_score.items())
        if counts.get("win", 0) + counts.get("loss", 0) > 0
    ]

    rw, rl = recent.get("win", 0.0), recent.get("loss", 0.0)
    return {
        "totals": totals,
        "resolved": decided,
        "hit_rate_pct": round(100 * totals.get("win", 0) / decided, 1) if decided else None,
        "recent": {
            "resolved_weighted": round(rw + rl, 1),
            "hit_rate_pct": _rate(rw, rl),
            "total_pnl": round(recent.get("pnl", 0.0), 2),
        },
        "ev_calibration": {
            "avg_ev_win_pct": avg_ev_win,
            "avg_ev_loss_pct": avg_ev_loss,
            "gap_pct": ev_gap,
        },
        "by_market": market_rows,
        "by_league": league_rows,
        "by_mode": mode_rows,
        "by_combo": combo_rows,
        "by_score_bucket": score_rows,
    }


def build_learning_insights(log_path: Path | None = None) -> dict:
    """Resume acertos/erros e estado de auto-tune para API/UI."""
    data = build_tune_dataset(log_path)
    totals = data["totals"]
    decided = data["resolved"]
    market_rows = data["by_market"]
    league_rows = data["by_league"]
    score_rows = data["by_score_bucket"]
    ev_cal = data["ev_calibration"]

    suggestions: list[str] = []
    if decided >= 5:
        low = next((r for r in score_rows if r["bucket"] == "low"), None)
        low_rate = low.get("hit_rate_pct") if low else None
        if low_rate is not None and low_rate < 45:
            suggestions.append(
                "Scores <0.55 com taxa baixa — considerar subir min_score"
            )
        for row in market_rows:
            if row["wins"] + row["losses"] >= 3 and (row["hit_rate_pct"] or 0) < 40:
                suggestions.append(
                    f"Mercado fraco: {row['market']} ({row['hit_rate_pct']}%)"
                )
        recent = data.get("recent") or {}
        if recent.get("hit_rate_pct") is not None and recent["hit_rate_pct"] < 40:
            suggestions.append(
                f"Forma recente fraca ({recent['hit_rate_pct']}% ponderado)"
            )
        gap = ev_cal.get("gap_pct")
        if gap is not None and gap > 4:
            suggestions.append(
                f"EV médio maior nos reds (+{gap}pp) — modelo pode estar optimista"
            )

    from history.auto_tune import compute_tune_state, load_tune_state

    tune = compute_tune_state(data)
    persisted = load_tune_state()
    tune_payload = tune.to_dict()
    if persisted and persisted.active and not tune.adjustments:
        tune_payload = persisted.to_dict()

    if tune.active and tune.adjustments:
        suggestions.extend(tune.adjustments[:8])

    note = (
        "Auto-tune activo — min_score calibrado com histórico ponderado."
        if tune.active and tune.adjustments
        else tune.reason or "A recolher mais tips resolvidas para auto-tune."
    )

    return {
        "totals": totals,
        "resolved": decided,
        "hit_rate_pct": data["hit_rate_pct"],
        "avg_ev_win_pct": ev_cal.get("avg_ev_win_pct"),
        "avg_ev_loss_pct": ev_cal.get("avg_ev_loss_pct"),
        "ev_gap_pct": ev_cal.get("gap_pct"),
        "recent": data["recent"],
        "by_market": market_rows[:12],
        "by_league": league_rows[:12],
        "by_mode": data["by_mode"][:4],
        "by_score_bucket": score_rows,
        "suggestions": suggestions,
        "auto_tune_active": tune.active and bool(
            tune.adjustments or tune.base_delta or tune.mode_deltas or tune.combo_deltas
        ),
        "auto_tune": tune_payload,
        "note": note,
    }