"""Testes — underdog com raça / galinha, significância e bots pré-jogo."""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bot, evaluate_bots_for_scan
from bots.ia_audit import extract_ia_context, is_ia_bot
from bots.live_enrich import enrich_prematch_ranked_for_bots
from bots.types import BotConfig
from bots.underdog_ia import compute_underdog_ia_analysis
from bots.underdog_table import (
    MIN_RATE_DELTA,
    UNDERDOG_PROGRESS_MAX,
    UNDERDOG_PROGRESS_MIN,
    _classify_scenario,
    _z_test_two_proportions,
    compute_underdog_analysis,
)


def test_z_test_significant_raca_profile():
    z, p = _z_test_two_proportions(19, 40, 8, 40)
    assert z > 1.96
    assert p < 0.05


def test_classify_raca_significant():
    scenario, sig, rate_s, rate_w, z = _classify_scenario(
        scored_strong=19,
        games_strong=40,
        scored_weak=8,
        games_weak=40,
    )
    assert scenario == "raca"
    assert sig is True
    assert rate_s >= 0.38
    assert rate_s - rate_w >= MIN_RATE_DELTA
    assert z > 1.96


def test_classify_galinha_significant():
    scenario, sig, rate_s, rate_w, z = _classify_scenario(
        scored_strong=6,
        games_strong=40,
        scored_weak=22,
        games_weak=40,
    )
    assert scenario == "galinha"
    assert sig is True
    assert rate_s <= 0.28
    assert rate_w - rate_s >= MIN_RATE_DELTA
    assert z < -1.96


def test_classify_insufficient_sample():
    scenario, sig, _, _, _ = _classify_scenario(
        scored_strong=1,
        games_strong=3,
        scored_weak=1,
        games_weak=3,
    )
    assert scenario == "insufficient"
    assert sig is False


def test_progress_window_constants():
    assert UNDERDOG_PROGRESS_MIN == 25.0
    assert UNDERDOG_PROGRESS_MAX == 85.0


def test_compute_underdog_ia_easy_score():
    match = {
        "underdog_scenario": "raca",
        "underdog_significant": True,
        "underdog_progress_ok": True,
        "underdog_favorite_hunt": True,
        "underdog_summary": "Team A vs Team B: raça.",
    }
    out = compute_underdog_ia_analysis(match)
    assert out["underdog_ia_active"] is True
    assert out["underdog_ia_alert"] == "easy_score"
    assert out["underdog_ia_play_allowed"] is True
    assert out["underdog_ia_favorite_hunt"] is True
    assert "Caça favoritos" in out["underdog_ia_summary"]


def test_compute_underdog_ia_hard_score():
    match = {
        "underdog_scenario": "galinha",
        "underdog_significant": True,
        "underdog_progress_ok": True,
        "underdog_summary": "Team A vs Team B: galinha.",
    }
    out = compute_underdog_ia_analysis(match)
    assert out["underdog_ia_alert"] == "hard_score"
    assert out["underdog_ia_play_allowed"] is True


def test_compute_underdog_ia_blocked_progress():
    match = {
        "underdog_scenario": "raca",
        "underdog_significant": True,
        "underdog_progress_ok": False,
    }
    out = compute_underdog_ia_analysis(match)
    assert out["underdog_ia_active"] is False
    assert out["underdog_ia_alert"] == "blocked_progress"
    assert out["underdog_ia_play_allowed"] is False


def test_compute_underdog_analysis_favorite_hunt():
    table = [
        {"position": 1, "team": {"name": "Favorito"}},
        {"position": 18, "team": {"name": "Underdog"}},
    ]
    profile = {
        "scenario": "raca",
        "significant": True,
        "rate_vs_strong_pct": 45.0,
        "rate_vs_weak_pct": 20.0,
        "games_vs_strong": 12,
        "games_vs_weak": 10,
        "z_score": 2.1,
        "p_value": 0.03,
    }
    match = {
        "home": "Underdog",
        "away": "Favorito",
        "league": "Primeira Liga",
        "competition_progress": {"progress_pct": 50},
    }

    with (
        patch("bots.underdog_table._progress_window", return_value=(True, 50.0)),
        patch("bots.underdog_table.fetch_standings", return_value=table),
        patch("bots.underdog_table._profile_for_team", return_value=profile),
        patch(
            "bots.underdog_table._underdog_from_standings",
            return_value=("home", "Underdog", 17),
        ),
    ):
        out = compute_underdog_analysis(match, football_data_key="fake")

    assert out["underdog_scenario"] == "raca"
    assert out["underdog_significant"] is True
    assert out["underdog_favorite_hunt"] is True
    assert out["underdog_progress_ok"] is True
    assert out["underdog_scoring_alert"] == "marca com facilidade vs favorito"


