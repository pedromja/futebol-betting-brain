import json
from datetime import datetime
from pathlib import Path

from discovery.auto import DiscoveredVenue, MatchAutoDiscovery
from environment.geo import estimate_travel_hours, haversine_km
from environment.types import (
    ClimateZone,
    MatchEnvironment,
    TravelContext,
    VenueProfile,
    WeatherCondition,
    WeatherForecast,
)
from environment.venue_registry import VenueQuery, VenueRecord, VenueRegistry
from environment.weather_api import OpenWeatherClient
from models.team_stats import MatchInput, MatchOdds, TeamForm
from stakes.types import TeamStake

_DATA_DIR = Path(__file__).parent


def _team_from_dict(data: dict) -> TeamForm:
    return TeamForm(
        name=data["name"],
        goals_scored_avg=data["goals_scored_avg"],
        goals_conceded_avg=data["goals_conceded_avg"],
        games_played=data.get("games_played", 10),
        scored_in_last_n=data.get("scored_in_last_n", 7),
        conceded_in_last_n=data.get("conceded_in_last_n", 6),
        last_n=data.get("last_n", 10),
    )


def _odds_from_dict(data: dict) -> MatchOdds:
    return MatchOdds(
        home_win=data["home_win"],
        draw=data["draw"],
        away_win=data["away_win"],
        over_25=data["over_25"],
        under_25=data["under_25"],
        btts_yes=data["btts_yes"],
        btts_no=data["btts_no"],
        double_chance_1x=data.get("double_chance_1x", 0),
        double_chance_x2=data.get("double_chance_x2", 0),
        double_chance_12=data.get("double_chance_12", 0),
    )


def match_from_dict(data: dict) -> MatchInput:
    home_stake = None
    away_stake = None
    if data.get("home_stake"):
        home_stake = TeamStake.from_string(str(data["home_stake"]))
    if data.get("away_stake"):
        away_stake = TeamStake.from_string(str(data["away_stake"]))

    return MatchInput(
        home=_team_from_dict(data["home"]),
        away=_team_from_dict(data["away"]),
        odds=_odds_from_dict(data["odds"]),
        league=data.get("league", ""),
        date=data.get("date", ""),
        home_advantage=data.get("home_advantage", 1.15),
        league_avg_goals=data.get("league_avg_goals", 1.35),
        venue_stadium=data.get("venue_stadium", ""),
        venue_city=data.get("venue_city", ""),
        venue_country=data.get("venue_country", "PT"),
        home_stake=home_stake,
        away_stake=away_stake,
    )


def load_sample(key: str) -> MatchInput:
    path = _DATA_DIR / "sample_matches.json"
    with open(path, encoding="utf-8") as f:
        samples = json.load(f)
    if key not in samples:
        available = ", ".join(samples.keys())
        raise KeyError(f"Jogo '{key}' não encontrado. Disponíveis: {available}")
    return match_from_dict(samples[key])


def list_samples() -> list[str]:
    path = _DATA_DIR / "sample_matches.json"
    with open(path, encoding="utf-8") as f:
        samples = json.load(f)
    return list(samples.keys())


def _load_sample_environment_raw(key: str) -> dict | None:
    path = _DATA_DIR / "sample_environment.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        samples = json.load(f)
    return samples.get(key)


def _venue_from_dict(data: dict) -> VenueProfile:
    return VenueProfile(
        team=data["team"],
        city=data.get("city", ""),
        stadium=data.get("stadium", ""),
        country=data.get("country", "PT"),
        altitude_m=data.get("altitude_m", 0),
        climate=ClimateZone(data.get("climate", "temperate")),
    )


def _build_environment(
    match: MatchInput,
    discovered: DiscoveredVenue | None,
    registry: VenueRegistry,
    sample_hint: dict | None = None,
) -> MatchEnvironment:
    country = match.venue_country or MatchAutoDiscovery.infer_country(match.league)

    home_profile = VenueProfile(
        team=match.home.name,
        city=match.home.name,
        country=country,
    )
    away_profile = VenueProfile(
        team=match.away.name,
        city=match.away.name,
        country=country,
    )

    if sample_hint:
        home_profile = _venue_from_dict(sample_hint["home_profile"])
        away_profile = _venue_from_dict(sample_hint["away_profile"])
        if discovered and discovered.stadium:
            home_profile.stadium = discovered.stadium
            home_profile.city = discovered.city or home_profile.city

    default_weather = WeatherForecast()
    if sample_hint and sample_hint.get("weather"):
        w = sample_hint["weather"]
        default_weather = WeatherForecast(
            condition=WeatherCondition(w.get("condition", "clear")),
            temperature_c=w.get("temperature_c", 15),
            precipitation_mm=w.get("precipitation_mm", 0),
            wind_kmh=w.get("wind_kmh", 10),
            humidity_pct=w.get("humidity_pct", 50),
        )

    env = MatchEnvironment(
        venue=VenueProfile(
            team=match.home.name,
            city=match.venue_city or home_profile.city,
            stadium=match.venue_stadium or home_profile.stadium,
            country=country,
            altitude_m=sample_hint.get("venue_altitude_m", 0) if sample_hint else 0,
            climate=home_profile.climate,
        ),
        home_profile=home_profile,
        away_profile=away_profile,
        weather=default_weather,
        travel=TravelContext(),
        source="auto",
        weather_source="sample",
    )

    if discovered:
        env.venue_resolved_name = discovered.stadium or discovered.city
        env.venue_resolve_source = discovered.source
        env.venue_corrected_from_usual = discovered.corrected_from_usual
        env.venue_usual_home = discovered.usual_home_stadium
        env.venue_verification_sources = list(discovered.verification_sources)
        env.is_neutral_venue = not discovered.is_home_venue
        if discovered.stadium:
            env.venue.stadium = discovered.stadium
        if discovered.city:
            env.venue.city = discovered.city
        if discovered.country:
            env.venue.country = discovered.country

    return env


