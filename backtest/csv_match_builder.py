"""CSV football-data.co.uk → jogos ordenados + stats rolling anti-leakage."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from models.team_stats import MatchInput, MatchOdds, TeamForm
from prematch.historical.aggregate import _closing_triple, _num, _ou_over, fetch_csv_text
from prematch.historical.names import canonical_team
from prematch.historical.sources import LEAGUE_FILES, csv_url

LEAGUE_LABELS: dict[str, str] = {
    "PPL": "Primeira Liga",
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
}

DEFAULT_SEASONS = ("2324", "2425", "2526")
DEFAULT_LEAGUES = tuple(LEAGUE_FILES.keys())
ROLLING_WINDOW = 12
MIN_GAMES_BEFORE_BET = 8


@dataclass
class ParsedMatch:
    league_code: str
    league_label: str
    season: str
    date: str
    date_sort: datetime
    home: str
    away: str
    fthg: int
    ftag: int
    hthg: int | None
    htag: int | None
    hs: int
    as_: int
    hst: int
    ast: int
    hc: int
    ac: int
    hf: int
    af: int
    home_odd: float | None
    draw_odd: float | None
    away_odd: float | None
    over_25_odd: float | None
    under_25_odd: float | None

    @property
    def total_goals(self) -> int:
        return self.fthg + self.ftag

    @property
    def total_corners(self) -> int:
        return self.hc + self.ac


@dataclass
class _TeamRolling:
    gf: list[float] = field(default_factory=list)
    ga: list[float] = field(default_factory=list)
    scored_flags: list[bool] = field(default_factory=list)
    conceded_flags: list[bool] = field(default_factory=list)

    def snapshot(self) -> dict:
        n = len(self.gf)
        if n == 0:
            return {"games": 0}
        window = self.gf[-ROLLING_WINDOW:]
        ga_w = self.ga[-ROLLING_WINDOW:]
        sf = self.scored_flags[-ROLLING_WINDOW:]
        cf = self.conceded_flags[-ROLLING_WINDOW:]
        return {
            "games": n,
            "gf_avg": sum(window) / len(window),
            "ga_avg": sum(ga_w) / len(ga_w),
            "scored_in": sum(1 for x in sf if x),
            "conceded_in": sum(1 for x in cf if x),
            "last_n": len(window),
        }

    def push(self, gf: float, ga: float) -> None:
        self.gf.append(gf)
        self.ga.append(ga)
        self.scored_flags.append(gf > 0)
        self.conceded_flags.append(ga > 0)


def _parse_date(raw: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime((raw or "").strip(), fmt)
        except ValueError:
            continue
    return datetime(2000, 1, 1)


def parse_csv_rows(
    rows: list[dict],
    *,
    league_code: str,
    season: str,
) -> list[ParsedMatch]:
    label = LEAGUE_LABELS.get(league_code, league_code)
    out: list[ParsedMatch] = []
    for row in rows:
        home = canonical_team(row.get("HomeTeam") or "")
        away = canonical_team(row.get("AwayTeam") or "")
        if not home or not away:
            continue
        fthg = _num(row.get("FTHG"))
        ftag = _num(row.get("FTAG"))
        if fthg is None or ftag is None:
            continue
        hthg = _num(row.get("HTHG"))
        htag = _num(row.get("HTAG"))
        ch, cd, ca = _closing_triple(row)
        ou = _ou_over(row)
        under = _num(row.get("B365C<2.5")) or _num(row.get("AvgC<2.5"))
        if (under is None or under < 1.05) and ou and ou > 1.05:
            under = round(max(1.05, ou * 0.88), 2)
        date_raw = str(row.get("Date") or "")
        out.append(
            ParsedMatch(
                league_code=league_code,
                league_label=label,
                season=season,
                date=date_raw,
                date_sort=_parse_date(date_raw),
                home=home,
                away=away,
                fthg=int(fthg),
                ftag=int(ftag),
                hthg=int(hthg) if hthg is not None else None,
                htag=int(htag) if htag is not None else None,
                hs=int(_num(row.get("HS")) or 0),
                as_=int(_num(row.get("AS")) or 0),
                hst=int(_num(row.get("HST")) or 0),
                ast=int(_num(row.get("AST")) or 0),
                hc=int(_num(row.get("HC")) or 0),
                ac=int(_num(row.get("AC")) or 0),
                hf=int(_num(row.get("HF")) or 0),
                af=int(_num(row.get("AF")) or 0),
                home_odd=ch,
                draw_odd=cd,
                away_odd=ca,
                over_25_odd=ou,
                under_25_odd=under,
            )
        )
    out.sort(key=lambda m: m.date_sort)
    return out


def load_league_matches(
    league_code: str,
    season: str,
    *,
    csv_text: str | None = None,
) -> list[ParsedMatch]:
    if csv_text is None:
        url = csv_url(league_code, season)
        if not url:
            return []
        try:
            csv_text = fetch_csv_text(url)
        except OSError:
            return []
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = [r for r in reader if r.get("HomeTeam")]
    return parse_csv_rows(rows, league_code=league_code, season=season)


def load_multi_league_matches(
    leagues: tuple[str, ...] | list[str] | None = None,
    seasons: tuple[str, ...] | list[str] | None = None,
    *,
    csv_by_key: dict[tuple[str, str], str] | None = None,
) -> list[ParsedMatch]:
    leagues = tuple(leagues or DEFAULT_LEAGUES)
    seasons = tuple(seasons or DEFAULT_SEASONS)
    csv_by_key = csv_by_key or {}
    all_matches: list[ParsedMatch] = []
    for code in leagues:
        for season in seasons:
            text = csv_by_key.get((code, season))
            batch = load_league_matches(code, season, csv_text=text)
            all_matches.extend(batch)
    all_matches.sort(key=lambda m: (m.date_sort, m.league_code))
    return all_matches


def build_team_form(name: str, snap: dict) -> TeamForm:
    games = int(snap.get("games") or 0)
    last_n = int(snap.get("last_n") or 0)
    return TeamForm(
        name=name,
        goals_scored_avg=float(snap.get("gf_avg") or 1.2),
        goals_conceded_avg=float(snap.get("ga_avg") or 1.2),
        games_played=games,
        scored_in_last_n=int(snap.get("scored_in") or 0),
        conceded_in_last_n=int(snap.get("conceded_in") or 0),
        last_n=max(last_n, 1),
    )


def build_match_input(
    match: ParsedMatch,
    *,
    home_snap: dict,
    away_snap: dict,
) -> MatchInput | None:
    if home_snap.get("games", 0) < MIN_GAMES_BEFORE_BET:
        return None
    if away_snap.get("games", 0) < MIN_GAMES_BEFORE_BET:
        return None
    hw = match.home_odd or 0
    aw = match.away_odd or 0
    dr = match.draw_odd or 0
    ou = match.over_25_odd or 0
    un = match.under_25_odd or 0
    if hw < 1.05 or aw < 1.05 or ou < 1.05 or un < 1.05:
        return None
    btts_yes = round(min(2.5, 1.0 / max(0.05, 0.5 - 1.0 / ou)), 2) if ou > 1.1 else 1.9
    btts_no = round(max(1.5, ou * 0.55), 2)
    dc_1x = round(max(1.05, 1.0 / (1.0 / hw + (1.0 / dr if dr > 1 else 0.28))), 2) if dr > 1 else round(hw * 1.35, 2)
    dc_x2 = round(max(1.05, 1.0 / ((1.0 / dr if dr > 1 else 0.28) + 1.0 / aw)), 2) if dr > 1 else round(aw * 1.35, 2)
    return MatchInput(
        home=build_team_form(match.home, home_snap),
        away=build_team_form(match.away, away_snap),
        odds=MatchOdds(
            home_win=hw,
            draw=dr if dr > 1.05 else round((hw + aw) / 2, 2),
            away_win=aw,
            over_25=ou,
            under_25=un if un > 1.05 else round(ou / (ou - 1) * 0.9, 2),
            btts_yes=btts_yes,
            btts_no=btts_no,
            double_chance_1x=dc_1x,
            double_chance_x2=dc_x2,
        ),
        league=match.league_label,
        date=match.date,
    )


class RollingState:
    """Stats por equipa/liga — só jogos anteriores ao actual."""

    def __init__(self) -> None:
        self._teams: dict[tuple[str, str], _TeamRolling] = defaultdict(_TeamRolling)

    def snapshot(self, team: str, league_code: str) -> dict:
        return self._teams[(team, league_code)].snapshot()

    def record(self, match: ParsedMatch) -> None:
        self._teams[(match.home, match.league_code)].push(match.fthg, match.ftag)
        self._teams[(match.away, match.league_code)].push(match.ftag, match.fthg)


def estimate_live_at_minute(match: ParsedMatch, minute: int = 58) -> dict:
    """Estado sintético ao vivo a partir de stats FT/HT (backtest parcial)."""
    pace = min(max(minute, 1), 90) / 90.0
    hthg = match.hthg if match.hthg is not None else 0
    htag = match.htag if match.htag is not None else 0
    gh_2h = max(0, match.fthg - hthg)
    ga_2h = max(0, match.ftag - htag)
    post_ht_share = max(0.0, min(1.0, (minute - 45) / 45.0)) if minute > 45 else 0.0
    home_score = hthg + round(gh_2h * post_ht_share)
    away_score = htag + round(ga_2h * post_ht_share)
    home_corners = max(0, round(match.hc * pace))
    away_corners = max(0, round(match.ac * pace))
    home_sot = max(0, round(match.hst * pace))
    away_sot = max(0, round(match.ast * pace))
    home_xg = round(home_sot * 0.12 + home_score * 0.35, 2)
    away_xg = round(away_sot * 0.12 + away_score * 0.35, 2)
    return {
        "minute": minute,
        "home_score": home_score,
        "away_score": away_score,
        "ht_home_score": hthg,
        "ht_away_score": htag,
        "home_corners": home_corners,
        "away_corners": away_corners,
        "home_shots_on": home_sot,
        "away_shots_on": away_sot,
        "home_xg": home_xg,
        "away_xg": away_xg,
        "xg_diff": round(home_xg - away_xg, 2),
        "home_possession_pct": 52 if home_xg >= away_xg else 48,
        "away_possession_pct": 48 if home_xg >= away_xg else 52,
        "total_fouls": max(0, round((match.hf + match.af) * pace)),
        "match_status": "2H",
        "is_second_half": True,
    }