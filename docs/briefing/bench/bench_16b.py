# -*- coding: utf-8 -*-
"""bench_16 續：把「重算整條曲線」的查詢調優，看真正的下界在哪。
沿用 bench_16.py 最後一次 seed 出來的資料庫（極端情境 50 標的 x 20 年），
另外重建基準情境比較。
"""
import pathlib, statistics, sys, tempfile, time
import pgserver, psycopg
import bench_16 as B

OUT = []
def log(s=""):
    print(s); OUT.append(s)

def run(conn, name, sql, params, n=15):
    lat = []
    rows = None
    for _ in range(n):
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(sql, params); rows = cur.fetchall()
        lat.append((time.perf_counter()-t0)*1000)
    s = sorted(lat)
    log(f"{name:<56} min={s[0]:8.2f}ms p50={statistics.median(s):8.2f}ms "
        f"p95={s[int(len(s)*0.95)-1]:8.2f}ms  rows={len(rows)}")
    return rows

# 調優版：
#  1) 只取「使用者曾經持有過」的標的（daily_close 還有一堆只看不買的標的）
#  2) 每支標的只從它第一筆交易日開始鋪格子
#  3) 匯率 LOCF 先攤平成一張小表（交易日數列，不是 標的x日 的矩陣）
#  4) 聚合用 float8 而非 numeric
Q_OPT = """
WITH held AS (
  SELECT t.instrument_id, MIN(t.traded_on) AS since
  FROM "transaction" t WHERE t.user_id = 1 GROUP BY 1
),
cal AS (
  SELECT DISTINCT trade_date AS d FROM daily_close
  WHERE trade_date BETWEEN %(a)s AND %(b)s
),
fxg AS (
  SELECT c.d, e.rate, COUNT(e.rate) OVER (ORDER BY c.d) AS blk
  FROM cal c LEFT JOIN exchange_rate e ON e.currency='USD' AND e.rate_date=c.d
),
fx AS (
  SELECT d, FIRST_VALUE(rate) OVER (PARTITION BY blk ORDER BY d)::float8 AS rate FROM fxg
),
tx AS (
  SELECT instrument_id, traded_on AS d,
         SUM(CASE WHEN type IN ('BUY','STOCK_DIVIDEND') THEN quantity
                  WHEN type='SELL' THEN -quantity ELSE 0 END)::float8 AS dq
  FROM "transaction" WHERE user_id=1 GROUP BY 1,2
),
grid AS (
  SELECT h.instrument_id, i.currency, c.d, dc.close::float8 AS close
  FROM held h
  JOIN instrument i ON i.id = h.instrument_id
  JOIN cal c ON c.d >= h.since
  LEFT JOIN daily_close dc ON dc.instrument_id = h.instrument_id AND dc.trade_date = c.d
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
h2 AS (
  SELECT px.instrument_id, px.currency, px.d, px.close,
         SUM(COALESCE(tx.dq,0)) OVER (PARTITION BY px.instrument_id ORDER BY px.d) AS shares
  FROM px LEFT JOIN tx ON tx.instrument_id=px.instrument_id AND tx.d=px.d
)
SELECT h2.d, SUM(h2.shares * COALESCE(h2.close,0)
       * CASE WHEN h2.currency='TWD' THEN 1 ELSE COALESCE(fx.rate,1) END)
FROM h2 LEFT JOIN fx ON fx.d = h2.d
GROUP BY 1 ORDER BY 1
"""

# 極簡版：完全不在 SQL 做 LOCF。SQL 只負責兩件便宜的事，
# 其餘（前值補齊、累計股數、換算）在 Python 端一次掃過。
Q_RAW_CLOSE = """
SELECT dc.instrument_id, dc.trade_date, dc.close::float8, i.currency
FROM daily_close dc JOIN instrument i ON i.id = dc.instrument_id
WHERE dc.trade_date BETWEEN %(a)s AND %(b)s
  AND dc.instrument_id IN (SELECT DISTINCT instrument_id FROM "transaction" WHERE user_id=1)
ORDER BY dc.instrument_id, dc.trade_date
"""
Q_RAW_TX = """
SELECT instrument_id, traded_on, type, quantity::float8
FROM "transaction" WHERE user_id=1 ORDER BY traded_on, id
"""
Q_RAW_FX = "SELECT rate_date, rate::float8 FROM exchange_rate WHERE currency='USD' ORDER BY rate_date"


