"""Contexto competitivo — o que cada equipa precisa do jogo."""

from dataclasses import dataclass, field
from enum import Enum


class StakeSituation(str, Enum):
    """Situação no campeonato/jogo."""

    NEUTRAL = "neutral"
    MUST_WIN = "must_win"
    MUST_NOT_LOSE = "must_not_lose"
    DRAW_OK = "draw_ok"
    QUALIFIED = "qualified"
    DEPENDS_OTHERS = "depends_others"
    ELIMINATED = "eliminated"
    KNOCKOUT = "knockout"


STAKE_LABELS: dict[StakeSituation, str] = {
    StakeSituation.NEUTRAL: "Jogo normal",
    StakeSituation.MUST_WIN: "Precisa de vitória",
    StakeSituation.MUST_NOT_LOSE: "Não pode perder",
    StakeSituation.DRAW_OK: "Empate chega",
    StakeSituation.QUALIFIED: "Já apurada (pode poupar)",
    StakeSituation.DEPENDS_OTHERS: "Depende de outros resultados",
    StakeSituation.ELIMINATED: "Já eliminada",
    StakeSituation.KNOCKOUT: "Eliminatória (empate → prolongamento)",
}


@dataclass
class TeamStake:
    situation: StakeSituation = StakeSituation.NEUTRAL
    points_needed: int | None = None
    group_position: int | None = None
    notes: str = ""

    @classmethod
    def from_string(cls, raw: str, notes: str = "") -> "TeamStake":
        key = raw.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "win": StakeSituation.MUST_WIN,
            "need_win": StakeSituation.MUST_WIN,
            "apurado": StakeSituation.QUALIFIED,
            "qualified": StakeSituation.QUALIFIED,
            "safe": StakeSituation.MUST_NOT_LOSE,
            "draw": StakeSituation.DRAW_OK,
            "knockout": StakeSituation.KNOCKOUT,
            "eliminatoria": StakeSituation.KNOCKOUT,
            "depends": StakeSituation.DEPENDS_OTHERS,
            "out": StakeSituation.ELIMINATED,
        }
        try:
            sit = StakeSituation(key)
        except ValueError:
            sit = aliases.get(key, StakeSituation.NEUTRAL)
        return cls(situation=sit, notes=notes)


@dataclass
class StakeAdjustment:
    team_name: str
    situation: StakeSituation
    attack_mult: float
    defense_mult: float
    urgency: float
    label: str
    formula_steps: list[str] = field(default_factory=list)


@dataclass
class MatchStakesReport:
    home: StakeAdjustment
    away: StakeAdjustment
    combined_note: str = ""