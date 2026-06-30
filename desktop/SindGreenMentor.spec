# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — SindGreenMentor Pro Desktop."""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

from PyInstaller.utils.hooks import collect_submodules

_pkgs = [
    "bankroll",
    "config",
    "decision",
    "discovery",
    "environment",
    "history",
    "live",
    "markets",
    "models",
    "news",
    "odds",
    "prematch",
    "scanner",
    "stakes",
    "web",
]
_hidden = []
for _pkg in _pkgs:
    try:
        _hidden.extend(collect_submodules(_pkg))
    except Exception:
        _hidden.append(_pkg)

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "web" / "static"), "web/static"),
        (str(ROOT / "web" / "branding.json"), "web"),
        (str(ROOT / "desktop" / "splash.html"), "desktop"),
        (str(ROOT / "data" / "historical"), "data/historical"),
        (str(ROOT / "data" / "transfermarkt"), "data/transfermarkt"),
    ],
    hiddenimports=_hidden + [
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "webview",
        "clr",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SindGreenMentor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "desktop" / "app.ico") if (ROOT / "desktop" / "app.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SindGreenMentor",
)