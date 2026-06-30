"""Catálogo de condições — categorias alinhadas aos dados reais do motor."""

from __future__ import annotations

CONDITION_CATEGORIES: list[dict] = [
    {
        "id": "mercado",
        "label": "Mercado",
        "description": "Mercado recomendado pelo motor",
        "fields": [
            {
                "id": "best_market",
                "label": "Mercado",
                "type": "market",
                "operators": ["eq", "in_list"],
            }
        ],
    },
    {
        "id": "ev",
        "label": "EV / Valor",
        "description": "Expected value da pick",
        "fields": [
            {
                "id": "best_ev_pct",
                "label": "EV %",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "%",
            }
        ],
    },
    {
        "id": "score",
        "label": "Score",
        "description": "Confiança do modelo",
        "fields": [
            {
                "id": "best_score",
                "label": "Score total",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "should_bet",
                "label": "Dica recomendada",
                "type": "boolean",
                "operators": ["eq"],
            },
        ],
    },
    {
        "id": "liga",
        "label": "Competição",
        "description": "Filtrar por liga ou fase",
        "fields": [
            {
                "id": "league",
                "label": "Liga",
                "type": "text",
                "operators": ["contains", "eq"],
            },
            {
                "id": "stage",
                "label": "Fase",
                "type": "text",
                "operators": ["contains"],
            },
        ],
    },
    {
        "id": "motivacao",
        "label": "Motivação",
        "description": "Motivation Gate",
        "fields": [
            {
                "id": "motivation_score",
                "label": "Score motivação",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "motivation_alignment",
                "label": "Alinhamento",
                "type": "enum",
                "operators": ["eq"],
                "options": ["strong", "neutral", "weak", "veto"],
            },
        ],
    },
    {
        "id": "transfermarkt",
        "label": "Transfermarkt",
        "description": "Inteligência de plantel",
        "fields": [
            {
                "id": "tm_alignment",
                "label": "Alinhamento TM",
                "type": "enum",
                "operators": ["eq"],
                "options": ["strong", "neutral", "weak"],
            },
            {
                "id": "tm_available",
                "label": "Dados disponíveis",
                "type": "boolean",
                "operators": ["eq"],
            },
        ],
    },
    {
        "id": "timing",
        "label": "Timing pré-jogo",
        "description": "Janela antes do kickoff",
        "modes": ["prematch"],
        "fields": [
            {
                "id": "minutes_to_kickoff",
                "label": "Minutos até ao jogo",
                "type": "number",
                "operators": ["lte", "gte"],
                "unit": "min",
            },
        ],
    },
    {
        "id": "live",
        "label": "Ao vivo",
        "description": "Estado do jogo in-play",
        "modes": ["live"],
        "fields": [
            {
                "id": "minute",
                "label": "Minuto",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "total_goals",
                "label": "Golos totais",
                "type": "number",
                "operators": ["gte", "lte"],
            },
        ],
    },
    {
        "id": "xg_live",
        "label": "Performance xG",
        "description": "Expected goals ao vivo (API ou estimativa)",
        "modes": ["live"],
        "fields": [
            {
                "id": "home_xg",
                "label": "xG casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_xg",
                "label": "xG fora",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "total_xg",
                "label": "xG total",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "xg_diff",
                "label": "Δ xG (casa − fora)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_possession_pct",
                "label": "Posse casa %",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "%",
            },
        ],
    },
    {
        "id": "cartoes",
        "label": "Cartões",
        "description": "Amarelos e vermelhos ao vivo",
        "modes": ["live"],
        "fields": [
            {
                "id": "total_yellow_cards",
                "label": "Amarelos (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "total_red_cards",
                "label": "Vermelhos (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "total_cards",
                "label": "Cartões (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_yellow_cards",
                "label": "Amarelos casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_yellow_cards",
                "label": "Amarelos fora",
                "type": "number",
                "operators": ["gte", "lte"],
            },
        ],
    },
    {
        "id": "clima",
        "label": "Clima",
        "description": "Condições meteorológicas",
        "fields": [
            {
                "id": "temperature_c",
                "label": "Temperatura",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "°C",
            },
            {
                "id": "precipitation_mm",
                "label": "Chuva",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "mm",
            },
        ],
    },
]

MARKET_OPTIONS = [
    "Vitória Casa",
    "Empate",
    "Vitória Fora",
    "Over 2.5",
    "Under 2.5",
    "BTTS Sim",
    "BTTS Não",
    "Dupla Hipótese 1X",
    "Dupla Hipótese X2",
    "Dupla Hipótese 12",
]

BOT_TEMPLATES: list[dict] = [
    {
        "id": "prematch_over",
        "name": "Over 2.5 pré-jogo",
        "description": "Jogos abertos com EV positivo",
        "mode": "prematch",
        "markets": ["Over 2.5"],
        "min_score": 0.58,
        "min_ev_pct": 5,
        "minutes_before": 120,
        "conditions": [
            {"category": "score", "field": "should_bet", "operator": "eq", "value": True, "label": "Dica recomendada"},
        ],
    },
    {
        "id": "prematch_btts",
        "name": "BTTS pré-jogo",
        "description": "Ambas marcam com motivação forte",
        "mode": "prematch",
        "markets": ["BTTS Sim"],
        "min_ev_pct": 4,
        "conditions": [
            {"category": "motivacao", "field": "motivation_score", "operator": "gte", "value": 2, "label": "Motivação ≥ 2"},
        ],
    },
    {
        "id": "live_value",
        "name": "Valor ao vivo",
        "description": "Oportunidades in-play após min 20",
        "mode": "live",
        "min_ev_pct": 6,
        "conditions": [
            {"category": "live", "field": "minute", "operator": "gte", "value": 20, "label": "Minuto ≥ 20"},
            {"category": "score", "field": "should_bet", "operator": "eq", "value": True, "label": "Dica recomendada"},
        ],
    },
    {
        "id": "live_xg_press",
        "name": "Pressão xG live",
        "description": "Casa a dominar xG após min 25",
        "mode": "live",
        "min_ev_pct": 5,
        "conditions": [
            {"category": "live", "field": "minute", "operator": "gte", "value": 25, "label": "Minuto ≥ 25"},
            {"category": "xg_live", "field": "xg_diff", "operator": "gte", "value": 0.4, "label": "Δ xG ≥ 0.4"},
            {"category": "xg_live", "field": "home_possession_pct", "operator": "gte", "value": 52, "label": "Posse casa ≥ 52%"},
        ],
    },
    {
        "id": "live_cards",
        "name": "Jogo intenso (cartões)",
        "description": "Muitos cartões — mercados de cartões/over",
        "mode": "live",
        "markets": ["Over 2.5"],
        "conditions": [
            {"category": "live", "field": "minute", "operator": "gte", "value": 30, "label": "Minuto ≥ 30"},
            {"category": "cartoes", "field": "total_yellow_cards", "operator": "gte", "value": 3, "label": "Amarelos ≥ 3"},
        ],
    },
]


def catalog_payload() -> dict:
    return {
        "categories": CONDITION_CATEGORIES,
        "markets": MARKET_OPTIONS,
        "templates": BOT_TEMPLATES,
        "operators": {
            "eq": "é",
            "neq": "não é",
            "gte": "≥",
            "lte": "≤",
            "contains": "contém",
            "in_list": "está em",
        },
    }