"""Saved notification targets (address book) — reusable across feeds.

Stores a list of named notification URLs that can be selected when subscribing
to any feed, instead of typing the URL each time.

Shape on disk (var/notification_targets.json):
    [
      {"name": "Telegram 群组", "url": "tgram://123:ABC/chat_id"},
      {"name": "ntfy RSS", "url": "ntfys://ntfy.yufei.im/RSS"}
    ]
"""

import json
import os
import threading
from typing import List, Optional


class NotificationTargets:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> list:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                return []
        return data if isinstance(data, list) else []

    def _save(self, targets: list) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(targets, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list(self) -> List[dict]:
        """Return all saved targets: [{"name": ..., "url": ...}, ...]."""
        return self._load()

    def urls(self) -> List[str]:
        """Return just the URL strings."""
        return [t["url"] for t in self._load() if t.get("url")]

    def add(self, name: str, url: str) -> str:
        """Add a new target. Returns 'added', 'exists', or 'invalid'."""
        name = (name or "").strip()
        url = (url or "").strip()
        if not name or not url:
            return "invalid"
        with self._lock:
            targets = self._load()
            if any(t["url"] == url for t in targets):
                return "exists"
            targets.append({"name": name, "url": url})
            self._save(targets)
        return "added"

    def remove(self, url: str) -> bool:
        """Remove a target by URL. Returns True if found and removed."""
        url = (url or "").strip()
        with self._lock:
            targets = self._load()
            new_targets = [t for t in targets if t.get("url") != url]
            if len(new_targets) == len(targets):
                return False
            self._save(new_targets)
        return True
