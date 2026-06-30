"""Backtest de prognósticos em competições — fases, duração e validação de EV."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from bankroll.competition_stake import is_stake_capped_competition
from bankroll.threshold import dynamic_min_score
from history.learning import _rate
from history.market_settlement import pnl_for_outcome, settle_market
from markets.evaluator import MarketEvaluator
from models.team_stats import MatchInput, TeamForm

from backtest.intervention import classify_odd_spread, intervention_thresholds, passes_intervention_gate
from backtest.runner import FLAT_STAKE, BacktestBet, _bet_public, _group_summary, _summarize_bucket
from backtest.tournament_elo import EloState, edition_team_form, elo_to_match_odds
from backtest.tournament_sources import TOURNAMENT_GOALS_AVG, TournamentMatch, load_tournament_matches

BASE_MIN_SCORE = 0.55


@dataclass
class _TeamEditionForm:
    gf: list[float] = None  # type: ignore
    ga: list[float] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.gf is None:
            self.gf = []
        if self.ga is None:
            self.ga = []


def _duration_bucket(match: TournamentMatch) -> str:
    """Janela dentro do torneio — semelhante ao que vivemos no presente."""
    gmin = min(match.home_games_before, match.away_games_before)
    if gmin <= 0:
        return "abertura"
    if gmin == 1:
        return "2.º jogo"
    if gmin == 2:
        return "3.º jogo grupos"
    return "fase final"


def _build_match_input(
    match: TournamentMatch,
    *,
    home_form: tuple[float, float, int, int, int, int],
    away_form: tuple[float, float, int, int, int, int],
    odds,
) -> MatchInput:
    hgf, hga, hg, hs, hc, hn = home_form
    agf, aga, ag, as_, ac, an = away_form
    league_avg = TOURNAMENT_GOALS_AVG.get(match.competition, 2.55)
    return MatchInput(
        home=TeamForm(
            name=match.home,
            goals_scored_avg=hgf,
            goals_conceded_avg=hga,
            games_played=hg,
            scored_in_last_n=hs,
            conceded_in_last_n=hc,
            last_n=hn,
        ),
        away=TeamForm(
            name=match.away,
            goals_scored_avg=agf,
            goals_conceded_avg=aga,
            games_played=ag,
            scored_in_last_n=as_,
            conceded_in_last_n=ac,
            last_n=an,
        ),
        odds=odds,
        league=match.edition,
        date=match.date,
        home_advantage=1.0 if match.neutral else 1.08,
        league_avg_goals=league_avg,
    )


def _evaluate_best(match_input: MatchInput, min_score: float) -> dict | None:
    ev = MarketEvaluator(min_score=min_score)
    rec = ev.evaluate(match_input)
    if not rec.best or not rec.should_bet or rec.best.expected_value <= 0:
        return None
    return {
        "market": rec.best.label,
        "odd": rec.best.odd,
        "score": rec.best.total_score,
        "ev_pct": rec.best.ev_percent,
        "all_ev_count": sum(1 for m in rec.all_markets if m.expected_value > 0),
    }


def _validate_assumptions(
    bets: list[BacktestBet],
    *,
    bets_fixed: list[BacktestBet],
    all_ev_rows: list[dict],
) -> list[dict]:
    """Pressupostos do motor — validados no histórico de competições."""
    assumptions: list[dict] = []

    def _assumption(aid: str, label: str, ok: bool | None, detail: str) -> dict:
        return {"id": aid, "label": label, "validated": ok, "detail": detail}

    def _roi(chunk: list[BacktestBet]) -> float | None:
        s = _summarize_bucket(chunk)
        return s.get("roi_pct")

    def _hit(chunk: list[BacktestBet]) -> float | None:
        s = _summarize_bucket(chunk)
        return s.get("hit_rate_pct")

    knockout = [b for b in bets if (b.signal or "").startswith("knockout")]
    group = [b for b in bets if (b.signal or "").startswith("group")]
    over_bets = [b for b in bets if "Over" in b.market]
    over_ko = [b for b in over_bets if b in knockout]
    over_gr = [b for b in over_bets if b in group]
    opening = [b for b in bets if b.scenario_id == "abertura"]
    with_dyn = bets
    without_dyn = bets_fixed
    tight = [b for b in bets if b.tier == "tight"]
    clear = [b for b in bets if b.tier == "clear_fav"]

    ev_positive_count = sum(1 for r in all_ev_rows if r["ev_pct"] > 0)
    assumptions.append(
        _assumption(
            "ev_exists",
            "O motor encontra EV+ no melhor mercado",
            ev_positive_count > 0,
            f"{ev_positive_count} jogos com EV+ no rank (amostra avaliada)",
        )
    )
    assumptions.append(
        _assumption(
            "ev_settled_profit",
            "Apostas filtradas (score+gate) têm ROI positivo",
            ((_roi(bets) or 0) > 0 and len(bets) >= 20) if len(bets) >= 20 else None,
            f"ROI {(_roi(bets) or 0):.1f}% em {len(bets)} entradas",
        )
    )

    if over_ko and over_gr and len(over_ko) >= 5 and len(over_gr) >= 5:
        assumptions.append(
            _assumption(
                "over_knockout_vs_group",
                "Over 2.5 rende melhor em eliminatórias que em grupos",
                (_roi(over_ko) or 0) > (_roi(over_gr) or 0),
                f"KO ROI {(_roi(over_ko) or 0):.1f}% vs grupos {(_roi(over_gr) or 0):.1f}%",
            )
        )
    else:
        assumptions.append(
            _assumption(
                "over_knockout_vs_group",
                "Over 2.5 rende melhor em eliminatórias que em grupos",
                None,
                "Amostra insuficiente de Over 2.5 por fase",
            )
        )

    if len(with_dyn) >= 15 and len(without_dyn) >= 15:
        assumptions.append(
            _assumption(
                "dynamic_min_score_helps",
                "min_score dinâmico (poucos jogos) melhora ROI vs baseline fixo",
                (_roi(with_dyn) or 0) >= (_roi(without_dyn) or 0),
                f"Com dinâmico {(_roi(with_dyn) or 0):.1f}% vs fixo {(_roi(without_dyn) or 0):.1f}%",
            )
        )
    else:
        assumptions.append(
            _assumption(
                "dynamic_min_score_helps",
                "min_score dinâmico (poucos jogos) melhora ROI vs baseline fixo",
                None,
                "Comparar com mais edições de torneio",
            )
        )

    if len(opening) >= 8:
        assumptions.append(
            _assumption(
                "opening_caution",
                "1.ª jornada do torneio é mais fraca para 1X2",
                (_hit(opening) or 100) < (_hit(bets) or 0),
                f"Abertura {(_hit(opening) or 0):.1f}% vs global {(_hit(bets) or 0):.1f}%",
            )
        )
    else:
        assumptions.append(
            _assumption(
                "opening_caution",
                "1.ª jornada do torneio é mais fraca para 1X2",
                None,
                f"Só {len(opening)} entradas na abertura",
            )
        )
    if tight and clear and len(tight) >= 8 and len(clear) >= 8:
        assumptions.append(
            _assumption(
                "tight_spread_underperforms",
                "Jogos equilibrados (spread baixo) exigem mais filtro",
                (_roi(tight) or 0) <= (_roi(clear) or 0) + 5,
                f"Tight ROI {(_roi(tight) or 0):.1f}% vs clear_fav {(_roi(clear) or 0):.1f}%",
            )
        )
    assumptions.append(
        _assumption(
            "stake_cap_competition",
            "Competições curtas são stake-capped no motor",
            is_stake_capped_competition("FIFA World Cup", "Group A"),
            "Mundial/Euro marcados como baixa confiança de amostra",
        )
    )
    return assumptions


def run_competition_backtest(
    *,
    csv_text: str | None = None,
    base_min_score: float = BASE_MIN_SCORE,
    use_dynamic_min_score: bool = True,
) -> dict[str, Any]:
    matches = load_tournament_matches(csv_text=csv_text)
    global_elo = EloState()
    edition_form: dict[tuple[str, str, str], _TeamEditionForm] = defaultdict(_TeamEditionForm)
    bets: list[BacktestBet] = []
    bets_fixed: list[BacktestBet] = []
    all_ev_rows: list[dict] = []
    skipped = 0

    for match in matches:
        form_key = (match.competition, str(match.year))
        hf = edition_form[(form_key[0], form_key[1], match.home)]
        af = edition_form[(form_key[0], form_key[1], match.away)]

        home_form = edition_team_form(
            team=match.home,
            goals_for=list(hf.gf),
            goals_against=list(hf.ga),
        )
        away_form = edition_team_form(
            team=match.away,
            goals_for=list(af.gf),
            goals_against=list(af.ga),
        )

        goals_avg = TOURNAMENT_GOALS_AVG.get(match.competition, 2.55)
        odds = elo_to_match_odds(
            global_elo,
            match.home,
            match.away,
            neutral=match.neutral,
            goals_avg=goals_avg,
        )
        mi = _build_match_input(match, home_form=home_form, away_form=away_form, odds=odds)

        dyn_min = dynamic_min_score(base_min_score, mi) if use_dynamic_min_score else base_min_score
        spread = classify_odd_spread(odds.home_win, odds.away_win)
        thresholds = intervention_thresholds(spread, base_min_score=dyn_min)

        best = _evaluate_best(mi, dyn_min)
        if best:
            all_ev_rows.append(best)
            gate = passes_intervention_gate(
                score=best["score"],
                ev_pct=best["ev_pct"],
                thresholds=thresholds,
            )
            if gate:
                outcome = settle_market(best["market"], match.fthg, match.ftag)
                pnl = pnl_for_outcome(outcome, best["odd"], FLAT_STAKE) or 0.0
                dur = _duration_bucket(match)
                bets.append(
                    BacktestBet(
                        mode="competition",
                        league=match.edition,
                        season=str(match.year),
                        date=match.date,
                        home=match.home,
                        away=match.away,
                        market=best["market"],
                        odd=best["odd"],
                        score=best["score"],
                        ev_pct=best["ev_pct"],
                        outcome=outcome,
                        pnl=pnl,
                        tier=thresholds.tier,
                        spread_ratio=spread.spread_ratio if spread else None,
                        pattern_score=1 if use_dynamic_min_score else 0,
                        scenario_id=dur,
                        signal=f"{match.phase}|{dur}",
                    )
                )
            else:
                skipped += 1
        else:
            skipped += 1

        # Baseline sem min_score dinâmico (comparar pressuposto)
        b = _evaluate_best(mi, base_min_score)
        if b:
            outcome = settle_market(b["market"], match.fthg, match.ftag)
            pnl = pnl_for_outcome(outcome, b["odd"], FLAT_STAKE) or 0.0
            bets_fixed.append(
                BacktestBet(
                    mode="competition_fixed",
                    league=match.edition,
                    season=str(match.year),
                    date=match.date,
                    home=match.home,
                    away=match.away,
                    market=b["market"],
                    odd=b["odd"],
                    score=b["score"],
                    ev_pct=b["ev_pct"],
                    outcome=outcome,
                    pnl=pnl,
                    tier=thresholds.tier,
                    spread_ratio=spread.spread_ratio if spread else None,
                    pattern_score=0,
                    scenario_id=_duration_bucket(match),
                    signal=f"{match.phase}|fixed",
                )
            )

        hf.gf.append(float(match.fthg))
        hf.ga.append(float(match.ftag))
        af.gf.append(float(match.ftag))
        af.ga.append(float(match.fthg))
        global_elo.update(match.home, match.away, match.fthg, match.ftag, neutral=match.neutral)

    by_phase = _group_summary(bets, lambda b: (b.signal or "").split("|")[0])
    by_duration = _group_summary(bets, lambda b: (b.signal or "").split("|")[-1])
    by_comp = _group_summary(bets, lambda b: b.league.split(" 20")[0] if " 20" in b.league else b.league)
    by_market = _group_summary(bets, lambda b: b.market)

    assumptions = _validate_assumptions(bets, bets_fixed=bets_fixed, all_ev_rows=all_ev_rows)

    return {
        "matches_parsed": len(matches),
        "editions": sorted({m.edition for m in matches}),
        "summary": _summarize_bucket(bets),
        "summary_fixed_min_score": _summarize_bucket(bets_fixed),
        "by_competition": by_comp,
        "by_phase": by_phase,
        "by_duration": by_duration,
        "by_market": by_market,
        "by_tier": _group_summary(bets, lambda b: b.tier),
        "skipped_gates": skipped,
        "assumptions": assumptions,
        "samples": [_bet_public(b) for b in bets[-30:]],
    }