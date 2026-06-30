"""Testes — parser ESPN commentary (gameId 760490)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.espn_commentary import (
    classify_event_text,
    fetch_espn_commentary,
    parse_minute_display,
    phase_window_for_minute,
    resolve_league_code_for_event,
)


def test_parse_minute_display():
    assert parse_minute_display("39'") == (39, "39'")
    assert parse_minute_display("90'+7'") == (97, "90'+7'")
    assert parse_minute_display("") == (0, "")


def test_phase_window_for_minute():
    assert phase_window_for_minute(20) == "J1"
    assert phase_window_for_minute(40) == "J2"
    assert phase_window_for_minute(65) == "J3"
    assert phase_window_for_minute(86) == "J4"
    assert phase_window_for_minute(10) is None


def test_classify_event_text():
    assert classify_event_text("Corner, Côte d'Ivoire.") == "corner"
    assert classify_event_text("Goal! Norway 1") == "goal"
    assert classify_event_text("Foul by Martin Ødegaard") == "foul"
    assert classify_event_text("Norway have had over 75% possession") == "pressure"


def test_fetch_espn_commentary_game_760490():
    feed = fetch_espn_commentary("fifa.world", "760490", cache_ttl=300)
    assert feed is not None
    assert feed.espn_event_id == "760490"
    assert feed.home
    assert feed.away
    assert len(feed.entries) >= 10
    assert any(e.event_type == "goal" for e in feed.key_events)
    assert any(e.event_type == "corner" for e in feed.entries)
    payload = feed.to_dict()
    assert "recent" in payload
    assert len(payload["recent"]) <= 12


def test_resolve_league_code_for_event_760490():
    code = resolve_league_code_for_event("760490", candidates=("fifa.world",))
    assert code == "fifa.world"