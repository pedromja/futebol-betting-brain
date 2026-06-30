"""Compara ritmo live com padrão histórico da equipa — alerta de discrepância crescente."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config.data_paths import PATTERN_TRACK_LOG, ensure_data_dir
from prematch.historical.situation_store import get_situation_store
from prematch.historical.store import get_store
from prematch.historical.types import TeamHistoricalProfile, VenueSlice

# Ritmo extra quando o favorito está em apuros (pressão típica pós-HT)
SITUATION_MULTIPLIERS: dict[str, dict[str, float]] = {
    "fav_losing_post_ht": {"corners": 1.45, "goals": 1.35, "cards": 1.25, "fouls": 1.2},
    "fav_losing_ht": {"corners": 1.35, "goals": 1.25, "cards": 1.15, "fouls": 1.15},
    "fav_losing": {"corners": 1.3, "goals": 1.2, "cards": 1.12, "fouls": 1.1},
    "fav_drawing": {"corners": 1.15, "goals": 1.1, "cards": 1.05, "fouls": 1.05},
    "fav_winning": {"corners": 0.85, "goals": 0.9, "cards": 0.95, "fouls": 0.95},
    "neutral": {"corners": 1.0, "goals": 1.0, "cards": 1.0, "fouls": 1.0},
}

SECOND_HALF_SHARE = 0.52
LEAGUE_CARDS_PER_MATCH = 2.4
LEAGUE_FOULS_PER_MATCH = 22.0

PATTERN_FIELDS = frozenset(
    {
        "pattern_has_profile",
        "pattern_team",
        "pattern_situation",
        "pattern_discrepancy_score",
        "pattern_discrepancy_trend",
        "pattern_corners_gap",
        "pattern_corners_gap_pct",
        "pattern_goals_gap",
        "pattern_goals_gap_pct",
        "pattern_cards_gap",
        "pattern_cards_gap_pct",
        "pattern_expected_corners",
        "pattern_expected_goals",
        "pattern_expected_cards",
        "pattern_alert",
        "pattern_summary",
        "pattern_window",
        "pattern_source",
        "pattern_hist_situation",
        "pattern_situation_sample",
    }
)

WINDOW_LABELS = {
    "first_half": "1.º tempo",
    "post_ht_0_15": "pós-HT 46–60'",
    "post_ht_16_30": "pós-HT 61–75'",
    "post_ht_31_45": "pós-HT 76–90'",
}


def _minute(match: dict) -> int:
    try:
        return max(0, int(match.get("minute") or 0))
    except (TypeError, ValueError):
        return 0


def _scores(match: dict) -> tuple[int | None, int | None]:
    hs, aw = match.get("home_score"), match.get("away_score")
    if hs is not None and aw is not None:
        try:
            return int(hs), int(aw)
        except (TypeError, ValueError):
            pass
    score = str(match.get("score") or "")
    if "-" in score:
        parts = score.split("-", 1)
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except ValueError:
            pass
    return None, None


def _ht_scores(match: dict) -> tuple[int | None, int | None]:
    ht_h, ht_a = match.get("ht_home_score"), match.get("ht_away_score")
    try:
        ht_h = int(ht_h) if ht_h is not None else None
    except (TypeError, ValueError):
        ht_h = None
    try:
        ht_a = int(ht_a) if ht_a is not None else None
    except (TypeError, ValueError):
        ht_a = None
    return ht_h, ht_a


def _favorite_losing_at_ht(match: dict) -> bool:
    side = str(match.get("favorite_side") or "none")
    if side == "none":
        return False
    ht_h, ht_a = _ht_scores(match)
    if ht_h is None or ht_a is None:
        return False
    if side == "home":
        return ht_h < ht_a
    return ht_a < ht_h


def detect_situation(match: dict) -> str:
    """Estado contextual para ajustar expectativas históricas."""
    status = str(match.get("match_status") or match.get("status") or "").upper()
    minute = _minute(match)
    fav = str(match.get("favorite_status") or "unknown")

    if fav == "losing":
        if status == "HT" or match.get("is_halftime"):
            return "fav_losing_ht"
        if minute > 45 and _favorite_losing_at_ht(match):
            if minute <= 76:
                return "fav_losing_post_ht"
        return "fav_losing"
    if fav == "drawing":
        return "fav_drawing"
    if fav == "winning":
        return "fav_winning"
    return "neutral"


def _venue_slice(profile: TeamHistoricalProfile, *, is_home: bool) -> VenueSlice:
    return profile.home if is_home else profile.away


def _pace_fraction(match: dict, situation: str) -> float:
    minute = _minute(match)
    if minute <= 0:
        return 0.0
    if situation == "fav_losing_post_ht" and minute > 45:
        return min((minute - 45) / 45.0, 1.0) * SECOND_HALF_SHARE
    return min(minute / 90.0, 1.0)


def _mult(situation: str, metric: str) -> float:
    return SITUATION_MULTIPLIERS.get(situation, SITUATION_MULTIPLIERS["neutral"]).get(metric, 1.0)


def _expected_cards(slice_: VenueSlice, pace: float, situation: str) -> float:
    foul_rate = slice_.fouls_avg or LEAGUE_FOULS_PER_MATCH
    base = LEAGUE_CARDS_PER_MATCH * (foul_rate / LEAGUE_FOULS_PER_MATCH)
    return base * pace * _mult(situation, "cards")


def _expected_cards_from_fouls(fouls_avg: float) -> float:
    if fouls_avg <= 0:
        return LEAGUE_CARDS_PER_MATCH * 0.25
    return LEAGUE_CARDS_PER_MATCH * (fouls_avg / LEAGUE_FOULS_PER_MATCH)


def _season_fallback_expected(
    slice_: VenueSlice,
    match: dict,
    situation: str,
) -> tuple[float, float, float]:
    pace = _pace_fraction(match, situation)
    exp_corners = slice_.corners_avg * pace * _mult(situation, "corners")
    exp_goals = slice_.goals_scored_avg * pace * _mult(situation, "goals")
    exp_cards = _expected_cards(slice_, pace, situation)
    return exp_corners, exp_goals, exp_cards


def _resolve_expected(
    match: dict,
    *,
    team_name: str,
    league: str,
    venue: str,
    situation: str,
    slice_: VenueSlice,
) -> tuple[float, float, float, str, str, str, int]:
    """Prioridade: perfil condicional por janela → fallback época."""
    minute = _minute(match)
    sit_store = get_situation_store()
    sit_metrics, window, hist_sit, sample = sit_store.expected_for_live(
        team_name,
        league=league,
        venue=venue,
        live_situation=situation,
        minute=minute,
        fav_losing_at_ht=_favorite_losing_at_ht(match),
    )

    if sit_metrics and sample >= 3:
        exp_corners = sit_metrics.corners_avg
        exp_goals = sit_metrics.goals_scored_avg
        exp_cards = _expected_cards_from_fouls(sit_metrics.fouls_avg)
        return exp_corners, exp_goals, exp_cards, "situation", window, hist_sit, sample

    c, g, cards = _season_fallback_expected(slice_, match, situation)
    return c, g, cards, "season", "", "", slice_.matches


@dataclass
class MetricGap:
    expected: float
    actual: float
    gap: float
    gap_pct: float


def _metric_gap(expected: float, actual: float | None) -> MetricGap:
    act = float(actual or 0)
    exp = max(expected, 0.05)
    gap = round(exp - act, 2)
    gap_pct = round(max(0.0, gap / exp) * 100.0, 1)
    return MetricGap(expected=round(exp, 2), actual=act, gap=gap, gap_pct=gap_pct)


def _team_actuals(match: dict, *, is_favorite_home: bool) -> dict[str, float | None]:
    if is_favorite_home:
        return {
            "corners": match.get("home_corners"),
            "goals": match.get("home_score"),
            "cards": _sum_cards(match, home=True),
        }
    return {
        "corners": match.get("away_corners"),
        "goals": match.get("away_score"),
        "cards": _sum_cards(match, home=False),
    }


def _sum_cards(match: dict, *, home: bool) -> int | None:
    y = match.get("home_yellow_cards") if home else match.get("away_yellow_cards")
    r = match.get("home_red_cards") if home else match.get("away_red_cards")
    if y is None and r is None:
        return None
    return int(y or 0) + int(r or 0)


def _aggregate_score(gaps: list[MetricGap]) -> float:
    if not gaps:
        return 0.0
    weights = [0.4, 0.35, 0.25][: len(gaps)]
    total_w = sum(weights)
    score = sum(g.gap_pct * w for g, w in zip(gaps, weights)) / total_w
    return round(min(100.0, score), 1)


def _load_last_track(fixture_key: str) -> dict | None:
    path = PATTERN_TRACK_LOG
    if not path.exists():
        return None
    last: dict | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines[-400:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("fixture_key") or "") == fixture_key:
            last = row
    return last


def _record_track(fixture_key: str, payload: dict) -> int:
    """Grava snapshot e devolve tendência: -1 melhora, 0 estável, 1 piora."""
    ensure_data_dir()
    prev = _load_last_track(fixture_key)
    score = float(payload.get("pattern_discrepancy_score") or 0)
    trend = 0
    if prev is not None:
        prev_score = float(prev.get("pattern_discrepancy_score") or 0)
        delta = score - prev_score
        if delta >= 4.0:
            trend = 1
        elif delta <= -4.0:
            trend = -1

    row = {
        "fixture_key": fixture_key,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pattern_discrepancy_score": score,
        "pattern_discrepancy_trend": trend,
        **{k: payload.get(k) for k in ("minute", "pattern_situation", "pattern_team")},
    }
    with PATTERN_TRACK_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return trend


def _build_summary(
    match: dict,
    *,
    team: str,
    situation: str,
    minute: int,
    corners: MetricGap,
    goals: MetricGap,
    cards: MetricGap,
    trend: int,
    pattern_source: str = "season",
    pattern_window: str = "",
    hist_situation: str = "",
    sample: int = 0,
) -> str:
    sit_labels = {
        "fav_losing_post_ht": "favorito a perder ao intervalo — janela 2.ª parte",
        "fav_losing_ht": "favorito a perder no intervalo",
        "fav_losing": "favorito a perder",
        "fav_drawing": "favorito só empata",
        "fav_winning": "favorito a ganhar",
        "neutral": "jogo equilibrado",
    }
    sit = sit_labels.get(situation, situation)
    trend_txt = {1: "discrepância a aumentar", 0: "discrepância estável", -1: "ritmo a recuperar"}.get(
        trend, ""
    )
    src_txt = ""
    if pattern_source == "situation" and pattern_window:
        win = WINDOW_LABELS.get(pattern_window, pattern_window)
        src_txt = f" Histórico condicional ({hist_situation}, {win}, n={sample})."

    parts = [
        f"{team}: ao min {minute} ({sit}).{src_txt}",
        f"Cantos {int(corners.actual)}/{corners.expected:.1f} esperados (Δ {corners.gap_pct:.0f}%).",
        f"Golos {int(goals.actual)}/{goals.expected:.1f} esperados (Δ {goals.gap_pct:.0f}%).",
    ]
    if cards.expected > 0.1:
        parts.append(
            f"Cartões {int(cards.actual)}/{cards.expected:.1f} esperados (Δ {cards.gap_pct:.0f}%)."
        )
    if trend_txt:
        parts.append(trend_txt + ".")
    home = match.get("home") or "?"
    away = match.get("away") or "?"
    return f"{home} vs {away}: " + " ".join(parts)


def compute_pattern_analysis(match: dict) -> dict[str, Any]:
    """Calcula campos de discrepância histórica vs live para o favorito (ou equipa focada)."""
    minute = _minute(match)
    if minute < 15:
        return {"pattern_has_profile": False}

    side = str(match.get("favorite_side") or "none")
    if side == "none":
        return {"pattern_has_profile": False}

    situation = detect_situation(match)
    store = get_store()
    is_home = side == "home"
    team_name = str(match.get("home") if is_home else match.get("away") or "")
    league = str(match.get("league") or "")

    profile = store.profile(team_name, league=league)
    slice_ = _venue_slice(profile, is_home=is_home) if profile else VenueSlice()
    actuals = _team_actuals(match, is_favorite_home=is_home)
    venue = "home" if is_home else "away"

    exp_corners, exp_goals, exp_cards, pattern_source, pattern_window, hist_sit, sample = (
        _resolve_expected(
            match,
            team_name=team_name,
            league=league,
            venue=venue,
            situation=situation,
            slice_=slice_,
        )
    )

    has_situation = pattern_source == "situation" and sample >= 3
    has_season = bool(profile and profile.matches >= 5 and slice_.matches >= 3)
    if not has_situation and not has_season:
        return {"pattern_has_profile": False, "pattern_team": team_name, "pattern_situation": situation}

    corners_gap = _metric_gap(exp_corners, actuals["corners"])
    goals_gap = _metric_gap(exp_goals, actuals["goals"])
    cards_gap = _metric_gap(exp_cards, actuals["cards"])

    gaps = [corners_gap, goals_gap]
    if actuals["cards"] is not None:
        gaps.append(cards_gap)

    score = _aggregate_score(gaps)
    fixture_key = (
        f"{match.get('fixture_id')}|{match.get('espn_event_id')}|{match.get('home')}|{match.get('away')}"
    )
    trend = _record_track(
        fixture_key,
        {
            "pattern_discrepancy_score": score,
            "minute": minute,
            "pattern_situation": situation,
            "pattern_team": team_name,
        },
    )

    alert = score >= 50.0 and trend >= 0 and situation in (
        "fav_losing",
        "fav_losing_ht",
        "fav_losing_post_ht",
        "fav_drawing",
    )

    summary = _build_summary(
        match,
        team=team_name,
        situation=situation,
        minute=minute,
        corners=corners_gap,
        goals=goals_gap,
        cards=cards_gap,
        trend=trend,
        pattern_source=pattern_source,
        pattern_window=pattern_window,
        hist_situation=hist_sit,
        sample=sample,
    )

    return {
        "pattern_has_profile": True,
        "pattern_team": team_name,
        "pattern_situation": situation,
        "pattern_window": pattern_window or None,
        "pattern_source": pattern_source,
        "pattern_hist_situation": hist_sit or None,
        "pattern_situation_sample": sample if pattern_source == "situation" else None,
        "pattern_discrepancy_score": score,
        "pattern_discrepancy_trend": trend,
        "pattern_expected_corners": corners_gap.expected,
        "pattern_expected_goals": goals_gap.expected,
        "pattern_expected_cards": cards_gap.expected,
        "pattern_corners_gap": corners_gap.gap,
        "pattern_corners_gap_pct": corners_gap.gap_pct,
        "pattern_goals_gap": goals_gap.gap,
        "pattern_goals_gap_pct": goals_gap.gap_pct,
        "pattern_cards_gap": cards_gap.gap,
        "pattern_cards_gap_pct": cards_gap.gap_pct,
        "pattern_alert": alert,
        "pattern_summary": summary,
    }


def attach_pattern_fields(match: dict) -> dict:
    """Anexa análise de padrão + cenários comunidade ao dict do jogo."""
    from bots.scenario_engine import SCENARIO_FIELDS, compute_scenario_analysis

    out = {**match}
    out.update(compute_pattern_analysis(out))
    out.update(compute_scenario_analysis(out))
    return out


def bot_conditions_need_pattern(conditions: list[dict]) -> bool:
    from bots.scenario_engine import SCENARIO_FIELDS, bot_conditions_need_scenario

    for cond in conditions or []:
        field = str(cond.get("field") or "")
        if field in PATTERN_FIELDS or field in SCENARIO_FIELDS:
            return True
    return bot_conditions_need_scenario(conditions)