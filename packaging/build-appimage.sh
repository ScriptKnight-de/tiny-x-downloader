#!/usr/bin/env bash
# Build dist/tiny-x-downloader-<version>-x86_64.AppImage
# Bundles a relocatable CPython (with Tk) + the app. Needs: bash, curl, tar, sha256sum.
# Both downloads are pinned to a version and verified against a SHA-256 below.
set -euo pipefail

PBS_TAG=20261110
PBS_FILE="cpython-3.13.18+${PBS_TAG}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
PBS_SHA256=f2d2199eb25880e07863b391cf7124e7ffa1338b0d65600dfcec117c4223a7fb
AIT_VERSION=1.9.1
AIT_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/appimage"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)"
OUT="$ROOT/dist/tiny-x-downloader-${VERSION}-x86_64.AppImage"

fetch() { # url file sha256
    if [ ! -f "$2" ] || ! echo "$3  $2" | sha256sum -c --quiet 2>/dev/null; then
        curl -fsSL "$1" -o "$2"
        echo "$3  $2" | sha256sum -c --quiet
    fi
}

mkdir -p "$BUILD/cache" "$ROOT/dist"
rm -rf "$BUILD/AppDir"
mkdir -p "$BUILD/AppDir/opt"

fetch "https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${PBS_FILE//+/%2B}" \
      "$BUILD/cache/python.tar.gz" "$PBS_SHA256"
fetch "https://github.com/AppImage/appimagetool/releases/download/${AIT_VERSION}/appimagetool-x86_64.AppImage" \
      "$BUILD/cache/appimagetool" "$AIT_SHA256"
chmod +x "$BUILD/cache/appimagetool"

tar -xzf "$BUILD/cache/python.tar.gz" -C "$BUILD/AppDir/opt"      # -> opt/python
PY="$BUILD/AppDir/opt/python/bin/python3"
"$PY" -m pip install --quiet --no-warn-script-location --no-cache-dir "$ROOT"
"$PY" -c "import tkinter, gallery_dl, tiny_x_downloader"                 # sanity check
find "$BUILD/AppDir/opt/python" -name __pycache__ -type d -prune -exec rm -rf {} +

install -m755 "$ROOT/packaging/AppRun" "$BUILD/AppDir/AppRun"
install -m644 "$ROOT/packaging/tiny-x-downloader.desktop" "$BUILD/AppDir/tiny-x-downloader.desktop"
install -m644 "$ROOT/packaging/tiny-x-downloader.svg" "$BUILD/AppDir/tiny-x-downloader.svg"
install -Dm644 "$ROOT/DONATE.md" "$BUILD/AppDir/usr/share/doc/tiny-x-downloader/DONATE.md"
install -Dm644 "$ROOT/packaging/tiny-x-downloader.desktop" \
    "$BUILD/AppDir/usr/share/applications/tiny-x-downloader.desktop"
install -Dm644 "$ROOT/packaging/tiny-x-downloader.appdata.xml" \
    "$BUILD/AppDir/usr/share/metainfo/tiny-x-downloader.appdata.xml"
ln -sf tiny-x-downloader.svg "$BUILD/AppDir/.DirIcon"

ARCH=x86_64 "$BUILD/cache/appimagetool" --appimage-extract-and-run --no-appstream "$BUILD/AppDir" "$OUT"
echo "built: $OUT"
