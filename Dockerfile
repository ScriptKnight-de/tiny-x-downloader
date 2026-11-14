FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/data \
    XDG_CACHE_HOME=/data/cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Defaults for container paths; override via compose/.env
ENV X_COOKIES=/config/cookies.txt \
    X_DOWNLOADER_OUTPUT_DIR=/downloads \
    X_DOWNLOADER_ARCHIVE=/data/archive.sqlite3

RUN mkdir -p /data /downloads /config && chmod 777 /data
VOLUME ["/data", "/downloads"]

ENTRYPOINT ["x-downloader"]
CMD ["daemon"]
