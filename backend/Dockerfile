FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# The shared auth library is an editable path dependency (../oqtopus-auth) that
# lives outside this build context. Bring only its build inputs in from the
# BuildKit additional context ("oqtopus_auth") so local .git/.venv contents are
# neither transferred into the build nor copied into the image. For real image
# builds, replace this path source with a published/pinned oqtopus-auth.
COPY --from=oqtopus_auth pyproject.toml README.md LICENSE /oqtopus-auth/
COPY --from=oqtopus_auth src /oqtopus-auth/src

COPY . /app

RUN uv sync --frozen

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
