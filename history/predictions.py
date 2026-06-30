"""Registo de dicas do robot — para aprender com acertos e erros."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from bankroll.ev_stake import suggest_stake
from config.data_paths import PREDICTIONS_LOG

DEFAULT_LOG = PREDICTIONS_LOG
_RECENT_HOURS = 8
_TAIL_LINES = 800


@dataclass
class PredictionLog:
    logged_at: str
    scanned_at: str
    mode: str
    home: str
    away: str
    league: str
    kickoff: str
    stage: str
    market: str
    odd: float
    model_prob: float
    ev_pct: float
    score: float
    min_score: float
    kelly_stake: float | None
    bankroll: float | None
    minute: int | None
    score_at_tip: str
    outcome: str | None
    fixture_id: int | None
    stake_level: int | None
    stake_label: str
    stake_pct: float | None
    stake_amount: float | None


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_recent_signatures(path: Path) -> set[str]:
    if not path.exists():
        return set()
    cutoff = datetime.now(timezone.utc).timestamp() - _RECENT_HOURS * 3600
    sigs: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return sigs
    for line in lines[-_TAIL_LINES:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        logged = _parse_ts(str(row.get("logged_at", "")))
        if logged and logged.timestamp() < cutoff:
            continue
        sig = row.get("signature")
        if sig:
            sigs.add(sig)
    return sigs


def _prematch_signature(item: object) -> str:
    fx = item.fixture
    return (
        f"prematch|{fx.home}|{fx.away}|{item.best_market}|"
        f"{fx.kickoff}|{item.best_score:.3f}"
    )


def _live_signature(item: object) -> str:
    fx = item.fixture
    return (
        f"live|{fx.home}|{fx.away}|{item.best_market}|"
        f"{fx.score_label}|{fx.minute}|{item.best_score:.3f}"
    )


def _fixture_key(home: str, away: str) -> str:
    return f"{home}|{away}"


def _fixture_id_from_hint(fixture: object) -> int | None:
    hint = getattr(fixture, "stats_hint", None) or {}
    raw = hint.get("api_football_fixture_id") or hint.get("fixture_id")
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def load_fixture_markets_used(
    log_path: Path | None = None,
    *,
    mode: str | None = None,
) -> dict[str, set[str]]:
    """Mercados já lançados por confronto (sem limite de tempo)."""
    path = log_path or DEFAULT_LOG
    used: dict[str, set[str]] = {}
    if not path.exists():
        return used
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return used
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row_mode = str(row.get("mode") or "prematch").strip()
        if mode and row_mode != mode:
            continue
        home = str(row.get("home", "")).strip()
        away = str(row.get("away", "")).strip()
        market = str(row.get("market", "")).strip()
        if not home or not away or not market:
            continue
        key = _fixture_key(home, away)
        used.setdefault(key, set()).add(market)
    return used


def load_live_markets_used(log_path: Path | None = None) -> dict[str, set[str]]:
    return load_fixture_markets_used(log_path, mode="live")


def markets_used_for_fixture(
    home: str,
    away: str,
    *,
    cache: dict[str, set[str]] | None = None,
    log_path: Path | None = None,
    mode: str | None = None,
) -> set[str]:
    if cache is not None:
        return set(cache.get(_fixture_key(home, away), set()))
    return set(
        load_fixture_markets_used(log_path, mode=mode).get(_fixture_key(home, away), set())
    )


def live_markets_used_for_fixture(
    home: str,
    away: str,
    *,
    cache: dict[str, set[str]] | None = None,
    log_path: Path | None = None,
) -> set[str]:
    return markets_used_for_fixture(home, away, cache=cache, log_path=log_path)


def pick_unused_market(
    all_markets: list[object],
    used_markets: set[str],
    min_score: float,
) -> object | None:
    """Primeiro mercado elegível que ainda não foi lançado neste confronto."""
    for market in all_markets:
        label = getattr(market, "label", "")
        score = getattr(market, "total_score", 0.0)
        if label and label not in used_markets and score >= min_score:
            return market
    return None


def pick_unused_live_market(
    all_markets: list[object],
    used_markets: set[str],
    min_score: float,
) -> object | None:
    return pick_unused_market(all_markets, used_markets, min_score)


def _write_entries(
    entries: list[PredictionLog],
    signatures: list[str],
    *,
    log_path: Path | None = None,
) -> int:
    if not entries:
        return 0
    path = log_path or DEFAULT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("a", encoding="utf-8") as fh:
        for entry, sig in zip(entries, signatures):
            row = asdict(entry)
            row["signature"] = sig
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def append_scan_predictions(
    result: object,
    *,
    bankroll: float | None = None,
    log_path: Path | None = None,
    only_recommended: bool = True,
) -> int:
    path = log_path or DEFAULT_LOG
    known = _load_recent_signatures(path)
    fixture_markets = load_fixture_markets_used(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries: list[PredictionLog] = []
    signatures: list[str] = []

    for item in result.ranked:
        if only_recommended and not item.should_bet:
            continue
        best = item.decision.recommendation.best
        if not best:
            continue
        fx = item.fixture
        fx_key = _fixture_key(fx.home, fx.away)
        if item.best_market in fixture_markets.get(fx_key, set()):
            continue
        sig = _prematch_signature(item)
        if sig in known:
            continue
        known.add(sig)
        fixture_markets.setdefault(fx_key, set()).add(item.best_market)
        plan = getattr(item, "stake_plan", None) or suggest_stake(
            item.best_ev,
            bankroll,
            league=fx.league,
            stage=fx.stage,
        )
        entries.append(
            PredictionLog(
                logged_at=now,
                scanned_at=result.scanned_at,
                mode="prematch",
                home=fx.home,
                away=fx.away,
                league=fx.league,
                kickoff=fx.kickoff,
                stage=fx.stage,
                market=item.best_market,
                odd=best.odd,
                model_prob=round(best.model_prob, 4),
                ev_pct=round(item.best_ev * 100, 1),
                score=round(item.best_score, 3),
                min_score=item.effective_min_score,
                kelly_stake=item.kelly_stake,
                bankroll=bankroll,
                minute=None,
                score_at_tip="",
                outcome="pending",
                fixture_id=_fixture_id_from_hint(fx),
                stake_level=plan.level,
                stake_label=plan.label,
                stake_pct=plan.bankroll_pct,
                stake_amount=plan.suggested_amount,
            )
        )
        signatures.append(sig)

    return _write_entries(entries, signatures, log_path=path)


def append_live_predictions(
    result: object,
    *,
    bankroll: float | None = None,
    log_path: Path | None = None,
    only_recommended: bool = True,
) -> int:
    path = log_path or DEFAULT_LOG
    known = _load_recent_signatures(path)
    fixture_markets = load_fixture_markets_used(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries: list[PredictionLog] = []
    signatures: list[str] = []

    for item in result.ranked:
        if only_recommended and not item.should_bet:
            continue
        best = item.decision.recommendation.best
        if not best:
            continue
        fx = item.fixture
        fx_key = _fixture_key(fx.home, fx.away)
        if item.best_market in fixture_markets.get(fx_key, set()):
            continue
        sig = _live_signature(item)
        if sig in known:
            continue
        known.add(sig)
        fixture_markets.setdefault(fx_key, set()).add(item.best_market)
        plan = getattr(item, "stake_plan", None) or suggest_stake(
            item.best_ev,
            bankroll,
            league=fx.league,
            stage=fx.stage,
        )
        entries.append(
            PredictionLog(
                logged_at=now,
                scanned_at=result.scanned_at,
                mode="live",
                home=fx.home,
                away=fx.away,
                league=fx.league,
                kickoff=fx.kickoff,
                stage=fx.stage,
                market=item.best_market,
                odd=best.odd,
                model_prob=round(best.model_prob, 4),
                ev_pct=round(item.best_ev * 100, 1),
                score=round(item.best_score, 3),
                min_score=item.effective_min_score,
                kelly_stake=item.kelly_stake,
                bankroll=bankroll,
                minute=fx.minute,
                score_at_tip=fx.score_label,
                outcome="pending",
                fixture_id=getattr(fx, "fixture_id", None) or _fixture_id_from_hint(fx),
                stake_level=plan.level,
                stake_label=plan.label,
                stake_pct=plan.bankroll_pct,
                stake_amount=plan.suggested_amount,
            )
        )
        signatures.append(sig)

    return _write_entries(entries, signatures, log_path=path)