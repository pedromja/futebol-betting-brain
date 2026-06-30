"""Auto-aprendizagem — ajusta min_score com base em greens/reds resolvidos."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config.data_paths import DATA_DIR, ensure_data_dir
from history.learning import build_learning_insights

TUNE_FILE = DATA_DIR / "learning_tune.json"
MIN_RESOLVED = 8
MIN_MARKET_SAMPLES = 3
MIN_LEAGUE_SAMPLES = 4
WEAK_HIT_RATE = 40.0
STRONG_HIT_RATE = 62.0
LOW_BUCKET_WEAK = 45.0
MARKET_PENALTY = 0.05
LEAGUE_PENALTY = 0.03
GLOBAL_LOW_BUCKET_BUMP = 0.04
STRONG_RELIEF = 0.02
MAX_BASE_DELTA = 0.08
MAX_MARKET_DELTA = 0.10
MAX_LEAGUE_DELTA = 0.06
ABS_MIN_SCORE = 0.50
ABS_MAX_SCORE = 0.88
_CACHE_TTL_SEC = 300


def _auto_tune_enabled() -> bool:
    return os.getenv("AUTO_TUNE", "1").strip().lower() not in ("0", "false", "no")


@dataclass
class LearningTuneState:
    active: bool = False
    resolved: int = 0
    base_delta: float = 0.0
    market_deltas: dict[str, float] = field(default_factory=dict)
    league_deltas: dict[str, float] = field(default_factory=dict)
    adjustments: list[str] = field(default_factory=list)
    updated_at: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


_cache: LearningTuneState | None = None
_cache_at: float = 0.0
_cache_mtime: float = 0.0


def _clamp_delta(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _clamp_score(value: float) -> float:
    return round(max(ABS_MIN_SCORE, min(ABS_MAX_SCORE, value)), 3)


def compute_tune_state(insights: dict | None = None) -> LearningTuneState:
    """Calcula deltas de min_score a partir do histórico resolvido."""
    if not _auto_tune_enabled():
        return LearningTuneState(
            active=False,
            reason="Auto-tune desactivado (AUTO_TUNE=0)",
        )

    data = insights or build_learning_insights()
    resolved = int(data.get("resolved") or 0)
    if resolved < MIN_RESOLVED:
        return LearningTuneState(
            active=False,
            resolved=resolved,
            reason=f"Dados insuficientes ({resolved}/{MIN_RESOLVED} resolvidas)",
        )

    base_delta = 0.0
    market_deltas: dict[str, float] = {}
    league_deltas: dict[str, float] = {}
    adjustments: list[str] = []

    for row in data.get("by_score_bucket") or []:
        if row.get("bucket") != "low":
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < 5:
            continue
        rate = row.get("hit_rate_pct")
        if rate is not None and rate < LOW_BUCKET_WEAK:
            base_delta += GLOBAL_LOW_BUCKET_BUMP
            adjustments.append(
                f"Scores baixos com {rate}% acerto → base +{GLOBAL_LOW_BUCKET_BUMP}"
            )
        break

    for row in data.get("by_market") or []:
        market = str(row.get("market") or "").strip()
        if not market or market == "—":
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < MIN_MARKET_SAMPLES:
            continue
        rate = row.get("hit_rate_pct")
        if rate is None:
            continue
        if rate < WEAK_HIT_RATE:
            market_deltas[market] = _clamp_delta(MARKET_PENALTY, MAX_MARKET_DELTA)
            adjustments.append(f"{market}: {rate}% → +{MARKET_PENALTY} min_score")
        elif rate >= STRONG_HIT_RATE and w + l >= 5:
            market_deltas[market] = _clamp_delta(-STRONG_RELIEF, MAX_MARKET_DELTA)
            adjustments.append(f"{market}: {rate}% → -{STRONG_RELIEF} min_score")

    for row in data.get("by_league") or []:
        league = str(row.get("league") or "").strip()
        if not league or league == "—":
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < MIN_LEAGUE_SAMPLES:
            continue
        rate = row.get("hit_rate_pct")
        if rate is not None and rate < WEAK_HIT_RATE:
            league_deltas[league] = _clamp_delta(LEAGUE_PENALTY, MAX_LEAGUE_DELTA)
            adjustments.append(f"Liga {league}: {rate}% → +{LEAGUE_PENALTY}")

    base_delta = _clamp_delta(base_delta, MAX_BASE_DELTA)

    if not adjustments:
        return LearningTuneState(
            active=True,
            resolved=resolved,
            reason="Histórico OK — sem ajustes necessários",
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    return LearningTuneState(
        active=True,
        resolved=resolved,
        base_delta=round(base_delta, 3),
        market_deltas={k: round(v, 3) for k, v in market_deltas.items()},
        league_deltas={k: round(v, 3) for k, v in league_deltas.items()},
        adjustments=adjustments,
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        reason=f"{len(adjustments)} ajuste(s) activos",
    )


def save_tune_state(state: LearningTuneState, path: Path | None = None) -> None:
    ensure_data_dir()
    target = path or TUNE_FILE
    target.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_tune_state(path: Path | None = None) -> LearningTuneState | None:
    target = path or TUNE_FILE
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return LearningTuneState(
            active=bool(raw.get("active")),
            resolved=int(raw.get("resolved") or 0),
            base_delta=float(raw.get("base_delta") or 0),
            market_deltas=dict(raw.get("market_deltas") or {}),
            league_deltas=dict(raw.get("league_deltas") or {}),
            adjustments=list(raw.get("adjustments") or []),
            updated_at=str(raw.get("updated_at") or ""),
            reason=str(raw.get("reason") or ""),
        )
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


def refresh_tune_state(*, log_path: Path | None = None, force: bool = False) -> LearningTuneState:
    """Recalcula e persiste o estado de auto-tune (com cache em memória)."""
    global _cache, _cache_at, _cache_mtime

    from history.predictions import DEFAULT_LOG

    pred_path = log_path or DEFAULT_LOG
    mtime = pred_path.stat().st_mtime if pred_path.exists() else 0.0
    now = time.time()

    if (
        not force
        and _cache is not None
        and mtime == _cache_mtime
        and (now - _cache_at) < _CACHE_TTL_SEC
    ):
        return _cache

    insights = build_learning_insights(pred_path)
    state = compute_tune_state(insights)
    if state.active:
        save_tune_state(state)

    _cache = state
    _cache_at = now
    _cache_mtime = mtime
    return state


def tuned_min_score(
    base_min: float,
    market: str,
    league: str = "",
    state: LearningTuneState | None = None,
) -> float:
    """min_score efectivo após dynamic_min_score + auto-tune."""
    tune = state or refresh_tune_state()
    if not tune.active:
        return _clamp_score(base_min)

    total = base_min + tune.base_delta
    total += tune.market_deltas.get(market, 0.0)
    if league:
        total += tune.league_deltas.get(league, 0.0)
    return _clamp_score(total)


