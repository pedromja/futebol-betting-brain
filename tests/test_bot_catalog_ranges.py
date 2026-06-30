"""Testes — intervalos nos filtros e condições do catálogo de bots."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.catalog import BOT_WIZARD_FILTERS, catalog_payload


def test_wizard_filters_expose_ranges():
    by_id = {f["id"]: f for f in BOT_WIZARD_FILTERS}
    assert by_id["min_score"]["range_hint"] == "0.50–0.90"
    assert by_id["min_ev_pct"]["range_hint"] == "−5–50%"
    assert by_id["minutes_before"]["range_hint"] == "5–720 min"
    assert by_id["max_stake_level"]["range_hint"] == "1–10"


def test_categories_enriched_with_ranges():
    payload = catalog_payload()
    cats = {c["id"]: c for c in payload["categories"]}
    ev = next(f for f in cats["ev"]["fields"] if f["id"] == "best_ev_pct")
    assert ev["range_hint"] == "−5–50%"
    assert ev["min"] == -5
    minute = next(f for f in cats["live"]["fields"] if f["id"] == "minute")
    assert minute["range_hint"] == "0–120"
    assert payload["wizard_filters"]