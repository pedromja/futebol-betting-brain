"""Converte resultados do motor para JSON — camada fina, evolui com o projeto."""

from discovery.fixture_types import UpcomingFixture
from discovery.live_fixture_types import LiveFixture
from scanner.live_ranker import LiveScanResult, RankedLiveMatch
from scanner.ranker import RankedMatch, ScanResult


def upcoming_fixture_to_dict(fx: UpcomingFixture) -> dict:
    return {
        "home": fx.home,
        "away": fx.away,
        "league": fx.league,
        "kickoff": fx.kickoff,
        "stage": fx.stage,
        "source": fx.source,
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


def live_fixture_to_dict(fx: LiveFixture) -> dict:
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
        }
    )
    return base


def live_scan_result_to_dict(result: LiveScanResult) -> dict:
    best = result.best
    return {
        "scanned_at": result.scanned_at,
        "total_live": result.total_live,
        "total_analyzed": result.total_analyzed,
        "skipped": [
            {"match": label, "reason": reason}
            for label, reason in result.skipped
        ],
        "best": ranked_live_to_dict(best) if best else None,
        "ranked": [ranked_live_to_dict(r) for r in result.ranked],
        "fixtures": [live_fixture_to_dict(f) for f in result.fixtures],
    }