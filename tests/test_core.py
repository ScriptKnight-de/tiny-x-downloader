import pytest

from x_downloader.cli import build_parser
from x_downloader.core import download, parse_status_id


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x.com/jack/status/20", "20"),
        ("https://twitter.com/jack/status/20?s=46", "20"),
        ("https://mobile.twitter.com/jack/status/123/video/1", "123"),
        ("https://example.com/jack/status/20", None),
        ("not a url", None),
    ],
)
def test_parse_status_id(url, expected):
    assert parse_status_id(url) == expected


def test_download_rejects_invalid_url(tmp_path):
    with pytest.raises(ValueError):
        download("https://example.com", tmp_path)


def test_parser_defaults():
    args = build_parser().parse_args(["https://x.com/a/status/1"])
    assert args.output_dir == "downloads"
