# ---- Build stage: install dependencies into a self-contained venv ----
FROM python:3.12-slim-bookworm AS build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /tmp/requirements.txt

# ---- Final stage: runtime only ----
FROM python:3.12-slim-bookworm

# Patch OS packages at build time.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin where

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WHERE_DATA_DIR=/data \
    WHERE_PORT=8080

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY run.py VERSION ./

RUN mkdir -p /data && chown -R 1000:1000 /data /app

# Deliberately no USER line. The container starts as root, hands /data to user
# 1000 if a fresh bind mount arrived owned by somebody else, and then drops to
# user 1000 for good before it serves anything (see app/bootstrap.py). That is
# what lets "docker compose up -d" work on a new host with no chown first.
# Setting `user: "1000:1000"` in compose also works: the handover is skipped
# and the folder has to be owned correctly already.
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=8)" || exit 1

CMD ["python", "run.py"]
