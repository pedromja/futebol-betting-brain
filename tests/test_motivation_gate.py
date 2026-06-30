"""Testes — Motivation Gate e auditores."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prematch.auditors.gate import _score_votes, apply_motivation_stake, evaluate_motivation
from stakes.auto import is_knockout_context
from prematch.auditors.market_side import bet_side_from_market, vote_aligns_with_market
from prematch.auditors.table_stakes import _classify_stakes, _stakes_side
from prematch.auditors.types import AuditorVote, TableStakesInsight
from bankroll.ev_stake import suggest_stake


def test_bet_side_from_market():
    assert bet_side_from_market("Vitória Casa") == "home"
    assert bet_side_from_market("Vitória Fora") == "away"
    assert bet_side_from_market("Over 2.5") == "over"
    assert bet_side_from_market("Under 2.5") == "under"


def test_score_votes_two_categories():
    votes = [
        AuditorVote("strength_clubelo", "strength", "home", "Elo +90"),
        AuditorVote("table_stakes", "table", "home", "Luta pelo título"),
    ]
    score, indep, labels = _score_votes(votes, "home")
    assert score == 2
    assert indep == 2
    assert len(labels) == 2


def test_vote_aligns_with_market_home():
    assert vote_aligns_with_market("home", "home") is True
    assert vote_aligns_with_market("away", "home") is False


def test_apply_motivation_stake_scales_plan():
    plan = suggest_stake(0.10, bankroll=100)
    from prematch.auditors.types import MotivationReport

    report = MotivationReport(
        home="A",
        away="B",
        bet_market="Vitória Casa",
        bet_side="home",
        bet_ev=0.10,
        stake_multiplier=0.5,
        should_bet=True,
    )
    scaled = apply_motivation_stake(plan, report)
    assert scaled is not None
    assert scaled.bankroll_pct == plan.bankroll_pct * 0.5
    assert scaled.suggested_amount == plan.suggested_amount * 0.5


def test_table_stakes_classify_relegation():
    motivation, _ = _classify_stakes(17, 18, 22, 55)
    assert motivation == "relegation"


def test_table_stakes_side_relegation_home():
    home = TableStakesInsight("Casa", 17, 18, 22, "relegation", "descida")
    away = TableStakesInsight("Fora", 8, 18, 40, "midtable", "meio")
    assert _stakes_side(home, away) == "home"


def test_is_knockout_context_detects_round_of_16():
    assert is_knockout_context("FIFA World Cup", "Round of 16")
    assert is_knockout_context("Primeira Liga", "Jornada 12") is False


def test_evaluate_motivation_knockout_both_motivated():
    report = evaluate_motivation(
        "Brazil",
        "Japan",
        best_market="Vitória Casa",
        best_ev=0.15,
        league="FIFA World Cup",
        stage="Round of 32",
    )
    assert report.summary == "Ambas motivadas para progredir na prova."
    assert report.alignment == "strong"
    assert report.should_bet is True
    assert report.veto is False
    assert report.stake_multiplier == 1.0
    assert report.motivation_score >= 2


def test_availability_risk_vote_not_aligned():
    votes = [
        AuditorVote(
            "availability_bet_risk",
            "availability",
            "neutral",
            "Risco plantel",
            supports_market=False,
        ),
    ]
    score, indep, labels = _score_votes(votes, "home")
    assert score == 0
    assert labels == ["Risco plantel"]