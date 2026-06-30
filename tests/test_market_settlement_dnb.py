"""Testes — DNB void no empate e 1X2 no empate."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.market_settlement import (
    is_dnb_market,
    pnl_for_outcome,
    settle_market,
    settlement_note,
)


def test_dnb_home_void_on_draw():
    assert settle_market("DNB Casa", 1, 1) == "void"
    assert settle_market("DNB Casa", 2, 0) == "win"
    assert settle_market("DNB Casa", 0, 2) == "loss"
    assert pnl_for_outcome("void", 1.9, 10.0) == 0.0


def test_dnb_away_void_on_draw():
    assert settle_market("DNB Fora", 0, 0) == "void"
    assert settle_market("DNB Fora", 0, 1) == "win"
    assert settle_market("DNB Fora", 3, 1) == "loss"


def test_dnb_text_aliases():
    assert settle_market("Draw No Bet Casa", 2, 2) == "void"
    assert settle_market("empate anula fora", 1, 1) == "void"
    assert is_dnb_market("DNB Casa") is True


def test_1x2_loss_on_draw_not_void():
    assert settle_market("Vitória Casa", 1, 1) == "loss"
    assert settle_market("Vitória Fora", 2, 2) == "loss"
    assert settle_market("Empate", 1, 1) == "win"
    note = settlement_note("Vitória Casa", 1, 1, "loss")
    assert "1X2 perde" in note
    assert "DNB" in note


def test_dnb_settlement_note():
    note = settlement_note("DNB Casa", 0, 0, "void")
    assert "DNB void" in note