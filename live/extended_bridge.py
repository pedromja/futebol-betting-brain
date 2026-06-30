"""Liga ExtendedMarketAnalyzer ao bundle de stats e contexto live da PWA."""

from __future__ import annotations

from markets.extended import ExtendedMarketAnalyzer, ExtendedMarketPick, ExtendedOdds, LiveContext
from discovery.match_stats_types import MatchLiveStatsBundle


def _remaining_minutes(minute: int, injury_time: int = 0) -> float:
    base = max(0, 90 - minute)
    return float(base + max(0, injury_time))


def _pressure(home_possession: float, home_xg: float, away_xg: float) -> str:
    if home_possession >= 0.62 or home_xg >= away_xg * 2.5:
        return "high"
    if home_possession <= 0.38 or away_xg >= home_xg * 2.5:
        return "low"
    return "medium"


def build_live_context(
    bundle: MatchLiveStatsBundle,
    *,
    home_score: int,
    away_score: int,
    minute: int,
    injury_time: int = 0,
) -> LiveContext:
    home_xg = bundle.home.xg or 0.0
    away_xg = bundle.away.xg or 0.0
    home_poss = (bundle.home.possession_pct or 50) / 100.0
    return LiveContext(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        home_xg=home_xg,
        away_xg=away_xg,
        home_possession=home_poss,
        home_shots=bundle.home.shots_total or bundle.home.shots_on or 0,
        away_shots=bundle.away.shots_total or bundle.away.shots_on or 0,
        home_pressure=_pressure(home_poss, home_xg, away_xg),
        remaining_minutes=_remaining_minutes(minute, injury_time),
    )


def _estimate_extended_odds(odds_hint: dict | None, bundle: MatchLiveStatsBundle) -> ExtendedOdds:
    hint = odds_hint or {}
    home_win = float(hint.get("home_win") or 2.10)
    draw = float(hint.get("draw") or 3.20)
    away_win = float(hint.get("away_win") or 3.50)
    over_25 = float(hint.get("over_25") or 1.95)

    total_corners = (bundle.home.corners or 0) + (bundle.away.corners or 0)
    corners_line = 6.5 if total_corners < 4 else 8.5 if total_corners >= 7 else 7.5

    fav_home = home_win < away_win
    handicap_home = max(1.55, round(home_win * 1.35, 2)) if fav_home else max(2.80, round(home_win * 2.1, 2))
    handicap_away = max(1.25, round(min(draw, away_win) * 0.92, 2))

    corners_over = max(1.45, round(over_25 * 0.82, 2))
    corners_under = max(1.45, round(2.15 - (over_25 - 1.8) * 0.35, 2))
    home_team_over = max(1.50, round(home_win * 0.72, 2))

    return ExtendedOdds(
        handicap_home_line=-0.5,
        handicap_home=handicap_home,
        handicap_away_line=0.5,
        handicap_away=handicap_away,
        corners_line=corners_line,
        corners_over=corners_over,
        corners_under=corners_under,
        corners_current=total_corners or None,
        home_team_goals_line=1.5,
        home_team_goals_over=home_team_over,
        home_team_goals_under=max(1.45, round(2.4 - (home_team_over - 1.5) * 0.4, 2)),
        source=str(hint.get("_source") or "estimated"),
    )


def extended_pick_to_dict(pick: ExtendedMarketPick) -> dict:
    return {
        "market_type": pick.market_type.value,
        "label": pick.label,
        "odd": round(pick.odd, 2),
        "model_prob_pct": round(pick.model_prob * 100, 1),
        "implied_prob_pct": round(pick.implied_prob * 100, 1),
        "ev_pct": round(pick.ev_percent, 1),
        "reasoning": pick.reasoning,
        "status": pick.status,
    }


def analyze_extended_markets(
    bundle: MatchLiveStatsBundle,
    *,
    home_score: int,
    away_score: int,
    minute: int,
    home_name: str = "Casa",
    away_name: str = "Fora",
    injury_time: int = 0,
    odds_hint: dict | None = None,
    max_picks: int = 6,
) -> list[dict]:
    ctx = build_live_context(
        bundle,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        injury_time=injury_time,
    )
    odds = _estimate_extended_odds(odds_hint, bundle)
    if odds_hint:
        odds.source = str(odds_hint.get("_source") or odds.source)

    analyzer = ExtendedMarketAnalyzer()
    picks = analyzer.analyze(ctx, odds, home_name, away_name)
    return [extended_pick_to_dict(p) for p in picks[:max_picks]]