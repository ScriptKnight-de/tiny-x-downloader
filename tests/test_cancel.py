"""Stop button, SIGTERM and Ctrl+C must end the gallery-dl child and leave things clean."""
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

from tiny_x_downloader import sync as s
from tiny_x_downloader.config import Settings
from tiny_x_downloader.daemon import run_daemon

# Stand-in for gallery-dl: prints its pid, then either stays silent (like a rate-limit
# sleep) or keeps printing. It ignores the arguments gallery-dl would get.
SILENT = "import os,time; print(os.getpid(), flush=True); time.sleep(60)"
CHATTY = "import os,time; print(os.getpid(), flush=True)\nwhile True: print('x', flush=True); time.sleep(0.05)"


@pytest.fixture
def settings(tmp_path):
    cookies = tmp_path / "c.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    return Settings(cookies, tmp_path / "out", tmp_path / "state" / "a.sqlite3")


def fake_gallery_dl(monkeypatch, code):
    monkeypatch.setattr(s, "GALLERY_DL", [sys.executable, "-c", code])


def is_gone(pid: int, timeout: float = 5.0) -> bool:
    """True once the process has exited (a zombie that is not yet reaped counts as gone)."""
    stat = Path(f"/proc/{pid}/stat")
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                return True
        except (FileNotFoundError, ProcessLookupError):
            return True
        time.sleep(0.05)
    return False


class Lines:
    """on_line callback that records the child's pid and can run a hook once it is known."""

    def __init__(self, hook=None):
        self.pid = None
        self.hook = hook

    def __call__(self, line):
        if self.pid is None and line.strip().isdigit():
            self.pid = int(line)
            if self.hook:
                self.hook()


@pytest.mark.parametrize("child", [SILENT, CHATTY], ids=["silent", "chatty"])
def test_stop_terminates_the_child(settings, monkeypatch, child):
    settings.archive.parent.mkdir(parents=True)
    fake_gallery_dl(monkeypatch, child)
    stop = threading.Event()
    lines = Lines(hook=lambda: threading.Timer(0.3, stop.set).start())
    start = time.monotonic()
    assert s.run_source("likes", settings, on_line=lines, cancel=stop) == s.CANCELLED
    assert time.monotonic() - start < 10
    assert is_gone(lines.pid)
    assert not settings.state_file.exists()  # a cancelled run is not a finished backfill


def test_stop_in_sync_releases_the_lock_and_sends_no_alert(settings, monkeypatch):
    fake_gallery_dl(monkeypatch, SILENT)
    stop = threading.Event()
    sent = []

    class Spy:
        enabled = True
        warn_days = 7
        def send(self, *a, **k): sent.append(a)

    lines = Lines(hook=lambda: threading.Timer(0.3, stop.set).start())
    start = time.monotonic()
    assert s.sync(settings, on_line=lines, cancel=stop, notifier=Spy()) == s.CANCELLED
    assert time.monotonic() - start < 10
    assert is_gone(lines.pid)
    assert sent == []
    fake_gallery_dl(monkeypatch, "pass")
    assert s.sync(settings, notifier=Spy()) == 0  # lock was released, a new sync can start


def test_ctrl_c_terminates_the_child(settings, monkeypatch):
    settings.archive.parent.mkdir(parents=True)
    fake_gallery_dl(monkeypatch, SILENT)

    def interrupt():
        raise KeyboardInterrupt

    lines = Lines(hook=interrupt)
    with pytest.raises(KeyboardInterrupt):
        s.run_source("likes", settings, on_line=lines)
    assert is_gone(lines.pid)
    assert not settings.state_file.exists()


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_daemon_signal_stops_a_running_sync(settings, monkeypatch, sig):
    """SIGTERM (docker stop) and SIGINT must stop the child and let the daemon exit."""
    settings.archive.parent.mkdir(parents=True)
    fake_gallery_dl(monkeypatch, SILENT)
    stop = threading.Event()
    old = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
    lines = Lines(hook=lambda: threading.Timer(0.3, os.kill, (os.getpid(), sig)).start())
    codes = []
    try:
        start = time.monotonic()
        run_daemon(lambda: codes.append(s.run_source("likes", settings, on_line=lines, cancel=stop)) or 0,
                   "04:00", run_on_start=True, stop=stop)
        assert time.monotonic() - start < 15
    finally:
        for n, handler in old.items():
            signal.signal(n, handler)
    assert codes == [s.CANCELLED]
    assert is_gone(lines.pid)
