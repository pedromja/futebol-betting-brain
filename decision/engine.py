from dataclasses import dataclass

from discovery.auto import DiscoveredVenue
from environment.impact_formula import EnvironmentFormula, TeamEnvironmentalDistortion
from environment.types import MatchEnvironment
from live.evaluator import LiveMarketEvaluator
from live.types import LiveAnalysisMeta, LiveMatchState
from markets.evaluator import MarketEvaluator, MarketRecommendation
from models.team_stats import MatchInput
from news.deepsearch import DeepSearchClient
from news.impact_formula import ImpactFormula, TeamDistortion
from news.types import MatchNewsReport
from odds.types import OddsFetchResult
from stakes.formula import apply_stakes_to_match
from stakes.types import MatchStakesReport, TeamStake


@dataclass
class Decision:
    match: MatchInput
    recommendation: MarketRecommendation
    alternative: object | None
    summary: str
    original_match: MatchInput | None = None
    news_report: MatchNewsReport | None = None
    environment: MatchEnvironment | None = None
    home_distortion: TeamDistortion | None = None
    away_distortion: TeamDistortion | None = None
    home_env_distortion: TeamEnvironmentalDistortion | None = None
    away_env_distortion: TeamEnvironmentalDistortion | None = None
    discovered_venue: DiscoveredVenue | None = None
    stakes_report: MatchStakesReport | None = None
    live_state: LiveMatchState | None = None
    live_meta: LiveAnalysisMeta | None = None
    mode: str = "pre_match"
    odds_fetch: OddsFetchResult | None = None


class DecisionEngine:
    def __init__(
        self,
        min_score: float = 0.55,
        news_enabled: bool = True,
        environment_enabled: bool = True,
        stakes_enabled: bool = True,
        api_key: str | None = None,
        force_sample_news: bool = False,
    ):
        self.evaluator = MarketEvaluator(min_score=min_score)
        self.live_evaluator = LiveMarketEvaluator(min_score=min_score)
        self.news_impact = ImpactFormula()
        self.env_impact = EnvironmentFormula()
        self.deepsearch = DeepSearchClient(api_key=api_key)
        self.news_enabled = news_enabled
        self.environment_enabled = environment_enabled
        self.stakes_enabled = stakes_enabled
        self.force_sample_news = force_sample_news

    def decide(
        self,
        match: MatchInput,
        match_key: str | None = None,
        environment: MatchEnvironment | None = None,
        discovered_venue: DiscoveredVenue | None = None,
        live_state: LiveMatchState | None = None,
        home_stake: TeamStake | None = None,
        away_stake: TeamStake | None = None,
        odds_fetch: OddsFetchResult | None = None,
    ) -> Decision:
        original_match = match
        news_report: MatchNewsReport | None = None
        home_dist: TeamDistortion | None = None
        away_dist: TeamDistortion | None = None
        home_env: TeamEnvironmentalDistortion | None = None
        away_env: TeamEnvironmentalDistortion | None = None
        stakes_report: MatchStakesReport | None = None
        live_meta: LiveAnalysisMeta | None = None
        mode = "live" if live_state else "pre_match"

        hs = home_stake or match.home_stake
        aws = away_stake or match.away_stake

        if self.news_enabled:
            news_report = self.deepsearch.fetch(
                match,
                match_key=match_key,
                force_sample=self.force_sample_news,
            )
            match, home_dist, away_dist = self.news_impact.adjust_match(match, news_report)

        if self.environment_enabled and environment:
            match, home_env, away_env = self.env_impact.adjust_match(match, environment)

        if self.stakes_enabled:
            score_diff = live_state.score_diff_home if live_state else None
            minute = live_state.minute if live_state else None
            match, stakes_report = apply_stakes_to_match(
                match,
                hs,
                aws,
                score_diff_home=score_diff,
                minute=minute,
            )

        if live_state:
            rec, live_meta = self.live_evaluator.evaluate_live(
                match, live_state, stakes_report
            )
        else:
            rec = self.evaluator.evaluate(match)

        alternative = None
        if rec.should_bet and len(rec.all_markets) > 1:
            for market in rec.all_markets[1:]:
                if market.total_score >= self.evaluator.min_score * 0.9:
                    alternative = market
                    break

        context_note = self._build_context_note(
            home_dist, away_dist, home_env, away_env, stakes_report, mode
        )

        if not rec.should_bet:
            summary = (
                f"Nenhum mercado atinge confiança suficiente para "
                f"{original_match.home.name} vs {original_match.away.name}. "
                f"Recomendação: não apostar neste jogo.{context_note}"
            )
        elif rec.best:
            mode_tag = " [AO VIVO]" if live_state else ""
            summary = (
                f"Apostar em {rec.best.label} @ {rec.best.odd:.2f} "
                f"(score {rec.best.total_score:.2f}, EV {rec.best.ev_percent:+.1f}%){mode_tag}{context_note}"
            )
        else:
            summary = "Sem recomendação disponível."

        return Decision(
            match=match,
            recommendation=rec,
            alternative=alternative,
            summary=summary,
            original_match=original_match,
            news_report=news_report,
            environment=environment if self.environment_enabled else None,
            home_distortion=home_dist,
            away_distortion=away_dist,
            home_env_distortion=home_env,
            away_env_distortion=away_env,
            discovered_venue=discovered_venue,
            stakes_report=stakes_report,
            live_state=live_state,
            live_meta=live_meta,
            mode=mode,
            odds_fetch=odds_fetch,
        )

    @staticmethod
    def _build_context_note(
        home_dist: TeamDistortion | None,
        away_dist: TeamDistortion | None,
        home_env: TeamEnvironmentalDistortion | None,
        away_env: TeamEnvironmentalDistortion | None,
        stakes_report: MatchStakesReport | None,
        mode: str,
    ) -> str:
        parts: list[str] = []
        if stakes_report and stakes_report.combined_note != "Sem ajuste de necessidade":
            parts.append(f"necessidades: {stakes_report.combined_note}")
        if home_dist and home_dist.total_distortion > 0.001:
            parts.append(f"notícias {home_dist.team_name}")
        if away_dist and away_dist.total_distortion > 0.001:
            parts.append(f"notícias {away_dist.team_name}")
        if home_env and home_env.total_distortion > 0.001:
            parts.append(f"ambiente {home_env.team_name}")
        if away_env and away_env.total_distortion > 0.001:
            parts.append(f"ambiente {away_env.team_name}")
        if mode == "live":
            parts.append("modo ao vivo")
        return f" [{', '.join(parts)}]" if parts else ""