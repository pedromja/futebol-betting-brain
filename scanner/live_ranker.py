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
    learning_tune: dict | None = None


@dataclass
class LiveScanResult:
    scanned_at: str
    total_live: int
    total_analyzed: int
    skipped: list[tuple[str, str]]
    ranked: list[RankedLiveMatch]
    best: RankedLiveMatch | None
    fixtures: list[LiveFixture] = field(default_factory=list)


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
        news_enabled: bool = False,
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
            news_enabled=news_enabled and bool(xai_api_key),
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

        from history.auto_tune import refresh_tune_state, tuned_min_score
        from history.predictions import load_fixture_markets_used, pick_unused_market

        tune_state = refresh_tune_state()
        used_markets_by_fixture = load_fixture_markets_used()
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
            dynamic_base = dynamic_min_score(self.min_score, match)
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
            if not rec.all_markets:
                skipped.append((fx.label, "nenhum mercado avaliável"))
                continue

            fx_key = f"{fx.home}|{fx.away}"
            used = used_markets_by_fixture.setdefault(fx_key, set())
            unused_markets = [m for m in rec.all_markets if m.label not in used]
            best = pick_unused_market(
                rec.all_markets,
                used,
                dynamic_base,
                min_score_for=lambda lbl, b, league="": tuned_min_score(
                    b, lbl, league or fx.league, tune_state
                ),
                league=fx.league,
            )
            if not best:
                if not unused_markets:
                    skipped.append(
                        (fx.label, "mercados já lançados neste confronto")
                    )
                else:
                    skipped.append(
                        (fx.label, "sem mercado novo com confiança suficiente")
                    )
                continue

            effective_min = tuned_min_score(
                dynamic_base,
                best.label,
                fx.league,
                tune_state,
            )

            rec.best = best
            should_bet = True
            top_markets = [
                f"{m.label} ({m.total_score:.2f})"
                for m in rec.all_markets[:3]
                if m.label not in used
            ]

            kelly_stake = None
            stake_plan = None
            stake_plan = suggest_stake(
                best.expected_value,
                self.bankroll,
                league=fx.league,
                stage=fx.stage,
            )
            if self.bankroll:
                sizing = fractional_kelly(
                    best.model_prob,
                    best.odd,
                    self.bankroll,
                    fraction=self.kelly_fraction,
                )
                if sizing:
                    kelly_stake = sizing.stake_amount

            used.add(best.label)
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
                    learning_tune=tune_state.to_dict() if tune_state.active else None,
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
            fixtures=live_fixtures,
        )

        from history.predictions import append_live_predictions
        from history.resolve_scheduler import maybe_resolve_pending

        append_live_predictions(result, bankroll=self.bankroll)
        maybe_resolve_pending()

        return result