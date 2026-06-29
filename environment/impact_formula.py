"""
Fórmulas de distorção por condições ambientais.

METEOROLOGIA — por equipa t (casa/fora):
    S_w = severidade da condição [0, 1] (chuva, vento, temperatura)
    A_t = fator de assimetria: casa=0.35 (aclimatada ao local), fora=1.0
    C_t = choque climático: 1 + 0.25×choque (equipa de clima quente no frio, etc.)

    Δataque_meteo = -W_m.ataque × S_w × A_t × C_t
    Δdefesa_meteo = +W_m.defesa × S_w × A_t × C_t

ALTITUDE — equipa visitante sobe de h_natal para h_venue:
    Δh = max(0, h_venue - h_equipa_natal)
    I_alt = min(Δh / 1000, 1.0)

    Visitante:  Δataque = -0.18 × I_alt,  Δdefesa = +0.10 × I_alt
    Casa (alta): Δataque = +0.06 × I_alt   (vantagem de aclimatação)

VIAGEM — só equipa visitante:
    I_dist = min(max(0, km-300)/1500, 0.65)
    I_time = min(max(0, horas-3)/8, 0.30)
    I_tz   = 0.08 × min(fusos, 3)
    I_travel = min(I_dist + I_time + I_tz, 1.0)

    Δataque = -0.20 × I_travel
    Δdefesa = +0.09 × I_travel

Agregação (igual às notícias):
    Δ_total = tanh(Σ Δ_i × 2) / 2
    M = clamp(1 + Δ_total, limites)
"""

from dataclasses import dataclass
from math import tanh

from models.team_stats import MatchInput, TeamForm

from .types import (
    CONDITION_LABELS,
    ClimateZone,
    EnvironmentalImpactDetail,
    MatchEnvironment,
    WeatherCondition,
)


@dataclass
class TeamEnvironmentalDistortion:
    team_name: str
    is_home: bool
    attack_multiplier: float
    defense_multiplier: float
    total_distortion: float
    attack_delta_total: float
    defense_delta_total: float
    details: list[EnvironmentalImpactDetail]
    original_attack: float
    original_defense: float
    adjusted_attack: float
    adjusted_defense: float


WEATHER_WEIGHTS: dict[WeatherCondition, dict[str, float]] = {
    WeatherCondition.CLEAR: {"attack": 0.0, "defense": 0.0},
    WeatherCondition.LIGHT_RAIN: {"attack": 0.06, "defense": 0.02},
    WeatherCondition.HEAVY_RAIN: {"attack": 0.12, "defense": 0.05},
    WeatherCondition.STRONG_WIND: {"attack": 0.09, "defense": 0.03},
    WeatherCondition.EXTREME_HEAT: {"attack": 0.14, "defense": 0.06},
    WeatherCondition.COLD: {"attack": 0.10, "defense": 0.04},
    WeatherCondition.SNOW: {"attack": 0.18, "defense": 0.08},
}

HOME_ACCLIMATION = 0.35
AWAY_EXPOSURE = 1.0

ALTITUDE_ATTACK_AWAY = 0.18
ALTITUDE_DEFENSE_AWAY = 0.10
ALTITUDE_ATTACK_HOME_BOOST = 0.06

TRAVEL_ATTACK = 0.20
TRAVEL_DEFENSE = 0.09


