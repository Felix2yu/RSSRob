from rssrob.models import Item, StoredItem


def test_item_defaults():
    it = Item(id="x")
    assert it.id == "x"
    assert it.title is None and it.link is None and it.summary is None and it.date is None


def test_stored_item_fields():
    s = StoredItem(id="x", title="T", link="L", summary="S",
                   published=1.0, first_seen=2.0)
    assert s.published == 1.0 and s.first_seen == 2.0
