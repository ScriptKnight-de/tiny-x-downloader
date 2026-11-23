"""Run gallery-dl for the likes and bookmarks timelines."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable

from .config import Settings
from .notify import Notifier, cookie_warning, looks_like_auth_error

SOURCES = ("likes", "bookmarks")
# After the first complete run, stop a source after this many consecutive
# already-archived files (timelines are newest-first).
ABORT_AFTER = 30
CANCELLED = 130

# Command used to run gallery-dl (overridable in tests)
GALLERY_DL = [sys.executable, "-m", "gallery_dl"]


def source_url(source: str, settings: Settings) -> str:
    if source == "bookmarks":
        return "https://x.com/i/bookmarks"
    # /i/history/likes takes the account from the "twid" cookie, so no username lookup is needed
    return "https://x.com/i/history/likes"


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


def run_source(
    source: str,
    settings: Settings,
    full: bool = False,
    dry_run: bool = False,
    on_line: Callable[[str], None] | None = None,
    cancel: threading.Event | None = None,
    state_auth: list[str] | None = None,
) -> int:
    if state_auth is None:
        state_auth = []
    emit = on_line or (lambda line: print(line, flush=True))
    state = _load_state(settings)
    incremental = bool(state.get(source, {}).get("backfilled")) and not full
    cfg = build_config(source, settings, incremental)

    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "gallery-dl.json"
        cfg_path.write_text(json.dumps(cfg))
        cmd = [*GALLERY_DL, "--config-ignore", "--config-json", str(cfg_path)]
        if dry_run:
            cmd.append("--simulate")
        cmd.append(source_url(source, settings))
        emit(f"[{source}] {'incremental' if incremental else 'full backfill'} run")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        cancelled = False
        assert proc.stdout is not None
        done = threading.Event()

        def watch() -> None:  # stop gallery-dl even while it prints nothing (e.g. rate-limit sleep)
            while not done.wait(0.5):
                if cancel is not None and cancel.is_set():
                    proc.terminate()
                    return

        threading.Thread(target=watch, daemon=True).start()
        try:
            for line in proc.stdout:
                emit(line.rstrip("\n"))
                if looks_like_auth_error(line):
                    state_auth.append(line.strip())
                if cancel is not None and cancel.is_set():
                    cancelled = True
                    proc.terminate()
                    break
        except BaseException:  # e.g. Ctrl+C: don't leave gallery-dl running
            proc.terminate()
            raise
        finally:
            done.set()
        cancelled = cancelled or (cancel is not None and cancel.is_set())
        try:
            code = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()

    if cancelled:
        return CANCELLED
    if code == 0 and not dry_run:
        state.setdefault(source, {})["backfilled"] = True
        _save_state(settings, state)
    return code


def sync(
    settings: Settings,
    sources=SOURCES,
    full=False,
    dry_run=False,
    on_line: Callable[[str], None] | None = None,
    cancel: threading.Event | None = None,
    notifier: Notifier | None = None,
) -> int:
    notifier = notifier if notifier is not None else Notifier.from_env()
    alert = notifier.enabled and not dry_run
    try:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        settings.archive.parent.mkdir(parents=True, exist_ok=True)
        if not settings.cookies.is_file():
            raise ValueError(f"cookies file not found: {settings.cookies}")
        worst, auth_lines, failed = 0, [], []
        for source in sources:
            code = run_source(source, settings, full, dry_run, on_line, cancel, auth_lines)
            if code == CANCELLED:
                return CANCELLED
            if code:
                failed.append(f"{source} (exit {code})")
            worst = max(worst, code)
    except Exception as exc:
        if alert:
            notifier.send("sync crashed", str(exc))
        raise
    if alert:
        _report(settings, notifier, worst, failed, auth_lines)
    return worst


def _report(settings: Settings, notifier: Notifier, worst: int, failed: list[str],
            auth_lines: list[str]) -> None:
    state = _load_state(settings)
    if auth_lines:
        notifier.send("login expired", "gallery-dl was rejected, the session cookie is no longer "
                      "valid. Export a fresh cookies.txt.\n" + auth_lines[-1][:300])
        state["alert"] = "auth"
    elif worst:
        notifier.send("sync failed", "Failed: " + ", ".join(failed))
        state["alert"] = "failed"
    else:
        warn = cookie_warning(settings.cookies, notifier.warn_days)
        if warn:
            notifier.send("cookie expiring", warn, priority=4)
        if state.get("alert"):
            notifier.send("sync recovered", "The last sync finished without errors.", priority=3)
            state.pop("alert")
    _save_state(settings, state)
