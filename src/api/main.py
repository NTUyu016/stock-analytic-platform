"""FastAPI 應用進入點。

`quote-worker` 是可選元件（tech-stack.md §4）：這個 app 必須能在它完全不存在
時正常啟動與運作，本檔案不對 quote_worker 有任何 import 依賴。
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="stock-analytic-platform api")


@app.get("/api/health")
async def health() -> dict[str, str]:
    """未登入可存取。⚠️ 只能回不含即時報價的靜態資訊（tech-stack.md §8 硬性規則）。"""
    return {"status": "ok"}
