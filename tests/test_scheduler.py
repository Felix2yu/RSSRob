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


def _wechat_site():
    return Site(name="oa", url=None, type="wechat", account_id="x",
                account_name="某号", interval=7200)


def test_scheduler_builds_wechat_client_lazily(tmp_path, monkeypatch):
    import rssrob.scheduler as sch_mod
    site = _wechat_site()
    sentinel = object()
    monkeypatch.setattr(sch_mod, "build_wechat_client", lambda: sentinel)
    captured = {}
    monkeypatch.setattr(sch_mod, "run_cycle",
        lambda s, st, f, o, now, wechat_client=None, twitter_client=None:
            captured.update(wc=wechat_client) or 0)
    sched = Scheduler(_config(tmp_path, site), store=object(), fetcher=object())
    sched._run_site(site, now=0.0)
    assert captured["wc"] is sentinel


def test_scheduler_isolates_auth_error(tmp_path, monkeypatch):
    import rssrob.scheduler as sch_mod
    from rssrob.wechat import WeChatAuthError
    site = _wechat_site()
    monkeypatch.setattr(sch_mod, "build_wechat_client", lambda: object())

    def boom(*a, **k):
        raise WeChatAuthError("login expired")
    monkeypatch.setattr(sch_mod, "run_cycle", boom)
    sched = Scheduler(_config(tmp_path, site), store=object(), fetcher=object())
    sched._run_site(site, now=0.0)   # must not raise


def test_scheduler_backs_off_on_rate_limit(tmp_path, monkeypatch):
    import rssrob.scheduler as sch_mod
    from rssrob.wechat import WeChatRateLimited
    site = _wechat_site()
    monkeypatch.setattr(sch_mod, "build_wechat_client", lambda: object())

    def boom(*a, **k):
        raise WeChatRateLimited("freq control")
    monkeypatch.setattr(sch_mod, "run_cycle", boom)
    sched = Scheduler(_config(tmp_path, site), store=object(), fetcher=object())
    sched._run_site(site, now=1000.0)
    assert sched._backoff.get("oa", 0) >= 1000.0 + 1800   # pushed out


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


def test_build_twitter_client_uses_env_proxy(monkeypatch, tmp_path):
    import json
    from rssrob import scheduler
    cred = tmp_path / "tw.json"
    cred.write_text(json.dumps({"auth_token": "a", "csrf_token": "c",
                                "updated_at": 1.0, "proxy": None}), encoding="utf-8")
    monkeypatch.setenv("RSSROB_TWITTER_CREDENTIAL", str(cred))
    monkeypatch.setattr(scheduler, "TWITTER_CRED_PATH", str(cred))
    monkeypatch.setenv("RSSROB_PROXY", "7890")
    client = scheduler.build_twitter_client()
    assert client.transport.proxy == "http://127.0.0.1:7890"


def test_scheduler_passes_twitter_client(monkeypatch, tmp_path):
    from rssrob.config import Config, HttpConfig, Site
    from rssrob.scheduler import Scheduler

    captured = {}
    def fake_run_cycle(site, store, fetcher, output_dir, now, wechat_client=None,
                       twitter_client=None):
        captured["twitter_client"] = twitter_client
        return 0
    monkeypatch.setattr("rssrob.scheduler.run_cycle", fake_run_cycle)

    cfg = Config(output_dir=str(tmp_path), state_db=":memory:", http=HttpConfig(),
                 sites=[Site(name="elon", type="twitter", username="elonmusk")])
    sch = Scheduler(cfg, store=None, fetcher=object())
    sentinel = object()
    monkeypatch.setattr(sch, "_twitter", lambda: sentinel)
    sch._run_site(cfg.sites[0], now=0.0)
    assert captured["twitter_client"] is sentinel


