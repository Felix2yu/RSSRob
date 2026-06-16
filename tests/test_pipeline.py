from rssrob.config import Site
from rssrob.pipeline import obtain_items, run_cycle
from rssrob.store import Store


def _html_site():
    return Site(
        name="ipp", url="http://www.ipp.cas.cn/", type="html",
        title="IPP", item=(
            "xpath://h2[normalize-space()='通知公告']"
            "/ancestor::div[contains(@class,'ipp2020-item')][1]//div[@class='bd']//ul/li"
        ),
        fields={"title": "xpath:.//a", "link": "xpath:.//a/@href",
                "date": "xpath:.//span"},
    )


def _rss_site():
    return Site(name="feedy", url="http://example.com/feed.xml", type="rss")


def test_obtain_items_html(fixtures, make_fetcher):
    html = (fixtures / "notices.html").read_bytes()
    fetcher = make_fetcher({"http://www.ipp.cas.cn/": html})
    items, title, desc = obtain_items(_html_site(), fetcher)
    assert len(items) == 2 and title is None and desc is None


def test_obtain_items_rss_exposes_channel_meta(fixtures, make_fetcher):
    xml = (fixtures / "sample_rss.xml").read_bytes()
    fetcher = make_fetcher({"http://example.com/feed.xml": xml})
    items, title, desc = obtain_items(_rss_site(), fetcher)
    assert len(items) == 2 and title == "Sample Feed" and desc == "A sample"


def test_run_cycle_writes_feed_and_returns_inserted(tmp_path, fixtures, make_fetcher):
    html = (fixtures / "notices.html").read_bytes()
    fetcher = make_fetcher({"http://www.ipp.cas.cn/": html})
    store = Store(str(tmp_path / "db.sqlite"))
    out = str(tmp_path / "feeds")
    inserted = run_cycle(_html_site(), store, fetcher, out, now=1000.0)
    assert inserted == 2
    assert (tmp_path / "feeds" / "ipp.xml").exists()


def test_run_cycle_rss_defaults_feed_title(tmp_path, fixtures, make_fetcher):
    xml = (fixtures / "sample_rss.xml").read_bytes()
    fetcher = make_fetcher({"http://example.com/feed.xml": xml})
    store = Store(str(tmp_path / "db.sqlite"))
    out = str(tmp_path / "feeds")
    run_cycle(_rss_site(), store, fetcher, out, now=1000.0)
    written = (tmp_path / "feeds" / "feedy.xml").read_text(encoding="utf-8")
    assert "Sample Feed" in written     # title inherited from source feed
