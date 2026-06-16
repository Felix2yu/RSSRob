import os
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


class FeedHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, **kwargs)

    def do_GET(self):
        path = unquote(self.path.split("?", 1)[0])
        if path in ("/", "/index.html"):
            return self._send_index()
        if path.startswith("/feeds/"):
            return self._send_feed(path[len("/feeds/"):])
        self.send_error(404)

    def _send_feed(self, name):
        if "/" in name or "\\" in name or not name.endswith(".xml"):
            return self.send_error(404)
        full = os.path.join(self.directory, name)
        if not os.path.isfile(full):
            return self.send_error(404)
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_index(self):
        feeds = (sorted(f for f in os.listdir(self.directory) if f.endswith(".xml"))
                 if os.path.isdir(self.directory) else [])
        links = "".join(f'<li><a href="/feeds/{f}">{f}</a></li>' for f in feeds)
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>RSSRob</title></head><body><h1>RSSRob feeds</h1>"
            f"<ul>{links}</ul></body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep the console quiet


def make_server(output_dir, host, port) -> ThreadingHTTPServer:
    os.makedirs(output_dir, exist_ok=True)
    handler = partial(FeedHandler, directory=output_dir)
    return ThreadingHTTPServer((host, port), handler)
