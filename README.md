# stock-analytic-platform

個人台股持股儀表板。規格見 [`docs/spec/README.md`](docs/spec/README.md)——所有設計決策與「為什麼」都在那裡，這份 README 只講怎麼跑起來。

## 開發環境

- **後端**：Python 3.13 + [uv](https://docs.astral.sh/uv/)。PATH 上的 `python`／`py` 若是 Microsoft Store 假殼，一律用 `uv run` 執行。
- **前端**：Node 22 + Vite + React。
- **資料庫**：PostgreSQL 17（`postgres:17-bookworm`，見 [`docs/spec/deployment.md`](docs/spec/deployment.md) §3 為什麼釘死這個版本）。
- **部署**：WSL2 + Docker Engine（不是 Docker Desktop）+ Tailscale，見 `docs/spec/deployment.md`。

## 本機起手式

```bash
# 後端
uv sync
cp .env.example .env   # 依需要填值；不進版控

# 資料庫（本機測試用，正式跑法見 compose.yaml）
docker compose up -d db
uv run alembic upgrade head

uv run pytest
uv run ruff check src tests
uv run mypy src

# 前端
cd frontend
npm install
npm run dev
```

## 全套（含反向代理）

```bash
docker compose up -d db api caddy
# 盤中要測即時報價：
docker compose --profile intraday up -d quote-worker
```

## 目錄

```
src/
├── core/          # 領域模型、資料表綱要、adapter 共用邏輯
├── api/           # FastAPI 應用
└── quote_worker/  # 行情訂閱、重連、扇出（可選元件）
frontend/          # React + Vite，純靜態 SPA
alembic/           # 資料庫 migration，src/core/db_schema.py 是綱要的單一事實來源
docs/spec/         # 規格（先讀 docs/spec/README.md）
docs/research/      docs/briefing/   # 決策依據，不可據以實作
```
