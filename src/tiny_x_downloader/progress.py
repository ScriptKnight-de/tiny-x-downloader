"""Interpret gallery-dl output lines for the GUI (no GUI imports here)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath


@dataclass
class Progress:
    state: str = "idle"          # idle | running | stopping
    source: str = ""
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    current_file: str = ""
    last_result: str = "never run"
    last_finished: datetime | None = None

    def start(self) -> None:
        self.state = "running"
        self.source = ""
        self.downloaded = self.skipped = self.errors = 0
        self.current_file = ""

    def feed(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        if line.startswith("[") and "] " in line and line.split("]")[0].lstrip("[") in ("likes", "bookmarks"):
            self.source = line.split("]")[0].lstrip("[")
        elif line.startswith("# "):
            self.skipped += 1
        elif line.startswith("["):
            if "[error]" in line:
                self.errors += 1
        else:
            self.downloaded += 1
            self.current_file = PurePath(line).name

    def finish(self, code: int, now: datetime | None = None) -> None:
        self.state = "idle"
        self.source = ""
        self.current_file = ""
        self.last_finished = now or datetime.now()
        if code == 130:
            self.last_result = "stopped"
        elif code == 0:
            self.last_result = f"ok, {self.downloaded} new file(s)"
        else:
            self.last_result = f"finished with errors (exit {code}), {self.downloaded} new file(s)"

    def summary(self) -> str:
        if self.state == "idle":
            return "Idle"
        where = f" {self.source}" if self.source else ""
        stop = " (stopping...)" if self.state == "stopping" else ""
        return f"Running{where}: {self.downloaded} downloaded, {self.skipped} already known{stop}"
