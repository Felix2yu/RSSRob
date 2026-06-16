import time

from rssrob.config import Config, HttpConfig, Site
from rssrob.scheduler import Scheduler
from rssrob.store import Store


def _html_site():
    return Site(
        name="ipp", url="http://www.ipp.cas.cn/", type="html", title="IPP",
        item=(
            "xpath://h2[normalize-space()='通知公告']"
            "/ancestor::div[contains(@class,'ipp2020-item')][1]//div[@class='bd']//ul/li"
        ),
        fields={"title": "xpath:.//a", "link": "xpath:.//a/@href"},
        interval=3600,
    )


def _config(tmp_path, site):
    return Config(output_dir=str(tmp_path / "feeds"),
                  state_db=str(tmp_path / "db.sqlite"),
                  http=HttpConfig(), sites=[site])


def test_run_site_scrapes_and_writes(tmp_path, fixtures, make_fetcher):
    html = (fixtures / "notices.html").read_bytes()
    fetcher = make_fetcher({"http://www.ipp.cas.cn/": html})
    site = _html_site()
    store = Store(str(tmp_path / "db.sqlite"))
    sched = Scheduler(_config(tmp_path, site), store, fetcher)
    sched._run_site(site, now=1000.0)
    assert (tmp_path / "feeds" / "ipp.xml").exists()
    assert len(store.recent("ipp", 10)) == 2


def test_run_site_isolates_errors(tmp_path):
    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("network down")

    site = _html_site()
    store = Store(str(tmp_path / "db.sqlite"))
    sched = Scheduler(_config(tmp_path, site), store, Boom())
    # must not raise — the error is caught and logged
    sched._run_site(site, now=1000.0)
    assert store.recent("ipp", 10) == []


def test_start_stop_is_clean(tmp_path, fixtures, make_fetcher):
    html = (fixtures / "notices.html").read_bytes()
    fetcher = make_fetcher({"http://www.ipp.cas.cn/": html})
    site = _html_site()
    store = Store(str(tmp_path / "db.sqlite"))
    sched = Scheduler(_config(tmp_path, site), store, fetcher)
    sched.start()
    time.sleep(0.2)        # first cycle runs immediately (next_run starts at 0)
    sched.stop()
    assert (tmp_path / "feeds" / "ipp.xml").exists()
