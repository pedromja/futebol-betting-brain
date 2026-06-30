"""Converte resultados do motor para JSON — camada fina, evolui com o projeto."""

from __future__ import annotations

from decision.engine import Decision
from discovery.fixture_types import UpcomingFixture
from discovery.live_fixture_types import LiveFixture
from environment.types import CONDITION_LABELS, MatchEnvironment
from markets.markets import Market
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
    venue_correction = None
    if env.venue_corrected_from_usual:
        venue_correction = {
            "usual_home": env.venue_usual_home,
            "sources": list(env.venue_verification_sources),
            "is_neutral_venue": env.is_neutral_venue,
        }

    return {
        "venue": venue_label,
        "city": venue.city,
        "stadium": venue.stadium,
        "venue_correction": venue_correction,
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


def _score_breakdown_to_dict(market: Market) -> dict:
    bd = market.breakdown
    return {
        "edge_pct": round(bd.edge * 100, 1),
        "ev_contribution": round(bd.ev_contribution, 3),
        "conf_contribution": round(bd.conf_contribution, 3),
        "form_contribution": round(bd.form_contribution, 3),
        "prob_derivation": bd.prob_derivation,
        "total_score": round(market.total_score, 3),
        "confidence": round(market.confidence, 3),
        "form_score": round(market.form_score, 3),
    }


def _context_factors_for_decision(item: RankedMatch | RankedLiveMatch) -> list[str]:
    factors: list[str] = []
    decision = item.decision

    if item.block_reason:
        factors.append(f"Bloqueio activo: {item.block_reason}")

    mot = getattr(item, "motivation", None) or {}
    if mot.get("summary"):
        factors.append(f"Motivação: {mot['summary']}")
    for label in (mot.get("labels") or [])[:3]:
        if label:
            factors.append(label)

    tm = getattr(item, "transfermarkt", None) or {}
    for signal in (tm.get("signals") or [])[:3]:
        factors.append(f"Transfermarkt: {signal}")
    if tm.get("summary") and tm.get("data_available"):
        factors.append(f"Plantel: {tm['summary']}")

    env_imp = environment_impact_to_dict(decision)
    if env_imp:
        for side, data in env_imp.items():
            factors.append(
                f"Ambiente {data.get('team', side)}: ataque {data.get('attack_orig')}→{data.get('attack')}, "
                f"defesa {data.get('defense_orig')}→{data.get('defense')}"
            )

    stakes = decision.stakes_report
    if stakes and stakes.combined_note and stakes.combined_note != "Sem ajuste de necessidade":
        factors.append(f"Necessidades competitivas: {stakes.combined_note}")

    if decision.home_distortion and decision.home_distortion.total_distortion > 0.001:
        factors.append(
            f"Notícias {decision.home_distortion.team_name}: "
            f"ataque/distorsão {decision.home_distortion.total_distortion:.0%}"
        )
    if decision.away_distortion and decision.away_distortion.total_distortion > 0.001:
        factors.append(
            f"Notícias {decision.away_distortion.team_name}: "
            f"ataque/distorsão {decision.away_distortion.total_distortion:.0%}"
        )

    prog = getattr(item, "competition_progress", None) or {}
    if prog.get("progress_pct") is not None:
        factors.append(f"Progresso da época: {prog['progress_pct']}%")

    return factors


def build_ev_explanation(item: RankedMatch | RankedLiveMatch) -> dict | None:
    """Explicação legível do EV positivo — para diálogo na UI."""
    rec = item.decision.recommendation
    best = rec.best
    if not best or best.expected_value <= 0:
        return None

    lb = rec.lambda_breakdown
    alternatives = []
    for m in rec.all_markets[:5]:
        alternatives.append(
            {
                "market": m.label,
                "ev_pct": round(m.expected_value * 100, 1),
                "score": round(m.total_score, 3),
                "model_prob_pct": round(m.model_prob * 100, 1),
                "implied_prob_pct": round(m.implied_prob * 100, 1),
            }
        )

    headline = (
        f"O modelo estima {best.model_prob * 100:.1f}% de probabilidade em «{best.label}», "
        f"enquanto a odd {best.odd:.2f} implica apenas {best.implied_prob * 100:.1f}% — "
        f"essa diferença gera EV de {best.expected_value * 100:+.1f}%."
    )

    return {
        "market": best.label,
        "odd": round(best.odd, 2),
        "ev_pct": round(best.expected_value * 100, 1),
        "model_prob_pct": round(best.model_prob * 100, 1),
        "implied_prob_pct": round(best.implied_prob * 100, 1),
        "edge_pct": round(best.breakdown.edge * 100, 1),
        "headline": headline,
        "reasoning": list(best.reasoning),
        "score_breakdown": _score_breakdown_to_dict(best),
        "min_score": round(rec.min_score, 3),
        "should_bet": item.should_bet,
        "expected_goals": {
            "home": round(rec.home_lambda, 2),
            "away": round(rec.away_lambda, 2),
            "total": round(rec.home_lambda + rec.away_lambda, 2),
            "home_formula": lb.home_formula,
            "away_formula": lb.away_formula,
        },
        "context_factors": _context_factors_for_decision(item),
        "alternatives": alternatives,
        "summary": item.decision.summary,
    }


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
        "learning_tune": getattr(item, "learning_tune", None),
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
        "transfermarkt": item.transfermarkt,
        "motivation": item.motivation,
        "competition_progress": item.competition_progress,
        "block_reason": item.block_reason,
        "ev_explanation": build_ev_explanation(item),
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
        "ht_home_score": fx.ht_home_score,
        "ht_away_score": fx.ht_away_score,
        "kickoff": fx.kickoff,
        "fixture_id": fx.fixture_id,
        "source": fx.source,
        "source_label": LIVE_SOURCE_LABELS.get(fx.source, fx.source),
        "odds_source": odds_src,
        "odds_source_label": ODDS_SOURCE_LABELS.get(odds_src, odds_src) if odds_src else None,
        "odds_hint": fx.odds_hint or None,
        "espn_event_id": fx.espn_event_id or None,
        "espn_league_code": fx.espn_league_code or None,
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
        "learning_tune": getattr(item, "learning_tune", None),
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
            "motivation": getattr(item, "motivation", None),
            "ev_explanation": build_ev_explanation(item),
        }
    )
    return base


