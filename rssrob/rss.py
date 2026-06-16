from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin

import feedparser

from .models import Item


@dataclass
class ParsedFeed:
    items: List[Item]
    title: Optional[str] = None
    description: Optional[str] = None


def parse_feed(content, base_url: str) -> ParsedFeed:
    parsed = feedparser.parse(content)
    feed = parsed.feed
    items = []
    for entry in parsed.entries:
        link = entry.get("link")
        if link:
            link = urljoin(base_url, link)
        item_id = entry.get("id") or link
        items.append(Item(
            id=item_id,
            title=entry.get("title"),
            link=link,
            summary=entry.get("summary"),
            date=entry.get("published") or entry.get("updated"),
        ))
    return ParsedFeed(
        items=items,
        title=feed.get("title"),
        description=feed.get("description") or feed.get("subtitle"),
    )
