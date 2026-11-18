# tiny-x-downloader

Daily sync of the **images and videos** from the posts you **liked** and **bookmarked** on X (Twitter).
Built on [gallery-dl](https://github.com/mikf/gallery-dl).

[![Support me on Ko-fi](assets/kofi/support_me_on_kofi_blue.png)](https://ko-fi.com/scriptknight)

## How "already downloaded" works

Every downloaded file is recorded (post id + media index) in an SQLite archive that lives
**outside** the output folder (default `~/.local/share/tiny-x-downloader/archive.sqlite3`).
Because the memory is independent of the files, you can move, rename or delete downloaded
content freely and it will never be fetched again. Don't delete the archive.

- First run per source (likes / bookmarks): full backfill of the whole timeline.
- Later runs: newest-first scan that stops after 30 consecutive already-known files.
  Use `--full` to force a complete rescan.

## Docker (recommended)

```bash
cp .env.example .env                  # set PUID/PGID (id -u / id -g), TZ, X_SYNC_TIME
mkdir -p config data downloads        # create as your user, otherwise Docker creates them as root
cp /path/to/cookies.txt config/cookies.txt && chmod 600 config/cookies.txt
docker compose up -d --build         # build locally ...
# ... or use the image published by the Forgejo workflow (see "CI image" below):
# docker login forgejo.scriptknight.de && docker compose pull && docker compose up -d
docker compose logs -f
```

The container runs `tiny-x-downloader daemon`: it syncs once per day at `X_SYNC_TIME` (local time
per `TZ`) and keeps running if a sync fails (e.g. expired cookies, replace the file and the
next run picks it up). Set `X_RUN_ON_START=true` to also sync right after start.

| Host path (default) | Container | Purpose |
|---|---|---|
| `./config/cookies.txt` | `/config/cookies.txt` (ro) | your x.com session cookies |
| `./data` | `/data` | archive DB + state: **keep this**, it is the memory of what was downloaded |
| `./downloads` | `/downloads` | media (`likes/`, `bookmarks/`); move files out freely |

One-off commands: `docker compose run --rm tiny-x-downloader sync --dry-run`.

## Desktop app (GUI + AppImage)

`tiny-x-downloader gui` opens a small window: enter your cookies file, download folder and
archive location, press **Sync now** (or **Dry run**), and watch the current file, counters and
the log. Settings are saved to `~/.config/tiny-x-downloader/env`. An optional daily sync runs while
the window is open.

Build a self-contained AppImage (bundles Python + Tk, x86_64 only):

```bash
./packaging/build-appimage.sh      # -> dist/tiny-x-downloader-<version>-x86_64.AppImage
chmod +x dist/*.AppImage && ./dist/tiny-x-downloader-*.AppImage          # opens the GUI
./dist/tiny-x-downloader-*.AppImage sync --dry-run                       # CLI use works too
```

The script downloads a pinned python-build-standalone and appimagetool and verifies their SHA-256.

## CI image

`.forgejo/workflows/build.yml` runs the tests, then builds the Alpine-based image
(`linux/amd64` + `linux/arm64`) and pushes it to
`forgejo.scriptknight.de/scriptknight/tiny-x-downloader` on every push to `main`
(`latest`, `sha-<short>`) and on `v*` tags (`1.2.3`, `1.2`).

Setup once: add repository secrets `REGISTRY_USER` (your Forgejo user) and `REGISTRY_TOKEN`
(access token with the `write:package` scope), and make sure a Forgejo runner with the label
`docker` and Docker access is registered.

## Without Docker

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate   # or: uv venv && uv pip install -e .
pip install -e .
mkdir -p ~/.config/tiny-x-downloader
cp .env.example ~/.config/tiny-x-downloader/env      # edit: paths
```

X has no free API for likes/bookmarks, so this reads them with your logged-in browser session:
export your x.com cookies as Netscape `cookies.txt` (e.g. with a "Get cookies.txt" browser
extension) to the path in `X_COOKIES`. Keep that file private (`chmod 600`). Cookies expire
or get invalidated now and then; if a run reports `AuthRequired`, export fresh ones.
Automated access may conflict with X's terms; use your own account, at your own risk.

## Usage

```bash
tiny-x-downloader sync --dry-run          # list what would be downloaded
tiny-x-downloader sync                    # likes + bookmarks
tiny-x-downloader sync --source bookmarks
tiny-x-downloader install-timer --time 04:00   # daily systemd user timer (runs missed jobs, Persistent=true)
```

Output: `<output dir>/likes/` and `<output dir>/bookmarks/`, files named
`<author>_<post-id>_<n>.<ext>`.

Settings come from environment variables, `./.env` or `~/.config/tiny-x-downloader/env`
(see `.env.example`).

## Development

```bash
pip install -e ".[dev]" && pytest
```

## Support

tiny-x-downloader is free and open source. If it is useful to you, you can support its
development on [Ko-fi](https://ko-fi.com/scriptknight), see also [DONATE.md](DONATE.md).
The same info is built into the tools: `tiny-x-downloader donate`, the **Support on Ko-fi**
button in the GUI/AppImage, the daemon start-up log and the Docker image
(`/usr/share/doc/tiny-x-downloader/DONATE.md`).
