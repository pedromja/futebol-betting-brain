"""Testes — Transfermarkt pré-jogo (4 pilares)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_cinfaes_maritimo_value_gap():
    from prematch.transfermarkt.analyzer import analyze_prematch

    insights = analyze_prematch(
        "Cinfães",
        "Marítimo",
        odds_hint={"home_win": 4.5, "draw": 3.6, "away_win": 1.75},
    )
    assert insights.data_available
    assert insights.value_gap is not None
    assert insights.value_gap.ratio < 1
    assert insights.value_gap.away_value_m > insights.value_gap.home_value_m


def test_tactical_and_referee_fixture():
    from prematch.transfermarkt.analyzer import analyze_prematch

    insights = analyze_prematch("Cinfães", "Marítimo")
    assert insights.tactical is not None
    assert insights.referee is not None
    assert insights.referee.referee == "António Nobre"


def test_absences_sporting():
    from prematch.transfermarkt.analyzer import analyze_prematch

    insights = analyze_prematch("Sporting", "Estoril")
    assert insights.away_absences is None or insights.home_absences is not None
    if insights.home_absences:
        assert insights.home_absences.total_impact > 0


def test_to_dict_serializable():
    from prematch.transfermarkt.analyzer import analyze_prematch

    payload = analyze_prematch("Benfica", "Sporting").to_dict()
    assert "value_gap" in payload
    assert "alignment" in payload
    assert payload["home"] == "Benfica"