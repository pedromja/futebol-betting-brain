"""Testes — backtest CSV, intervenção por odd spread e settlement IA."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.csv_match_builder import (
    RollingState,
    build_match_input,
    load_multi_league_matches,
    parse_csv_rows,
)
from backtest.intervention import classify_odd_spread, intervention_thresholds, passes_intervention_gate
from backtest.runner import run_backtest
from backtest.settlement import settle_ia_market


def _csv_block() -> str:
    rows = []
    teams = ("Benfica", "Sp Lisbon", "Porto", "Sp Braga", "Guimaraes")
    dates = [f"{(i % 28) + 1:02d}/08/24" for i in range(30)]
    for i, date in enumerate(dates):
        h, a = teams[i % 5], teams[(i + 2) % 5]
        fthg, ftag = (2, 1) if i % 3 else (1, 1)
        hthg, htag = (0, 1) if i == 11 else (1, 0)
        ch, ca = (1.45, 6.5) if h == "Benfica" else (2.8, 2.5)
        rows.append(
            f"{date},{h},{a},{fthg},{ftag},{hthg},{htag},"
            f"14,11,6,4,7,5,12,10,"
            f"{ch},3.6,{ca},1.72,2.05"
        )
    header = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG,"
        "HS,AS,HST,AST,HC,AC,HF,AF,"
        "B365CH,B365CD,B365CA,B365C>2.5,B365C<2.5"
    )
    return header + "\n" + "\n".join(rows)


def test_classify_odd_spread_tiers():
    tight = classify_odd_spread(2.55, 2.70)
    assert tight is not None
    assert tight.tier == "tight"
    clear = classify_odd_spread(1.40, 7.50)
    assert clear is not None
    assert clear.tier == "clear_fav"
    thr_clear = intervention_thresholds(clear)
    thr_tight = intervention_thresholds(tight)
    assert thr_clear.min_score < thr_tight.min_score
    assert thr_clear.interventive is True
    assert thr_tight.interventive is False


def test_intervention_gate_pattern():
    thr = intervention_thresholds(classify_odd_spread(1.5, 5.0))
    assert passes_intervention_gate(
        score=0.60,
        ev_pct=4.0,
        pattern_score=55.0,
        reaction_score=58.0,
        thresholds=thr,
        require_pattern=True,
    )
    tight_thr = intervention_thresholds(classify_odd_spread(2.5, 2.7))
    assert not passes_intervention_gate(
        score=0.56,
        ev_pct=4.0,
        pattern_score=55.0,
        reaction_score=58.0,
        thresholds=tight_thr,
        require_pattern=True,
    )


def test_settle_ia_extended_markets():
    assert settle_ia_market("Over 1.5", home_goals=1, away_goals=1, home_corners=5, away_corners=4) == "win"
    assert settle_ia_market("Cantos Over", home_goals=0, away_goals=0, home_corners=6, away_corners=5) == "win"
    assert settle_ia_market(
        "Vitória Favorito",
        home_goals=2,
        away_goals=1,
        home_corners=4,
        away_corners=3,
        favorite_side="home",
    ) == "win"


def test_rolling_match_input_requires_history():
    text = _csv_block()
    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    parsed = parse_csv_rows(list(reader), league_code="PPL", season="2425")
    rolling = RollingState()
    built = 0
    for m in parsed:
        mi = build_match_input(
            m,
            home_snap=rolling.snapshot(m.home, m.league_code),
            away_snap=rolling.snapshot(m.away, m.league_code),
        )
        if mi:
            built += 1
        rolling.record(m)
    assert built >= 1


def test_run_backtest_offline_csv():
    text = _csv_block()
    payload = run_backtest(
        leagues=("PPL",),
        seasons=("2425",),
        csv_by_key={("PPL", "2425"): text},
    )
    assert payload["config"]["matches_parsed"] == 30
    assert "prematch" in payload
    assert "live_ia" in payload
    assert "intervention_compare" in payload
    assert payload["combined"]["bets"] >= 0


def test_load_multi_league_from_injected_csv():
    text = _csv_block()
    matches = load_multi_league_matches(
        ("PPL",),
        ("2425",),
        csv_by_key={("PPL", "2425"): text},
    )
    assert len(matches) == 30
    assert matches[0].home in ("Benfica", "Sp Lisbon", "Porto", "Sp Braga", "Guimaraes")