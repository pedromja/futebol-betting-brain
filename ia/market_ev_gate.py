"""Gate EV leve — cruza tips IA com odds ESPN e rejeita sem valor real."""

from __future__ import annotations

import os
import re

# EV mínimo para emitir tip (decimal, ex: 0.04 = 4%)
_MIN_EV = float(os.getenv("IA_MIN_EV_PCT", "4")) / 100.0
# Penalização odds ESPN possivelmente stale in-play
_LIVE_ODDS_HAIRCUT = float(os.getenv("IA_LIVE_ODDS_HAIRCUT", "0.94"))

_MARKET_TO_KEY: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"over\s*2\.?5", re.I), "over_25"),
    (re.compile(r"under\s*2\.?5", re.I), "under_25"),
    (re.compile(r"over\s*1\.?5", re.I), "over_15_proxy"),
    (re.compile(r"under\s*1\.?5", re.I), "under_15_proxy"),
    (re.compile(r"over\s*3\.?5", re.I), "over_35_proxy"),
    (re.compile(r"under\s*3\.?5", re.I), "under_35_proxy"),
    (re.compile(r"over\s*0\.?5\s*ht|over\s*1\s*ht|over\s*1\.?5\s*ht", re.I), "ht_goals_proxy"),
    (re.compile(r"btts\s*sim|ambas.*sim", re.I), "btts_yes"),
    (re.compile(r"btts\s*n[aã]o|ambas.*n[aã]o", re.I), "btts_no"),
    (re.compile(r"vit[oó]ria\s*casa|vitória casa", re.I), "home_win"),
    (re.compile(r"^empate$", re.I), "draw"),
    (re.compile(r"vit[oó]ria\s*fora", re.I), "away_win"),
    (re.compile(r"dnb\s*casa|empate anula.*casa", re.I), "home_win"),
    (re.compile(r"dnb\s*fora|empate anula.*fora", re.I), "away_win"),
    (re.compile(r"dupla.*1x", re.I), "double_chance_1x"),
    (re.compile(r"dupla.*x2", re.I), "double_chance_x2"),
    (re.compile(r"dupla.*12", re.I), "double_chance_12"),
]


def _norm_market(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip().lower())


def _total_goals(home_score: int, away_score: int) -> int:
    return max(0, int(home_score) + int(away_score))


def _goals_live_state(home_score: int, away_score: int, both_scored: bool) -> dict:
    return {
        "total": _total_goals(home_score, away_score),
        "home": max(0, int(home_score)),
        "away": max(0, int(away_score)),
        "btts": both_scored or (home_score > 0 and away_score > 0),
    }


def _resolve_odds_key(market: str) -> str | None:
    blob = _norm_market(market)
    for pattern, key in _MARKET_TO_KEY:
        if pattern.search(blob):
            return key
    return None


def _pick_odd(odds_hint: dict, key: str) -> float | None:
    raw = odds_hint.get(key)
    try:
        val = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        val = None
    if val and val >= 1.01:
        return round(val, 3)
    return None


def _proxy_odd(
    key: str,
    odds_hint: dict,
    *,
    goals: dict,
    minute: int,
) -> tuple[float | None, str]:
    """Deriva odd conservadora quando ESPN só tem linha principal (O/U 2.5)."""
    o25 = _pick_odd(odds_hint, "over_25")
    u25 = _pick_odd(odds_hint, "under_25")
    total = goals["total"]

    if key == "over_15_proxy":
        if total >= 2:
            return None, "linha_ja_bateu"
        if total == 1:
            return round(max(1.08, (o25 or 1.9) * 0.42), 3), "proxy_o15_de_o25"
        if o25:
            return round(o25 * 0.58, 3), "proxy_o15_de_o25"
        return None, "sem_odd_o25"

    if key == "under_15_proxy":
        if total >= 2:
            return None, "linha_ja_perdeu"
        if u25:
            return round(max(1.15, u25 * 0.72), 3), "proxy_u15_de_u25"
        return None, "sem_odd_u25"

    if key == "over_35_proxy":
        if total >= 4:
            return None, "linha_ja_bateu"
        if o25:
            return round(o25 * 1.52, 3), "proxy_o35_de_o25"
        return None, "sem_odd_o25"

    if key == "under_35_proxy":
        if total >= 4:
            return None, "linha_ja_perdeu"
        if u25:
            return round(max(1.05, u25 * 0.68), 3), "proxy_u35_de_u25"
        return None, "sem_odd_u25"

    if key == "ht_goals_proxy":
        if minute > 45:
            return None, "ht_terminado"
        if o25:
            return round(o25 * 0.48, 3), "proxy_ht_de_o25"
        return None, "sem_odd_ht"

    return None, "chave_desconhecida"


