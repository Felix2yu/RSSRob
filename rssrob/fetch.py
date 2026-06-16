import requests


class Fetcher:
    """Thin requests wrapper. Injectable: anything with a matching `get` works."""

    def get(self, url: str, timeout: int = 20, user_agent: str = "RSSRob/0.1") -> bytes:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": user_agent})
        resp.raise_for_status()
        return resp.content
