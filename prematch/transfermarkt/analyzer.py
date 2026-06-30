"""Orquestra os 4 pilares Transfermarkt para um confronto pré-jogo."""

from __future__ import annotations

from prematch.transfermarkt.absences import compute_absences
from prematch.transfermarkt.manager_h2h import compute_tactical
from prematch.transfermarkt.referee_stats import compute_referee
from prematch.transfermarkt.store import get_store
from prematch.transfermarkt.types import PrematchInsights
from prematch.transfermarkt.value_gap import compute_value_gap


def _market_family(market_label: str) -> str:
    text = (market_label or "").lower()
    if "over" in text or "btts sim" in text:
        return "over"
    if "under" in text or "btts não" in text or "btts nao" in text:
        return "under"
    if "vitória casa" in text or "casa" in text and "dupla" not in text:
        return "home"
    if "vitória fora" in text or "fora" in text and "dupla" not in text:
        return "away"
    if "empate" in text:
        return "draw"
    return "other"


def _compute_alignment(
    insights: PrematchInsights,
    best_market: str | None = None,
) -> tuple[str, list[str]]:
    signals: list[str] = []
    score = 0

    if insights.value_gap:
        vg = insights.value_gap
        if vg.signal == "home_undervalued":
            signals.append("Valor: plantel casa subprecificado vs odds")
            score += 1
        elif vg.signal == "away_undervalued":
            signals.append("Valor: plantel fora subprecificado vs odds")
            score += 1
        elif vg.signal in ("home_overpriced", "away_overpriced"):
            score -= 1

    if insights.tactical:
        t = insights.tactical
        if t.goals_tendency == "over":
            signals.append("Tática/H2H: jogo aberto — Over/BTTS")
            if _market_family(best_market or "") == "over":
                score += 1
        elif t.goals_tendency == "under":
            signals.append("Tática/H2H: jogo fechado — Under")
            if _market_family(best_market or "") == "under":
                score += 1

    if insights.referee:
        r = insights.referee
        if r.penalty_signal == "high":
            signals.append("Árbitro: penáltis acima da média")
        if r.cards_signal == "high":
            signals.append("Árbitro: cartões acima da média")

    home_imp = insights.home_absences.total_impact if insights.home_absences else 0
    away_imp = insights.away_absences.total_impact if insights.away_absences else 0
    if home_imp >= 0.25:
        signals.append(f"Lesões casa: impacto {home_imp:.0%}")
        if _market_family(best_market or "") == "away":
            score += 1
    if away_imp >= 0.25:
        signals.append(f"Lesões fora: impacto {away_imp:.0%}")
        if _market_family(best_market or "") == "home":
            score += 1

    if score >= 2:
        alignment = "strong"
    elif score <= -1:
        alignment = "weak"
    else:
        alignment = "neutral"
    return alignment, signals


def _build_summary(insights: PrematchInsights) -> str:
    parts: list[str] = []
    if insights.value_gap:
        parts.append(insights.value_gap.label)
    if insights.tactical:
        parts.append(insights.tactical.label)
    if insights.referee:
        parts.append(insights.referee.label)
    if insights.home_absences and insights.home_absences.total_impact >= 0.15:
        parts.append(f"Casa: {insights.home_absences.label}")
    if insights.away_absences and insights.away_absences.total_impact >= 0.15:
        parts.append(f"Fora: {insights.away_absences.label}")
    return " · ".join(parts[:3]) if parts else "Sem dados Transfermarkt para este confronto."


def analyze_prematch(
    home: str,
    away: str,
    *,
    odds_hint: dict | None = None,
    referee_name: str | None = None,
    best_market: str | None = None,
) -> PrematchInsights:
    store = get_store()
    home_squad = store.squad(home)
    away_squad = store.squad(away)
    home_mgr = store.manager(home)
    away_mgr = store.manager(away)
    h2h = None
    if home_mgr and away_mgr:
        h2h = store.manager_h2h(home_mgr.manager, away_mgr.manager)

    ref = None
    if referee_name:
        ref = store.referee(referee_name)
    if not ref:
        ref = store.referee_for_fixture(home, away)

    value_gap = compute_value_gap(
        home_squad.market_value_m if home_squad else 0,
        away_squad.market_value_m if away_squad else 0,
        odds_hint,
    )
    tactical = compute_tactical(home_mgr, away_mgr, h2h)
    referee_insight = compute_referee(ref)
    home_abs = compute_absences(home, home_squad, store.absences(home))
    away_abs = compute_absences(away, away_squad, store.absences(away))

    data_available = bool(
        value_gap or tactical or referee_insight or home_abs or away_abs
    )

    insights = PrematchInsights(
        home=home,
        away=away,
        data_available=data_available,
        value_gap=value_gap,
        tactical=tactical,
        referee=referee_insight,
        home_absences=home_abs,
        away_absences=away_abs,
    )
    insights.alignment, insights.signals = _compute_alignment(insights, best_market)
    insights.summary = _build_summary(insights)
    return insights