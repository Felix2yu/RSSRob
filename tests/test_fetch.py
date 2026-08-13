from unittest.mock import patch

from rssrob.fetch import Fetcher, fetch_in_browserless


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


def test_fetcher_renders_via_browserless_content_api():
    class Resp:
        ok = True
        content = b"<html>rendered</html>"
        def raise_for_status(self):
            pass

    with patch("rssrob.fetch.requests.post", return_value=Resp()) as mock_post:
        out = Fetcher(browserless="localhost:3000").get(
            "http://x/", timeout=20, user_agent="UA")
    assert out == b"<html>rendered</html>"
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:3000/content"     # scheme added
    assert kwargs["json"]["url"] == "http://x/"
    assert kwargs["json"]["userAgent"] == {"userAgent": "UA"}  # v2 object form
    assert kwargs["json"]["waitForTimeout"] == 3000
    assert kwargs["timeout"] == 30                        # browser headroom


def test_fetcher_browserless_url_scheme_normalized():
    assert Fetcher(browserless="localhost:3000").browserless == "http://localhost:3000"
    assert Fetcher(browserless="http://bl:3000/").browserless == "http://bl:3000"
    assert Fetcher(browserless="").browserless is None
    assert Fetcher().browserless is None


def test_fetcher_browserless_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("RSSROB_BROWSERLESS", "bl:3000")
    assert Fetcher().browserless == "http://bl:3000"    # global default from env
    assert Fetcher(browserless="http://x:1").browserless == "http://x:1"  # explicit wins
    monkeypatch.delenv("RSSROB_BROWSERLESS")
    assert Fetcher().browserless is None


def test_fetch_in_browserless_posts_function_and_returns_json():
    class Resp:
        ok = True
        def raise_for_status(self):
            pass
        def json(self):
            return {"__ok": True, "data": {"data": {"dataList": [1, 2]}}}

    with patch("rssrob.fetch.requests.post", return_value=Resp()) as mock_post:
        out = fetch_in_browserless(
            "http://bl:3000", "https://szwtfz.maitix.com/h5/",
            {"url": "https://client.maitix.com/api/pro/projects",
             "headers": {"Origin": "https://szwtfz.maitix.com"}, "wait": 6000},
            timeout=30)
    assert out == {"data": {"dataList": [1, 2]}}
    args, kwargs = mock_post.call_args
    assert args[0] == "http://bl:3000/function"
    assert kwargs["json"]["code"].count("szwtfz.maitix.com") == 2   # page + API url
    assert "waitForTimeout(cfg.waitMs)" in kwargs["json"]["code"]
    assert '"waitMs": 6000' in kwargs["json"]["code"]
    assert "credentials: 'include'" in kwargs["json"]["code"]
    assert kwargs["timeout"] == 40


def test_fetch_in_browserless_raises_on_non_json():
    class Resp:
        ok = True
        def raise_for_status(self):
            pass
        def json(self):
            return {"__ok": False, "data": "<html>challenge</html>"}

    with patch("rssrob.fetch.requests.post", return_value=Resp()):
        try:
            fetch_in_browserless("bl:3000", "http://p/", {"url": "http://a/"})
            assert False, "should have raised"
        except RuntimeError as e:
            assert "did not return JSON" in str(e)