def attach_game_temperature(fixtures: list[dict]) -> list[dict]:
    """Ícone verde/amarelo/vermelho — sem API extra (golos + snapshots locais)."""
    from discovery.stats_snapshots import load_snapshot_hints_batch
    from live.match_intensity import temperature_from_fixture_dict

    ids = [int(f["fixture_id"]) for f in fixtures if f.get("fixture_id")]
    hints = load_snapshot_hints_batch(ids)
    out: list[dict] = []
    for fx in fixtures:
        row = dict(fx)
        fid = int(row.get("fixture_id") or 0)
        prev, last = hints.get(fid, (None, None))
        row["game_temperature"] = temperature_from_fixture_dict(
            row, snapshot_prev=prev, snapshot_last=last
        )
        out.append(row)
    return out


def live_scan_result_to_dict(
    result: LiveScanResult,
    *,
    last_tip: dict | None = None,
    live_source: str = "none",
) -> dict:
    best = result.best
    fixtures = attach_game_temperature([live_fixture_to_dict(f) for f in result.fixtures])
    ranked = [ranked_live_to_dict(r) for r in result.ranked]
    fx_by_key = {
        f"{f['home']}|{f['away']}": f.get("game_temperature")
        for f in fixtures
        if f.get("home") and f.get("away")
    }
    for row in ranked:
        key = f"{row.get('home')}|{row.get('away')}"
        if key in fx_by_key:
            row["game_temperature"] = fx_by_key[key]

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
        "ranked": ranked,
        "fixtures": fixtures,
    }
    if payload["best"]:
        bk = f"{payload['best'].get('home')}|{payload['best'].get('away')}"
        if bk in fx_by_key:
            payload["best"]["game_temperature"] = fx_by_key[bk]
    if last_tip:
        payload["last_tip"] = last_tip
    return payload