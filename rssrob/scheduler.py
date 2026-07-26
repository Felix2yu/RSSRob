import json
import logging
import os
import threading
import time

from .config import normalize_proxy
from .notify import send_notification
from .subscribers import Subscribers
from .fetch import Fetcher
from .pipeline import run_cycle
from .twitter import (GraphQlTransport, TwitterAuthError, TwitterClient,
                      TwitterRateLimited)
from .twitter_credential import DEFAULT_PATH as TWITTER_CRED_PATH
from .twitter_credential import load as load_twitter_credential
from .wechat import (MpPlatformTransport, WeChatAuthError, WeChatClient,
                     WeChatRateLimited)
from .wechat_credential import DEFAULT_PATH, load

log = logging.getLogger("rssrob.scheduler")

_RATE_LIMIT_BACKOFF = 1800   # extra seconds to wait after mp.weixin freq control
_AUTH_NOTIFY_COOLDOWN = 86400  # seconds between auth-expiry notifications (24 h)
_AUTH_NOTIFY_STATE_PATH = os.path.join("var", "auth_notify_state.json")


class _AuthNotifyTracker:
    """Rate-limit auth-expiry notifications to once per cooldown period.

    Uses a JSON file on disk so that multiple worker processes (e.g. gunicorn)
    share the same cooldown state."""

    def __init__(self, cooldown: int = _AUTH_NOTIFY_COOLDOWN,
                 path: str = _AUTH_NOTIFY_STATE_PATH):
        self._cooldown = cooldown
        self._path = path

    def _load(self) -> dict[str, float]:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:
                return json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict[str, float]) -> None:
        directory = os.path.dirname(self._path) or "."
        os.makedirs(directory, exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self._path)

    def should_send(self, service: str, now: float) -> bool:
        data = self._load()
        last = data.get(service, 0.0)
        if now - last < self._cooldown:
            return False
        data[service] = now
        self._save(data)
        return True


_auth_notify_tracker = _AuthNotifyTracker()


def build_wechat_client() -> WeChatClient:
    """Construct a 公众号-platform client from the persisted credential.

    The credential may be ``None`` (not logged in yet); the client raises
    ``WeChatAuthError`` on first use in that case, which the scheduler isolates."""
    path = DEFAULT_PATH
    return WeChatClient(MpPlatformTransport(), credential=load(path),
                        credential_path=path)


def build_twitter_client() -> TwitterClient:
    """Construct an X client from the persisted credential.

    Proxy resolves to RSSROB_PROXY env, else the proxy saved with the credential.
    The credential may be ``None`` (not logged in); the client raises
    ``TwitterAuthError`` on first use, which the scheduler isolates."""
    cred = load_twitter_credential(TWITTER_CRED_PATH)
    proxy = normalize_proxy(os.environ.get("RSSROB_PROXY")
                            or (cred.proxy if cred else None))
    return TwitterClient(GraphQlTransport(proxy=proxy), credential=cred,
                         credential_path=TWITTER_CRED_PATH)


_NOTIFY_PATH = os.path.join("var", "subscribers.json")


def _notify_auth_error(service, error):
    """Send a notification about token expiration to configured targets.

    Notifications are rate-limited to once per cooldown period per service
    (default 24 h) to avoid flooding when the scheduler retries frequently.
    Sends to only one target to avoid duplicate messages."""
    now = time.time()
    if not _auth_notify_tracker.should_send(service, now):
        return
    try:
        subs = Subscribers(_NOTIFY_PATH)
        if not subs.auth_notify_enabled():
            return
        explicit = subs.auth_notify_targets()
        targets = explicit if explicit else subs.all_target_urls()
        if not targets:
            return
        # Send to only one target to avoid duplicate messages
        target = targets[0]
        title = "[RSSRob] " + service + " 会话过期"
        body = service + " 的登录凭证已过期，请重新登录。\n\n错误信息：" + str(error)
        send_notification([target], title, body)
    except Exception:
        pass  # best-effort


class Scheduler:
    def __init__(self, config, store, fetcher):
        self.config = config
        self.store = store
        self.fetcher = fetcher
        self._stop = threading.Event()
        self._thread = None
        self._next_run = {site.name: 0.0 for site in config.sites}
        self._backoff = {}                 # site name -> earliest next-due time
        self._wechat_client = None         # built lazily, shared across wechat feeds
        self._twitter_client = None        # built lazily, shared across twitter feeds
        self._proxy_fetchers = {}          # proxy url -> Fetcher (per-site proxy)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _wechat(self) -> WeChatClient:
        if self._wechat_client is None:
            self._wechat_client = build_wechat_client()
        return self._wechat_client

    def _twitter(self) -> TwitterClient:
        if self._twitter_client is None:
            self._twitter_client = build_twitter_client()
        return self._twitter_client

    def _fetcher_for(self, site):
        """The shared fetcher, or a per-site proxied one when site.proxy is set."""
        if not site.proxy:
            return self.fetcher
        if site.proxy not in self._proxy_fetchers:
            self._proxy_fetchers[site.proxy] = Fetcher(proxy=site.proxy)
        return self._proxy_fetchers[site.proxy]

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            for site in self.config.sites:
                if self._stop.is_set():
                    break
                due = max(self._next_run[site.name], self._backoff.get(site.name, 0.0))
                if now >= due:
                    self._run_site(site, now)
                    self._next_run[site.name] = now + site.interval
            self._stop.wait(1.0)

    def _run_site(self, site, now) -> None:
        wechat_client = self._wechat() if site.type == "wechat" else None
        twitter_client = self._twitter() if site.type == "twitter" else None
        fetcher = self._fetcher_for(site)
        try:
            inserted = run_cycle(site, self.store, fetcher,
                                 self.config.output_dir, now,
                                 wechat_client=wechat_client,
                                 twitter_client=twitter_client)
            log.info("scraped %s: %d new item(s)", site.name, inserted)
        except WeChatAuthError as e:
            log.warning("session expired for %s: %s -- re-run wechat-login",
                        site.name, e)
            _notify_auth_error("微信公众号", e)
        except TwitterAuthError as e:
            log.warning("session expired for %s: %s -- re-run twitter-login",
                        site.name, e)
            _notify_auth_error("X/Twitter", e)
        except (WeChatRateLimited, TwitterRateLimited) as e:
            self._backoff[site.name] = now + max(site.interval, _RATE_LIMIT_BACKOFF)
            log.warning("rate-limited %s: %s — backing off", site.name, e)
        except Exception as e:  # per-site isolation: never crash the loop
            log.warning("error scraping %s: %s", site.name, e)
