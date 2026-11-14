"""Command line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .core import download


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="x-downloader",
        description="Download videos and GIFs from X (Twitter) posts.",
    )
    p.add_argument("urls", nargs="+", help="post URLs (x.com or twitter.com)")
    p.add_argument(
        "-o", "--output-dir",
        default=os.environ.get("X_DOWNLOADER_OUTPUT_DIR", "downloads"),
        help="target directory (default: ./downloads)",
    )
    p.add_argument(
        "-c", "--cookies",
        default=os.environ.get("X_DOWNLOADER_COOKIES") or None,
        help="Netscape cookies file for protected/age-restricted posts",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="suppress progress output")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cookies = Path(args.cookies) if args.cookies else None
    failures = 0
    for url in args.urls:
        try:
            path = download(url, Path(args.output_dir), cookies, args.quiet)
            print(f"saved: {path}")
        except (ValueError, RuntimeError) as exc:
            failures += 1
            print(f"error: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
