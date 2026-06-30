"""Contrasta narrativas de comunidade com o que acontece em campo — gate de apatia."""

from __future__ import annotations

from typing import Any

from bots.market_match import market_matches_filter
from bots.scenario_playbook import COMMUNITY_SCENARIOS, ScenarioPlay
from discovery.stats_snapshots import load_stats_history


SCENARIO_FIELDS = frozenset(
    {
        "scenario_id",
        "scenario_name",
        "scenario_active",
        "scenario_apathetic",
        "scenario_reaction_confirmed",
        "scenario_reaction_score",
        "scenario_play_allowed",
        "scenario_ev_aligned",
        "scenario_ev_positive",
        "scenario_field_gap",
        "scenario_community_thesis",
        "scenario_summary",
        "scenario_block_reason",
    }
)


def _minute(match: dict) -> int:
    try:
        return max(0, int(match.get("minute") or 0))
    except (TypeError, ValueError):
        return 0


def _favorite_side(match: dict) -> str:
    return str(match.get("favorite_side") or "none")


def _fav_metrics(match: dict) -> dict[str, float | int | None]:
    side = _favorite_side(match)
    if side == "home":
        return {
            "corners": match.get("home_corners"),
            "shots_on": match.get("home_shots_on"),
            "xg": match.get("home_xg"),
            "possession": match.get("home_possession_pct"),
            "goals": match.get("home_score"),
        }
    if side == "away":
        return {
            "corners": match.get("away_corners"),
            "shots_on": match.get("away_shots_on"),
            "xg": match.get("away_xg"),
            "possession": match.get("away_possession_pct"),
            "goals": match.get("away_score"),
        }
    return {"corners": None, "shots_on": None, "xg": None, "possession": None, "goals": None}


def _xg_diff_fav(match: dict) -> float | None:
    side = _favorite_side(match)
    if side == "home":
        diff = match.get("xg_diff")
    elif side == "away":
        hx = match.get("home_xg")
        ax = match.get("away_xg")
        if hx is not None and ax is not None:
            diff = float(ax) - float(hx)
        else:
            diff = match.get("xg_diff")
            if diff is not None:
                diff = -float(diff)
    else:
        return None
    return float(diff) if diff is not None else None


def _recent_fav_deltas(match: dict, *, window_minutes: int = 18) -> dict[str, float]:
    """Variação recente (snapshots) nos sinais do favorito vs scan anterior."""
    fid = match.get("fixture_id")
    fav = _fav_metrics(match)
    side = _favorite_side(match)
    if side not in ("home", "away"):
        return {"corners": 0.0, "shots_on": 0.0, "xg": 0.0}

    cur = {
        "corners": float(fav.get("corners") or 0),
        "shots_on": float(fav.get("shots_on") or 0),
        "xg": float(fav.get("xg") or 0),
    }
    if not fid:
        return {"corners": 0.0, "shots_on": 0.0, "xg": 0.0}

    history = load_stats_history(int(fid), limit=12)
    if not history:
        return {"corners": 0.0, "shots_on": 0.0, "xg": 0.0}

    cur_min = _minute(match)
    prev = None
    for row in reversed(history):
        row_min = row.get("minute")
        if row_min is None:
            continue
        try:
            row_min = int(row_min)
        except (TypeError, ValueError):
            continue
        if 0 < cur_min - row_min <= window_minutes:
            prev = row
            break
    if not prev and len(history) >= 1:
        prev = history[-1]

    def _get(row: dict, key: str) -> float:
        val = row.get(f"{side}_{key}")
        return float(val) if val is not None else 0.0

    return {
        "corners": cur["corners"] - _get(prev, "corners"),
        "shots_on": cur["shots_on"] - _get(prev, "shots_on"),
        "xg": cur["xg"] - _get(prev, "xg"),
    }


def _pick_scenario(match: dict, situation: str) -> ScenarioPlay | None:
    minute = _minute(match)
    fav_trouble = bool(match.get("favorite_losing_or_drawing"))
    total_fouls = match.get("total_fouls")

    candidates: list[ScenarioPlay] = []
    for play in COMMUNITY_SCENARIOS:
        if situation not in play.situations:
            continue
        if minute < play.minute_min or minute > play.minute_max:
            continue
        if play.requires_favorite_trouble and not fav_trouble:
            continue
        if play.id == "physical_game_cards":
            try:
                if int(total_fouls or 0) < 18:
                    continue
            except (TypeError, ValueError):
                continue
        if play.id == "xg_dominant_loser":
            xg_d = _xg_diff_fav(match)
            if xg_d is None or xg_d < 0.3:
                continue
        candidates.append(play)

    if not candidates:
        return None
    # Prioridade: cenário mais específico (janela mais estreita)
    candidates.sort(key=lambda p: (p.minute_max - p.minute_min, p.minute_min))
    return candidates[0]


