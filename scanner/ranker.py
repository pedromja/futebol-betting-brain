"""Analisa todos os jogos descobertos e rankeia pelo melhor EV."""

from dataclasses import dataclass, field

from bankroll.ev_stake import EvStakePlan, suggest_stake
from bankroll.kelly import fractional_kelly
from bankroll.threshold import dynamic_min_score
from data.loader import load_environment_for_match
from decision.engine import Decision, DecisionEngine
from discovery.fixture_scanner import FixtureScanner, UpcomingFixture
from discovery.team_stats_fetcher import TeamStatsFetcher
from odds.provider import OddsProvider
from scanner.match_builder import build_match


@dataclass
class RankedMatch:
    fixture: UpcomingFixture
    decision: Decision
    best_ev: float
    best_market: str
    best_score: float
    should_bet: bool
    effective_min_score: float = 0.55
    top_markets: list[str] = field(default_factory=list)
    kelly_stake: float | None = None
    kelly_pct: float | None = None
    stake_plan: EvStakePlan | None = None
    rank: int = 0


@dataclass
class ScanResult:
    scanned_at: str
    hours_window: int
    total_found: int
    total_analyzed: int
    ranked: list[RankedMatch]
    best: RankedMatch | None


class ScanRanker:
    def __init__(
        self,
        xai_api_key: str | None = None,
        the_odds_api_key: str | None = None,
        odds_region: str = "eu",
        weather_api_key: str | None = None,
        football_data_key: str | None = None,
        api_football_key: str | None = None,
        hours_ahead: int = 12,
        min_score: float = 0.55,
        live_weather: bool = True,
        bankroll: float | None = None,
        kelly_fraction: float = 0.25,
        log_predictions: bool = False,
    ):
        self.scanner = FixtureScanner(
            xai_api_key=xai_api_key,
            football_data_key=football_data_key,
            api_football_key=api_football_key,
            hours_ahead=hours_ahead,
        )
        self.odds_provider = OddsProvider(
            the_odds_api_key=the_odds_api_key,
            xai_api_key=xai_api_key,
            region=odds_region,
        )
        self.stats_fetcher = TeamStatsFetcher(
            football_data_key=football_data_key,
            api_football_key=api_football_key,
        )
        self.min_score = min_score
        self.engine = DecisionEngine(
            min_score=min_score,
            api_key=xai_api_key,
            force_sample_news=False,
        )
        self.weather_api_key = weather_api_key
        self.live_weather = live_weather
        self.hours_ahead = hours_ahead
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.log_predictions = log_predictions

    def scan_and_rank(self) -> ScanResult:
        from datetime import datetime

        fixtures = self.scanner.scan()
        ranked: list[RankedMatch] = []

        if fixtures:
            teams: list[str] = []
            for fx in fixtures:
                teams.extend([fx.home, fx.away])
            self.stats_fetcher.warm_teams(teams)

        for fixture in fixtures:
            match, _ = build_match(
                fixture, self.odds_provider, stats_fetcher=self.stats_fetcher
            )
            if not match:
                continue

            env, discovered = load_environment_for_match(
                match,
                weather_api_key=self.weather_api_key,
                live_weather=self.live_weather,
            )

            effective_min = dynamic_min_score(self.min_score, match)

            decision = self.engine.decide(
                match,
                environment=env,
                discovered_venue=discovered,
            )

            rec = decision.recommendation
            best = rec.best
            if not best:
                continue

            should_bet = best.total_score >= effective_min
            top_markets = [
                f"{m.label} ({m.total_score:.2f})"
                for m in rec.all_markets[:3]
            ]

            kelly_stake = None
            kelly_pct = None
            stake_plan = None
            if should_bet:
                stake_plan = suggest_stake(best.expected_value, self.bankroll)
                if self.bankroll:
                    sizing = fractional_kelly(
                        best.model_prob,
                        best.odd,
                        self.bankroll,
                        fraction=self.kelly_fraction,
                    )
                    if sizing:
                        kelly_stake = sizing.stake_amount
                        kelly_pct = sizing.stake_percent

            ranked.append(
                RankedMatch(
                    fixture=fixture,
                    decision=decision,
                    best_ev=best.expected_value,
                    best_market=best.label,
                    best_score=best.total_score,
                    should_bet=should_bet,
                    effective_min_score=effective_min,
                    top_markets=top_markets,
                    kelly_stake=kelly_stake,
                    kelly_pct=kelly_pct,
                    stake_plan=stake_plan,
                )
            )

        ranked.sort(key=lambda r: (r.should_bet, r.best_ev, r.best_score), reverse=True)
        for i, r in enumerate(ranked):
            r.rank = i + 1

        result = ScanResult(
            scanned_at=datetime.now().isoformat(timespec="seconds"),
            hours_window=self.hours_ahead,
            total_found=len(fixtures),
            total_analyzed=len(ranked),
            ranked=ranked,
            best=ranked[0] if ranked else None,
        )

        from history.predictions import append_scan_predictions

        append_scan_predictions(result, bankroll=self.bankroll)

        return result