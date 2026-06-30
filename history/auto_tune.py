"""Auto-aprendizagem — calibra min_score com histórico ponderado de apostas."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config.data_paths import DATA_DIR, ensure_data_dir
from history.learning import build_tune_dataset

TUNE_FILE = DATA_DIR / "learning_tune.json"
TUNE_VERSION = 3
MIN_RESOLVED = 8
MIN_MARKET_SAMPLES = 3
MIN_LEAGUE_SAMPLES = 4
MIN_MODE_SAMPLES = 5
MIN_COMBO_SAMPLES = 3
WEAK_HIT_RATE = 40.0
STRONG_HIT_RATE = 62.0
COMBO_WEAK_HIT_RATE = 35.0
MODE_WEAK_HIT_RATE = 42.0
LOW_BUCKET_WEAK = 45.0
MARKET_PENALTY = 0.05
LEAGUE_PENALTY = 0.03
COMBO_PENALTY = 0.04
MODE_PENALTY = 0.03
GLOBAL_LOW_BUCKET_BUMP = 0.04
EV_OVERCONFIDENCE_GAP = 4.0
EV_OVERCONFIDENCE_BUMP = 0.03
ROI_WEAK_PCT = -25.0
ROI_EXTRA_PENALTY = 0.02
STRONG_RELIEF = 0.02
MAX_BASE_DELTA = 0.10
MAX_MARKET_DELTA = 0.12
MAX_LEAGUE_DELTA = 0.08
MAX_MODE_DELTA = 0.06
MAX_COMBO_DELTA = 0.08
ABS_MIN_SCORE = 0.50
ABS_MAX_SCORE = 0.88
_CACHE_TTL_SEC = 300


def _auto_tune_enabled() -> bool:
    return os.getenv("AUTO_TUNE", "1").strip().lower() not in ("0", "false", "no")


@dataclass
class LearningTuneState:
    version: int = TUNE_VERSION
    active: bool = False
    resolved: int = 0
    base_delta: float = 0.0
    market_deltas: dict[str, float] = field(default_factory=dict)
    league_deltas: dict[str, float] = field(default_factory=dict)
    mode_deltas: dict[str, float] = field(default_factory=dict)
    combo_deltas: dict[str, float] = field(default_factory=dict)
    adjustments: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
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


def _hit_rate(row: dict, *, weighted: bool = False) -> float | None:
    if weighted:
        w, l = row.get("weighted_wins", 0), row.get("weighted_losses", 0)
    else:
        w, l = row.get("wins", 0), row.get("losses", 0)
    total = w + l
    if total <= 0:
        return None
    return 100 * w / total


def _scaled_penalty(base: float, wins: int, losses: int, hit_rate: float, weak_at: float) -> float:
    """Penalização proporcional à gravidade e ao tamanho da amostra."""
    if hit_rate >= weak_at:
        return 0.0
    severity = min(1.0, (weak_at - hit_rate) / weak_at)
    samples = wins + losses
    sample_factor = min(1.4, 0.75 + samples / 10)
    return round(base * (0.65 + 0.35 * severity) * sample_factor, 3)


def compute_tune_state(insights: dict | None = None) -> LearningTuneState:
    """Calcula deltas de min_score a partir do histórico resolvido."""
    if not _auto_tune_enabled():
        return LearningTuneState(
            active=False,
            reason="Auto-tune desactivado (AUTO_TUNE=0)",
        )

    data = insights or build_tune_dataset()
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
    mode_deltas: dict[str, float] = {}
    combo_deltas: dict[str, float] = {}
    adjustments: list[str] = []

    ev_cal = data.get("ev_calibration") or {}
    ev_gap = ev_cal.get("gap_pct")
    global_hit = data.get("hit_rate_pct")
    recent = data.get("recent") or {}

    metrics = {
        "hit_rate_pct": global_hit,
        "recent_hit_rate_pct": recent.get("hit_rate_pct"),
        "ev_gap_pct": ev_gap,
        "avg_ev_win_pct": ev_cal.get("avg_ev_win_pct"),
        "avg_ev_loss_pct": ev_cal.get("avg_ev_loss_pct"),
    }

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

    if ev_gap is not None and ev_gap >= EV_OVERCONFIDENCE_GAP and (global_hit or 100) < 52:
        base_delta += EV_OVERCONFIDENCE_BUMP
        adjustments.append(
            f"EV optimista (reds +{ev_gap}pp vs greens) → base +{EV_OVERCONFIDENCE_BUMP}"
        )

    recent_rate = recent.get("hit_rate_pct")
    if recent_rate is not None and recent_rate < 38 and (recent.get("resolved_weighted") or 0) >= 4:
        bump = 0.02
        base_delta += bump
        adjustments.append(f"Forma recente {recent_rate}% → base +{bump}")

    for row in data.get("by_market") or []:
        market = str(row.get("market") or "").strip()
        if not market or market == "—":
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < MIN_MARKET_SAMPLES:
            continue
        rate = _hit_rate(row) or row.get("hit_rate_pct")
        w_rate = _hit_rate(row, weighted=True)
        effective_rate = w_rate if w_rate is not None else rate
        if effective_rate is None:
            continue

        if effective_rate < WEAK_HIT_RATE:
            delta = _scaled_penalty(MARKET_PENALTY, w, l, effective_rate, WEAK_HIT_RATE)
            if delta:
                market_deltas[market] = _clamp_delta(delta, MAX_MARKET_DELTA)
                adjustments.append(f"{market}: {effective_rate:.1f}% → +{delta} min_score")
        elif effective_rate >= STRONG_HIT_RATE and w + l >= 5:
            market_deltas[market] = _clamp_delta(-STRONG_RELIEF, MAX_MARKET_DELTA)
            adjustments.append(f"{market}: {effective_rate:.1f}% → -{STRONG_RELIEF} min_score")

        roi = row.get("roi_pct")
        if roi is not None and roi <= ROI_WEAK_PCT and w + l >= MIN_MARKET_SAMPLES:
            extra = ROI_EXTRA_PENALTY
            market_deltas[market] = _clamp_delta(
                market_deltas.get(market, 0.0) + extra,
                MAX_MARKET_DELTA,
            )
            adjustments.append(f"{market}: ROI {roi}% → +{extra} extra")

    for row in data.get("by_league") or []:
        league = str(row.get("league") or "").strip()
        if not league or league == "—":
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < MIN_LEAGUE_SAMPLES:
            continue
        rate = _hit_rate(row, weighted=True) or row.get("hit_rate_pct")
        if rate is not None and rate < WEAK_HIT_RATE:
            delta = _scaled_penalty(LEAGUE_PENALTY, w, l, rate, WEAK_HIT_RATE)
            if delta:
                league_deltas[league] = _clamp_delta(delta, MAX_LEAGUE_DELTA)
                adjustments.append(f"Liga {league}: {rate:.1f}% → +{delta}")

    for row in data.get("by_mode") or []:
        mode = str(row.get("mode") or "").strip().lower()
        if mode not in ("prematch", "live"):
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < MIN_MODE_SAMPLES:
            continue
        rate = _hit_rate(row, weighted=True) or row.get("hit_rate_pct")
        if rate is not None and rate < MODE_WEAK_HIT_RATE:
            delta = _scaled_penalty(MODE_PENALTY, w, l, rate, MODE_WEAK_HIT_RATE)
            if delta:
                mode_deltas[mode] = _clamp_delta(delta, MAX_MODE_DELTA)
                label = "Pré-jogo" if mode == "prematch" else "Live"
                adjustments.append(f"{label}: {rate:.1f}% → +{delta}")

    for row in data.get("by_combo") or []:
        combo = str(row.get("combo") or "").strip()
        if not combo or "|" not in combo:
            continue
        w, l = row.get("wins", 0), row.get("losses", 0)
        if w + l < MIN_COMBO_SAMPLES:
            continue
        rate = _hit_rate(row, weighted=True) or row.get("hit_rate_pct")
        if rate is not None and rate < COMBO_WEAK_HIT_RATE:
            delta = _scaled_penalty(COMBO_PENALTY, w, l, rate, COMBO_WEAK_HIT_RATE)
            if delta:
                combo_deltas[combo] = _clamp_delta(delta, MAX_COMBO_DELTA)
                market, league = combo.split("|", 1)
                adjustments.append(f"{market} @ {league}: {rate:.1f}% → +{delta}")

    base_delta = _clamp_delta(base_delta, MAX_BASE_DELTA)

    has_deltas = bool(
        adjustments
        or base_delta
        or market_deltas
        or league_deltas
        or mode_deltas
        or combo_deltas
    )

    if not has_deltas:
        return LearningTuneState(
            active=True,
            resolved=resolved,
            metrics=metrics,
            reason="Histórico OK — sem ajustes necessários",
            updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    return LearningTuneState(
        active=True,
        resolved=resolved,
        base_delta=round(base_delta, 3),
        market_deltas={k: round(v, 3) for k, v in market_deltas.items()},
        league_deltas={k: round(v, 3) for k, v in league_deltas.items()},
        mode_deltas={k: round(v, 3) for k, v in mode_deltas.items()},
        combo_deltas={k: round(v, 3) for k, v in combo_deltas.items()},
        adjustments=adjustments[:12],
        metrics=metrics,
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
            version=int(raw.get("version") or 1),
            active=bool(raw.get("active")),
            resolved=int(raw.get("resolved") or 0),
            base_delta=float(raw.get("base_delta") or 0),
            market_deltas=dict(raw.get("market_deltas") or {}),
            league_deltas=dict(raw.get("league_deltas") or {}),
            mode_deltas=dict(raw.get("mode_deltas") or {}),
            combo_deltas=dict(raw.get("combo_deltas") or {}),
            adjustments=list(raw.get("adjustments") or []),
            metrics=dict(raw.get("metrics") or {}),
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

    data = build_tune_dataset(pred_path)
    state = compute_tune_state(data)
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
    mode: str = "prematch",
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
    mode_key = (mode or "prematch").lower()
    total += tune.mode_deltas.get(mode_key, 0.0)
    if league:
        combo = f"{market}|{league}"
        total += tune.combo_deltas.get(combo, 0.0)
    return _clamp_score(total)