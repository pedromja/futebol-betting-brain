"""ESPN summary — comentário live, key events e classificação semântica leve."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from discovery.web_browser import WebBrowser

# Janelas de fase IA (minutos de jogo)
PHASE_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("J1", 15, 30),
    ("J2", 30, 45),
    ("J3", 60, 75),
    ("J4", 75, 120),
)

_EVENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("goal", re.compile(r"\bgoal\b|go+a+l", re.I)),
    ("corner", re.compile(r"\bcorner\b", re.I)),
    ("substitution", re.compile(r"\bsubstitution\b|\breplaces\b|\bcomes off\b|\bon for\b", re.I)),
    ("yellow_card", re.compile(r"\byellow card\b", re.I)),
    ("red_card", re.compile(r"\bred card\b", re.I)),
    ("foul", re.compile(r"\bfoul\b|\bfree kick\b", re.I)),
    ("save", re.compile(r"\bsave[ds]?\b|\battempt saved\b", re.I)),
    ("shot", re.compile(r"\bshot\b|\bheader\b|\battempt\b", re.I)),
    ("offside", re.compile(r"\boffside\b", re.I)),
    ("kickoff", re.compile(r"\bkickoff\b|\bbegins\b|\bend[s]?\b", re.I)),
    ("pressure", re.compile(r"\bpressure\b|\bdominat\w*\b|\bpossession\b|\bcontrol\b", re.I)),
)

_TEAM_IN_PARENS = re.compile(r"\(([^)]+)\)")
_MINUTE_RE = re.compile(r"^(\d+)(?:\+(\d+))?'?$")


@dataclass
class EspnCommentaryEntry:
    sequence: int
    minute: int
    minute_display: str
    period: int
    text: str
    event_type: str
    team: str | None = None
    player: str | None = None
    is_key_event: bool = False
    scoring_play: bool = False
    phase_window: str | None = None
    source: str = "commentary"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EspnCommentaryFeed:
    espn_event_id: str
    espn_league_code: str
    home: str
    away: str
    status: str
    minute: int
    minute_display: str
    fetched_at: str
    entries: list[EspnCommentaryEntry] = field(default_factory=list)
    key_events: list[EspnCommentaryEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "espn_event_id": self.espn_event_id,
            "espn_league_code": self.espn_league_code,
            "home": self.home,
            "away": self.away,
            "status": self.status,
            "minute": self.minute,
            "minute_display": self.minute_display,
            "fetched_at": self.fetched_at,
            "entries": [e.to_dict() for e in self.entries],
            "key_events": [e.to_dict() for e in self.key_events],
            "recent": [e.to_dict() for e in self.entries[-12:]],
        }


def parse_minute_display(display: str) -> tuple[int, str]:
    """Converte '90'+7'' ou '39'' em minuto inteiro."""
    raw = (display or "").strip().replace("\u2019", "'").replace("′", "'")
    if not raw:
        return 0, ""
    m = _MINUTE_RE.match(raw)
    if not m:
        digits = re.findall(r"\d+", raw)
        if digits:
            base = int(digits[0])
            extra = int(digits[1]) if len(digits) > 1 else 0
            return base + extra, raw
        return 0, raw
    base = int(m.group(1))
    extra = int(m.group(2) or 0)
    return base + extra, raw


def phase_window_for_minute(minute: int) -> str | None:
    for code, lo, hi in PHASE_WINDOWS:
        if lo <= minute <= hi:
            return code
    return None


def classify_event_text(text: str) -> str:
    blob = text or ""
    for name, pattern in _EVENT_PATTERNS:
        if pattern.search(blob):
            return name
    return "narrative"


def _extract_team_player(text: str) -> tuple[str | None, str | None]:
    """Extrai equipa/jogador de padrões ESPN — 'Name (Team)'."""
    if not text:
        return None, None
    m = _TEAM_IN_PARENS.search(text)
    team = m.group(1).strip() if m else None
    player = None
    if m:
        before = text[: m.start()].strip()
        if before:
            player = before.split(".", 1)[-1].strip()
    return team, player


def _header_teams(payload: dict) -> tuple[str, str, str, int, str]:
    header = payload.get("header") or {}
    comps = (header.get("competitions") or [{}])[0]
    status = comps.get("status") or {}
    stype = status.get("type") or {}
    state = str(stype.get("state") or stype.get("name") or "")
    clock = status.get("clock") or 0
    try:
        minute = int(clock)
    except (TypeError, ValueError):
        minute = 0
    display = str(status.get("displayClock") or "")
    if display:
        minute, _ = parse_minute_display(display)

    home = away = ""
    for row in comps.get("competitors") or []:
        name = (row.get("team") or {}).get("displayName") or ""
        if row.get("homeAway") == "home":
            home = name
        elif row.get("homeAway") == "away":
            away = name
    return home, away, state, minute, display


