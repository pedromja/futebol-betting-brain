"""Testes — backtest de competições internacionais."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.competition_runner import run_competition_backtest
from backtest.tournament_elo import EloState, elo_to_match_odds
from backtest.tournament_sources import load_tournament_matches


def _mini_international_csv() -> str:
    header = "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral"
    rows = [
        "2018-06-14,Russia,Saudi Arabia,5,0,FIFA World Cup,Moscow,Russia,FALSE",
        "2018-06-15,Egypt,Uruguay,0,1,FIFA World Cup,Ekaterinburg,Russia,FALSE",
        "2018-06-15,Portugal,Spain,3,3,FIFA World Cup,Sochi,Russia,FALSE",
        "2018-06-30,France,Argentina,4,3,FIFA World Cup,Kazan,Russia,FALSE",
        "2018-07-15,France,Croatia,4,2,FIFA World Cup,Moscow,Russia,FALSE",
        "2024-06-14,Germany,Scotland,5,1,UEFA Euro,Munich,Germany,FALSE",
        "2024-07-14,Spain,England,2,1,UEFA Euro,Berlin,Germany,FALSE",
    ]
    return header + "\n" + "\n".join(rows) + "\n"


def test_elo_generates_odds():
    st = EloState()
    st.ratings["Brazil"] = 1650
    st.ratings["Japan"] = 1420
    odds = elo_to_match_odds(st, "Brazil", "Japan", neutral=True)
    assert odds.home_win < odds.away_win
    assert odds.over_25 >= 1.05


def test_load_tournament_matches_mini():
    matches = load_tournament_matches(
        world_cup_years=(2018,),
        euro_years=(2024,),
        copa_years=(),
        csv_text=_mini_international_csv(),
    )
    assert len(matches) == 7
    assert any(m.phase == "knockout" for m in matches)


def test_run_competition_backtest_offline():
    payload = run_competition_backtest(csv_text=_mini_international_csv())
    assert payload["matches_parsed"] == 7
    assert "summary" in payload
    assert "assumptions" in payload
    assert len(payload["assumptions"]) >= 5