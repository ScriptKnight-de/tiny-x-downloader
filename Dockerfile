FROM python:3.13-alpine

LABEL org.opencontainers.image.title="tiny-x-downloader" \
      org.opencontainers.image.description="Daily sync of media from liked and bookmarked X posts" \
      org.opencontainers.image.source="https://forgejo.scriptknight.de/scriptknight/tiny-x-downloader" \
      org.opencontainers.image.authors="ScriptKnight" \
      de.scriptknight.donate="https://ko-fi.com/scriptknight"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/data \
    XDG_CACHE_HOME=/data/cache

RUN apk add --no-cache tzdata ca-certificates

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . && rm -rf /app/src /root/.cache

# Defaults for container paths; override via compose/.env
ENV X_COOKIES=/config/cookies.txt \
    TINY_X_DOWNLOADER_OUTPUT_DIR=/downloads \
    TINY_X_DOWNLOADER_ARCHIVE=/data/archive.sqlite3

COPY DONATE.md /usr/share/doc/tiny-x-downloader/DONATE.md

RUN mkdir -p /data /downloads /config && chmod 777 /data
VOLUME ["/data", "/downloads"]

ENTRYPOINT ["tiny-x-downloader"]
CMD ["daemon"]
