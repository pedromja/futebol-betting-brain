#!/usr/bin/env python3
"""Futebol Betting Brain — motor de decisão para mercados de futebol 11."""

import argparse
import sys

from config.env import load_dotenv

load_dotenv()

from data.loader import list_samples, load_environment_for_match, load_sample
from decision.engine import DecisionEngine
from live.types import LiveMatchState
from models.team_stats import MatchInput, MatchOdds, TeamForm
from output.report import ReportGenerator
from discovery.fixture_scanner import FixtureScanner
from scanner.fixture_report import FixtureListReport
from discovery.api_football_client import ApiFootballClient
from scanner.live_ranker import LiveScanRanker
from scanner.live_report import LiveListReport, LiveScanReport
from scanner.live_watcher import LiveWatcher
from scanner.ranker import ScanRanker
from scanner.scan_report import ScanReport
from odds.provider import OddsProvider
from stakes.types import TeamStake


def _float(prompt: str, default: float | None = None) -> float:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return float(raw.replace(",", "."))
        except ValueError:
            print("  Valor inválido. Introduz um número.")


def _int(prompt: str, default: int | None = None) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Valor inválido. Introduz um número inteiro.")


def _str(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or default


def _read_team(side: str) -> TeamForm:
    print(f"\n--- Equipa {side} ---")
    return TeamForm(
        name=_str(f"Nome ({side})"),
        goals_scored_avg=_float("Média golos marcados/jogo"),
        goals_conceded_avg=_float("Média golos sofridos/jogo"),
        games_played=_int("Jogos analisados", 10),
        scored_in_last_n=_int("Jogos em que marcou (últimos N)", 7),
        conceded_in_last_n=_int("Jogos em que sofreu (últimos N)", 6),
        last_n=_int("Tamanho da amostra (N)", 10),
    )


def _read_odds() -> MatchOdds:
    print("\n--- Odds da casa de apostas ---")
    return MatchOdds(
        home_win=_float("Vitória Casa (1)"),
        draw=_float("Empate (X)"),
        away_win=_float("Vitória Fora (2)"),
        over_25=_float("Over 2.5"),
        under_25=_float("Under 2.5"),
        btts_yes=_float("BTTS Sim"),
        btts_no=_float("BTTS Não"),
        double_chance_1x=_float("Dupla Hipótese 1X (0 se N/A)", 0),
        double_chance_x2=_float("Dupla Hipótese X2 (0 se N/A)", 0),
        double_chance_12=_float("Dupla Hipótese 12 (0 se N/A)", 0),
    )


def run_manual() -> MatchInput:
    print("\n" + "=" * 58)
    print("  MODO MANUAL — Estádio e notícias são descobertos automaticamente")
    print("=" * 58)

    league = _str("Liga", "Primeira Liga")
    date = _str("Data (AAAA-MM-DD)", "")
    home = _read_team("CASA")
    away = _read_team("FORA")
    odds = _read_odds()

    return MatchInput(
        home=home, away=away, odds=odds, league=league, date=date,
    )


def run_demo(key: str) -> MatchInput:
    return load_sample(key)


def analyze(
    match: MatchInput,
    min_score: float,
    quiet: bool = False,
    match_key: str | None = None,
    news_enabled: bool = True,
    environment_enabled: bool = True,
    stakes_enabled: bool = True,
    api_key: str | None = None,
    weather_api_key: str | None = None,
    live_weather: bool = True,
    live_state: LiveMatchState | None = None,
    home_stake: TeamStake | None = None,
    away_stake: TeamStake | None = None,
    fetch_odds: bool = False,
    the_odds_api_key: str | None = None,
    odds_region: str = "eu",
    sport_key: str | None = None,
) -> None:
    environment = None
    discovered = None
    odds_fetch = None

    if fetch_odds:
        provider = OddsProvider(
            the_odds_api_key=the_odds_api_key,
            xai_api_key=api_key,
            region=odds_region,
        )
        odds_fetch = provider.fetch_for_match(match, sport_key=sport_key)
        if odds_fetch:
            match = OddsProvider.apply_to_match(match, odds_fetch)
            print(
                f"  Odds obtidas: {odds_fetch.bookmaker_title} "
                f"({odds_fetch.source}, decimal)"
            )
        else:
            print(
                "  Aviso: não foi possível obter odds live "
                "(verifica THE_ODDS_API_KEY ou nomes das equipas)."
            )

    if environment_enabled:
        environment, discovered = load_environment_for_match(
            match,
            match_key=match_key,
            weather_api_key=weather_api_key,
            live_weather=live_weather,
        )
        if discovered and environment:
            match = MatchInput(
                home=match.home,
                away=match.away,
                odds=match.odds,
                league=match.league,
                date=match.date,
                venue_stadium=discovered.stadium,
                venue_city=discovered.city,
                venue_country=discovered.country,
                home_advantage=match.home_advantage,
                league_avg_goals=match.league_avg_goals,
                home_stake=home_stake or match.home_stake,
                away_stake=away_stake or match.away_stake,
            )

    engine = DecisionEngine(
        min_score=min_score,
        news_enabled=news_enabled,
        environment_enabled=environment_enabled,
        stakes_enabled=stakes_enabled,
        api_key=api_key,
        force_sample_news=False,
    )
    decision = engine.decide(
        match,
        match_key=match_key,
        environment=environment,
        discovered_venue=discovered,
        live_state=live_state,
        home_stake=home_stake,
        away_stake=away_stake,
        odds_fetch=odds_fetch,
    )
    report = ReportGenerator().generate(decision, verbose=not quiet)
    print("\n" + report)
    print(f"\n  RESUMO: {decision.summary}")
    if not quiet:
        mode = "ao vivo" if live_state else "pré-jogo"
        print(
            f"\n  Modo: {mode} | stakes: {'on' if stakes_enabled else 'off'} | "
            "estádio via web/registo | notícias via web/X | meteo OpenWeatherMap."
        )
    print("\n  ⚠ Aviso: Isto é apoio à decisão, não garantia de lucro.")
    print("  Aposta com responsabilidade.\n")


def run_list_fixtures(
    hours: int,
    football_data_key: str | None = None,
    api_football_key: str | None = None,
    api_key: str | None = None,
) -> None:
    scanner = FixtureScanner(
        xai_api_key=api_key,
        football_data_key=football_data_key,
        api_football_key=api_football_key,
        hours_ahead=hours,
    )
    fixtures = scanner.scan()
    fixtures.sort(key=lambda f: f.kickoff)

    from datetime import datetime

    scanned_at = datetime.now().isoformat(timespec="seconds")
    print("\n" + FixtureListReport().generate(fixtures, hours, scanned_at) + "\n")


def run_live_list(
    api_football_key: str | None = None,
) -> None:
    from datetime import datetime

    client = ApiFootballClient(api_key=api_football_key)
    if not client.is_configured:
        print("\n  API_FOOTBALL_KEY não definida.")
        print("  → https://dashboard.api-football.com/\n")
        return

    fixtures = client.scan_live()
    scanned_at = datetime.now().isoformat(timespec="seconds")
    print("\n" + LiveListReport().generate(fixtures, scanned_at) + "\n")


def run_live_scan(
    min_score: float,
    api_football_key: str | None = None,
    football_data_key: str | None = None,
    weather_api_key: str | None = None,
    api_key: str | None = None,
    live_weather: bool = True,
    bankroll: float | None = None,
    kelly_fraction: float = 0.25,
    max_games: int = 15,
    league_filter: str | None = None,
    prefer_live_odds: bool = True,
    verbose: bool = False,
) -> None:
    if not ApiFootballClient(api_key=api_football_key).is_configured:
        print("\n  API_FOOTBALL_KEY não definida.")
        print("  → https://dashboard.api-football.com/\n")
        return

    ranker = LiveScanRanker(
        api_football_key=api_football_key,
        football_data_key=football_data_key,
        weather_api_key=weather_api_key,
        xai_api_key=api_key,
        min_score=min_score,
        live_weather=live_weather,
        bankroll=bankroll,
        kelly_fraction=kelly_fraction,
        max_games=max_games,
        league_filter=league_filter,
        prefer_live_odds=prefer_live_odds,
    )
    result = ranker.scan_and_rank()
    print("\n" + LiveScanReport().generate(result))

    if verbose and result.best and result.best.should_bet:
        print("\n" + "=" * 58)
        print("  DETALHE — MELHOR JOGO LIVE")
        print("=" * 58)
        print(ReportGenerator().generate(result.best.decision, verbose=True))
        print(f"\n  RESUMO: {result.best.decision.summary}")

    print("\n  ⚠ Apoio à decisão in-play. Odds in-play quando disponíveis.")
    print("  Aposta com responsabilidade.\n")


def run_resolve_predictions(dry_run: bool = False) -> None:
    from history.outcome_resolver import format_report, resolve_predictions

    _, stats = resolve_predictions(dry_run=dry_run)
    print("\n" + format_report(stats))
    if dry_run and stats.resolved:
        print("\n  (dry-run — nada gravado)")
    elif stats.resolved:
        print("\n  Gravado em: data/predictions.jsonl")
    print()


def run_live_watch(
    min_score: float,
    api_football_key: str | None = None,
    football_data_key: str | None = None,
    weather_api_key: str | None = None,
    api_key: str | None = None,
    bankroll: float | None = None,
    max_games: int = 15,
    league_filter: str | None = None,
    prefer_live_odds: bool = True,
    interval: int = 45,
) -> None:
    if not ApiFootballClient(api_key=api_football_key).is_configured:
        print("\n  API_FOOTBALL_KEY não definida.")
        print("  → https://dashboard.api-football.com/\n")
        return

    LiveWatcher(
        interval=interval,
        league_filter=league_filter,
        min_score=min_score,
        bankroll=bankroll,
        max_games=max_games,
        prefer_live_odds=prefer_live_odds,
        api_football_key=api_football_key,
        football_data_key=football_data_key,
        weather_api_key=weather_api_key,
        xai_api_key=api_key,
    ).run_loop()


def run_scan(
    hours: int,
    min_score: float,
    api_key: str | None = None,
    the_odds_api_key: str | None = None,
    odds_region: str = "eu",
    weather_api_key: str | None = None,
    football_data_key: str | None = None,
    api_football_key: str | None = None,
    live_weather: bool = True,
    verbose: bool = False,
    bankroll: float | None = None,
    kelly_fraction: float = 0.25,
    log_predictions: bool = False,
) -> None:
    ranker = ScanRanker(
        xai_api_key=api_key,
        the_odds_api_key=the_odds_api_key,
        odds_region=odds_region,
        weather_api_key=weather_api_key,
        football_data_key=football_data_key,
        api_football_key=api_football_key,
        hours_ahead=hours,
        min_score=min_score,
        live_weather=live_weather,
        bankroll=bankroll,
        kelly_fraction=kelly_fraction,
        log_predictions=log_predictions,
    )
    result = ranker.scan_and_rank()
    print("\n" + ScanReport().generate(result))

    if verbose and result.best:
        print("\n" + "=" * 58)
        print("  DETALHE — MELHOR JOGO")
        print("=" * 58)
        print(ReportGenerator().generate(result.best.decision, verbose=True))
        print(f"\n  RESUMO: {result.best.decision.summary}")

    if not api_key and not the_odds_api_key:
        print(
            "  Fontes gratuitas: jogos/odds ESPN+Bing | stats TheSportsDB | "
            "notícias Bing | meteo OpenWeather."
        )
    print("\n  ⚠ Aviso: Isto é apoio à decisão, não garantia de lucro.")
    print("  Aposta com responsabilidade.\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Motor de decisão para mercados de apostas em futebol 11"
    )
    parser.add_argument(
        "--demo",
        metavar="JOGO",
        help=f"Usar jogo de exemplo. Opções: {', '.join(list_samples())}",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Introduzir dados manualmente (estádio descoberto automaticamente)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.55,
        help="Score mínimo para recomendar aposta (default: 0.55)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Listar jogos de demonstração (demos locais, não jogos reais)",
    )
    parser.add_argument(
        "--list-fixtures",
        action="store_true",
        help="Listar jogos reais nas próximas N horas (só tabela, sem análise)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Mostrar só a decisão final, sem o processo detalhado",
    )
    parser.add_argument(
        "--no-news",
        action="store_true",
        help="Desativar pesquisa de notícias no X",
    )
    parser.add_argument(
        "--no-environment",
        action="store_true",
        help="Desativar ajuste por meteorologia, viagem e altitude",
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="XAI_API_KEY para DeepSearch em tempo real (x_search)",
    )
    parser.add_argument(
        "--weather-api-key",
        metavar="KEY",
        help="OPENWEATHERMAP_API_KEY para meteorologia em tempo real",
    )
    parser.add_argument(
        "--no-live-weather",
        action="store_true",
        help="Usar meteorologia de exemplo em vez da OpenWeatherMap",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Modo principal: descobre jogos nas próximas N horas e rankeia por EV",
    )
    parser.add_argument(
        "--live-list",
        action="store_true",
        help="Listar jogos ao vivo agora (1 pedido API-Football, sem análise)",
    )
    parser.add_argument(
        "--live-scan",
        action="store_true",
        help="Analisar jogos ao vivo (API-Football live=all + motor in-play)",
    )
    parser.add_argument(
        "--live-max",
        type=int,
        default=15,
        help="Máximo de jogos live a analisar (default: 15)",
    )
    parser.add_argument(
        "--live-league",
        metavar="TEXTO",
        help="Filtrar live por competição (ex: 'World Cup', 'Primeira')",
    )
    parser.add_argument(
        "--prematch-odds",
        action="store_true",
        help="Live scan: usar só odds pré-jogo (ignora in-play)",
    )
    parser.add_argument(
        "--live-watch",
        action="store_true",
        help="Vigilância contínua ao vivo com alertas de golo e oportunidades",
    )
    parser.add_argument(
        "--live-watch-interval",
        type=int,
        default=45,
        help="Segundos entre ciclos do live-watch (default: 45)",
    )
    parser.add_argument(
        "--resolve-predictions",
        action="store_true",
        help="Resolver win/loss em data/predictions.jsonl (jogos terminados)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=12,
        help="Janela de horas para o scanner (default: 12)",
    )
    parser.add_argument(
        "--football-data-key",
        metavar="KEY",
        help="FOOTBALL_DATA_API_KEY para fixtures via football-data.org",
    )
    parser.add_argument(
        "--api-football-key",
        metavar="KEY",
        help="API_FOOTBALL_KEY — API-Sports v3 (dashboard.api-football.com)",
    )
    parser.add_argument(
        "--scan-verbose",
        action="store_true",
        help="No modo --scan, mostrar processo completo do melhor jogo",
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        metavar="EUR",
        help="Banca em euros — activa sugestão de stake Kelly no scan",
    )
    parser.add_argument(
        "--kelly-fraction",
        type=float,
        default=0.25,
        help="Fracção Kelly (default 0.25 = quarter-Kelly)",
    )
    parser.add_argument(
        "--log-predictions",
        action="store_true",
        help="Guardar apostas recomendadas em data/predictions.jsonl",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Modo ao vivo: usa resultado e minuto actuais",
    )
    parser.add_argument(
        "--score",
        metavar="H-A",
        help="Resultado ao vivo, ex: 1-1 (obrigatório com --live)",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=0,
        help="Minuto actual do jogo (ex: 68)",
    )
    parser.add_argument(
        "--injury-time",
        type=int,
        default=0,
        help="Compensação estimada em minutos",
    )
    parser.add_argument(
        "--home-stake",
        metavar="SITUACAO",
        help="Necessidade da equipa casa: must_win, qualified, knockout, draw_ok, ...",
    )
    parser.add_argument(
        "--away-stake",
        metavar="SITUACAO",
        help="Necessidade da equipa fora",
    )
    parser.add_argument(
        "--no-stakes",
        action="store_true",
        help="Desactivar ajuste por necessidades das equipas",
    )
    parser.add_argument(
        "--fetch-odds",
        action="store_true",
        help="Obter odds decimais via The-Odds-API (primária) ou X",
    )
    parser.add_argument(
        "--odds-api-key",
        metavar="KEY",
        help="THE_ODDS_API_KEY — fonte principal de odds decimais",
    )
    parser.add_argument(
        "--odds-region",
        default="eu",
        choices=["eu", "uk", "us", "au"],
        help="Região de casas de apostas (default: eu)",
    )
    parser.add_argument(
        "--sport-key",
        metavar="KEY",
        help="Sport key The-Odds-API (ex: soccer_fifa_world_cup). Auto se omitido.",
    )
    args = parser.parse_args()

    if args.live and not args.score:
        parser.error("--live requer --score (ex: --score 1-1)")

    if args.resolve_predictions:
        run_resolve_predictions()
        return 0

    if args.live_list:
        run_live_list(api_football_key=args.api_football_key)
        return 0

    if args.live_scan:
        run_live_scan(
            min_score=args.min_score,
            api_football_key=args.api_football_key,
            football_data_key=args.football_data_key,
            weather_api_key=args.weather_api_key,
            api_key=args.api_key,
            live_weather=not args.no_live_weather,
            bankroll=args.bankroll,
            kelly_fraction=args.kelly_fraction,
            max_games=args.live_max,
            league_filter=args.live_league,
            prefer_live_odds=not args.prematch_odds,
            verbose=args.scan_verbose,
        )
        return 0

    if args.live_watch:
        run_live_watch(
            min_score=args.min_score,
            api_football_key=args.api_football_key,
            football_data_key=args.football_data_key,
            weather_api_key=args.weather_api_key,
            api_key=args.api_key,
            bankroll=args.bankroll,
            max_games=args.live_max,
            league_filter=args.live_league,
            prefer_live_odds=not args.prematch_odds,
            interval=args.live_watch_interval,
        )
        return 0

    if args.list_fixtures:
        run_list_fixtures(
            hours=args.hours,
            football_data_key=args.football_data_key,
            api_football_key=args.api_football_key,
            api_key=args.api_key,
        )
        return 0

    if args.scan:
        run_scan(
            hours=args.hours,
            min_score=args.min_score,
            api_key=args.api_key,
            the_odds_api_key=args.odds_api_key,
            odds_region=args.odds_region,
            weather_api_key=args.weather_api_key,
            bankroll=args.bankroll,
            kelly_fraction=args.kelly_fraction,
            log_predictions=args.log_predictions,
            football_data_key=args.football_data_key,
            api_football_key=args.api_football_key,
            live_weather=not args.no_live_weather,
            verbose=args.scan_verbose,
        )
        return 0

    if args.list:
        print("Jogos de demonstração:")
        for key in list_samples():
            match = load_sample(key)
            print(f"  {key}: {match.home.name} vs {match.away.name}")
        return 0

    match_key: str | None = None

    if args.demo:
        match = run_demo(args.demo)
        match_key = args.demo
    elif args.manual:
        match = run_manual()
    else:
        print("Futebol Betting Brain")
        print("-" * 40)
        print("1) Scanner — jogos próximas 12h (recomendado)")
        print("2) Demo — Benfica vs Sporting")
        print("3) Demo — FC Porto vs SC Braga")
        print("4) Demo — Estoril vs Farense")
        print("5) Modo manual")
        print("0) Sair")
        choice = input("\nEscolhe uma opção: ").strip()
        demos = {
            "2": "benfica_sporting",
            "3": "porto_braga",
            "4": "estoril_farense",
        }
        if choice == "0":
            return 0
        if choice == "1":
            run_scan(hours=12, min_score=args.min_score)
            return 0
        if choice == "5":
            match = run_manual()
        elif choice in demos:
            match_key = demos[choice]
            match = run_demo(match_key)
        else:
            print("Opção inválida.")
            return 1

    live_state = None
    if args.live:
        live_state = LiveMatchState.from_score_string(
            args.score,
            minute=args.minute,
            injury_time=args.injury_time,
        )

    home_stake = TeamStake.from_string(args.home_stake) if args.home_stake else None
    away_stake = TeamStake.from_string(args.away_stake) if args.away_stake else None

    analyze(
        match,
        args.min_score,
        quiet=args.quiet,
        match_key=match_key,
        news_enabled=not args.no_news,
        environment_enabled=not args.no_environment,
        stakes_enabled=not args.no_stakes,
        api_key=args.api_key,
        weather_api_key=args.weather_api_key,
        live_weather=not args.no_live_weather,
        live_state=live_state,
        home_stake=home_stake,
        away_stake=away_stake,
        fetch_odds=args.fetch_odds,
        the_odds_api_key=args.odds_api_key,
        odds_region=args.odds_region,
        sport_key=args.sport_key,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())