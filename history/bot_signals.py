"""Registo persistente de sinais dos bots — para PnL e ROI por estratégia."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from bankroll.ev_stake import suggest_stake
from config.data_paths import BOT_SIGNALS_LOG

DEFAULT_LOG = BOT_SIGNALS_LOG
_RECENT_HOURS = 8
_TAIL_LINES = 1200


@dataclass
class BotSignalLog:
    logged_at: str
    scanned_at: str
    bot_id: str
    bot_name: str
    mode: str
    home: str
    away: str
    league: str
    kickoff: str
    stage: str
    market: str
    odd: float
    ev_pct: float
    score: float
    minute: int | None
    score_at_tip: str
    outcome: str
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


def _prematch_signature(bot_id: str, match: dict) -> str:
    return (
        f"bot|{bot_id}|prematch|{match.get('home')}|{match.get('away')}|"
        f"{match.get('best_market')}|{match.get('kickoff')}"
    )


def _live_signature(bot_id: str, match: dict) -> str:
    score = match.get("score") or ""
    if not score and match.get("home_score") is not None:
        score = f"{match.get('home_score')}-{match.get('away_score')}"
    return (
        f"bot|{bot_id}|live|{match.get('home')}|{match.get('away')}|"
        f"{match.get('best_market')}|{score}|{match.get('minute')}"
    )


def _write_entries(
    entries: list[BotSignalLog],
    signatures: list[str],
    *,
    log_path: Path | None = None,
) -> int:
    if not entries:
        return 0
    path = log_path or DEFAULT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry, sig in zip(entries, signatures):
            row = asdict(entry)
            row["signature"] = sig
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(entries)


def append_bot_hits(
    hits: list[dict],
    *,
    scanned_at: str,
    bankroll: float | None = None,
    log_path: Path | None = None,
) -> int:
    """Grava cada par (bot, jogo) uma vez por janela de dedup."""
    if not hits:
        return 0
    path = log_path or DEFAULT_LOG
    known = _load_recent_signatures(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entries: list[BotSignalLog] = []
    signatures: list[str] = []

    for hit in hits:
        bot_id = str(hit.get("bot_id") or "")
        if not bot_id:
            continue
        mode = str(hit.get("mode") or "prematch")
        for match in hit.get("matches") or []:
            market = str(match.get("best_market") or "").strip()
            odd = match.get("odd")
            if not market or odd is None:
                continue
            try:
                odd_f = float(odd)
            except (TypeError, ValueError):
                continue
            if odd_f <= 1.0:
                continue

            sig_fn = _live_signature if mode == "live" else _prematch_signature
            sig = sig_fn(bot_id, match)
            if sig in known:
                continue
            known.add(sig)

            ev_pct = match.get("best_ev_pct")
            try:
                ev_decimal = float(ev_pct) / 100.0
            except (TypeError, ValueError):
                ev_decimal = 0.0

            plan = suggest_stake(
                ev_decimal,
                bankroll,
                league=str(match.get("league") or ""),
                stage=str(match.get("stage") or ""),
            )
            stake_level = match.get("stake_level")
            stake_label = match.get("stake_label")
            stake_pct = match.get("stake_pct")
            stake_amount = match.get("stake_amount")
            if stake_level is not None:
                try:
                    plan_level = int(stake_level)
                    stake_level = plan_level
                    stake_label = str(stake_label or plan.label)
                    stake_pct = float(stake_pct) if stake_pct is not None else plan.bankroll_pct
                    stake_amount = (
                        float(stake_amount) if stake_amount is not None else plan.suggested_amount
                    )
                except (TypeError, ValueError):
                    stake_level = plan.level
                    stake_label = plan.label
                    stake_pct = plan.bankroll_pct
                    stake_amount = plan.suggested_amount
            else:
                stake_level = plan.level
                stake_label = plan.label
                stake_pct = plan.bankroll_pct
                stake_amount = plan.suggested_amount

            score_at_tip = ""
            if mode == "live":
                score_at_tip = str(match.get("score") or "")
                if not score_at_tip and match.get("home_score") is not None:
                    score_at_tip = f"{match.get('home_score')}-{match.get('away_score')}"

            minute = match.get("minute")
            try:
                minute_i = int(minute) if minute is not None else None
            except (TypeError, ValueError):
                minute_i = None

            fixture_id = match.get("fixture_id")
            try:
                fixture_id_i = int(fixture_id) if fixture_id else None
            except (TypeError, ValueError):
                fixture_id_i = None

            entries.append(
                BotSignalLog(
                    logged_at=now,
                    scanned_at=scanned_at or now,
                    bot_id=bot_id,
                    bot_name=str(hit.get("bot_name") or ""),
                    mode=mode,
                    home=str(match.get("home") or ""),
                    away=str(match.get("away") or ""),
                    league=str(match.get("league") or ""),
                    kickoff=str(match.get("kickoff") or ""),
                    stage=str(match.get("stage") or ""),
                    market=market,
                    odd=round(odd_f, 2),
                    ev_pct=round(float(ev_pct or 0), 1),
                    score=round(float(match.get("best_score") or 0), 3),
                    minute=minute_i,
                    score_at_tip=score_at_tip,
                    outcome="pending",
                    fixture_id=fixture_id_i,
                    stake_level=stake_level,
                    stake_label=stake_label or "",
                    stake_pct=stake_pct,
                    stake_amount=stake_amount,
                )
            )
            signatures.append(sig)

    return _write_entries(entries, signatures, log_path=path)