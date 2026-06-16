import argparse
import logging
import sys

from .config import ConfigError, default_config_path, load_config
from .fetch import Fetcher
from .pipeline import obtain_items, run_cycle
from .scheduler import Scheduler
from .server import make_server
from .store import Store


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rssrob")
    parser.add_argument("--config", default=default_config_path(),
                        help="config file or directory (default: ./config/ if present, "
                             "else config.yaml, else config.example.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    p_once = sub.add_parser("run-once")
    p_once.add_argument("site")
    p_once.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"config not found: {args.config}", file=sys.stderr)
        return 2

    if args.command == "serve":
        return _serve(config)
    return _run_once(config, args.site, args.write)


def _serve(config) -> int:
    store = Store(config.state_db)
    fetcher = Fetcher()
    scheduler = Scheduler(config, store, fetcher)
    scheduler.start()
    server = make_server(config.output_dir, config.http.host, config.http.port)
    print(f"serving on http://{config.http.host}:{config.http.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down…")
    finally:
        scheduler.stop()
        server.server_close()
        store.close()
    return 0


def _run_once(config, site_name, write) -> int:
    site = next((s for s in config.sites if s.name == site_name), None)
    if site is None:
        print(f"no such site: {site_name}", file=sys.stderr)
        return 2

    fetcher = Fetcher()
    if write:
        store = Store(config.state_db)
        try:
            inserted = run_cycle(site, store, fetcher, config.output_dir)
        finally:
            store.close()
        print(f"{inserted} new item(s); wrote {config.output_dir}/{site.name}.xml")
        return 0

    items, _, _ = obtain_items(site, fetcher)
    print(f"{len(items)} item(s) from {site.name}:")
    for i, it in enumerate(items, 1):
        print(f"{i:>2}. [{it.date}] {it.title}")
        print(f"    {it.link}")
    return 0
