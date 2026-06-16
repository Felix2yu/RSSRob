from rssrob.cli import main


HTML_CFG = """
output_dir: {out}
state_db: {db}
sites:
  - name: ipp
    type: html
    url: http://www.ipp.cas.cn/
    title: IPP
    item: "xpath://h2[normalize-space()='通知公告']/ancestor::div[contains(@class,'ipp2020-item')][1]//div[@class='bd']//ul/li"
    fields:
      title: "xpath:.//a"
      link: "xpath:.//a/@href"
"""


def _cfg(tmp_path, fixtures):
    text = HTML_CFG.format(out=tmp_path / "feeds", db=tmp_path / "db.sqlite")
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_run_once_prints_items(tmp_path, fixtures, make_fetcher, monkeypatch, capsys):
    html = (fixtures / "notices.html").read_bytes()
    monkeypatch.setattr("rssrob.cli.Fetcher",
                        lambda: make_fetcher({"http://www.ipp.cas.cn/": html}))
    rc = main(["--config", _cfg(tmp_path, fixtures), "run-once", "ipp"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "通知一" in out
    assert not (tmp_path / "feeds" / "ipp.xml").exists()   # no --write


def test_run_once_write_persists(tmp_path, fixtures, make_fetcher, monkeypatch):
    html = (fixtures / "notices.html").read_bytes()
    monkeypatch.setattr("rssrob.cli.Fetcher",
                        lambda: make_fetcher({"http://www.ipp.cas.cn/": html}))
    rc = main(["--config", _cfg(tmp_path, fixtures), "run-once", "ipp", "--write"])
    assert rc == 0
    assert (tmp_path / "feeds" / "ipp.xml").exists()


def test_unknown_site_returns_2(tmp_path, fixtures, monkeypatch):
    rc = main(["--config", _cfg(tmp_path, fixtures), "run-once", "nope"])
    assert rc == 2


def test_bad_config_returns_2(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text("sites:\n  - {name: x}\n", encoding="utf-8")  # missing url
    rc = main(["--config", str(bad), "run-once", "x"])
    assert rc == 2