class EnvironmentFormula:
    def _climate_shock(self, team_climate: ClimateZone, weather_temp: float) -> float:
        shock = 0.0
        if team_climate == ClimateZone.WARM and weather_temp < 10:
            shock = min((10 - weather_temp) / 15.0, 1.0)
        elif team_climate == ClimateZone.COLD and weather_temp > 28:
            shock = min((weather_temp - 28) / 12.0, 1.0)
        elif team_climate == ClimateZone.DRY and weather_temp < 5:
            shock = min((5 - weather_temp) / 10.0, 0.6)
        return 1.0 + 0.25 * shock

    def _weather_impact(
        self, env: MatchEnvironment, is_home: bool, team_climate: ClimateZone
    ) -> EnvironmentalImpactDetail:
        w = env.weather
        severity = w.computed_severity
        asymmetry = HOME_ACCLIMATION if is_home else AWAY_EXPOSURE
        climate_mult = self._climate_shock(team_climate, w.temperature_c)
        weights = WEATHER_WEIGHTS[w.condition]

        attack_delta = -weights["attack"] * severity * asymmetry * climate_mult
        defense_delta = weights["defense"] * severity * asymmetry * climate_mult

        side = "casa" if is_home else "fora"
        label = CONDITION_LABELS[w.condition]
        steps = [
            f"Meteorologia ({side}): {label}",
            f"S_w={severity:.3f} (temp {w.temperature_c:.0f}°C, "
            f"chuva {w.precipitation_mm:.0f}mm, vento {w.wind_kmh:.0f}km/h)",
            f"A_t={asymmetry:.2f} ({'aclimatada ao local' if is_home else 'visitante exposto'})",
            f"C_t={climate_mult:.3f} (choque climático)",
            f"Δataque = -{weights['attack']:.2f} × {severity:.3f} × "
            f"{asymmetry:.2f} × {climate_mult:.3f} = {attack_delta:+.4f}",
            f"Δdefesa = +{weights['defense']:.2f} × {severity:.3f} × "
            f"{asymmetry:.2f} × {climate_mult:.3f} = {defense_delta:+.4f}",
        ]

        return EnvironmentalImpactDetail(
            factor="meteorologia",
            attack_delta=attack_delta,
            defense_delta=defense_delta,
            formula_steps=steps,
        )

    def _altitude_impact(
        self, env: MatchEnvironment, is_home: bool
    ) -> EnvironmentalImpactDetail | None:
        venue_alt = env.venue.altitude_m
        if is_home:
            away_alt = env.away_profile.altitude_m
            delta_h = max(0, venue_alt - away_alt)
            if delta_h < 150:
                return None
            intensity = min(delta_h / 1000.0, 1.0)
            attack_delta = ALTITUDE_ATTACK_HOME_BOOST * intensity
            defense_delta = -0.02 * intensity
            steps = [
                f"Altitude (casa): vantagem de jogar aos {venue_alt:.0f}m",
                f"Δh visitante = {delta_h:.0f}m → I_alt={intensity:.3f}",
                f"Δataque = +{ALTITUDE_ATTACK_HOME_BOOST:.2f} × {intensity:.3f} = {attack_delta:+.4f}",
                f"Δdefesa = {defense_delta:+.4f} (defesa ligeiramente mais sólida)",
            ]
        else:
            away_alt = env.away_profile.altitude_m
            delta_h = max(0, venue_alt - away_alt)
            if delta_h < 150:
                return None
            intensity = min(delta_h / 1000.0, 1.0)
            attack_delta = -ALTITUDE_ATTACK_AWAY * intensity
            defense_delta = ALTITUDE_DEFENSE_AWAY * intensity
            steps = [
                f"Altitude (fora): estadio {venue_alt:.0f}m vs natal {away_alt:.0f}m",
                f"Δh = {delta_h:.0f}m → I_alt = min(Δh/1000, 1) = {intensity:.3f}",
                f"Δataque = -{ALTITUDE_ATTACK_AWAY:.2f} × {intensity:.3f} = {attack_delta:+.4f}",
                f"Δdefesa = +{ALTITUDE_DEFENSE_AWAY:.2f} × {intensity:.3f} = {defense_delta:+.4f}",
            ]

        return EnvironmentalImpactDetail(
            factor="altitude",
            attack_delta=attack_delta,
            defense_delta=defense_delta,
            formula_steps=steps,
        )

    def _travel_impact(self, env: MatchEnvironment) -> EnvironmentalImpactDetail | None:
        t = env.travel
        if t.away_distance_km < 100 and t.away_travel_hours < 1.5:
            return None

        i_dist = min(max(0, t.away_distance_km - 300) / 1500.0, 0.65)
        i_time = min(max(0, t.away_travel_hours - 3) / 8.0, 0.30)
        i_tz = 0.08 * min(abs(t.timezone_diff), 3)
        intensity = min(i_dist + i_time + i_tz, 1.0)

        if intensity < 0.05:
            return None

        attack_delta = -TRAVEL_ATTACK * intensity
        defense_delta = TRAVEL_DEFENSE * intensity

        steps = [
            "Viagem (fora): fadiga de deslocação",
            f"I_dist = min(max(0, {t.away_distance_km:.0f}-300)/1500, 0.65) = {i_dist:.3f}",
            f"I_time = min(max(0, {t.away_travel_hours:.1f}-3)/8, 0.30) = {i_time:.3f}",
            f"I_tz = 0.08 × {min(abs(t.timezone_diff), 3)} = {i_tz:.3f}",
            f"I_travel = min(I_dist+I_time+I_tz, 1) = {intensity:.3f}",
            f"Δataque = -{TRAVEL_ATTACK:.2f} × {intensity:.3f} = {attack_delta:+.4f}",
            f"Δdefesa = +{TRAVEL_DEFENSE:.2f} × {intensity:.3f} = {defense_delta:+.4f}",
        ]

        return EnvironmentalImpactDetail(
            factor="viagem",
            attack_delta=attack_delta,
            defense_delta=defense_delta,
            formula_steps=steps,
        )

    def compute_team_distortion(
        self,
        team: TeamForm,
        env: MatchEnvironment,
        is_home: bool,
    ) -> TeamEnvironmentalDistortion | None:
        profile = env.home_profile if is_home else env.away_profile
        details: list[EnvironmentalImpactDetail] = []

        weather_detail = self._weather_impact(env, is_home, profile.climate)
        if env.weather.computed_severity > 0.01:
            details.append(weather_detail)

        alt_detail = self._altitude_impact(env, is_home)
        if alt_detail:
            details.append(alt_detail)

        if not is_home:
            travel_detail = self._travel_impact(env)
            if travel_detail:
                details.append(travel_detail)

        if not details:
            return None

        raw_attack = sum(d.attack_delta for d in details)
        raw_defense = sum(d.defense_delta for d in details)
        attack_delta_total = tanh(raw_attack * 2) / 2
        defense_delta_total = tanh(raw_defense * 2) / 2

        attack_mult = max(0.65, min(1.15, 1 + attack_delta_total))
        defense_mult = max(0.90, min(1.40, 1 + defense_delta_total))

        return TeamEnvironmentalDistortion(
            team_name=team.name,
            is_home=is_home,
            attack_multiplier=attack_mult,
            defense_multiplier=defense_mult,
            total_distortion=abs(attack_mult - 1) + abs(defense_mult - 1),
            attack_delta_total=attack_delta_total,
            defense_delta_total=defense_delta_total,
            details=details,
            original_attack=team.goals_scored_avg,
            original_defense=team.goals_conceded_avg,
            adjusted_attack=team.goals_scored_avg * attack_mult,
            adjusted_defense=team.goals_conceded_avg * defense_mult,
        )

    def adjust_match(
        self,
        match: MatchInput,
        env: MatchEnvironment | None,
    ) -> tuple[MatchInput, TeamEnvironmentalDistortion | None, TeamEnvironmentalDistortion | None]:
        if not env:
            return match, None, None

        home_dist = self.compute_team_distortion(match.home, env, is_home=True)
        away_dist = self.compute_team_distortion(match.away, env, is_home=False)

        if not home_dist and not away_dist:
            return match, None, None

        home_attack = (
            home_dist.adjusted_attack if home_dist else match.home.goals_scored_avg
        )
        home_defense = (
            home_dist.adjusted_defense if home_dist else match.home.goals_conceded_avg
        )
        away_attack = (
            away_dist.adjusted_attack if away_dist else match.away.goals_scored_avg
        )
        away_defense = (
            away_dist.adjusted_defense if away_dist else match.away.goals_conceded_avg
        )

        adjusted = MatchInput(
            home=TeamForm(
                name=match.home.name,
                goals_scored_avg=home_attack,
                goals_conceded_avg=home_defense,
                games_played=match.home.games_played,
                scored_in_last_n=match.home.scored_in_last_n,
                conceded_in_last_n=match.home.conceded_in_last_n,
                last_n=match.home.last_n,
            ),
            away=TeamForm(
                name=match.away.name,
                goals_scored_avg=away_attack,
                goals_conceded_avg=away_defense,
                games_played=match.away.games_played,
                scored_in_last_n=match.away.scored_in_last_n,
                conceded_in_last_n=match.away.conceded_in_last_n,
                last_n=match.away.last_n,
            ),
            odds=match.odds,
            league=match.league,
            date=match.date,
            home_advantage=match.home_advantage,
            league_avg_goals=match.league_avg_goals,
        )

        return adjusted, home_dist, away_dist