"""Backtest multi-liga — pré-jogo vs IA live (parcial) com política de intervenção por odd spread."""

from backtest.competition_runner import run_competition_backtest
from backtest.runner import build_backtest_payload, load_backtest_results, run_backtest, save_backtest_results

__all__ = [
    "run_backtest",
    "run_competition_backtest",
    "build_backtest_payload",
    "load_backtest_results",
    "save_backtest_results",
]