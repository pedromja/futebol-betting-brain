"""Auditores Tier 2 — fecho histórico + estilo de jogo."""

from __future__ import annotations

from prematch.auditors.types import AuditorVote
from prematch.historical.store import get_store
from prematch.historical.types import TeamHistoricalProfile

_CLOSING_VALUE_PCT = 4.0
_CLOSING_TRAP_PCT = -6.0
_OPEN_GAME_SHOTS = 12.0
_OPEN_GAME_SOT = 4.0
_OPEN_GAME_GOALS = 2.6
_CLOSED_GAME_SHOTS = 9.5
_CLOSED_GAME_GOALS = 2.3


def _pick_odd(odds_hint: dict | None, key: str) -> float | None:
    if not odds_hint:
        return None
    val = odds_hint.get(key)
    try:
        return float(val) if val and float(val) > 1 else None
    except (TypeError, ValueError):
        return None


def _closing_reference(
    profile: TeamHistoricalProfile | None,
    *,
    venue: str,
) -> float | None:
    if not profile:
        return None
    slice_ = profile.home if venue == "home" else profile.away
    return slice_.closing_win_odd_avg


def audit_market_closing(
    home: str,
    away: str,
    *,
    bet_side: str,
    odds_hint: dict | None,
    league: str = "",
) -> tuple[AuditorVote | None, dict | None]:
    store = get_store()
    home_prof = store.profile(home, league=league)
    away_prof = store.profile(away, league=league)

    if bet_side == "home":
        ref = _closing_reference(home_prof, venue="home")
        today = _pick_odd(odds_hint, "home_win")
        team = home
    elif bet_side == "away":
        ref = _closing_reference(away_prof, venue="away")
        today = _pick_odd(odds_hint, "away_win")
        team = away
    else:
        return None, None

    if not ref or not today:
        return None, None

    delta_pct = (today / ref - 1.0) * 100.0
    payload = {
        "team": team,
        "today_odd": round(today, 2),
        "closing_avg": round(ref, 2),
        "delta_pct": round(delta_pct, 1),
    }

    if delta_pct >= _CLOSING_VALUE_PCT:
        return (
            AuditorVote(
                auditor_id="market_closing",
                category="historical_market",
                side=bet_side,
                label=(
                    f"Odd {bet_side} {today:.2f} vs fecho hist. {ref:.2f} "
                    f"(+{delta_pct:.0f}% — linha generosa)"
                ),
            ),
            payload,
        )
    if delta_pct <= _CLOSING_TRAP_PCT:
        return (
            AuditorVote(
                auditor_id="market_closing_trap",
                category="historical_market",
                side="neutral",
                label=(
                    f"Odd {today:.2f} abaixo do fecho típico {ref:.2f} "
                    f"({delta_pct:.0f}% — suspeito)"
                ),
                supports_market=False,
            ),
            payload,
        )
    return None, payload


def _open_game_score(home_prof: TeamHistoricalProfile | None, away_prof: TeamHistoricalProfile | None) -> float:
    scores: list[float] = []
    for prof, venue in ((home_prof, "home"), (away_prof, "away")):
        if not prof:
            continue
        sl = prof.home if venue == "home" else prof.away
        if sl.matches < 3:
            continue
        s = 0.0
        if sl.shots_avg >= _OPEN_GAME_SHOTS:
            s += 1
        if sl.sot_avg >= _OPEN_GAME_SOT:
            s += 1
        if prof.goals_total_avg >= _OPEN_GAME_GOALS:
            s += 0.5
        scores.append(s)
    return sum(scores) / len(scores) if scores else 0.0


def audit_style_profile(
    home: str,
    away: str,
    *,
    bet_side: str,
    league: str = "",
) -> AuditorVote | None:
    store = get_store()
    home_prof = store.profile(home, league=league)
    away_prof = store.profile(away, league=league)
    if not home_prof and not away_prof:
        return None

    open_score = _open_game_score(home_prof, away_prof)
    if open_score < 0.75 and bet_side not in ("over", "under"):
        return None

    avg_shots = 0.0
    count = 0
    for prof, venue in ((home_prof, "home"), (away_prof, "away")):
        if not prof:
            continue
        sl = prof.home if venue == "home" else prof.away
        if sl.matches >= 3:
            avg_shots += sl.shots_avg
            count += 1
    shots_mean = avg_shots / count if count else 0.0
    goals_mean = 0.0
    g_n = 0
    for prof in (home_prof, away_prof):
        if prof and prof.goals_total_avg > 0:
            goals_mean += prof.goals_total_avg
            g_n += 1
    goals_mean = goals_mean / g_n if g_n else 0.0

    if bet_side == "over":
        if open_score >= 1.0 or goals_mean >= _OPEN_GAME_GOALS:
            return AuditorVote(
                auditor_id="style_profile",
                category="historical_market",
                side="neutral",
                market_side="over",
                label=(
                    f"Estilo aberto — {shots_mean:.1f} remates/equipa, "
                    f"{goals_mean:.1f} golos/jogo (hist.)"
                ),
            )
        return None

    if bet_side == "under":
        if shots_mean > 0 and shots_mean <= _CLOSED_GAME_SHOTS and goals_mean <= _CLOSED_GAME_GOALS:
            return AuditorVote(
                auditor_id="style_profile",
                category="historical_market",
                side="neutral",
                market_side="under",
                label=(
                    f"Estilo fechado — {shots_mean:.1f} remates/equipa, "
                    f"{goals_mean:.1f} golos/jogo (hist.)"
                ),
            )
        return None

    if bet_side == "home" and open_score >= 1.0:
        return AuditorVote(
            auditor_id="style_profile",
            category="historical_market",
            side="home",
            label=f"Casa cria volume ({home_prof.home.shots_avg:.1f} remates em casa)" if home_prof else "Estilo ofensivo casa",
        )
    if bet_side == "away" and open_score >= 1.0:
        return AuditorVote(
            auditor_id="style_profile",
            category="historical_market",
            side="away",
            label=f"Fora cria volume ({away_prof.away.shots_avg:.1f} remates fora)" if away_prof else "Estilo ofensivo fora",
        )
    return None