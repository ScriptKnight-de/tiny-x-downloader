"""Run gallery-dl for the likes and bookmarks timelines."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import Settings

SOURCES = ("likes", "bookmarks")
# After the first complete run, stop a source after this many consecutive
# already-archived files (timelines are newest-first).
ABORT_AFTER = 30


def source_url(source: str, settings: Settings) -> str:
    if source == "bookmarks":
        return "https://x.com/i/bookmarks"
    if not settings.username:
        raise ValueError("X_USERNAME is required to read the likes timeline")
    return f"https://x.com/{settings.username}/likes"


def build_config(source: str, settings: Settings, incremental: bool) -> dict:
    return {
        "extractor": {
            "cookies": str(settings.cookies),
            "archive": str(settings.archive),
            "twitter": {
                "base-directory": str(settings.output_dir),
                "directory": [source],
                "filename": "{author[name]}_{tweet_id}_{num}.{extension}",
                "videos": True,
                "skip": f"abort:{ABORT_AFTER}" if incremental else True,
            },
        }
    }


def _load_state(settings: Settings) -> dict:
    try:
        return json.loads(settings.state_file.read_text())
    except (OSError, ValueError):
        return {}


def _save_state(settings: Settings, state: dict) -> None:
    settings.state_file.write_text(json.dumps(state, indent=2))


def run_source(source: str, settings: Settings, full: bool = False, dry_run: bool = False) -> int:
    state = _load_state(settings)
    incremental = bool(state.get(source, {}).get("backfilled")) and not full
    cfg = build_config(source, settings, incremental)

    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "gallery-dl.json"
        cfg_path.write_text(json.dumps(cfg))
        cmd = [sys.executable, "-m", "gallery_dl", "--config-ignore",
               "--config-json", str(cfg_path)]
        if dry_run:
            cmd.append("--simulate")
        cmd.append(source_url(source, settings))
        print(f"[{source}] {'incremental' if incremental else 'full backfill'} run", flush=True)
        code = subprocess.call(cmd)

    if code == 0 and not dry_run:
        state.setdefault(source, {})["backfilled"] = True
        _save_state(settings, state)
    return code


def sync(settings: Settings, sources=SOURCES, full=False, dry_run=False) -> int:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.archive.parent.mkdir(parents=True, exist_ok=True)
    if not settings.cookies.is_file():
        raise ValueError(f"cookies file not found: {settings.cookies}")
    worst = 0
    for source in sources:
        worst = max(worst, run_source(source, settings, full, dry_run))
    return worst
