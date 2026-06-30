"""Auditoria e aprendizagem — performance green/red dos modelos IA."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from config.data_paths import BOT_SIGNALS_LOG, IA_AUDIT_FILE, ensure_data_dir
from history.learning import RECENT_HALF_LIFE_DAYS, _decay_weight, _parse_ts, _rate
from history.tips_history import _read_all_rows

AUDIT_VERSION = 1

IA_TEMPLATE_PREFIXES = ("live_pattern_", "live_scenario_")
IA_PREMATCH_TEMPLATES = frozenset(
    {
        "prematch_underdog_raca_ia",
        "prematch_underdog_galinha_ia",
        "prematch_underdog_favorite_hunt",
    }
)

MIN_RESOLVED_GLOBAL = 8
MIN_SAMPLES_MODEL = 6
MIN_SAMPLES_COMBO = 5
WEAK_HIT_RATE = 38.0
STRONG_HIT_RATE = 58.0
WEAK_ROI_PCT = -22.0
STRONG_ROI_PCT = 8.0

_CACHE_TTL_SEC = 120
_cache_state: dict | None = None
_cache_at: float = 0.0


def _audit_enabled() -> bool:
    return os.getenv("IA_AUDIT", "1").strip().lower() not in ("0", "false", "no")


def is_ia_template(template: str | None) -> bool:
    t = str(template or "")
    if t in IA_PREMATCH_TEMPLATES:
        return True
    return any(t.startswith(p) for p in IA_TEMPLATE_PREFIXES)


def is_ia_bot(template: str | None, bot_name: str | None = None) -> bool:
    if is_ia_template(template):
        return True
    name = str(bot_name or "").lower()
    return "ia —" in name or name.startswith("ia ")


def extract_ia_context(match: dict) -> dict:
    """Metadados IA gravados em cada sinal para auditoria."""
    keys = (
        "pattern_source",
        "pattern_window",
        "pattern_hist_situation",
        "pattern_situation",
        "pattern_discrepancy_score",
        "pattern_situation_sample",
        "scenario_id",
        "scenario_name",
        "scenario_apathetic",
        "scenario_reaction_confirmed",
        "scenario_play_allowed",
        "scenario_field_gap",
        "underdog_scenario",
        "underdog_significant",
        "underdog_favorite_hunt",
        "underdog_scoring_alert",
        "underdog_rate_vs_strong_pct",
        "underdog_rate_vs_weak_pct",
        "underdog_z_score",
        "underdog_p_value",
        "underdog_progress_pct",
        "underdog_ia_alert",
        "underdog_ia_play_allowed",
        "underdog_ia_favorite_hunt",
    )
    ctx: dict = {}
    for k in keys:
        if k in match and match.get(k) is not None:
            ctx[k] = match.get(k)
    for extra in ("pattern_summary", "scenario_summary", "underdog_summary", "underdog_ia_summary"):
        if match.get(extra):
            ctx[extra] = match.get(extra)
    return ctx


@dataclass
class IaRestriction:
    key: str
    kind: str
    blocked: bool
    reason: str
    samples: int = 0
    wins: int = 0
    losses: int = 0
    hit_rate_pct: float | None = None
    roi_pct: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IaAuditState:
    version: int = AUDIT_VERSION
    active: bool = False
    updated_at: str = ""
    resolved_ia: int = 0
    restrictions: list[dict] = field(default_factory=list)
    insights: list[dict] = field(default_factory=list)
    knowledge: list[str] = field(default_factory=list)
    by_template: dict = field(default_factory=dict)
    by_scenario: dict = field(default_factory=dict)
    by_window: dict = field(default_factory=dict)
    by_combo: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _agg() -> dict:
    return {"win": 0.0, "loss": 0.0, "pnl": 0.0, "stake": 0.0}


def _add(bucket: dict, row: dict, weight: float) -> None:
    outcome = str(row.get("outcome") or "").lower()
    if outcome not in ("win", "loss"):
        return
    bucket[outcome] += weight
    try:
        bucket["pnl"] += float(row.get("pnl") or 0)
    except (TypeError, ValueError):
        pass
    try:
        bucket["stake"] += float(row.get("stake_amount") or 0)
    except (TypeError, ValueError):
        pass


def _row_stats(name: str, bucket: dict) -> dict:
    w = int(round(bucket.get("win", 0)))
    l = int(round(bucket.get("loss", 0)))
    stake = bucket.get("stake", 0.0)
    pnl = bucket.get("pnl", 0.0)
    roi = round(100 * pnl / stake, 1) if stake > 0 else None
    return {
        "key": name,
        "wins": w,
        "losses": l,
        "samples": w + l,
        "hit_rate_pct": _rate(w, l),
        "roi_pct": roi,
        "total_pnl": round(pnl, 2),
    }


def _is_ia_row(row: dict) -> bool:
    if row.get("ia_context") or row.get("template"):
        return is_ia_bot(row.get("template"), row.get("bot_name"))
    return is_ia_bot(None, row.get("bot_name"))


def _template_key(row: dict) -> str:
    return str(row.get("template") or row.get("bot_id") or "unknown")


def _scenario_key(row: dict) -> str:
    ctx = row.get("ia_context") or {}
    return str(ctx.get("scenario_id") or "none")


def _window_key(row: dict) -> str:
    ctx = row.get("ia_context") or {}
    return str(ctx.get("pattern_window") or "unknown")


def _combo_key(row: dict) -> str:
    ctx = row.get("ia_context") or {}
    return (
        f"{_template_key(row)}|{ctx.get('scenario_id') or 'none'}|"
        f"{ctx.get('pattern_window') or 'any'}|{ctx.get('pattern_source') or 'any'}"
    )


def _evaluate_bucket(
    key: str,
    kind: str,
    stats: dict,
    *,
    min_samples: int,
) -> IaRestriction | None:
    samples = int(stats.get("samples") or 0)
    if samples < min_samples:
        return None
    hr = stats.get("hit_rate_pct")
    roi = stats.get("roi_pct")
    wins = int(stats.get("wins") or 0)
    losses = int(stats.get("losses") or 0)

    weak_hr = hr is not None and hr < WEAK_HIT_RATE
    weak_roi = roi is not None and roi < WEAK_ROI_PCT and samples >= min_samples + 2

    if not weak_hr and not weak_roi:
        return None

    parts = []
    if weak_hr:
        parts.append(f"hit rate {hr}% < {WEAK_HIT_RATE}%")
    if weak_roi:
        parts.append(f"ROI {roi}% < {WEAK_ROI_PCT}%")
    reason = f"Modelo IA fraco ({', '.join(parts)}) — {samples} entradas resolvidas"

    return IaRestriction(
        key=key,
        kind=kind,
        blocked=True,
        reason=reason,
        samples=samples,
        wins=wins,
        losses=losses,
        hit_rate_pct=hr,
        roi_pct=roi,
    )


def _insight_from_stats(key: str, kind: str, stats: dict) -> dict | None:
    samples = int(stats.get("samples") or 0)
    if samples < 4:
        return None
    hr = stats.get("hit_rate_pct")
    roi = stats.get("roi_pct")
    status = "neutral"
    if hr is not None:
        if hr >= STRONG_HIT_RATE and (roi is None or roi >= 0):
            status = "strong"
        elif hr < WEAK_HIT_RATE:
            status = "weak"
    return {**stats, "kind": kind, "status": status}


def _knowledge_line(kind: str, stats: dict) -> str | None:
    samples = int(stats.get("samples") or 0)
    hr = stats.get("hit_rate_pct")
    if samples < 4 or hr is None:
        return None
    roi = stats.get("roi_pct")
    roi_txt = f", ROI {roi}%" if roi is not None else ""
    label = stats.get("key", kind)
    verdict = "funciona" if hr >= STRONG_HIT_RATE else ("fraco" if hr < WEAK_HIT_RATE else "misto")
    return f"{label}: {hr}% green ({samples} entradas{roi_txt}) — {verdict}"


def build_ia_audit_dataset(log_path: Path | None = None) -> IaAuditState:
    rows = _read_all_rows(log_path or BOT_SIGNALS_LOG)
    ia_rows = [r for r in rows if _is_ia_row(r)]

    by_template: dict[str, dict] = {}
    by_scenario: dict[str, dict] = {}
    by_window: dict[str, dict] = {}
    by_combo: dict[str, dict] = {}
    resolved = 0

    for row in ia_rows:
        outcome = str(row.get("outcome") or "").lower()
        if outcome not in ("win", "loss"):
            continue
        resolved += 1
        logged = str(row.get("logged_at") or row.get("scanned_at") or "")
        w = _decay_weight(logged, half_life_days=RECENT_HALF_LIFE_DAYS)

        tk = _template_key(row)
        sk = _scenario_key(row)
        wk = _window_key(row)
        ck = _combo_key(row)

        for store, key in (
            (by_template, tk),
            (by_scenario, sk),
            (by_window, wk),
            (by_combo, ck),
        ):
            store.setdefault(key, _agg())
            _add(store[key], row, w)

    state = IaAuditState(
        updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        resolved_ia=resolved,
    )

    restrictions: list[IaRestriction] = []

    for key, bucket in by_template.items():
        stats = _row_stats(key, bucket)
        state.by_template[key] = stats
        hit = _evaluate_bucket(f"template:{key}", "template", stats, min_samples=MIN_SAMPLES_MODEL)
        if hit:
            restrictions.append(hit)

    for key, bucket in by_scenario.items():
        if key == "none":
            continue
        stats = _row_stats(key, bucket)
        state.by_scenario[key] = stats
        hit = _evaluate_bucket(f"scenario:{key}", "scenario", stats, min_samples=MIN_SAMPLES_MODEL)
        if hit:
            restrictions.append(hit)

    for key, bucket in by_window.items():
        if key == "unknown":
            continue
        stats = _row_stats(key, bucket)
        state.by_window[key] = stats

    for key, bucket in by_combo.items():
        stats = _row_stats(key, bucket)
        state.by_combo[key] = stats
        hit = _evaluate_bucket(f"combo:{key}", "combo", stats, min_samples=MIN_SAMPLES_COMBO)
        if hit:
            restrictions.append(hit)

    state.restrictions = [r.to_dict() for r in restrictions]

    insights: list[dict] = []
    knowledge: list[str] = []
    for kind, group in (
        ("template", state.by_template),
        ("scenario", state.by_scenario),
        ("window", state.by_window),
    ):
        for key, stats in group.items():
            ins = _insight_from_stats(key, kind, stats)
            if ins:
                insights.append(ins)
            line = _knowledge_line(kind, stats)
            if line:
                knowledge.append(line)

    state.insights = sorted(
        insights,
        key=lambda x: (-(x.get("hit_rate_pct") or 0), -(x.get("samples") or 0)),
    )[:24]
    state.knowledge = knowledge[:20]

    state.active = _audit_enabled() and bool(restrictions)

    if resolved < MIN_RESOLVED_GLOBAL:
        state.knowledge.insert(
            0,
            f"Amostra global {resolved}/{MIN_RESOLVED_GLOBAL} — restrições só com evidência por modelo.",
        )

    return state


def save_ia_audit(state: IaAuditState) -> Path:
    ensure_data_dir()
    IA_AUDIT_FILE.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return IA_AUDIT_FILE


def refresh_ia_audit(*, log_path: Path | None = None) -> IaAuditState:
    global _cache_state, _cache_at
    state = build_ia_audit_dataset(log_path)
    save_ia_audit(state)
    _cache_state = state.to_dict()
    _cache_at = datetime.now(timezone.utc).timestamp()
    return state


def load_ia_audit(*, max_age_sec: int = _CACHE_TTL_SEC) -> IaAuditState:
    global _cache_state, _cache_at
    now = datetime.now(timezone.utc).timestamp()
    if _cache_state and (now - _cache_at) < max_age_sec:
        data = _cache_state
    elif IA_AUDIT_FILE.exists():
        try:
            data = json.loads(IA_AUDIT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = IaAuditState().to_dict()
        _cache_state = data
        _cache_at = now
    else:
        return IaAuditState()

    return IaAuditState(
        version=int(data.get("version") or AUDIT_VERSION),
        active=bool(data.get("active")),
        updated_at=str(data.get("updated_at") or ""),
        resolved_ia=int(data.get("resolved_ia") or 0),
        restrictions=list(data.get("restrictions") or []),
        insights=list(data.get("insights") or []),
        knowledge=list(data.get("knowledge") or []),
        by_template=dict(data.get("by_template") or {}),
        by_scenario=dict(data.get("by_scenario") or {}),
        by_window=dict(data.get("by_window") or {}),
        by_combo=dict(data.get("by_combo") or {}),
    )


def _blocked_keys(state: IaAuditState) -> dict[str, str]:
    out: dict[str, str] = {}
    if not state.active:
        return out
    for row in state.restrictions:
        if not row.get("blocked"):
            continue
        key = str(row.get("key") or "")
        reason = str(row.get("reason") or "Modelo IA restrito por auditoria")
        if key:
            out[key] = reason
    return out


def check_ia_blocked(
    *,
    template: str | None,
    match: dict,
    audit: IaAuditState | None = None,
) -> tuple[bool, str]:
    """True se o sinal IA deve ser bloqueado por histórico red/weak."""
    state = audit or load_ia_audit()
    blocked = _blocked_keys(state)
    if not blocked:
        return False, ""

    tpl = str(template or "")
    if tpl:
        reason = blocked.get(f"template:{tpl}")
        if reason:
            return True, reason

    ctx = extract_ia_context(match)
    scenario = str(ctx.get("scenario_id") or "")
    if scenario and scenario != "none":
        reason = blocked.get(f"scenario:{scenario}")
        if reason:
            return True, reason

    combo = f"{tpl or 'unknown'}|{scenario or 'none'}|{ctx.get('pattern_window') or 'any'}|{ctx.get('pattern_source') or 'any'}"
    reason = blocked.get(f"combo:{combo}")
    if reason:
        return True, reason

    return False, ""


def maybe_refresh_ia_audit(*, min_new_resolved: int = 1) -> IaAuditState | None:
    """Recalcula auditoria após resolução de sinais."""
    if not _audit_enabled():
        return None
    prev = load_ia_audit(max_age_sec=0)
    state = refresh_ia_audit()
    if state.resolved_ia >= prev.resolved_ia + min_new_resolved or not prev.updated_at:
        return state
    if not IA_AUDIT_FILE.exists():
        return state
    return prev