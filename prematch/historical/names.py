"""Nomes CSV football-data.co.uk → nomes canónicos do motor."""

from __future__ import annotations

from prematch.transfermarkt.match_names import normalize_team, resolve_team_name

# Nomes como aparecem no P1.csv
_CSV_ALIASES: dict[str, str] = {
    "sp lisbon": "Sporting",
    "sporting lisbon": "Sporting",
    "sp braga": "SC Braga",
    "guimaraes": "Vitória Guimarães",
    "vitoria guimaraes": "Vitória Guimarães",
    "vitoria de guimaraes": "Vitória Guimarães",
    "famalicao": "Famalicão",
    "estrela": "Estrela Amadora",
    "estrela amadora": "Estrela Amadora",
    "avs": "AVS",
    "fc porto": "FC Porto",
    "porto": "FC Porto",
    "benfica": "Benfica",
    "maritimo": "Marítimo",
    "cs maritimo": "Marítimo",
}


def canonical_team(csv_name: str) -> str:
    raw = normalize_team(csv_name)
    if not raw:
        return ""
    key = raw.lower()
    if key in _CSV_ALIASES:
        return _CSV_ALIASES[key]
    resolved = resolve_team_name(raw, None)
    if key == "guimaraes":
        return "Vitória Guimarães"
    return resolved