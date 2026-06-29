"""Extrai odds gratuitas da API pública ESPN (formato americano DraftKings)."""

from odds.converter import american_to_decimal


def _parse_american(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return american_to_decimal(value)
    text = str(value).strip().replace("−", "-")
    if not text or text == "EVEN":
        return 2.0 if text == "EVEN" else None
    try:
        return american_to_decimal(int(text))
    except (ValueError, TypeError):
        return None


def extract_match_odds(competition: dict) -> dict | None:
    """Converte bloco odds ESPN → dict MatchOdds-compatible."""
    odds_blocks = competition.get("odds") or []
    if not odds_blocks:
        return None

    block = odds_blocks[0]
    ml = block.get("moneyline") or {}
    total = block.get("total") or {}

    home_ml = _parse_american((ml.get("home") or {}).get("close", {}).get("odds"))
    away_ml = _parse_american((ml.get("away") or {}).get("close", {}).get("odds"))
    draw_ml = _parse_american((ml.get("draw") or {}).get("close", {}).get("odds"))

    if not all([home_ml, away_ml, draw_ml]):
        draw_ml = draw_ml or _parse_american(block.get("drawOdds", {}).get("moneyLine"))

    over_25 = _parse_american((total.get("over") or {}).get("close", {}).get("odds"))
    under_25 = _parse_american((total.get("under") or {}).get("close", {}).get("odds"))

    if not home_ml or not away_ml or not draw_ml:
        return None

    if not over_25 or not under_25:
        over_25 = over_25 or 1.90
        under_25 = under_25 or 1.90

    # BTTS não vem na ESPN — estimativa conservadora a partir do O/U
    btts_yes = round(min(2.20, max(1.55, (over_25 + under_25) / 2.05)), 2)
    btts_no = round(max(1.55, 3.6 - btts_yes), 2)

    return {
        "home_win": home_ml,
        "draw": draw_ml,
        "away_win": away_ml,
        "over_25": over_25,
        "under_25": under_25,
        "btts_yes": btts_yes,
        "btts_no": btts_no,
        "double_chance_1x": 0.0,
        "double_chance_x2": 0.0,
        "double_chance_12": 0.0,
    }