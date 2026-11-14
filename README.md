# x-downloader

Command-line tool to download videos and GIFs from X (Twitter) posts. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
x-downloader https://x.com/user/status/1234567890
x-downloader -o ~/Videos URL1 URL2
x-downloader -c cookies.txt URL      # protected / age-restricted posts
```

Files are saved as `<uploader>-<post-id>.<ext>`. Defaults can be set via environment
variables (see `.env.example`); CLI flags take precedence.

## Limitations

Only posts containing video or GIF media are supported; image-only posts are not.
Download only content you have the right to save.

## Development

```bash
pytest
```