def resolve_book_odd(
    market: str,
    odds_hint: dict | None,
    *,
    home_score: int = 0,
    away_score: int = 0,
    minute: int = 0,
    live: bool = True,
) -> dict:
    """
    Resolve odd de mercado a partir do odds_hint ESPN.
    Devolve dict com odd, fonte, ev_key, nota.
    """
    oh = odds_hint or {}
    key = _resolve_odds_key(market)
    if not key:
        return {"odd": None, "source": "none", "reject_reason": "mercado_sem_mapeamento_odd"}

    goals = _goals_live_state(
        home_score, away_score, home_score > 0 and away_score > 0
    )

    if key == "over_25" and goals["total"] >= 3:
        return {"odd": None, "source": "book", "reject_reason": "over25_ja_bateu"}
    if key == "under_25" and goals["total"] >= 3:
        return {"odd": None, "source": "book", "reject_reason": "under25_ja_perdeu"}
    if key == "btts_yes" and goals["btts"]:
        return {"odd": None, "source": "book", "reject_reason": "btts_ja_bateu"}
    if key == "btts_no" and goals["btts"]:
        return {"odd": None, "source": "book", "reject_reason": "btts_ja_perdeu"}

    if key.endswith("_proxy") or key == "ht_goals_proxy":
        odd, note = _proxy_odd(key, oh, goals=goals, minute=minute)
        if not odd:
            return {"odd": None, "source": "proxy", "reject_reason": note}
        src = f"espn_proxy:{note}"
    else:
        odd = _pick_odd(oh, key)
        if not odd and key in ("home_win", "away_win"):
            odd = _pick_odd(oh, key)
        if not odd or (key.startswith("double_chance") and odd <= 1.01):
            return {"odd": None, "source": "book", "reject_reason": "odd_indisponivel_espn"}
        src = f"espn:{key}"

    if live and odd:
        odd = round(odd * _LIVE_ODDS_HAIRCUT, 3)

    return {
        "odd": odd,
        "source": src,
        "odds_key": key,
        "goals_total": goals["total"],
        "minute": minute,
    }


def confidence_to_model_prob(
    confidence_pct: float,
    *,
    prematch_alignment: str = "neutral",
) -> float:
    """Converte confiança LLM em probabilidade conservadora (nunca overfit)."""
    try:
        conf = float(confidence_pct)
    except (TypeError, ValueError):
        conf = 50.0
    conf = max(0.0, min(100.0, conf))
    # 28%–68% — abaixo da confiança bruta do LLM
    prob = 0.28 + (conf / 100.0) * 0.40
    align = str(prematch_alignment or "neutral").lower()
    if align == "divergent":
        prob *= 0.88
    elif align == "convergent":
        prob *= 1.04
    return round(max(0.22, min(0.68, prob)), 4)


def compute_ev_decimal(model_prob: float, odd: float) -> float:
    if odd < 1.01:
        return -1.0
    return round(model_prob * odd - 1.0, 4)


def apply_ev_gate(
    tip: dict,
    odds_hint: dict | None,
    *,
    home_score: int = 0,
    away_score: int = 0,
    minute: int = 0,
    min_ev: float | None = None,
) -> tuple[dict | None, str | None]:
    """
    Enriquece tip com book_odd, model_prob, ev_pct.
    Devolve (tip, None) se OK ou (None, reject_reason).
    """
    threshold = _MIN_EV if min_ev is None else min_ev
    market = str(tip.get("market") or "")
    resolved = resolve_book_odd(
        market,
        odds_hint,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        live=True,
    )
    if not resolved.get("odd"):
        return None, resolved.get("reject_reason") or "sem_odd"

    odd = float(resolved["odd"])
    model_prob = confidence_to_model_prob(
        tip.get("confidence_pct", 0),
        prematch_alignment=str(tip.get("prematch_alignment") or "neutral"),
    )
    ev = compute_ev_decimal(model_prob, odd)
    implied = round(1.0 / odd, 4) if odd > 1 else 0.0
    edge = round(model_prob - implied, 4)

    if ev < threshold:
        return None, f"ev_baixo_{round(ev * 100, 1)}pct"

    if model_prob < implied:
        return None, f"prob_abaixo_mercado_{round(implied * 100, 1)}pct"

    enriched = {
        **tip,
        "odd": odd,
        "book_odd": odd,
        "odds_source": resolved.get("source"),
        "model_prob": model_prob,
        "implied_prob": implied,
        "prob_edge": edge,
        "ev": ev,
        "ev_pct": round(ev * 100, 1),
        "min_ev_pct": round(threshold * 100, 1),
    }
    return enriched, None