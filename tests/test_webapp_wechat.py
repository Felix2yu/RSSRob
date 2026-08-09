"""Preview-page resilience: when mp.weixin.qq.com rate-limits (freq control) and
the session dies, the page must fall back to the last cached feed instead of
showing an all-or-nothing error screen."""

import importlib.util
import sys
from pathlib import Path

from rssrob.models import Item
from rssrob.store import Store
from rssrob.wechat import WeChatAuthError, WeChatRateLimited


def _load_webapp():
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("webapp", root / "rssrob" / "webapp.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["webapp"] = m
    spec.loader.exec_module(m)
    return m


WECHAT_FEED = """\
name: sh
type: wechat
account_id: MzAxNDU=
account_name: 上海昆剧团
max_items: 30
"""


def _app(wa, tmp_path, db_seed=None):
    """Config folder + optional seeded item rows; returns (test_client, db_path)."""
    d = tmp_path / "configs"
    d.mkdir()
    (tmp_path / "var").mkdir(exist_ok=True)
    state_db = str(tmp_path / "var" / "rssrob.db")
    (d / "00-settings.yaml").write_text(
        f"output_dir: {tmp_path}/var/feeds\nstate_db: {state_db}\n", encoding="utf-8")
    (d / "sh.yaml").write_text(WECHAT_FEED, encoding="utf-8")
    if db_seed:
        store = Store(state_db)
        store.insert_new(
            "sh",
            [Item(id=f"https://mp.weixin.qq.com/s/{i}", title=f"缓存文章{i}",
                  summary="缓存摘要", link=f"https://mp.weixin.qq.com/s/{i}")
             for i in db_seed],
            now=100.0)
        store.close()
    wa.CONFIG_OVERRIDE = str(d)
    wa.REPO_ROOT = tmp_path
    return wa.app.test_client(), state_db


def _rate_limited_obtain(*a, **k):
    raise WeChatRateLimited("mp.weixin.qq.com freq control: ret=200013")


def test_wechat_preview_uses_cache_when_rate_limited(tmp_path, monkeypatch):
    wa = _load_webapp()
    client, _ = _app(wa, tmp_path, db_seed=["1", "2"])
    monkeypatch.setattr(wa, "obtain_items", _rate_limited_obtain)
    r = client.get("/", query_string={"site": "sh"})
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "缓存文章1" in html and "缓存文章2" in html
    assert "缓存副本" in html                       # cached badge/none banner
    assert "接口暂时不可用" in html


def test_wechat_no_cache_shows_guidance(tmp_path, monkeypatch):
    wa = _load_webapp()
    client, _ = _app(wa, tmp_path)
    monkeypatch.setattr(wa, "obtain_items", _rate_limited_obtain)
    r = client.get("/", query_string={"site": "sh"})
    assert r.status_code == 502
    html = r.get_data(as_text=True)
    assert "频率限制" in html or "freq control" in html


def test_wechat_auth_error_without_cache_guides_login(tmp_path, monkeypatch):
    wa = _load_webapp()
    client, _ = _app(wa, tmp_path)

    def _auth(*a, **k):
        raise WeChatAuthError("mp.weixin.qq.com session invalid: ret=200003")
    monkeypatch.setattr(wa, "obtain_items", _auth)
    r = client.get("/", query_string={"site": "sh"})
    assert r.status_code == 502
    html = r.get_data(as_text=True)
    assert "cookie+token" in html