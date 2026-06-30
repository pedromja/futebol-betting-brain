"""Testa XAI_API_KEY do .env contra api.x.ai."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

key = os.getenv("XAI_API_KEY", "")
if not key:
    print("XAI_API_KEY: missing")
    sys.exit(1)

payload = {
    "model": "grok-4.3",
    "input": [{"role": "user", "content": 'Responde só JSON: {"ok": true}'}],
}
req = urllib.request.Request(
    "https://api.x.ai/v1/responses",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print("status:", resp.status)
        print("ok:", bool(body))
except urllib.error.HTTPError as exc:
    print("HTTP", exc.code)
    print(exc.read().decode("utf-8")[:800])
    sys.exit(2)