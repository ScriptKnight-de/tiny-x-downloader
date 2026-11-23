"""Optional alerts (Gotify, ntfy, generic webhook) for failed syncs and expiring cookies.

Configured purely through environment variables; with none set, nothing is sent.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__

APP = "tiny-x-downloader"
PREFIX = "X"
# cookie that proves you are logged in (its expiry is what we watch)
AUTH_COOKIES = ("auth_token",)
DEFAULT_WARN_DAYS = 7
TIMEOUT = 10

# gallery-dl output that means "the session is no longer valid"
AUTH_ERROR = re.compile(
    r"authrequired|authenticationerror|login required|log in|logged out|"
    r"\b401\b|\b403\b|unauthori[sz]ed|bad guest token|invalid.*cookie|cookie.*(expired|invalid)",
    re.IGNORECASE,
)


def looks_like_auth_error(line: str) -> bool:
    # only log lines that are errors/warnings, not e.g. file names containing "401"
    low = line.lower()
    return ("error" in low or "warning" in low) and bool(AUTH_ERROR.search(line))


@dataclass(frozen=True)
class Notifier:
    gotify_url: str = ""
    gotify_token: str = ""
    ntfy_url: str = ""
    ntfy_token: str = ""
    webhook_url: str = ""
    warn_days: int = DEFAULT_WARN_DAYS

    @classmethod
    def from_env(cls) -> "Notifier":
        def get(name: str) -> str:
            return os.environ.get(f"{PREFIX}_{name}", "").strip()

        try:
            days = int(get("COOKIE_WARN_DAYS") or DEFAULT_WARN_DAYS)
        except ValueError:
            days = DEFAULT_WARN_DAYS
        return cls(get("GOTIFY_URL"), get("GOTIFY_TOKEN"), get("NTFY_URL"),
                   get("NTFY_TOKEN"), get("WEBHOOK_URL"), days)

    @property
    def enabled(self) -> bool:
        return bool((self.gotify_url and self.gotify_token) or self.ntfy_url or self.webhook_url)

    def send(self, title: str, message: str, priority: int = 5) -> list[str]:
        """Deliver to every configured target; returns error strings (empty = all ok)."""
        errors: list[str] = []
        title = f"{APP}: {title}"
        jobs = []
        if self.gotify_url and self.gotify_token:
            jobs.append(("gotify", lambda: _post(
                f"{self.gotify_url.rstrip('/')}/message",
                {"title": title, "message": message, "priority": priority},
                {"X-Gotify-Key": self.gotify_token})))
        if self.ntfy_url:
            headers = {"Title": title, "Priority": str(min(5, max(1, priority // 2 + 1)))}
            if self.ntfy_token:
                headers["Authorization"] = f"Bearer {self.ntfy_token}"
            jobs.append(("ntfy", lambda: _post(self.ntfy_url, message.encode(), headers)))
        if self.webhook_url:
            jobs.append(("webhook", lambda: _post(
                self.webhook_url,
                {"app": APP, "version": __version__, "title": title,
                 "message": message, "priority": priority})))
        for name, job in jobs:
            try:
                job()
            except Exception as exc:  # never let alerting break a sync
                errors.append(f"{name}: {exc}")
        return errors


def _post(url: str, body, headers: dict[str, str] | None = None) -> None:
    if isinstance(body, bytes):
        data, ctype = body, "text/plain; charset=utf-8"
    else:
        data, ctype = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": ctype, "User-Agent": f"{APP}/{__version__}",
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        resp.read()


def cookie_expiry(cookies: Path, names=AUTH_COOKIES) -> float | None:
    """Latest expiry (unix time) of the login cookie in a Netscape cookies.txt.

    Returns None if the cookie is missing or is a session cookie (no expiry).
    """
    best = None
    try:
        text = cookies.read_text()
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw[len("#HttpOnly_"):] if raw.startswith("#HttpOnly_") else raw
        parts = line.split("\t")
        if line.startswith("#") or len(parts) < 7 or parts[5] not in names:
            continue
        try:
            exp = float(parts[4])
        except ValueError:
            continue
        if exp > 0 and (best is None or exp > best):
            best = exp
    return best


def cookie_warning(cookies: Path, warn_days: int, now: float | None = None) -> str | None:
    exp = cookie_expiry(cookies)
    if exp is None:
        return None
    left = (exp - (now if now is not None else time.time())) / 86400
    if left <= 0:
        return f"The login cookie in {cookies} has expired. Export a fresh cookies.txt."
    if left <= warn_days:
        return f"The login cookie in {cookies} expires in {left:.1f} days. Export a fresh cookies.txt soon."
    return None
