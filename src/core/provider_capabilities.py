"""行情 provider 的能力宣告。

硬性規則（tech-stack.md §4、realtime-quotes.md §2）：
`src/core/` 內不得出現字面量 `5`，也不得自行把 slot 換算成檔數。所有「是否超過
訂閱額度」的判斷一律是 `adapter.slots_needed(...) <= capabilities.max_subscription_slots`。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderCapabilities:
    max_subscription_slots: int
    max_connections: int
    supports_symbol_quote: bool
    supports_market_snapshot: bool
    supports_odd_lot: bool


class QuoteAdapter(Protocol):
    """每個 provider adapter 必須實作額度換算，核心不得自己算。"""

    capabilities: ProviderCapabilities

    def slots_needed(self, symbols: Sequence[str], channels: Sequence[str]) -> int:
        """換算這個訂閱計畫需要幾個 slot。Fugle: len(symbols)*len(channels)；Shioaji: len(symbols)。"""
        ...
