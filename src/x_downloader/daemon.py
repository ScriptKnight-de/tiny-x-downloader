"""Long-running scheduler: run a sync once per day at a fixed local time."""

from __future__ import annotations

import signal
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

from .config import Settings


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":")
        h, m = int(h), int(m)
    except ValueError:
        raise ValueError(f"invalid time {value!r}, expected HH:MM") from None
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"invalid time {value!r}, expected HH:MM")
    return h, m


def next_run(now: datetime, hhmm: str) -> datetime:
    h, m = parse_hhmm(hhmm)
    candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(days=1)


def run_daemon(
    run: Callable[[], int],
    hhmm: str,
    run_on_start: bool = False,
    stop: threading.Event | None = None,
) -> None:
    parse_hhmm(hhmm)
    stop = stop or threading.Event()
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())

    def attempt() -> None:
        print(f"{datetime.now():%F %T} sync started", flush=True)
        try:
            code = run()
        except Exception as exc:  # keep the daemon alive; retry next day
            print(f"sync failed: {exc}", flush=True)
        else:
            print(f"{datetime.now():%F %T} sync finished (exit {code})", flush=True)

    if run_on_start:
        attempt()
    while not stop.is_set():
        target = next_run(datetime.now(), hhmm)
        print(f"next sync at {target:%F %T}", flush=True)
        while not stop.is_set() and datetime.now() < target:
            stop.wait(min(60, max(1.0, (target - datetime.now()).total_seconds())))
        if not stop.is_set():
            attempt()
    print("stopping", flush=True)
