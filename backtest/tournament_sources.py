"""Fontes de jogos de competições (Mundial, Euro, Copa) — resultados internacionais."""

from __future__ import annotations

import csv
import io
import urllib.request
from dataclasses import dataclass
from datetime import datetime

INTERNATIONAL_CSV_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)

# Edições completas com histórico semelhante ao ciclo actual (fase final)
WORLD_CUP_YEARS = (2010, 2014, 2018, 2022)
EURO_YEARS = (2012, 2016, 2020, 2021, 2024)
COPA_YEARS = (2015, 2016, 2019, 2021, 2024)

TOURNAMENT_GOALS_AVG: dict[str, float] = {
    "FIFA World Cup": 2.65,
    "UEFA Euro": 2.45,
    "Copa América": 2.55,
}


@dataclass
class TournamentMatch:
    competition: str
    edition: str
    year: int
    date: str
    date_sort: datetime
    home: str
    away: str
    fthg: int
    ftag: int
    neutral: bool
    city: str
    country: str
    edition_index: int = 0
    phase: str = "group"
    home_games_before: int = 0
    away_games_before: int = 0

    @property
    def total_goals(self) -> int:
        return self.fthg + self.ftag


def _parse_date(raw: str) -> datetime:
    try:
        return datetime.strptime((raw or "").strip()[:10], "%Y-%m-%d")
    except ValueError:
        return datetime(2000, 1, 1)


def _normalize_team(name: str) -> str:
    return str(name or "").strip()


def fetch_international_csv(*, url: str = INTERNATIONAL_CSV_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "futebol-betting-brain/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _phase_for_index(competition: str, idx: int, total: int) -> str:
    if total <= 12:
        return "knockout" if idx > max(2, int(total * 0.65)) else "group"
    if competition == "FIFA World Cup":
        return "knockout" if idx > min(48, int(total * 0.72)) else "group"
    if competition == "UEFA Euro":
        return "knockout" if idx > min(36, int(total * 0.70)) else "group"
    if competition == "Copa América":
        return "knockout" if idx > max(12, int(total * 0.55)) else "group"
    return "knockout" if idx > int(total * 0.65) else "group"


def _filter_edition_rows(
    rows: list[dict],
    *,
    competition: str,
    year: int,
) -> list[dict]:
    out = []
    for row in rows:
        if str(row.get("tournament") or "") != competition:
            continue
        if not str(row.get("date") or "").startswith(str(year)):
            continue
        try:
            int(row.get("home_score") or -1)
            int(row.get("away_score") or -1)
        except (TypeError, ValueError):
            continue
        out.append(row)
    out.sort(key=lambda r: r.get("date") or "")
    return out


def _annotate_edition(rows: list[dict], *, competition: str, year: int) -> list[TournamentMatch]:
    team_counts: dict[str, int] = {}
    total = len(rows)
    matches: list[TournamentMatch] = []
    for i, row in enumerate(rows, start=1):
        home = _normalize_team(row.get("home_team") or "")
        away = _normalize_team(row.get("away_team") or "")
        if not home or not away:
            continue
        hg = int(row.get("home_score") or 0)
        ag = int(row.get("away_score") or 0)
        neutral = str(row.get("neutral") or "").upper() in ("TRUE", "1", "YES")
        hb = team_counts.get(home, 0)
        ab = team_counts.get(away, 0)
        date_raw = str(row.get("date") or "")
        matches.append(
            TournamentMatch(
                competition=competition,
                edition=f"{competition} {year}",
                year=year,
                date=date_raw,
                date_sort=_parse_date(date_raw),
                home=home,
                away=away,
                fthg=hg,
                ftag=ag,
                neutral=neutral,
                city=str(row.get("city") or ""),
                country=str(row.get("country") or ""),
                edition_index=i,
                phase=_phase_for_index(competition, i, total),
                home_games_before=hb,
                away_games_before=ab,
            )
        )
        team_counts[home] = hb + 1
        team_counts[away] = ab + 1
    return matches


def load_tournament_matches(
    *,
    world_cup_years: tuple[int, ...] = WORLD_CUP_YEARS,
    euro_years: tuple[int, ...] = EURO_YEARS,
    copa_years: tuple[int, ...] = COPA_YEARS,
    csv_text: str | None = None,
) -> list[TournamentMatch]:
    if csv_text is None:
        csv_text = fetch_international_csv()
    raw_rows = list(csv.DictReader(io.StringIO(csv_text)))
    all_matches: list[TournamentMatch] = []
    for year in world_cup_years:
        batch = _filter_edition_rows(raw_rows, competition="FIFA World Cup", year=year)
        all_matches.extend(_annotate_edition(batch, competition="FIFA World Cup", year=year))
    for year in euro_years:
        batch = _filter_edition_rows(raw_rows, competition="UEFA Euro", year=year)
        all_matches.extend(_annotate_edition(batch, competition="UEFA Euro", year=year))
    for year in copa_years:
        batch = _filter_edition_rows(raw_rows, competition="Copa América", year=year)
        all_matches.extend(_annotate_edition(batch, competition="Copa América", year=year))
    all_matches.sort(key=lambda m: (m.date_sort, m.competition, m.edition_index))
    return all_matches