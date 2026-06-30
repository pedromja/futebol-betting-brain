"""Testes — explicação legível de EV positivo para o diálogo na UI."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from markets.evaluator import LambdaBreakdown
from markets.markets import Market, MarketType, ScoreBreakdown
from web.api.serializers import build_ev_explanation, ranked_match_to_dict


def _market(
    *,
    market_type: MarketType = MarketType.HOME_WIN,
    odd: float = 2.10,
    model_prob: float = 0.52,
    implied_prob: float = 0.476,
    ev: float = 0.194,
    score: float = 0.62,
    reasoning: list[str] | None = None,
) -> Market:
    return Market(
        market_type=market_type,
        odd=odd,
        model_prob=model_prob,
        implied_prob=implied_prob,
        expected_value=ev,
        confidence=0.7,
        form_score=0.55,
        total_score=score,
        reasoning=reasoning or ["Forma recente favorável à casa", "Odd acima do fair value"],
        breakdown=ScoreBreakdown(
            normalized_ev=0.35,
            ev_contribution=0.14,
            conf_contribution=0.25,
            form_contribution=0.19,
            edge=0.044,
            prob_derivation="Soma P(h>a) em todos os resultados da matriz Poisson",
        ),
    )


class _Fixture:
    home = "Holanda"
    away = "Marrocos"
    league = "FIFA World Cup"
    kickoff = "2026-06-30T20:00:00Z"
    stage = "Round of 32"


class _Rec:
    def __init__(self, markets: list[Market]):
        self.all_markets = markets
        self.best = markets[0] if markets else None
        self.home_lambda = 1.45
        self.away_lambda = 1.12
        self.lambda_breakdown = LambdaBreakdown(
            home_attack=1.2,
            away_defense_factor=0.95,
            home_advantage=1.08,
            away_attack=1.0,
            home_defense_factor=1.05,
            league_avg=1.35,
            home_formula="λ_casa = ataque × defesa_adv × vantagem",
            away_formula="λ_fora = ataque × defesa_casa",
        )
        self.min_score = 0.55


class _Decision:
    def __init__(self, markets: list[Market]):
        self.recommendation = _Rec(markets)
        self.summary = "Melhor valor em vitória casa"
        self.environment = None
        self.stakes_report = None
        self.home_distortion = None
        self.away_distortion = None


class _Ranked:
    def __init__(self, markets: list[Market], *, should_bet: bool = True, ev: float | None = None):
        self.fixture = _Fixture()
        self.decision = _Decision(markets)
        self.best_ev = ev if ev is not None else (markets[0].expected_value if markets else 0)
        self.best_market = markets[0].label if markets else ""
        self.best_score = markets[0].total_score if markets else 0
        self.should_bet = should_bet
        self.effective_min_score = 0.55
        self.top_markets = [m.label for m in markets[:3]]
        self.kelly_stake = None
        self.kelly_pct = None
        self.stake_plan = None
        self.rank = 1
        self.transfermarkt = {"summary": "Plantel equilibrado", "data_available": True, "signals": ["Lesão leve no avançado"]}
        self.motivation = {"summary": "Eliminatória — alta pressão", "labels": ["Jogo a eliminar"]}
        self.competition_progress = {"progress_pct": 78}
        self.block_reason = None
        self.learning_tune = None


def test_build_ev_explanation_none_when_ev_not_positive():
    market = _market(ev=0.0)
    assert build_ev_explanation(_Ranked([market], ev=0.0)) is None


def test_build_ev_explanation_includes_human_readable_fields():
    home = _market()
    draw = _market(market_type=MarketType.DRAW, ev=0.05, score=0.48)
    item = _Ranked([home, draw], should_bet=True)

    ex = build_ev_explanation(item)
    assert ex is not None
    assert ex["market"] == "Vitória Casa"
    assert ex["ev_pct"] == 19.4
    assert ex["model_prob_pct"] == 52.0
    assert ex["implied_prob_pct"] == 47.6
    assert ex["edge_pct"] == 4.4
    assert "Vitória Casa" in ex["headline"]
    assert len(ex["reasoning"]) == 2
    assert ex["score_breakdown"]["ev_contribution"] == 0.14
    assert ex["expected_goals"]["home"] == 1.45
    assert ex["expected_goals"]["away"] == 1.12
    assert ex["should_bet"] is True
    assert any("Motivação" in f for f in ex["context_factors"])
    assert any("Transfermarkt" in f for f in ex["context_factors"])
    assert len(ex["alternatives"]) == 2


def test_ranked_match_to_dict_exposes_ev_explanation():
    item = _Ranked([_market()], should_bet=False)
    payload = ranked_match_to_dict(item)
    assert payload["ev_explanation"] is not None
    assert payload["ev_explanation"]["ev_pct"] == 19.4
    assert payload["should_bet"] is False