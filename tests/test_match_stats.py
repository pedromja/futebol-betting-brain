from discovery.match_stats import parse_events_response, parse_statistics_response


def test_parse_statistics_response():
    payload = {
        "response": [
            {
                "team": {"name": "Home FC"},
                "statistics": [
                    {"type": "Ball Possession", "value": "62%"},
                    {"type": "Total Shots", "value": 11},
                    {"type": "Shots on Goal", "value": 5},
                ],
            },
            {
                "team": {"name": "Away FC"},
                "statistics": [
                    {"type": "Ball Possession", "value": "38%"},
                    {"type": "Total Shots", "value": 4},
                    {"type": "Shots on Goal", "value": 1},
                ],
            },
        ]
    }
    bundle = parse_statistics_response(99, payload)
    assert bundle is not None
    assert bundle.fixture_id == 99
    assert bundle.home.possession_pct == 62
    assert bundle.home.shots_total == 11
    assert bundle.away.shots_on == 1


def test_parse_events_response():
    payload = {
        "response": [
            {
                "time": {"elapsed": 12, "extra": None},
                "team": {"name": "Home FC"},
                "player": {"name": "Striker"},
                "assist": {"name": "Winger"},
                "type": "Goal",
                "detail": "Normal Goal",
            }
        ]
    }
    events = parse_events_response(payload)
    assert len(events) == 1
    assert events[0].minute == 12
    assert events[0].player == "Striker"