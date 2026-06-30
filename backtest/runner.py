"""Motor de backtest — pré-jogo + IA live parcial, multi-liga e tiers de odd spread."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from bots.live_context import attach_favorite_fields
from bots.market_match import market_matches_filter
from bots.pattern_discrepancy import attach_pattern_fields
from config.data_paths import BACKTEST_RESULTS_FILE, ensure_data_dir
from history.learning import _rate
from history.market_settlement import pnl_for_outcome, settle_market
from markets.evaluator import MarketEvaluator
from prematch.historical.types import TeamHistoricalProfile, VenueSlice

from backtest.csv_match_builder import (
    DEFAULT_LEAGUES,
    DEFAULT_SEASONS,
    ParsedMatch,
    RollingState,
    build_match_input,
    estimate_live_at_minute,
    load_multi_league_matches,
)
from backtest.intervention import (
    classify_odd_spread,
    intervention_thresholds,
    passes_intervention_gate,
)
from backtest.settlement import settle_ia_market

FLAT_STAKE = 10.0
LIVE_SIM_MINUTE = 58


@dataclass
class _VenueAcc:
    corners: list[float] = field(default_factory=list)
    goals: list[float] = field(default_factory=list)
    fouls: list[float] = field(default_factory=list)
    sot: list[float] = field(default_factory=list)

    def to_slice(self) -> VenueSlice:
        def avg(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        n = max(len(self.goals), len(self.corners))
        return VenueSlice(
            matches=n,
            corners_avg=avg(self.corners),
            goals_scored_avg=avg(self.goals),
            fouls_avg=avg(self.fouls),
            sot_avg=avg(self.sot),
        )


class _BacktestProfileStore:
    """Perfis rolling anti-leakage para pattern_discrepancy no backtest."""

    def __init__(self) -> None:
        self._home: dict[tuple[str, str], _VenueAcc] = defaultdict(_VenueAcc)
        self._away: dict[tuple[str, str], _VenueAcc] = defaultdict(_VenueAcc)

    def record(self, match: ParsedMatch) -> None:
        hk = (match.home, match.league_code)
        ak = (match.away, match.league_code)
        self._home[hk].corners.append(float(match.hc))
        self._home[hk].goals.append(float(match.fthg))
        self._home[hk].fouls.append(float(match.hf))
        self._home[hk].sot.append(float(match.hst))
        self._away[ak].corners.append(float(match.ac))
        self._away[ak].goals.append(float(match.ftag))
        self._away[ak].fouls.append(float(match.af))
        self._away[ak].sot.append(float(match.ast))

    def profile(self, team_name: str, *, league: str = "") -> TeamHistoricalProfile | None:
        from prematch.historical.sources import league_to_code

        code = league_to_code(league) or league
        hk = (team_name, code)
        ak = (team_name, code)
        home = self._home.get(hk)
        away = self._away.get(ak)
        if not home and not away:
            return None
        h_slice = home.to_slice() if home else VenueSlice()
        a_slice = away.to_slice() if away else VenueSlice()
        matches = h_slice.matches + a_slice.matches
        if matches < 5:
            return None
        return TeamHistoricalProfile(
            team=team_name,
            league=str(code),
            season="backtest",
            matches=matches,
            home=h_slice,
            away=a_slice,
        )


@dataclass
class BacktestBet:
    mode: str
    league: str
    season: str
    date: str
    home: str
    away: str
    market: str
    odd: float
    score: float
    ev_pct: float
    outcome: str
    pnl: float
    tier: str
    spread_ratio: float | None
    pattern_score: float | None = None
    reaction_score: float | None = None
    scenario_id: str | None = None
    signal: str | None = None


def _estimate_live_odd(market: str, match: ParsedMatch, favorite_side: str) -> float:
    m = market.lower()
    if "over 2.5" in m:
        return max(1.4, (match.over_25_odd or 1.85) * 0.82)
    if "over 1.5" in m:
        return max(1.2, (match.over_25_odd or 1.85) * 0.45)
    if "cantos over" in m:
        return 1.88
    if favorite_side == "home" and ("vitória casa" in m or "vitoria favorito" in m):
        return max(1.35, (match.home_odd or 2.0) * 1.55)
    if favorite_side == "away" and ("vitória fora" in m or "vitoria favorito" in m):
        return max(1.35, (match.away_odd or 2.0) * 1.55)
    if "dnb casa" in m:
        return max(1.25, (match.home_odd or 2.0) * 1.2)
    if "dnb fora" in m:
        return max(1.25, (match.away_odd or 2.0) * 1.2)
    return 1.9


def _pick_ia_market(analysis: dict, favorite_side: str) -> str | None:
    scenario_id = analysis.get("scenario_id")
    if analysis.get("scenario_play_allowed"):
        from bots.scenario_playbook import COMMUNITY_SCENARIOS

        play = next((p for p in COMMUNITY_SCENARIOS if p.id == scenario_id), None)
        if play:
            probe = {
                "favorite_side": favorite_side,
                "best_market": play.markets[0],
                "top_markets": [{"label": m} for m in play.markets],
            }
            for mkt in play.markets:
                probe["best_market"] = mkt
                if market_matches_filter(probe, mkt):
                    return mkt
            return play.markets[0]
    if analysis.get("pattern_alert"):
        return "Cantos Over"
    return None


def _favorite_losing_at_ht(match: ParsedMatch, favorite_side: str) -> bool:
    if match.hthg is None or match.htag is None:
        return False
    if favorite_side == "home":
        return match.hthg < match.htag
    if favorite_side == "away":
        return match.htag < match.hthg
    return False


def _summarize_bucket(bets: list[BacktestBet]) -> dict[str, Any]:
    wins = sum(1 for b in bets if b.outcome == "win")
    losses = sum(1 for b in bets if b.outcome == "loss")
    voids = sum(1 for b in bets if b.outcome == "void")
    decided = wins + losses
    stake = FLAT_STAKE * decided
    pnl = round(sum(b.pnl for b in bets if b.outcome in ("win", "loss")), 2)
    return {
        "bets": len(bets),
        "wins": wins,
        "losses": losses,
        "voids": voids,
        "samples": decided,
        "hit_rate_pct": _rate(wins, losses),
        "total_pnl": pnl,
        "roi_pct": round(100 * pnl / stake, 1) if stake > 0 else None,
    }


def _group_summary(bets: list[BacktestBet], key_fn) -> list[dict]:
    groups: dict[str, list[BacktestBet]] = defaultdict(list)
    for b in bets:
        groups[str(key_fn(b))].append(b)
    rows = []
    for key, chunk in groups.items():
        row = _summarize_bucket(chunk)
        row["key"] = key
        rows.append(row)
    rows.sort(key=lambda r: (-(r.get("samples") or 0), -(r.get("hit_rate_pct") or 0)))
    return rows


def run_backtest(
    *,
    leagues: tuple[str, ...] | list[str] | None = None,
    seasons: tuple[str, ...] | list[str] | None = None,
    csv_by_key: dict[tuple[str, str], str] | None = None,
    base_min_score: float = 0.55,
) -> dict[str, Any]:
    matches = load_multi_league_matches(leagues, seasons, csv_by_key=csv_by_key)
    rolling = RollingState()
    profiles = _BacktestProfileStore()
    prematch_bets: list[BacktestBet] = []
    live_bets: list[BacktestBet] = []
    skipped_no_odds = 0
    skipped_samples = 0

    class _MockSituationStore:
        def expected_for_live(self, *args, **kwargs):
            return None, "", "", 0

    mock_situation = _MockSituationStore()

    def _synthetic_deltas(match_dict: dict, parsed: ParsedMatch) -> dict[str, float]:
        side = str(match_dict.get("favorite_side") or "none")
        hthg = parsed.hthg or 0
        htag = parsed.htag or 0
        gh2 = max(0, parsed.fthg - hthg)
        ga2 = max(0, parsed.ftag - htag)
        if side == "home":
            press = gh2 >= ga2
            return {
                "corners": 1.5 if press else 0.0,
                "shots_on": 1.0 if press else 0.0,
                "xg": 0.15 if press else 0.0,
            }
        if side == "away":
            press = ga2 >= gh2
            return {
                "corners": 1.5 if press else 0.0,
                "shots_on": 1.0 if press else 0.0,
                "xg": 0.15 if press else 0.0,
            }
        return {"corners": 0.0, "shots_on": 0.0, "xg": 0.0}

    for match in matches:
        spread = classify_odd_spread(match.home_odd, match.away_odd)
        thresholds = intervention_thresholds(spread, base_min_score=base_min_score)

        home_snap = rolling.snapshot(match.home, match.league_code)
        away_snap = rolling.snapshot(match.away, match.league_code)
        mi = build_match_input(match, home_snap=home_snap, away_snap=away_snap)

        if mi:
            evaluator = MarketEvaluator(min_score=thresholds.min_score)
            rec = evaluator.evaluate(mi)
            if rec.best and rec.should_bet:
                gate_ok = passes_intervention_gate(
                    score=rec.best.total_score,
                    ev_pct=rec.best.ev_percent,
                    thresholds=thresholds,
                )
                if gate_ok:
                    label = rec.best.label
                    outcome = settle_market(label, match.fthg, match.ftag)
                    pnl = pnl_for_outcome(outcome, rec.best.odd, FLAT_STAKE) or 0.0
                    prematch_bets.append(
                        BacktestBet(
                            mode="prematch",
                            league=match.league_label,
                            season=match.season,
                            date=match.date,
                            home=match.home,
                            away=match.away,
                            market=label,
                            odd=rec.best.odd,
                            score=rec.best.total_score,
                            ev_pct=rec.best.ev_percent,
                            outcome=outcome,
                            pnl=pnl,
                            tier=thresholds.tier,
                            spread_ratio=spread.spread_ratio if spread else None,
                            signal="rank_ev",
                        )
                    )
        else:
            if not spread:
                skipped_no_odds += 1
            else:
                skipped_samples += 1

        if spread and match.hthg is not None and match.htag is not None:
            live_raw = estimate_live_at_minute(match, LIVE_SIM_MINUTE)
            live_raw.update(
                {
                    "home": match.home,
                    "away": match.away,
                    "league": match.league_label,
                    "odds_hint": {
                        "home_win": match.home_odd,
                        "draw": match.draw_odd,
                        "away_win": match.away_odd,
                    },
                    "best_ev_pct": 5.0,
                }
            )
            live_ctx = attach_favorite_fields(live_raw)
            fav_side = str(live_ctx.get("favorite_side") or "none")
            if fav_side != "none" and _favorite_losing_at_ht(match, fav_side):
                live_ctx["best_market"] = "Cantos Over"
                live_ctx["top_markets"] = [
                    {"label": "Cantos Over"},
                    {"label": "Over 1.5"},
                    {"label": "Over 2.5"},
                ]
                store = profiles
                deltas = _synthetic_deltas(live_ctx, match)
                with patch("bots.pattern_discrepancy.get_store", return_value=store), patch(
                    "prematch.historical.situation_store.get_situation_store",
                    return_value=mock_situation,
                ), patch("bots.pattern_discrepancy._record_track", return_value=1), patch(
                    "bots.scenario_engine._recent_fav_deltas", return_value=deltas
                ):
                    analysis = attach_pattern_fields(live_ctx)

                pattern_score = analysis.get("pattern_discrepancy_score")
                reaction_score = analysis.get("scenario_reaction_score")
                ia_signal = bool(analysis.get("pattern_alert")) or bool(
                    analysis.get("scenario_play_allowed")
                )
                if ia_signal:
                    gate_ok = passes_intervention_gate(
                        score=0.62 if analysis.get("scenario_play_allowed") else 0.58,
                        ev_pct=float(live_ctx.get("best_ev_pct") or 0),
                        pattern_score=float(pattern_score or 0),
                        reaction_score=float(reaction_score or 0),
                        thresholds=thresholds,
                        require_pattern=True,
                    )
                    if gate_ok:
                        market = _pick_ia_market(analysis, fav_side)
                        if market:
                            odd = _estimate_live_odd(market, match, fav_side)
                            outcome = settle_ia_market(
                                market,
                                home_goals=match.fthg,
                                away_goals=match.ftag,
                                home_corners=match.hc,
                                away_corners=match.ac,
                                favorite_side=fav_side,
                            )
                            pnl = pnl_for_outcome(outcome, odd, FLAT_STAKE) or 0.0
                            live_bets.append(
                                BacktestBet(
                                    mode="live_ia",
                                    league=match.league_label,
                                    season=match.season,
                                    date=match.date,
                                    home=match.home,
                                    away=match.away,
                                    market=market,
                                    odd=odd,
                                    score=float(reaction_score or pattern_score or 0),
                                    ev_pct=float(live_ctx.get("best_ev_pct") or 0),
                                    outcome=outcome,
                                    pnl=pnl,
                                    tier=thresholds.tier,
                                    spread_ratio=spread.spread_ratio,
                                    pattern_score=float(pattern_score) if pattern_score else None,
                                    reaction_score=float(reaction_score) if reaction_score else None,
                                    scenario_id=analysis.get("scenario_id"),
                                    signal="pattern" if analysis.get("pattern_alert") else "scenario",
                                )
                            )

        rolling.record(match)
        profiles.record(match)

    all_bets = prematch_bets + live_bets

    from backtest.competition_runner import run_competition_backtest

    competitions = run_competition_backtest(base_min_score=base_min_score)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "generated_at": now,
        "config": {
            "leagues": list(leagues or DEFAULT_LEAGUES),
            "seasons": list(seasons or DEFAULT_SEASONS),
            "matches_parsed": len(matches),
            "live_sim_minute": LIVE_SIM_MINUTE,
            "flat_stake": FLAT_STAKE,
            "base_min_score": base_min_score,
        },
        "coverage": {
            "skipped_no_odds": skipped_no_odds,
            "skipped_insufficient_form": skipped_samples,
        },
        "prematch": {
            **_summarize_bucket(prematch_bets),
            "by_league": _group_summary(prematch_bets, lambda b: b.league),
            "by_tier": _group_summary(prematch_bets, lambda b: b.tier),
            "by_market": _group_summary(prematch_bets, lambda b: b.market),
        },
        "live_ia": {
            **_summarize_bucket(live_bets),
            "by_league": _group_summary(live_bets, lambda b: b.league),
            "by_tier": _group_summary(live_bets, lambda b: b.tier),
            "by_market": _group_summary(live_bets, lambda b: b.market),
            "by_signal": _group_summary(live_bets, lambda b: b.signal or "—"),
        },
        "combined": _summarize_bucket(all_bets),
        "competitions": competitions,
        "intervention_compare": _intervention_compare(prematch_bets, live_bets),
        "samples": [
            _bet_public(b)
            for b in sorted(
                all_bets,
                key=lambda x: (x.date, x.league),
                reverse=True,
            )[:40]
        ],
    }


def _intervention_compare(
    prematch: list[BacktestBet],
    live: list[BacktestBet],
) -> list[dict]:
    """Compara desempenho por tier de spread — interventivo vs conservador."""
    rows = []
    for mode, bets in (("prematch", prematch), ("live_ia", live)):
        by_tier = _group_summary(bets, lambda b: b.tier)
        for row in by_tier:
            rows.append(
                {
                    "mode": mode,
                    "tier": row["key"],
                    "samples": row["samples"],
                    "hit_rate_pct": row["hit_rate_pct"],
                    "roi_pct": row["roi_pct"],
                    "total_pnl": row["total_pnl"],
                }
            )
    return rows


def _bet_public(b: BacktestBet) -> dict:
    return {
        "mode": b.mode,
        "league": b.league,
        "season": b.season,
        "date": b.date,
        "home": b.home,
        "away": b.away,
        "market": b.market,
        "odd": b.odd,
        "score": round(b.score, 3),
        "ev_pct": round(b.ev_pct, 1),
        "outcome": b.outcome,
        "pnl": b.pnl,
        "tier": b.tier,
        "spread_ratio": b.spread_ratio,
        "pattern_score": b.pattern_score,
        "reaction_score": b.reaction_score,
        "scenario_id": b.scenario_id,
        "signal": b.signal,
    }


def save_backtest_results(payload: dict, path=None) -> None:
    target = path or BACKTEST_RESULTS_FILE
    ensure_data_dir()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_backtest_results(path=None) -> dict | None:
    target = path or BACKTEST_RESULTS_FILE
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_backtest_payload(*, refresh: bool = False) -> dict:
    if refresh:
        payload = run_backtest()
        save_backtest_results(payload)
        return payload
    cached = load_backtest_results()
    if cached:
        return cached
    payload = run_backtest()
    save_backtest_results(payload)
    return payload