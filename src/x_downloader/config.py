"""Settings from environment variables and optional env files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILES = (Path(".env"), Path("~/.config/x-downloader/env").expanduser())


def load_env_files(files=ENV_FILES) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing vars."""
    for f in files:
        if not f.is_file():
            continue
        for raw in f.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


@dataclass(frozen=True)
class Settings:
    username: str
    cookies: Path
    output_dir: Path
    archive: Path

    @property
    def state_file(self) -> Path:
        return self.archive.with_name("state.json")

    @classmethod
    def from_env(cls) -> "Settings":
        username = os.environ.get("X_USERNAME", "").strip().lstrip("@")
        cookies = os.environ.get("X_COOKIES", "").strip()
        if not cookies:
            raise ValueError("X_COOKIES is not set (see .env.example)")
        return cls(
            username=username,
            cookies=_path(cookies),
            output_dir=_path(os.environ.get("X_DOWNLOADER_OUTPUT_DIR", "downloads")),
            archive=_path(
                os.environ.get(
                    "X_DOWNLOADER_ARCHIVE", "~/.local/share/x-downloader/archive.sqlite3"
                )
            ),
        )
