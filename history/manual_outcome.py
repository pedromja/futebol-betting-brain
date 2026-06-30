"""Correcção manual de resultado — GREEN/RED quando a resolução automática falha."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config.data_paths import BOT_SIGNALS_LOG, PREDICTIONS_LOG
from history.market_settlement import pnl_for_outcome, settlement_note
from history.outcome_resolver import _write_rows

_VALID_OUTCOMES = frozenset({"win", "loss", "void", "pending"})
_KIND_PATHS = {
    "tip": PREDICTIONS_LOG,
    "tips": PREDICTIONS_LOG,
    "bot": BOT_SIGNALS_LOG,
    "bots": BOT_SIGNALS_LOG,
    "signal": BOT_SIGNALS_LOG,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public_id(row: dict, *, kind: str) -> str:
    sig = row.get("signature")
    if sig:
        return str(sig)
    if kind in ("bot", "bots", "signal"):
        return f"{row.get('bot_id')}|{row.get('logged_at')}"
    return f"{row.get('home')}|{row.get('away')}|{row.get('logged_at')}"


def _load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def find_row_index(rows: list[dict], entry_id: str, *, kind: str) -> int | None:
    needle = (entry_id or "").strip()
    if not needle:
        return None
    for idx, row in enumerate(rows):
        if str(row.get("signature") or "") == needle:
            return idx
        if _public_id(row, kind=kind) == needle:
            return idx
    return None


def _recalc_pnl(row: dict, outcome: str) -> float | None:
    if outcome == "void":
        return 0.0
    if outcome == "pending":
        return None
    try:
        odd_f = float(row.get("odd") or 0)
        stake = row.get("stake_amount") or row.get("kelly_stake")
        stake_f = float(stake) if stake is not None else None
        return pnl_for_outcome(outcome, odd_f, stake_f)
    except (TypeError, ValueError):
        return None


def apply_manual_correction(
    row: dict,
    *,
    outcome: str,
    final_score: str | None = None,
    note: str | None = None,
) -> dict:
    new_outcome = str(outcome or "").lower().strip()
    if new_outcome not in _VALID_OUTCOMES:
        raise ValueError(f"Outcome inválido: {outcome}")

    now = _now_iso()
    prev_outcome = str(row.get("outcome") or "pending").lower()
    prev_pnl = row.get("pnl")
    prev_score = row.get("final_score")

    row["manual_correction"] = {
        "corrected_at": now,
        "previous_outcome": prev_outcome,
        "previous_pnl": prev_pnl,
        "previous_final_score": prev_score,
        "note": (note or "").strip(),
        "by": "user",
    }
    row["outcome"] = new_outcome
    row["pnl"] = _recalc_pnl(row, new_outcome)

    if final_score is not None and str(final_score).strip():
        row["final_score"] = str(final_score).strip()

    if new_outcome == "pending":
        row["resolved_at"] = None
    else:
        row["resolved_at"] = now

    note_txt = (note or "").strip()
    change = f"{prev_outcome.upper()} → {new_outcome.upper()}"
    context = f"Corrigido manualmente: {change}"
    if note_txt:
        context = f"{context} — {note_txt}"
    if row.get("final_score"):
        context = f"{context} · FT {row['final_score']}"
        score = str(row["final_score"])
        if "-" in score:
            try:
                hg, ag = [int(x.strip()) for x in score.split("-", 1)]
                settle_note = settlement_note(
                    str(row.get("market") or ""),
                    hg,
                    ag,
                    new_outcome,
                )
                if settle_note:
                    context = f"{context} · {settle_note}"
            except ValueError:
                pass

    row["review"] = {
        "status": "manual",
        "reviewed_at": now,
        "outcome_confirmed": True,
        "needs_verification": False,
        "context_note": context,
        "verify_prompt": None,
        "sources": ["manual"],
    }
    return row


def correct_outcome(
    *,
    kind: str,
    entry_id: str,
    outcome: str,
    final_score: str | None = None,
    note: str | None = None,
    log_path: Path | None = None,
) -> dict:
    kind_key = str(kind or "tip").lower().strip()
    path = log_path or _KIND_PATHS.get(kind_key)
    if not path:
        raise ValueError(f"Tipo inválido: {kind}")

    rows = _load_rows(path)
    idx = find_row_index(rows, entry_id, kind=kind_key)
    if idx is None:
        raise LookupError("Entrada não encontrada")

    row = apply_manual_correction(
        rows[idx],
        outcome=outcome,
        final_score=final_score,
        note=note,
    )
    _write_rows(path, rows)
    return row


def manual_correction_to_public(row: dict) -> dict | None:
    mc = row.get("manual_correction")
    if not mc:
        return None
    return {
        "corrected_at": mc.get("corrected_at"),
        "previous_outcome": mc.get("previous_outcome"),
        "note": mc.get("note"),
    }