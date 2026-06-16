import logging
import threading
import time

from .pipeline import run_cycle

log = logging.getLogger("rssrob.scheduler")


class Scheduler:
    def __init__(self, config, store, fetcher):
        self.config = config
        self.store = store
        self.fetcher = fetcher
        self._stop = threading.Event()
        self._thread = None
        self._next_run = {site.name: 0.0 for site in config.sites}

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            for site in self.config.sites:
                if self._stop.is_set():
                    break
                if now >= self._next_run[site.name]:
                    self._run_site(site, now)
                    self._next_run[site.name] = now + site.interval
            self._stop.wait(1.0)

    def _run_site(self, site, now) -> None:
        try:
            inserted = run_cycle(site, self.store, self.fetcher,
                                 self.config.output_dir, now)
            log.info("scraped %s: %d new item(s)", site.name, inserted)
        except Exception as e:  # per-site isolation: never crash the loop
            log.warning("error scraping %s: %s", site.name, e)
