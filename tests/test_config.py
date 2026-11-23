import stat

from tiny_x_downloader.config import write_env_file


def test_write_env_file_is_private_and_keeps_other_lines(tmp_path):
    f = tmp_path / "sub" / "env"
    f.parent.mkdir()
    f.write_text("# keep me\nOTHER=1\nX_COOKIES=old\n")
    f.chmod(0o644)
    write_env_file(f, {"X_COOKIES": "new", "X_SYNC_TIME": "05:00"})
    assert f.read_text() == "# keep me\nOTHER=1\nX_COOKIES=new\nX_SYNC_TIME=05:00\n"
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert [p.name for p in f.parent.iterdir()] == ["env"]


def test_write_env_file_keeps_symlink(tmp_path):
    real = tmp_path / "real"
    real.write_text("A=1\n")
    link = tmp_path / "env"
    link.symlink_to(real)
    write_env_file(link, {"X_COOKIES": "c"})
    assert link.is_symlink() and "X_COOKIES=c" in real.read_text()
