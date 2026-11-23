"""Settings from environment variables and optional env files."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

USER_ENV_FILE = Path("~/.config/tiny-x-downloader/env").expanduser()
ENV_FILES = (Path(".env"), USER_ENV_FILE)
DEFAULT_ARCHIVE = "~/.local/share/tiny-x-downloader/archive.sqlite3"

# Only these keys are taken from env files. Anything else (PATH, PYTHONPATH, LD_PRELOAD, ...)
# would be inherited by the gallery-dl subprocess, so a stray .env must not be able to set it.
ALLOWED_PREFIXES = ("X_", "TINY_X_DOWNLOADER_")
ALLOWED_KEYS = ("TZ",)


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
            key = key.strip()
            if key.startswith(ALLOWED_PREFIXES) or key in ALLOWED_KEYS:
                os.environ.setdefault(key, value.strip().strip("'\""))


def _path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


@dataclass(frozen=True)
class Settings:
    cookies: Path
    output_dir: Path
    archive: Path

    @property
    def state_file(self) -> Path:
        return self.archive.with_name("state.json")

    @classmethod
    def from_values(cls, cookies: str, output_dir: str, archive: str) -> "Settings":
        if not cookies.strip():
            raise ValueError("cookies file is not set")
        return cls(
            cookies=_path(cookies.strip()),
            output_dir=_path(output_dir.strip() or "downloads"),
            archive=_path(archive.strip() or DEFAULT_ARCHIVE),
        )

    @classmethod
    def from_env(cls) -> "Settings":
        if not os.environ.get("X_COOKIES", "").strip():
            raise ValueError("X_COOKIES is not set (see .env.example)")
        return cls.from_values(
            os.environ["X_COOKIES"],
            os.environ.get("TINY_X_DOWNLOADER_OUTPUT_DIR", "downloads"),
            os.environ.get("TINY_X_DOWNLOADER_ARCHIVE", DEFAULT_ARCHIVE),
        )


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip("'\"")
    return values


def write_env_file(path: Path, updates: dict[str, str]) -> None:
    """Update KEY=VALUE pairs in place, keeping comments and unrelated keys."""
    lines = path.read_text().splitlines() if path.is_file() else []
    remaining = dict(updates)
    out = []
    for raw in lines:
        key = raw.split("=", 1)[0].strip() if "=" in raw and not raw.lstrip().startswith("#") else None
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(raw)
    out += [f"{k}={v}" for k, v in remaining.items()]
    target = path.resolve()  # follow a symlinked env file (dotfile managers) instead of replacing it
    target.parent.mkdir(parents=True, exist_ok=True)
    # the temp file is created 0600 and swapped in: never readable by others, never half-written
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(out) + "\n")
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
