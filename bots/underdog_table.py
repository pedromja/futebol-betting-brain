"""Underdog vs classificação — «com raça» vs «galinha» com significância estatística."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from bankroll.competition_progress import resolve_competition_progress
from prematch.auditors.table_stakes import _match_team_row, fetch_standings, league_to_fd_code
from prematch.historical.names import canonical_team
from prematch.historical.sources import LEAGUE_FILES, csv_url
from prematch.historical.aggregate import fetch_csv_text
from prematch.transfermarkt.match_names import team_key

UNDERDOG_PROGRESS_MIN = 25.0
UNDERDOG_PROGRESS_MAX = 85.0

MIN_GAMES_STRONG = 5
MIN_GAMES_WEAK = 5
MIN_RATE_RACA = 0.38
MAX_RATE_GALINHA = 0.28
MIN_RATE_DELTA = 0.12
Z_SIGNIFICANCE = 1.96

UNDERDOG_FIELDS = frozenset(
    {
        "underdog_side",
        "underdog_team",
        "underdog_opponent",
        "underdog_table_gap",
        "underdog_scenario",
        "underdog_significant",
        "underdog_favorite_hunt",
        "underdog_scoring_alert",
        "underdog_rate_vs_strong_pct",
        "underdog_rate_vs_weak_pct",
        "underdog_games_vs_strong",
        "underdog_games_vs_weak",
        "underdog_z_score",
        "underdog_p_value",
        "underdog_progress_ok",
        "underdog_progress_pct",
        "underdog_summary",
        "competition_progress_pct",
    }
)

_PROFILE_CACHE: dict[tuple[str, str], dict] = {}
_STANDINGS_SESSION: dict[str, list[dict] | None] = {}
_PROGRESS_SESSION: dict[str, tuple[bool, float | None]] = {}


@dataclass
class _TableState:
    points: dict[str, int]
    played: dict[str, int]

    def position(self, team: str) -> int | None:
        if team not in self.points:
            return None
        ordered = sorted(
            self.points.keys(),
            key=lambda t: (-self.points[t], self.played.get(t, 0), t),
        )
        try:
            return ordered.index(team) + 1
        except ValueError:
            return None

    def record(self, home: str, away: str, hg: int, ag: int) -> None:
        for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
            self.points[team] = self.points.get(team, 0) + (3 if gf > ga else 1 if gf == ag else 0)
            self.played[team] = self.played.get(team, 0) + 1


def _z_test_two_proportions(success_a: int, n_a: int, success_b: int, n_b: int) -> tuple[float, float]:
    if n_a < 2 or n_b < 2:
        return 0.0, 1.0
    p_a = success_a / n_a
    p_b = success_b / n_b
    p_pool = (success_a + success_b) / (n_a + n_b)
    if p_pool <= 0 or p_pool >= 1:
        return 0.0, 1.0
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n_a + 1.0 / n_b))
    if se <= 1e-9:
        return 0.0, 1.0
    z = (p_a - p_b) / se
    p_approx = math.erfc(abs(z) / math.sqrt(2.0))
    return round(z, 3), round(min(1.0, p_approx), 4)


def _p_from_z(z: float) -> float:
    return round(math.erfc(abs(z) / math.sqrt(2.0)), 4)


def _classify_scenario(
    *,
    scored_strong: int,
    games_strong: int,
    scored_weak: int,
    games_weak: int,
) -> tuple[str, bool, float, float, float]:
    rate_s = scored_strong / games_strong if games_strong else 0.0
    rate_w = scored_weak / games_weak if games_weak else 0.0
    z, p_val = _z_test_two_proportions(scored_strong, games_strong, scored_weak, games_weak)
    significant = (
        games_strong >= MIN_GAMES_STRONG
        and games_weak >= MIN_GAMES_WEAK
        and p_val < 0.05
        and abs(rate_s - rate_w) >= MIN_RATE_DELTA
    )
    scenario = "insufficient"
    if significant:
        if rate_s >= rate_w + MIN_RATE_DELTA and rate_s >= MIN_RATE_RACA:
            scenario = "raca"
        elif rate_s <= rate_w - MIN_RATE_DELTA and rate_s <= MAX_RATE_GALINHA:
            scenario = "galinha"
        else:
            scenario = "neutral"
    elif games_strong >= 3:
        if rate_s >= MIN_RATE_RACA and rate_s >= rate_w + 0.08:
            scenario = "raca_trend"
        elif rate_s <= MAX_RATE_GALINHA and rate_s <= rate_w - 0.08:
            scenario = "galinha_trend"
    return scenario, significant, rate_s, rate_w, z


def _ingest_csv_season(league_code: str, season: str) -> None:
    from backtest.csv_match_builder import parse_csv_rows
    import csv
    import io

    url = csv_url(league_code, season)
    if not url:
        return
    try:
        text = fetch_csv_text(url)
    except OSError:
        return
    rows = list(csv.DictReader(io.StringIO(text)))
    parsed = parse_csv_rows(rows, league_code=league_code, season=season)
    table = _TableState(points={}, played={})
    acc: dict[str, dict[str, int]] = {}

    def _acc(team: str) -> dict[str, int]:
        if team not in acc:
            acc[team] = {
                "scored_strong": 0,
                "games_strong": 0,
                "scored_weak": 0,
                "games_weak": 0,
            }
        return acc[team]

    for m in parsed:
        home = canonical_team(m.home) or m.home
        away = canonical_team(m.away) or m.away
        hp = table.position(home)
        ap = table.position(away)
        if hp and ap and hp != ap:
            if hp < ap:
                stronger, weaker = home, away
                wg, sg = m.ftag, m.fthg
            else:
                stronger, weaker = away, home
                wg, sg = m.fthg, m.ftag
            wa = _acc(weaker)
            wa["games_strong"] += 1
            if sg >= 1:
                wa["scored_strong"] += 1
            sa = _acc(stronger)
            sa["games_weak"] += 1
            if wg >= 1:
                sa["scored_weak"] += 1
        table.record(home, away, m.fthg, m.ftag)

    for team, stats in acc.items():
        scenario, sig, rate_s, rate_w, z = _classify_scenario(
            scored_strong=stats["scored_strong"],
            games_strong=stats["games_strong"],
            scored_weak=stats["scored_weak"],
            games_weak=stats["games_weak"],
        )
        key = (league_code, team_key(team))
        _PROFILE_CACHE[key] = {
            "team": team,
            "league_code": league_code,
            "scenario": scenario,
            "significant": sig,
            "rate_vs_strong_pct": round(rate_s * 100, 1),
            "rate_vs_weak_pct": round(rate_w * 100, 1),
            "games_vs_strong": stats["games_strong"],
            "games_vs_weak": stats["games_weak"],
            "z_score": z,
            "p_value": _p_from_z(z) if stats["games_strong"] >= 2 else None,
        }


def warm_underdog_league(league: str, *, football_data_key: str | None = None) -> None:
    """Pré-carrega perfis CSV e classificação — uma vez por liga por scan."""
    if not league:
        return
    _ensure_league_profiles(league)
    if league not in _STANDINGS_SESSION and football_data_key:
        _STANDINGS_SESSION[league] = fetch_standings(league, api_key=football_data_key)
    if league not in _PROGRESS_SESSION:
        _PROGRESS_SESSION[league] = _progress_window(league, football_data_key=football_data_key)


def clear_underdog_session_cache() -> None:
    _STANDINGS_SESSION.clear()
    _PROGRESS_SESSION.clear()


def _ensure_league_profiles(league: str) -> None:
    code = league_to_fd_code(league)
    if not code or code not in LEAGUE_FILES:
        return
    if any(k[0] == code for k in _PROFILE_CACHE):
        return
    for season in ("2324", "2425", "2526"):
        _ingest_csv_season(code, season)


def _profile_for_team(team: str, league: str) -> dict | None:
    _ensure_league_profiles(league)
    code = league_to_fd_code(league)
    if not code:
        return None
    return _PROFILE_CACHE.get((code, team_key(team)))


def _underdog_from_standings(
    home: str,
    away: str,
    table: list[dict] | None,
    *,
    odds_hint: dict | None,
) -> tuple[str | None, str | None, int | None]:
    if table:
        hr = _match_team_row(home, table)
        ar = _match_team_row(away, table)
        if hr and ar:
            hp = int(hr.get("position") or 0)
            ap = int(ar.get("position") or 0)
            if hp > 0 and ap > 0 and hp != ap:
                if hp > ap:
                    return "home", home, hp - ap
                return "away", away, ap - hp
    hint = odds_hint or {}
    try:
        hw = float(hint.get("home_win") or 0)
        aw = float(hint.get("away_win") or 0)
    except (TypeError, ValueError):
        return None, None, None
    if hw > 1.05 and aw > 1.05 and abs(hw - aw) >= 0.12:
        if hw > aw:
            return "away", away, None
        return "home", home, None
    return None, None, None


def _progress_window(
    league: str,
    *,
    stage: str = "",
    football_data_key: str | None = None,
) -> tuple[bool, float | None]:
    info = resolve_competition_progress(
        league, stage=stage, football_data_key=football_data_key
    )
    if info is None:
        return True, None
    pct = info.progress_pct
    ok = UNDERDOG_PROGRESS_MIN <= pct <= UNDERDOG_PROGRESS_MAX
    return ok, pct


def _build_summary(
    *,
    team: str,
    opponent: str,
    scenario: str,
    significant: bool,
    rate_s: float,
    rate_w: float,
    progress_pct: float | None,
    favorite_hunt: bool,
    alert: str,
) -> str:
    sig_txt = "significativo" if significant else "amostra curta"
    prog = f"época {progress_pct:.0f}%" if progress_pct is not None else "época n/d"
    hunt = " — caça favoritos" if favorite_hunt else ""
    if scenario in ("raca", "raca_trend"):
        return (
            f"{team} vs {opponent} ({prog}): underdog com raça — marca {rate_s:.0f}% "
            f"contra melhor classificado vs {rate_w:.0f}% contra piores ({sig_txt}). "
            f"Alerta: {alert}{hunt}."
        )
    if scenario in ("galinha", "galinha_trend"):
        return (
            f"{team} vs {opponent} ({prog}): underdog galinha — só {rate_s:.0f}% a marcar "
            f"contra melhor classificado vs {rate_w:.0f}% contra piores ({sig_txt}). "
            f"Alerta: {alert}{hunt}."
        )
    return f"{team} vs {opponent}: perfil underdog neutro ({rate_s:.0f}% vs fortes)."


def compute_underdog_analysis(
    match: dict,
    *,
    football_data_key: str | None = None,
) -> dict[str, Any]:
    """Analisa underdog da jornada com janela 25–85% de progresso."""
    home = str(match.get("home") or "")
    away = str(match.get("away") or "")
    league = str(match.get("league") or "")
    stage = str(match.get("stage") or "")
    if not home or not away or not league:
        return {"underdog_scenario": "insufficient"}

    league_key = league.strip()
    if league_key in _PROGRESS_SESSION:
        progress_ok, progress_pct = _PROGRESS_SESSION[league_key]
    else:
        progress_ok, progress_pct = _progress_window(
            league, stage=stage, football_data_key=football_data_key
        )
        _PROGRESS_SESSION[league_key] = (progress_ok, progress_pct)
    cp = match.get("competition_progress") or {}
    if progress_pct is None and cp.get("progress_pct") is not None:
        try:
            progress_pct = float(cp["progress_pct"])
            progress_ok = UNDERDOG_PROGRESS_MIN <= progress_pct <= UNDERDOG_PROGRESS_MAX
            _PROGRESS_SESSION[league_key] = (progress_ok, progress_pct)
        except (TypeError, ValueError):
            pass

    if league_key in _STANDINGS_SESSION:
        table = _STANDINGS_SESSION[league_key]
    elif football_data_key:
        table = fetch_standings(league, api_key=football_data_key)
        _STANDINGS_SESSION[league_key] = table
    else:
        table = None
    side, ud_team, gap = _underdog_from_standings(
        home, away, table, odds_hint=match.get("odds_hint")
    )
    if not side or not ud_team:
        return {
            "underdog_scenario": "none",
            "underdog_progress_ok": progress_ok,
            "underdog_progress_pct": progress_pct,
            "competition_progress_pct": progress_pct,
            "underdog_summary": "Sem underdog claro (classificação ou odds equilibradas).",
        }

    opponent = away if side == "home" else home
    prof = _profile_for_team(ud_team, league) or {}
    scenario = str(prof.get("scenario") or "insufficient")
    significant = bool(prof.get("significant"))
    rate_s = float(prof.get("rate_vs_strong_pct") or 0)
    rate_w = float(prof.get("rate_vs_weak_pct") or 0)

    top_half = False
    if table and gap is not None:
        opp_row = _match_team_row(opponent, table)
        if opp_row:
            pos = int(opp_row.get("position") or 99)
            top_half = pos <= max(1, len(table) // 2)

    favorite_hunt = (
        progress_ok
        and scenario in ("raca", "raca_trend")
        and significant
        and top_half
    )

    if scenario in ("raca", "raca_trend"):
        alert = "marca com facilidade vs favorito"
    elif scenario in ("galinha", "galinha_trend"):
        alert = "dificuldade em marcar vs favorito"
    else:
        alert = "neutro"

    summary = _build_summary(
        team=ud_team,
        opponent=opponent,
        scenario=scenario,
        significant=significant,
        rate_s=rate_s,
        rate_w=rate_w,
        progress_pct=progress_pct,
        favorite_hunt=favorite_hunt,
        alert=alert,
    )

    return {
        "underdog_side": side,
        "underdog_team": ud_team,
        "underdog_opponent": opponent,
        "underdog_table_gap": gap,
        "underdog_scenario": scenario,
        "underdog_significant": significant,
        "underdog_favorite_hunt": favorite_hunt,
        "underdog_scoring_alert": alert,
        "underdog_rate_vs_strong_pct": rate_s,
        "underdog_rate_vs_weak_pct": rate_w,
        "underdog_games_vs_strong": prof.get("games_vs_strong"),
        "underdog_games_vs_weak": prof.get("games_vs_weak"),
        "underdog_z_score": prof.get("z_score"),
        "underdog_p_value": prof.get("p_value"),
        "underdog_progress_ok": progress_ok,
        "underdog_progress_pct": progress_pct,
        "competition_progress_pct": progress_pct,
        "underdog_summary": summary,
    }


def attach_underdog_fields(match: dict, *, football_data_key: str | None = None) -> dict:
    out = {**match}
    out.update(compute_underdog_analysis(out, football_data_key=football_data_key))
    return out


def bot_conditions_need_underdog(conditions: list[dict]) -> bool:
    from bots.underdog_ia import UNDERDOG_IA_FIELDS

    fields = UNDERDOG_FIELDS | UNDERDOG_IA_FIELDS
    for cond in conditions or []:
        if str(cond.get("field") or "") in fields:
            return True
    return False