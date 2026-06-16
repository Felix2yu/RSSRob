from unittest.mock import patch

from rssrob.fetch import Fetcher


def test_fetcher_returns_content_and_sets_headers():
    class Resp:
        content = b"<html>ok</html>"
        def raise_for_status(self):
            pass

    with patch("rssrob.fetch.requests.get", return_value=Resp()) as mock_get:
        out = Fetcher().get("http://x/", timeout=5, user_agent="UA")
    assert out == b"<html>ok</html>"
    _, kwargs = mock_get.call_args
    assert kwargs["timeout"] == 5
    assert kwargs["headers"]["User-Agent"] == "UA"
