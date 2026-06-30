"""Testes — stake por EV e filtros de tempo live."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bankroll.competition_stake import is_stake_capped_competition, stake_cap_reason
from bankroll.ev_stake import ev_to_stake_level, suggest_stake
from live.tip_filters import live_tip_omit_reason
from live.types import LiveMatchState, MatchPeriod


def test_ev_stake_levels():
    assert ev_to_stake_level(0.01) == 1
    assert ev_to_stake_level(0.04) == 2
    assert ev_to_stake_level(0.12) >= 5
    assert ev_to_stake_level(0.22) == 10

    plan = suggest_stake(0.15, bankroll=100)
    assert 1 <= plan.level <= 10
    assert plan.suggested_amount is not None
    assert plan.suggested_amount > 0


def test_omit_first_half_40():
    state = LiveMatchState(
        home_score=0,
        away_score=1,
        minute=41,
        period=MatchPeriod.FIRST_HALF,
    )
    omit, reason = live_tip_omit_reason(state)
    assert omit is True
    assert "1.º tempo" in reason


def test_omit_second_half_last_5():
    state = LiveMatchState(
        home_score=1,
        away_score=1,
        minute=86,
        period=MatchPeriod.SECOND_HALF,
    )
    omit, reason = live_tip_omit_reason(state)
    assert omit is True
    assert "Fim do jogo" in reason


def test_allow_second_half_mid_game():
    state = LiveMatchState(
        home_score=1,
        away_score=0,
        minute=70,
        period=MatchPeriod.SECOND_HALF,
    )
    omit, _ = live_tip_omit_reason(state)
    assert omit is False


def test_allow_first_half_early():
    state = LiveMatchState(
        home_score=0,
        away_score=0,
        minute=25,
        period=MatchPeriod.FIRST_HALF,
    )
    omit, _ = live_tip_omit_reason(state)
    assert omit is False


def test_stake_cap_fifa_uefa_youth():
    assert is_stake_capped_competition("FIFA World Cup", "Round of 32")
    assert is_stake_capped_competition("UEFA Champions League", "")
    assert is_stake_capped_competition("International Friendly", "")
    assert is_stake_capped_competition("Amigável", "")
    assert is_stake_capped_competition("Spain U21", "Euro U21")
    assert not is_stake_capped_competition("Primeira Liga", "")

    plan = suggest_stake(0.22, bankroll=100, league="FIFA World Cup", stage="Round of 32")
    assert plan.level == 1
    assert plan.bankroll_pct == 0.5
    assert plan.suggested_amount == 0.5
    assert "juniores" not in plan.label.lower()
    assert "seleções" in plan.label.lower()

    u21 = suggest_stake(0.22, bankroll=100, league="Spain U21", stage="Euro U21")
    assert u21.level == 1
    assert "juniores" in u21.label.lower()

    domestic = suggest_stake(0.22, bankroll=100, league="Premier League")
    assert domestic.level == 10
    assert "seleções" not in domestic.label.lower()
    assert "juniores" not in domestic.label.lower()


def test_stake_cap_reason_terminology():
    assert stake_cap_reason("FIFA World Cup", "Round of 32") == "seleções"
    assert stake_cap_reason("Holanda", "Mundial") == "seleções"
    assert stake_cap_reason("Spain U21", "Euro U21") == "juniores"
    assert stake_cap_reason("International Friendly", "") == "amigável internacional"
    assert stake_cap_reason("UEFA Champions League", "") == "UEFA"
    assert stake_cap_reason("Primeira Liga", "") is None


def test_ev_shrink_with_small_sample():
    from markets.evaluator import MarketEvaluator
    from models.team_stats import MatchInput, MatchOdds, TeamForm

    match = MatchInput(
        home=TeamForm("Ivory Coast", 1.33, 0.67, games_played=3),
        away=TeamForm("Norway", 2.67, 2.33, games_played=3),
        odds=MatchOdds(
            home_win=3.55,
            draw=3.45,
            away_win=2.1,
            over_25=1.95,
            under_25=1.87,
            btts_yes=1.86,
            btts_no=1.74,
        ),
        league="FIFA World Cup",
        date="2026-06-30",
        league_avg_goals=2.65,
    )
    rec = MarketEvaluator(min_score=0.55).evaluate(match)
    best = rec.best
    assert best is not None
    assert best.label == "Vitória Casa"
    assert best.expected_value < 0.50
    assert best.model_prob < 0.45


def test_market_settlement():
    from history.market_settlement import settle_market

    assert settle_market("Over 2.5", 2, 1) == "win"
    assert settle_market("Under 2.5", 2, 1) == "loss"
    assert settle_market("BTTS Sim", 1, 1) == "win"
    assert settle_market("Vitória Casa", 2, 0) == "win"
    assert settle_market("Dupla Hipótese X2", 1, 1) == "win"


if __name__ == "__main__":
    test_ev_stake_levels()
    test_omit_first_half_40()
    test_omit_second_half_last_5()
    test_allow_second_half_mid_game()
    test_allow_first_half_early()
    test_market_settlement()
    print("OK — todos os testes passaram")