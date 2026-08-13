import json
import os

import requests

from .config import normalize_browserless


def _raise_browserless_error(resp):
    """Turn a non-2xx browserless response into an error that carries the
    service's own error body (browserless 500s usually explain the cause)."""
    try:
        detail = resp.text[:500]
    except Exception:
        detail = ""
    raise RuntimeError(f"browserless HTTP {resp.status_code}: {detail}")


def _post_browserless(url, v2_payload, v1_payload, timeout):
    """POST with v1/v2 compatibility.

    browserless v2 strictly rejects unknown/ill-typed fields with 4xx (e.g.
    /function wants ``code``, userAgent is an object), while v1 ignores them
    and wants the old shapes (``function`` key, string userAgent). Try the v2
    payload first; on a 4xx fall back to the v1 payload exactly once."""
    resp = requests.post(url, json=v2_payload, timeout=timeout)
    if 400 <= resp.status_code < 500 and v1_payload is not None:
        resp = requests.post(url, json=v1_payload, timeout=timeout)
    return resp


def fetch_in_browserless(browserless_url, page_url, api, timeout: int = 30):
    """Render ``page_url`` in a headless browser and fetch an API *inside the
    page context*, returning the parsed JSON.

    Needed for WAF-protected sites (e.g. Alibaba Baxia challenges) where every
    API call must carry signature headers the browser SDK generates at runtime —
    ``POST /content`` alone cannot help because the data lives behind an API,
    not in the rendered HTML. ``api`` is a dict with ``url`` (+ optional
    ``method``, ``headers``); ``wait`` (ms) is the post-load settle time for
    the WAF SDK to initialize."""
    cfg = {
        "pageUrl": page_url,
        "waitMs": int(api.get("wait") or 5000),
        "url": api["url"],
        "method": api.get("method") or "GET",
        "headers": api.get("headers") or {},
    }
    code = """
    async ({ page }) => {
      const cfg = %s;
      await page.goto(cfg.pageUrl, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(cfg.waitMs);
      return await page.evaluate(async (c) => {
        const res = await fetch(c.url, {
          method: c.method || 'GET',
          headers: c.headers || {},
          credentials: 'include',
        });
        const text = await res.text();
        try { return { __ok: true, data: JSON.parse(text) }; }
        catch (e) { return { __ok: false, data: text }; }
      }, cfg);
    }
    """ % json.dumps(cfg)
    # v2 runs the function in-browser as an ES module; v1 wants CommonJS.
    resp = _post_browserless(f"{normalize_browserless(browserless_url)}/function",
                             {"code": "export default " + code},   # v2 (ESM)
                             {"function": "module.exports = " + code},  # v1
                             timeout + 10)
    if not resp.ok:
        _raise_browserless_error(resp)
    out = resp.json()
    if not out.get("__ok"):
        raise RuntimeError(
            f"API did not return JSON: {str(out.get('data'))[:200]}")
    return out.get("data")


class Fetcher:
    """Thin requests wrapper. Injectable: anything with a matching `get` works.

    An optional `proxy` URL (http(s)://… or socks5://…) routes outbound
    requests, e.g. for a feed behind a firewall.

    An optional `browserless` URL (e.g. ``http://localhost:3000``) renders the
    page in a headless Chrome via the browserless ``/content`` API instead of a
    plain HTTP GET — needed for JS-challenge-protected sites (WAF token/cookie
    challenges) that return nothing useful to `requests`. When not given, the
    ``RSSROB_BROWSERLESS`` environment variable is used as the global default
    (handy in Docker)."""

    def __init__(self, proxy: str = None, browserless: str = None):
        self.proxy = proxy
        self.browserless = normalize_browserless(
            browserless or os.environ.get("RSSROB_BROWSERLESS"))

    def get(self, url: str, timeout: int = 20, user_agent: str = "RSSRob/0.1") -> bytes:
        if self.browserless:
            return self._get_via_browserless(url, timeout, user_agent)
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": user_agent},
                            proxies=proxies)
        resp.raise_for_status()
        return resp.content

    def _get_via_browserless(self, url: str, timeout: int, user_agent: str) -> bytes:
        """Render ``url`` in the remote headless browser and return the HTML.

        Waits up to 3s after page load so WAF JS challenges (token/cookie
        generation) have time to finish; browserless applies the challenge's
        cookies to the final response."""
        v2_body = {
            "url": url,
            "userAgent": {"userAgent": user_agent},   # v2: object
            "waitForTimeout": 3000,
            "gotoOptions": {"waitUntil": "domcontentloaded"},
        }
        v1_body = {
            "url": url,
            "userAgent": user_agent,                  # v1: plain string
            "waitForTimeout": 3000,
            "gotoOptions": {"waitUntil": "domcontentloaded"},
        }
        resp = _post_browserless(f"{self.browserless}/content", v2_body, v1_body,
                                 timeout + 10)
        if not resp.ok:
            _raise_browserless_error(resp)
        return resp.content

    def fetch_page_api(self, page_url: str, api: dict, timeout: int = 30):
        """Fetch an API from inside a rendered page (WAF signature headers
        included automatically). Requires a browserless service; raises
        RuntimeError otherwise."""
        if not self.browserless:
            raise RuntimeError(
                "pageapi feed needs a browserless service — set the site's "
                "`browserless:` key or the RSSROB_BROWSERLESS env var")
        return fetch_in_browserless(self.browserless, page_url, api, timeout)
