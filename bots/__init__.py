"""Bots configuráveis pelo utilizador."""

from bots.evaluator import evaluate_bot, evaluate_bots_for_scan
from bots.store import delete_bot, get_bot, list_bots, save_bot, toggle_bot

__all__ = [
    "evaluate_bot",
    "evaluate_bots_for_scan",
    "delete_bot",
    "get_bot",
    "list_bots",
    "save_bot",
    "toggle_bot",
]