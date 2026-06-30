"""Avalia se um jogo analisado cumpre as regras de um bot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bots.market_match import market_matches_filter
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
    if field == "home_score":
        hs, _ = _scores(match)
        return hs
    if field == "away_score":
        _, aw = _scores(match)
        return aw
    if field == "goal_diff":
        hs, aw = _scores(match)
        if hs is None or aw is None:
            return match.get("goal_diff")
        return hs - aw
    if field in ("ht_home_score", "ht_away_score", "ht_total_goals", "first_half_goals"):
        return match.get(field)
    if field == "match_status":
        return match.get("match_status") or match.get("status")
    if field == "is_halftime":
        return match.get("is_halftime")
    if field == "is_first_half":
        return match.get("is_first_half")
    if field == "is_second_half":
        return match.get("is_second_half")
    if field == "remaining_minutes":
        return match.get("remaining_minutes")
    if field == "favorite_winning":
        return match.get("favorite_winning")
    if field == "away_is_favorite":
        return match.get("away_is_favorite")
    if field == "stake_level":
        return match.get("stake_level")
    if field.startswith("pattern_") or field.startswith("scenario_"):
        return match.get(field)
    if field.startswith("underdog_") or field == "competition_progress_pct":
        return match.get(field)
    return None


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
        return str(actual).lower() in [str(x).lower() for x in items]
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


def _eval_condition_list(match: dict, conditions: list[dict], logic: str) -> bool:
    if not conditions:
        return True
    results = [_eval_condition(match, c) for c in conditions]
    return all(results) if logic == "and" else any(results)


def _eval_bot_conditions(bot: BotConfig, match: dict) -> bool:
    groups = bot.condition_groups or []
    if groups:
        group_results = []
        for group in groups:
            gconds = group.get("conditions") or []
            if not gconds:
                continue
            glogic = str(group.get("logic") or "and").lower()
            if glogic not in ("and", "or"):
                glogic = "and"
            group_results.append(_eval_condition_list(match, gconds, glogic))
        if not group_results:
            return True
        gl = str(bot.groups_logic or "or").lower()
        return all(group_results) if gl == "and" else any(group_results)

    conds = bot.conditions or []
    logic = str(bot.conditions_logic or "and").lower()
    if logic not in ("and", "or"):
        logic = "and"
    return _eval_condition_list(match, conds, logic)


def _league_ok(match: dict, leagues: list[str]) -> bool:
    if not leagues:
        return True
    text = f"{match.get('league') or ''} {match.get('stage') or ''}".lower()
    return any(l.lower() in text for l in leagues if l.strip())


def _market_ok(match: dict, markets: list[str]) -> bool:
    if not markets:
        return True
    return any(market_matches_filter(match, m) for m in markets if m.strip())


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
    return _eval_bot_conditions(bot, match)


def evaluate_bots_for_scan(
    ranked: list[dict],
    *,
    mode: str,
    bots: list[BotConfig] | None = None,
) -> list[dict]:
    from bots.live_enrich import enrich_live_ranked_for_bots
    from bots.store import list_bots

    pool_bots = bots if bots is not None else list_bots(active_only=True)
    active = [b for b in pool_bots if b.active and b.mode == mode]
    if not active or not ranked:
        return []

    pool = ranked
    if mode == "live":
        pool = enrich_live_ranked_for_bots(ranked, bots=active)
    else:
        from bots.live_enrich import enrich_prematch_ranked_for_bots

        pool = enrich_prematch_ranked_for_bots(ranked, bots=active)

    from bots.ia_gate import apply_ia_gate_to_hits

    hits: list[dict] = []
    for bot in active:
        matches = [m for m in pool if evaluate_bot(bot, m, mode=mode)]
        if not matches:
            continue
        hits.append(
            {
                "bot_id": bot.id,
                "bot_name": bot.name,
                "bot_template": bot.template,
                "template": bot.template,
                "mode": bot.mode,
                "notify": bot.notify,
                "total": len(matches),
                "matches": matches[:8],
            }
        )
    return apply_ia_gate_to_hits(hits)