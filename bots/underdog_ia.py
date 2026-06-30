"""IA — alertas underdog com raça / galinha (pré-jogo e live)."""

from __future__ import annotations

from typing import Any

UNDERDOG_IA_FIELDS = frozenset(
    {
        "underdog_ia_active",
        "underdog_ia_alert",
        "underdog_ia_play_allowed",
        "underdog_ia_favorite_hunt",
        "underdog_ia_summary",
    }
)

IA_UNDERDOG_MARKETS_RACA = (
    "BTTS Sim",
    "Over 1.5",
    "Golos Fora Over",
    "Golos Casa Over",
    "Dupla Hipótese X2",
    "Dupla Hipótese 1X",
)
IA_UNDERDOG_MARKETS_GALINHA = (
    "BTTS Não",
    "Under 2.5",
    "Under 1.5",
    "Vitória Casa",
    "Vitória Fora",
)


def compute_underdog_ia_analysis(match: dict) -> dict[str, Any]:
    """Gera alerta IA quando o perfil underdog é estatisticamente significativo."""
    scenario = str(match.get("underdog_scenario") or "")
    significant = bool(match.get("underdog_significant"))
    progress_ok = bool(match.get("underdog_progress_ok", True))
    favorite_hunt = bool(match.get("underdog_favorite_hunt"))

    if not progress_ok:
        return {
            "underdog_ia_active": False,
            "underdog_ia_alert": "blocked_progress",
            "underdog_ia_play_allowed": False,
            "underdog_ia_summary": match.get("underdog_summary")
            or "Fora da janela 25–85% da época.",
        }

    active = scenario in ("raca", "galinha", "raca_trend", "galinha_trend")
    if not active:
        return {"underdog_ia_active": False}

    play_allowed = significant and scenario in ("raca", "galinha")
    if scenario in ("raca", "raca_trend"):
        alert = "easy_score"
        mkts = IA_UNDERDOG_MARKETS_RACA
    else:
        alert = "hard_score"
        mkts = IA_UNDERDOG_MARKETS_GALINHA

    team = match.get("underdog_team") or "?"
    extra = ""
    if favorite_hunt and play_allowed:
        extra = " Caça favoritos — diferença estatisticamente significativa."

    summary = str(match.get("underdog_summary") or "")
    if play_allowed:
        summary += f" IA: mercados alinhados — {', '.join(mkts[:3])}.{extra}"
    elif significant is False:
        summary += " IA: aguardar mais jogos para confirmar padrão."

    return {
        "underdog_ia_active": True,
        "underdog_ia_alert": alert,
        "underdog_ia_play_allowed": play_allowed,
        "underdog_ia_favorite_hunt": favorite_hunt and play_allowed,
        "underdog_ia_markets": list(mkts),
        "underdog_ia_summary": summary.strip(),
    }


def attach_underdog_ia_fields(match: dict, *, football_data_key: str | None = None) -> dict:
    out = {**match}
    if out.get("underdog_scenario") in (None, "none", "insufficient") and not out.get(
        "underdog_team"
    ):
        from bots.underdog_table import attach_underdog_fields

        out = attach_underdog_fields(out, football_data_key=football_data_key)
    out.update(compute_underdog_ia_analysis(out))
    return out