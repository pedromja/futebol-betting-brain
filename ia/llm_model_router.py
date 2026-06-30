"""Escolhe Grok 4.1 Fast vs 4.3 conforme complexidade do momento in-play."""

from __future__ import annotations

import os

MODEL_FAST = os.getenv("IA_LLM_MODEL_FAST", "grok-4-1-fast")
MODEL_DEEP = os.getenv("IA_LLM_MODEL_DEEP", "grok-4.3")

_HIGH_STAKES_EVENTS = frozenset(
    {"goal", "red_card", "yellow_card", "penalty", "substitution", "var"}
)
_ROUTINE_EVENTS = frozenset({"foul", "offside", "kickoff"})


def _recent_entries(context: dict) -> list[dict]:
    rows = context.get("recent_commentary") or []
    return [r for r in rows if isinstance(r, dict)]


def _key_events(context: dict) -> list[dict]:
    rows = context.get("key_events") or []
    return [r for r in rows if isinstance(r, dict)]


def _pattern_alert(context: dict) -> bool:
    pat = context.get("pattern_discrepancy") or {}
    if pat.get("pattern_alert"):
        return True
    try:
        score = float(pat.get("pattern_discrepancy_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return score >= 0.65


def _score_tuple(context: dict) -> tuple[int, int]:
    fx = context.get("fixture") or {}
    try:
        home = int(fx.get("home_score") or 0)
        away = int(fx.get("away_score") or 0)
    except (TypeError, ValueError):
        home = away = 0
    return home, away


def _event_types(entries: list[dict]) -> set[str]:
    return {
        str(e.get("event_type") or "").lower()
        for e in entries
        if e.get("event_type")
    }


def select_llm_model(context: dict) -> tuple[str, str]:
    """
    Devolve (model_slug, reason).
    Usa 4.3 em momentos críticos; 4.1 Fast no ritmo normal do jogo.
    """
    minute = int(context.get("minute") or 0)
    entries = _recent_entries(context)
    keys = _key_events(context)
    types_recent = _event_types(entries)
    types_keys = _event_types(keys)

    critical = (types_recent | types_keys) & _HIGH_STAKES_EVENTS
    if critical:
        return MODEL_DEEP, f"evento_critico:{sorted(critical)[0]}"

    if _pattern_alert(context):
        return MODEL_DEEP, "pattern_discrepancy"

    prematch = context.get("prematch_snapshot") or {}
    assumptions = context.get("prematch_assumptions") or prematch.get("prematch_assumptions") or {}
    if assumptions and minute >= 30:
        # Pré-jogo carregado + jogo já evoluiu — reavaliação mais profunda
        live_stats = context.get("live_stats") or {}
        home = (live_stats.get("home") or {}).get("possession_pct")
        away = (live_stats.get("away") or {}).get("possession_pct")
        fav = str(assumptions.get("favorite_side") or "").lower()
        if fav in ("home", "away") and home is not None and away is not None:
            fav_pct = home if fav == "home" else away
            if fav_pct is not None and fav_pct < 45:
                return MODEL_DEEP, "favorito_pre_a_perder_posse"

    if minute >= 75:
        return MODEL_DEEP, "fase_j4_final"

    # Início de cada janela IA — leitura mais cuidadosa
    phase = str(context.get("phase_window") or "")
    phase_edges = {"J1": 15, "J2": 30, "J3": 60, "J4": 75}
    edge = phase_edges.get(phase)
    if edge is not None and edge <= minute <= edge + 2:
        return MODEL_DEEP, f"entrada_{phase}"

    # Rajada de acção ofensiva
    shots = sum(1 for e in entries if e.get("event_type") in ("shot", "save", "corner", "goal"))
    if shots >= 3:
        return MODEL_DEEP, "rajada_ofensiva"

    saves = sum(1 for e in entries if e.get("event_type") == "save")
    if saves >= 2:
        return MODEL_DEEP, "sequencia_remates"

    if len(entries) >= 8 and not types_recent <= _ROUTINE_EVENTS:
        return MODEL_DEEP, "comentario_denso"

    home_g, away_g = _score_tuple(context)
    if home_g + away_g >= 3:
        return MODEL_DEEP, "jogo_aberto"

    # Ritmo normal — cantos isolados, faltas, posse estável
    return MODEL_FAST, "ritmo_normal"