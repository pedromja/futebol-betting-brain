"""Caminhos e bootstrap para modo desktop (dev ou executável PyInstaller)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def app_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def configure_environment() -> Path:
    """Define cwd, DATA_DIR e WEB_DIR antes de importar o motor."""
    root = app_root()
    bundle = bundle_root()
    os.chdir(root)
    os.environ.setdefault("APP_ROOT", str(root))
    os.environ.setdefault("DATA_DIR", str(root / "data"))
    os.environ.setdefault("WEB_DIR", str(bundle / "web"))
    os.environ.setdefault("DESKTOP_APP", "1")
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root