"""Agrega perfis condicionais por situação ao intervalo e janelas pós-HT (HTHG/HTAG)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from prematch.historical.aggregate import _closing_triple, _num, fetch_csv_text
from prematch.historical.names import canonical_team
from prematch.historical.sources import csv_url
from prematch.historical.types import SituationWindowMetrics, TeamSituationProfile

SECOND_HALF_SHARE = 0.52

# Janelas incrementais na 2.ª parte (minutos de jogo)
POST_HT_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("post_ht_0_15", 46, 60),
    ("post_ht_16_30", 61, 75),
    ("post_ht_31_45", 76, 90),
)

WINDOW_MINUTES: dict[str, int] = {
    "first_half": 45,
    "post_ht_0_15": 15,
    "post_ht_16_30": 15,
    "post_ht_31_45": 15,
}

SITUATIONS = (
    "fav_losing_at_ht",
    "fav_drawing_at_ht",
    "fav_winning_at_ht",
    "losing_at_ht",
    "drawing_at_ht",
    "winning_at_ht",
)


def _favorite_side(home_odd: float | None, away_odd: float | None) -> str | None:
    if home_odd is None or away_odd is None or home_odd <= 1 or away_odd <= 1:
        return None
    if abs(home_odd - away_odd) < 0.08:
        return None
    return "home" if home_odd < away_odd else "away"


def _ht_result(hg: float, ag: float) -> str:
    if hg > ag:
        return "winning_at_ht"
    if hg < ag:
        return "losing_at_ht"
    return "drawing_at_ht"


def _fav_situation(fav: str | None, side: str, ht_result: str) -> str | None:
    if fav != side:
        return None
    if ht_result == "losing_at_ht":
        return "fav_losing_at_ht"
    if ht_result == "drawing_at_ht":
        return "fav_drawing_at_ht"
    return "fav_winning_at_ht"


class _WindowAcc:
    def __init__(self) -> None:
        self.corners: list[float] = []
        self.goals_scored: list[float] = []
        self.goals_conceded: list[float] = []
        self.shots: list[float] = []
        self.sot: list[float] = []
        self.fouls: list[float] = []

    def add(
        self,
        *,
        corners: float | None,
        goals_scored: float | None,
        goals_conceded: float | None,
        shots: float | None,
        sot: float | None,
        fouls: float | None,
    ) -> None:
        if corners is not None:
            self.corners.append(corners)
        if goals_scored is not None:
            self.goals_scored.append(goals_scored)
        if goals_conceded is not None:
            self.goals_conceded.append(goals_conceded)
        if shots is not None:
            self.shots.append(shots)
        if sot is not None:
            self.sot.append(sot)
        if fouls is not None:
            self.fouls.append(fouls)

    def to_metrics(self) -> SituationWindowMetrics:
        def avg(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        n = max(
            len(self.goals_scored),
            len(self.corners),
            len(self.shots),
            len(self.fouls),
        )
        return SituationWindowMetrics(
            matches=n,
            corners_avg=avg(self.corners),
            goals_scored_avg=avg(self.goals_scored),
            goals_conceded_avg=avg(self.goals_conceded),
            shots_avg=avg(self.shots),
            sot_avg=avg(self.sot),
            fouls_avg=avg(self.fouls),
        )


def _window_fraction(window_id: str) -> float:
    return WINDOW_MINUTES.get(window_id, 15) / 45.0


def _ingest_team_match(
    acc: dict[tuple[str, str, str], _WindowAcc],
    *,
    team: str,
    venue: str,
    situation: str,
    hthg: float,
    htag: float,
    goals_2h: float,
    goals_conceded_2h: float,
    corners_ft: float | None,
    shots_ft: float | None,
    sot_ft: float | None,
    fouls_ft: float | None,
) -> None:
    corners_2h = (corners_ft or 0) * SECOND_HALF_SHARE
    shots_2h = (shots_ft or 0) * SECOND_HALF_SHARE
    sot_2h = (sot_ft or 0) * SECOND_HALF_SHARE
    fouls_2h = (fouls_ft or 0) * SECOND_HALF_SHARE

    key_1h = (venue, situation, "first_half")
    acc[key_1h].add(
        corners=(corners_ft or 0) * (1.0 - SECOND_HALF_SHARE) if corners_ft is not None else None,
        goals_scored=hthg,
        goals_conceded=htag,
        shots=(shots_ft or 0) * (1.0 - SECOND_HALF_SHARE) if shots_ft is not None else None,
        sot=(sot_ft or 0) * (1.0 - SECOND_HALF_SHARE) if sot_ft is not None else None,
        fouls=(fouls_ft or 0) * (1.0 - SECOND_HALF_SHARE) if fouls_ft is not None else None,
    )

    for window_id, _, _ in POST_HT_WINDOWS:
        frac = _window_fraction(window_id)
        key = (venue, situation, window_id)
        acc[key].add(
            corners=corners_2h * frac if corners_ft is not None else None,
            goals_scored=goals_2h * frac,
            goals_conceded=goals_conceded_2h * frac,
            shots=shots_2h * frac if shots_ft is not None else None,
            sot=sot_2h * frac if sot_ft is not None else None,
            fouls=fouls_2h * frac if fouls_ft is not None else None,
        )


def aggregate_situation_rows(
    rows: list[dict],
    *,
    league_code: str,
    season: str,
) -> list[TeamSituationProfile]:
    """Constrói perfis (equipa, situação, janela, venue) a partir de CSV com HTHG/HTAG."""
    acc: dict[str, dict[tuple[str, str, str], _WindowAcc]] = defaultdict(
        lambda: defaultdict(_WindowAcc)
    )

    for row in rows:
        home = canonical_team(row.get("HomeTeam") or "")
        away = canonical_team(row.get("AwayTeam") or "")
        if not home or not away:
            continue

        hthg = _num(row.get("HTHG"))
        htag = _num(row.get("HTAG"))
        fthg = _num(row.get("FTHG"))
        ftag = _num(row.get("FTAG"))
        if hthg is None or htag is None or fthg is None or ftag is None:
            continue

        ch, _, ca = _closing_triple(row)
        fav = _favorite_side(ch, ca)

        home_ht = _ht_result(hthg, htag)
        away_ht = _ht_result(htag, hthg)
        home_fav = _fav_situation(fav, "home", home_ht)
        away_fav = _fav_situation(fav, "away", away_ht)

        goals_2h_home = fthg - hthg
        goals_2h_away = ftag - htag

        for team, venue, sit in (
            (home, "home", home_ht),
            (away, "away", away_ht),
        ):
            _ingest_team_match(
                acc[team],
                team=team,
                venue=venue,
                situation=sit,
                hthg=hthg if venue == "home" else htag,
                htag=htag if venue == "home" else hthg,
                goals_2h=goals_2h_home if venue == "home" else goals_2h_away,
                goals_conceded_2h=goals_2h_away if venue == "home" else goals_2h_home,
                corners_ft=_num(row.get("HC") if venue == "home" else row.get("AC")),
                shots_ft=_num(row.get("HS") if venue == "home" else row.get("AS")),
                sot_ft=_num(row.get("HST") if venue == "home" else row.get("AST")),
                fouls_ft=_num(row.get("HF") if venue == "home" else row.get("AF")),
            )

        if home_fav:
            _ingest_team_match(
                acc[home],
                team=home,
                venue="home",
                situation=home_fav,
                hthg=hthg,
                htag=htag,
                goals_2h=goals_2h_home,
                goals_conceded_2h=goals_2h_away,
                corners_ft=_num(row.get("HC")),
                shots_ft=_num(row.get("HS")),
                sot_ft=_num(row.get("HST")),
                fouls_ft=_num(row.get("HF")),
            )
        if away_fav:
            _ingest_team_match(
                acc[away],
                team=away,
                venue="away",
                situation=away_fav,
                hthg=htag,
                htag=hthg,
                goals_2h=goals_2h_away,
                goals_conceded_2h=goals_2h_home,
                corners_ft=_num(row.get("AC")),
                shots_ft=_num(row.get("AS")),
                sot_ft=_num(row.get("AST")),
                fouls_ft=_num(row.get("AF")),
            )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    profiles: list[TeamSituationProfile] = []
    for team in sorted(acc):
        for (venue, situation, window), bucket in sorted(acc[team].items()):
            metrics = bucket.to_metrics()
            if metrics.matches < 1:
                continue
            profiles.append(
                TeamSituationProfile(
                    team=team,
                    league=league_code,
                    season=season,
                    venue=venue,
                    situation=situation,
                    window=window,
                    metrics=metrics,
                    updated_at=now,
                )
            )
    return profiles


def ingest_situation_league(
    league_code: str,
    *,
    season: str = "2526",
    csv_text: str | None = None,
) -> list[TeamSituationProfile]:
    if csv_text is None:
        url = csv_url(league_code, season)
        if not url:
            return []
        try:
            csv_text = fetch_csv_text(url)
        except (OSError, TimeoutError):
            return []

    import csv
    import io

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = [row for row in reader if row.get("HomeTeam")]
    return aggregate_situation_rows(rows, league_code=league_code, season=season)