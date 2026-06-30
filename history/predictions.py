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
    espn_event_id: str | None
    espn_league_code: str | None
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
    *,
    min_score_for: object | None = None,
    league: str = "",
) -> object | None:
    """Primeiro mercado elegível que ainda não foi lançado neste confronto."""
    for market in all_markets:
        label = getattr(market, "label", "")
        score = getattr(market, "total_score", 0.0)
        required = min_score
        if callable(min_score_for):
            try:
                required = min_score_for(label, min_score, league=league)
            except TypeError:
                required = min_score_for(label, min_score)
        if label and label not in used_markets and score >= required:
            return market
    return None


def pick_unused_live_market(
    all_markets: list[object],
    used_markets: set[str],
    min_score: float,
) -> object | None:
    return pick_unused_market(all_markets, used_markets, min_score)


def _append_raw_rows(rows: list[dict], *, log_path: Path | None = None) -> int:
    if not rows:
        return 0
    path = log_path or DEFAULT_LOG
    known = _load_recent_signatures(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            sig = row.get("signature")
            if sig and sig in known:
                continue
            if sig:
                known.add(str(sig))
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def ia_autonomous_signature(row: dict) -> str:
    return (
        f"ia_live|{row.get('espn_event_id')}|{row.get('home')}|{row.get('away')}|"
        f"{row.get('market')}|{row.get('minute')}|{row.get('logged_at')}"
    )


def append_ia_autonomous_predictions(
    records: list[dict],
    *,
    log_path: Path | None = None,
) -> int:
    """Espelha sinais do motor IA autónomo em predictions.jsonl (mode=live)."""
    if not records:
        return 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict] = []
    for rec in records:
        market = str(rec.get("market") or "").strip()
        odd = rec.get("book_odd") or rec.get("odd")
        if not market or odd is None:
            continue
        try:
            odd_f = float(odd)
        except (TypeError, ValueError):
            continue
        if odd_f < 1.01:
            continue
        sig = ia_autonomous_signature(rec)
        rows.append(
            {
                "logged_at": rec.get("logged_at") or now,
                "scanned_at": now,
                "mode": "live",
                "tip_source": "ia_autonomous",
                "home": rec.get("home"),
                "away": rec.get("away"),
                "league": rec.get("league"),
                "kickoff": "",
                "stage": "",
                "market": market,
                "odd": round(odd_f, 3),
                "model_prob": rec.get("model_prob"),
                "ev_pct": rec.get("ev_pct"),
                "score": None,
                "min_score": None,
                "kelly_stake": rec.get("stake_raw"),
                "bankroll": None,
                "minute": rec.get("minute"),
                "score_at_tip": "",
                "outcome": "pending",
                "fixture_id": None,
                "espn_event_id": rec.get("espn_event_id"),
                "espn_league_code": rec.get("espn_league_code"),
                "stake_level": None,
                "stake_label": "",
                "stake_pct": rec.get("bankroll_pct"),
                "stake_amount": rec.get("stake_raw"),
                "signature": sig,
            }
        )
    return _append_raw_rows(rows, log_path=log_path)


def append_ia_bot_prediction_mirror(
    row: dict,
    *,
    log_path: Path | None = None,
) -> int:
    """Espelha um sinal IA de bot_signals → predictions (pré ou live)."""
    sig = row.get("signature")
    if not sig:
        return 0
    mode = str(row.get("mode") or "prematch").lower()
    mirror = {
        **{k: v for k, v in row.items() if k != "ia_context"},
        "tip_source": "ia_bot",
        "mode": "live" if mode == "live" else "prematch",
        "signature": f"pred|{sig}",
        "outcome": str(row.get("outcome") or "pending").lower(),
    }
    return _append_raw_rows([mirror], log_path=log_path)


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
                espn_event_id=getattr(fx, "espn_event_id", "") or None,
                espn_league_code=getattr(fx, "espn_league_code", "") or None,
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
                espn_event_id=getattr(fx, "espn_event_id", "") or None,
                espn_league_code=getattr(fx, "espn_league_code", "") or None,
                stake_level=plan.level,
                stake_label=plan.label,
                stake_pct=plan.bankroll_pct,
                stake_amount=plan.suggested_amount,
            )
        )
        signatures.append(sig)

    return _write_entries(entries, signatures, log_path=path)