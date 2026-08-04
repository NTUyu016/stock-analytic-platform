# -*- coding: utf-8 -*-
"""
丟棄式 benchmark：驗證 issue #16 待決事項 1（快照 vs 重算）的實際成本。
不進 repo。用 pgserver 起一個真的 PostgreSQL 16。

情境依 data-model.md 與 #19：
  - 10 支標的 x 10 年 daily_close ~= 2.5 萬列
  - 交易量 150 筆/年 -> 10 年 1500 筆
  - 8 支 TWD、2 支 USD（測多幣別換算）
"""
import json
import pathlib
import random
import statistics
import sys
import tempfile
import time

import pgserver
import psycopg

random.seed(20260804)

OUT = []


def log(s=""):
    print(s)
    OUT.append(s)


def timeit(conn, sql, params=None, n=15, fetch=True):
    lat = []
    rows = None
    for i in range(n):
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() if fetch else None
        lat.append((time.perf_counter() - t0) * 1000)
    return lat, rows


def stats(lat):
    lat_sorted = sorted(lat)
    return {
        "min": lat_sorted[0],
        "p50": statistics.median(lat_sorted),
        "p95": lat_sorted[int(len(lat_sorted) * 0.95) - 1],
        "max": lat_sorted[-1],
    }


def fmt(name, lat, nrows=None):
    s = stats(lat)
    extra = f"  rows={nrows}" if nrows is not None else ""
    log(
        f"{name:<52} min={s['min']:7.2f}ms  p50={s['p50']:7.2f}ms  "
        f"p95={s['p95']:7.2f}ms  max={s['max']:7.2f}ms{extra}"
    )
    return s


DDL = """
DROP TABLE IF EXISTS "transaction", daily_close, exchange_rate, instrument CASCADE;

CREATE TABLE instrument (
  id bigserial PRIMARY KEY,
  market text, symbol text, name text,
  currency char(3), instrument_type text, is_active boolean DEFAULT true
);

CREATE TABLE daily_close (
  instrument_id bigint NOT NULL,
  trade_date date NOT NULL,
  close numeric(20,8) NOT NULL,
  prev_close numeric(20,8),
  source text,
  PRIMARY KEY (instrument_id, trade_date)
);

CREATE TABLE exchange_rate (
  currency char(3) NOT NULL,
  rate_date date NOT NULL,
  rate numeric(20,8) NOT NULL,
  PRIMARY KEY (currency, rate_date)
);

CREATE TABLE "transaction" (
  id bigserial PRIMARY KEY,
  user_id bigint NOT NULL,
  portfolio_id bigint NOT NULL,
  instrument_id bigint NOT NULL,
  type text NOT NULL,
  traded_on date NOT NULL,
  quantity numeric(20,8),
  price numeric(20,8),
  fee numeric(20,4) DEFAULT 0,
  tax numeric(20,4) DEFAULT 0,
  cash_amount numeric(20,4),
  currency char(3),
  note text,
  external_ref text,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX tx_pit ON "transaction" (portfolio_id, instrument_id, traded_on);
CREATE INDEX tx_ut  ON "transaction" (user_id, traded_on);
"""


