"""Notification targets (Apprise URLs) + per-target digest frequency, in one JSON file.

Shape on disk:
    {
      "feeds": {"<feed>": ["tgram://123:ABC/chat_id", ...], ...},
      "frequencies": {"tgram://123:ABC/chat_id": 24, ...}
    }

The frequency is per *notification target* (one value for all of that target's
feeds), set on first subscribe and editable afterwards. Legacy email-based
shapes are auto-migrated on load (emails become mailto:// URLs).
"""

import json
import os
import re
import threading
from typing import List, Tuple

DEFAULT_FREQ_HOURS = 24


def normalize_hours(value, default: float = DEFAULT_FREQ_HOURS):
    """Coerce a frequency to a positive number of hours, else `default`."""
    try:
        h = float(value)
    except (TypeError, ValueError):
        return default
    if h <= 0:
        return default
    return int(h) if float(h).is_integer() else h


def _is_apprise_url(s: str) -> bool:
    """Check if a string looks like an Apprise URL (scheme://...)."""
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]+://", s or ""))


def _migrate_email(email: str) -> str:
    """Convert a legacy email address to a mailto:// Apprise URL."""
    return f"mailto://{email}"


class Subscribers:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _load_raw(self) -> dict:
        """Return the full raw JSON dict from disk."""
        if not os.path.exists(self.path):
            return {}
        with open(self.path, encoding="utf-8") as f:
            try:
                return json.load(f) or {}
            except (json.JSONDecodeError, ValueError):
                return {}

    def _load(self) -> Tuple[dict, dict]:
        """Return (feeds {feed: [urls]}, frequencies {url: hours})."""
        raw = self._load_raw()

        if isinstance(raw.get("feeds"), dict):
            feeds = {}
            freqs = {}
            for fd, urls in raw["feeds"].items():
                migrated = []
                for u in (urls or []):
                    if _is_apprise_url(u):
                        migrated.append(u)
                    else:
                        migrated.append(_migrate_email(u))
                feeds[fd] = list(dict.fromkeys(migrated))

            for key, h in (raw.get("frequencies") or {}).items():
                if _is_apprise_url(key):
                    freqs[key] = normalize_hours(h)
                else:
                    freqs[_migrate_email(key)] = normalize_hours(h)
            return feeds, freqs

        # legacy top-level map
        feeds, freqs = {}, {}
        for feed, val in raw.items():
            if isinstance(val, list):
                feeds[feed] = list(dict.fromkeys(
                    _migrate_email(v) if not _is_apprise_url(v) else v
                    for v in val))
            elif isinstance(val, dict):
                feeds[feed] = list(dict.fromkeys(
                    _migrate_email(k) if not _is_apprise_url(k) else k
                    for k in val.keys()))
                for e, h in val.items():
                    url = _migrate_email(e) if not _is_apprise_url(e) else e
                    freqs[url] = normalize_hours(h)
            else:
                feeds[feed] = []
        return feeds, freqs

    def _save(self, feeds: dict, freqs: dict) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        # preserve auth_notify and any future top-level keys
        existing = self._load_raw()
        payload = {"feeds": feeds, "frequencies": freqs}
        if "auth_notify" in existing:
            payload["auth_notify"] = existing["auth_notify"]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def list(self, feed: str) -> List[str]:
        """Notification URLs for a feed."""
        feeds, _ = self._load()
        return list(feeds.get(feed, []))

    def freq(self, url: str):
        """The target's digest frequency in hours (default if unknown)."""
        _, freqs = self._load()
        return freqs.get((url or "").strip(), DEFAULT_FREQ_HOURS)

    def items(self, feed: str) -> dict:
        """{url: hours} for a feed."""
        feeds, freqs = self._load()
        return {u: freqs.get(u, DEFAULT_FREQ_HOURS) for u in feeds.get(feed, [])}

    def by_email(self) -> dict:
        """Legacy alias: {url: {"feeds": [...], "hours": N}}, sorted."""
        return self.by_target()

    def by_target(self) -> dict:
        """{url: {"feeds": [feeds...], "hours": N}}, sorted."""
        feeds, freqs = self._load()
        out: dict = {}
        for feed, urls in feeds.items():
            for u in urls:
                out.setdefault(u, []).append(feed)
        return {u: {"feeds": sorted(out[u]),
                     "hours": freqs.get(u, DEFAULT_FREQ_HOURS)}
                for u in sorted(out)}

    def add(self, feed: str, url: str, hours=DEFAULT_FREQ_HOURS) -> str:
        """Subscribe a notification target to a feed. Returns 'added',
        'exists', or 'invalid'."""
        url = (url or "").strip()
        if not url:
            return "invalid"
        if not _is_apprise_url(url):
            return "invalid"
        with self._lock:
            feeds, freqs = self._load()
            lst = feeds.setdefault(feed, [])
            existed = url in lst
            if not existed:
                lst.append(url)
            if url not in freqs:
                freqs[url] = normalize_hours(hours)
            self._save(feeds, freqs)
        return "exists" if existed else "added"

    def set_freq(self, url: str, hours) -> bool:
        """Update an existing target's frequency."""
        url = (url or "").strip()
        with self._lock:
            feeds, freqs = self._load()
            if not any(url in us for us in feeds.values()):
                return False
            freqs[url] = normalize_hours(hours)
            self._save(feeds, freqs)
        return True

    def remove(self, feed: str, url: str) -> bool:
        url = (url or "").strip()
        with self._lock:
            feeds, freqs = self._load()
            lst = feeds.get(feed, [])
            if url not in lst:
                return False
            lst.remove(url)
            if not any(url in us for us in feeds.values()):
                freqs.pop(url, None)
            self._save(feeds, freqs)
        return True

    # ── auth-notify settings (token expiry notifications) ─────────────

    def auth_notify_enabled(self) -> bool:
        """Whether token-expiry notifications are enabled (default True)."""
        raw = self._load_raw()
        an = raw.get("auth_notify")
        if not isinstance(an, dict):
            return True  # default: enabled
        return an.get("enabled", True)

    def set_auth_notify_enabled(self, enabled: bool) -> None:
        with self._lock:
            feeds, freqs = self._load()
            raw = self._load_raw()
            an = raw.get("auth_notify") or {}
            an["enabled"] = bool(enabled)
            # preserve existing targets
            if "targets" not in an:
                an["targets"] = []
            # write back via _save which preserves auth_notify
            self._save_with(feeds, freqs, auth_notify=an)

    def auth_notify_targets(self) -> List[str]:
        """Specific targets for auth notifications; empty = all targets."""
        raw = self._load_raw()
        an = raw.get("auth_notify") or {}
        return an.get("targets") or []

    def set_auth_notify_targets(self, targets: List[str]) -> None:
        with self._lock:
            feeds, freqs = self._load()
            raw = self._load_raw()
            an = raw.get("auth_notify") or {}
            an["targets"] = [t for t in targets if t]
            self._save_with(feeds, freqs, auth_notify=an)

    def all_target_urls(self) -> List[str]:
        """All unique notification target URLs across all feeds."""
        feeds, _ = self._load()
        urls = set()
        for url_list in feeds.values():
            urls.update(url_list)
        return sorted(urls)

    # alias used by scheduler
    urls = all_target_urls

    def _save_with(self, feeds: dict, freqs: dict, auth_notify: dict = None) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        payload = {"feeds": feeds, "frequencies": freqs}
        if auth_notify is not None:
            payload["auth_notify"] = auth_notify
        else:
            existing = self._load_raw()
            if "auth_notify" in existing:
                payload["auth_notify"] = existing["auth_notify"]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, self.path)