def test_scheduler_uses_per_site_proxy_fetcher(monkeypatch, tmp_path):
    from rssrob.config import Config, HttpConfig, Site
    from rssrob.scheduler import Scheduler

    seen = {}
    def fake_run_cycle(site, store, fetcher, output_dir, now, wechat_client=None,
                       twitter_client=None):
        seen["proxy"] = getattr(fetcher, "proxy", "MISSING")
        return 0
    monkeypatch.setattr("rssrob.scheduler.run_cycle", fake_run_cycle)

    cfg = Config(output_dir=str(tmp_path), state_db=":memory:", http=HttpConfig(),
                 sites=[Site(name="s", type="rss", url="http://x", proxy="http://127.0.0.1:9")])
    sch = Scheduler(cfg, store=None, fetcher=object())
    sch._run_site(cfg.sites[0], now=0.0)
    assert seen["proxy"] == "http://127.0.0.1:9"


# --- credential hot-refresh -------------------------------------------------

def _qfile(path, cookie, token, t):
    import json
    import os
    path.write_text(json.dumps({"cookie": cookie, "token": token,
                                "updated_at": t}), encoding="utf-8")
    os.utime(path, (t, t))
    return path


def test_scheduler_refreshes_wechat_client_after_credential_change(tmp_path, monkeypatch):
    import os
    import rssrob.scheduler as sch_mod
    site = _wechat_site()
    cred = _qfile(tmp_path / "wc.json", cookie="a", token="1", t=100.0)
    monkeypatch.setattr(sch_mod, "DEFAULT_PATH", str(cred))
    made = []
    monkeypatch.setattr(sch_mod, "build_wechat_client", lambda: made.append(object()) or made[-1])

    sched = Scheduler(_config(tmp_path, site), store=object(), fetcher=object())
    first = sched._wechat()                 # lazy build + remember mtime
    assert sched._wechat() is first         # unchanged credential => same client
    assert len(made) == 1

    os.utime(cred, (200.0, 200.0))          # simulate re-login rewriting the file
    second = sched._wechat()
    assert second is not first
    assert len(made) == 2


def test_credential_refresh_clears_rate_limit_backoff(tmp_path, monkeypatch):
    import os
    import rssrob.scheduler as sch_mod
    from rssrob.wechat import WeChatRateLimited
    site = _wechat_site()
    cred = _qfile(tmp_path / "credo.json", cookie="a", token="1", t=100.0)
    monkeypatch.setattr(sch_mod, "DEFAULT_PATH", str(cred))
    monkeypatch.setattr(sch_mod, "build_wechat_client", lambda: object())

    def boom(*a, **k):
        raise WeChatRateLimited("freq control")
    monkeypatch.setattr(sch_mod, "run_cycle", boom)

    sched = Scheduler(_config(tmp_path, site), store=object(), fetcher=object())
    sched._run_site(site, now=1000.0)
    assert sched._backoff.get("oa", 0) >= 1000.0 + 1800   # pushed out

    # user re-pastes the token -> scheduler loop notices the new mtime and
    # clears the backoff so the fresh credential is used right away.
    os.utime(cred, (200.0, 200.0))
    sched._refresh_wechat_credential()
    assert "oa" not in sched._backoff


def test_scheduler_reloads_config_on_change(tmp_path, monkeypatch):
    import os
    import yaml
    from rssrob.scheduler import Scheduler

    cfg_path = tmp_path / "sites.yaml"
    cfg_path.write_text(yaml.safe_dump({"sites": [{"name": "a", "type": "html",
                                                    "url": "http://a", "item": "x",
                                                    "fields": {"title": "t"}}]}),
                        encoding="utf-8")
    site = _html_site()
    sched = Scheduler(_config(tmp_path, site), store=object(), fetcher=object(),
                      config_path=str(cfg_path))
    assert [s.name for s in sched.config.sites] == ["ipp"]

    # a new site appears on disk -> picked up without restart
    cfg_path.write_text(yaml.safe_dump({"sites": [
        {"name": "a", "type": "html", "url": "http://a",
         "item": "x", "fields": {"title": "t"}},
        {"name": "b", "type": "html", "url": "http://b",
         "item": "y", "fields": {"title": "u"}}]}), encoding="utf-8")
    os.utime(cfg_path, (300.0, 300.0))
    sched._reload_config()
    assert [s.name for s in sched.config.sites] == ["a", "b"]
    assert "b" in sched._next_run
