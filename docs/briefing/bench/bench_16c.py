# -*- coding: utf-8 -*-
"""bench_16 續二：報酬率演算法本身的計算成本，以及「前端本地重算任意區間」的可行性。
Python 迴圈作為 JS 的代理（同量級；JIT 後的 JS 通常更快，故此為保守上界）。
"""
import random, statistics, sys, time

random.seed(1)

def xirr(cashflows, guess=0.1):
    """cashflows: [(t_years, amount)]，牛頓法求根。"""
    r = guess
    for _ in range(100):
        f = fp = 0.0
        for t, a in cashflows:
            d = (1.0 + r) ** t
            f += a / d
            fp += -t * a / (d * (1.0 + r))
        if abs(fp) < 1e-12: break
        step = f / fp
        r -= step
        if abs(step) < 1e-10:
            break
    return r

def main():
    n_cf = 1500  # 10 年 x 150 筆
    cfs = [(i * 10.0 / n_cf, -random.uniform(1e4, 2e5)) for i in range(n_cf)]
    cfs.append((10.0, sum(-a for _, a in cfs) * 1.4))

    lat = []
    for _ in range(200):
        t0 = time.perf_counter(); r = xirr(cfs); lat.append((time.perf_counter()-t0)*1000)
    print(f"XIRR（{len(cfs)} 筆現金流，牛頓法收斂）: p50={statistics.median(lat):.3f} ms, "
          f"max={max(lat):.3f} ms, 解={r:.4%}")

    # TWR：每日報酬連乘，事先算好累積指數後，任意區間為 O(1)
    n = 2514
    daily = [1 + random.gauss(0.0004, 0.012) for _ in range(n)]
    lat = []
    for _ in range(200):
        t0 = time.perf_counter()
        idx = [1.0]*n; acc = 1.0
        for k in range(n):
            acc *= daily[k]; idx[k] = acc
        lat.append((time.perf_counter()-t0)*1000)
    print(f"TWR 累積指數（{n} 天，建表一次）: p50={statistics.median(lat):.3f} ms")

    t0 = time.perf_counter()
    for _ in range(100000):
        a = random.randrange(n); b = random.randrange(n)
        if a > b: a, b = b, a
        _ = idx[b]/idx[a] - 1
    print(f"任意區間 TWR 查詢（建表後）: {(time.perf_counter()-t0)/100000*1e6:.3f} µs／次")

    # 拖曳：每影格預算 16.7ms。若每影格重跑一次 XIRR：
    print(f"\n每影格預算 16.7ms（60fps）：")
    print(f"  · 區間 TWR / 絕對變化 / 百分比 → O(1) 陣列查表，可負擔")
    print(f"  · 區間 XIRR（全部 1500 筆現金流）→ {statistics.median(lat):.3f} ms 等級"
          f" 之外另需 {statistics.median([x for x in lat]):.3f}；見上方 XIRR 數字")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
