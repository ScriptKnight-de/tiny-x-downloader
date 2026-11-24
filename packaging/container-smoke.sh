#!/usr/bin/env bash
# Smoke test for the container image: start it with the same hardening as docker-compose.yml
# and check that it really works under those restrictions.
#
#   packaging/container-smoke.sh IMAGE      e.g.  packaging/container-smoke.sh tiny-x-smoke:ci
#
# Needs a working `docker`. It uses throwaway named volumes (not bind mounts, so it also works
# against a remote Docker daemon) and removes everything it creates. It never touches the network
# and uses an invented cookie file.
set -euo pipefail

IMG=${1:?usage: container-smoke.sh IMAGE}
id=tiny-x-smoke-$$
cfg=$id-config data=$id-data dl=$id-downloads
fail=0

# The same restrictions as docker-compose.yml (user, read-only rootfs, no capabilities, no new privileges).
HARDEN=(--user 1000:1000 --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true)
MOUNTS=(-v "$cfg":/config:ro -v "$data":/data -v "$dl":/downloads)

cleanup() {
  docker rm -f "$id" >/dev/null 2>&1 || true
  docker volume rm -f "$cfg" "$data" "$dl" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ok()   { echo "ok    $1"; }
bad()  { echo "FAIL  $1"; fail=1; }
# check "description" command...   (passes when the command succeeds)
check() { local what=$1; shift; if "$@" >/dev/null 2>&1; then ok "$what"; else bad "$what"; fi; }
# refuse "description" command...  (passes when the command fails)
refuse() { local what=$1; shift; if "$@" >/dev/null 2>&1; then bad "$what"; else ok "$what"; fi; }
run() { docker run --rm "${HARDEN[@]}" "${MOUNTS[@]}" "$@"; }

for v in "$cfg" "$data" "$dl"; do docker volume create "$v" >/dev/null; done
# An invented, empty Netscape cookie file, written as root (the compose setup mounts it read-only).
docker run --rm --user 0 -v "$cfg":/config --entrypoint sh "$IMG" \
  -c 'printf "# Netscape HTTP Cookie File\n" > /config/cookies.txt && chmod 644 /config/cookies.txt'

echo "== image: $IMG"
version=$(run "$IMG" --version 2>&1 || true)
case "$version" in "tiny-x-downloader "[0-9]*) ok "--version prints '$version'" ;; *) bad "--version printed '$version'" ;; esac
check "--help works" run "$IMG" --help

echo "== hardening is actually applied"
[ "$(run --entrypoint id "$IMG" -u)" = 1000 ] && ok "runs as uid 1000, not root" || bad "does not run as uid 1000"
refuse "root filesystem is read-only"        run --entrypoint sh "$IMG" -c 'touch /probe'
refuse "/config is mounted read-only"        run --entrypoint sh "$IMG" -c 'touch /config/probe'
check  "/tmp (tmpfs) is writable"            run --entrypoint sh "$IMG" -c 'touch /tmp/probe'
check  "no capabilities (CapEff is zero)"    run --entrypoint sh "$IMG" -c 'grep -q "^CapEff:[[:space:]]*0*$" /proc/self/status'
check  "no-new-privileges is set"            run --entrypoint sh "$IMG" -c 'grep -q "^NoNewPrivs:[[:space:]]*1" /proc/self/status'

echo "== the app can do its writes under those restrictions"
check "/data and /downloads are writable by the app user" \
  run --entrypoint sh "$IMG" -c 'touch /data/probe /downloads/probe'
check "archive database and atomic state file can be written in /data" \
  run --entrypoint python "$IMG" -c '
import os, sqlite3, tempfile
db = sqlite3.connect("/data/archive.sqlite3"); db.execute("create table if not exists t(a)"); db.commit(); db.close()
fd, tmp = tempfile.mkstemp(dir="/data", prefix="state.", suffix=".tmp"); os.close(fd)
os.replace(tmp, "/data/state.json")'
check "cache directory under /data is writable (XDG_CACHE_HOME)" \
  run --entrypoint sh "$IMG" -c 'mkdir -p "$XDG_CACHE_HOME" && touch "$XDG_CACHE_HOME/probe"'

echo "== daemon starts and stops cleanly on SIGTERM (docker stop)"
docker run -d --name "$id" "${HARDEN[@]}" "${MOUNTS[@]}" -e X_RUN_ON_START=false "$IMG" daemon >/dev/null
started=0
for _ in $(seq 1 30); do
  logs=$(docker logs "$id" 2>&1 || true)   # not piped into grep -q: SIGPIPE + pipefail gives false negatives
  if grep -q "next sync at" <<<"$logs"; then started=1; break; fi
  [ "$(docker inspect -f '{{.State.Running}}' "$id")" = true ] || break
  sleep 1
done
[ "$started" = 1 ] && ok "daemon is running and scheduled the next sync" || { bad "daemon did not start"; docker logs "$id" 2>&1 | tail -5 || true; }
t0=$SECONDS
docker stop -t 15 "$id" >/dev/null 2>&1 || true
took=$((SECONDS - t0))
code=$(docker inspect -f '{{.State.ExitCode}}' "$id" 2>/dev/null || echo "?")
[ "$code" = 0 ] && ok "exit code 0 after docker stop" || bad "exit code $code after docker stop (137 = killed, SIGTERM ignored)"
[ "$took" -lt 10 ] && ok "stopped within ${took}s" || bad "stop took ${took}s"
logs=$(docker logs "$id" 2>&1 || true)
grep -q "^stopping" <<<"$logs" && ok "logged 'stopping'" || bad "no 'stopping' line in the log"

echo
if [ "$fail" = 0 ]; then echo "container smoke test: all checks passed"; else echo "container smoke test: FAILED"; fi
exit "$fail"