def test_evaluate_prematch_underdog_raca_bot():
    match = {
        "best_ev_pct": 5,
        "underdog_progress_ok": True,
        "underdog_scenario": "raca",
        "underdog_significant": True,
        "underdog_favorite_hunt": False,
    }
    bot = BotConfig(
        name="Raça",
        mode="prematch",
        active=True,
        template="prematch_underdog_raca",
        conditions=[
            {"field": "underdog_progress_ok", "operator": "eq", "value": True},
            {"field": "underdog_scenario", "operator": "eq", "value": "raca"},
            {"field": "underdog_significant", "operator": "eq", "value": True},
        ],
        min_ev_pct=3,
    )
    assert evaluate_bot(bot, match, mode="prematch")
    assert not evaluate_bot(bot, {**match, "underdog_scenario": "galinha"}, mode="prematch")
    assert not evaluate_bot(bot, {**match, "underdog_progress_ok": False}, mode="prematch")


def test_evaluate_prematch_favorite_hunt_bot():
    match = {
        "best_ev_pct": 6,
        "underdog_progress_ok": True,
        "underdog_favorite_hunt": True,
        "underdog_significant": True,
    }
    bot = BotConfig(
        name="Hunt",
        mode="prematch",
        active=True,
        template="prematch_underdog_favorite_hunt",
        conditions=[
            {"field": "underdog_favorite_hunt", "operator": "eq", "value": True},
            {"field": "underdog_significant", "operator": "eq", "value": True},
            {"field": "underdog_progress_ok", "operator": "eq", "value": True},
        ],
        min_ev_pct=4,
    )
    assert evaluate_bot(bot, match, mode="prematch")
    assert not evaluate_bot(bot, {**match, "underdog_significant": False}, mode="prematch")


def test_enrich_prematch_only_when_needed():
    ranked = [{"home": "A", "away": "B", "league": "Liga", "best_ev_pct": 5}]
    skip_bot = BotConfig(
        name="Over",
        mode="prematch",
        active=True,
        conditions=[{"field": "best_ev_pct", "operator": "gte", "value": 3}],
    )
    out = enrich_prematch_ranked_for_bots(ranked, bots=[skip_bot])
    assert out is ranked
    assert "underdog_scenario" not in out[0]


def test_enrich_prematch_attaches_underdog_fields():
    ranked = [{"home": "Underdog", "away": "Favorito", "league": "Primeira Liga", "best_ev_pct": 5}]
    bot = BotConfig(
        name="IA Raça",
        mode="prematch",
        active=True,
        conditions=[{"field": "underdog_ia_alert", "operator": "eq", "value": "easy_score"}],
    )
    enriched = {
        "underdog_scenario": "raca",
        "underdog_significant": True,
        "underdog_progress_ok": True,
        "underdog_ia_alert": "easy_score",
        "underdog_ia_play_allowed": True,
        "underdog_ia_active": True,
    }

    with patch("bots.live_enrich.attach_underdog_ia_fields", return_value={**ranked[0], **enriched}) as attach:
        out = enrich_prematch_ranked_for_bots(ranked, bots=[bot])

    attach.assert_called_once()
    assert out[0]["underdog_scenario"] == "raca"
    assert out[0]["underdog_ia_alert"] == "easy_score"


def test_evaluate_bots_for_scan_prematch_enriches():
    ranked = [{"home": "U", "away": "F", "league": "Liga", "best_ev_pct": 6}]
    bot = BotConfig(
        name="Raça",
        mode="prematch",
        active=True,
        conditions=[
            {"field": "underdog_scenario", "operator": "eq", "value": "raca"},
            {"field": "underdog_progress_ok", "operator": "eq", "value": True},
            {"field": "underdog_significant", "operator": "eq", "value": True},
        ],
        min_ev_pct=3,
    )
    enriched_match = {
        **ranked[0],
        "underdog_scenario": "raca",
        "underdog_progress_ok": True,
        "underdog_significant": True,
    }

    with patch("bots.live_enrich.enrich_prematch_ranked_for_bots", return_value=[enriched_match]):
        hits = evaluate_bots_for_scan(ranked, mode="prematch", bots=[bot])

    assert len(hits) == 1
    assert hits[0]["matches"][0]["underdog_scenario"] == "raca"


def test_ia_audit_extract_underdog_context():
    match = {
        "underdog_scenario": "raca",
        "underdog_significant": True,
        "underdog_favorite_hunt": True,
        "underdog_ia_alert": "easy_score",
        "underdog_summary": "Resumo underdog.",
        "underdog_ia_summary": "IA: mercados alinhados.",
    }
    ctx = extract_ia_context(match)
    assert ctx["underdog_scenario"] == "raca"
    assert ctx["underdog_favorite_hunt"] is True
    assert ctx["underdog_ia_alert"] == "easy_score"
    assert "Resumo" in ctx["underdog_summary"]


def test_is_ia_bot_prematch_underdog():
    assert is_ia_bot("prematch_underdog_raca_ia")
    assert is_ia_bot("prematch_underdog_galinha_ia")
    assert not is_ia_bot("prematch_underdog_raca")