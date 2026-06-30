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
    transfermarkt: dict | None = None
    motivation: dict | None = None
    competition_progress: dict | None = None
    block_reason: str | None = None
    learning_tune: dict | None = None


@dataclass
class ScanResult:
    scanned_at: str
    hours_window: int
    total_found: int
    total_analyzed: int
    ranked: list[RankedMatch]
    best: RankedMatch | None
    fixtures: list[UpcomingFixture] = field(default_factory=list)
    requested_hours: int = 12
    window_extended: bool = False


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
        news_enabled: bool = False,
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
            news_enabled=news_enabled and bool(xai_api_key),
        )
        self.weather_api_key = weather_api_key
        self.live_weather = live_weather
        self.hours_ahead = hours_ahead
        self.requested_hours = hours_ahead
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.log_predictions = log_predictions

    @staticmethod
    def _real_fixtures(fixtures: list[UpcomingFixture]) -> list[UpcomingFixture]:
        return [fx for fx in fixtures if fx.source != "sample"]

    def _discover_fixtures(self, hours: int) -> list[UpcomingFixture]:
        self.scanner.hours_ahead = hours
        self.hours_ahead = hours
        return self.scanner.scan(allow_sample=False)

    def _needs_wider_window(
        self, fixtures: list[UpcomingFixture], window: int
    ) -> bool:
        return window < 24 and not self._real_fixtures(fixtures)

    def discover_only(self) -> tuple[list[UpcomingFixture], int, bool]:
        window = self.requested_hours
        fixtures = self._discover_fixtures(window)
        window_extended = False

        if self._needs_wider_window(fixtures, window):
            window = 24
            fixtures = self._discover_fixtures(window)
            window_extended = True

        return fixtures, window, window_extended

    def scan_and_rank(self) -> ScanResult:
        from datetime import datetime

        from history.auto_tune import refresh_tune_state, tuned_min_score
        from history.predictions import load_fixture_markets_used, pick_unused_market

        tune_state = refresh_tune_state()
        fixtures, window, window_extended = self.discover_only()
        used_markets_by_fixture = load_fixture_markets_used()
        ranked: list[RankedMatch] = []
        progress_cache: dict[str, object] = {}

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

            dynamic_base = dynamic_min_score(self.min_score, match)

            decision = self.engine.decide(
                match,
                environment=env,
                discovered_venue=discovered,
            )

            rec = decision.recommendation
            if not rec.all_markets:
                continue

            fx_key = f"{fixture.home}|{fixture.away}"
            used = used_markets_by_fixture.setdefault(fx_key, set())
            best = pick_unused_market(
                rec.all_markets,
                used,
                dynamic_base,
                min_score_for=lambda lbl, b, league="": tuned_min_score(
                    b, lbl, league or fixture.league, tune_state
                ),
                league=fixture.league,
            )
            if not best:
                continue

            effective_min = tuned_min_score(
                dynamic_base,
                best.label,
                fixture.league,
                tune_state,
            )

            rec.best = best
            should_bet = True
            block_reason: str | None = None
            comp_progress_dict: dict | None = None

            from bankroll.competition_progress import resolve_competition_progress

            league_key = (fixture.league or "").strip().lower()
            if league_key not in progress_cache:
                progress_cache[league_key] = resolve_competition_progress(
                    fixture.league,
                    stage=fixture.stage,
                    football_data_key=self.stats_fetcher.fd_key,
                )
            comp_prog = progress_cache.get(league_key)
            if comp_prog is not None:
                comp_progress_dict = comp_prog.to_dict()
                if not comp_prog.allowed:
                    should_bet = False
                    block_reason = comp_prog.reason

            top_markets = [
                f"{m.label} ({m.total_score:.2f})"
                for m in rec.all_markets[:3]
                if m.label not in used
            ]

            kelly_stake = None
            kelly_pct = None
            stake_plan = suggest_stake(
                best.expected_value,
                self.bankroll,
                league=fixture.league,
                stage=fixture.stage,
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
                    kelly_pct = sizing.stake_percent

            used.add(best.label)

            from prematch.auditors import apply_motivation_stake, evaluate_motivation
            from prematch.transfermarkt import analyze_prematch

            tm = analyze_prematch(
                fixture.home,
                fixture.away,
                odds_hint=fixture.odds_hint,
                best_market=best.label,
            )

            home_snap = self.stats_fetcher.fetch_form(fixture.home)
            away_snap = self.stats_fetcher.fetch_form(fixture.away)
            mot = evaluate_motivation(
                fixture.home,
                fixture.away,
                best_market=best.label,
                best_ev=best.expected_value,
                league=fixture.league,
                stage=fixture.stage,
                tm_insights=tm,
                home_form=home_snap,
                away_form=away_snap,
                odds_hint=fixture.odds_hint,
            )
            if not mot.should_bet:
                should_bet = False
            stake_plan = apply_motivation_stake(stake_plan, mot)
            if stake_plan and stake_plan.bankroll_pct <= 0:
                should_bet = False
            if block_reason:
                should_bet = False
                stake_plan = None
                kelly_stake = None
                kelly_pct = None
            if kelly_stake is not None and mot.stake_multiplier < 1.0:
                kelly_stake = round(kelly_stake * mot.stake_multiplier, 2)
                if kelly_pct is not None:
                    kelly_pct = round(kelly_pct * mot.stake_multiplier, 3)

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
                    transfermarkt=tm.to_dict() if tm.data_available else None,
                    motivation=mot.to_dict(),
                    competition_progress=comp_progress_dict,
                    block_reason=block_reason,
                    learning_tune=tune_state.to_dict() if tune_state.active else None,
                )
            )

        ranked.sort(key=lambda r: (r.should_bet, r.best_ev, r.best_score), reverse=True)
        for i, r in enumerate(ranked):
            r.rank = i + 1

        result = ScanResult(
            scanned_at=datetime.now().isoformat(timespec="seconds"),
            hours_window=window,
            total_found=len(fixtures),
            total_analyzed=len(ranked),
            ranked=ranked,
            best=ranked[0] if ranked else None,
            fixtures=fixtures,
            requested_hours=self.requested_hours,
            window_extended=window_extended,
        )

        from history.predictions import append_scan_predictions
        from history.resolve_scheduler import maybe_resolve_pending

        append_scan_predictions(result, bankroll=self.bankroll)
        maybe_resolve_pending()

        return result