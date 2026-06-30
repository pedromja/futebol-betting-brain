"""Testes — mercado live não repete no mesmo confronto."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.predictions import (
    append_live_predictions,
    append_scan_predictions,
    load_fixture_markets_used,
    load_live_markets_used,
    pick_unused_live_market,
    pick_unused_market,
)
from markets.markets import Market, MarketType, ScoreBreakdown


def _market(label_key: MarketType, score: float) -> Market:
    return Market(
        market_type=label_key,
        odd=2.0,
        model_prob=0.5,
        implied_prob=0.5,
        expected_value=0.1,
        confidence=0.6,
        form_score=0.5,
        total_score=score,
        reasoning=[],
        breakdown=ScoreBreakdown(
            normalized_ev=0.1,
            ev_contribution=0.1,
            conf_contribution=0.1,
            form_contribution=0.1,
            edge=0.05,
            prob_derivation="test",
        ),
    )


class _Fx:
    home = "Brasil"
    away = "Argentina"
    league = "Amistoso"
    kickoff = "2026-06-30T20:00:00"
    stage = ""
    minute = 55
    score_label = "1-0"
    fixture_id = 99

    @property
    def label(self) -> str:
        return f"{self.home} vs {self.away}"


class _PrematchFx:
    home = "Mexico"
    away = "Ecuador"
    league = "FIFA World Cup"
    kickoff = "2026-07-01T01:00:00Z"
    stage = "Round of 32"


class _Rec:
    def __init__(self, markets: list[Market]):
        self.all_markets = markets
        self.best = markets[0] if markets else None


class _Decision:
    def __init__(self, markets: list[Market]):
        self.recommendation = _Rec(markets)


class _Ranked:
    def __init__(self, market: Market, *, should_bet: bool = True, fixture=None):
        self.fixture = fixture or _Fx()
        self.decision = _Decision([market])
        self.best_market = market.label
        self.best_ev = market.expected_value
        self.best_score = market.total_score
        self.should_bet = should_bet
        self.effective_min_score = 0.55
        self.kelly_stake = None
        self.stake_plan = None


class _Result:
    def __init__(self, ranked: list[_Ranked]):
        self.ranked = ranked
        self.scanned_at = "2026-06-30T21:00:00"


class _ScanResult:
    def __init__(self, ranked: list[_Ranked]):
        self.ranked = ranked
        self.scanned_at = "2026-06-30T21:00:00"


def test_load_live_markets_used_from_log(tmp_path):
    log = tmp_path / "load.jsonl"
    rows = [
        {
            "mode": "live",
            "home": "Brasil",
            "away": "Argentina",
            "market": "Over 2.5",
        },
        {
            "mode": "live",
            "home": "Brasil",
            "away": "Argentina",
            "market": "BTTS Sim",
        },
        {
            "mode": "prematch",
            "home": "Brasil",
            "away": "Argentina",
            "market": "Vitória Casa",
        },
    ]
    log.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )

    used = load_live_markets_used(log)
    assert used["Brasil|Argentina"] == {"Over 2.5", "BTTS Sim"}


def test_pick_unused_live_market_skips_used():
    markets = [
        _market(MarketType.OVER_25, 0.72),
        _market(MarketType.UNDER_25, 0.61),
        _market(MarketType.BTTS_YES, 0.58),
    ]
    used = {"Over 2.5"}
    picked = pick_unused_live_market(markets, used, min_score=0.55)
    assert picked is not None
    assert picked.label == "Under 2.5"


def test_pick_unused_returns_none_when_all_used():
    markets = [_market(MarketType.OVER_25, 0.72)]
    used = {"Over 2.5"}
    assert pick_unused_live_market(markets, used, min_score=0.55) is None


def test_append_live_predictions_skips_repeated_market(tmp_path):
    log = tmp_path / "append_once.jsonl"
    market = _market(MarketType.OVER_25, 0.7)
    first = _Result([_Ranked(market)])
    assert append_live_predictions(first, log_path=log) == 1

    second = _Result([_Ranked(market)])
    assert append_live_predictions(second, log_path=log) == 0

    used = load_live_markets_used(log)
    assert used["Brasil|Argentina"] == {"Over 2.5"}


def test_pick_unused_market_alias():
    markets = [
        _market(MarketType.BTTS_NO, 0.72),
        _market(MarketType.OVER_25, 0.61),
    ]
    used = {"BTTS Não"}
    picked = pick_unused_market(markets, used, min_score=0.55)
    assert picked is not None
    assert picked.label == "Over 2.5"


def test_append_scan_predictions_skips_same_market_despite_score_change(tmp_path):
    log = tmp_path / "prematch_dedup.jsonl"
    m1 = _market(MarketType.BTTS_NO, 0.716)
    m2 = _market(MarketType.BTTS_NO, 0.796)
    fx = _PrematchFx()
    first = _ScanResult([_Ranked(m1, fixture=fx)])
    assert append_scan_predictions(first, log_path=log) == 1

    second = _ScanResult([_Ranked(m2, fixture=fx)])
    assert append_scan_predictions(second, log_path=log) == 0

    used = load_fixture_markets_used(log)
    assert used["Mexico|Ecuador"] == {"BTTS Não"}


def test_live_blocks_market_already_used_in_prematch(tmp_path):
    log = tmp_path / "cross_mode.jsonl"
    btts = _market(MarketType.BTTS_NO, 0.7)
    fx = _PrematchFx()
    assert append_scan_predictions(
        _ScanResult([_Ranked(btts, fixture=fx)]), log_path=log
    ) == 1
    live_fx = _Fx()
    live_fx.home = fx.home
    live_fx.away = fx.away
    assert append_live_predictions(
        _Result([_Ranked(btts, fixture=live_fx)]), log_path=log
    ) == 0


def test_append_live_predictions_allows_different_market_same_fixture(tmp_path):
    log = tmp_path / "append_multi.jsonl"
    over = _market(MarketType.OVER_25, 0.7)
    under = _market(MarketType.UNDER_25, 0.62)

    assert append_live_predictions(_Result([_Ranked(over)]), log_path=log) == 1
    assert append_live_predictions(_Result([_Ranked(under)]), log_path=log) == 1

    used = load_live_markets_used(log)
    assert used["Brasil|Argentina"] == {"Over 2.5", "Under 2.5"}