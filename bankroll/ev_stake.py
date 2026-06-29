"""Gestão de stake por EV — escala 1 a 10."""

from dataclasses import dataclass

_EV_THRESHOLDS_PCT = (3, 5, 7, 9, 11, 13, 15, 17, 19)
_BANKROLL_PCTS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
_LABELS = (
    "Mínima",
    "Muito baixa",
    "Baixa",
    "Moderada−",
    "Moderada",
    "Moderada+",
    "Alta−",
    "Alta",
    "Muito alta",
    "Máxima",
)


@dataclass
class EvStakePlan:
    level: int
    label: str
    bankroll_pct: float
    suggested_amount: float | None
    ev_pct: float

    @property
    def display(self) -> str:
        base = f"Stake {self.level}/10 ({self.label}) · {self.bankroll_pct:.1f}% banca"
        if self.suggested_amount is not None:
            return f"{base} · €{self.suggested_amount:.2f}"
        return base


def ev_to_stake_level(ev: float) -> int:
    """Converte EV decimal (ex: 0.12) em nível 1–10."""
    pct = ev * 100
    if pct < _EV_THRESHOLDS_PCT[0]:
        return 1
    for i, threshold in enumerate(_EV_THRESHOLDS_PCT[1:], start=2):
        if pct < threshold:
            return i
    return 10


def suggest_stake(ev: float, bankroll: float | None = None) -> EvStakePlan:
    level = ev_to_stake_level(ev)
    pct = _BANKROLL_PCTS[level - 1]
    amount = round(bankroll * pct / 100, 2) if bankroll and bankroll > 0 else None
    return EvStakePlan(
        level=level,
        label=_LABELS[level - 1],
        bankroll_pct=pct,
        suggested_amount=amount,
        ev_pct=round(ev * 100, 1),
    )