def _parse_commentary_rows(rows: list, *, start_sequence: int = 0) -> list[EspnCommentaryEntry]:
    out: list[EspnCommentaryEntry] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        time_obj = row.get("time") or {}
        display = str(time_obj.get("displayValue") or "").strip()
        minute, minute_display = parse_minute_display(display)
        period = int((row.get("period") or {}).get("number") or (1 if minute <= 45 else 2))
        team, player = _extract_team_player(text)
        event_type = classify_event_text(text)
        out.append(
            EspnCommentaryEntry(
                sequence=int(row.get("sequence") or start_sequence + len(out)),
                minute=minute,
                minute_display=minute_display or display,
                period=period,
                text=text,
                event_type=event_type,
                team=team,
                player=player,
                is_key_event=event_type in ("goal", "red_card", "substitution"),
                phase_window=phase_window_for_minute(minute),
                source="commentary",
            )
        )
    return out


def _parse_key_events(rows: list) -> list[EspnCommentaryEntry]:
    out: list[EspnCommentaryEntry] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        clock = row.get("clock") or {}
        display = str(clock.get("displayValue") or "").strip()
        minute, minute_display = parse_minute_display(display)
        period = int((row.get("period") or {}).get("number") or (1 if minute <= 45 else 2))
        type_obj = row.get("type") or {}
        type_slug = str(type_obj.get("type") or type_obj.get("text") or "").lower()
        event_type = classify_event_text(f"{type_slug} {text}")
        if type_slug and type_slug not in event_type:
            if "goal" in type_slug:
                event_type = "goal"
            elif "substitution" in type_slug:
                event_type = "substitution"
            elif "card" in type_slug:
                event_type = "yellow_card" if "yellow" in type_slug else "red_card"
            elif "kickoff" in type_slug:
                event_type = "kickoff"
        team, player = _extract_team_player(text)
        out.append(
            EspnCommentaryEntry(
                sequence=int(row.get("id") or len(out)),
                minute=minute,
                minute_display=minute_display or display,
                period=period,
                text=text,
                event_type=event_type,
                team=team,
                player=player,
                is_key_event=True,
                scoring_play=bool(row.get("scoringPlay")),
                phase_window=phase_window_for_minute(minute),
                source="key_event",
            )
        )
    return out


def parse_espn_commentary_payload(
    payload: dict | None,
    *,
    espn_event_id: str,
    espn_league_code: str,
) -> EspnCommentaryFeed | None:
    if not payload:
        return None

    home, away, status, minute, minute_display = _header_teams(payload)
    commentary = _parse_commentary_rows(payload.get("commentary") or [])
    key_events = _parse_key_events(payload.get("keyEvents") or [])

    if not commentary and not key_events:
        plays = payload.get("plays") or []
        commentary = _parse_commentary_rows(plays)

    if not commentary and not key_events:
        return None

    if minute <= 0 and commentary:
        minute = commentary[-1].minute
        minute_display = commentary[-1].minute_display or minute_display

    return EspnCommentaryFeed(
        espn_event_id=str(espn_event_id),
        espn_league_code=espn_league_code,
        home=home,
        away=away,
        status=status,
        minute=minute,
        minute_display=minute_display,
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        entries=commentary,
        key_events=key_events,
    )


def fetch_espn_commentary(
    league_code: str,
    event_id: str,
    *,
    browser: WebBrowser | None = None,
    cache_ttl: int = 45,
) -> EspnCommentaryFeed | None:
    if not league_code or not event_id:
        return None
    br = browser or WebBrowser()
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/soccer/"
        f"{league_code}/summary?event={event_id}"
    )
    data = br.fetch_json(url, cache_ns="espn_commentary", cache_ttl=cache_ttl)
    return parse_espn_commentary_payload(
        data,
        espn_event_id=str(event_id),
        espn_league_code=league_code,
    )


def resolve_league_code_for_event(
    event_id: str,
    *,
    candidates: tuple[str, ...] | None = None,
    browser: WebBrowser | None = None,
) -> str | None:
    """Tenta descobrir league_code ESPN quando só se conhece o gameId."""
    br = browser or WebBrowser()
    for code in candidates or (
        "fifa.world",
        "uefa.champions",
        "uefa.europa",
        "eng.1",
        "esp.1",
        "ita.1",
        "ger.1",
        "fra.1",
        "por.1",
    ):
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{code}/summary?event={event_id}"
        )
        data = br.fetch_json(url, cache_ns="espn_commentary_resolve", cache_ttl=120)
        if not data:
            continue
        header = data.get("header") or {}
        if str(header.get("id") or "") == str(event_id):
            return code
        if data.get("commentary") or data.get("keyEvents"):
            return code
    return None