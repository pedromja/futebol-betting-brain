"""Merge conservador — usa a odd decimal menos favorável entre duas fontes."""

from __future__ import annotations

COMPARABLE_KEYS = (
    "home_win",
    "draw",
    "away_win",
    "over_25",
    "under_25",
    "btts_yes",
    "btts_no",
)

_INTERNAL_PREFIX = "_"


def _valid_odd(raw) -> float | None:
    try:
        val = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        val = None
    if val and val >= 1.01:
        return round(val, 3)
    return None


def _strip_internal(hint: dict | None) -> dict:
    oh = hint or {}
    return {k: v for k, v in oh.items() if not str(k).startswith(_INTERNAL_PREFIX)}


def less_favorable_odd(a: float | None, b: float | None) -> tuple[float | None, str | None]:
    """Devolve a odd mais baixa (pior para o apostador) e qual fonte foi escolhida."""
    if a is None and b is None:
        return None, None
    if a is None:
        return b, "niche"
    if b is None:
        return a, "espn"
    if abs(a - b) < 0.001:
        return a, "tie"
    if a < b:
        return a, "espn"
    return b, "niche"


def merge_conservative_odds(
    espn_hint: dict | None,
    niche_hint: dict | None,
    *,
    niche_book: str = "",
) -> dict:
    """
    Cruza odds ESPN com casas de nicho (ex. 1xBet via The-Odds-API).
    Por mercado, guarda a odd menos favorável (decimal mais baixa).
    """
    espn = _strip_internal(espn_hint)
    niche = _strip_internal(niche_hint)
    merged = dict(espn)
    compare: dict[str, dict] = {}

    for key in COMPARABLE_KEYS:
        e_odd = _valid_odd(espn.get(key))
        n_odd = _valid_odd(niche.get(key))
        used, picked = less_favorable_odd(e_odd, n_odd)
        if used is None:
            continue
        merged[key] = used
        entry: dict = {"used": used, "picked": picked or "espn"}
        if e_odd is not None:
            entry["espn"] = e_odd
        if n_odd is not None:
            entry["niche"] = n_odd
            entry["niche_book"] = niche_book or "niche"
        compare[key] = entry

    merged["_espn_raw"] = espn
    merged["_niche_raw"] = niche
    merged["_niche_book"] = niche_book or ""
    merged["_odds_compare"] = compare
    merged["_odds_enriched"] = True
    return merged


def public_odds_hint(hint: dict | None) -> dict:
    """Remove metadados internos — para LLM e API pública."""
    oh = hint or {}
    return {k: v for k, v in oh.items() if not str(k).startswith(_INTERNAL_PREFIX)}


def public_odds_compare(hint: dict | None) -> dict | None:
    """Resumo legível da comparação ESPN vs nicho."""
    oh = hint or {}
    raw = oh.get("_odds_compare")
    if not isinstance(raw, dict) or not raw:
        return None
    book = str(oh.get("_niche_book") or "niche")
    out: dict[str, dict] = {}
    for key, row in raw.items():
        if not isinstance(row, dict):
            continue
        out[key] = {
            "espn": row.get("espn"),
            "niche": row.get("niche"),
            "niche_book": row.get("niche_book") or book,
            "used": row.get("used"),
            "picked": row.get("picked"),
        }
    return {
        "niche_book": book,
        "markets": out,
    }


def format_odds_source_label(hint: dict | None, odds_key: str | None = None) -> str:
    """Etiqueta curta para UI — ex. min:1xBet (ESPN 2.05 vs 1xBet 1.92)."""
    oh = hint or {}
    compare = oh.get("_odds_compare") or {}
    book = str(oh.get("_niche_book") or "niche")
    book_label = {"onexbet": "1xBet"}.get(book, book.replace("_", " ").title())

    if odds_key and odds_key in compare:
        row = compare[odds_key]
        used = row.get("used")
        espn = row.get("espn")
        niche = row.get("niche")
        picked = row.get("picked") or "espn"
        if espn is not None and niche is not None:
            src = book_label if picked == "niche" else "ESPN"
            return (
                f"min:{src} (ESPN {espn:.2f} vs {book_label} {niche:.2f}"
                f"{f' → {used:.2f}' if used else ''})"
            )
        if used:
            return f"{'ESPN' if picked == 'espn' else book_label} {used:.2f}"

    if oh.get("_odds_enriched"):
        return f"ESPN+{book_label} (pior)"
    return "ESPN"