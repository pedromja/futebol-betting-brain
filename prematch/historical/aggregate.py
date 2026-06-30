"""Agrega CSV → perfis por equipa (fecho + estilo)."""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

from prematch.historical.names import canonical_team
from prematch.historical.sources import csv_url
from prematch.historical.types import TeamHistoricalProfile, VenueSlice


def _num(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _closing_triple(row: dict, prefix: str = "B365C") -> tuple[float | None, float | None, float | None]:
    home = _num(row.get(f"{prefix}H")) or _num(row.get("AvgCH")) or _num(row.get("AvgH"))
    draw = _num(row.get(f"{prefix}D")) or _num(row.get("AvgCD")) or _num(row.get("AvgD"))
    away = _num(row.get(f"{prefix}A")) or _num(row.get("AvgCA")) or _num(row.get("AvgA"))
    return home, draw, away


def _ou_over(row: dict) -> float | None:
    return _num(row.get("B365C>2.5")) or _num(row.get("AvgC>2.5")) or _num(row.get("B365>2.5"))


class _Acc:
    def __init__(self) -> None:
        self.shots: list[float] = []
        self.sot: list[float] = []
        self.corners: list[float] = []
        self.fouls: list[float] = []
        self.gf: list[float] = []
        self.ga: list[float] = []
        self.win_odds: list[float] = []
        self.ou_over: list[float] = []
        self.total_goals: list[float] = []

    def add(
        self,
        *,
        shots: float | None,
        sot: float | None,
        corners: float | None,
        fouls: float | None,
        gf: float | None,
        ga: float | None,
        win_odd: float | None,
        ou_over: float | None,
    ) -> None:
        if shots is not None:
            self.shots.append(shots)
        if sot is not None:
            self.sot.append(sot)
        if corners is not None:
            self.corners.append(corners)
        if fouls is not None:
            self.fouls.append(fouls)
        if gf is not None:
            self.gf.append(gf)
        if ga is not None:
            self.ga.append(ga)
        if gf is not None and ga is not None:
            self.total_goals.append(gf + ga)
        if win_odd is not None and win_odd > 1:
            self.win_odds.append(win_odd)
        if ou_over is not None and ou_over > 1:
            self.ou_over.append(ou_over)

    def to_slice(self) -> VenueSlice:
        def avg(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        return VenueSlice(
            matches=max(len(self.gf), len(self.shots)),
            shots_avg=avg(self.shots),
            sot_avg=avg(self.sot),
            corners_avg=avg(self.corners),
            fouls_avg=avg(self.fouls),
            goals_scored_avg=avg(self.gf),
            goals_conceded_avg=avg(self.ga),
            closing_win_odd_avg=avg(self.win_odds) if self.win_odds else None,
            closing_ou_over_avg=avg(self.ou_over) if self.ou_over else None,
        )


def fetch_csv_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "futebol-betting-brain/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")


def aggregate_csv_rows(
    rows: list[dict],
    *,
    league_code: str,
    season: str,
) -> list[TeamHistoricalProfile]:
    home_acc: dict[str, _Acc] = defaultdict(_Acc)
    away_acc: dict[str, _Acc] = defaultdict(_Acc)
    total_goals: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        home_raw = row.get("HomeTeam") or ""
        away_raw = row.get("AwayTeam") or ""
        home = canonical_team(home_raw)
        away = canonical_team(away_raw)
        if not home or not away:
            continue

        ch, _, ca = _closing_triple(row)
        ou = _ou_over(row)
        fthg = _num(row.get("FTHG"))
        ftag = _num(row.get("FTAG"))

        home_acc[home].add(
            shots=_num(row.get("HS")),
            sot=_num(row.get("HST")),
            corners=_num(row.get("HC")),
            fouls=_num(row.get("HF")),
            gf=fthg,
            ga=ftag,
            win_odd=ch,
            ou_over=ou,
        )
        away_acc[away].add(
            shots=_num(row.get("AS")),
            sot=_num(row.get("AST")),
            corners=_num(row.get("AC")),
            fouls=_num(row.get("AF")),
            gf=ftag,
            ga=fthg,
            win_odd=ca,
            ou_over=ou,
        )
        if fthg is not None and ftag is not None:
            total_goals[home].append(fthg + ftag)
            total_goals[away].append(fthg + ftag)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    teams = sorted(set(home_acc) | set(away_acc))
    profiles: list[TeamHistoricalProfile] = []
    for team in teams:
        h = home_acc[team].to_slice()
        a = away_acc[team].to_slice()
        tg = total_goals.get(team) or []
        profiles.append(
            TeamHistoricalProfile(
                team=team,
                league=league_code,
                season=season,
                matches=h.matches + a.matches,
                home=h,
                away=a,
                goals_total_avg=sum(tg) / len(tg) if tg else 0.0,
                updated_at=now,
            )
        )
    return profiles


def ingest_league(
    league_code: str,
    *,
    season: str = "2526",
    csv_text: str | None = None,
) -> list[TeamHistoricalProfile]:
    if csv_text is None:
        url = csv_url(league_code, season)
        if not url:
            return []
        try:
            csv_text = fetch_csv_text(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = [row for row in reader if row.get("HomeTeam")]
    return aggregate_csv_rows(rows, league_code=league_code, season=season)