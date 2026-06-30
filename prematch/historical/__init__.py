"""Dados históricos football-data.co.uk — fecho + estilo agregados."""

from prematch.historical.aggregate import ingest_league
from prematch.historical.auditors import audit_market_closing, audit_style_profile
from prematch.historical.store import get_store

__all__ = [
    "ingest_league",
    "get_store",
    "audit_market_closing",
    "audit_style_profile",
]