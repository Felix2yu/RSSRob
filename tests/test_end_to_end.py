import threading

import requests

from rssrob.config import Config, HttpConfig, Site
from rssrob.pipeline import run_cycle
from rssrob.server import make_server
from rssrob.store import Store

ITEM = (
    "xpath://h2[normalize-space()='通知公告']"
    "/ancestor::div[contains(@class,'ipp2020-item')][1]//div[@class='bd']//ul/li"
)


def _site():
    return Site(name="ipp", url="http://www.ipp.cas.cn/", type="html", title="IPP",
                item=ITEM, fields={"title": "xpath:.//a", "link": "xpath:.//a/@href"},
                max_items=50)


def test_dedup_history_and_serving(tmp_path, fixtures, make_fetcher):
    page1 = (fixtures / "notices.html").read_bytes()
    fetcher = make_fetcher({"http://www.ipp.cas.cn/": page1})
    store = Store(str(tmp_path / "db.sqlite"))
    out = str(tmp_path / "feeds")
    site = _site()

    # cycle 1: 2 new items
    assert run_cycle(site, store, fetcher, out, now=1000.0) == 2
    # cycle 2: same page -> 0 new (dedup), history retained
    assert run_cycle(site, store, fetcher, out, now=2000.0) == 0
    assert len(store.recent("ipp", 50)) == 2

    # a 3rd item appears only in a newer page; the old ones must persist (history)
    # (build the new <li> as text then encode — bytes literals can't hold non-ASCII)
    new_li = '<li><span>06-20</span><a href="./tzgg/3.html">通知三</a></li>'.encode("utf-8")
    page2 = page1.replace(
        b"</ul></div>\n</div>\n</body>",
        new_li + b"</ul></div>\n</div>\n</body>",
    )
    assert page2 != page1   # guard: the replacement anchor actually matched
    fetcher.mapping["http://www.ipp.cas.cn/"] = page2
    assert run_cycle(site, store, fetcher, out, now=3000.0) == 1
    assert len(store.recent("ipp", 50)) == 3   # old items retained, new one added

    # serve the generated feed and confirm it is valid RSS with items
    srv = make_server(out, "127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        r = requests.get(f"http://127.0.0.1:{port}/feeds/ipp.xml")
        assert r.status_code == 200
        assert b"<rss" in r.content
        assert r.content.count(b"<item>") == 3
    finally:
        srv.shutdown()
        srv.server_close()
