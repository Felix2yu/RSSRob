import threading

import requests

from rssrob.server import make_server


def test_server_serves_feed_index_and_404(tmp_path):
    out = tmp_path / "feeds"
    out.mkdir()
    (out / "blog.xml").write_bytes(b"<rss>hi</rss>")

    srv = make_server(str(out), "127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        r = requests.get(f"http://127.0.0.1:{port}/feeds/blog.xml")
        assert r.status_code == 200
        assert b"<rss>hi</rss>" in r.content
        assert "rss+xml" in r.headers["Content-Type"]

        idx = requests.get(f"http://127.0.0.1:{port}/")
        assert idx.status_code == 200
        assert "blog.xml" in idx.text

        missing = requests.get(f"http://127.0.0.1:{port}/feeds/nope.xml")
        assert missing.status_code == 404
    finally:
        srv.shutdown()
        srv.server_close()
