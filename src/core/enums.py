"""交易類型、規則類型等具名列舉。

單一事實來源：這裡定義的字串必須與 docs/spec/data-model.md 的 CHECK 約束逐字相同，
且 Alembic migration 的列舉值必須從這裡讀出，不得在兩處各自維護一份。
"""

from __future__ import annotations

from enum import StrEnum


class TransactionType(StrEnum):
    """data-model.md `transaction.type`。

    ⚠️ 所有依此列舉分支的程式碼必須是窮舉式的（match + case _: raise），
    不得有靜默的 fall-through 或 else: pass（corporate-actions.md §1.7）。
    """

    BUY = "BUY"
    SELL = "SELL"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    SPLIT = "SPLIT"
    ADJUSTMENT = "ADJUSTMENT"


class InstrumentMarket(StrEnum):
    TWSE = "TWSE"
    TPEX = "TPEX"
    US = "US"
    CRYPTO = "CRYPTO"


class InstrumentType(StrEnum):
    """⚠️ 不得由反查自動決定——決定證交稅是 0.3% 還是 0.1%（transaction-input.md §5）。"""

    STOCK = "STOCK"
    ETF = "ETF"
    CRYPTO = "CRYPTO"


class AlertRuleType(StrEnum):
    """alerts.md §1：六種具名類別、展開為九個列舉值。"""

    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    CHANGE_PCT_ABOVE = "CHANGE_PCT_ABOVE"
    CHANGE_PCT_BELOW = "CHANGE_PCT_BELOW"
    RETURN_PCT_ABOVE = "RETURN_PCT_ABOVE"
    RETURN_PCT_BELOW = "RETURN_PCT_BELOW"
    TRAILING_STOP = "TRAILING_STOP"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    EX_DIVIDEND_AHEAD = "EX_DIVIDEND_AHEAD"


#: 依部位的規則必須有 portfolio_id；純價格規則必須為 NULL（data-model.md `alert`）。
PORTFOLIO_SCOPED_RULE_TYPES = frozenset(
    {AlertRuleType.RETURN_PCT_ABOVE, AlertRuleType.RETURN_PCT_BELOW, AlertRuleType.TRAILING_STOP}
)


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class PendingActionKind(StrEnum):
    CORPORATE_ACTION = "CORPORATE_ACTION"
    IMPORT_CONFLICT = "IMPORT_CONFLICT"


class LoginAttemptOutcome(StrEnum):
    """auth.md §8.1：login_attempt 稽核表。"""

    REJECTED_NO_IDENTITY = "REJECTED_NO_IDENTITY"
    LINKED = "LINKED"


class IdentityProvider(StrEnum):
    GOOGLE = "google"
    GITHUB = "github"
