# tech-stack.md §9：base image 必須是 Debian，不可以用 Alpine。
# shioaji 發布的是 manylinux（glibc）wheel，Alpine 用 musl 裝不起來。
FROM python:3.13-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# deployment.md §4.2.1：容器一律 TZ=UTC，所有「哪一天」在應用層顯式換算 Asia/Taipei。

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ src/

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# 兩個部署單元共用同一個 image；compose.yaml 用 command 覆蓋進入點
# （tech-stack.md §4：quote-worker 是可選元件，api 不對它有任何 import 依賴）。
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
