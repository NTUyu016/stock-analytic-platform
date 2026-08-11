"""單一事實來源的資料表綱要，逐字對應 docs/spec/data-model.md。

這個檔案是 Table 定義，不是 ORM mapped class——phase 0 只求綱要落地與 CHECK
齊全，ORM 映射與查詢層留給 phase 1/2 按實際需要長出來。Alembic 的 initial
migration 直接 `metadata.create_all()` 這裡的 `metadata`，兩處不重複定義一次
綱要。

⚠️ 修改這個檔案等於修改資料庫綱要，要同步回頭改 docs/spec/data-model.md，
反之亦然——README.md 的規則是「規格與程式碼衝突時以規格為準」，但兩者不該
長期不一致。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()

NUMERIC_AMOUNT = sa.Numeric(20, 8)
NUMERIC_MONEY = sa.Numeric(20, 4)

# ---------------------------------------------------------------------------
# 認證
# ---------------------------------------------------------------------------

app_user = sa.Table(
    "app_user",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("email", sa.Text, nullable=True),
    sa.Column("display_name", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)

user_identity = sa.Table(
    "user_identity",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("subject", sa.Text, nullable=False),
    sa.Column("email", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("provider", "subject", name="uq_user_identity_provider_subject"),
    sa.CheckConstraint("provider IN ('google', 'github')", name="ck_user_identity_provider"),
)

# auth.md §8.1：bootstrap 流程「先被拒、再綁定」的落地處。
# 不帶 user_id——被拒絕時系統還不知道這個身分屬於哪個 app_user。
login_attempt = sa.Table(
    "login_attempt",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("subject", sa.Text, nullable=False),
    sa.Column("email", sa.Text, nullable=True),
    sa.Column("name", sa.Text, nullable=True),
    sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("outcome", sa.Text, nullable=False),
    sa.CheckConstraint("provider IN ('google', 'github')", name="ck_login_attempt_provider"),
    sa.CheckConstraint(
        "outcome IN ('REJECTED_NO_IDENTITY', 'LINKED')", name="ck_login_attempt_outcome"
    ),
)

# session 必須落地（不可存行程記憶體）：api 走 scale-to-zero 的雲端形狀下
# 停機重啟會把記憶體裡的 session 全部丟掉；v1 本機部署雖不做 scale-to-zero，
# 但落地同時買到「可撤銷」——這是不用 JWT 的主因（auth.md §5）。
session = sa.Table(
    "session",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column(
        "user_id",
        sa.BigInteger,
        sa.ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Index("ix_session_expires_at", "expires_at"),
)

# ---------------------------------------------------------------------------
# 參考資料：標的與產業
# ---------------------------------------------------------------------------

instrument = sa.Table(
    "instrument",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("market", sa.Text, nullable=False),
    sa.Column("symbol", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("currency", sa.CHAR(3), nullable=False),
    sa.Column("instrument_type", sa.Text, nullable=False),
    sa.Column("industry_code", sa.Text, nullable=True),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.UniqueConstraint("market", "symbol", name="uq_instrument_market_symbol"),
    sa.ForeignKeyConstraint(
        ["market", "industry_code"],
        ["industry_category.market", "industry_category.industry_code"],
        name="fk_instrument_industry",
        ondelete="RESTRICT",
    ),
    sa.CheckConstraint(
        "market IN ('TWSE', 'TPEX', 'US', 'CRYPTO')", name="ck_instrument_market"
    ),
    sa.CheckConstraint(
        "instrument_type IN ('STOCK', 'ETF', 'CRYPTO')", name="ck_instrument_type"
    ),
)

instrument_provider_symbol = sa.Table(
    "instrument_provider_symbol",
    metadata,
    sa.Column(
        "instrument_id",
        sa.BigInteger,
        sa.ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("provider", sa.Text, nullable=False),
    sa.Column("provider_symbol", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("instrument_id", "provider", name="pk_instrument_provider_symbol"),
    sa.UniqueConstraint("provider", "provider_symbol", name="uq_instrument_provider_symbol"),
)

# industry_category：人工確認過的種子資料，不是每日同步的鏡像
# （analysis-dimensions.md §13.2；種子資料由 phase 8.3 的 migration 填入）。
industry_category = sa.Table(
    "industry_category",
    metadata,
    sa.Column("market", sa.Text, nullable=False),
    sa.Column("industry_code", sa.Text, nullable=False),
    sa.Column("industry_name", sa.Text, nullable=False),
    sa.Column("industry_index_name", sa.Text, nullable=True),
    sa.PrimaryKeyConstraint("market", "industry_code", name="pk_industry_category"),
    sa.CheckConstraint("market IN ('TWSE', 'TPEX')", name="ck_industry_category_market"),
)

# market_index_daily：MI_INDEX 每日快照，官方只給最新一日，回補做不到
# （data-model.md `market_index_daily`；填入時機是 phase 8.3 排程，不是本 migration）。
market_index_daily = sa.Table(
    "market_index_daily",
    metadata,
    sa.Column("index_name", sa.Text, nullable=False),
    sa.Column("trade_date", sa.Date, nullable=False),
    sa.Column("close_index", NUMERIC_AMOUNT, nullable=False),
    sa.Column("change_point", NUMERIC_AMOUNT, nullable=False),
    sa.Column("change_pct", sa.Numeric(10, 4), nullable=False),
    # 官方原始欄位「特殊處理註記」實測恆有值（無註記時為空字串，不是缺鍵）——NOT NULL 而非 nullable。
    sa.Column("special_note", sa.Text, nullable=False, server_default=""),
    sa.Column("source", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("index_name", "trade_date", name="pk_market_index_daily"),
    sa.Index("ix_market_index_daily_trade_date", "trade_date"),
)

# ---------------------------------------------------------------------------
# Portfolio 與 Transaction（唯一事實來源）
# ---------------------------------------------------------------------------

portfolio = sa.Table(
    "portfolio",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    sa.UniqueConstraint("user_id", "name", name="uq_portfolio_user_name"),
)

transaction = sa.Table(
    "transaction",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column(
        "portfolio_id",
        sa.BigInteger,
        sa.ForeignKey("portfolio.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "instrument_id",
        sa.BigInteger,
        sa.ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("type", sa.Text, nullable=False),
    sa.Column("traded_on", sa.Date, nullable=False),
    sa.Column("quantity", NUMERIC_AMOUNT, nullable=True),
    sa.Column("price", NUMERIC_AMOUNT, nullable=True),
    sa.Column("fee", NUMERIC_MONEY, nullable=True),
    sa.Column("tax", NUMERIC_MONEY, nullable=True),
    sa.Column("cash_amount", NUMERIC_MONEY, nullable=True),
    sa.Column("currency", sa.CHAR(3), nullable=False),
    sa.Column("ratio", NUMERIC_AMOUNT, nullable=True),
    sa.Column("note", sa.Text, nullable=True),
    sa.Column("external_ref", sa.Text, nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Index("ix_transaction_portfolio_instrument_traded_on", "portfolio_id", "instrument_id", "traded_on"),
    sa.Index("ix_transaction_user_traded_on", "user_id", "traded_on"),
    sa.Index(
        "uq_transaction_user_external_ref",
        "user_id",
        "external_ref",
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    ),
    sa.CheckConstraint(
        "type IN ('BUY', 'SELL', 'CASH_DIVIDEND', 'STOCK_DIVIDEND', 'SPLIT', 'ADJUSTMENT')",
        name="ck_transaction_type",
    ),
    # --- SPLIT 專屬（corporate-actions.md §1.4, §1.5）---
    sa.CheckConstraint(
        "(type = 'SPLIT') = (ratio IS NOT NULL)", name="ck_transaction_split_ratio"
    ),
    sa.CheckConstraint("ratio IS NULL OR ratio > 0", name="ck_transaction_ratio_positive"),
    sa.CheckConstraint(
        "type <> 'SPLIT' OR quantity IS NULL", name="ck_transaction_split_no_quantity"
    ),
    # --- 各型別必填/必空（data-model.md N3）---
    sa.CheckConstraint(
        "type NOT IN ('BUY', 'SELL', 'STOCK_DIVIDEND') OR quantity IS NOT NULL",
        name="ck_transaction_quantity_required",
    ),
    sa.CheckConstraint(
        "type IN ('BUY', 'SELL', 'STOCK_DIVIDEND', 'ADJUSTMENT') OR quantity IS NULL",
        name="ck_transaction_quantity_forbidden",
    ),
    sa.CheckConstraint(
        "type NOT IN ('BUY', 'SELL') OR price IS NOT NULL", name="ck_transaction_price_required"
    ),
    sa.CheckConstraint(
        "type IN ('BUY', 'SELL', 'ADJUSTMENT') OR price IS NULL",
        name="ck_transaction_price_forbidden",
    ),
    sa.CheckConstraint(
        "type <> 'CASH_DIVIDEND' OR cash_amount IS NOT NULL",
        name="ck_transaction_cash_amount_required",
    ),
    sa.CheckConstraint(
        "type IN ('CASH_DIVIDEND', 'ADJUSTMENT') OR cash_amount IS NULL",
        name="ck_transaction_cash_amount_forbidden",
    ),
    sa.CheckConstraint(
        "type <> 'ADJUSTMENT' OR note IS NOT NULL", name="ck_transaction_note_required"
    ),
)

# ---------------------------------------------------------------------------
# 日線與匯率
# ---------------------------------------------------------------------------

daily_close = sa.Table(
    "daily_close",
    metadata,
    sa.Column(
        "instrument_id",
        sa.BigInteger,
        sa.ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("trade_date", sa.Date, nullable=False),
    sa.Column("open", NUMERIC_AMOUNT, nullable=False),
    sa.Column("high", NUMERIC_AMOUNT, nullable=False),
    sa.Column("low", NUMERIC_AMOUNT, nullable=False),
    sa.Column("close", NUMERIC_AMOUNT, nullable=False),
    sa.Column("prev_close", NUMERIC_AMOUNT, nullable=True),
    sa.Column("volume", sa.BigInteger, nullable=False),
    sa.Column("source", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("instrument_id", "trade_date", name="pk_daily_close"),
)

exchange_rate = sa.Table(
    "exchange_rate",
    metadata,
    sa.Column("currency", sa.CHAR(3), nullable=False),
    sa.Column("rate_date", sa.Date, nullable=False),
    sa.Column("cash_buy", NUMERIC_AMOUNT, nullable=False),
    sa.Column("cash_sell", NUMERIC_AMOUNT, nullable=False),
    sa.Column("spot_buy", NUMERIC_AMOUNT, nullable=False),
    sa.Column("spot_sell", NUMERIC_AMOUNT, nullable=False),
    # generated column：口徑定為即期中價，見 data-model.md exchange_rate 修訂欄。
    sa.Column(
        "rate",
        NUMERIC_AMOUNT,
        sa.Computed("(spot_buy + spot_sell) / 2", persisted=True),
    ),
    sa.Column("source", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("currency", "rate_date", name="pk_exchange_rate"),
    sa.CheckConstraint(
        "spot_buy > 0 AND spot_sell > 0", name="ck_exchange_rate_spot_positive"
    ),
)

benchmark_series = sa.Table(
    "benchmark_series",
    metadata,
    sa.Column("benchmark_code", sa.Text, nullable=False),
    sa.Column("trade_date", sa.Date, nullable=False),
    sa.Column("index_value", NUMERIC_AMOUNT, nullable=False),
    sa.Column("source", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("benchmark_code", "trade_date", name="pk_benchmark_series"),
)

# ---------------------------------------------------------------------------
# 警示
# ---------------------------------------------------------------------------

alert = sa.Table(
    "alert",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column(
        "instrument_id",
        sa.BigInteger,
        sa.ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "portfolio_id",
        sa.BigInteger,
        sa.ForeignKey("portfolio.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    sa.Column("rule_type", sa.Text, nullable=False),
    sa.Column("threshold", NUMERIC_AMOUNT, nullable=False),
    sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.CheckConstraint(
        "rule_type IN ("
        "'PRICE_ABOVE', 'PRICE_BELOW', "
        "'CHANGE_PCT_ABOVE', 'CHANGE_PCT_BELOW', "
        "'RETURN_PCT_ABOVE', 'RETURN_PCT_BELOW', "
        "'TRAILING_STOP', 'VOLUME_SPIKE', 'EX_DIVIDEND_AHEAD'"
        ")",
        name="ck_alert_rule_type",
    ),
    # 依部位的規則（成本報酬率、追蹤停損）必須有 portfolio_id；純價格規則必須為 NULL。
    sa.CheckConstraint(
        "(rule_type IN ('RETURN_PCT_ABOVE', 'RETURN_PCT_BELOW', 'TRAILING_STOP')) "
        "= (portfolio_id IS NOT NULL)",
        name="ck_alert_portfolio_scoped",
    ),
)

alert_state = sa.Table(
    "alert_state",
    metadata,
    sa.Column(
        "alert_id",
        sa.BigInteger,
        sa.ForeignKey("alert.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("is_armed", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("peak_price", NUMERIC_AMOUNT, nullable=True),
    sa.Column("peak_since", sa.Date, nullable=True),
    sa.Column("suspended_reason", sa.Text, nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)

notification = sa.Table(
    "notification",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column(
        "alert_id", sa.BigInteger, sa.ForeignKey("alert.id", ondelete="RESTRICT"), nullable=True
    ),
    sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("channel", sa.Text, nullable=False),
    sa.Column("payload", pg.JSONB, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
    sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_error", sa.Text, nullable=True),
    sa.CheckConstraint(
        "status IN ('PENDING', 'SENT', 'FAILED', 'ABANDONED')", name="ck_notification_status"
    ),
)

# ---------------------------------------------------------------------------
# 公司行動與對帳
# ---------------------------------------------------------------------------

pending_action = sa.Table(
    "pending_action",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column(
        "instrument_id",
        sa.BigInteger,
        sa.ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    sa.Column(
        "portfolio_id",
        sa.BigInteger,
        sa.ForeignKey("portfolio.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("notified_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("effective_on", sa.Date, nullable=True),
    sa.Column("proposed", pg.JSONB, nullable=False),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.CheckConstraint(
        "kind IN ('CORPORATE_ACTION', 'IMPORT_CONFLICT')", name="ck_pending_action_kind"
    ),
    # CORPORATE_ACTION 必填 portfolio_id（corporate-actions.md §4.6；transaction.portfolio_id 是 NOT NULL）。
    sa.CheckConstraint(
        "kind <> 'CORPORATE_ACTION' OR portfolio_id IS NOT NULL",
        name="ck_pending_action_corporate_action_portfolio",
    ),
)

reconciliation = sa.Table(
    "reconciliation",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column(
        "user_id", sa.BigInteger, sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("as_of_date", sa.Date, nullable=False),
    sa.Column("is_balanced", sa.Boolean, nullable=False),
    sa.Column("differences", pg.JSONB, nullable=False),
)
