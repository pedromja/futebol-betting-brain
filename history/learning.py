"""Análise de greens/reds — calibração para ajuste futuro do motor (sem mutar pesos ainda)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from history.predictions import DEFAULT_LOG


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


def _bucket_score(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.70:
        return "high"
    if score >= 0.55:
        return "mid"
    return "low"


def build_learning_insights(log_path: Path | None = None) -> dict:
    """
    Resume acertos/erros por mercado, liga e faixa de score.
    Alimenta decisões humanas ou futuro auto-tuning de min_score.
    """
    rows = _iter_rows(log_path or DEFAULT_LOG)
    totals = {"win": 0, "loss": 0, "pending": 0, "void": 0}
    by_market: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_league: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_score: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    ev_win: list[float] = []
    ev_loss: list[float] = []

    for row in rows:
        outcome = str(row.get("outcome") or "pending").lower()
        totals[outcome] = totals.get(outcome, 0) + 1
        market = str(row.get("market") or "—")
        league = str(row.get("league") or "—")
        bucket = _bucket_score(row.get("score"))
        if outcome in ("win", "loss"):
            by_market[market][outcome] += 1
            by_league[league][outcome] += 1
            by_score[bucket][outcome] += 1
            try:
                ev = float(row.get("ev_pct"))
            except (TypeError, ValueError):
                ev = None
            if ev is not None:
                (ev_win if outcome == "win" else ev_loss).append(ev)

    decided = totals.get("win", 0) + totals.get("loss", 0)

    def _rate(bucket: dict[str, int]) -> float | None:
        w, l = bucket.get("win", 0), bucket.get("loss", 0)
        if w + l == 0:
            return None
        return round(100 * w / (w + l), 1)

    market_rows = []
    for name, counts in by_market.items():
        w, l = counts.get("win", 0), counts.get("loss", 0)
        if w + l == 0:
            continue
        market_rows.append(
            {
                "market": name,
                "wins": w,
                "losses": l,
                "hit_rate_pct": _rate(counts),
            }
        )
    market_rows.sort(key=lambda r: r["wins"] + r["losses"], reverse=True)

    league_rows = []
    for name, counts in by_league.items():
        w, l = counts.get("win", 0), counts.get("loss", 0)
        if w + l == 0:
            continue
        league_rows.append(
            {
                "league": name,
                "wins": w,
                "losses": l,
                "hit_rate_pct": _rate(counts),
            }
        )
    league_rows.sort(key=lambda r: r["wins"] + r["losses"], reverse=True)

    score_rows = [
        {
            "bucket": bucket,
            "wins": counts.get("win", 0),
            "losses": counts.get("loss", 0),
            "hit_rate_pct": _rate(counts),
        }
        for bucket, counts in sorted(by_score.items())
        if counts.get("win", 0) + counts.get("loss", 0) > 0
    ]

    avg_ev_win = round(sum(ev_win) / len(ev_win), 1) if ev_win else None
    avg_ev_loss = round(sum(ev_loss) / len(ev_loss), 1) if ev_loss else None

    suggestions: list[str] = []
    if decided >= 5:
        low = by_score.get("low", {})
        if _rate(low) is not None and _rate(low) < 45:
            suggestions.append(
                "Scores <0.55 com taxa baixa — considerar subir min_score"
            )
        for row in market_rows:
            if row["wins"] + row["losses"] >= 3 and (row["hit_rate_pct"] or 0) < 40:
                suggestions.append(
                    f"Mercado fraco: {row['market']} ({row['hit_rate_pct']}%)"
                )

    return {
        "totals": totals,
        "resolved": decided,
        "hit_rate_pct": round(100 * totals.get("win", 0) / decided, 1) if decided else None,
        "avg_ev_win_pct": avg_ev_win,
        "avg_ev_loss_pct": avg_ev_loss,
        "by_market": market_rows[:12],
        "by_league": league_rows[:12],
        "by_score_bucket": score_rows,
        "suggestions": suggestions,
        "auto_tune_active": False,
        "note": "Análise apenas — o motor ainda não aplica estes dados automaticamente.",
    }