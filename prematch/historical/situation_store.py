"""Cache JSONL — perfis condicionais por situação e janela de minutos."""

from __future__ import annotations

import json

from config.data_paths import HISTORICAL_SITUATION_PROFILES, ensure_data_dir
from prematch.historical.situation_aggregate import POST_HT_WINDOWS, WINDOW_MINUTES
from prematch.historical.sources import league_to_code
from prematch.historical.types import SituationWindowMetrics, TeamSituationProfile
from prematch.transfermarkt.match_names import find_in_index, team_key

_MIN_SAMPLE = 3


def _read_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def _profile_key(team: str, venue: str, situation: str, window: str) -> str:
    return f"{team}|{venue}|{situation}|{window}"


def live_situation_key(live_situation: str, *, fav_losing_at_ht: bool) -> str:
    """Mapeia situação live do motor IA → chave histórica."""
    if live_situation in ("fav_losing_post_ht", "fav_losing_ht", "fav_losing"):
        return "fav_losing_at_ht" if fav_losing_at_ht or live_situation != "fav_losing" else "losing_at_ht"
    if live_situation == "fav_drawing":
        return "fav_drawing_at_ht"
    if live_situation == "fav_winning":
        return "fav_winning_at_ht"
    return "drawing_at_ht"


def resolve_live_window(minute: int, *, post_ht: bool) -> str:
    if not post_ht or minute <= 45:
        return "first_half"
    for window_id, start, end in POST_HT_WINDOWS:
        if start <= minute <= end:
            return window_id
    if minute > 90:
        return "post_ht_31_45"
    return "post_ht_31_45"


def cumulative_expected(
    profiles: dict[str, TeamSituationProfile],
    *,
    minute: int,
    post_ht: bool,
) -> tuple[SituationWindowMetrics, str, int]:
    """profiles: window_id → TeamSituationProfile."""
    """Soma janelas completas + fracção da janela actual (cantos/golos esperados acumulados)."""
    if not profiles:
        return SituationWindowMetrics(), "first_half", 0

    if not post_ht or minute <= 45:
        window = "first_half"
        prof = profiles.get("first_half")
        if not prof or prof.metrics.matches < _MIN_SAMPLE:
            return SituationWindowMetrics(), window, 0
        frac = min(minute / 45.0, 1.0)
        m = prof.metrics
        return (
            SituationWindowMetrics(
                matches=m.matches,
                corners_avg=m.corners_avg * frac,
                goals_scored_avg=m.goals_scored_avg * frac,
                goals_conceded_avg=m.goals_conceded_avg * frac,
                shots_avg=m.shots_avg * frac,
                sot_avg=m.sot_avg * frac,
                fouls_avg=m.fouls_avg * frac,
            ),
            window,
            m.matches,
        )

    total = SituationWindowMetrics()
    sample = 0
    current_window = "post_ht_0_15"

    for window_id, start, end in POST_HT_WINDOWS:
        prof = profiles.get(window_id)
        if not prof or prof.metrics.matches < 1:
            continue
        sample = max(sample, prof.metrics.matches)
        current_window = window_id
        if minute > end:
            total.corners_avg += prof.metrics.corners_avg
            total.goals_scored_avg += prof.metrics.goals_scored_avg
            total.goals_conceded_avg += prof.metrics.goals_conceded_avg
            total.shots_avg += prof.metrics.shots_avg
            total.sot_avg += prof.metrics.sot_avg
            total.fouls_avg += prof.metrics.fouls_avg
        elif minute >= start:
            span = max(1, end - start + 1)
            elapsed = minute - start + 1
            frac = min(elapsed / span, 1.0)
            total.corners_avg += prof.metrics.corners_avg * frac
            total.goals_scored_avg += prof.metrics.goals_scored_avg * frac
            total.goals_conceded_avg += prof.metrics.goals_conceded_avg * frac
            total.shots_avg += prof.metrics.shots_avg * frac
            total.sot_avg += prof.metrics.sot_avg * frac
            total.fouls_avg += prof.metrics.fouls_avg * frac
            break

    total.matches = sample
    return total, current_window, sample


class SituationStore:
    def __init__(self) -> None:
        self._index: dict[str, TeamSituationProfile] = {}
        self.reload()

    def reload(self) -> None:
        self._index = {}
        for row in _read_jsonl(HISTORICAL_SITUATION_PROFILES):
            profile = TeamSituationProfile.from_dict(row)
            if profile.team:
                key = _profile_key(
                    profile.team, profile.venue, profile.situation, profile.window
                )
                self._index[key] = profile

    def upsert_many(self, profiles: list[TeamSituationProfile]) -> int:
        ensure_data_dir()
        rows = _read_jsonl(HISTORICAL_SITUATION_PROFILES)
        by_key = {
            _profile_key(
                str(r.get("team")),
                str(r.get("venue")),
                str(r.get("situation")),
                str(r.get("window")),
            ): r
            for r in rows
        }
        for p in profiles:
            by_key[_profile_key(p.team, p.venue, p.situation, p.window)] = p.to_dict()
        _write_jsonl(HISTORICAL_SITUATION_PROFILES, list(by_key.values()))
        self.reload()
        return len(profiles)

    def profiles_for(
        self,
        team_name: str,
        *,
        league: str,
        venue: str,
        situation: str,
    ) -> dict[str, TeamSituationProfile]:
        teams = {prof.team for prof in self._index.values()}
        hit = find_in_index(team_name, {t: t for t in teams})
        resolved = hit[0] if hit else team_name
        code = league_to_code(league)

        out: dict[str, TeamSituationProfile] = {}
        for prof in self._index.values():
            if prof.venue != venue or prof.situation != situation:
                continue
            if code and prof.league != code:
                continue
            if prof.team != resolved and team_key(prof.team) != team_key(resolved):
                if not (
                    team_key(resolved) in team_key(prof.team)
                    or team_key(prof.team) in team_key(resolved)
                ):
                    continue
            out[prof.window] = prof
        return out

    def expected_for_live(
        self,
        team_name: str,
        *,
        league: str,
        venue: str,
        live_situation: str,
        minute: int,
        fav_losing_at_ht: bool,
    ) -> tuple[SituationWindowMetrics | None, str, str, int]:
        """
        Devolve (métricas acumuladas, janela actual, situação histórica, nº jogos amostra).
        """
        sit_key = live_situation_key(live_situation, fav_losing_at_ht=fav_losing_at_ht)
        post_ht = minute > 45 and (
            live_situation in ("fav_losing_post_ht", "fav_losing_ht")
            or fav_losing_at_ht
            or sit_key.endswith("_at_ht")
        )
        window_profiles = self.profiles_for(
            team_name, league=league, venue=venue, situation=sit_key
        )
        if not window_profiles:
            return None, resolve_live_window(minute, post_ht=post_ht), sit_key, 0

        metrics, current_window, sample = cumulative_expected(
            window_profiles, minute=minute, post_ht=post_ht
        )
        if sample < _MIN_SAMPLE:
            return None, current_window, sit_key, sample
        return metrics, current_window, sit_key, sample


_store: SituationStore | None = None


def get_situation_store() -> SituationStore:
    global _store
    if _store is None:
        _store = SituationStore()
    return _store