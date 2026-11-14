"""Core download logic."""

from __future__ import annotations

import re
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

_URL_RE = re.compile(
    r"^https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/[^/\s]+/status/(\d+)",
    re.IGNORECASE,
)


def parse_status_id(url: str) -> str | None:
    """Return the post ID of an x.com / twitter.com status URL, or None."""
    m = _URL_RE.match(url.strip())
    return m.group(1) if m else None


def download(
    url: str,
    output_dir: Path,
    cookies: Path | None = None,
    quiet: bool = False,
) -> Path:
    """Download the media of a single post and return the saved file path."""
    if parse_status_id(url) is None:
        raise ValueError(f"Not a valid X/Twitter post URL: {url}")

    output_dir.mkdir(parents=True, exist_ok=True)
    opts: dict = {
        "outtmpl": str(output_dir / "%(uploader_id)s-%(id)s.%(ext)s"),
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": quiet,
        "noprogress": quiet,
        "noplaylist": True,
    }
    if cookies:
        opts["cookiefile"] = str(cookies)

    with YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except DownloadError as exc:
            raise RuntimeError(str(exc)) from exc
        return Path(ydl.prepare_filename(info))
