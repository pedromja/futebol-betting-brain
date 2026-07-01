"""Sync de ficheiros críticos para Supabase Storage (plano free).

Sem disco persistente no Render: histórico, bots e contas sobrevivem a redeploys.
Requer SUPABASE_URL + SUPABASE_SERVICE_KEY no ambiente de produção.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from config.data_paths import DATA_DIR, ensure_data_dir

TRACKED_REL_PATHS: tuple[str, ...] = (
    "predictions.jsonl",
    "bots.jsonl",
    "bot_signals.jsonl",
    "ia_live_signals.jsonl",
    "ia_prematch_snapshots.jsonl",
    "auth_users.json",
    "push_subscriptions.jsonl",
    "ia_audit.json",
    "backtest_results.json",
    "last_resolve.json",
    "last_enrich.json",
    "live_stats_snapshots.jsonl",
    "pattern_track.jsonl",
)

_last_pushed_mtime: dict[str, float] = {}
_sync_started = False


def _flag(name: str, default: str = "1") -> bool:
    raw = (os.getenv(name) or default).strip().lower()
    return raw not in ("0", "false", "no", "off")


def remote_enabled() -> bool:
    if not _flag("REMOTE_STORAGE_ENABLED", "1"):
        return False
    return bool(
        (os.getenv("SUPABASE_URL") or "").strip()
        and (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    )


def _bucket() -> str:
    return (os.getenv("REMOTE_STORAGE_BUCKET") or "futebol-data").strip()


def _base_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")


def _headers(*, upsert: bool = False) -> dict[str, str]:
    key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }
    if upsert:
        headers["x-upsert"] = "true"
    return headers


def _rel_path(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError:
        return None


def _object_url(rel: str) -> str:
    return f"{_base_url()}/storage/v1/object/{_bucket()}/{rel}"


def _count_jsonl_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _should_replace_local(local_text: str, remote_text: str, rel: str) -> bool:
    if not remote_text.strip():
        return False
    if not local_text.strip():
        return True
    if rel.endswith(".jsonl"):
        return _count_jsonl_lines(remote_text) >= _count_jsonl_lines(local_text)
    return len(remote_text) >= len(local_text)


def _http_request(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def pull_file(rel: str) -> bool:
    if not remote_enabled():
        return False
    status, body = _http_request("GET", _object_url(rel), headers=_headers())
    if status == 404:
        return False
    if status != 200:
        return False
    local = DATA_DIR / rel
    local.parent.mkdir(parents=True, exist_ok=True)
    remote_text = body.decode("utf-8")
    local_text = local.read_text(encoding="utf-8") if local.exists() else ""
    if _should_replace_local(local_text, remote_text, rel):
        local.write_text(remote_text, encoding="utf-8")
        try:
            _last_pushed_mtime[rel] = local.stat().st_mtime
        except OSError:
            pass
        return True
    return False


def push_file(path: Path, *, force: bool = False) -> bool:
    if not remote_enabled():
        return False
    rel = _rel_path(path)
    if not rel or rel not in TRACKED_REL_PATHS:
        return False
    if not path.exists():
        return False
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    if not force and _last_pushed_mtime.get(rel) == mtime:
        return True
    body = path.read_bytes()
    status, _ = _http_request(
        "POST",
        _object_url(rel),
        data=body,
        headers={**_headers(upsert=True), "Content-Type": "application/octet-stream"},
    )
    if status in (200, 201):
        _last_pushed_mtime[rel] = mtime
        return True
    return False


def notify_data_changed(path: Path) -> None:
    """Chamar após gravar ficheiros em DATA_DIR."""
    if not remote_enabled():
        return
    try:
        push_file(path, force=True)
    except OSError:
        pass


def pull_tracked_files() -> dict[str, bool]:
    ensure_data_dir()
    if not remote_enabled():
        return {}
    out: dict[str, bool] = {}
    for rel in TRACKED_REL_PATHS:
        try:
            out[rel] = pull_file(rel)
        except OSError:
            out[rel] = False
    return out


def push_changed_files(*, force: bool = False) -> list[str]:
    if not remote_enabled():
        return []
    pushed: list[str] = []
    for rel in TRACKED_REL_PATHS:
        path = DATA_DIR / rel
        if push_file(path, force=force):
            pushed.append(rel)
    return pushed


def remote_status() -> dict:
    return {
        "enabled": remote_enabled(),
        "provider": "supabase" if remote_enabled() else None,
        "bucket": _bucket() if remote_enabled() else None,
        "tracked_files": len(TRACKED_REL_PATHS),
    }


def _periodic_loop(interval_sec: float) -> None:
    while True:
        time.sleep(interval_sec)
        try:
            push_changed_files()
        except OSError:
            pass


def start_periodic_sync(interval_sec: float | None = None) -> None:
    global _sync_started
    if _sync_started or not remote_enabled():
        return
    _sync_started = True
    raw = (os.getenv("REMOTE_STORAGE_SYNC_SEC") or "").strip()
    if interval_sec is None:
        try:
            interval_sec = float(raw) if raw else 120.0
        except ValueError:
            interval_sec = 120.0
    interval_sec = max(30.0, interval_sec)
    thread = threading.Thread(
        target=_periodic_loop,
        args=(interval_sec,),
        name="remote-storage-sync",
        daemon=True,
    )
    thread.start()


def push_all_tracked(*, force: bool = True) -> dict[str, bool]:
    """Upload manual — útil após configurar Supabase pela primeira vez."""
    ensure_data_dir()
    out: dict[str, bool] = {}
    for rel in TRACKED_REL_PATHS:
        path = DATA_DIR / rel
        out[rel] = push_file(path, force=force) if path.exists() else False
    return out