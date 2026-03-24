from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class NewsCalendar:
    def __init__(self, config: dict[str, Any], timeout: int = 10) -> None:
        self.config = config
        self.timeout = timeout

    def get_events(self) -> list[str]:
        provider = self.config.get("provider", "manual")
        if provider == "manual":
            return list(self.config.get("high_impact_events", []))
        if provider == "json_file":
            return self._from_json_file()
        if provider == "json_url":
            return self._from_json_url()
        raise ValueError(f"Unsupported news provider: {provider}")

    def _normalize(self, payload: Any) -> list[str]:
        if isinstance(payload, dict):
            payload = payload.get("events", [])
        events: list[str] = []
        for item in payload:
            if isinstance(item, str):
                events.append(item)
            elif isinstance(item, dict) and item.get("time"):
                events.append(str(item["time"]))
        return events

    def _from_json_file(self) -> list[str]:
        path_value = self.config.get("local_json_path")
        if not path_value:
            return []
        path = Path(path_value)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return self._normalize(payload)

    def _from_json_url(self) -> list[str]:
        url = self.config.get("provider_url")
        if not url:
            return []
        if requests is None:
            raise ImportError("requests is required for news_filter.provider=json_url")
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return self._normalize(response.json())
