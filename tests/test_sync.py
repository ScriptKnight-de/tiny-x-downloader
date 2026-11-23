import json

import pytest

from tiny_x_downloader import sync as s
from tiny_x_downloader.config import Settings, load_env_files


@pytest.fixture
def settings(tmp_path):
    return Settings(tmp_path / "c.txt", tmp_path / "out", tmp_path / "state" / "a.sqlite3")


def test_source_urls(settings):
    assert s.source_url("likes", settings) == "https://x.com/i/history/likes"
    assert s.source_url("bookmarks", settings) == "https://x.com/i/bookmarks"


def test_config_archive_outside_output_and_modes(settings):
    full = s.build_config("likes", settings, incremental=False)["extractor"]
    inc = s.build_config("likes", settings, incremental=True)["extractor"]
    assert full["archive"] == str(settings.archive)
    assert full["twitter"]["skip"] is True
    assert inc["twitter"]["skip"] == f"abort:{s.ABORT_AFTER}"
    assert full["twitter"]["directory"] == ["likes"]


def test_backfill_state_switches_to_incremental(settings, monkeypatch):
    settings.archive.parent.mkdir(parents=True)
    monkeypatch.setattr(s, "GALLERY_DL", [__import__("sys").executable, "-c", "pass"])
    s.run_source("likes", settings)
    assert json.loads(settings.state_file.read_text())["likes"]["backfilled"] is True
    seen = {}
    real = s.build_config
    monkeypatch.setattr(s, "build_config",
                        lambda src, st, inc: seen.setdefault("inc", inc) and real(src, st, inc) or real(src, st, inc))
    s.run_source("likes", settings)
    assert seen["inc"] is True


def test_failed_run_does_not_mark_backfilled(settings, monkeypatch):
    settings.archive.parent.mkdir(parents=True)
    monkeypatch.setattr(s, "GALLERY_DL", [__import__("sys").executable, "-c", "raise SystemExit(4)"])
    s.run_source("likes", settings)
    assert not settings.state_file.exists()


def test_env_file_does_not_override(tmp_path, monkeypatch):
    f = tmp_path / "env"
    f.write_text("# c\nX_USERNAME='fromfile'\nX_FOO=bar\n")
    monkeypatch.setenv("X_USERNAME", "fromenv")
    monkeypatch.delenv("X_FOO", raising=False)
    load_env_files([f])
    import os
    assert os.environ["X_USERNAME"] == "fromenv" and os.environ["X_FOO"] == "bar"
    monkeypatch.delenv("X_FOO")


def test_env_file_ignores_keys_outside_the_allowlist(tmp_path, monkeypatch):
    import os
    f = tmp_path / "env"
    f.write_text("PYTHONPATH=/evil\nLD_PRELOAD=/evil.so\nPUID=1000\nTINY_X_DOWNLOADER_ARCHIVE=/a.db\n")
    for k in ("PYTHONPATH", "LD_PRELOAD", "PUID", "TINY_X_DOWNLOADER_ARCHIVE"):
        monkeypatch.delenv(k, raising=False)
    load_env_files([f])
    try:
        assert "PYTHONPATH" not in os.environ and "LD_PRELOAD" not in os.environ
        assert "PUID" not in os.environ
        assert os.environ["TINY_X_DOWNLOADER_ARCHIVE"] == "/a.db"
    finally:
        os.environ.pop("TINY_X_DOWNLOADER_ARCHIVE", None)


def test_auth_error_detection():
    from tiny_x_downloader.notify import looks_like_auth_error as f

    assert f("[twitter][error] AuthRequired: authenticated cookies needed")
    assert f("[twitter][error] HttpError: '401 Unauthorized'")
    assert not f("downloads/likes/name_401_1.jpg")
    assert not f("[twitter][info] Requesting https://x.com/i/bookmarks")


def test_save_state_is_atomic(settings, monkeypatch):
    settings.state_file.parent.mkdir(parents=True)
    s._save_state(settings, {"likes": {"backfilled": True}})
    assert s._load_state(settings) == {"likes": {"backfilled": True}}

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(s.json, "dump", boom)
    with pytest.raises(OSError):
        s._save_state(settings, {"likes": {}})
    assert s._load_state(settings) == {"likes": {"backfilled": True}}
    assert [p.name for p in settings.state_file.parent.iterdir()] == ["state.json"]


def test_second_sync_is_refused_while_locked(settings):
    settings.archive.parent.mkdir(parents=True)
    with s._sync_lock(settings):
        with pytest.raises(s.AlreadyRunning):
            with s._sync_lock(settings):
                pass
    with s._sync_lock(settings):  # released again
        pass
