"""Conversão de odds americanas (ESPN/DraftKings) para decimais europeias."""


def american_to_decimal(american: int | float) -> float:
    a = float(american)
    if a == 0:
        raise ValueError("Odd americana 0 inválida")
    if a > 0:
        return round(1 + a / 100, 3)
    return round(1 + 100 / abs(a), 3)


def implied_prob(odd_decimal: float) -> float:
    if odd_decimal <= 0:
        return 0.0
    return 1.0 / odd_decimal