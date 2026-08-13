from dataclasses import dataclass
import re
from typing import Optional
from urllib.parse import urljoin

import lxml.html
from lxml.cssselect import CSSSelector
from lxml.etree import XPath

from .models import Item


# --- JSON path extraction (pageapi feeds) ------------------------------------
#
# A minimal JSONPath subset: `$.a.b[0].c` (dot-separated keys + [index]).
# Field specs may also be templates embedding paths, e.g.
#   "https://site/h5/#/pages-order/projectDetail/index?projectId={$.projectToken}"
# which interpolates each item's own value.

_JSON_SEG = re.compile(r"^([^\[\]]*)(?:\[(\d+)\])?$")
_TEMPLATE_RE = re.compile(r"\{(\$[^}]*)\}")


def validate_json_selector(s: str) -> None:
    """Raise ValueError unless ``s`` is a syntactically valid JSON path."""
    if not isinstance(s, str) or not s.startswith("$"):
        raise ValueError(f"invalid JSON path {s!r} (must start with '$')")
    for raw in s[1:].split("."):
        seg = raw.strip()
        if seg and not _JSON_SEG.match(seg):
            raise ValueError(f"invalid JSON path {s!r}")


def json_get(doc, path):
    """Resolve a ``$.a.b[0].c`` path against a parsed JSON document. Returns
    None when any key is missing or an index is out of range."""
    if not isinstance(path, str) or not path.startswith("$"):
        raise ValueError(f"invalid JSON path {path!r} (must start with '$')")
    cur = doc
    for raw in path[1:].split("."):
        seg = raw.strip()
        if not seg:
            continue
        m = _JSON_SEG.match(seg)
        if not m:
            raise ValueError(f"invalid JSON path segment {seg!r} in {path!r}")
        name, idx = m.groups()
        if name:
            if not isinstance(cur, dict) or name not in cur:
                return None
            cur = cur[name]
        if idx is not None:
            if not isinstance(cur, list) or int(idx) >= len(cur):
                return None
            cur = cur[int(idx)]
    return cur


def render_json_template(template: str, row) -> str:
    """Interpolate every ``{$.path}`` placeholder with the item's own value."""

    def _repl(m):
        v = json_get(row, m.group(1))
        return "" if v is None else str(v)

    return _TEMPLATE_RE.sub(_repl, template)


def _clean(v):
    """Normalize a raw field value: None and JS-ish 'null'/'undefined'
    literals (dirty backends stringify nulls) become None."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in ("null", "undefined", "none"):
        return None
    return v


def extract_json_items(doc, item_path: str, fields: dict) -> list:
    """Extract items from a parsed JSON document.

    ``item_path`` resolves to the list of entries; each field spec is either a
    JSON path (``$.projectName``) or a template embedding ``{$.path}``."""
    rows = json_get(doc, item_path)
    if not isinstance(rows, list):
        raise ValueError(f"item path {item_path!r} did not resolve to a list")
    items = []
    for row in rows:
        values = {}
        for name, spec in fields.items():
            if spec is None:
                values[name] = None
            elif isinstance(spec, str) and "{$" in spec:
                values[name] = render_json_template(spec, row)
            else:
                v = _clean(json_get(row, spec))
                values[name] = None if v is None else str(v)
        link = values.get("link")
        item_id = values.get("id") or link
        items.append(Item(
            id=item_id,
            title=values.get("title"),
            link=link,
            summary=values.get("summary"),
            date=values.get("date"),
            category=values.get("category"),
        ))
    return items


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
