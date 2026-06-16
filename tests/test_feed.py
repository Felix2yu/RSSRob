from lxml import etree

from rssrob.config import Site
from rssrob.feed import build_feed, write_feed
from rssrob.models import StoredItem


def _site():
    return Site(name="blog", url="http://example.com/", type="html",
                title="Test Feed", description="desc",
                item="css:li", fields={"title": "css:a"})


def _items():
    return [
        StoredItem(id="id-1", title="First", link="http://example.com/1",
                   summary="body 1", published=1750000000.0, first_seen=1.0),
        StoredItem(id="id-2", title=None, link=None,
                   summary=None, published=None, first_seen=2.0),
    ]


def test_build_feed_is_valid_rss():
    xml = build_feed(_site(), _items())
    root = etree.fromstring(xml)
    chan = root.find("channel")
    assert chan.findtext("title") == "Test Feed"
    assert chan.findtext("link") == "http://example.com/"
    assert chan.findtext("description") == "desc"
    items = chan.findall("item")
    assert len(items) == 2
    assert items[0].findtext("guid") == "id-1"
    assert items[0].find("pubDate") is not None        # has a date
    assert items[1].find("pubDate") is not None        # falls back to first_seen


def test_write_feed_creates_file(tmp_path):
    xml = build_feed(_site(), _items())
    path = write_feed(str(tmp_path / "feeds"), "blog", xml)
    assert path.endswith("blog.xml")
    data = (tmp_path / "feeds" / "blog.xml").read_bytes()
    assert b"<rss" in data
