"""Registo unificado de tips IA — pré-jogo, ao vivo e motor autónomo."""

from __future__ import annotations

from bots.ia_audit import is_ia_bot
from config.data_paths import BOT_SIGNALS_LOG, IA_LIVE_SIGNALS, PREDICTIONS_LOG
from history.tips_history import _read_all_rows, compute_performance, performance_to_dict

IA_TIP_SOURCES = frozenset({"ia_autonomous", "ia_bot"})


def _row_signature(row: dict, *, origin: str) -> str:
    sig = row.get("signature")
    if sig:
        return str(sig)
    rid = row.get("id")
    if rid:
        return f"{origin}|{rid}"
    return (
        f"{origin}|{row.get('logged_at')}|{row.get('home')}|{row.get('away')}|"
        f"{row.get('market')}|{row.get('minute')}"
    )


def _normalize_mode(row: dict) -> str:
    mode = str(row.get("mode") or "prematch").lower()
    return "live" if mode == "live" else "prematch"


def _normalize_ia_row(row: dict, *, origin: str) -> dict:
    mode = _normalize_mode(row)
    template = row.get("template")
    bot_name = row.get("bot_name")
    tip_source = row.get("tip_source")
    if not tip_source:
        if origin == "ia_live":
            tip_source = "ia_autonomous"
        elif origin == "bot_signal" or is_ia_bot(template, bot_name):
            tip_source = "ia_bot"
        else:
            tip_source = "ia_bot"
    return {
        **row,
        "mode": mode,
        "tip_source": tip_source,
        "signature": _row_signature(row, origin=origin),
        "outcome": str(row.get("outcome") or "pending").lower(),
    }


def load_ia_tip_rows(
    *,
    predictions_path=None,
    bot_signals_path=None,
    ia_live_path=None,
) -> list[dict]:
    """
    Todas as tips IA (deduplicadas) — bot_signals, ia_live_signals e predictions espelhadas.
    """
    pred_path = predictions_path or PREDICTIONS_LOG
    bot_path = bot_signals_path or BOT_SIGNALS_LOG
    live_path = ia_live_path or IA_LIVE_SIGNALS

    seen: set[str] = set()
    out: list[dict] = []

    def _add(row: dict, origin: str) -> None:
        norm = _normalize_ia_row(row, origin=origin)
        key = norm["signature"]
        if key in seen:
            return
        seen.add(key)
        out.append(norm)

    bot_sigs: set[str] = set()

    for row in _read_all_rows(live_path):
        _add({**row, "mode": "live"}, "ia_live")

    for row in _read_all_rows(bot_path):
        if is_ia_bot(row.get("template"), row.get("bot_name")):
            norm = _normalize_ia_row(row, origin="bot_signal")
            key = norm["signature"]
            if key not in seen:
                seen.add(key)
                bot_sigs.add(key)
                out.append(norm)

    for row in _read_all_rows(pred_path):
        src = str(row.get("tip_source") or "")
        if src not in IA_TIP_SOURCES:
            continue
        sig = str(row.get("signature") or "")
        if src == "ia_bot" and sig.startswith("pred|") and sig[5:] in bot_sigs:
            continue
        _add(row, "prediction")

    out.sort(key=lambda r: str(r.get("logged_at") or ""), reverse=True)
    return out


def _already_in_predictions(ia_row: dict, pred_sigs: set[str]) -> bool:
    sig = str(ia_row.get("signature") or "")
    if sig and sig in pred_sigs:
        return True
    if sig and f"pred|{sig}" in pred_sigs:
        return True
    return False


def load_trackable_tip_rows(
    *,
    predictions_path=None,
    bot_signals_path=None,
    ia_live_path=None,
) -> list[dict]:
    """
    Tips para histórico global (pré + live): predictions + IA ainda não espelhadas.
    """
    pred_path = predictions_path or PREDICTIONS_LOG
    ia_rows = load_ia_tip_rows(
        predictions_path=pred_path,
        bot_signals_path=bot_signals_path,
        ia_live_path=ia_live_path,
    )
    rows = [
        {**r, "mode": _normalize_mode(r)}
        for r in _read_all_rows(pred_path)
    ]
    pred_sigs = {str(r.get("signature") or "") for r in rows if r.get("signature")}
    for ia_row in ia_rows:
        if not _already_in_predictions(ia_row, pred_sigs):
            rows.append(ia_row)
    rows.sort(key=lambda r: str(r.get("logged_at") or ""), reverse=True)
    return rows


def ia_performance_payload(rows: list[dict] | None = None) -> dict:
    data = rows if rows is not None else load_ia_tip_rows()
    totals = performance_to_dict(compute_performance(data))
    return {
        "totals": totals,
        "totals_by_mode": {
            "prematch": performance_to_dict(compute_performance(data, mode="prematch")),
            "live": performance_to_dict(compute_performance(data, mode="live")),
        },
    }