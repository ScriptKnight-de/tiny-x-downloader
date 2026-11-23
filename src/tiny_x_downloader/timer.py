"""Install a daily systemd user timer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .daemon import parse_hhmm

UNIT_DIR = Path("~/.config/systemd/user").expanduser()

SERVICE = """[Unit]
Description=Download media from liked and bookmarked X posts

[Service]
Type=oneshot
EnvironmentFile=-%h/.config/tiny-x-downloader/env
ExecStart={command} sync
"""

TIMER = """[Unit]
Description=Daily tiny-x-downloader sync

[Timer]
OnCalendar=*-*-* {time}:00
Persistent=true
RandomizedDelaySec=10min

[Install]
WantedBy=timers.target
"""


def _quote(arg: str) -> str:
    """Quote one word for a systemd ExecStart= line (spaces, quotes, % and $ are special there)."""
    arg = arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
    return f'"{arg}"'


def _exec_command() -> str:
    appimage = os.environ.get("APPIMAGE")
    if appimage:  # inside an AppImage sys.executable is a temporary mount path; use the file itself
        return _quote(appimage)
    return f"{_quote(sys.executable)} -m tiny_x_downloader"


def install_timer(time: str = "04:00", enable: bool = True) -> None:
    h, m = parse_hhmm(time)  # raises ValueError before anything is written
    time = f"{h:02d}:{m:02d}"
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    (UNIT_DIR / "tiny-x-downloader.service").write_text(SERVICE.format(command=_exec_command()))
    (UNIT_DIR / "tiny-x-downloader.timer").write_text(TIMER.format(time=time))
    print(f"wrote units to {UNIT_DIR}")
    if enable:
        subprocess.check_call(["systemctl", "--user", "daemon-reload"])
        subprocess.check_call(["systemctl", "--user", "enable", "--now", "tiny-x-downloader.timer"])
        print("timer enabled; check with: systemctl --user list-timers tiny-x-downloader.timer")
