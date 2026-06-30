from discovery.match_stats import parse_statistics_response
from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats
from discovery.xg_estimate import enrich_bundle_xg, estimate_team_xg


def test_estimate_from_shots_on_off():
    stats = TeamLiveStats(shots_on=5, shots_off=3, shots_blocked=2)
    xg = estimate_team_xg(stats)
    assert xg == round(0.10 * 5 + 0.05 * 3 + 0.03 * 2, 2)


def test_estimate_from_total_shots_only():
    stats = TeamLiveStats(shots_total=10)
    xg = estimate_team_xg(stats)
    assert xg is not None
    assert xg > 0


def test_enrich_keeps_api_xg():
    bundle = MatchLiveStatsBundle(
        fixture_id=1,
        home=TeamLiveStats(team="H", xg=1.42),
        away=TeamLiveStats(team="A", shots_on=2),
    )
    enrich_bundle_xg(bundle)
    assert bundle.home.xg == 1.42
    assert bundle.home.xg_source == "api"
    assert bundle.away.xg_source == "estimated"
    assert bundle.away.xg == 0.2
    assert bundle.xg_source == "mixed"


def test_enrich_full_pipeline():
    payload = {
        "response": [
            {
                "team": {"name": "Home"},
                "statistics": [
                    {"type": "Shots on Goal", "value": 4},
                    {"type": "Shots off Goal", "value": 2},
                ],
            },
            {
                "team": {"name": "Away"},
                "statistics": [
                    {"type": "Expected Goals", "value": "0.88"},
                    {"type": "Shots on Goal", "value": 1},
                ],
            },
        ]
    }
    bundle = parse_statistics_response(7, payload)
    enrich_bundle_xg(bundle)
    assert bundle.home.xg_source == "estimated"
    assert bundle.away.xg_source == "api"
    assert bundle.away.xg == 0.88
    assert bundle.xg_source == "mixed"