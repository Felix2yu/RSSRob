from rssrob.models import Item
from rssrob.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "test.db"))


def test_insert_new_dedups(tmp_path):
    s = _store(tmp_path)
    items = [Item(id="a", title="A"), Item(id="b", title="B")]
    assert s.insert_new("feed1", items, now=100.0) == 2
    # re-inserting the same ids inserts nothing
    assert s.insert_new("feed1", items, now=200.0) == 0
    assert len(s.recent("feed1", 10)) == 2


def test_recent_orders_by_published_then_first_seen(tmp_path):
    s = _store(tmp_path)
    s.insert_new("f", [
        Item(id="old", title="old", date="Sun, 08 Jun 2026 10:00:00 GMT"),
        Item(id="new", title="new", date="Mon, 15 Jun 2026 10:00:00 GMT"),
    ], now=100.0)
    rows = s.recent("f", 10)
    assert [r.id for r in rows] == ["new", "old"]   # newest published first
    assert rows[0].published is not None


def test_undated_item_uses_first_seen_and_is_kept(tmp_path):
    s = _store(tmp_path)
    s.insert_new("f", [Item(id="x", title="x", date=None)], now=123.0)
    rows = s.recent("f", 10)
    assert rows[0].published is None
    assert rows[0].first_seen == 123.0


def test_max_items_window(tmp_path):
    s = _store(tmp_path)
    s.insert_new("f", [Item(id=str(i), title=str(i)) for i in range(5)], now=1.0)
    assert len(s.recent("f", 3)) == 3
