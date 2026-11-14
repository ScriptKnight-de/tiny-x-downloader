"""Install a daily systemd user timer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

UNIT_DIR = Path("~/.config/systemd/user").expanduser()

SERVICE = """[Unit]
Description=Download media from liked and bookmarked X posts

[Service]
Type=oneshot
EnvironmentFile=-%h/.config/x-downloader/env
ExecStart={python} -m x_downloader sync
"""

TIMER = """[Unit]
Description=Daily x-downloader sync

[Timer]
OnCalendar=*-*-* {time}:00
Persistent=true
RandomizedDelaySec=10min

[Install]
WantedBy=timers.target
"""


def install_timer(time: str = "04:00", enable: bool = True) -> None:
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    (UNIT_DIR / "x-downloader.service").write_text(SERVICE.format(python=sys.executable))
    (UNIT_DIR / "x-downloader.timer").write_text(TIMER.format(time=time))
    print(f"wrote units to {UNIT_DIR}")
    if enable:
        subprocess.check_call(["systemctl", "--user", "daemon-reload"])
        subprocess.check_call(["systemctl", "--user", "enable", "--now", "x-downloader.timer"])
        print("timer enabled; check with: systemctl --user list-timers x-downloader.timer")
