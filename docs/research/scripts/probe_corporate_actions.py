# -*- coding: utf-8 -*-
r"""
issue #20 公司行動（分割／減資／換股）資料源查證腳本。

用途：產生 docs/research/corporate-actions-datasources.md 的全部第一手證據。
不含任何 token 或金鑰；所有端點皆為無授權的公開端點。

重跑方式（PATH 上的 python 是 Microsoft Store 假殼，必須用 uv）：

    # Git Bash
    cd <repo root>
    PYTHONIOENCODING=utf-8 uv run --with requests python \
        docs/research/scripts/probe_corporate_actions.py \
        > docs/research/scripts/probe-corporate-actions-output.txt 2>&1

    # PowerShell
    $env:PYTHONIOENCODING="utf-8"
    uv run --with requests python docs\research\scripts\probe_corporate_actions.py |
        Out-File -Encoding utf8 docs\research\scripts\probe-corporate-actions-output.txt

節次順序是刻意排的：**便宜的查證全部排在前面，§F 的抽樣掃描排最後**，
因為 §F 必定把 FinMind 免費層（無 token）的每小時額度打完，之後任何請求都會
收到 HTTP 402。若在 §F 之前就被限流，代表上一次執行距今不到一小時，等一小時再跑。

其他注意事項：
  * TPEx 的 TLS 憑證缺 Subject Key Identifier，Python 3.13 的預設
    VERIFY_X509_STRICT 會拒絕。此處沿用 tw-benchmark-and-fx-sources.md 附錄 G
    已記載的相同解法（關閉 strict 旗標，仍驗證憑證鏈）。
  * 法律分界（沿用 tw-fundamental-chip-data-sources.md §4）：本腳本只打
    openapi.twse.com.tw 與 www.tpex.org.tw/openapi（政府資料開放授權側），
    不打 www.twse.com.tw/rwd/* 與 MOPS 內部 API。
"""
import json
import random
import ssl
import time

import requests
import urllib3
from requests.adapters import HTTPAdapter

urllib3.disable_warnings()

FINMIND = "https://api.finmindtrade.com/api/v4/data"
CAPRED_SAMPLE_N = 400          # §F 抽樣掃描的檔數（會打完免費層額度，這是刻意的）
CAPRED_SAMPLE_SEED = 20260809  # 固定種子，任何人重跑抽到同一批標的

CALLS = 0                      # 對 FinMind 的累計請求數，用來釘住限流門檻


class LaxSSLAdapter(HTTPAdapter):
    """TPEx 憑證缺 Subject Key Identifier；關掉 strict 但保留憑證鏈驗證。"""

    def init_poolmanager(self, *a, **kw):
        ctx = ssl.create_default_context()
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
        kw["ssl_context"] = ctx
        return super().init_poolmanager(*a, **kw)


SESSION = requests.Session()
SESSION.mount("https://", LaxSSLAdapter())


def hr(title):
    print("\n" + "=" * 96)
    print("### " + title)
    print("=" * 96)


def fm(**params):
    """打一次 FinMind，回傳 (status_code, json, 秒數, 第幾次請求)。"""
    global CALLS
    CALLS += 1
    t0 = time.perf_counter()
    r = SESSION.get(FINMIND, params=params, timeout=60)
    dt = time.perf_counter() - t0
    try:
        j = r.json()
    except ValueError:
        j = {"_raw": r.text[:400]}
    return r.status_code, j, dt, CALLS


def show(label, **params):
    sc, j, dt, n = fm(**params)
    if "data" in j:
        d = j["data"]
        print("%-62s [#%3d] HTTP %3d %5.2fs rows=%-5d msg=%s" % (label, n, sc, dt, len(d), j.get("msg")))
        return d
    print("%-62s [#%3d] HTTP %3d %5.2fs %s" % (label, n, sc, dt, json.dumps(j, ensure_ascii=False)[:200]))
    return None


def dump(rows, indent="    "):
    for x in rows:
        print(indent + json.dumps(x, ensure_ascii=False))


