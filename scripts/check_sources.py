#!/usr/bin/env python3
"""Valida se cada fonte de dados real está configurada e a responder."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.env import load_dotenv

load_dotenv(ROOT / ".env")

from discovery.api_football_client import ApiFootballClient
from discovery.fixture_scanner import FixtureScanner
from discovery.team_stats_fetcher import TeamStatsFetcher
from discovery.web_fixture_scanner import WebFixtureScanner
from discovery.x_client import XSearchClient
from environment.weather_api import OpenWeatherClient


def _status(ok: bool) -> str:
    return "OK" if ok else "FALHA"


def check_weather() -> bool:
    client = OpenWeatherClient()
    if not client.is_configured:
        print("  [ ] OPENWEATHERMAP_API_KEY — não definida")
        print("      → https://home.openweathermap.org/users/sign_up (grátis)")
        return False

    forecast, reason = client.fetch_current("Lisboa,PT")
    ok = forecast is not None and reason not in ("no_api_key", "error")
    print(f"  [{'x' if ok else ' '}] OPENWEATHERMAP_API_KEY — {_status(ok)}")
    if forecast:
        print(
            f"      Lisboa agora: {forecast.condition.value}, "
            f"{forecast.temperature_c:.0f}°C"
        )
    elif reason:
        print(f"      Motivo: {reason}")
    return ok


def check_xai() -> bool:
    client = XSearchClient()
    if not client.is_live:
        print("  [ ] XAI_API_KEY — não definida")
        print("      → https://console.x.ai/ (jogos, notícias, odds, estádio)")
        return False

    text, source = client.query(
        "Responde só com a palavra: ONLINE", days_back=1
    )
    ok = source == "x_search" and bool(text.strip())
    print(f"  [{'x' if ok else ' '}] XAI_API_KEY — {_status(ok)}")
    if ok:
        preview = text.strip().replace("\n", " ")[:60]
        print(f"      Resposta: {preview}")
    elif source.startswith("error"):
        print(f"      {source}")
    return ok


def check_web_scanner() -> bool:
    fixtures = WebFixtureScanner().scan(hours_ahead=12)
    web_hits = [f for f in fixtures if f.source != "sample"]
    ok = len(web_hits) > 0
    print(f"  [{'x' if ok else ' '}] Pesquisa web (ESPN/Bing/TheSportsDB) — {_status(ok)}")
    if web_hits:
        for fx in web_hits[:3]:
            print(f"      • {fx.label} ({fx.league}) [{fx.source}]")
        if len(web_hits) > 3:
            print(f"      … +{len(web_hits) - 3} jogos")
    else:
        print("      Nenhum jogo nas próximas 12h via web (pode ser dia sem jogos)")
    return ok


def check_api_football() -> bool:
    client = ApiFootballClient()
    if not client.is_configured:
        print("  [ ] API_FOOTBALL_KEY — não definida (opcional)")
        print("      → https://dashboard.api-football.com/")
        return False

    ok = client.ping()
    fixtures = client.scan_fixtures(hours_ahead=48) if ok else []
    live = client.scan_live() if ok else []
    print(f"  [{'x' if ok else ' '}] API_FOOTBALL_KEY — {_status(ok)}")
    quota = client.quota_hint()
    if quota:
        print(f"      Quota: {quota}")
    if fixtures:
        for fx in fixtures[:3]:
            print(f"      • {fx.label} ({fx.league}) [{fx.source}]")
        if len(fixtures) > 3:
            print(f"      … +{len(fixtures) - 3} jogos")
        scores = client.team_form_scores(fixtures[0].home, last_n=5)
        if scores:
            sc, cc = scores
            n = len(sc)
            print(
                f"      Stats {fixtures[0].home}: "
                f"{sum(sc)/n:.1f} marcados, {sum(cc)/n:.1f} sofridos ({n} jogos)"
            )
    else:
        print("      API OK — 0 jogos na janela 48h (pode ser dia calmo)")
    print(f"      Ao vivo agora: {len(live)} jogos (GET /fixtures?live=all)")
    if live:
        fx = live[0]
        print(f"      Ex: {fx.minute}' {fx.score_label} {fx.label}")
    return ok


def check_football_data() -> bool:
    key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    if not key:
        print("  [ ] FOOTBALL_DATA_API_KEY — não definida (opcional)")
        print("      → https://www.football-data.org/client/register")
        return False

    fetcher = TeamStatsFetcher(football_data_key=key)
    snap = fetcher._fetch_football_data("Netherlands")  # noqa: SLF001
    ok = (
        snap is not None
        and snap.source == "football-data.org"
        and snap.games_played >= 1
    )
    print(f"  [{'x' if ok else ' '}] FOOTBALL_DATA_API_KEY (stats) — {_status(ok)}")
    if snap:
        print(
            f"      Netherlands: {snap.scored_avg} marcados, "
            f"{snap.conceded_avg} sofridos, {snap.games_played} jogos"
        )
    else:
        print("      Não foi possível obter forma via football-data.org")
    return ok


def check_scanner_combo() -> bool:
    scanner = FixtureScanner(
        xai_api_key=os.getenv("XAI_API_KEY"),
        football_data_key=os.getenv("FOOTBALL_DATA_API_KEY"),
        hours_ahead=12,
    )
    fixtures = scanner.scan()
    ok = len(fixtures) > 0
    print(f"  [{'x' if ok else ' '}] Scanner completo (web + APIs) — {_status(ok)}")
    if fixtures:
        for fx in fixtures[:3]:
            print(f"      • {fx.label} ({fx.league}) [{fx.source}]")
        if len(fixtures) > 3:
            print(f"      … +{len(fixtures) - 3} jogos")
    else:
        print("      Sem jogos na janela — normal se não houver jogos nas próximas 12h")
    return ok


def main() -> int:
    print("\n" + "=" * 58)
    print("  FUTEBOL BETTING BRAIN — Verificação de fontes reais")
    print("=" * 58 + "\n")

    results = {
        "meteo": check_weather(),
        "web": check_web_scanner(),
        "api_football": check_api_football(),
        "xai": check_xai(),
        "football_data": check_football_data(),
    }
    print()
    results["scanner"] = check_scanner_combo()

    print("\n" + "-" * 58)
    if results["meteo"] and results["web"] and results["scanner"]:
        print("  Modo web activo: python main.py --scan --hours 12")
        print("  (XAI opcional para notícias quando tiveres créditos)")
    elif results["meteo"]:
        print("  Meteo OK. Scanner web pode estar vazio fora de dias de jogo.")
        print("  Teste: python main.py --scan --hours 12")
    else:
        print("  Configura OPENWEATHERMAP_API_KEY (ver .env.example).")
        print("  Jogos: web automático | Notícias: XAI quando houver créditos")
    print("-" * 58 + "\n")

    return 0 if results["meteo"] else 1


if __name__ == "__main__":
    sys.exit(main())