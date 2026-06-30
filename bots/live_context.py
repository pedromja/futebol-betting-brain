"""Contexto live derivado de odds ESPN/API e resultado — sem pedidos extra."""

from __future__ import annotations

from typing import Any


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


def _odds_hint(match: dict) -> dict:
    hint = match.get("odds_hint")
    if isinstance(hint, dict) and hint:
        return hint
    top = match.get("top_markets") or []
    for row in top:
        label = str(row.get("label") or row.get("market") or "").lower()
        if "vitória casa" in label or label == "home":
            return {
                "home_win": row.get("odd"),
                "draw": None,
                "away_win": None,
            }
    return {}


def favorite_side_from_odds(odds: dict) -> str:
    try:
        hw = float(odds.get("home_win") or 0)
        aw = float(odds.get("away_win") or 0)
    except (TypeError, ValueError):
        return "none"
    if hw <= 0 or aw <= 0:
        return "none"
    if abs(hw - aw) < 0.08:
        return "none"
    return "home" if hw < aw else "away"


def attach_favorite_fields(match: dict) -> dict:
    out = {**match}
    odds = _odds_hint(match)
    side = favorite_side_from_odds(odds)
    hs, aw = _scores(match)

    out["favorite_side"] = side
    out["home_is_favorite"] = side == "home"
    out["away_is_favorite"] = side == "away"
    out["prematch_home_odd"] = odds.get("home_win")
    out["prematch_away_odd"] = odds.get("away_win")
    out["prematch_draw_odd"] = odds.get("draw")

    if hs is None or aw is None or side == "none":
        out["favorite_status"] = "unknown"
        out["favorite_losing_or_drawing"] = False
        out["favorite_winning"] = False
        out["goal_diff"] = None
        out["favorite_goal_diff"] = None
        return attach_live_timing_fields(out)

    diff = hs - aw
    out["goal_diff"] = diff
    if side == "home":
        fav_diff = diff
    else:
        fav_diff = -diff

    out["favorite_goal_diff"] = fav_diff
    if fav_diff > 0:
        status = "winning"
    elif fav_diff == 0:
        status = "drawing"
    else:
        status = "losing"

    out["favorite_status"] = status
    out["favorite_losing_or_drawing"] = status in ("losing", "drawing")
    out["favorite_winning"] = status == "winning"
    return attach_live_timing_fields(out)


def attach_live_timing_fields(match: dict) -> dict:
    """Intervalo, golos HT e fase do jogo — para condições dos bots."""
    out = {**match}
    status = str(out.get("match_status") or out.get("status") or "").upper()
    out["match_status"] = status or None

    minute_raw = out.get("minute")
    try:
        minute = int(minute_raw) if minute_raw is not None else 0
    except (TypeError, ValueError):
        minute = 0
    injury = out.get("injury_time") or 0
    try:
        injury = int(injury)
    except (TypeError, ValueError):
        injury = 0

    out["is_halftime"] = status == "HT"
    out["is_first_half"] = status in ("1H", "HT") or (status not in ("2H", "ET", "BT", "P") and minute <= 45)
    out["is_second_half"] = status in ("2H", "ET", "BT", "LIVE") or minute > 45

    hs, aw = _scores(match)
    ht_h = out.get("ht_home_score")
    ht_a = out.get("ht_away_score")
    try:
        ht_h = int(ht_h) if ht_h is not None else None
    except (TypeError, ValueError):
        ht_h = None
    try:
        ht_a = int(ht_a) if ht_a is not None else None
    except (TypeError, ValueError):
        ht_a = None

    if status == "HT" and hs is not None and aw is not None:
        ht_h, ht_a = hs, aw
    elif out["is_first_half"] and hs is not None and aw is not None:
        ht_h, ht_a = hs, aw

    out["ht_home_score"] = ht_h
    out["ht_away_score"] = ht_a
    if ht_h is not None and ht_a is not None:
        out["ht_total_goals"] = ht_h + ht_a
    else:
        out["ht_total_goals"] = None

    if out["is_first_half"] and hs is not None and aw is not None:
        out["first_half_goals"] = hs + aw
    elif out["ht_total_goals"] is not None:
        out["first_half_goals"] = out["ht_total_goals"]
    else:
        out["first_half_goals"] = None

    if minute > 0:
        out["remaining_minutes"] = max(0, 90 - minute + max(0, injury))
    else:
        out["remaining_minutes"] = None

    return out


LIVE_TIMING_FIELDS = frozenset(
    {
        "match_status",
        "is_halftime",
        "is_first_half",
        "is_second_half",
        "ht_home_score",
        "ht_away_score",
        "ht_total_goals",
        "first_half_goals",
        "remaining_minutes",
        "home_score",
        "away_score",
        "goal_diff",
    }
)


FAVORITE_FIELDS = frozenset(
    {
        "favorite_side",
        "favorite_status",
        "favorite_losing_or_drawing",
        "favorite_winning",
        "home_is_favorite",
        "away_is_favorite",
        "goal_diff",
        "favorite_goal_diff",
        "prematch_home_odd",
        "prematch_away_odd",
    }
)