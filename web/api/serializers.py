"""Converte resultados do motor para JSON — camada fina, evolui com o projeto."""

from decision.engine import Decision
from discovery.fixture_types import UpcomingFixture
from discovery.live_fixture_types import LiveFixture
from environment.types import CONDITION_LABELS, MatchEnvironment
from scanner.live_ranker import LiveScanResult, RankedLiveMatch
from scanner.ranker import RankedMatch, ScanResult

WEATHER_SOURCE_LABELS = {
    "openweathermap_current": "Tempo atual",
    "openweathermap_forecast": "Previsão para o jogo",
    "sample": "Estimativa",
}


def environment_to_dict(env: MatchEnvironment | None) -> dict | None:
    if env is None:
        return None
    w = env.weather
    venue = env.venue
    venue_label = env.venue_resolved_name or venue.stadium or venue.city
    return {
        "venue": venue_label,
        "city": venue.city,
        "stadium": venue.stadium,
        "altitude_m": round(venue.altitude_m),
        "home_altitude_m": round(env.home_profile.altitude_m),
        "away_altitude_m": round(env.away_profile.altitude_m),
        "weather": {
            "condition": w.condition.value,
            "condition_label": CONDITION_LABELS.get(w.condition, w.condition.value),
            "temperature_c": round(w.temperature_c, 1),
            "precipitation_mm": round(w.precipitation_mm, 1),
            "wind_kmh": round(w.wind_kmh, 1),
            "humidity_pct": round(w.humidity_pct),
            "severity": round(w.computed_severity, 3),
        },
        "travel": {
            "distance_km": round(env.travel.away_distance_km),
            "hours": round(env.travel.away_travel_hours, 1),
            "timezone_diff": env.travel.timezone_diff,
        },
        "weather_source": env.weather_source,
        "weather_source_label": WEATHER_SOURCE_LABELS.get(
            env.weather_source, env.weather_source
        ),
        "weather_fetched_at": env.weather_fetched_at,
    }


def environment_impact_to_dict(decision: Decision) -> dict | None:
    if not decision.environment:
        return None
    out: dict = {}
    for key, dist in (
        ("home", decision.home_env_distortion),
        ("away", decision.away_env_distortion),
    ):
        if dist and dist.total_distortion > 0.001:
            out[key] = {
                "team": dist.team_name,
                "attack": round(dist.adjusted_attack, 2),
                "attack_orig": round(dist.original_attack, 2),
                "defense": round(dist.adjusted_defense, 2),
                "defense_orig": round(dist.original_defense, 2),
                "distortion": round(dist.total_distortion, 3),
            }
    return out or None


def upcoming_fixture_to_dict(fx: UpcomingFixture) -> dict:
    fixture_id = fx.stats_hint.get("api_football_fixture_id")
    return {
        "home": fx.home,
        "away": fx.away,
        "league": fx.league,
        "kickoff": fx.kickoff,
        "stage": fx.stage,
        "source": fx.source,
        "fixture_id": fixture_id,
    }


def ranked_match_to_dict(item: RankedMatch) -> dict:
    best = item.decision.recommendation.best
    return {
        "rank": item.rank,
        "home": item.fixture.home,
        "away": item.fixture.away,
        "league": item.fixture.league,
        "kickoff": item.fixture.kickoff,
        "best_market": item.best_market,
        "best_ev_pct": round(item.best_ev * 100, 1),
        "best_score": round(item.best_score, 3),
        "odd": round(best.odd, 2) if best else None,
        "should_bet": item.should_bet,
        "min_score": item.effective_min_score,
        "top_markets": item.top_markets,
        "kelly_stake": item.kelly_stake,
        "kelly_pct": item.kelly_pct,
        "stake_level": item.stake_plan.level if item.stake_plan else None,
        "stake_label": item.stake_plan.label if item.stake_plan else None,
        "stake_pct": item.stake_plan.bankroll_pct if item.stake_plan else None,
        "stake_amount": item.stake_plan.suggested_amount if item.stake_plan else None,
        "stake_display": item.stake_plan.display if item.stake_plan else None,
        "stage": item.fixture.stage,
        "summary": item.decision.summary,
        "environment": environment_to_dict(item.decision.environment),
        "environment_impact": environment_impact_to_dict(item.decision),
    }


