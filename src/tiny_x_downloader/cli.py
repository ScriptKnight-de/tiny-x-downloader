"""Command line interface."""

from __future__ import annotations

import argparse
import sys
import threading

from . import __version__
import os

from .config import Settings, load_env_files
from .daemon import run_daemon
from .donate import DONATE_TEXT
from .notify import Notifier
from .sync import SOURCES, sync
from .timer import install_timer


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tiny-x-downloader",
        description="Download images and videos from your liked and bookmarked X posts.",
        epilog=DONATE_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sync", help="download new media from likes and bookmarks")
    s.add_argument("--source", choices=SOURCES, action="append",
                   help="limit to one source (repeatable; default: both)")
    s.add_argument("--full", action="store_true",
                   help="scan the whole timeline instead of stopping at known posts")
    s.add_argument("--dry-run", action="store_true", help="list what would be downloaded")

    d = sub.add_parser("daemon", help="run forever, syncing once per day (for Docker)")
    d.add_argument("--time", default=os.environ.get("X_SYNC_TIME", "04:00"),
                   help="HH:MM local time (default 04:00, env X_SYNC_TIME)")
    d.add_argument("--run-on-start", action="store_true",
                   default=os.environ.get("X_RUN_ON_START", "").lower() in ("1", "true", "yes"),
                   help="also sync immediately at startup (env X_RUN_ON_START)")

    sub.add_parser("gui", help="open the graphical settings and status window")
    sub.add_parser("notify-test", help="send a test alert to the configured Gotify/ntfy/webhook")
    sub.add_parser("donate", help="show how to support the project (Ko-fi)")

    t = sub.add_parser("install-timer", help="install a daily systemd user timer")
    t.add_argument("--time", default="04:00", help="HH:MM local time (default 04:00)")
    t.add_argument("--no-enable", action="store_true", help="only write the unit files")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "install-timer":
            install_timer(args.time, enable=not args.no_enable)
            return 0
        if args.command == "donate":
            print(DONATE_TEXT)
            return 0
        if args.command == "gui":
            from .gui import run_gui  # lazy: needs tkinter

            return run_gui()
        load_env_files()
        if args.command == "notify-test":
            n = Notifier.from_env()
            if not n.enabled:
                print("error: no notification target configured (see .env.example)", file=sys.stderr)
                return 2
            errors = n.send("test", "Notifications are working.", priority=3)
            for e in errors:
                print(f"error: {e}", file=sys.stderr)
            print("sent" if not errors else "failed")
            return 1 if errors else 0
        if args.command == "daemon":
            settings = Settings.from_env()
            stop = threading.Event()  # set by SIGTERM/SIGINT; also stops a running sync
            run_daemon(lambda: sync(settings, cancel=stop), args.time, args.run_on_start, stop)
            return 0
        return sync(Settings.from_env(), tuple(args.source or SOURCES),
                    full=args.full, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
