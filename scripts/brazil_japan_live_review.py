"""Reavaliação ao vivo Brasil vs Japão — golos + mercados extra."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.loader import load_sample
from decision.engine import DecisionEngine
from live.types import LiveMatchState
from markets.extended import ExtendedMarketAnalyzer, ExtendedOdds, LiveContext
from models.team_stats import MatchInput, MatchOdds
from odds.converter import american_to_decimal
from output.report import ReportGenerator

# DraftKings via ESPN — min ~86', 1-1 (29 Jun 2026)
LIVE_AMERICAN = {
    "home_win": 330,
    "draw": -350,
    "away_win": 1200,
    "over_25": 227,
    "under_25": -279,
    "handicap_home": 310,
    "handicap_away": -450,
    "corners_over": -155,
    "corners_under": 115,
    "home_team_over_15": 157,
}


def build_live_odds() -> MatchOdds:
    d = {k: american_to_decimal(v) for k, v in LIVE_AMERICAN.items() if k in (
        "home_win", "draw", "away_win", "over_25", "under_25"
    )}
    return MatchOdds(
        home_win=d["home_win"],
        draw=d["draw"],
        away_win=d["away_win"],
        over_25=d["over_25"],
        under_25=d["under_25"],
        btts_yes=1.01,
        btts_no=50.0,
        double_chance_1x=1.05,
        double_chance_x2=1.15,
        double_chance_12=1.40,
    )


def main() -> None:
    base = load_sample("brazil_japan")
    match = MatchInput(
        home=base.home,
        away=base.away,
        odds=build_live_odds(),
        league=base.league,
        date=base.date,
        home_advantage=base.home_advantage,
        league_avg_goals=base.league_avg_goals,
        venue_stadium=base.venue_stadium,
        venue_city=base.venue_city,
        venue_country=base.venue_country,
        home_stake=base.home_stake,
        away_stake=base.away_stake,
    )

    state = LiveMatchState.from_score_string("1-1", minute=86, injury_time=5)

    engine = DecisionEngine(min_score=0.55, news_enabled=False, environment_enabled=False)
    decision = engine.decide(match, live_state=state)

    print("=" * 62)
    print("  REAVALIAÇÃO AO VIVO — Brasil vs Japão (~86', 1-1)")
    print("  Odds decimais: DraftKings (via ESPN), convertidas automaticamente")
    print("=" * 62)
    print()
    print("  ODDS DECIMAIS ACTUAIS (golos / 1X2):")
    o = match.odds
    for label, val in [
        ("Vitória Brasil", o.home_win),
        ("Empate 90'", o.draw),
        ("Vitória Japão", o.away_win),
        ("Over 2.5", o.over_25),
        ("Under 2.5", o.under_25),
        ("Brasil -0.5 AH", american_to_decimal(LIVE_AMERICAN["handicap_home"])),
        ("Japão +0.5 AH", american_to_decimal(LIVE_AMERICAN["handicap_away"])),
        ("Cantos Over 6.5", american_to_decimal(LIVE_AMERICAN["corners_over"])),
        ("Cantos Under 6.5", american_to_decimal(LIVE_AMERICAN["corners_under"])),
        ("Brasil Over 1.5 golos (equipa)", american_to_decimal(LIVE_AMERICAN["home_team_over_15"])),
    ]:
        print(f"    {label:32s} {val:.2f}")

    print()
    print(ReportGenerator().generate(decision, verbose=False))
    print(f"  RESUMO MOTOR GOLOS: {decision.summary}")

    ext_odds = ExtendedOdds(
        handicap_home=american_to_decimal(LIVE_AMERICAN["handicap_home"]),
        handicap_away=american_to_decimal(LIVE_AMERICAN["handicap_away"]),
        corners_over=american_to_decimal(LIVE_AMERICAN["corners_over"]),
        corners_under=american_to_decimal(LIVE_AMERICAN["corners_under"]),
        home_team_goals_over=american_to_decimal(LIVE_AMERICAN["home_team_over_15"]),
        source="draftkings/espn",
    )
    ctx = LiveContext(
        home_score=1,
        away_score=1,
        minute=86,
        home_xg=1.48,
        away_xg=0.23,
        home_possession=0.69,
        home_shots=17,
        away_shots=5,
        home_pressure="high",
        remaining_minutes=9,
    )
    ext = ExtendedMarketAnalyzer().analyze(ctx, ext_odds, "Brazil", "Japan")

    print()
    print("  MERCADOS EXTRA (não-golos / handicap / cantos):")
    print("  ┌────────────────────────────┬──────┬──────┬──────┐")
    print("  │ Mercado                    │ Odd  │ EV   │ Prob │")
    print("  ├────────────────────────────┼──────┼──────┼──────┤")
    for p in ext[:6]:
        print(
            f"  │ {p.label[:26].ljust(26)} │ {p.odd:4.2f} │ {p.ev_percent:+4.0f}% │ {p.model_prob*100:3.0f}% │"
        )
    print("  └────────────────────────────┴──────┴──────┴──────┘")
    if ext:
        best = ext[0]
        print()
        print(f"  ★ MELHOR EXTRA: {best.label} @ {best.odd:.2f} (EV {best.ev_percent:+.0f}%)")
        for r in best.reasoning:
            print(f"    • {r}")


if __name__ == "__main__":
    main()