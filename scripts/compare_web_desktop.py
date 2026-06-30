"""Compara o que cada porta serve (desktop vs web dev)."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request

PORTS = {
    8765: "desktop-exe",
    18765: "web-dev",
}

CHECKS = [
    ("index.html", "/"),
    ("app.js", "/app.js?v=79"),
    ("style.css", "/style.css?v=79"),
    ("sw.js", "/sw.js"),
    ("branding", "/api/branding"),
    ("auth", "/api/auth/status"),
    ("health", "/api/health"),
]

MARKERS = [
    "prematch-moment-card",
    "moment-banner-critical",
    "cfg-auth-section",
    "sindgreen-mentor-v79",
    "app.js?v=79",
]


def fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, str(exc)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> None:
    print("=== Desktop (8765) vs Web dev (18765) ===\n")
    results: dict[int, dict] = {}

    for port, label in PORTS.items():
        base = f"http://127.0.0.1:{port}"
        row: dict = {"label": label, "up": False}
        code, html = fetch(base + "/")
        row["up"] = code == 200
        if code == 200:
            row["markers"] = {m: m in html for m in MARKERS}
            row["html_hash"] = digest(html)
        results[port] = row

        print(f"[{port}] {label} — {'ONLINE' if row['up'] else 'OFFLINE'}")
        if row.get("markers"):
            for m, ok in row["markers"].items():
                print(f"  {'OK' if ok else 'MISSING':7} {m}")

        for name, path in CHECKS[1:]:
            code, body = fetch(base + path)
            if path.startswith("/api/"):
                try:
                    parsed = json.loads(body)
                    print(f"  {name:10} {code} -> {json.dumps(parsed, ensure_ascii=False)[:120]}")
                except json.JSONDecodeError:
                    print(f"  {name:10} {code} -> {body[:80]}")
            else:
                print(f"  {name:10} {code} hash={digest(body)} len={len(body)}")
        print()

    if results.get(8765, {}).get("html_hash") and results.get(18765, {}).get("html_hash"):
        same = results[8765]["html_hash"] == results[18765]["html_hash"]
        print("HTML igual entre portas:", "SIM" if same else "NAO")
        if not same:
            missing_8765 = [m for m, ok in results[8765].get("markers", {}).items() if not ok]
            missing_18765 = [m for m, ok in results[18765].get("markers", {}).items() if not ok]
            if missing_8765:
                print("  Falta na 8765 (desktop):", ", ".join(missing_8765))
            if missing_18765:
                print("  Falta na 18765 (web):", ", ".join(missing_18765))


if __name__ == "__main__":
    main()