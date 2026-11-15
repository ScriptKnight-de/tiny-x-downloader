import sys
import threading

from x_downloader import sync as s
from x_downloader.config import Settings, read_env_file, write_env_file
from x_downloader.progress import Progress


def test_progress_parsing():
    p = Progress()
    p.start()
    for line in ["[likes] full backfill run", "[twitter][info] Requesting guest token",
                 "/out/likes/a_1_1.jpg", "# /out/likes/a_1_2.jpg", "/out/likes/b_2_1.mp4",
                 "[twitter][error] boom"]:
        p.feed(line)
    assert (p.source, p.downloaded, p.skipped, p.errors, p.current_file) == (
        "likes", 2, 1, 1, "b_2_1.mp4")
    assert "2 downloaded" in p.summary()
    p.finish(0)
    assert p.state == "idle" and "2 new" in p.last_result


def test_env_file_roundtrip_keeps_other_lines(tmp_path):
    f = tmp_path / "sub" / "env"
    write_env_file(f, {"A": "1", "B": "2"})
    f.write_text("# keep me\n" + f.read_text() + "OTHER=x\n")
    write_env_file(f, {"A": "9", "C": "3"})
    assert read_env_file(f) == {"A": "9", "B": "2", "OTHER": "x", "C": "3"}
    assert "# keep me" in f.read_text()
    assert oct(f.stat().st_mode & 0o777) == "0o600"


def test_from_values_validation(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        Settings.from_values("  ", "x", "y")
    st = Settings.from_values("~/c.txt", "", "")
    assert st.output_dir.name == "downloads"


def _fake(monkeypatch, script):
    monkeypatch.setattr(s, "GALLERY_DL", [sys.executable, "-c", script])


def test_run_source_streams_lines(tmp_path, monkeypatch):
    st = Settings(tmp_path / "c", tmp_path / "o", tmp_path / "a" / "a.sqlite3")
    st.archive.parent.mkdir()
    _fake(monkeypatch, "print('/o/x.jpg'); print('# /o/y.jpg')")
    got = []
    assert s.run_source("bookmarks", st, on_line=got.append) == 0
    assert got[1:] == ["/o/x.jpg", "# /o/y.jpg"]


def test_run_source_cancel(tmp_path, monkeypatch):
    st = Settings(tmp_path / "c", tmp_path / "o", tmp_path / "a" / "a.sqlite3")
    st.archive.parent.mkdir()
    _fake(monkeypatch, "import time\nfor i in range(100):\n print(i, flush=True); time.sleep(0.05)")
    cancel = threading.Event()
    seen = []

    def on_line(line):
        seen.append(line)
        if len(seen) == 3:
            cancel.set()

    assert s.run_source("bookmarks", st, on_line=on_line, cancel=cancel) == s.CANCELLED
    assert len(seen) < 10 and not st.state_file.exists()
