"""不需要真的 Postgres 的 smoke test：驗證綱要定義本身是自洽的。

真正的 DDL 落地（含 JSONB、Computed column、partial index 這些 Postgres 專屬
語法）需要真的 Postgres，那些留給 phase 0.4 的 Alembic migration 對照
docker compose 裡的資料庫實測，不在這裡用 SQLite 假驗證出一個假結果。
"""

from __future__ import annotations

from core import db_schema

EXPECTED_TABLES = {
    "app_user",
    "user_identity",
    "login_attempt",
    "session",
    "instrument",
    "instrument_provider_symbol",
    "industry_category",
    "market_index_daily",
    "portfolio",
    "transaction",
    "daily_close",
    "exchange_rate",
    "benchmark_series",
    "alert",
    "alert_state",
    "notification",
    "pending_action",
    "reconciliation",
}


def test_all_data_model_tables_are_defined() -> None:
    assert set(db_schema.metadata.tables.keys()) == EXPECTED_TABLES


def test_transaction_type_check_matches_enum() -> None:
    from core.enums import TransactionType

    checks = {
        c.name: str(c.sqltext) for c in db_schema.transaction.constraints if hasattr(c, "sqltext")
    }
    type_check = checks["ck_transaction_type"]
    for member in TransactionType:
        assert f"'{member.value}'" in type_check


def test_alert_rule_type_check_has_nine_values() -> None:
    from core.enums import AlertRuleType

    checks = {c.name: str(c.sqltext) for c in db_schema.alert.constraints if hasattr(c, "sqltext")}
    rule_check = checks["ck_alert_rule_type"]
    assert len(list(AlertRuleType)) == 9
    for member in AlertRuleType:
        assert f"'{member.value}'" in rule_check


def test_split_ratio_check_is_bidirectional() -> None:
    """corporate-actions.md §1.4：不可寫成單向（type<>'SPLIT' OR ratio IS NOT NULL）。"""
    checks = {c.name: str(c.sqltext) for c in db_schema.transaction.constraints if hasattr(c, "sqltext")}
    assert checks["ck_transaction_split_ratio"] == "(type = 'SPLIT') = (ratio IS NOT NULL)"
