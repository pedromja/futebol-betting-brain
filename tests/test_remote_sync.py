"""Testes — sync remoto Supabase (mock HTTP)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storage import remote_sync


def test_remote_disabled_without_env(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    assert remote_sync.remote_enabled() is False


def test_remote_enabled_with_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    assert remote_sync.remote_enabled() is True


def test_merge_jsonl_prefers_more_lines():
    local = '{"a":1}\n'
    remote = '{"a":1}\n{"b":2}\n'
    assert remote_sync._should_replace_local(local, remote, "predictions.jsonl") is True
    assert remote_sync._should_replace_local(remote, local, "predictions.jsonl") is False


def test_push_file_tracked(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pred = data_dir / "predictions.jsonl"
    pred.write_text('{"home":"A"}\n', encoding="utf-8")
    monkeypatch.setattr(remote_sync, "DATA_DIR", data_dir)
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b""
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert remote_sync.push_file(pred, force=True) is True


def test_pull_file_writes_local(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(remote_sync, "DATA_DIR", data_dir)
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")

    body = b'{"home":"France"}\n'

    def fake_request(method, url, **kwargs):
        assert method == "GET"
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = body
        return resp

    with patch("storage.remote_sync._http_request", side_effect=lambda m, u, **k: (200, body)):
        assert remote_sync.pull_file("predictions.jsonl") is True
    assert (data_dir / "predictions.jsonl").read_text(encoding="utf-8") == body.decode()