def curve_in_python(closes, txs, fxs):
    """SQL 只撈原始列，曲線在應用層算。回傳 [(date, total_twd)]。"""
    from collections import defaultdict
    dates = sorted({r[1] for r in closes})
    di = {d: k for k, d in enumerate(dates)}
    n = len(dates)
    fxmap = dict(fxs)
    fx = [1.0]*n; last = 1.0
    for k, d in enumerate(dates):
        last = fxmap.get(d, last); fx[k] = last
    # 每支標的：價格 LOCF + 累計股數
    px = defaultdict(lambda: [0.0]*n)
    ccy = {}
    for iid, d, c, cu in closes:
        px[iid][di[d]] = c
        ccy[iid] = cu
    for iid, arr in px.items():
        last = 0.0
        for k in range(n):
            if arr[k] == 0.0: arr[k] = last
            else: last = arr[k]
    sh = defaultdict(lambda: [0.0]*n)
    for iid, d, typ, q in txs:
        k = di.get(d)
        if k is None: continue
        dq = q if typ in ("BUY", "STOCK_DIVIDEND") else (-q if typ == "SELL" else 0.0)
        sh[iid][k] += dq
    total = [0.0]*n
    for iid, arr in sh.items():
        run = 0.0
        p = px[iid]
        mult = 1.0 if ccy.get(iid) == "TWD" else None
        for k in range(n):
            run += arr[k]
            if run:
                total[k] += run * p[k] * (1.0 if mult == 1.0 else fx[k])
    return list(zip(dates, total))


def bench_scenario(uri, title, ni, yrs, tpy, sy):
    log("="*104); log(f"### {title}")
    with psycopg.connect(uri) as conn:
        n_dc, n_tx, n_days = B.seed(conn, ni, yrs, tpy, sy)
        log(f"daily_close {n_dc:,} 列／transaction {n_tx:,} 列／交易日 {n_days:,} 天")
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(trade_date), MAX(trade_date) FROM daily_close")
            lo, hi = cur.fetchone()
        run(conn, "C.  LOCF 天真版（bench_16 的查詢）", B.Q_CURVE_LOCF, {"a": lo, "b": hi})
        run(conn, "C'. LOCF 調優版（限持有標的 + float8 + 起算日）", Q_OPT, {"a": lo, "b": hi})

        # SQL 只撈原始列，Python 算
        lat = []
        for _ in range(10):
            t0 = time.perf_counter()
            with conn.cursor() as cur:
                cur.execute(Q_RAW_CLOSE, {"a": lo, "b": hi}); closes = cur.fetchall()
                cur.execute(Q_RAW_TX); txs = cur.fetchall()
                cur.execute(Q_RAW_FX); fxs = cur.fetchall()
            t_fetch = (time.perf_counter()-t0)*1000
            t1 = time.perf_counter()
            curve = curve_in_python(closes, txs, fxs)
            t_calc = (time.perf_counter()-t1)*1000
            lat.append((t_fetch, t_calc))
        f = sorted(x[0] for x in lat); c = sorted(x[1] for x in lat)
        log(f"{'G.  SQL 只撈原始列 + 應用層算曲線':<56} "
            f"撈列 p50={statistics.median(f):7.2f}ms  算 p50={statistics.median(c):7.2f}ms  "
            f"合計 p50={statistics.median(f)+statistics.median(c):7.2f}ms  "
            f"rows={len(closes):,}+{len(txs):,}  曲線點={len(curve)}")
        log()


def main():
    d = pathlib.Path(tempfile.gettempdir())/"pgdata16"
    srv = pgserver.get_server(str(d)); uri = srv.get_uri()
    bench_scenario(uri, "基準情境（10 標的 x 10 年 / 1500 筆）", 10, 10, 150, 2016)
    bench_scenario(uri, "放大（50 標的 x 20 年 / 6000 筆）", 50, 20, 300, 2006)
    p = pathlib.Path(__file__).with_name("bench-16b-results.txt")
    p.write_text("\n".join(OUT), encoding="utf-8")
    print("寫出：", p)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
