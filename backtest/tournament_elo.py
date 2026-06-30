"""Elo internacional → odds sintéticas de mercado (proxy independente do Poisson)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from models.team_stats import MatchOdds

DEFAULT_ELO = 1500.0
HOME_ADV_ELO = 35.0
DRAW_BASE = 0.26


@dataclass
class EloState:
    ratings: dict[str, float] = field(default_factory=dict)
    played: dict[str, int] = field(default_factory=dict)

    def rating(self, team: str) -> float:
        return self.ratings.get(team, DEFAULT_ELO)

    def games(self, team: str) -> int:
        return self.played.get(team, 0)

    def expected_score(self, home: str, away: str, *, neutral: bool) -> float:
        ra = self.rating(home) + (0.0 if neutral else HOME_ADV_ELO)
        rb = self.rating(away)
        return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))

    def update(self, home: str, away: str, hg: int, ag: int, *, neutral: bool, k: float = 28.0) -> None:
        exp = self.expected_score(home, away, neutral=neutral)
        actual = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        delta = k * (actual - exp)
        self.ratings[home] = self.rating(home) + delta
        self.ratings[away] = self.rating(away) - delta
        self.played[home] = self.games(home) + 1
        self.played[away] = self.games(away) + 1


def _clamp_odd(v: float, lo: float = 1.08, hi: float = 29.0) -> float:
    return round(max(lo, min(hi, v)), 2)


def elo_to_match_odds(
    state: EloState,
    home: str,
    away: str,
    *,
    neutral: bool,
    goals_avg: float = 2.55,
) -> MatchOdds:
    """Converte Elo em odds 1X2/O/U/BTTS com margem de mercado (~5%)."""
    exp_home = state.expected_score(home, away, neutral=neutral)
    elo_gap = abs(state.rating(home) - state.rating(away))
    draw_p = max(0.14, min(0.34, DRAW_BASE - elo_gap / 2500.0))
    rem = max(0.05, 1.0 - draw_p)
    p_home = exp_home * rem
    p_away = (1.0 - exp_home) * rem
    vig = 1.05

    home_odd = _clamp_odd(vig / max(p_home, 0.04))
    draw_odd = _clamp_odd(vig / max(draw_p, 0.04))
    away_odd = _clamp_odd(vig / max(p_away, 0.04))

    # Over 2.5 — proxy por soma de "força" ofensiva implícita no Elo
    attack_sum = (state.rating(home) + state.rating(away) - 2 * DEFAULT_ELO) / 400.0
    over_p = max(0.32, min(0.72, (goals_avg / 3.4) + attack_sum * 0.04))
    over_odd = _clamp_odd(vig / over_p)
    under_odd = _clamp_odd(vig / max(0.08, 1.0 - over_p))
    btts_p = max(0.38, min(0.68, 0.50 + attack_sum * 0.03))
    btts_yes = _clamp_odd(vig / btts_p)
    btts_no = _clamp_odd(vig / (1.0 - btts_p))

    dc_1x = _clamp_odd(1.0 / max(0.05, p_home + draw_p) * vig)
    dc_x2 = _clamp_odd(1.0 / max(0.05, p_away + draw_p) * vig)
    dc_12 = _clamp_odd(1.0 / max(0.05, p_home + p_away) * vig)

    return MatchOdds(
        home_win=home_odd,
        draw=draw_odd,
        away_win=away_odd,
        over_25=over_odd,
        under_25=under_odd,
        btts_yes=btts_yes,
        btts_no=btts_no,
        double_chance_1x=dc_1x,
        double_chance_x2=dc_x2,
        double_chance_12=dc_12,
    )


def edition_team_form(
    *,
    team: str,
    goals_for: list[float],
    goals_against: list[float],
) -> tuple[float, float, int, int, int, int]:
    n = len(goals_for)
    if n == 0:
        return 1.2, 1.2, 0, 0, 0, 1
    gf = sum(goals_for) / n
    ga = sum(goals_against) / n
    scored = sum(1 for g in goals_for if g > 0)
    conceded = sum(1 for g in goals_against if g > 0)
    return gf, ga, n, scored, conceded, max(n, 1)