def scan_result_to_dict(result: ScanResult) -> dict:
    payload = {
        "scanned_at": result.scanned_at,
        "hours_window": result.hours_window,
        "requested_hours": result.requested_hours,
        "window_extended": result.window_extended,
        "total_found": result.total_found,
        "total_analyzed": result.total_analyzed,
        "best": ranked_match_to_dict(result.best) if result.best else None,
        "ranked": [ranked_match_to_dict(r) for r in result.ranked],
        "fixtures": [upcoming_fixture_to_dict(f) for f in result.fixtures],
    }
    if result.window_extended:
        payload["notice"] = (
            f"Sem jogos nas próximas {result.requested_hours}h "
            f"— janela alargada para {result.hours_window}h"
        )
    return payload


LIVE_SOURCE_LABELS = {
    "api-football": "API-Football",
    "espn": "ESPN",
    "none": "Indisponível",
}

ODDS_SOURCE_LABELS = {
    "api-football-live": "Odds API-Football",
    "api-football-prematch": "Odds pré-jogo",
    "espn-live": "Odds ESPN",
}


def live_fixture_to_dict(fx: LiveFixture) -> dict:
    odds_src = fx.odds_source or None
    return {
        "home": fx.home,
        "away": fx.away,
        "league": fx.league,
        "stage": fx.stage,
        "home_score": fx.home_score,
        "away_score": fx.away_score,
        "score": fx.score_label,
        "minute": fx.minute,
        "injury_time": fx.injury_time,
        "status": fx.status_short,
        "kickoff": fx.kickoff,
        "fixture_id": fx.fixture_id,
        "source": fx.source,
        "source_label": LIVE_SOURCE_LABELS.get(fx.source, fx.source),
        "odds_source": odds_src,
        "odds_source_label": ODDS_SOURCE_LABELS.get(odds_src, odds_src) if odds_src else None,
    }


def ranked_live_to_dict(item: RankedLiveMatch) -> dict:
    fx = item.fixture
    best = item.decision.recommendation.best
    base = live_fixture_to_dict(fx)
    base.update(
        {
            "rank": item.rank,
            "best_market": item.best_market,
            "best_ev_pct": round(item.best_ev * 100, 1),
            "best_score": round(item.best_score, 3),
            "odd": round(best.odd, 2) if best else None,
            "should_bet": item.should_bet,
            "min_score": item.effective_min_score,
            "top_markets": item.top_markets,
            "kelly_stake": item.kelly_stake,
            "stake_level": item.stake_plan.level if item.stake_plan else None,
            "stake_label": item.stake_plan.label if item.stake_plan else None,
            "stake_pct": item.stake_plan.bankroll_pct if item.stake_plan else None,
            "stake_amount": item.stake_plan.suggested_amount if item.stake_plan else None,
            "stake_display": item.stake_plan.display if item.stake_plan else None,
            "summary": item.decision.summary,
            "environment": environment_to_dict(item.decision.environment),
            "environment_impact": environment_impact_to_dict(item.decision),
        }
    )
    return base


def live_scan_result_to_dict(
    result: LiveScanResult,
    *,
    last_tip: dict | None = None,
    live_source: str = "none",
) -> dict:
    best = result.best
    payload = {
        "scanned_at": result.scanned_at,
        "total_live": result.total_live,
        "total_analyzed": result.total_analyzed,
        "live_source": live_source,
        "live_source_label": LIVE_SOURCE_LABELS.get(live_source, live_source),
        "skipped": [
            {"match": label, "reason": reason}
            for label, reason in result.skipped
        ],
        "best": ranked_live_to_dict(best) if best else None,
        "ranked": [ranked_live_to_dict(r) for r in result.ranked],
        "fixtures": [live_fixture_to_dict(f) for f in result.fixtures],
    }
    if last_tip:
        payload["last_tip"] = last_tip
    return payload