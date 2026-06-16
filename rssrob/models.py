from dataclasses import dataclass
from typing import Optional


@dataclass
class Item:
    """Raw item produced by extraction (html) or feed parsing (rss)."""
    id: str
    title: Optional[str] = None
    link: Optional[str] = None
    summary: Optional[str] = None
    date: Optional[str] = None  # raw date string from source; parsed in the store


@dataclass
class StoredItem:
    """A row read back from the SQLite store."""
    id: str
    title: Optional[str]
    link: Optional[str]
    summary: Optional[str]
    published: Optional[float]  # epoch seconds, or None
    first_seen: float