def _dynamic_thresholds(match: dict, play: ScenarioPlay) -> tuple[int, int]:
    """Usa perfil condicional por janela quando disponível."""
    corners_thr = play.min_reaction_corners
    shots_thr = play.min_reaction_shots_on
    if str(match.get("pattern_source") or "") == "situation":
        try:
            exp_c = float(match.get("pattern_expected_corners") or 0)
            exp_s = float(match.get("pattern_expected_goals") or 0)
            if exp_c > 0:
                corners_thr = max(1, round(exp_c * 0.55))
            if exp_s > 0:
                shots_thr = max(play.min_reaction_shots_on, round(exp_s * 2))
        except (TypeError, ValueError):
            pass
    return corners_thr, shots_thr


def _reaction_score(
    match: dict,
    play: ScenarioPlay,
    fav: dict[str, float | int | None],
    deltas: dict[str, float],
) -> float:
    score = 0.0
    corners = int(fav.get("corners") or 0)
    shots_on = int(fav.get("shots_on") or 0)
    xg_d = _xg_diff_fav(match)
    poss = fav.get("possession")
    corners_thr, shots_thr = _dynamic_thresholds(match, play)

    if corners >= corners_thr:
        score += 22
    if shots_on >= shots_thr:
        score += 22
    if xg_d is not None and xg_d >= play.min_reaction_xg_diff:
        score += 18
    if poss is not None and float(poss) >= play.min_reaction_possession:
        score += 12

    if deltas.get("corners", 0) >= 1:
        score += 14
    if deltas.get("shots_on", 0) >= 1:
        score += 14
    if deltas.get("xg", 0) >= 0.12:
        score += 10

    trend = match.get("pattern_discrepancy_trend")
    disc = match.get("pattern_discrepancy_score")
    if trend == -1:
        score += 15
    if disc is not None and float(disc) < 35:
        score += 8

    return min(100.0, score)


def _is_apathetic(
    match: dict,
    play: ScenarioPlay,
    fav: dict[str, float | int | None],
    xg_d: float | None,
    reaction_score: float,
    deltas: dict[str, float],
) -> bool:
    corners = int(fav.get("corners") or 0)
    shots_on = int(fav.get("shots_on") or 0)

    apathy_corners = play.apathy_corners_max
    if str(match.get("pattern_source") or "") == "situation":
        try:
            exp_c = float(match.get("pattern_expected_corners") or 0)
            if exp_c >= 1.5:
                apathy_corners = max(play.apathy_corners_max, int(exp_c * 0.35))
        except (TypeError, ValueError):
            pass

    static_apathy = (
        corners <= apathy_corners
        and shots_on <= play.apathy_shots_on_max
        and (xg_d is None or xg_d <= play.apathy_xg_diff_max)
    )
    if str(match.get("pattern_source") or "") == "situation":
        try:
            gap = float(match.get("pattern_corners_gap_pct") or 0)
            if gap >= 60 and reaction_score < 40:
                static_apathy = True
        except (TypeError, ValueError):
            pass
    no_momentum = (
        deltas.get("corners", 0) <= 0
        and deltas.get("shots_on", 0) <= 0
        and deltas.get("xg", 0) < 0.08
    )
    return static_apathy and no_momentum and reaction_score < 45


def _field_gap(play: ScenarioPlay, fav: dict, xg_d: float | None, reaction_score: float) -> float:
    """Quão longe o campo está do que a comunidade espera (0=alinhado, 100=muito abaixo)."""
    gaps: list[float] = []
    corners = int(fav.get("corners") or 0)
    shots_on = int(fav.get("shots_on") or 0)

    if play.min_reaction_corners > 0:
        gaps.append(max(0.0, (play.min_reaction_corners - corners) / play.min_reaction_corners) * 100)
    if play.min_reaction_shots_on > 0:
        gaps.append(max(0.0, (play.min_reaction_shots_on - shots_on) / play.min_reaction_shots_on) * 100)
    if play.min_reaction_xg_diff > 0 and xg_d is not None:
        gaps.append(max(0.0, (play.min_reaction_xg_diff - xg_d) / play.min_reaction_xg_diff) * 100)

    base = sum(gaps) / len(gaps) if gaps else 0.0
    return round(min(100.0, max(base, 100.0 - reaction_score)), 1)


