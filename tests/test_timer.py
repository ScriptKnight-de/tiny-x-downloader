import sys

import pytest

from tiny_x_downloader import timer


def test_install_timer_rejects_invalid_time(tmp_path, monkeypatch):
    monkeypatch.setattr(timer, "UNIT_DIR", tmp_path)
    with pytest.raises(ValueError):
        timer.install_timer("25:99", enable=False)
    assert list(tmp_path.iterdir()) == []


def test_install_timer_pads_time(tmp_path, monkeypatch):
    monkeypatch.setattr(timer, "UNIT_DIR", tmp_path)
    timer.install_timer("4:05", enable=False)
    assert "OnCalendar=*-*-* 04:05:00" in (tmp_path / "tiny-x-downloader.timer").read_text()


def test_service_uses_appimage_path_when_set(tmp_path, monkeypatch):
    monkeypatch.setattr(timer, "UNIT_DIR", tmp_path)
    monkeypatch.setenv("APPIMAGE", "/home/me/Apps/tiny x.AppImage")
    timer.install_timer("04:00", enable=False)
    assert 'ExecStart="/home/me/Apps/tiny x.AppImage" sync' in (tmp_path / "tiny-x-downloader.service").read_text()


def test_service_uses_python_module_otherwise(tmp_path, monkeypatch):
    monkeypatch.setattr(timer, "UNIT_DIR", tmp_path)
    monkeypatch.delenv("APPIMAGE", raising=False)
    timer.install_timer("04:00", enable=False)
    assert f'ExecStart="{sys.executable}" -m tiny_x_downloader sync' in (tmp_path / "tiny-x-downloader.service").read_text()
