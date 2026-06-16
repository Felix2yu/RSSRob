import time
from dataclasses import replace
from typing import Optional, Tuple

from . import extract, rss
from .config import Site
from .feed import build_feed, write_feed
from .store import Store


def obtain_items(site: Site, fetcher) -> Tuple[list, Optional[str], Optional[str]]:
    """Return (items, feed_title, feed_description). Meta is None for html."""
    content = fetcher.get(site.url, site.timeout, site.user_agent)
    if site.type == "rss":
        parsed = rss.parse_feed(content, site.url)
        return parsed.items, parsed.title, parsed.description
    html = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    items = extract.extract_items(html, site.url, site.item, site.fields)
    return items, None, None


def run_cycle(site: Site, store: Store, fetcher, output_dir: str,
              now: Optional[float] = None) -> int:
    if now is None:
        now = time.time()
    items, feed_title, feed_desc = obtain_items(site, fetcher)
    inserted = store.insert_new(site.name, items, now)

    effective = site
    if site.type == "rss" and (site.title is None or site.description is None):
        effective = replace(
            site,
            title=site.title or feed_title,
            description=site.description or feed_desc,
        )

    recent = store.recent(site.name, site.max_items)
    xml = build_feed(effective, recent)
    write_feed(output_dir, site.name, xml)
    return inserted
