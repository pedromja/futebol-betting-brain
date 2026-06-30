"""Pilar 3 — estatísticas do árbitro."""

from __future__ import annotations

from prematch.transfermarkt.types import RefereeInsight, RefereeProfile


def compute_referee(ref: RefereeProfile | None) -> RefereeInsight | None:
    if not ref:
        return None
    cards = "high" if ref.yellow_avg >= 4.8 or ref.red_avg >= 0.15 else (
        "low" if ref.yellow_avg <= 3.5 else "medium"
    )
    penalty = "high" if ref.penalty_avg >= 0.30 else (
        "low" if ref.penalty_avg <= 0.18 else "medium"
    )
    parts = []
    if penalty == "high":
        parts.append("penáltis frequentes")
    if cards == "high":
        parts.append("cartões acima da média")
    if not parts:
        parts.append("perfil disciplinar moderado")
    label = f"{ref.name}: {', '.join(parts)} (penáltis {ref.penalty_avg:.2f}/jogo)"
    return RefereeInsight(
        referee=ref.name,
        yellow_avg=ref.yellow_avg,
        red_avg=ref.red_avg,
        penalty_avg=ref.penalty_avg,
        cards_signal=cards,
        penalty_signal=penalty,
        label=label,
    )