def trading_days(start_year, years):
    """近似交易日：週一到週五，扣掉每年約 13 天假期。"""
    import datetime as dt

    days = []
    d = dt.date(start_year, 1, 1)
    end = dt.date(start_year + years, 1, 1)
    holidays = set()
    for y in range(start_year, start_year + years + 1):
        # 粗略假期：農曆年 6 天 + 其他 7 天，用固定日期近似
        for m, dd in [(1, 1), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5),
                      (4, 4), (5, 1), (6, 10), (9, 20), (10, 10), (1, 2), (2, 28)]:
            holidays.add(dt.date(y, m, dd))
    while d < end:
        if d.weekday() < 5 and d not in holidays:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def seed(conn, n_instruments=10, years=10, tx_per_year=150, start_year=2016):
    days = trading_days(start_year, years)
    with conn.cursor() as cur:
        cur.execute(DDL)
        # 8 支 TWD + 2 支 USD
        for i in range(n_instruments):
            cur_ = "TWD" if i < int(n_instruments * 0.8) else "USD"
            mkt = "TWSE" if cur_ == "TWD" else "US"
            cur.execute(
                "INSERT INTO instrument (market,symbol,name,currency,instrument_type)"
                " VALUES (%s,%s,%s,%s,'STOCK')",
                (mkt, f"S{i:04d}", f"標的{i}", cur_),
            )
        cur.execute("SELECT id, currency FROM instrument ORDER BY id")
        instruments = cur.fetchall()

        # daily_close：US 標的少 3% 的交易日（模擬不同交易日曆）
        rows = []
        for iid, ccy in instruments:
            price = random.uniform(30, 600)
            prev = price
            for d in days:
                if ccy == "USD" and random.random() < 0.03:
                    continue
                prev = price
                price = max(1.0, price * (1 + random.gauss(0, 0.015)))
                rows.append((iid, d, round(price, 4), round(prev, 4), "bench"))
        with cur.copy(
            "COPY daily_close (instrument_id,trade_date,close,prev_close,source) FROM STDIN"
        ) as cp:
            for r in rows:
                cp.write_row(r)
        n_dc = len(rows)

        # exchange_rate：USD 逐日
        fx = []
        rate = 31.0
        for d in days:
            rate = max(25.0, rate * (1 + random.gauss(0, 0.002)))
            fx.append(("USD", d, round(rate, 6)))
        with cur.copy("COPY exchange_rate (currency,rate_date,rate) FROM STDIN") as cp:
            for r in fx:
                cp.write_row(r)

        # transaction：確保不出現負股數（先買才賣）
        holdings = {iid: 0.0 for iid, _ in instruments}
        n_tx = tx_per_year * years
        tx_days = sorted(random.sample(days[10:], min(n_tx, len(days) - 10)))
        txs = []
        for d in tx_days:
            iid, ccy = random.choice(instruments)
            r = random.random()
            if r < 0.55 or holdings[iid] <= 0:
                typ, q = "BUY", float(random.choice([1000, 2000, 1000, 500, 137]))
                holdings[iid] += q
            elif r < 0.9:
                q = min(holdings[iid], float(random.choice([1000, 500, 1000])))
                typ = "SELL"
                holdings[iid] -= q
            else:
                typ, q = "STOCK_DIVIDEND", round(holdings[iid] * 0.05, 2)
                holdings[iid] += q
            price = random.uniform(30, 600)
            txs.append((1, 1, iid, typ, d, q, round(price, 2),
                        round(q * price * 0.000399, 4),
                        round(q * price * 0.003, 4) if typ == "SELL" else 0,
                        None, ccy, None, None))
        with cur.copy(
            'COPY "transaction" (user_id,portfolio_id,instrument_id,type,traded_on,'
            "quantity,price,fee,tax,cash_amount,currency,note,external_ref) FROM STDIN"
        ) as cp:
            for r in txs:
                cp.write_row(r)
        cur.execute("ANALYZE")
    conn.commit()
    return n_dc, len(txs), len(days)


# ---------------------------------------------------------------- 查詢

# A. 任意單一日的總資產（從 Transaction 重算）
Q_SINGLE_DAY = """
SELECT SUM(h.shares * dc.close * COALESCE(fx.rate, 1)) AS total_twd
FROM (
  SELECT t.instrument_id,
         SUM(CASE WHEN t.type IN ('BUY','STOCK_DIVIDEND') THEN t.quantity
                  WHEN t.type = 'SELL' THEN -t.quantity ELSE 0 END) AS shares
  FROM "transaction" t
  WHERE t.user_id = 1 AND t.traded_on <= %(d)s
  GROUP BY t.instrument_id
) h
JOIN instrument i ON i.id = h.instrument_id
JOIN LATERAL (
  SELECT close FROM daily_close d
  WHERE d.instrument_id = h.instrument_id AND d.trade_date <= %(d)s
  ORDER BY d.trade_date DESC LIMIT 1
) dc ON true
LEFT JOIN LATERAL (
  SELECT rate FROM exchange_rate e
  WHERE e.currency = i.currency AND e.rate_date <= %(d)s
  ORDER BY e.rate_date DESC LIMIT 1
) fx ON i.currency <> 'TWD'
WHERE h.shares <> 0
"""

