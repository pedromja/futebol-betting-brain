"""Cliente partilhado xAI Responses API com x_search."""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta


class XSearchClient:
    API_URL = "https://api.x.ai/v1/responses"
    MODEL = "grok-4.3"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("XAI_API_KEY", "")

    @property
    def is_live(self) -> bool:
        return bool(self.api_key)

    def query(
        self,
        prompt: str,
        days_back: int = 14,
    ) -> tuple[str, str]:
        if not self.is_live:
            return "", "offline"

        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        payload = {
            "model": self.MODEL,
            "input": [{"role": "user", "content": prompt}],
            "tools": [{"type": "x_search", "from_date": from_date, "to_date": to_date}],
        }

        req = urllib.request.Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return "", f"error: {exc}"

        return self._extract_text(body), "x_search"

    @staticmethod
    def _extract_text(response: dict) -> str:
        if "output" in response:
            parts = []
            for block in response.get("output", []):
                if block.get("type") == "message":
                    for content in block.get("content", []):
                        if content.get("type") in ("output_text", "text"):
                            parts.append(content.get("text", ""))
            if parts:
                return "\n".join(parts)
        if "choices" in response:
            return response["choices"][0]["message"]["content"]
        return json.dumps(response)

    @staticmethod
    def parse_json_object(text: str) -> dict | None:
        text = text.strip()
        obj_match = re.search(r"\{[\s\S]*\}", text)
        if obj_match:
            try:
                return json.loads(obj_match.group())
            except json.JSONDecodeError:
                pass
        arr_match = re.search(r"\[[\s\S]*\]", text)
        if arr_match:
            try:
                return {"items": json.loads(arr_match.group())}
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def parse_json_array(text: str) -> list:
        text = text.strip()
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group())
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []