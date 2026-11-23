import sys

import pytest

from tiny_x_downloader import notify, sync as s
from tiny_x_downloader.config import Settings
from tiny_x_downloader.notify import Notifier


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, url, body, headers=None):
        self.calls.append((url, body, headers or {}))


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(notify, "_post", r)
    return r


@pytest.fixture
def settings(tmp_path):
    (tmp_path / "c.txt").write_text("# Netscape\n")
    return Settings(tmp_path / "c.txt", tmp_path / "out", tmp_path / "state" / "a.sqlite3")


def fake_gdl(monkeypatch, script):
    monkeypatch.setattr(s, "GALLERY_DL", [sys.executable, "-c", script])


def test_disabled_by_default(monkeypatch):
    for k in ("GOTIFY_URL", "GOTIFY_TOKEN", "NTFY_URL", "WEBHOOK_URL"):
        monkeypatch.delenv(f"{notify.PREFIX}_{k}", raising=False)
    assert not Notifier.from_env().enabled


def test_all_targets(rec):
    n = Notifier(gotify_url="http://g/", gotify_token="T", ntfy_url="http://n/t", webhook_url="http://w")
    assert n.send("x", "msg") == []
    urls = [c[0] for c in rec.calls]
    assert urls == ["http://g/message", "http://n/t", "http://w"]
    assert rec.calls[0][2]["X-Gotify-Key"] == "T"


def test_send_swallows_errors(monkeypatch):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(notify, "_post", boom)
    assert Notifier(webhook_url="http://w").send("x", "y") == ["webhook: down"]


def test_cookie_expiry(tmp_path):
    f = tmp_path / "c.txt"
    f.write_text(f"#HttpOnly_.x.com\tTRUE\t/\tTRUE\t2000000000\t{notify.AUTH_COOKIES[0]}\tv\n")
    assert notify.cookie_expiry(f) == 2000000000
    assert "expires in" in notify.cookie_warning(f, 7, now=2000000000 - 86400)
    assert "expired" in notify.cookie_warning(f, 7, now=2000000001)
    assert notify.cookie_warning(f, 7, now=1) is None


def test_failed_sync_alerts_then_recovery(settings, rec, monkeypatch):
    n = Notifier(webhook_url="http://w")
    fake_gdl(monkeypatch, "import sys; sys.exit(4)")
    assert s.sync(settings, notifier=n) == 4
    assert rec.calls[-1][1]["title"].endswith("sync failed")
    fake_gdl(monkeypatch, "pass")
    assert s.sync(settings, notifier=n) == 0
    assert rec.calls[-1][1]["title"].endswith("sync recovered")
    rec.calls.clear()
    s.sync(settings, notifier=n)
    assert rec.calls == []


def test_auth_error_alert(settings, rec, monkeypatch):
    fake_gdl(monkeypatch, "import sys; print('[twitter][error] AuthRequired: x'); sys.exit(16)")
    s.sync(settings, notifier=Notifier(webhook_url="http://w"))
    assert rec.calls[-1][1]["title"].endswith("login expired")


def test_dry_run_and_missing_cookie(settings, rec, monkeypatch):
    n = Notifier(webhook_url="http://w")
    fake_gdl(monkeypatch, "import sys; sys.exit(1)")
    s.sync(settings, dry_run=True, notifier=n)
    assert rec.calls == []
    settings.cookies.unlink()
    with pytest.raises(ValueError):
        s.sync(settings, notifier=n)
    assert rec.calls[-1][1]["title"].endswith("sync crashed")