def _ev_check(match: dict, play: ScenarioPlay) -> tuple[bool, bool]:
    try:
        ev = float(match.get("best_ev_pct") or 0)
    except (TypeError, ValueError):
        ev = 0.0
    ev_positive = ev >= play.min_ev_pct
    ev_aligned = any(market_matches_filter(match, m) for m in play.markets)
    return ev_positive, ev_aligned


def _build_summary(
    match: dict,
    play: ScenarioPlay,
    *,
    apathetic: bool,
    reaction_confirmed: bool,
    reaction_score: float,
    field_gap: float,
    play_allowed: bool,
    block_reason: str,
    ev_positive: bool,
    ev_aligned: bool,
) -> str:
    team = match.get("pattern_team") or (
        match.get("home") if _favorite_side(match) == "home" else match.get("away")
    )
    minute = _minute(match)
    home = match.get("home") or "?"
    away = match.get("away") or "?"

    parts = [f"{home} vs {away}: [{play.name}] min {minute}."]
    if apathetic:
        parts.append(f"{team} apática — não seguir tese da comunidade ainda.")
    elif reaction_confirmed:
        parts.append(f"Reação confirmada (score {reaction_score:.0f}/100).")
    else:
        parts.append(f"Aguardar sinais de pressão (score {reaction_score:.0f}/100).")

    parts.append(f"Campo vs narrativa: Δ {field_gap:.0f}%.")
    if play_allowed:
        mkts = ", ".join(play.markets[:3])
        ev_bit = []
        if ev_positive:
            ev_bit.append("EV+")
        if ev_aligned:
            ev_bit.append("mercado alinhado")
        suffix = f" ({', '.join(ev_bit)})" if ev_bit else ""
        parts.append(f"Jogada permitida: {mkts}{suffix}.")
    elif block_reason:
        parts.append(block_reason)
    return " ".join(parts)


def compute_scenario_analysis(match: dict) -> dict[str, Any]:
    """Avalia cenário de comunidade vs campo; bloqueia se equipa apática."""
    situation = str(match.get("pattern_situation") or "")
    if not situation or _favorite_side(match) == "none":
        return {"scenario_active": False}

    minute = _minute(match)
    if minute < 15:
        return {"scenario_active": False}

    play = _pick_scenario(match, situation)
    if not play:
        return {"scenario_active": False, "scenario_id": None}

    fav = _fav_metrics(match)
    deltas = _recent_fav_deltas(match)
    xg_d = _xg_diff_fav(match)
    reaction_score = _reaction_score(match, play, fav, deltas)
    apathetic = _is_apathetic(match, play, fav, xg_d, reaction_score, deltas)
    reaction_confirmed = reaction_score >= 55 and not apathetic
    field_gap = _field_gap(play, fav, xg_d, reaction_score)
    ev_positive, ev_aligned = _ev_check(match, play)

    block_reason = ""
    if apathetic:
        block_reason = (
            "Equipa sem cantos/remates/xG recentes — esperar até demonstrar reação em campo."
        )
    elif not reaction_confirmed:
        block_reason = "Raciocínio da comunidade válido em teoria; aguardar confirmação live."
    elif not ev_positive and not ev_aligned:
        block_reason = "Reação visível mas motor sem EV+ no mercado do cenário."

    play_allowed = reaction_confirmed and not apathetic and (ev_positive or ev_aligned)

    summary = _build_summary(
        match,
        play,
        apathetic=apathetic,
        reaction_confirmed=reaction_confirmed,
        reaction_score=reaction_score,
        field_gap=field_gap,
        play_allowed=play_allowed,
        block_reason=block_reason,
        ev_positive=ev_positive,
        ev_aligned=ev_aligned,
    )

    return {
        "scenario_id": play.id,
        "scenario_name": play.name,
        "scenario_active": True,
        "scenario_apathetic": apathetic,
        "scenario_reaction_confirmed": reaction_confirmed,
        "scenario_reaction_score": round(reaction_score, 1),
        "scenario_play_allowed": play_allowed,
        "scenario_ev_aligned": ev_aligned,
        "scenario_ev_positive": ev_positive,
        "scenario_field_gap": field_gap,
        "scenario_community_thesis": play.community_thesis,
        "scenario_summary": summary,
        "scenario_block_reason": block_reason,
    }


def bot_conditions_need_scenario(conditions: list[dict]) -> bool:
    for cond in conditions or []:
        if str(cond.get("field") or "") in SCENARIO_FIELDS:
            return True
    return False