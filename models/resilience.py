"""
Resiliência equilibrada por tipo de choque.

Auditoria (PSG vs Nice — lesão de estrela):
  - O modelo antigo usava um único G (grandiosidade) onde estádio/adeptos
    pesavam 15% — irrelevante para substituir um Mbappé.
  - PSG e Nice podiam ficar demasiado próximos se só olhássemos ao tier.
  - Crises de balneário/salários NÃO devem ser fortemente amortecidas
    só porque a equipa é grande.

Solução: três eixos independentes + pesos por categoria de notícia.

Eixos ∈ [0, 1]:
  D = profundidade de plantel (valor do banco, qualidade do 2.º onda)
  I = institucional (tier, UEFA, títulos 10 anos)
  F = financeiro (orçamento relativo à liga)

Resiliência base por categoria c:
  S_c = w_D×D + w_I×I + w_F×F        (pesos somam 1, variam por categoria)
  R_c = clamp(0.22 + 0.58 × S_c, 0.22, 0.78)

Amortecimento do impacto bruto I:
  I_efetivo = I_bruto × (1 − α_c × R_c)

  α_c = intensidade do amortecimento por tipo de notícia [0, 1]
  Lesão de estrela: α alto, eixo D domina (55%)
  Crise no balneário: α baixo — equipas grandes também sofrem
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

_DATA = Path(__file__).parent.parent / "data" / "team_grandiosity.json"

TIER_SCORES = {"S": 0.95, "A": 0.72, "B": 0.52, "C": 0.32, "D": 0.18}

# Pesos dos eixos por categoria (D, I, F) — somam 1.0
CATEGORY_AXIS_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "key_player_injury": (0.55, 0.25, 0.20),
    "key_player_suspension": (0.55, 0.25, 0.20),
    "squad_player_injury": (0.50, 0.30, 0.20),
    "positive_return": (0.50, 0.30, 0.20),
    "manager_change": (0.25, 0.50, 0.25),
    "fan_unrest": (0.20, 0.45, 0.35),
    "dressing_room_crisis": (0.15, 0.45, 0.40),
    "unpaid_salaries": (0.10, 0.40, 0.50),
    "general_negative": (0.35, 0.40, 0.25),
    "general_positive": (0.35, 0.40, 0.25),
}

# α_c — quanto da resiliência se aplica (0 = ignora, 1 = aplica total)
CATEGORY_DAMPING: dict[str, float] = {
    "key_player_injury": 1.00,
    "key_player_suspension": 1.00,
    "squad_player_injury": 0.75,
    "positive_return": 0.85,
    "manager_change": 0.45,
    "fan_unrest": 0.50,
    "dressing_room_crisis": 0.30,
    "unpaid_salaries": 0.25,
    "general_negative": 0.55,
    "general_positive": 0.55,
}


def _category_key(category: Any) -> str:
    return category.value if hasattr(category, "value") else str(category)

R_MIN, R_MAX = 0.22, 0.78
R_BASE, R_SCALE = 0.22, 0.58

DEFAULT_SQUAD_DEPTH = 0.45
DEFAULT_INSTITUTIONAL = 0.45
DEFAULT_FINANCIAL = 0.45


@dataclass
class TeamResilienceProfile:
    name: str
    tier: str
    squad_depth: float
    institutional: float
    financial: float
    grandiosity_score: float
    market_value_m: float = 0.0
    titles_10y: int = 0


@dataclass
class ResilienceResult:
    profile: TeamResilienceProfile | None
    category: str
    axis_score: float
    resilience: float
    damping_alpha: float
    dampen_factor: float
    raw_impact: float
    effective_impact: float


def _load_data() -> dict:
    if not _DATA.exists():
        return {}
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f)


def _find_entry(team_name: str, data: dict) -> tuple[str, dict] | None:
    if team_name in data:
        return team_name, data[team_name]
    lower = team_name.lower()
    for key, val in data.items():
        if key.startswith("_"):
            continue
        kl = key.lower()
        if lower in kl or kl in lower:
            return key, val
    aliases = {
        "psg": "Paris Saint-Germain",
        "paris sg": "Paris Saint-Germain",
        "olympique nice": "Nice",
        "ogc nice": "Nice",
    }
    alias_key = aliases.get(lower)
    if alias_key and alias_key in data:
        return alias_key, data[alias_key]
    return None


def _derive_axes(entry: dict) -> tuple[float, float, float]:
    if "squad_depth" in entry:
        d = float(entry["squad_depth"])
        i = float(entry.get("institutional", entry.get("grandiosity_score", 0.5)))
        f = float(entry.get("financial", entry.get("grandiosity_score", 0.5)))
        return d, i, f

    g = float(entry.get("grandiosity_score", 0.5))
    tier = entry.get("tier", "B")
    tier_s = TIER_SCORES.get(tier, 0.52)
    return (
        max(0.0, min(1.0, 0.55 * g + 0.45 * tier_s)),
        max(0.0, min(1.0, 0.60 * g + 0.40 * tier_s)),
        max(0.0, min(1.0, 0.50 * g + 0.50 * tier_s)),
    )


def get_team_profile(team_name: str) -> TeamResilienceProfile:
    data = _load_data()
    found = _find_entry(team_name, data)
    if not found:
        return TeamResilienceProfile(
            name=team_name,
            tier="B",
            squad_depth=DEFAULT_SQUAD_DEPTH,
            institutional=DEFAULT_INSTITUTIONAL,
            financial=DEFAULT_FINANCIAL,
            grandiosity_score=0.45,
        )

    _, entry = found
    d, i, f = _derive_axes(entry)
    return TeamResilienceProfile(
        name=team_name,
        tier=entry.get("tier", "B"),
        squad_depth=d,
        institutional=i,
        financial=f,
        grandiosity_score=float(entry.get("grandiosity_score", (d + i + f) / 3)),
        market_value_m=float(entry.get("market_value_m", 0)),
        titles_10y=int(entry.get("titles_10y", 0)),
    )


def compute_axis_score(profile: TeamResilienceProfile, category: Any) -> float:
    w_d, w_i, w_f = CATEGORY_AXIS_WEIGHTS.get(
        _category_key(category), (0.35, 0.40, 0.25)
    )
    return (
        w_d * profile.squad_depth
        + w_i * profile.institutional
        + w_f * profile.financial
    )


def compute_resilience(axis_score: float) -> float:
    s = max(0.0, min(1.0, axis_score))
    return max(R_MIN, min(R_MAX, R_BASE + R_SCALE * s))


def dampen_news_impact(
    raw_impact: float,
    team_name: str,
    category: Any,
) -> ResilienceResult:
    cat_key = _category_key(category)
    profile = get_team_profile(team_name)
    axis_score = compute_axis_score(profile, cat_key)
    resilience = compute_resilience(axis_score)
    alpha = CATEGORY_DAMPING.get(cat_key, 0.55)
    dampen_factor = max(0.15, 1.0 - alpha * resilience)
    effective = raw_impact * dampen_factor

    return ResilienceResult(
        profile=profile,
        category=cat_key,
        axis_score=axis_score,
        resilience=resilience,
        damping_alpha=alpha,
        dampen_factor=dampen_factor,
        raw_impact=raw_impact,
        effective_impact=effective,
    )


def dampen_environment_delta(
    raw_delta: float, team_name: str, factor: float = 0.40
) -> tuple[float, float]:
    """Amortecimento leve para meteo/viagem/altitude."""
    profile = get_team_profile(team_name)
    axis_score = (
        0.30 * profile.squad_depth
        + 0.45 * profile.institutional
        + 0.25 * profile.financial
    )
    resilience = compute_resilience(axis_score)
    dampen = 1.0 - factor * resilience
    return raw_delta * dampen, resilience