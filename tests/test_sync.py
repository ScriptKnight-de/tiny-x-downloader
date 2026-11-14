import json

import pytest

from x_downloader import sync as s
from x_downloader.config import Settings, load_env_files


@pytest.fixture
def settings(tmp_path):
    return Settings("me", tmp_path / "c.txt", tmp_path / "out", tmp_path / "state" / "a.sqlite3")


def test_source_urls(settings):
    assert s.source_url("likes", settings) == "https://x.com/me/likes"
    assert s.source_url("bookmarks", settings) == "https://x.com/i/bookmarks"


def test_likes_requires_username(tmp_path):
    st = Settings("", tmp_path / "c", tmp_path, tmp_path / "a")
    with pytest.raises(ValueError):
        s.source_url("likes", st)


def test_config_archive_outside_output_and_modes(settings):
    full = s.build_config("likes", settings, incremental=False)["extractor"]
    inc = s.build_config("likes", settings, incremental=True)["extractor"]
    assert full["archive"] == str(settings.archive)
    assert full["twitter"]["skip"] is True
    assert inc["twitter"]["skip"] == f"abort:{s.ABORT_AFTER}"
    assert full["twitter"]["directory"] == ["likes"]


def test_backfill_state_switches_to_incremental(settings, monkeypatch):
    settings.archive.parent.mkdir(parents=True)
    modes = []
    monkeypatch.setattr(s.subprocess, "call", lambda cmd: modes.append(cmd) or 0)
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
    monkeypatch.setattr(s.subprocess, "call", lambda cmd: 4)
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
