"""Testes — caminhos de dados configuráveis."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_predictions_log_uses_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib

    import config.data_paths as dp
    import history.predictions as pred

    importlib.reload(dp)
    importlib.reload(pred)

    assert pred.DEFAULT_LOG == tmp_path / "predictions.jsonl"
    assert dp.PREDICTIONS_LOG == tmp_path / "predictions.jsonl"