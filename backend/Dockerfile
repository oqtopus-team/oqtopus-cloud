FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY . /app

RUN uv sync --frozen

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
