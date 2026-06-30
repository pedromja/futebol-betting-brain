"""Normaliza fase/competição a partir de payloads ESPN (scoreboard ou evento)."""

from __future__ import annotations

_SLUG_LABELS: dict[str, str] = {
    "group-stage": "Group Stage",
    "round-of-32": "Round of 32",
    "round-of-16": "Round of 16",
    "quarterfinals": "Quarterfinals",
    "semifinals": "Semifinals",
    "3rd-place-match": "3rd-Place Match",
    "final": "Final",
    "playoffs": "Playoffs",
    "play-off": "Play-off",
}


def _slug_to_label(slug: str) -> str:
    key = (slug or "").strip().lower()
    if not key:
        return ""
    if key in _SLUG_LABELS:
        return _SLUG_LABELS[key]
    return key.replace("-", " ").title()


def _type_object_label(typ: object) -> str:
    if not isinstance(typ, dict):
        return ""
    return str(typ.get("name") or typ.get("abbreviation") or "").strip()


def stage_from_scoreboard(data: dict | None) -> str:
    """Fase actual da liga no scoreboard (ex.: Round of 32)."""
    if not data:
        return ""
    leagues = data.get("leagues") or []
    if not leagues:
        return ""
    season = leagues[0].get("season") or {}
    label = _type_object_label(season.get("type"))
    if label:
        return label
    slug = str(season.get("slug") or "")
    return _slug_to_label(slug)


def stage_from_event_season(season: dict | None, *, scoreboard_stage: str = "") -> str:
    """Resolve fase a partir de event.season — evita IDs numéricos (ex.: 13801)."""
    if scoreboard_stage:
        return scoreboard_stage
    if not season:
        return ""

    typ = season.get("type")
    if isinstance(typ, dict):
        label = _type_object_label(typ)
        if label:
            return label

    slug = str(season.get("slug") or "")
    if slug:
        return _slug_to_label(slug)

    if isinstance(typ, int):
        return ""

    text = str(typ or "").strip()
    if text.isdigit():
        return ""
    return text


def resolve_espn_stage(
    event: dict | None,
    scoreboard: dict | None = None,
) -> str:
    """Melhor esforço: scoreboard → event.season → notas da competição."""
    board_stage = stage_from_scoreboard(scoreboard)
    season = (event or {}).get("season") if event else None
    stage = stage_from_event_season(season if isinstance(season, dict) else None, scoreboard_stage=board_stage)
    if stage:
        return stage

    if not event:
        return board_stage

    comp = (event.get("competitions") or [{}])[0]
    for note in comp.get("notes") or []:
        text = str(note.get("text") or note.get("headline") or "").strip()
        if text:
            return text
    alt = str(comp.get("altGameNote") or "").strip()
    if alt:
        return alt
    return board_stage