# B. 整條曲線（天真版）：只在該標的自己有收盤價的日子計入
#    -> 美股休市日該標的會整個從當日總資產消失，數字會塌陷。留作對照。
Q_CURVE_NAIVE = """
WITH tx AS (
  SELECT instrument_id, traded_on AS d,
         SUM(CASE WHEN type IN ('BUY','STOCK_DIVIDEND') THEN quantity
                  WHEN type = 'SELL' THEN -quantity ELSE 0 END) AS dq
  FROM "transaction" WHERE user_id = 1 GROUP BY 1,2
),
h AS (
  SELECT dc.instrument_id, dc.trade_date, dc.close,
         SUM(COALESCE(tx.dq,0)) OVER (PARTITION BY dc.instrument_id
                                      ORDER BY dc.trade_date) AS shares
  FROM daily_close dc
  LEFT JOIN tx ON tx.instrument_id = dc.instrument_id AND tx.d = dc.trade_date
  WHERE dc.trade_date BETWEEN %(a)s AND %(b)s
)
SELECT h.trade_date, SUM(h.shares * h.close * COALESCE(fx.rate,1))
FROM h
JOIN instrument i ON i.id = h.instrument_id
LEFT JOIN exchange_rate fx ON fx.currency = i.currency AND fx.rate_date = h.trade_date
GROUP BY 1 ORDER BY 1
"""

# C. 整條曲線（正確版）：統一日曆 + 價格 LOCF（前值補齊）+ 匯率 LOCF
Q_CURVE_LOCF = """
WITH cal AS (
  SELECT DISTINCT trade_date AS d FROM daily_close
  WHERE trade_date BETWEEN %(a)s AND %(b)s
),
tx AS (
  SELECT instrument_id, traded_on AS d,
         SUM(CASE WHEN type IN ('BUY','STOCK_DIVIDEND') THEN quantity
                  WHEN type = 'SELL' THEN -quantity ELSE 0 END) AS dq
  FROM "transaction" WHERE user_id = 1 GROUP BY 1,2
),
grid AS (
  SELECT i.id AS instrument_id, i.currency, c.d, dc.close
  FROM instrument i CROSS JOIN cal c
  LEFT JOIN daily_close dc ON dc.instrument_id = i.id AND dc.trade_date = c.d
),
grp AS (
  SELECT g.*, COUNT(g.close) OVER (PARTITION BY g.instrument_id ORDER BY g.d) AS blk
  FROM grid g
),
px AS (
  SELECT instrument_id, currency, d,
         FIRST_VALUE(close) OVER (PARTITION BY instrument_id, blk ORDER BY d) AS close
  FROM grp
),
h AS (
  SELECT px.instrument_id, px.currency, px.d, px.close,
         SUM(COALESCE(tx.dq,0)) OVER (PARTITION BY px.instrument_id ORDER BY px.d) AS shares
  FROM px LEFT JOIN tx ON tx.instrument_id = px.instrument_id AND tx.d = px.d
),
fxgrid AS (
  SELECT c.d, e.rate,
         COUNT(e.rate) OVER (ORDER BY c.d) AS blk
  FROM cal c LEFT JOIN exchange_rate e ON e.currency='USD' AND e.rate_date = c.d
),
fx AS (
  SELECT d, FIRST_VALUE(rate) OVER (PARTITION BY blk ORDER BY d) AS rate FROM fxgrid
)
SELECT h.d, SUM(h.shares * COALESCE(h.close,0) *
                CASE WHEN h.currency = 'TWD' THEN 1 ELSE COALESCE(fx.rate,1) END)
FROM h LEFT JOIN fx ON fx.d = h.d
GROUP BY 1 ORDER BY 1
"""


