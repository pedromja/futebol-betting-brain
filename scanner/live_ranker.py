"""Descobre jogos live e rankeia oportunidades in-play."""

from dataclasses import dataclass, field
from datetime import datetime

from bankroll.ev_stake import EvStakePlan, suggest_stake
from bankroll.kelly import fractional_kelly
from bankroll.threshold import dynamic_min_score
from live.tip_filters import live_tip_omit_reason
from data.loader import load_environment_for_match
from decision.engine import Decision, DecisionEngine
from discovery.api_football_client import ApiFootballClient
from discovery.live_fixture_types import LiveFixture
from discovery.live_odds_fetcher import LiveOddsFetcher
from discovery.team_stats_fetcher import TeamStatsFetcher
from scanner.match_builder import build_match


@dataclass
class RankedLiveMatch:
    fixture: LiveFixture
    decision: Decision
    best_ev: float
    best_market: str
    best_score: float
    should_bet: bool
    effective_min_score: float = 0.55
    top_markets: list[str] = field(default_factory=list)
    kelly_stake: float | None = None
    stake_plan: EvStakePlan | None = None
    rank: int = 0
    skipped_reason: str = ""


@dataclass
class LiveScanResult:
    scanned_at: str
    total_live: int
    total_analyzed: int
    skipped: list[tuple[str, str]]
    ranked: list[RankedLiveMatch]
    best: RankedLiveMatch | None


class LiveScanRanker:
    def __init__(
        self,
        api_football_key: str | None = None,
        football_data_key: str | None = None,
        weather_api_key: str | None = None,
        xai_api_key: str | None = None,
        min_score: float = 0.55,
        live_weather: bool = True,
        bankroll: float | None = None,
        kelly_fraction: float = 0.25,
        max_games: int = 15,
        fetch_odds: bool = True,
        prefer_live_odds: bool = True,
        league_filter: str | None = None,
    ):
        self.client = ApiFootballClient(api_key=api_football_key)
        self.live_odds = LiveOddsFetcher(self.client)
        self.stats_fetcher = TeamStatsFetcher(
            football_data_key=football_data_key,
            api_football_key=api_football_key,
        )
        self.engine = DecisionEngine(
            min_score=min_score,
            api_key=xai_api_key,
            force_sample_news=False,
            news_enabled=False,
        )
        self.weather_api_key = weather_api_key
        self.live_weather = live_weather
        self.min_score = min_score
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.max_games = max_games
        self.fetch_odds = fetch_odds
        self.prefer_live_odds = prefer_live_odds
        self.league_filter = (league_filter or "").lower()

    def _matches_league_filter(self, fx: LiveFixture) -> bool:
        if not self.league_filter:
            return True
        blob = f"{fx.league} {fx.stage}".lower()
        return self.league_filter in blob

    def scan_and_rank(self) -> LiveScanResult:
        live_fixtures = self.client.scan_live()
        if self.league_filter:
            live_fixtures = [f for f in live_fixtures if self._matches_league_filter(f)]

        if self.fetch_odds:
            self.live_odds.enrich(
                live_fixtures[: self.max_games],
                prefer_live=self.prefer_live_odds,
            )

        ranked: list[RankedLiveMatch] = []
        skipped: list[tuple[str, str]] = []

        teams: list[str] = []
        for fx in live_fixtures[: self.max_games]:
            teams.extend([fx.home, fx.away])
        if teams:
            self.stats_fetcher.warm_teams(teams)

        for fx in live_fixtures[: self.max_games]:
            if not fx.odds_hint:
                skipped.append((fx.label, "sem odds disponíveis"))
                continue

            upcoming = fx.to_upcoming()
            match, _ = build_match(upcoming, stats_fetcher=self.stats_fetcher)
            if not match:
                skipped.append((fx.label, "stats/odds inválidos"))
                continue

            env, discovered = load_environment_for_match(
                match,
                weather_api_key=self.weather_api_key,
                live_weather=self.live_weather,
            )
            effective_min = dynamic_min_score(self.min_score, match)
            live_state = fx.to_live_state()

            omit, omit_reason = live_tip_omit_reason(live_state)
            if omit:
                skipped.append((fx.label, omit_reason))
                continue

            decision = self.engine.decide(
                match,
                environment=env,
                discovered_venue=discovered,
                live_state=live_state,
            )

            rec = decision.recommendation
            best = rec.best
            if not best:
                skipped.append((fx.label, "nenhum mercado avaliável"))
                continue

            should_bet = best.total_score >= effective_min
            top_markets = [
                f"{m.label} ({m.total_score:.2f})"
                for m in rec.all_markets[:3]
            ]

            kelly_stake = None
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

            ranked.append(
                RankedLiveMatch(
                    fixture=fx,
                    decision=decision,
                    best_ev=best.expected_value,
                    best_market=best.label,
                    best_score=best.total_score,
                    should_bet=should_bet,
                    effective_min_score=effective_min,
                    top_markets=top_markets,
                    kelly_stake=kelly_stake,
                    stake_plan=stake_plan,
                )
            )

        ranked.sort(key=lambda r: (r.should_bet, r.best_ev, r.best_score), reverse=True)
        for i, row in enumerate(ranked):
            row.rank = i + 1

        result = LiveScanResult(
            scanned_at=datetime.now().isoformat(timespec="seconds"),
            total_live=len(live_fixtures),
            total_analyzed=len(ranked),
            skipped=skipped,
            ranked=ranked,
            best=ranked[0] if ranked else None,
        )

        from history.predictions import append_live_predictions

        append_live_predictions(result, bankroll=self.bankroll)

        return result