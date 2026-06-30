"""Infere necessidades competitivas a partir do fixture (sem input manual)."""

from discovery.fixture_types import UpcomingFixture
from stakes.types import StakeSituation, TeamStake

_KNOCKOUT_HINTS = (
    "round of",
    "oitav",
    "quart",
    "semi",
    "final",
    "eliminator",
    "knockout",
    "playoff",
    "play-off",
    "last 16",
    "last 32",
)

_GROUP_HINTS = (
    "group stage",
    "fase de grupos",
    "group a",
    "group b",
    "group c",
    "group d",
    "group e",
    "group f",
    "group g",
    "group h",
)


def _context_text(league: str, stage: str = "") -> str:
    return f"{league or ''} {stage or ''}".lower()


def is_knockout_context(league: str, stage: str = "") -> bool:
    """True em fases eliminatórias — ambas as equipas pressionadas a avançar."""
    ctx = _context_text(league, stage)
    if any(hint in ctx for hint in _KNOCKOUT_HINTS):
        return True
    league_l = (league or "").lower()
    if ("champions" in league_l or "europa" in league_l) and not any(
        hint in ctx for hint in _GROUP_HINTS
    ):
        return True
    return False


def infer_match_stakes(fixture: UpcomingFixture) -> tuple[TeamStake, TeamStake]:
    """Devolve stakes casa/fora quando o contexto do jogo é reconhecível."""
    ctx = _context_text(fixture.league, fixture.stage)

    if is_knockout_context(fixture.league, fixture.stage):
        note = fixture.stage or "Eliminatória"
        stake = TeamStake(situation=StakeSituation.KNOCKOUT, notes=f"auto: {note}")
        return stake, stake

    if any(hint in ctx for hint in _GROUP_HINTS):
        stake = TeamStake(
            situation=StakeSituation.MUST_WIN,
            notes="auto: fase de grupos — vitória valorizada",
        )
        return stake, stake

    return TeamStake(), TeamStake()