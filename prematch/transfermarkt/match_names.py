"""Normalização e matching de nomes de equipas."""

from __future__ import annotations

import re
import unicodedata


ALIASES: dict[str, str] = {
    "fc porto": "FC Porto",
    "porto": "FC Porto",
    "sporting cp": "Sporting",
    "sporting lisbon": "Sporting",
    "sl benfica": "Benfica",
    "sc braga": "SC Braga",
    "braga": "SC Braga",
    "maritimo": "Marítimo",
    "cs maritimo": "Marítimo",
    "cinfães": "Cinfães",
    "cinfães fc": "Cinfães",
    "estoril praia": "Estoril",
    "gd estoril": "Estoril",
    "farense": "Farense",
    "sc farense": "Farense",
    "psg": "Paris Saint-Germain",
    "paris sg": "Paris Saint-Germain",
    "ogc nice": "Nice",
    "olympique nice": "Nice",
}


def normalize_team(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def team_key(name: str) -> str:
    return normalize_team(name).lower()


def resolve_team_name(name: str, known: set[str] | None = None) -> str:
    raw = normalize_team(name)
    lower = raw.lower()
    if lower in ALIASES:
        return ALIASES[lower]
    if known:
        for key in known:
            kl = key.lower()
            if lower == kl or lower in kl or kl in lower:
                return key
    return raw


def find_in_index(name: str, index: dict[str, object]) -> tuple[str, object] | None:
    if not index:
        return None
    resolved = resolve_team_name(name, set(index.keys()))
    if resolved in index:
        return resolved, index[resolved]
    lower = team_key(resolved)
    for key, val in index.items():
        kl = team_key(key)
        if lower == kl or lower in kl or kl in lower:
            return key, val
    alias = ALIASES.get(lower)
    if alias and alias in index:
        return alias, index[alias]
    return None