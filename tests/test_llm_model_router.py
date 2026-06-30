"""Testes — router Grok Fast vs Deep."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ia.llm_model_router import MODEL_DEEP, MODEL_FAST, select_llm_model


def _ctx(**overrides):
    base = {
        "minute": 22,
        "phase_window": "J1",
        "fixture": {"home_score": 0, "away_score": 0},
        "recent_commentary": [
            {"minute": 20, "event_type": "foul", "text": "Foul by X."},
            {"minute": 21, "event_type": "foul", "text": "Foul by Y."},
        ],
        "key_events": [],
        "pattern_discrepancy": {},
        "prematch_assumptions": {},
        "live_stats": {},
    }
    base.update(overrides)
    return base


def test_routine_uses_fast():
    model, reason = select_llm_model(_ctx())
    assert model == MODEL_FAST
    assert reason == "ritmo_normal"


def test_goal_uses_deep():
    ctx = _ctx(
        recent_commentary=[
            {"minute": 44, "event_type": "goal", "text": "Goal! France 1, Sweden 0."}
        ]
    )
    model, reason = select_llm_model(ctx)
    assert model == MODEL_DEEP
    assert reason.startswith("evento_critico:")


def test_j4_uses_deep():
    model, reason = select_llm_model(_ctx(minute=78, phase_window="J4"))
    assert model == MODEL_DEEP
    assert reason == "fase_j4_final"


def test_offensive_burst_uses_deep():
    ctx = _ctx(
        recent_commentary=[
            {"minute": 16, "event_type": "corner", "text": "Corner France."},
            {"minute": 17, "event_type": "save", "text": "Attempt saved."},
            {"minute": 17, "event_type": "shot", "text": "Attempt missed."},
            {"minute": 18, "event_type": "corner", "text": "Corner France."},
        ]
    )
    model, reason = select_llm_model(ctx)
    assert model == MODEL_DEEP
    assert reason in ("rajada_ofensiva", "sequencia_remates")