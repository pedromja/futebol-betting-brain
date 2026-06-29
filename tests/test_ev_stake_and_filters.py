"""Testes — stake por EV e filtros de tempo live."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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