"""Testes — regra de progresso do campeonato."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bankroll.competition_progress import (
    MIN_PROGRESS_PCT,
    MAX_PROGRESS_PCT,
    applies_progress_rule,
    parse_round_from_stage,
    _progress_from_standings,
)


def test_applies_only_domestic_leagues():
    assert applies_progress_rule("Primeira Liga", "")
    assert not applies_progress_rule("UEFA Champions League", "")
    assert not applies_progress_rule("FIFA World Cup", "Group A")


def test_parse_round_from_stage():
    assert parse_round_from_stage("Regular Season - 15") == 15
    assert parse_round_from_stage("Matchday 8") == 8
    assert parse_round_from_stage("15ª Jornada") == 15


def test_progress_from_standings_mid_season():
    table = [{"playedGames": 17} for _ in range(18)]
    pct, md, total = _progress_from_standings(table)
    assert total == 34
    assert abs(pct - 50.0) < 0.1
    assert md == 17


def test_block_thresholds():
    early_pct, _, _ = _progress_from_standings(
        [{"playedGames": 4} for _ in range(18)]
    )
    late_pct, _, _ = _progress_from_standings(
        [{"playedGames": 31} for _ in range(18)]
    )
    mid_pct, _, _ = _progress_from_standings(
        [{"playedGames": 17} for _ in range(18)]
    )
    assert early_pct < MIN_PROGRESS_PCT
    assert late_pct > MAX_PROGRESS_PCT
    assert MIN_PROGRESS_PCT <= mid_pct <= MAX_PROGRESS_PCT