def _resolve_venue_record(
    env: MatchEnvironment,
    registry: VenueRegistry,
    auto_geocode: bool,
) -> VenueRecord | None:
    query = VenueQuery(
        stadium=env.venue.stadium,
        city=env.venue.city,
        country=env.venue.country,
        team=env.venue.team,
    )
    record, source = registry.resolve(query, auto_geocode=auto_geocode)
    if record:
        env.venue_resolved_name = record.display_name
        env.venue_resolve_source = source
        env.venue.altitude_m = record.altitude_m or env.venue.altitude_m
        if record.city:
            env.venue.city = record.city
        if record.stadium:
            env.venue.stadium = record.stadium
    return record


def _enrich_travel_from_registry(
    env: MatchEnvironment,
    registry: VenueRegistry,
    auto_geocode: bool,
) -> None:
    venue_rec = _resolve_venue_record(env, registry, auto_geocode)
    if not venue_rec:
        return

    away_query = VenueQuery(
        stadium=env.away_profile.stadium,
        city=env.away_profile.city,
        country=env.away_profile.country,
        team=env.away_profile.team,
    )
    away_rec, _ = registry.resolve(away_query, auto_geocode=auto_geocode)

    home_query = VenueQuery(
        team=env.home_profile.team,
        country=env.home_profile.country,
    )
    home_rec, _ = registry.resolve(home_query, auto_geocode=auto_geocode)
    if home_rec and home_rec.altitude_m:
        env.home_profile.altitude_m = home_rec.altitude_m
        if home_rec.city:
            env.home_profile.city = home_rec.city
        if home_rec.stadium:
            env.home_profile.stadium = home_rec.stadium

    if away_rec:
        if away_rec.altitude_m:
            env.away_profile.altitude_m = away_rec.altitude_m
        distance = haversine_km(
            venue_rec.lat, venue_rec.lon, away_rec.lat, away_rec.lon
        )
        env.travel.away_distance_km = round(distance, 1)
        env.travel.away_travel_hours = round(estimate_travel_hours(distance), 1)


def _fetch_live_weather(
    env: MatchEnvironment,
    match_date: str,
    weather_api_key: str | None,
    registry: VenueRegistry,
    auto_geocode: bool,
) -> None:
    client = OpenWeatherClient(api_key=weather_api_key)
    if not client.is_configured:
        return

    venue_rec = _resolve_venue_record(env, registry, auto_geocode)
    if not venue_rec:
        return

    env.venue.altitude_m = venue_rec.altitude_m

    weather, source = client.fetch_for_match(
        city=venue_rec.city or env.venue.city,
        match_date=match_date,
        lat=venue_rec.lat,
        lon=venue_rec.lon,
    )

    if weather:
        env.weather = weather
        env.weather_source = source
        env.weather_fetched_at = datetime.now().isoformat(timespec="seconds")


def load_environment_for_match(
    match: MatchInput,
    match_key: str | None = None,
    weather_api_key: str | None = None,
    live_weather: bool = True,
    discovered_venue: DiscoveredVenue | None = None,
) -> tuple[MatchEnvironment | None, DiscoveredVenue | None]:
    """
    Constrói ambiente automaticamente. O estádio é descoberto sem input humano.
    """
    sample_hint = _load_sample_environment_raw(match_key) if match_key else None
    registry = VenueRegistry(api_key=weather_api_key)
    auto_geocode = bool(registry.api_key)

    if discovered_venue is None:
        auto = MatchAutoDiscovery(weather_api_key=weather_api_key)
        match, discovered_venue = auto.apply_venue_to_match(match)

    env = _build_environment(match, discovered_venue, registry, sample_hint)
    _enrich_travel_from_registry(env, registry, auto_geocode=auto_geocode)

    if live_weather:
        _fetch_live_weather(
            env, match.date, weather_api_key, registry, auto_geocode
        )

    env.venue_discovery_source = discovered_venue.source if discovered_venue else ""
    env.venue_discovery_steps = (
        discovered_venue.discovery_steps if discovered_venue else []
    )

    return env, discovered_venue