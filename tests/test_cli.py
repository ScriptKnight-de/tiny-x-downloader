from tiny_x_downloader import cli, timer


def test_oserror_becomes_error_message(monkeypatch, capsys):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(cli, "sync", boom)
    monkeypatch.setenv("X_COOKIES", "/nonexistent")
    assert cli.main(["sync"]) == 1
    assert "error: disk full" in capsys.readouterr().err


def test_install_timer_failure_is_reported(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(timer, "UNIT_DIR", tmp_path)

    def no_systemctl(*a, **k):
        raise FileNotFoundError(2, "No such file or directory", "systemctl")

    monkeypatch.setattr(timer.subprocess, "check_call", no_systemctl)
    assert cli.main(["install-timer"]) == 1
    assert "systemctl" in capsys.readouterr().err
