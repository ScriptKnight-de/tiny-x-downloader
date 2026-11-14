# x-downloader

Daily sync of the **images and videos** from the posts you **liked** and **bookmarked** on X (Twitter).
Built on [gallery-dl](https://github.com/mikf/gallery-dl).

## How "already downloaded" works

Every downloaded file is recorded (post id + media index) in an SQLite archive that lives
**outside** the output folder (default `~/.local/share/x-downloader/archive.sqlite3`).
Because the memory is independent of the files, you can move, rename or delete downloaded
content freely and it will never be fetched again. Don't delete the archive.

- First run per source (likes / bookmarks): full backfill of the whole timeline.
- Later runs: newest-first scan that stops after 30 consecutive already-known files.
  Use `--full` to force a complete rescan.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate   # or: uv venv && uv pip install -e .
pip install -e .
mkdir -p ~/.config/x-downloader
cp .env.example ~/.config/x-downloader/env      # edit: X_USERNAME, paths
```

X has no free API for likes/bookmarks, so this reads them with your logged-in browser session:
export your x.com cookies as Netscape `cookies.txt` (e.g. with a "Get cookies.txt" browser
extension) to the path in `X_COOKIES`. Keep that file private (`chmod 600`). Cookies expire
or get invalidated now and then; if a run reports `AuthRequired`, export fresh ones.
Automated access may conflict with X's terms; use your own account, at your own risk.

## Usage

```bash
x-downloader sync --dry-run          # list what would be downloaded
x-downloader sync                    # likes + bookmarks
x-downloader sync --source bookmarks
x-downloader install-timer --time 04:00   # daily systemd user timer (runs missed jobs, Persistent=true)
```

Output: `<output dir>/likes/` and `<output dir>/bookmarks/`, files named
`<author>_<post-id>_<n>.<ext>`.

Settings come from environment variables, `./.env` or `~/.config/x-downloader/env`
(see `.env.example`).

## Development

```bash
pip install -e ".[dev]" && pytest
```
