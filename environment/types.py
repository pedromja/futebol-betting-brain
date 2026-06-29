from dataclasses import dataclass, field  # field used by MatchEnvironment
from enum import Enum


class WeatherCondition(Enum):
    CLEAR = "clear"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    STRONG_WIND = "strong_wind"
    EXTREME_HEAT = "extreme_heat"
    COLD = "cold"
    SNOW = "snow"


class ClimateZone(Enum):
    TEMPERATE = "temperate"
    WARM = "warm"
    COLD = "cold"
    DRY = "dry"


CONDITION_LABELS = {
    WeatherCondition.CLEAR: "Céu limpo / condições normais",
    WeatherCondition.LIGHT_RAIN: "Chuva ligeira",
    WeatherCondition.HEAVY_RAIN: "Chuva forte",
    WeatherCondition.STRONG_WIND: "Vento forte",
    WeatherCondition.EXTREME_HEAT: "Calor extremo",
    WeatherCondition.COLD: "Frio intenso",
    WeatherCondition.SNOW: "Neve / gelo",
}


@dataclass
class VenueProfile:
    team: str
    city: str = ""
    stadium: str = ""
    country: str = "PT"
    altitude_m: float = 0.0
    climate: ClimateZone = ClimateZone.TEMPERATE


@dataclass
class WeatherForecast:
    condition: WeatherCondition = WeatherCondition.CLEAR
    temperature_c: float = 15.0
    precipitation_mm: float = 0.0
    wind_kmh: float = 10.0
    humidity_pct: float = 50.0

    @property
    def computed_severity(self) -> float:
        base = {
            WeatherCondition.CLEAR: 0.0,
            WeatherCondition.LIGHT_RAIN: 0.35,
            WeatherCondition.HEAVY_RAIN: 0.75,
            WeatherCondition.STRONG_WIND: 0.65,
            WeatherCondition.EXTREME_HEAT: 0.70,
            WeatherCondition.COLD: 0.55,
            WeatherCondition.SNOW: 0.90,
        }[self.condition]

        precip_boost = min(self.precipitation_mm / 25.0, 0.25)
        wind_boost = min(max(self.wind_kmh - 30, 0) / 50.0, 0.20)
        temp_boost = 0.0
        if self.temperature_c > 32:
            temp_boost = min((self.temperature_c - 32) / 10.0, 0.20)
        elif self.temperature_c < 5:
            temp_boost = min((5 - self.temperature_c) / 10.0, 0.20)

        return min(1.0, base + precip_boost + wind_boost + temp_boost)


@dataclass
class TravelContext:
    away_distance_km: float = 0.0
    away_travel_hours: float = 0.0
    timezone_diff: int = 0


@dataclass
class EnvironmentalImpactDetail:
    factor: str
    attack_delta: float
    defense_delta: float
    formula_steps: list[str] = field(default_factory=list)


@dataclass
class MatchEnvironment:
    venue: VenueProfile
    home_profile: VenueProfile
    away_profile: VenueProfile
    weather: WeatherForecast
    travel: TravelContext
    source: str = "manual"
    weather_source: str = "sample"
    weather_fetched_at: str = ""
    venue_resolved_name: str = ""
    venue_resolve_source: str = ""
    venue_discovery_source: str = ""
    venue_discovery_steps: list[str] = field(default_factory=list)