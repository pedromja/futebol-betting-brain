"""Testes — motor IA autónomo (mock LLM)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.espn_commentary import phase_window_for_minute
from discovery.live_fixture_types import LiveFixture
from ia.autonomous_engine import analyze_game, build_llm_context
from ia.llm_client import normalize_llm_output
from ia.stake_policy import apply_stake_policy, to_public_tip
from ia.tip_gate import filter_tips


def _fx() -> LiveFixture:
    return LiveFixture(
        home="Ivory Coast",
        away="Norway",
        league="FIFA World Cup",
        home_score=1,
        away_score=2,
        minute=86,
        status_short="2H",
        espn_event_id="760490",
        espn_league_code="fifa.world",
        odds_hint={
            "home_win": 2.4,
            "draw": 3.2,
            "away_win": 1.9,
            "over_25": 2.1,
            "under_25": 1.75,
            "btts_yes": 1.8,
            "btts_no": 1.7,
        },
    )


def test_normalize_llm_output():
    raw = {
        "tips": [
            {
                "market": "Cantos Over",
                "confidence_pct": 80,
                "stake_raw": 7,
                "prematch_alignment": "divergent",
                "phase_window": "J4",
                "reasoning_pt": "Pressão final",
                "quote_en": "LATE CORNER",
            }
        ],
        "action_forecasts": [
            {
                "team": "Norway",
                "metric": "corners",
                "direction": "more",
                "horizon_minutes": 15,
                "confidence_pct": 70,
                "reasoning_pt": "Domínio",
                "quote_en": "75% possession",
            }
        ],
    }
    out = normalize_llm_output(raw)
    assert len(out["tips"]) == 1
    assert out["tips"][0]["prematch_alignment"] == "divergent"
    assert out["action_forecasts"][0]["direction"] == "more"


def test_stake_policy_divergent_caps():
    tip = apply_stake_policy(
        {
            "market": "Cantos Over",
            "confidence_pct": 80,
            "stake_raw": 6,
            "prematch_alignment": "divergent",
        }
    )
    assert tip["confidence_pct"] < 80
    assert tip["stake_raw"] <= 5.0
    pub = to_public_tip(tip)
    assert "stake_raw" not in pub
    assert pub["stake_hidden"] is True


def test_tip_gate_cooldown():
    tips = [{"market": "Cantos Over", "phase_window": "J4"}]
    recent = [{"market": "Cantos Over", "minute": 80}]
    accepted, rejected = filter_tips(tips, current_minute=86, recent_signals=recent)
    assert len(accepted) == 0
    assert rejected[0]["reject_reason"].startswith("cooldown")


def test_tip_gate_accepts_different_market_same_phase():
    tips = [{"market": "Vitória Fora", "phase_window": "J4"}]
    recent = [{"market": "Cantos Over", "minute": 80}]
    accepted, _ = filter_tips(tips, current_minute=86, recent_signals=recent)
    assert len(accepted) == 1


@patch("ia.autonomous_engine.fetch_espn_commentary")
@patch("ia.autonomous_engine.fetch_espn_live_stats")
@patch("ia.autonomous_engine.load_snapshot_by_espn_event")
@patch("ia.autonomous_engine.append_ia_signals")
def test_analyze_game_mock_llm(mock_append, mock_snap, mock_stats, mock_comm):
    from discovery.espn_commentary import EspnCommentaryFeed

    mock_snap.return_value = {
        "prematch_assumptions": {"favorite_side": "away", "expected_market": "Vitória Fora"},
        "best_ev": 0.11,
    }
    mock_stats.return_value = None
    mock_comm.return_value = EspnCommentaryFeed(
        espn_event_id="760490",
        espn_league_code="fifa.world",
        home="Ivory Coast",
        away="Norway",
        status="in",
        minute=86,
        minute_display="86'",
        fetched_at="t",
        entries=[],
        key_events=[],
    )

    class _FakeLlm:
        is_live = True

        def analyze_live(self, context):
            return {
                "tips": [
                    {
                        "market": "Vitória Fora",
                        "confidence_pct": 85,
                        "stake_raw": 4.5,
                        "prematch_alignment": "convergent",
                        "phase_window": "J4",
                        "reasoning_pt": "Norway controla",
                        "quote_en": "full control",
                        "timing_note": "agora",
                    }
                ],
                "action_forecasts": [],
                "llm_status": "ok",
            }

    with patch(
        "bots.pattern_discrepancy.attach_pattern_fields",
        side_effect=lambda m: m,
    ):
        payload = analyze_game(_fx(), llm=_FakeLlm(), force=True)

    assert payload["llm_status"] == "ok"
    assert len(payload["tips"]) == 1
    assert payload["tips"][0]["confidence_pct"] == 85
    assert payload["tips"][0].get("book_odd") is not None
    assert payload["tips"][0].get("ev_pct") is not None
    assert "stake_raw" not in payload["tips"][0]
    mock_append.assert_called_once()


def test_phase_window_86_is_j4():
    assert phase_window_for_minute(86) == "J4"