"""Payload UI — dicas IA e acertividade acumulada por mercado."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from bots.ia_audit import (
    IA_TEMPLATE_PREFIXES,
    build_ia_audit_dataset,
    is_ia_bot,
    load_ia_audit,
)
from config.data_paths import BOT_SIGNALS_LOG
from history.learning import _rate
from history.tips_history import _read_all_rows

IA_TEMPLATE_LABELS: dict[str, str] = {
    "live_pattern_discrepancy": "IA — Padrão vs live",
    "live_pattern_post_ht": "IA — Favorito a perder no HT",
    "live_pattern_conditional_window": "IA — Janela condicional",
    "live_scenario_ev_confirmed": "IA — EV cenário confirmado",
    "live_scenario_apathy_warn": "IA — Apatia (não seguir)",
    "prematch_underdog_raca_ia": "IA — Underdog marca fácil",
    "prematch_underdog_galinha_ia": "IA — Underdog marca difícil",
    "prematch_underdog_favorite_hunt": "IA — Caça favoritos",
}


def _is_ia_row(row: dict) -> bool:
    return is_ia_bot(row.get("template"), row.get("bot_name"))


def _template_label(template: str | None, bot_name: str | None = None) -> str:
    t = str(template or "")
    if t in IA_TEMPLATE_LABELS:
        return IA_TEMPLATE_LABELS[t]
    if any(t.startswith(p) for p in IA_TEMPLATE_PREFIXES):
        return t.replace("live_", "IA — ").replace("_", " ")
    return str(bot_name or "IA")


def ia_tip_to_public(row: dict) -> dict:
    ctx = row.get("ia_context") or {}
    outcome = str(row.get("outcome") or "pending").lower()
    return {
        "id": row.get("signature") or f"{row.get('bot_id')}|{row.get('logged_at')}",
        "logged_at": row.get("logged_at") or row.get("scanned_at"),
        "bot_id": row.get("bot_id"),
        "bot_name": row.get("bot_name"),
        "template": row.get("template"),
        "template_label": _template_label(row.get("template"), row.get("bot_name")),
        "mode": row.get("mode") or "live",
        "home": row.get("home"),
        "away": row.get("away"),
        "league": row.get("league"),
        "market": row.get("market"),
        "odd": row.get("odd"),
        "ev_pct": row.get("ev_pct"),
        "score": row.get("score"),
        "minute": row.get("minute"),
        "score_at_tip": row.get("score_at_tip"),
        "final_score": row.get("final_score"),
        "outcome": outcome,
        "pnl": row.get("pnl"),
        "stake_amount": row.get("stake_amount"),
        "resolved_at": row.get("resolved_at"),
        "pattern_summary": ctx.get("pattern_summary"),
        "scenario_summary": ctx.get("scenario_summary"),
        "underdog_summary": ctx.get("underdog_ia_summary") or ctx.get("underdog_summary"),
        "ia_context": ctx,
    }


def _market_stats(rows: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "pending": 0, "pnl": 0.0, "stake": 0.0}
    )
    for row in rows:
        market = str(row.get("market") or "—").strip() or "—"
        outcome = str(row.get("outcome") or "pending").lower()
        b = buckets[market]
        if outcome == "win":
            b["wins"] += 1
        elif outcome == "loss":
            b["losses"] += 1
        else:
            b["pending"] += 1
        if outcome in ("win", "loss"):
            try:
                b["pnl"] += float(row.get("pnl") or 0)
            except (TypeError, ValueError):
                pass
            try:
                b["stake"] += float(row.get("stake_amount") or 0)
            except (TypeError, ValueError):
                pass

    out: list[dict] = []
    for market, b in buckets.items():
        w, l = b["wins"], b["losses"]
        decided = w + l
        stake = b["stake"]
        pnl = b["pnl"]
        out.append(
            {
                "market": market,
                "wins": w,
                "losses": l,
                "pending": b["pending"],
                "samples": decided,
                "hit_rate_pct": _rate(w, l),
                "total_pnl": round(pnl, 2),
                "roi_pct": round(100 * pnl / stake, 1) if stake > 0 else None,
            }
        )
    out.sort(key=lambda x: (-(x.get("samples") or 0), -(x.get("hit_rate_pct") or 0)))
    return out


def build_ia_tips_payload(
    *,
    log_path=None,
    limit: int = 80,
    auto_audit: bool = True,
) -> dict:
    path = log_path or BOT_SIGNALS_LOG
    all_rows = _read_all_rows(path)
    ia_rows = [r for r in all_rows if _is_ia_row(r)]

    wins = losses = pending = 0
    total_pnl = 0.0
    total_stake = 0.0
    for row in ia_rows:
        outcome = str(row.get("outcome") or "pending").lower()
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            pending += 1
        if outcome in ("win", "loss"):
            try:
                total_pnl += float(row.get("pnl") or 0)
                total_stake += float(row.get("stake_amount") or 0)
            except (TypeError, ValueError):
                pass

    decided = wins + losses
    tips_sorted = list(reversed(ia_rows))
    tips = [ia_tip_to_public(r) for r in tips_sorted[: max(1, limit)]]

    audit = load_ia_audit()
    if auto_audit and decided >= 4:
        try:
            audit = build_ia_audit_dataset(path)
            from bots.ia_audit import save_ia_audit

            save_ia_audit(audit)
        except Exception:
            pass

    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {
            "tips": len(ia_rows),
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "resolved": decided,
            "hit_rate_pct": _rate(wins, losses),
            "total_pnl": round(total_pnl, 2),
            "roi_pct": round(100 * total_pnl / total_stake, 1) if total_stake > 0 else None,
        },
        "by_market": _market_stats(ia_rows),
        "tips": tips,
        "audit": {
            "active": audit.active,
            "resolved_ia": audit.resolved_ia,
            "restrictions": audit.restrictions,
            "knowledge": audit.knowledge[:12],
            "insights": audit.insights[:8],
            "updated_at": audit.updated_at,
        },
    }