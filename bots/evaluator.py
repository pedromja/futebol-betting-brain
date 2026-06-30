"""Avalia se um jogo analisado cumpre as regras de um bot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bots.types import BotConfig


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_to_kickoff(kickoff: str | None) -> float | None:
    dt = _parse_ts(kickoff)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (dt - datetime.now(timezone.utc)).total_seconds() / 60.0
    return round(delta, 1)


def _resolve_field(match: dict, field: str) -> Any:
    if field in match:
        return match.get(field)
    if field == "motivation_score":
        return (match.get("motivation") or {}).get("motivation_score")
    if field == "motivation_alignment":
        return (match.get("motivation") or {}).get("alignment")
    if field == "tm_alignment":
        return (match.get("transfermarkt") or {}).get("alignment")
    if field == "tm_available":
        return (match.get("transfermarkt") or {}).get("data_available")
    if field == "minutes_to_kickoff":
        return _minutes_to_kickoff(match.get("kickoff"))
    if field == "total_goals":
        hs = match.get("home_score")
        aw = match.get("away_score")
        if hs is None or aw is None:
            score = str(match.get("score") or "")
            if "-" in score:
                parts = score.split("-", 1)
                try:
                    return int(parts[0].strip()) + int(parts[1].strip())
                except ValueError:
                    return None
            return None
        return int(hs) + int(aw)
    if field == "temperature_c":
        env = match.get("environment") or {}
        w = env.get("weather") or {}
        return w.get("temperature_c")
    if field == "precipitation_mm":
        env = match.get("environment") or {}
        w = env.get("weather") or {}
        return w.get("precipitation_mm")
    return None


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if actual is None:
        return False
    op = (operator or "eq").lower()
    if op == "eq":
        if isinstance(expected, bool):
            return bool(actual) is expected
        return str(actual).lower() == str(expected).lower()
    if op == "neq":
        return str(actual).lower() != str(expected).lower()
    if op == "contains":
        return str(expected).lower() in str(actual).lower()
    if op == "in_list":
        items = expected if isinstance(expected, list) else [expected]
        return str(actual) in [str(x) for x in items]
    try:
        a = float(actual)
        e = float(expected)
    except (TypeError, ValueError):
        return False
    if op == "gte":
        return a >= e
    if op == "lte":
        return a <= e
    return False


def _eval_condition(match: dict, cond: dict) -> bool:
    field = str(cond.get("field") or "")
    if not field:
        return True
    actual = _resolve_field(match, field)
    return _compare(actual, str(cond.get("operator") or "eq"), cond.get("value"))


def _league_ok(match: dict, leagues: list[str]) -> bool:
    if not leagues:
        return True
    text = f"{match.get('league') or ''} {match.get('stage') or ''}".lower()
    return any(l.lower() in text for l in leagues if l.strip())


def _market_ok(match: dict, markets: list[str]) -> bool:
    if not markets:
        return True
    bm = str(match.get("best_market") or "")
    return bm in markets


def evaluate_bot(bot: BotConfig, match: dict, *, mode: str) -> bool:
    if not bot.active:
        return False
    if bot.mode != mode:
        return False
    if not _league_ok(match, bot.leagues):
        return False
    if not _market_ok(match, bot.markets):
        return False
    if bot.min_score is not None:
        try:
            if float(match.get("best_score") or 0) < float(bot.min_score):
                return False
        except (TypeError, ValueError):
            return False
    if bot.min_ev_pct is not None:
        try:
            if float(match.get("best_ev_pct") or 0) < float(bot.min_ev_pct):
                return False
        except (TypeError, ValueError):
            return False
    if bot.max_stake_level is not None:
        try:
            if int(match.get("stake_level") or 0) > int(bot.max_stake_level):
                return False
        except (TypeError, ValueError):
            return False
    if bot.minutes_before is not None and mode == "prematch":
        mins = _minutes_to_kickoff(match.get("kickoff"))
        if mins is None or mins > float(bot.minutes_before) or mins < 0:
            return False
    for cond in bot.conditions or []:
        if not _eval_condition(match, cond):
            return False
    return True


def evaluate_bots_for_scan(
    ranked: list[dict],
    *,
    mode: str,
    bots: list[BotConfig] | None = None,
) -> list[dict]:
    from bots.store import list_bots

    active = bots if bots is not None else list_bots(active_only=True)
    if not active or not ranked:
        return []
    hits: list[dict] = []
    for bot in active:
        matches = [m for m in ranked if evaluate_bot(bot, m, mode=mode)]
        if not matches:
            continue
        hits.append(
            {
                "bot_id": bot.id,
                "bot_name": bot.name,
                "mode": bot.mode,
                "notify": bot.notify,
                "total": len(matches),
                "matches": matches[:8],
            }
        )
    return hits