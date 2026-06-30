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
        "id": "favorito",
        "label": "Favorito",
        "description": "Favorito pré-jogo (odds ESPN/API) vs resultado live",
        "modes": ["live"],
        "fields": [
            {
                "id": "favorite_status",
                "label": "Estado do favorito",
                "type": "enum",
                "operators": ["eq", "in_list"],
                "options": ["winning", "drawing", "losing", "unknown"],
            },
            {
                "id": "favorite_losing_or_drawing",
                "label": "Favorito a perder ou empatar",
                "type": "boolean",
                "operators": ["eq"],
            },
            {
                "id": "favorite_side",
                "label": "Lado favorito",
                "type": "enum",
                "operators": ["eq"],
                "options": ["home", "away", "none"],
            },
            {
                "id": "favorite_goal_diff",
                "label": "Diferença de golos (favorito)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_is_favorite",
                "label": "Casa é favorita",
                "type": "boolean",
                "operators": ["eq"],
            },
        ],
    },
    {
        "id": "cantos",
        "label": "Cantos",
        "description": "Cantos ao vivo (API-Football ou ESPN)",
        "modes": ["live"],
        "fields": [
            {
                "id": "total_corners",
                "label": "Cantos (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_corners",
                "label": "Cantos casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_corners",
                "label": "Cantos fora",
                "type": "number",
                "operators": ["gte", "lte"],
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
            {
                "id": "away_possession_pct",
                "label": "Posse fora %",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "%",
            },
        ],
    },
    {
        "id": "remates",
        "label": "Remates",
        "description": "Remates ao vivo (ESPN ou API-Football)",
        "modes": ["live"],
        "fields": [
            {
                "id": "total_shots",
                "label": "Remates (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "total_shots_on",
                "label": "Remates à baliza (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_shots_on",
                "label": "Remates à baliza casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_shots_on",
                "label": "Remates à baliza fora",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_shots_total",
                "label": "Remates casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_shots_total",
                "label": "Remates fora",
                "type": "number",
                "operators": ["gte", "lte"],
            },
        ],
    },
    {
        "id": "faltas",
        "label": "Faltas",
        "description": "Faltas cometidas ao vivo",
        "modes": ["live"],
        "fields": [
            {
                "id": "total_fouls",
                "label": "Faltas (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_fouls",
                "label": "Faltas casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_fouls",
                "label": "Faltas fora",
                "type": "number",
                "operators": ["gte", "lte"],
            },
        ],
    },
    {
        "id": "passes",
        "label": "Passes",
        "description": "Precisão de passe ao vivo",
        "modes": ["live"],
        "fields": [
            {
                "id": "home_passes_pct",
                "label": "Passe casa %",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "%",
            },
            {
                "id": "away_passes_pct",
                "label": "Passe fora %",
                "type": "number",
                "operators": ["gte", "lte"],
                "unit": "%",
            },
        ],
    },
    {
        "id": "defesa",
        "label": "Defesa",
        "description": "Defesas do guarda-redes ao vivo",
        "modes": ["live"],
        "fields": [
            {
                "id": "total_saves",
                "label": "Defesas (total)",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "home_saves",
                "label": "Defesas casa",
                "type": "number",
                "operators": ["gte", "lte"],
            },
            {
                "id": "away_saves",
                "label": "Defesas fora",
                "type": "number",
                "operators": ["gte", "lte"],
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
    "DNB Casa",
    "DNB Fora",
    "Cantos Over",
    "Cantos Under",
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
    {
        "id": "live_favorite_trouble",
        "name": "Favorito em apuros",
        "description": "Favorito pré-jogo a perder OU empatar (odds ESPN)",
        "mode": "live",
        "condition_groups": [
            {
                "label": "Favorito em apuros",
                "logic": "or",
                "conditions": [
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "losing", "label": "Favorito a perder"},
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "drawing", "label": "Favorito a empatar"},
                ],
            },
            {
                "label": "Jogo iniciado",
                "logic": "and",
                "conditions": [
                    {"category": "live", "field": "minute", "operator": "gte", "value": 15, "label": "Minuto ≥ 15"},
                ],
            },
        ],
        "groups_logic": "and",
    },
    {
        "id": "live_favorite_drawing",
        "name": "Favorito só empata",
        "description": "Favorito não ganha — útil para lay/empate",
        "mode": "live",
        "conditions": [
            {"category": "favorito", "field": "favorite_losing_or_drawing", "operator": "eq", "value": True, "label": "Favorito ≤ empate"},
            {"category": "live", "field": "minute", "operator": "gte", "value": 20, "label": "Minuto ≥ 20"},
        ],
    },
    {
        "id": "live_corners_press",
        "name": "Cantos live (ESPN/API)",
        "description": "Jogo com muitos cantos — mercado cantos/over",
        "mode": "live",
        "markets": ["Cantos Over", "Over 2.5"],
        "conditions": [
            {"category": "live", "field": "minute", "operator": "gte", "value": 25, "label": "Minuto ≥ 25"},
            {"category": "cantos", "field": "total_corners", "operator": "gte", "value": 5, "label": "Cantos ≥ 5"},
        ],
    },
    {
        "id": "live_favorite_corners",
        "name": "Favorito pressiona (cantos)",
        "description": "Favorito em apuros com volume de cantos",
        "mode": "live",
        "markets": ["Cantos Over"],
        "condition_groups": [
            {
                "label": "Favorito ≤ empate",
                "logic": "or",
                "conditions": [
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "losing", "label": "A perder"},
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "drawing", "label": "A empatar"},
                ],
            },
            {
                "label": "Volume de cantos",
                "logic": "and",
                "conditions": [
                    {"category": "cantos", "field": "total_corners", "operator": "gte", "value": 4, "label": "Cantos ≥ 4"},
                    {"category": "live", "field": "minute", "operator": "gte", "value": 20, "label": "Minuto ≥ 20"},
                ],
            },
        ],
        "groups_logic": "and",
    },
    {
        "id": "live_espn_shots_press",
        "name": "Pressão remates (ESPN)",
        "description": "Favorito em apuros com mais remates à baliza",
        "mode": "live",
        "markets": ["Over 2.5", "Cantos Over"],
        "condition_groups": [
            {
                "label": "Favorito ≤ empate",
                "logic": "or",
                "conditions": [
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "losing", "label": "A perder"},
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "drawing", "label": "A empatar"},
                ],
            },
            {
                "label": "Volume de remates",
                "logic": "and",
                "conditions": [
                    {"category": "live", "field": "minute", "operator": "gte", "value": 25, "label": "Minuto ≥ 25"},
                    {"category": "remates", "field": "total_shots_on", "operator": "gte", "value": 4, "label": "À baliza ≥ 4"},
                ],
            },
        ],
        "groups_logic": "and",
    },
    {
        "id": "live_espn_fouls",
        "name": "Jogo físico (faltas ESPN)",
        "description": "Muitas faltas — over/cartões",
        "mode": "live",
        "markets": ["Over 2.5"],
        "conditions": [
            {"category": "live", "field": "minute", "operator": "gte", "value": 30, "label": "Minuto ≥ 30"},
            {"category": "faltas", "field": "total_fouls", "operator": "gte", "value": 20, "label": "Faltas ≥ 20"},
        ],
    },
    {
        "id": "live_espn_dominance",
        "name": "Domínio posse+remates",
        "description": "Equipa visitante a dominar posse e remates (ESPN)",
        "mode": "live",
        "conditions": [
            {"category": "live", "field": "minute", "operator": "gte", "value": 30, "label": "Minuto ≥ 30"},
            {"category": "xg_live", "field": "away_possession_pct", "operator": "gte", "value": 60, "label": "Posse fora ≥ 60%"},
            {"category": "remates", "field": "away_shots_on", "operator": "gte", "value": 3, "label": "À baliza fora ≥ 3"},
        ],
    },
    {
        "id": "live_espn_xg_underdog",
        "name": "Underdog com xG (ESPN)",
        "description": "Favorito atrás mas adversário com menos xG — possível reação",
        "mode": "live",
        "condition_groups": [
            {
                "label": "Favorito em apuros",
                "logic": "or",
                "conditions": [
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "losing", "label": "A perder"},
                    {"category": "favorito", "field": "favorite_status", "operator": "eq", "value": "drawing", "label": "A empatar"},
                ],
            },
            {
                "label": "xG favorito superior",
                "logic": "and",
                "conditions": [
                    {"category": "live", "field": "minute", "operator": "gte", "value": 35, "label": "Minuto ≥ 35"},
                    {"category": "xg_live", "field": "xg_diff", "operator": "gte", "value": 0.3, "label": "Δ xG ≥ 0.3"},
                ],
            },
        ],
        "groups_logic": "and",
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
        "logic_options": {
            "conditions_logic": {
                "and": "Todas (AND)",
                "or": "Qualquer (OR)",
            },
            "groups_logic": {
                "and": "Todos os grupos (AND)",
                "or": "Qualquer grupo (OR)",
            },
            "group_logic": {
                "and": "Todas no grupo (AND)",
                "or": "Qualquer no grupo (OR)",
            },
        },
    }