"""行情訂閱、重連、扇出的進入點（phase 5 才長出實際邏輯）。

realtime-quotes.md §2：`quote-worker` 直接 import provider SDK，不跑本機 HTTP
sidecar；callback 不在 event loop 上，只能 `loop.call_soon_threadsafe(...)`。
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError("quote_worker：phase 5 實作")


if __name__ == "__main__":
    main()
