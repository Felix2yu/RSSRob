"""Standalone preview of RSSRob's extraction for the IPP 通知公告 block.

Reuses the package's real machinery — ``rssrob.extract`` to select the list
items and ``rssrob.article`` to follow ("click") each link for the full <h1>
title plus a short description — then writes a static ``preview.html``.

Fetches live and falls back to saved local copies (``ipp_page.html`` for the
homepage, ``site.html`` for the one saved article) so it also works offline.

    $CLAUDE_CODE_PYTHON tools/select_preview.py
"""

import html as _html
import os
import re
import sys
from pathlib import Path

# This file lives in tools/; put the repo root on sys.path for `import rssrob`
# and anchor sample/output paths to the repo root (CWD-independent).
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import requests

from rssrob.article import fetch_article
from rssrob.extract import extract_items

BASE_URL = "http://www.ipp.cas.cn/"
OUTPUT = str(REPO_ROOT / "preview.html")
SECTION = "通知公告"
DESC_LEN = 160

# Selector config (exactly what a RSSRob `html` site would carry).
ITEM = (
    "xpath://h2[normalize-space()='通知公告']"
    "/ancestor::div[contains(@class,'ipp2020-item')][1]//div[@class='bd']//ul/li"
)
FIELDS = {
    "title": "xpath:.//a",          # element text (may be truncated by the source)
    "link": "xpath:.//a/@href",     # native xpath attribute
    "date": "xpath:.//span",        # element text, e.g. "06-15"
}

# Live fetch falls back to these saved copies (keyed by url) on a network error.
FALLBACK_FILES = {
    BASE_URL: str(REPO_ROOT / "samples" / "ipp_page.html"),
    "http://www.ipp.cas.cn/tzgg/tz_zhb/202606/t20260615_841876.html":
        str(REPO_ROOT / "samples" / "site.html"),
}


def fetch(url):
    """Return (content_bytes, source) where source is 'live' or 'saved'."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "RSSRob/0.1"})
        r.raise_for_status()
        return r.content, "live"
    except Exception:
        path = FALLBACK_FILES.get(url)
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                return f.read(), "saved"
        raise


class FallbackFetcher:
    """Has the rssrob fetcher `get` shape; backed by fetch() above."""

    def get(self, url, timeout=20, user_agent="RSSRob/0.1"):
        return fetch(url)[0]


def shorten(text, n=DESC_LEN):
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n].rstrip() + "…"


def main():
    content, source = fetch(BASE_URL)
    items = extract_items(content.decode("utf-8", errors="replace"),
                          BASE_URL, ITEM, FIELDS)

    fetcher = FallbackFetcher()
    rows = []
    for it in items:
        full_title, desc = it.title, None
        if it.link:
            try:                              # follow the link for full title + body
                art = fetch_article(it.link, fetcher)
                full_title = art.title or it.title
                desc = shorten(art.content_text)
            except Exception:
                pass
        rows.append({"title": full_title, "link": it.link,
                     "date": it.date, "desc": desc})

    print(f"Section: {SECTION}  (source: {source})")
    print(f"{len(rows)} items:\n")
    for i, r in enumerate(rows, 1):
        print(f"{i:>2}. [{r['date']}] {r['title']}")
        if r["desc"]:
            print(f"     {r['desc']}")
        print(f"     {r['link']}")

    write_preview(rows, source)
    print(f"\nWrote {OUTPUT}")


def write_preview(rows, source):
    def esc(x):
        return _html.escape(x or "")

    badge = ('<span class="badge live">● live</span>' if source == "live"
             else '<span class="badge saved">● saved copy</span>')

    body_rows = "\n".join(
        f"""        <tr>
          <td class="n">{i}</td>
          <td class="d">{esc(r['date'])}</td>
          <td class="t">
            <a href="{esc(r['link'])}" target="_blank">{esc(r['title'])}</a>
            {f'<div class="summary">{esc(r["desc"])}</div>' if r['desc'] else ''}
          </td>
        </tr>"""
        for i, r in enumerate(rows, 1)
    )
    doc = f"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>RSSRob preview — {esc(SECTION)}</title>
<style>
  body {{ font: 15px/1.55 -apple-system, "Segoe UI", Roboto, "PingFang SC",
          "Microsoft YaHei", sans-serif; margin: 2rem auto; max-width: 860px; color: #1f2328; }}
  h1 {{ font-size: 1.35rem; }}
  .badge {{ display:inline-block; padding:.12rem .55rem; border-radius:999px;
            font-size:.75rem; font-weight:600; vertical-align:middle; }}
  .badge.live {{ background:#dafbe1; color:#1a7f37; }}
  .badge.saved {{ background:#fff8c5; color:#9a6700; }}
  .meta {{ background:#f6f8fa; border:1px solid #d0d7de; border-radius:10px; padding:.8rem 1rem; margin:1rem 0; font-size:.9rem; }}
  .meta div + div {{ margin-top:.3rem; }}
  .meta code {{ background:#eaeef2; padding:.08rem .35rem; border-radius:5px; font-size:.82rem; word-break:break-all; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .55rem .6rem; border-bottom: 1px solid #eaeef2; vertical-align: top; }}
  th {{ border-bottom: 2px solid #d0d7de; font-size:.76rem; color:#656d76; text-transform:uppercase; letter-spacing:.04em; }}
  td.n {{ color:#9aa3ad; width:2.2rem; }}
  td.d {{ color:#1a7f37; white-space:nowrap; width:4.5rem; font-variant-numeric: tabular-nums; font-size:.85rem; }}
  td.t a {{ color:#0353a4; text-decoration:none; }}
  td.t a:hover {{ text-decoration:underline; }}
  td.t .summary {{ color:#656d76; font-size:.85rem; margin-top:.2rem; }}
  .count {{ color:#656d76; }}
</style>
</head>
<body>
  <h1>RSSRob preview — {esc(SECTION)} {badge}</h1>
  <div class="meta">
    <div>Source: <code>{esc(BASE_URL)}</code></div>
    <div>Item selector: <code>{esc(ITEM)}</code></div>
    <div>Fields: title <code>{esc(FIELDS['title'])}</code> · link <code>{esc(FIELDS['link'])}</code> · date <code>{esc(FIELDS['date'])}</code></div>
    <div>Titles &amp; descriptions are pulled from each linked article (rssrob.article).</div>
  </div>
  <p class="count">{len(rows)} items selected</p>
  <table>
    <thead><tr><th>#</th><th>Date</th><th>Title &amp; description</th></tr></thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</body>
</html>
"""
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    main()
