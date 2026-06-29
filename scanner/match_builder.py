"""Constrói MatchInput a partir de um fixture descoberto automaticamente."""

from datetime import datetime

from discovery.fixture_scanner import UpcomingFixture
from discovery.team_stats_fetcher import TeamStatsFetcher
from models.team_stats import MatchInput, MatchOdds, TeamForm
from odds.provider import OddsProvider
from stakes.auto import infer_match_stakes


LEAGUE_DEFAULTS: dict[str, tuple[float, float]] = {
    "primeira liga": (1.35, 1.35),
    "liga portugal": (1.20, 1.25),
    "premier league": (1.45, 1.45),
    "la liga": (1.30, 1.30),
    "serie a": (1.35, 1.35),
    "bundesliga": (1.50, 1.50),
    "champions": (1.40, 1.40),
    "fifa world cup": (2.65, 1.12),
    "world cup": (2.65, 1.12),
    "europa league": (1.38, 1.38),
    "eredivisie": (1.55, 1.55),
    "ligue 1": (1.35, 1.35),
}


def _default_stats(league: str) -> tuple[float, float]:
    key = league.lower()
    for pattern, stats in LEAGUE_DEFAULTS.items():
        if pattern in key:
            return stats
    return 1.30, 1.30


def _league_avg_goals(league: str) -> float:
    scored, _ = _default_stats(league)
    return scored


def _team_from_hint(name: str, hint: dict, league: str) -> TeamForm:
    scored, conceded = _default_stats(league)
    if hint:
        home_h = hint.get("home", {})
        away_h = hint.get("away", {})
        side = home_h if name == hint.get("home_name") else away_h
        if side:
            scored = side.get("scored_avg", scored)
            conceded = side.get("conceded_avg", conceded)
    return TeamForm(
        name=name,
        goals_scored_avg=scored,
        goals_conceded_avg=conceded,
    )


def _odds_dict_from_fetch(fetched) -> dict:
    o = fetched.match_odds
    return {
        "home_win": o.home_win,
        "draw": o.draw,
        "away_win": o.away_win,
        "over_25": o.over_25,
        "under_25": o.under_25,
        "btts_yes": o.btts_yes,
        "btts_no": o.btts_no,
        "double_chance_1x": o.double_chance_1x,
        "double_chance_x2": o.double_chance_x2,
        "double_chance_12": o.double_chance_12,
    }


def build_match(
    fixture: UpcomingFixture,
    odds_provider: OddsProvider | None = None,
    stats_fetcher: TeamStatsFetcher | None = None,
) -> tuple[MatchInput | None, object | None]:
    if not fixture.home or not fixture.away:
        return None, None

    odds_data = fixture.odds_hint
    fetch_meta = None
    if odds_provider and not odds_data:
        fetch_meta = odds_provider.fetch_for_fixture(fixture)
        if fetch_meta:
            odds_data = _odds_dict_from_fetch(fetch_meta)

    if not odds_data:
        return None, None

    fetcher = stats_fetcher or TeamStatsFetcher()
    home_snap = fetcher.fetch_form(fixture.home)
    away_snap = fetcher.fetch_form(fixture.away)
    home = fetcher.to_team_form(fixture.home, home_snap)
    away = fetcher.to_team_form(fixture.away, away_snap)

    if fixture.stats_hint:
        ah = fixture.stats_hint.get("home", {})
        aa = fixture.stats_hint.get("away", {})
        if ah:
            home = TeamForm(
                name=fixture.home,
                goals_scored_avg=ah.get("scored_avg", home.goals_scored_avg),
                goals_conceded_avg=ah.get("conceded_avg", home.goals_conceded_avg),
            )
        if aa:
            away = TeamForm(
                name=fixture.away,
                goals_scored_avg=aa.get("scored_avg", away.goals_scored_avg),
                goals_conceded_avg=aa.get("conceded_avg", away.goals_conceded_avg),
            )

    kickoff_date = ""
    if fixture.kickoff_dt:
        kickoff_date = fixture.kickoff_dt.strftime("%Y-%m-%d")

    home_stake, away_stake = infer_match_stakes(fixture)

    return MatchInput(
        home=home,
        away=away,
        odds=MatchOdds(
            home_win=float(odds_data["home_win"]),
            draw=float(odds_data["draw"]),
            away_win=float(odds_data["away_win"]),
            over_25=float(odds_data["over_25"]),
            under_25=float(odds_data["under_25"]),
            btts_yes=float(odds_data["btts_yes"]),
            btts_no=float(odds_data["btts_no"]),
            double_chance_1x=float(odds_data.get("double_chance_1x", 0)),
            double_chance_x2=float(odds_data.get("double_chance_x2", 0)),
            double_chance_12=float(odds_data.get("double_chance_12", 0)),
        ),
        league=fixture.league,
        date=kickoff_date or datetime.now().strftime("%Y-%m-%d"),
        league_avg_goals=_league_avg_goals(fixture.league),
        home_stake=home_stake,
        away_stake=away_stake,
    ), fetch_meta