print("執行時間：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))

# ---------------------------------------------------------------- A
hr("A. TaiwanStockSplitPrice：全歷史 vs 僅最新快照")

print("\nA1. 不帶 data_id、start_date=1990-01-01（全市場、全期間）")
all_split = show("  GET ?dataset=TaiwanStockSplitPrice&start_date=1990-01-01",
                 dataset="TaiwanStockSplitPrice", start_date="1990-01-01")
if all_split:
    dump(all_split)
    ids, types = {}, {}
    for x in all_split:
        ids.setdefault(x["stock_id"], []).append(x["date"])
        types[x["type"]] = types.get(x["type"], 0) + 1
    print("\n  日期範圍：%s ~ %s" % (all_split[0]["date"], all_split[-1]["date"]))
    print("  distinct stock_id：%d／總列數 %d" % (len(ids), len(all_split)))
    print("  出現一次以上的 stock_id：%s"
          % json.dumps({k: v for k, v in ids.items() if len(v) > 1}, ensure_ascii=False))
    print("  type 值分布：%s" % json.dumps(types, ensure_ascii=False))
    print("  before_price/after_price 比值（>1 代表股數變多）：")
    for x in all_split:
        print("    %-10s %-8s %-6s ratio=%.4f" % (x["date"], x["stock_id"], x["type"],
                                                  x["before_price"] / x["after_price"]))

print("\nA2. 同一標的多列交叉驗證（帶 data_id）")
for sid in ["6548", "8932", "0050"]:
    rows = show("  data_id=%s" % sid, dataset="TaiwanStockSplitPrice",
                data_id=sid, start_date="1990-01-01")
    if rows:
        dump(rows, "      ")

print("\nA3. 回溯下限：查 2019-09-09 之前有沒有任何一列")
show("  start=1990-01-01&end=2019-09-08", dataset="TaiwanStockSplitPrice",
     start_date="1990-01-01", end_date="2019-09-08")
show("  start=1990-01-01&end=2019-12-31", dataset="TaiwanStockSplitPrice",
     start_date="1990-01-01", end_date="2019-12-31")

print("\nA4. 日期參數是否真的在過濾（不是回固定快照）")
show("  start=2026-01-01（無 end）", dataset="TaiwanStockSplitPrice", start_date="2026-01-01")
show("  完全不帶任何參數", dataset="TaiwanStockSplitPrice")
show("  data_id=0050、不帶 start_date", dataset="TaiwanStockSplitPrice", data_id="0050")

# ---------------------------------------------------------------- B
hr("B. TaiwanStockSplitPrice.date 的語意：對照 TaiwanStockPrice 的實際交易日")

CASES = [
    # (stock_id, 事件日, 觀察窗起, 觀察窗迄, 事件來源)
    ("0050", "2025-06-18", "2025-06-05", "2025-06-25", "SplitPrice 分割"),
    ("0052", "2025-11-26", "2025-11-14", "2025-12-03", "SplitPrice 分割"),
    ("00631L", "2026-03-31", "2026-03-20", "2026-04-07", "SplitPrice type 為空字串"),
    ("6548", "2019-09-09", "2019-08-28", "2019-09-16", "SplitPrice 面額變更"),
    ("8932", "2026-03-09", "2026-02-20", "2026-03-16", "SplitPrice 面額變更"),
    ("2327", "2025-08-25", "2025-08-12", "2025-09-01", "SplitPrice 面額變更"),
    ("2603", "2022-09-19", "2022-08-30", "2022-09-26", "CapitalReduction 現金減資"),
    ("2409", "2022-10-11", "2022-09-26", "2022-10-18", "CapitalReduction 現金減資"),
    ("6116", "2012-09-27", "2012-09-05", "2012-10-05", "CapitalReduction 彌補虧損"),
]
for sid, ev, s, e, src in CASES:
    rows = show("  %-7s 事件日 %s（%s）" % (sid, ev, src),
                dataset="TaiwanStockPrice", data_id=sid, start_date=s, end_date=e)
    if not rows:
        continue
    dates = [x["date"] for x in rows]
    before = [x for x in rows if x["date"] < ev]
    at = [x for x in rows if x["date"] == ev]
    print("      觀察窗內交易日：%s" % " ".join(dates))
    if before:
        print("      事件日前最後一個交易日 %s close=%s" % (before[-1]["date"], before[-1]["close"]))
    else:
        print("      事件日前最後一個交易日：觀察窗內無（起始日往前再拉才看得到）")
    print("      事件日當天：%s" % (json.dumps(at[0], ensure_ascii=False) if at else "【無此列】"))

# ---------------------------------------------------------------- C
hr("C. 減資／換股／合併的可程式化資料源盤點")

print("\nC1. FinMind TaiwanStockCapitalReductionReferencePrice（減資恢復買賣參考價格）")
for sid in ["2603", "2409", "6116", "0050", "2618", "1314"]:
    rows = show("  data_id=%s" % sid, dataset="TaiwanStockCapitalReductionReferencePrice",
                data_id=sid, start_date="1990-01-01")
    if rows:
        dump(rows, "      ")

print("\nC2. FinMind TaiwanStockParValueChange（變更面額恢復買賣參考價格）")
pv = show("  不帶 data_id", dataset="TaiwanStockParValueChange", start_date="1990-01-01")
if pv:
    dump(pv)
    print("      日期範圍：%s ~ %s（%d 列）" % (pv[0]["date"], pv[-1]["date"], len(pv)))
show("  帶 data_id=6548", dataset="TaiwanStockParValueChange", data_id="6548", start_date="1990-01-01")

print("\nC3. FinMind 有沒有合併／換股 dataset（拿不存在的名字打，讓 enum 錯誤訊息吐出合法清單）")
sc, j, dt, n = fm(dataset="TaiwanStockMerger", data_id="2330")
print("  dataset=TaiwanStockMerger -> HTTP %d" % sc)
print("  合法 dataset 全清單（回應原文）：")
print("    " + json.dumps(j, ensure_ascii=False))

print("\nC4. 唯一沾得上邊的兩個既有 dataset")
dl = show("  TaiwanStockDelisting（下市櫃表）不帶 data_id", dataset="TaiwanStockDelisting")
if dl:
    print("      欄位：%s" % list(dl[0].keys()))
    print("      最新一列：%s" % json.dumps(max(dl, key=lambda x: x["date"]), ensure_ascii=False))
    print("      最舊一列：%s" % json.dumps(min(dl, key=lambda x: x["date"]), ensure_ascii=False))
show("  TaiwanStockSuspended（暫停交易公告）不帶 data_id", dataset="TaiwanStockSuspended")

# ---------------------------------------------------------------- D
hr("D. FinMind 免費層的『不帶 data_id 全市場拉取』權限矩陣")

for ds in ["TaiwanStockSplitPrice", "TaiwanStockParValueChange", "TaiwanStockDelisting",
           "TaiwanStockCapitalReductionReferencePrice", "TaiwanStockDividendResult",
           "TaiwanStockDividend", "TaiwanStockPrice", "TaiwanStockSuspended"]:
    show("  %-44s" % ds, dataset=ds, start_date="2026-08-01")

# ---------------------------------------------------------------- E
hr("E. TWSE／TPEx OpenAPI（政府資料開放授權側）有沒有公司行動端點")

KEYWORDS = ["減資", "分割", "面額", "換股", "合併", "停止買賣", "暫停", "恢復", "終止", "換發", "參考價"]


def scan_swagger(url):
    r = SESSION.get(url, timeout=120)
    print("  GET %s -> HTTP %d, %d bytes" % (url, r.status_code, len(r.content)))
    paths = r.json().get("paths", {})
    print("  paths 總數：%d" % len(paths))
    for p, v in sorted(paths.items()):
        summ = ""
        for m in v.values():
            if isinstance(m, dict) and (m.get("summary") or m.get("description")):
                summ = (m.get("summary") or m.get("description")).strip()
                break
        if any(k in (p + summ) for k in KEYWORDS):
            print("    HIT %-48s %s" % (p, summ))


print("\nE1. TWSE openapi.twse.com.tw")
scan_swagger("https://openapi.twse.com.tw/v1/swagger.json")
print("\nE2. TPEx www.tpex.org.tw/openapi")
scan_swagger("https://www.tpex.org.tw/openapi/swagger.json")

print("\nE2b. 更嚴格的否證：直接在 swagger 原始文字中搜 TWSE 那四張公司行動報表的代號")
CODES = ["TWTC9U", "TWTCAU", "TWTAUU", "TWTB8U",       # ETF分割預告/恢復參考價、減資、面額變更
         "twtc9u", "twtcau", "twtauu", "twtb8u",
         "reduction", "split", "ParValue", "ReferencePrice"]
for u in ["https://openapi.twse.com.tw/v1/swagger.json",
          "https://www.tpex.org.tw/openapi/swagger.json"]:
    raw = SESSION.get(u, timeout=120).text
    print("  %s（%d bytes）" % (u, len(raw)))
    for c in CODES:
        print("    %-16s 出現於 swagger 原文：%s" % (c, c in raw))

print("\nE3. 實打命中的端點，看欄位與回傳筆數")
for u in ["https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU",
          "https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml",
          "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL",
          "https://www.tpex.org.tw/openapi/v1/tpex_spendi_history",
          "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"]:
    try:
        r = SESSION.get(u, timeout=120)
        j = r.json()
        print("\n  %s -> HTTP %d, %d 列" % (u, r.status_code, len(j)))
        if j:
            print("    欄位：%s" % list(j[0].keys()))
            for x in j[:3]:
                print("    " + json.dumps(x, ensure_ascii=False))
    except Exception as exc:                      # noqa: BLE001
        print("  %s -> 例外 %r" % (u, exc))

# ---------------------------------------------------------------- F
hr("F. 減資資料集的回溯深度（抽樣掃描）＋ FinMind 免費層限流門檻")

print("\nF1. 回應標頭全文（看有沒有任何 rate-limit 相關欄位）")
r = SESSION.get(FINMIND, params=dict(dataset="TaiwanStockSplitPrice", data_id="0050"), timeout=60)
CALLS += 1
for k, v in r.headers.items():
    print("    %s: %s" % (k, v))

print("\nF2. 對 %d 檔抽樣標的逐一查 TaiwanStockCapitalReductionReferencePrice" % CAPRED_SAMPLE_N)
sc, j, dt, n = fm(dataset="TaiwanStockInfo")
universe, seen = [], set()
for x in j.get("data", []):
    sid = x.get("stock_id", "")
    if sid.isdigit() and len(sid) == 4 and sid not in seen:
        seen.add(sid)
        universe.append(sid)
universe.sort()
print("  TaiwanStockInfo 取得 4 碼數字代號 %d 檔（母體）" % len(universe))
rng = random.Random(CAPRED_SAMPLE_SEED)
sample = sorted(rng.sample(universe, min(CAPRED_SAMPLE_N, len(universe))))

hits, codes, done, t0 = [], {}, 0, time.perf_counter()
for sid in sample:
    sc, j, _, n = fm(dataset="TaiwanStockCapitalReductionReferencePrice",
                     data_id=sid, start_date="1990-01-01")
    codes[sc] = codes.get(sc, 0) + 1
    if sc != 200:
        print("  ⚠️ 第 %d 個累計 FinMind 請求（本節第 %d 檔，stock_id=%s）起被擋："
              % (n, done + 1, sid))
        print("     %s" % json.dumps(j, ensure_ascii=False))
        break
    done += 1
    hits.extend(j.get("data", []))
elapsed = time.perf_counter() - t0
print("  本節送出 %d 個請求、耗時 %.1f 秒；狀態碼分布 %s" % (sum(codes.values()), elapsed, codes))
print("  成功掃完 %d 檔，命中 %d 列，涵蓋 %d 檔" % (done, len(hits), len({x["stock_id"] for x in hits})))
if hits:
    hits.sort(key=lambda x: x["date"])
    print("  欄位：%s" % list(hits[0].keys()))
    print("  最早：%s" % json.dumps(hits[0], ensure_ascii=False))
    print("  最新：%s" % json.dumps(hits[-1], ensure_ascii=False))
    reasons = {}
    for x in hits:
        k = x.get("ReasonforCapitalReduction")
        reasons[k] = reasons.get(k, 0) + 1
    print("  ReasonforCapitalReduction 值分布：%s" % json.dumps(reasons, ensure_ascii=False))
    multi = {}
    for x in hits:
        multi.setdefault(x["stock_id"], []).append(x["date"])
    print("  一檔多列者：%s"
          % json.dumps({k: v for k, v in multi.items() if len(v) > 1}, ensure_ascii=False))
    print("  逐年列數：%s" % json.dumps(
        {y: sum(1 for x in hits if x["date"][:4] == y)
         for y in sorted({x["date"][:4] for x in hits})}, ensure_ascii=False))

print("\n  本次執行對 FinMind 的累計請求數：%d" % CALLS)
print("\n完成：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
