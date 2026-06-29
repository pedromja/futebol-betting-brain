"""Regras de omissão de dicas ao vivo."""

from live.types import LiveMatchState, MatchPeriod

_FIRST_HALF_ENTRY_CUTOFF = 40
_REGULATION_END_BUFFER = 5


def is_first_half_entry_context(state: LiveMatchState) -> bool:
    """Dica de entrada no 1.º tempo — jogo ainda no primeiro período."""
    return state.period == MatchPeriod.FIRST_HALF or state.minute < 45


def regulation_minutes_remaining(state: LiveMatchState) -> float:
    if state.period == MatchPeriod.FIRST_HALF:
        return max(0.0, (45 - state.minute) + 45)
    if state.period == MatchPeriod.SECOND_HALF:
        return max(0.0, state.regulation_minutes - state.minute)
    return 0.0


def live_tip_omit_reason(state: LiveMatchState) -> tuple[bool, str]:
    """
    Omitir dica e não contabilizar quando:
    - 1.º tempo e minuto ≥ 40 (entrada 1T já inviável)
    - 2.º tempo e faltam < 5 min de tempo regulamentar
    """
    if is_first_half_entry_context(state) and state.minute >= _FIRST_HALF_ENTRY_CUTOFF:
        return (
            True,
            f"1.º tempo: minuto {state.minute}' (≥{_FIRST_HALF_ENTRY_CUTOFF}') — dica omitida",
        )

    if state.period == MatchPeriod.SECOND_HALF:
        remaining = regulation_minutes_remaining(state)
        if remaining < _REGULATION_END_BUFFER:
            return (
                True,
                f"Fim do jogo: faltam {remaining:.0f} min regulamentares — dica omitida",
            )

    if state.period == MatchPeriod.EXTRA_TIME:
        return True, "Prolongamento — dica de tempo regulamentar omitida"

    return False, ""