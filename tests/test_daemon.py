import threading
from datetime import datetime

import pytest

from x_downloader.daemon import next_run, parse_hhmm, run_daemon


def test_next_run_today_and_tomorrow():
    assert next_run(datetime(2026, 1, 1, 3, 0), "04:00") == datetime(2026, 1, 1, 4, 0)
    assert next_run(datetime(2026, 1, 1, 4, 0), "04:00") == datetime(2026, 1, 2, 4, 0)
    assert next_run(datetime(2026, 12, 31, 23, 0), "04:30") == datetime(2027, 1, 1, 4, 30)


@pytest.mark.parametrize("bad", ["4", "25:00", "ab:cd", "12:60"])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        parse_hhmm(bad)


def test_run_on_start_survives_errors():
    stop, calls = threading.Event(), []

    def run():
        calls.append(1)
        stop.set()
        raise RuntimeError("boom")

    run_daemon(run, "04:00", run_on_start=True, stop=stop)
    assert calls == [1]
