from pathlib import Path

import pytest


@pytest.fixture
def fixtures():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def make_fetcher():
    """Returns a class building a fetcher from a {url: bytes} mapping."""
    class FakeFetcher:
        def __init__(self, mapping):
            self.mapping = mapping

        def get(self, url, timeout=20, user_agent="RSSRob/0.1"):
            if url not in self.mapping:
                raise RuntimeError(f"no fixture for {url}")
            return self.mapping[url]

    return FakeFetcher
