from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import lxml.html
from lxml.cssselect import CSSSelector
from lxml.etree import XPath

from .models import Item


@dataclass
class Selector:
    engine: str            # "css" | "xpath"
    expr: str
    attr: Optional[str] = None


def parse_selector(s: str) -> Selector:
    """Parse `[css:|xpath:] <expr> [@attr]`. Default engine is css."""
    engine = "css"
    if s.startswith("css:"):
        s = s[4:]
    elif s.startswith("xpath:"):
        engine, s = "xpath", s[6:]
    attr = None
    # `@attr` suffix applies to CSS only; XPath uses its native `/@attr` axis.
    if engine == "css" and "@" in s:
        s, attr = s.rsplit("@", 1)
    return Selector(engine=engine, expr=s.strip(), attr=attr)


def validate_selector(s: str) -> None:
    """Raise ValueError if the selector cannot be compiled."""
    sel = parse_selector(s)
    try:
        if sel.engine == "css":
            CSSSelector(sel.expr)
        else:
            XPath(sel.expr)
    except Exception as e:  # lxml raises engine-specific errors
        raise ValueError(f"invalid selector {s!r}: {e}") from e


def _select_nodes(node, sel: Selector):
    if sel.engine == "css":
        return CSSSelector(sel.expr)(node)
    return node.xpath(sel.expr)


def _select_value(node, sel: Selector) -> Optional[str]:
    results = _select_nodes(node, sel)
    if not results:
        return None
    first = results[0]
    if isinstance(first, str):           # xpath attribute or text() result
        return first.strip() or None
    if sel.attr:                         # css @attr
        val = first.get(sel.attr)
        return val.strip() if val else None
    text = first.text_content()
    return text.strip() if text else None


def extract_items(html, base_url, item_selector, fields) -> list:
    tree = lxml.html.fromstring(html)
    item_sel = parse_selector(item_selector)
    field_sels = {name: parse_selector(s) for name, s in fields.items()}
    items = []
    for node in _select_nodes(tree, item_sel):
        values = {name: _select_value(node, s) for name, s in field_sels.items()}
        link = values.get("link")
        if link:
            link = urljoin(base_url, link)
        item_id = values.get("id") or link
        items.append(Item(
            id=item_id,
            title=values.get("title"),
            link=link,
            summary=values.get("summary"),
            date=values.get("date"),
        ))
    return items
