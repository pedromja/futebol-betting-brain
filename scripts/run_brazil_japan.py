"""Análise Brazil vs Japan — Mundial 2026, Houston."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.loader import load_environment_for_match
from decision.engine import DecisionEngine
from models.team_stats import MatchInput, MatchOdds, TeamForm
from output.report import ReportGenerator

# Estatísticas fase de grupos (ESPN, 29 Jun 2026)
# Brasil: 7 golos marcados, 1 sofrido em 3 jogos
# Japão: 7 marcados, 3 sofridos em 3 jogos

PRE_MATCH_ODDS = MatchOdds(
    home_win=1.55,
    draw=4.20,
    away_win=6.50,
    over_25=1.72,
    under_25=2.10,
    btts_yes=1.75,
    btts_no=2.05,
    double_chance_1x=1.14,
    double_chance_x2=2.35,
    double_chance_12=1.20,
)

# Odds ao vivo ~68' 1-1 (DraftKings via ESPN)
LIVE_ODDS = MatchOdds(
    home_win=1.74,
    draw=3.60,
    away_win=8.00,
    over_25=1.74,
    under_25=2.14,
    btts_yes=1.05,
    btts_no=12.0,
    double_chance_1x=1.08,
    double_chance_x2=2.05,
    double_chance_12=1.25,
)


def build_match(odds: MatchOdds, label: str) -> MatchInput:
    return MatchInput(
        home=TeamForm(
            name="Brazil",
            goals_scored_avg=2.33,
            goals_conceded_avg=0.33,
            games_played=3,
            scored_in_last_n=3,
            conceded_in_last_n=1,
            last_n=3,
        ),
        away=TeamForm(
            name="Japan",
            goals_scored_avg=2.33,
            goals_conceded_avg=1.00,
            games_played=3,
            scored_in_last_n=3,
            conceded_in_last_n=2,
            last_n=3,
        ),
        odds=odds,
        league="FIFA World Cup 2026 — Round of 32",
        date="2026-06-29",
        venue_stadium="NRG Stadium",
        venue_city="Houston",
        venue_country="US",
        home_advantage=1.08,
        league_avg_goals=2.65,
    )


def analyze(label: str, odds: MatchOdds) -> None:
    match = build_match(odds, label)
    env, discovered = load_environment_for_match(
        match,
        live_weather=False,
    )
    if discovered and env:
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
        )

    engine = DecisionEngine(
        min_score=0.55,
        news_enabled=False,
        environment_enabled=bool(env),
        force_sample_news=False,
    )
    decision = engine.decide(match, environment=env, discovered_venue=discovered)
    print(f"\n{'='*60}\n  CENÁRIO: {label}\n{'='*60}")
    print(ReportGenerator().generate(decision, verbose=True))
    print(f"\n  RESUMO: {decision.summary}\n")
    return decision


if __name__ == "__main__":
    pre = analyze("PRÉ-JOGO (odds de abertura)", PRE_MATCH_ODDS)
    live = analyze("AO VIVO ~68' 1-1 (odds actuais)", LIVE_ODDS)
    print("\n--- COMPARAÇÃO RÁPIDA ---")
    print(f"Pré-jogo:  {pre.recommendation.best.label if pre.recommendation.best else 'N/A'}")
    print(f"Ao vivo:   {live.recommendation.best.label if live.recommendation.best else 'N/A'}")