def main():
    d = pathlib.Path(tempfile.gettempdir()) / "pgdata16"
    d.mkdir(exist_ok=True)
    srv = pgserver.get_server(str(d))
    uri = srv.get_uri()
    log(f"PostgreSQL: {srv.psql('select version()').splitlines()[2].strip()}")
    log()

    scenarios = [
        ("基準情境（10 標的 x 10 年 / 1500 筆交易）", 10, 10, 150, 2016),
        ("放大 5 倍（50 標的 x 10 年 / 3000 筆）", 50, 10, 300, 2016),
        ("極端（50 標的 x 20 年 / 6000 筆）", 50, 20, 300, 2006),
    ]

    for title, ni, yrs, tpy, sy in scenarios:
        log("=" * 96)
        log(f"### {title}")
        with psycopg.connect(uri, autocommit=False) as conn:
            n_dc, n_tx, n_days = seed(conn, ni, yrs, tpy, sy)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_size_pretty(pg_total_relation_size('daily_close'))")
                sz = cur.fetchone()[0]
            log(f"daily_close {n_dc:,} 列（{sz}）／transaction {n_tx:,} 列／"
                f"交易日 {n_days:,} 天")
            log()

            with conn.cursor() as cur:
                cur.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_close")
                lo, hi = cur.fetchone()
                cur.execute(
                    "SELECT trade_date FROM daily_close "
                    "WHERE trade_date > %s ORDER BY random() LIMIT 1", (lo,))
                mid = cur.fetchone()[0]

            lat, rows = timeit(conn, Q_SINGLE_DAY, {"d": mid}, n=30)
            fmt("A. 任意單一日總資產（重算）", lat)

            lat, rows = timeit(conn, Q_CURVE_NAIVE, {"a": lo, "b": hi}, n=15)
            fmt("B. 全期間曲線 · 天真版（無 LOCF）", lat, len(rows))

            lat, rows = timeit(conn, Q_CURVE_LOCF, {"a": lo, "b": hi}, n=15)
            fmt("C. 全期間曲線 · LOCF 正確版", lat, len(rows))

            # 1 年區間
            import datetime as dt
            a1 = hi - dt.timedelta(days=365)
            lat, rows1y = timeit(conn, Q_CURVE_LOCF, {"a": a1, "b": hi}, n=20)
            fmt("D. 近 1 年曲線 · LOCF", lat, len(rows1y))

            # 3 個月
            a3 = hi - dt.timedelta(days=92)
            lat, rows3m = timeit(conn, Q_CURVE_LOCF, {"a": a3, "b": hi}, n=20)
            fmt("E. 近 3 個月曲線 · LOCF", lat, len(rows3m))

            # 模擬快取表（物化）讀取
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS snap_cache")
                cur.execute(
                    "CREATE TABLE snap_cache AS " + Q_CURVE_LOCF,
                    {"a": lo, "b": hi})
                cur.execute("ALTER TABLE snap_cache RENAME COLUMN d TO trade_date")
                cur.execute("CREATE INDEX ON snap_cache (trade_date)")
                cur.execute("ANALYZE snap_cache")
            conn.commit()
            lat, rows = timeit(
                conn, "SELECT * FROM snap_cache WHERE trade_date BETWEEN %(a)s AND %(b)s"
                " ORDER BY trade_date", {"a": lo, "b": hi}, n=20)
            fmt("F. 【對照】從快取表讀全期間曲線", lat, len(rows))

            # payload 大小（前端一次抓整段）
            payload = json.dumps(
                [[str(r[0]), float(r[1] or 0)] for r in rows], separators=(",", ":"))
            log(f"   全期間曲線 JSON payload = {len(payload)/1024:.1f} KB "
                f"（{len(rows)} 點；gzip 後約 {len(payload)/1024/4:.1f} KB 量級）")
            log()

    log("=" * 96)
    log("## 加權平均成本基礎：序列遞迴的實際成本（純 Python，與天數無關）")
    with psycopg.connect(uri) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT instrument_id, traded_on, type, quantity, price, fee, tax'
                        ' FROM "transaction" WHERE user_id=1 ORDER BY traded_on, id')
            txs = cur.fetchall()
    t0 = time.perf_counter()
    for _ in range(100):
        state = {}
        realized = 0.0
        for iid, d_, typ, q, p, fee, tax in txs:
            q = float(q); p = float(p); fee = float(fee or 0); tax = float(tax or 0)
            sh, cost = state.get(iid, (0.0, 0.0))
            if typ == "BUY":
                sh += q; cost += q * p + fee
            elif typ == "SELL":
                avg = cost / sh if sh else 0.0
                realized += (q * p - fee - tax) - q * avg
                cost -= q * avg; sh -= q
            elif typ == "STOCK_DIVIDEND":
                sh += q
            state[iid] = (sh, cost)
    el = (time.perf_counter() - t0) / 100 * 1000
    log(f"{len(txs):,} 筆交易跑完整套移動加權平均 + 已實現損益："
        f"{el:.3f} ms／次（100 次平均，純 Python 迴圈）")
    log()

    out = pathlib.Path(__file__).with_name("bench-16-results.txt")
    out.write_text("\n".join(OUT), encoding="utf-8")
    print(f"\n寫出：{out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
