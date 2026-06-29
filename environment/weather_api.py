"""
Cliente OpenWeatherMap — meteorologia em tempo real / previsão.

API gratuita: https://openweathermap.org/api
Variável de ambiente: OPENWEATHERMAP_API_KEY

Usa previsão horária (5 dias) se a data do jogo estiver dentro da janela;
caso contrário usa condições atuais no local do estádio.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from .types import WeatherCondition, WeatherForecast


class OpenWeatherClient:
    BASE = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENWEATHERMAP_API_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _map_condition(
        weather_main: str,
        weather_id: int,
        rain_mm: float,
        wind_kmh: float,
        temp_c: float,
    ) -> WeatherCondition:
        if 600 <= weather_id < 700:
            return WeatherCondition.SNOW
        if rain_mm >= 8 or weather_id in (502, 503, 504, 522, 531):
            return WeatherCondition.HEAVY_RAIN
        if rain_mm > 0 or weather_main.lower() in ("rain", "drizzle", "thunderstorm"):
            return WeatherCondition.LIGHT_RAIN
        if wind_kmh >= 40:
            return WeatherCondition.STRONG_WIND
        if temp_c >= 32:
            return WeatherCondition.EXTREME_HEAT
        if temp_c <= 5:
            return WeatherCondition.COLD
        return WeatherCondition.CLEAR

    def _parse_current(self, data: dict) -> WeatherForecast:
        main = data.get("main", {})
        wind = data.get("wind", {})
        rain = data.get("rain", {})
        weather = data.get("weather", [{}])[0]

        temp = main.get("temp", 15)
        wind_kmh = wind.get("speed", 0) * 3.6
        rain_mm = rain.get("1h", rain.get("3h", 0))
        humidity = main.get("humidity", 50)
        wmain = weather.get("main", "Clear")
        wid = weather.get("id", 800)

        condition = self._map_condition(wmain, wid, rain_mm, wind_kmh, temp)
        return WeatherForecast(
            condition=condition,
            temperature_c=temp,
            precipitation_mm=rain_mm,
            wind_kmh=wind_kmh,
            humidity_pct=humidity,
        )

    def _parse_forecast_entry(self, entry: dict) -> WeatherForecast:
        main = entry.get("main", {})
        wind = entry.get("wind", {})
        rain = entry.get("rain", {})
        weather = entry.get("weather", [{}])[0]

        temp = main.get("temp", 15)
        wind_kmh = wind.get("speed", 0) * 3.6
        rain_mm = rain.get("3h", 0)
        humidity = main.get("humidity", 50)
        wmain = weather.get("main", "Clear")
        wid = weather.get("id", 800)

        condition = self._map_condition(wmain, wid, rain_mm, wind_kmh, temp)
        return WeatherForecast(
            condition=condition,
            temperature_c=temp,
            precipitation_mm=rain_mm,
            wind_kmh=wind_kmh,
            humidity_pct=humidity,
        )

    def _request(self, endpoint: str, params: dict) -> dict | None:
        params["appid"] = self.api_key
        params["units"] = "metric"
        params["lang"] = "pt"
        url = f"{self.BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None

    def fetch_current(
        self, city: str, lat: float | None = None, lon: float | None = None
    ) -> tuple[WeatherForecast | None, str]:
        if lat is not None and lon is not None:
            data = self._request("weather", {"lat": lat, "lon": lon})
        else:
            data = self._request("weather", {"q": city})
        if not data or data.get("cod") not in (200, "200"):
            return None, "error"
        return self._parse_current(data), "openweathermap_current"

    def fetch_forecast(
        self,
        city: str,
        match_date: str,
        lat: float | None = None,
        lon: float | None = None,
        kickoff_hour: int = 20,
    ) -> tuple[WeatherForecast | None, str]:
        if lat is not None and lon is not None:
            data = self._request("forecast", {"lat": lat, "lon": lon})
        else:
            data = self._request("forecast", {"q": city})

        if not data or str(data.get("cod")) != "200":
            return None, "error"

        try:
            target = datetime.strptime(match_date, "%Y-%m-%d").replace(
                hour=kickoff_hour, minute=0
            )
        except ValueError:
            return None, "error"

        now = datetime.now()
        if target < now or target > now + timedelta(days=5):
            return None, "out_of_range"

        best_entry = None
        best_delta = timedelta(days=999)
        for entry in data.get("list", []):
            dt_txt = entry.get("dt_txt", "")
            try:
                slot = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            delta = abs(slot - target)
            if delta < best_delta:
                best_delta = delta
                best_entry = entry

        if not best_entry:
            return None, "error"

        return self._parse_forecast_entry(best_entry), "openweathermap_forecast"

    def fetch_for_match(
        self,
        city: str,
        match_date: str = "",
        lat: float | None = None,
        lon: float | None = None,
    ) -> tuple[WeatherForecast | None, str]:
        if not self.is_configured:
            return None, "no_api_key"

        if match_date:
            forecast, source = self.fetch_forecast(city, match_date, lat, lon)
            if forecast:
                return forecast, source

        return self.fetch_current(city, lat, lon)