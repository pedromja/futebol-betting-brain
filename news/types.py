from dataclasses import dataclass, field
from enum import Enum


class NewsCategory(Enum):
    KEY_PLAYER_INJURY = "key_player_injury"
    KEY_PLAYER_SUSPENSION = "key_player_suspension"
    SQUAD_PLAYER_INJURY = "squad_player_injury"
    UNPAID_SALARIES = "unpaid_salaries"
    FAN_UNREST = "fan_unrest"
    DRESSING_ROOM_CRISIS = "dressing_room_crisis"
    MANAGER_CHANGE = "manager_change"
    POSITIVE_RETURN = "positive_return"
    GENERAL_NEGATIVE = "general_negative"
    GENERAL_POSITIVE = "general_positive"


CATEGORY_LABELS = {
    NewsCategory.KEY_PLAYER_INJURY: "Lesão jogador-chave",
    NewsCategory.KEY_PLAYER_SUSPENSION: "Castigo jogador-chave",
    NewsCategory.SQUAD_PLAYER_INJURY: "Lesão jogador do plantel",
    NewsCategory.UNPAID_SALARIES: "Salários em atraso",
    NewsCategory.FAN_UNREST: "Descontentamento dos adeptos",
    NewsCategory.DRESSING_ROOM_CRISIS: "Crise no balneário",
    NewsCategory.MANAGER_CHANGE: "Mudança de treinador",
    NewsCategory.POSITIVE_RETURN: "Regresso de jogador importante",
    NewsCategory.GENERAL_NEGATIVE: "Notícia negativa geral",
    NewsCategory.GENERAL_POSITIVE: "Notícia positiva geral",
}


@dataclass
class NewsItem:
    team: str
    category: NewsCategory
    headline: str
    summary: str
    severity: float
    credibility: float
    player_importance: float = 0.5
    days_ago: float = 1.0
    source_url: str = ""
    source_handle: str = ""
    validated: bool = False

    def __post_init__(self) -> None:
        self.severity = max(0.0, min(1.0, self.severity))
        self.credibility = max(0.0, min(1.0, self.credibility))
        self.player_importance = max(0.0, min(1.0, self.player_importance))


@dataclass
class NewsImpactDetail:
    item: NewsItem
    recency_factor: float
    raw_impact: float
    attack_delta: float
    defense_delta: float
    formula_steps: list[str] = field(default_factory=list)
    resilience_score: float = 0.0
    resilience_damping: float = 0.0
    effective_impact: float = 0.0


@dataclass
class TeamNewsReport:
    team: str
    items: list[NewsItem] = field(default_factory=list)
    source: str = "none"
    fetched_at: str = ""


@dataclass
class MatchNewsReport:
    home: TeamNewsReport
    away: TeamNewsReport
    source: str = "none"