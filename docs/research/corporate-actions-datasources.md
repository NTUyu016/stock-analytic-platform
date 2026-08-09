# 公司行動（分割／面額變更／減資／換股）的資料源查證

> 對應票：[#20 決策：公司行動（分割／減資／換股）的型別與偵測](https://github.com/NTUyu016/stock-analytic-platform/issues/20)
> 補的是 [`docs/briefing/20-corporate-actions.md`](../briefing/20-corporate-actions.md) 三處「仍未查證的空白」：§4.3 第 1 項（`TaiwanStockSplitPrice` 是快照還是全歷史）、§2.3 第 2 項（`date` 的語意）、§3.3 第 1 項（減資／換股有無可程式化資料源）。
> 查證日期：**2026-08-09**（所有 API 回應、法規條文、TWSE 公告頁面均於當日實測／實查）
> 實測環境：`uv run --with requests`；腳本與原始輸出見 [§0.2](#02-怎麼重跑)
>
> **本文不做決策、不給推薦。** 每條事實附第一手出處（API 回應原文或官方 URL）；查不到的一律明寫「**未能查證，需人工確認**」；推論一律標「**推論**」。體例沿用 [`tw-benchmark-and-fx-sources.md`](./tw-benchmark-and-fx-sources.md) 與 [`tw-fundamental-chip-data-sources.md`](./tw-fundamental-chip-data-sources.md)。

---

## 0.1 六句話結論

1. **`TaiwanStockSplitPrice` 是全歷史，不是最新快照** —— 不帶 `data_id` 一次拉回**全市場 32 列、2019-09-09 ~ 2026-07-07**；`6548` 與 `8932` 兩檔各回**兩列**不同年份的事件。但**回溯下限只到 2019-09-09**：`end_date=2019-09-08` 回 0 列。
2. **`date` 的語意是「恢復買賣（新股上市買賣）的第一個交易日」**，不是停止買賣日、也不是最後交易日。9 個案例中，`date` 全部等於 `TaiwanStockPrice` 中該檔停止買賣後重新出現的第一列；TWSE 官方頁面把這張表的日期欄位直接叫「**恢復買賣日期**」。
3. **`before_price` = 停止買賣前最後收盤價，`after_price` = 恢復買賣參考價**，TWSE 官方公布的公式是「**恢復買賣參考價＝停止買賣前最後收盤價／分割（反分割）比率**」—— 因此 `before_price / after_price` **在定義上就是分割比率**（僅差 `after_price` 四捨五入的 ~10⁻⁵ 捨入誤差）。這條是恆等式不是經驗規律，跨標的交叉驗證這個顧慮可以消掉。
4. **減資有乾淨的可程式化資料源**：FinMind `TaiwanStockCapitalReductionReferencePrice`（免費層、帶 `data_id` 可用），欄位名可逐字對回 TWSE 英文版頁面用語，抽樣實測回溯逾十年。這**動搖了 [`transaction-input.md`](../spec/transaction-input.md) §8「減資……沒有乾淨的官方 feed」的敘述**（詳見 §5.1）。
5. **但減資的 `after/before` 比值不能當股數比率用**：TWSE 對「退還股款」型減資的公式是 `(停止買賣前收盤價 − 息值 − 每股退還股款) / 減資換股率`，**現金退款被摻在分子裡**，而 dataset 沒有任何欄位單獨給出換股率或退還股款。分割沒有這個問題（分子無扣項）。
6. **換股／合併：仍然沒有可程式化資料源。** FinMind 的合法 dataset 全清單（由 API 的 enum 驗證錯誤原樣吐出）沒有任何一個對應；`openapi.twse.com.tw`（143 paths）與 `www.tpex.org.tw/openapi`（225 paths）逐一掃過，也沒有。**#19 對「換股／合併」的判斷未被推翻，只有「減資」那一半被推翻。**

## 0.2 怎麼重跑

腳本與原始輸出都在 repo 裡（比照 [`docs/briefing/bench/`](../briefing/bench/) 的先例）：

| 檔案 | 內容 |
|---|---|
| [`scripts/probe_corporate_actions.py`](./scripts/probe_corporate_actions.py) | 本文所有 API 證據的產生腳本，**不含任何 token 或金鑰** |
| [`scripts/probe-corporate-actions-output.txt`](./scripts/probe-corporate-actions-output.txt) | 2026-08-09 的原始輸出全文 |

```bash
# Git Bash（PATH 上的 python 是 Microsoft Store 假殼，一定要用 uv）
cd <repo root>
PYTHONIOENCODING=utf-8 uv run --with requests python \
    docs/research/scripts/probe_corporate_actions.py \
    > docs/research/scripts/probe-corporate-actions-output.txt 2>&1
```

> ⚠️ 腳本的 §F 會**刻意把 FinMind 免費層（無 token）的每小時額度打完**，之後任何請求都收 HTTP 402。節次順序是刻意排的：所有便宜的查證都在 §F 之前。若在 §A 就被擋，代表距上次執行不到一小時，等一小時再跑。

## 0.3 法律分界（沿用既有判定，本文未重新查證）

本文**打過的**端點只有兩類，皆落在 [`tw-fundamental-chip-data-sources.md`](./tw-fundamental-chip-data-sources.md) §4 已確立的可用側：

- `api.finmindtrade.com`（第三方，授權狀態見 §7）
- `openapi.twse.com.tw/v1/*`、`www.tpex.org.tw/openapi/*`（政府資料開放授權條款-第1版）

本文**引用但未以程式存取**的 `www.twse.com.tw/zh/announcement/*` 頁面，落在 TWSE 使用條款的爬蟲禁止側（同上 §4.1）。它們在本文只作為**人工查證語意的一手文件**，**不得**寫進排程或當成資料管線的一環。

---

## 1. `TaiwanStockSplitPrice` 是全歷史還是最新快照

### 1.1 直接證據：不帶 `data_id` 一次拉回全市場全期間

```
GET https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockSplitPrice&start_date=1990-01-01
→ HTTP 200, msg=success, rows=32
```

32 列涵蓋 **2019-09-09 ~ 2026-07-07**、**30 個 distinct `stock_id`**。全文見原始輸出 §A1。頭尾兩列原文：

```json
{"date":"2019-09-09","stock_id":"6548","type":"面額變更","before_price":312.0,"after_price":31.2,"max_price":34.3,"min_price":28.1,"open_price":31.2}
{"date":"2026-07-07","stock_id":"00685L","type":"分割","before_price":306.0,"after_price":12.75,"max_price":15.3,"min_price":10.2,"open_price":12.75}
```

### 1.2 交叉驗證：同一標的拿得到多列

「一次拉回 32 列」本身還不足以證明它不是快照 —— 也可能是「每檔只留最新一次」的全市場快照。真正的判準是**同一標的能不能拿到多列**。做法是先用 §1.1 的全市場拉取找出重複的 `stock_id`，再用 `data_id` 分別驗證：

| `stock_id` | 全市場拉取中的日期 | 帶 `data_id` 單獨查的結果 |
|---|---|---|
| `6548`（長科） | 2019-09-09、2022-09-05 | **rows=2**，兩列與全市場拉取逐欄相同 |
| `8932`（智通） | 2024-09-09、2026-03-09 | **rows=2**，同上 |
| `0050` | 2025-06-18 | **rows=1**（0050 歷史上只分割過一次） |

```
?dataset=TaiwanStockSplitPrice&data_id=6548&start_date=1990-01-01  → rows=2
  {"date":"2019-09-09","stock_id":"6548","type":"面額變更","before_price":312.0,"after_price":31.2,...}
  {"date":"2022-09-05","stock_id":"6548","type":"面額變更","before_price":90.6,"after_price":36.24,...}
```

**結論：不是「僅最新快照」。** 同一標的的舊事件不會被新事件覆蓋。這回答了 [`20-corporate-actions.md`](../briefing/20-corporate-actions.md) §4.3 第 1 項與 §4.1(e)。

### 1.3 真正的限制不是快照，是回溯下限只到 2019-09-09

| 查詢 | 結果 |
|---|---|
| `start_date=1990-01-01&end_date=2019-09-08` | **rows=0** |
| `start_date=1990-01-01&end_date=2019-12-31` | rows=1（即 6548 那一列） |
| 完全不帶任何參數 | rows=32（與帶 `start_date=1990-01-01` 相同） |
| `start_date=2026-01-01` | rows=7 |

日期參數確實在過濾，不是回一份固定快照。**2019-09-09 之前查無任何一列** —— 這是本資料集的實際下限（**推論**：可能是 TWSE 該張公告表本身的線上保存範圍，本文未向 TWSE 求證，**未能查證**）。

> 對規格的影響：這代表**回補歷史分割事件時，2019-09-09 以前的事件不能靠這個 dataset**。0050 唯一一次分割在 2025 年，不受影響；但若日後使用者匯入更早的交易紀錄，這是一個會靜默漏事件的邊界。

### 1.4 `type` 欄位的四個值，其中一個是空字串

| `type` 值 | 列數 |
|---|---|
| `面額變更` | 21 |
| `反分割` | 6 |
| `分割` | 4 |
| **`""`（空字串）** | **1** |

空字串那一列是 `00631L`（元大台灣50正2）於 **2026-03-31**：

```json
{"date":"2026-03-31","stock_id":"00631L","type":"","before_price":443.15,"after_price":20.14,"max_price":24.16,"min_price":16.12,"open_price":20.14}
```

比值 `443.15 / 20.14 = 22.0` —— 從數字看是一次 1 拆 22 的分割，但 `type` 是空的。**若偵測邏輯用 `WHERE type = '分割'` 過濾，這一列會被靜默漏掉。**（這是事實陳述，不是建議。）

### 1.5 `反分割` 的比值方向相反，且 `max_price`／`min_price` 有髒值

6 列 `反分割` 的 `before_price < after_price`（股數變少、每股價格變高）。其中 4 列的 `max_price`／`min_price` 是 `9999.95`／`0.01`：

```json
{"date":"2025-10-22","stock_id":"00673R","type":"反分割","before_price":7.02,"after_price":28.08,"max_price":9999.95,"min_price":0.01,"open_price":28.08}
```

`9999.95`／`0.01` 是「首日無漲跌幅限制」的哨兵值（**推論**，本文未查證 TWSE 對此的正式定義）。這與 [`tw-benchmark-and-fx-sources.md`](./tw-benchmark-and-fx-sources.md) §C.2 記載的 FinMind `-1.0` 缺值哨兵是同一類問題：**`numeric` 收得下，不會報錯**。

`max_price`／`min_price`／`open_price` 三欄與峰值調整無關（它們是恢復買賣當日的漲停／跌停／開盤競價基準），本文只記錄不展開。

---

## 2. `TaiwanStockSplitPrice.date` 的語意

### 2.1 官方定義：TWSE 這張表的日期欄位就叫「恢復買賣日期」

FinMind 對 `TaiwanStockSplitPrice` 的官方說明是「**台股分割後參考價**」（[FinMind 台股資料集清單](https://finmind.github.io/tutor/TaiwanMarket/DataList/)）。對應的 TWSE 一手頁面有兩張：

| TWSE 頁面 | 標題（逐字） | 日期查詢欄位標籤（逐字） |
|---|---|---|
| [`/zh/announcement/split/twtcau.html`](https://www.twse.com.tw/zh/announcement/split/twtcau.html) | 「ETF分割(反分割)恢復買賣參考價格」 | 「**恢復買賣日期：　至**」 |
| [`/zh/announcement/change/twtb8u.html`](https://www.twse.com.tw/zh/announcement/change/twtb8u.html) | 「變更股票面額恢復買賣參考價格」 | 「**恢復買賣日期：　至**」 |

TWSE `twtcau.html` 頁面上的公式（逐字引用，2026-08-09 查）：

> 恢復買賣參考價 = 停止買賣前最後收盤價/分割（反分割）比率。
> 開盤競價基準：取最接近恢復買賣參考價之檔位價。
> 分割或反分割前受益憑證如無最後交易日收盤價格，則以本公司營業細則第五十八條之三第四項第二款之原則所決定價格替代。

**這同時釘死三件事**：
- `date` 的軸是**恢復買賣日期**；
- `before_price` = **停止買賣前最後收盤價**；
- `after_price` = **恢復買賣參考價**，因此 `before_price / after_price` **在定義上就是分割（反分割）比率**（不是經驗上湊巧成立的近似關係；但因 `after_price` 是四捨五入後的公告值，數值上仍有 ~10⁻⁵ 量級的捨入誤差，見 §2.3）。

### 2.2 逐案核對：9 個事件，`date` 全部等於停止買賣後的第一個交易日

方法：拿 `TaiwanStockSplitPrice` / `TaiwanStockCapitalReductionReferencePrice` 的 `date`，去 `TaiwanStockPrice` 查該檔前後的實際交易日。原始輸出見 §B。

| 標的 | 事件來源 | `date` | 前一個交易日（收盤價） | `before_price` | 兩者是否相等 | `date` 當天有交易列 |
|---|---|---|---|---|---|---|
| `0050` | 分割 | 2025-06-18 | 2025-06-10（188.65） | 188.65 | ✅ | ✅ open=47.5 close=47.57 |
| `0052` | 分割 | 2025-11-26 | 2025-11-18（245.3） | 245.3 | ✅ | ✅ open=35.38 close=35.35 |
| `00631L` | `type` 空字串 | 2026-03-31 | 2026-03-24（443.15） | 443.15 | ✅ | ✅ open=19.67 close=19.26 |
| `6548` | 面額變更 | 2019-09-09 | 2019-08-28（312.0） | 312.0 | ✅ | ✅ open=close=34.3（漲停） |
| `8932` | 面額變更 | 2026-03-09 | 見原始輸出 | 199.5 | ✅ | ✅ open=close=89.8（跌停） |
| `2327` | 面額變更 | 2025-08-25 | 2025-08-13（546.0） | 546.0 | ✅ | ✅ open=142.0 close=143.0 |
| `2603` | 現金減資 | 2022-09-19 | 2022-09-06（80.8） | 80.8※ | ✅ | ✅ open=185.5 close=169.0 |
| `2409` | 現金減資 | 2022-10-11 | 2022-09-28（14.7） | 14.7※ | ✅ | ✅ open=16.15 close=16.45 |
| `6116` | 彌補虧損減資 | 2012-09-27 | 2012-09-12（1.69） | 1.69※ | ✅ | ✅ open=3.56 close=3.15 |

※ 減資資料集的對應欄位名是 `ClosingPriceonTheLastTradingDay`。

**9/9 全部成立**：`date` 是恢復買賣的第一個交易日，`before_price` 是停止買賣前最後一個交易日的收盤價，且**停止買賣期間 `TaiwanStockPrice` 一律缺列、不補 0**（與 [`data-model.md`](../spec/data-model.md) 對 `daily_close`「停止買賣日不補列」的既定規則相容）。

### 2.3 0050 案例的官方逐日核對

一手來源：TWSE ETF e添富，元大投信 2025-06-17 11:35:21 公告「公告本公司經理之『元大台灣卓越50證券投資信託基金』（證券代碼0050）分割後單位數及每受益權單位參考價」
<https://www.twse.com.tw/zh/ETFortune/announcement?company=A00005&date=20250617&seq=1&fund=0050&type=all>

公告「三、分割作業時程」逐字：

> (1)受益憑證最後交易日期：**114年6月10日**
> (2)受益憑證停止交易期間：**114年6月11日至114年6月17日**
> (3)停止初級市場申贖日期：114年6月11日至114年6月17日
> (4)受益憑證最後過戶日期：114年6月12日
> (5)受益憑證停止過戶期間：114年6月13日至114年6月17日
> (6)新受益憑證上市(櫃)買賣日：**114年6月18日**
> (7)新受益憑證換發基準日暨受益憑證終止上市(櫃)日：**114年6月18日**

「四、其他應敘明事項」逐字：

> 二、本基金分割後之每受益權單位參考價(即**恢復買賣參考價**)為**47.16**元。
> 本基金以114年6月18日為新受益憑證換發基準日暨受益憑證終止上市(櫃)日，本基金分割後受益憑證買賣參考價係由分割前受益憑證最後交易日(**114年6月10日**)之收盤價(**188.65**元)除上分割比率(**4**倍)計算得出(188.65/4=47.16)。

**逐日核對結果**：

| FinMind 欄位 | 值 | 官方公告對應項 |
|---|---|---|
| `date` | 2025-06-18 | 新受益憑證上市(櫃)買賣日 ＝ 換發基準日 ＝ 終止上市日（三者同一天） |
| `before_price` | 188.65 | 分割前最後交易日（114年6月10日）之收盤價 |
| `after_price` | 47.16 | 分割後每受益權單位參考價（即恢復買賣參考價） |
| `before/after` | 4.0002※ | 官方分割比率 **4** |

※ `188.65 / 47.16 = 4.00021...`。**官方比率是整數 4**；47.16 是 `188.65 / 4 = 47.1625` 取到分位（公告原文即寫 `188.65/4=47.16`）。既有簡報寫「比例 4.0002 → 1 拆 4」是從價格反推的結果；**官方直接給了 4，不需要反推**（[`tw-benchmark-and-fx-sources.md`](./tw-benchmark-and-fx-sources.md) §B.4 的「比例 188.65/47.16 = 4.0002」因此是正確但迂迴的算法）。

> **連帶的一個小陷阱**：因為 `after_price` 是四捨五入後的公告值，`before_price / after_price` 只是分割比率的**近似**（誤差 ~2×10⁻⁵）。TWSE 另行說明「開盤競價基準：取最接近恢復買賣參考價之檔位價」，可見參考價本身也不必落在檔位上。若比率要當第一類值存起來，是要存這個近似比值、還是四捨五入成整數，本文不判斷。

### 2.4 「生效日 vs 基準日」這個問題的答案：對 ETF 是同一天，對個股未能查證

[`20-corporate-actions.md`](../briefing/20-corporate-actions.md) §2.3 第 2 項與 §4.1(d) 問的是 `date` 究竟是生效日、停止買賣日還是基準日。分開答：

| 候選語意 | 判定 |
|---|---|
| 停止買賣日 | ❌ **確定不是**。0050 的停止買賣日是 2025-06-11，`date` 是 06-18 |
| 分割前最後交易日 | ❌ **確定不是**。0050 是 2025-06-10 |
| 恢復買賣日／新股上市買賣日 | ✅ **就是這個**，9/9 案例成立，且 TWSE 官方頁面欄位名即「恢復買賣日期」 |
| 換發基準日 | ⚠️ **對 0050 這類 ETF 是同一天**（官方公告白紙黑字「新受益憑證換發基準日暨受益憑證終止上市(櫃)日：114年6月18日」，與上市買賣日同日）。**對一般個股的面額變更／減資，未能查證** |

一般個股走的是另一部法規：[臺灣證券交易所股份有限公司上市公司換發有價證券作業程序](https://twse-regulation.twse.com.tw/m/LawContent.aspx?FID=FL007110)（修正日期 106.08.31），第 3 條逐字：

> （三）因減資或其他原因致新舊有價證券權利義務不同者，應訂定舊有價證券停止在市場買賣之日期，該日期應自舊有價證券停止過戶日前第二個營業日起算。
> （四）新有價證券換發之基準日依公司法第一百六十五條規定，該日期應為舊有價證券停止過戶日起算之第五日。
> （五）新有價證券上市買賣日與舊有價證券終止上市日應訂為同一日。

**法規把「換發基準日」（第四項）與「新股上市買賣日」（第五項）定義成兩個獨立的日期，並未規定兩者相同。** 本文未能取得任何個股的官方逐案「換發基準日」資料（該欄位不在任何可程式化端點上），因此：

> **「一般個股的 `TaiwanStockSplitPrice.date` 是否等於換發基準日」——未能查證，需人工確認。**
> 已確定的是它等於**恢復買賣日**。若規格要用的是「恢復買賣日」，本項不構成阻礙；若規格要用的是「基準日」，兩者可能不同日。

> ⚠️ 這一項直接關係到 [`20-corporate-actions.md`](../briefing/20-corporate-actions.md) §4.1(d) 標的落差：`pending_action.effective_on` 的既有註解是「除權息**基準日**」（[`data-model.md`](../spec/data-model.md) 第 239 行）。分割這邊拿得到的是**恢復買賣日**，語意不是同一個詞。本文不判斷這是否要緊。

---

## 3. 減資：有可程式化資料源，且欄位比分割更豐富

### 3.1 FinMind `TaiwanStockCapitalReductionReferencePrice`

FinMind 官方說明為「**減資恢復買賣參考價格**」（[台股資料集清單](https://finmind.github.io/tutor/TaiwanMarket/DataList/)），對應 TWSE 頁面 [「股票減資恢復買賣參考價格」](https://www.twse.com.tw/zh/announcement/reduction/twtauu.html)。

**免費層可用，但只能帶 `data_id`**（見 §6 的權限矩陣）。實測回應原文：

```
?dataset=TaiwanStockCapitalReductionReferencePrice&data_id=2603&start_date=1990-01-01  → rows=1
{"date":"2022-09-19","stock_id":"2603","ClosingPriceonTheLastTradingDay":80.8,
 "PostReductionReferencePrice":187.0,"LimitUp":205.5,"LimitDown":168.5,
 "OpeningReferencePrice":187.0,"ExrightReferencePrice":-1.0,
 "ReasonforCapitalReduction":"Cash refund"}
```

**欄位名可直接對回 TWSE 英文版頁面的用語**（<https://www.twse.com.tw/en/announcement/reduction/twtauu.html>，2026-08-09 查）：該頁標題為「Reference Price for Capital Reduction」，公式寫作「**Post-Reduction Reference Price** ＝ [ (A)-(F)-(B) ] / (C)」，日期查詢欄位標籤為「**Resume Trading date**」。FinMind 的 `PostReductionReferencePrice` 與之逐字相同，`date` 軸也與「Resume Trading date」對應 —— 這使本 dataset 的溯源比 `TaiwanStockSplitPrice`（`before_price`／`after_price` 為 FinMind 自訂名）更清楚。

### 3.2 回溯深度與覆蓋率（抽樣掃描）

因為此 dataset 免費層不允許不帶 `data_id` 的全市場拉取，回溯下限只能靠抽樣。腳本 §F 對 `TaiwanStockInfo` 的四碼數字代號母體做固定種子抽樣，逐檔查詢：

**方法**：`TaiwanStockInfo` 取得四碼數字代號 **2,542 檔**為母體，固定種子抽樣 400 檔逐一查詢。**實際掃完 326 檔後被限流擋下**（見 §6.2），以下是那 326 檔的結果。

| 項目 | 值 |
|---|---|
| 掃描檔數 | **326**（送出 327 請求，最後一個收 402） |
| 命中列數 | **115 列**，涵蓋 **67 檔** |
| 最早一列 | `2011-08-25` / `1451` 年興 / `Cash refund`（22.5 → 24.28） |
| 最新一列 | `2026-08-03` / `1459` 聯發 / `Cash refund`（11.85 → 12.46） |
| **一檔多列** | **26 檔**。最多的是 `2327` 國巨（6 列：2013、2014、2016、2017、2022 兩次）與 `1451`、`6225`（各 5 列） |

**逐年列數**（抽樣 326 檔，非全市場）：

```
2011: 1   2012: 6   2013: 9   2014: 4   2015:10   2016: 8
2017:11   2018: 8   2019: 9   2020: 9   2021: 7   2022:14
2023: 9   2024: 4   2025: 4   2026: 2
```

**兩項可直接讀出的事實**：

1. **是全歷史，不是快照**——26 檔各有多列，且跨度達 15 年（`1451` 一檔就有 2011／2012／2013 兩次／2017 五列）。
2. **回溯至少到 2011-08-25**（抽樣所及的最早一列）。**這不是 dataset 的下限**——抽樣只涵蓋 326/2,542 檔，真正的下限**未能查證**。

> ⚠️ 逐年列數是**抽樣值**（約 12.8% 的母體），不可直接當成全市場的年度發生頻率。它能支持的推論只有「這件事每年都在發生，不是罕見事件」，不能支持任何精確的頻率估計。

### 3.3 ⚠️ `after/before` 比值在減資場合**不等於**股數比率

TWSE [「股票減資恢復買賣參考價格」](https://www.twse.com.tw/zh/announcement/reduction/twtauu.html) 頁面公布的公式（逐字引用，2026-08-09 查）：

> 恢復買賣參考價＝（停止買賣前收盤價-息值-每股退還股款）/（減資換股率）　　【退還股款】
> 恢復買賣參考價＝（停止買賣前收盤價）/（減資換股率）　　【彌補虧損】
> 恢復買賣參考價＝（停止買賣前收盤價）/（減資換股率）；減資後現金增資除權參考價＝（恢復買賣參考價+現金增資認購價\*減資後現金增資配股率）/（1+減資後現金增資配股率）　　【彌補虧損並現金增資】

同頁英文版（<https://www.twse.com.tw/en/announcement/reduction/twtauu.html>）以代號寫成同樣三式，可交叉比對：

> Capital reduction by cash refund of capital stock: Post-Reduction Reference Price＝ [ (A)-(F)-(B) ] / (C)
> Capital reduction for purposes of making up losses: Post-Reduction Reference Price＝ (A) / (C)
> Capital Reduction and Cash Injection: Post-Reduction Reference Price＝ (A) / (C); Ex-right Reference Price = [Post-Reduction Reference Price +(D)\*(E) ] / [ 1+(E) ]

**三式共用同一個輸出欄位 `PostReductionReferencePrice`，但分子扣項不同 —— 而 dataset 裡唯一能區分它們的線索只有 `ReasonforCapitalReduction` 這個自由文字欄（見 §3.4）。**

用實測資料驗這條公式（**粗體是 API 實測值；括號中的換股率與退還股款是本文從公式反解，標為推論**）：

| 標的 | `date` | `ReasonforCapitalReduction` | before → after（實測） | `after/before`（實測） | 反解（推論） |
|---|---|---|---|---|---|
| `6116` 彩晶 | 2012-09-27 | `Making up losses` | **1.69 → 3.38** | **2.0000** | 換股率 0.5。彌補虧損式分子無扣項，故比值**恰好**是換股率倒數 |
| `2603` 陽明 | 2022-09-19 | `Cash refund` | **80.8 → 187.0** | **2.3144** | 換股率 0.4、每股退還 6.0 元：`(80.8 − 6.0) / 0.4 = 187.0`。換股率倒數 2.5 **≠** 比值 2.3144 |
| `2409` 友達 | 2022-10-11 | `Cash refund` | **14.7 → 15.87** | **1.0796** | 換股率 0.8、每股退還 2.0 元：`(14.7 − 2.0) / 0.8 = 15.875`。換股率倒數 1.25 **≠** 比值 1.0796 |

> 反解出的換股率與退還股款是**推論不是查證**（兩者恰好都是整數、且兩式分毫吻合，是強證據但仍是推論）。**查證到的部分是**：TWSE 公式原文（分子含 `−每股退還股款` 項）、以及 API 回應中的 `ClosingPriceonTheLastTradingDay` 與 `PostReductionReferencePrice` 數值。這兩者已足以確立「退還股款型減資的 `after/before` 不是股數比率」，不依賴反解是否正確。

**這是分割與減資之間一個結構性的、不是量級上的差異**：

- **分割／面額變更**：`before/after` **就是**股數倍數（TWSE 公式分子無扣項）。
- **退還股款型減資**：`before/after` **混入了現金退款**，不是股數倍數。`TaiwanStockCapitalReductionReferencePrice` **沒有任何欄位單獨給出「減資換股率」或「每股退還股款」** —— 兩者都被壓進同一個參考價裡，**無法從這個 dataset 分離**。

> 對 [`20-corporate-actions.md`](../briefing/20-corporate-actions.md) 待決 2 選項 A（「比照 #15 公式，用 `after_price/before_price` 當調整比率」）的意義：**這條公式對分割成立，對退還股款型減資不成立。** 若日後把減資併進同一條路徑，會得到一個「看起來已經修好了」但實際錯的比率 —— 且與該節列出的失效模式一樣，**不會有任何錯誤訊息**。本文只陳述此事實，不建議任何做法。

### 3.4 ⚠️ `ReasonforCapitalReduction` 同時混用中英文

抽樣掃描命中的資料列中，這個欄位出現了**四個值**，其實只有兩種意思：

| `ReasonforCapitalReduction` 值 | 列數 | 語意 |
|---|---|---|
| `Cash refund` | **34** | 退還股款（**分子有扣項**） |
| `現金減資` | **16** | 同上 |
| `Making up losses` | **32** | 彌補虧損（分子無扣項） |
| `彌補虧損` | **33** | 同上 |

**兩種語意、四種寫法，且中英文各佔約一半**（英文 66 列、中文 49 列）。

**同一語意的兩種寫法並存**。若偵測邏輯用 `WHERE ReasonforCapitalReduction = 'Cash refund'` 過濾，會漏掉寫成「現金減資」的那些列 —— 而 §3.3 才剛說明，**正是這兩類需要被區分開**。

### 3.5 `TaiwanStockParValueChange`：與 `TaiwanStockSplitPrice` 重疊，且已經落後

FinMind 另有一個 dataset「台灣股票變更面額恢復買賣參考價格」。**它只能不帶 `data_id` 拉全市場**，帶 `data_id` 會被明確拒絕：

```
?dataset=TaiwanStockParValueChange&data_id=6548  → HTTP 400
{"msg":"parameter data_id don't provide on TaiwanStockParValueChange dataset","status":400,"token_tail":""}
```

不帶 `data_id` 拉回 **16 列，2019-09-09 ~ 2025-08-25**，欄位名與 `TaiwanStockSplitPrice` 不同（`before_close`／`after_ref_close`／`after_ref_max`／`after_ref_min`／`after_ref_open`），另多一個 `stock_name`：

```json
{"date":"2019-09-09","stock_id":"6548","stock_name":"長科","before_close":312.0,"after_ref_close":31.2,"after_ref_max":34.3,"after_ref_min":28.1,"after_ref_open":31.2}
```

**兩個 dataset 的關係（實測比對）**：`TaiwanStockParValueChange` 的 16 列，**逐列都能在 `TaiwanStockSplitPrice` 的 21 列 `type='面額變更'` 中找到數值相同的對應列**。反過來不成立 —— `TaiwanStockSplitPrice` 多出的 5 列（`8422` 2025-11-17、`7780` 2026-01-19、`8932` 2026-03-09、`8937` 2026-04-13、`3086` 2026-04-20）**全部晚於 `TaiwanStockParValueChange` 的最後一列 2025-08-25**。

> **推論**（本文未向 FinMind 求證）：`TaiwanStockParValueChange` 的更新管線自 2025-08-25 起已停擺，而 `TaiwanStockSplitPrice` 仍在更新並涵蓋同樣的面額變更事件。事實部分是：**兩者內容重疊，其中一個少了最近 5 筆。**

---

## 4. 換股與合併：沒有可程式化資料源

### 4.1 FinMind：合法 dataset 全清單中沒有

拿一個不存在的 dataset 名稱打 API，FastAPI 的 enum 驗證會把**全部合法值原樣吐出來**，這是拿到權威清單最省事的辦法：

```
?dataset=TaiwanStockMerger&data_id=2330  → HTTP 422
{"detail":[{"type":"enum","loc":["query","dataset"],
 "msg":"Input should be 'CnnFearGreedIndex', 'CrudeOilPrices', ... }]}
```

完整清單見原始輸出 §C3（回應原文照抄），並與 [FinMind 官方台股資料集清單](https://finmind.github.io/tutor/TaiwanMarket/DataList/)逐一比對。與公司行動有關的只有五個：

| dataset | 官方中文說明 | 涵蓋 |
|---|---|---|
| `TaiwanStockDividendResult` | 除權除息結果表 | 除權息 |
| `TaiwanStockDividend` | 股利政策表 | 股利宣告 |
| `TaiwanStockSplitPrice` | 台股分割後參考價 | 分割／反分割／面額變更 |
| `TaiwanStockParValueChange` | 台灣股票變更面額恢復買賣參考價格 | 面額變更（見 §3.5） |
| `TaiwanStockCapitalReductionReferencePrice` | 減資恢復買賣參考價格 | 減資 |

**沒有任何 dataset 對應合併、換股、股份轉換。** `TaiwanStockMerger` / `TaiwanStockShareSwap` / `TaiwanStockConversion` 三個猜測名稱皆回 HTTP 422。

唯一沾得上邊的是 `TaiwanStockDelisting`（台灣股票下市櫃表），不帶 `data_id` 可拉全市場：

```
?dataset=TaiwanStockDelisting  → rows=340
欄位：['date','stock_id','stock_name']
最舊：{"date":"2001-01-20","stock_id":"1505","stock_name":"楊鐵工廠"}
```

**只有三欄，沒有下市原因、沒有換股比例、沒有存續公司代號。** 併購被吃掉的公司會出現在這裡，但**看不出它是被誰吃掉、換股比例多少** —— 而換股比例正是重建部位唯一需要的數字。

### 4.2 TWSE OpenAPI（143 paths）：沒有

`https://openapi.twse.com.tw/v1/swagger.json` 逐 path 掃過（關鍵字：減資／分割／面額／換股／合併／停止買賣／暫停／恢復／終止／換發／參考價），命中 7 個，逐一檢視後**沒有一個是公司行動的參考價或換股比例表**：

| path | summary | 為什麼不適用 |
|---|---|---|
| `/exchangeReport/TWTAWU` | 集中市場暫停交易證券 | 實測**回 1 列**（只有當日）。欄位 `TradingHaltDate`／`TradingResumptionDate`，**不含事件原因與參考價** |
| `/company/suspendListingCsvAndHtml` | 終止上市公司 | 實測 264 列。欄位僅 `DelistingDate`／`Company`／`Code`，**與 FinMind `TaiwanStockDelisting` 同樣缺原因與換股比例** |
| `/opendata/t187ap26_L` | 經營權異動且營業範圍重大變更**停止買賣**公司 | 語意是治理事件，非公司行動 |
| `/opendata/t187ap29_C_L`、`_D_L` | **合併報表**董事／監察人酬金 | 「合併」在此指合併財報，非企業合併 |
| `/exchangeReport/TWTBAU1`、`TWTBAU2` | **暫停**先賣後買當沖 | 與公司行動無關 |

**作為對照**：除權息確實有專屬端點 `/exchangeReport/TWT48U_ALL`「上市股票除權除息**預告表**」（實測 117 列，欄位 `Date`／`Exdividend`／`StockDividendRatio`／`CashDividend` 等）。**分割、減資、換股都沒有等價物。**

### 4.3 TPEx OpenAPI（225 paths）：沒有

`https://www.tpex.org.tw/openapi/swagger.json` 同樣掃過，命中 10 個，同樣沒有公司行動參考價表。最接近的是：

| path | summary | 實測 |
|---|---|---|
| `/tpex_spendi_history` | 上櫃**歷史**公布暫停/恢復交易股票 | 360 列。欄位 `DateOfSuspendedTrading`／`DateOfResumedTrading`，**同一事件拆成兩列**（一列只填停止、一列只填恢復），**無原因、無參考價** |
| `/tpex_cmode` | 變更交易、分盤交易、管理股票與停止交易資訊 | 20 列，當日快照 |
| `/tpex_exright_prepost` | 上櫃股票除權除息**預告表** | 145 列，欄位與 TWSE `TWT48U_ALL` 對稱 —— 再次只有除權息有預告表 |

> TPEx 的 TLS 憑證缺 Subject Key Identifier，Python 3.13+ 預設的 `VERIFY_X509_STRICT` 會拒絕連線。腳本沿用 [`tw-benchmark-and-fx-sources.md`](./tw-benchmark-and-fx-sources.md) 附錄 G 已記載的同一解法（關掉 strict 旗標，仍驗證憑證鏈）。這是既有已知問題，不是本次新發現。

### 4.3b 更嚴格的否證：報表代號在兩份 swagger 原文中都找不到

上面兩節是按 `summary` 文字掃的，可能漏掉命名不直觀的端點。因此再做一次**在 swagger 原始文字上直接搜 TWSE 那四張公司行動報表的代號**（腳本 §E2b）：

| 搜尋字串 | `openapi.twse.com.tw` swagger | `tpex.org.tw/openapi` swagger |
|---|---|---|
| `TWTC9U`（ETF分割預告表） | ❌ 不存在 | ❌ 不存在 |
| `TWTCAU`（ETF分割恢復買賣參考價） | ❌ 不存在 | ❌ 不存在 |
| `TWTAUU`（減資恢復買賣參考價） | ❌ 不存在 | ❌ 不存在 |
| `TWTB8U`（變更面額恢復買賣參考價） | ❌ 不存在 | ❌ 不存在 |
| `reduction` / `split` | ❌ 兩者皆不存在 | ❌ 兩者皆不存在 |
| `ParValue` | ❌ 不存在 | ⚠️ 出現，但全部無關 |
| `ReferencePrice` | ❌ 不存在 | ⚠️ 出現，但全部無關 |

TPEx 那兩個 ⚠️ 逐一查過，出現在三個不相干的地方：`ParValueOfCommonStock`（上櫃股票基本資料的「普通股每股面額」）、`ParValueOfPurchase`／`ParValueOfSell`（債券買賣面額）、`NextReferencePrice`（次日參考價）與 `OpeningReferencePrice`（除權息計算結果表的開始交易基準價）。**沒有一個是公司行動的恢復買賣參考價。**

### 4.4 存在但**不在**開放授權側的官方表

查證過程中確認 TWSE 網站上有四張與公司行動直接對應的表。它們**全部**在 `www.twse.com.tw/zh/announcement/*`，即 [`tw-fundamental-chip-data-sources.md`](./tw-fundamental-chip-data-sources.md) §4.1 判定的**爬蟲禁止側**，且**未出現在 `openapi.twse.com.tw` 的 143 個 path 中**：

| 表 | URL | 對應的 FinMind dataset |
|---|---|---|
| ETF分割(反分割)**恢復買賣參考價格** | `/zh/announcement/split/twtcau.html` | `TaiwanStockSplitPrice` |
| ETF分割(反分割)**預告表** | `/zh/announcement/split/twtc9u.html` | **無** |
| 變更股票面額**恢復買賣參考價格** | `/zh/announcement/change/twtb8u.html` | `TaiwanStockParValueChange`／`TaiwanStockSplitPrice` |
| 股票**減資**恢復買賣參考價格 | `/zh/announcement/reduction/twtauu.html` | `TaiwanStockCapitalReductionReferencePrice` |

**兩件事實**：

1. **這四張表本文只用作人工查證語意的一手文件，不得寫進排程**（§0.3）。它們的存在解釋了 FinMind 三個 dataset 的資料來源，但不改變法律分界。
2. **「ETF分割(反分割)預告表」是唯一一張前瞻表，而 FinMind 沒有對應的 dataset。** 換句話說：**ETF 分割有官方預告，但在可程式化的授權側取不到；可程式化取得的只有事後的恢復買賣參考價。** 這與除權息不同 —— 除權息的預告表 `TWT48U_ALL`（上市）與 `tpex_exright_prepost`（上櫃）就在 OpenAPI 上。
   **個股的面額變更與減資，本文在 TWSE 網站上沒有找到對應的預告表**（`/zh/announcement/change/` 與 `/zh/announcement/reduction/` 下只找到「恢復買賣參考價格」）—— 但本文並未窮舉 TWSE 站上所有公告頁，**「個股面額變更／減資有沒有官方預告表」未能查證**。

> 這一點直接關係到 [`20-corporate-actions.md`](../briefing/20-corporate-actions.md) 待決 4 選項 A 的代價欄（「本文未查證分割公告的提前期一般是多久」）。**本文查到的是**：0050 的分割公告（元大投信 2025-06-17）發布於恢復買賣前一日，而分割申請公告可上溯到 114年5月9日（同一則公告「三、本基金分割相關公告資訊統整」自述）。**但這些都在禁止側或投信官網，不在可程式化授權側。**
>
> **推論（明確標為推論）**：若偵測只靠 `TaiwanStockSplitPrice`，最快也要等到**恢復買賣當日盤後**才會知道，沒有提前示警窗口。本文未實測 FinMind 該 dataset 每日更新的時點，**未能查證**。

---

## 5. 對既有規格／簡報的影響

> 本節只指出**敘述與本次查證結果不一致之處**，不建議如何改。

### 5.1 ⚠️ `transaction-input.md` §8「減資……沒有乾淨的官方 feed」與事實不符

原文（[`docs/spec/transaction-input.md`](../spec/transaction-input.md) §8）：

> 減資與換股一年難得一次、**沒有乾淨的官方 feed**（#3 已將 MOPS 列為不建議程式化存取），而 `CONTEXT.md` 已把 `ADJUSTMENT` 定義為「刻意保留的逃生門」—— 那就讓它當逃生門。

逐條對照本次查證：

| #19 的三條件 | 減資 | 換股／合併 |
|---|---|---|
| **有官方資料源** | ❌ 敘述不成立。`TaiwanStockCapitalReductionReferencePrice` 免費可用、欄位名可逐字對回 TWSE 英文版頁面、實測回溯逾十年，**且與除權息走的是同一個 FinMind API** | ✅ 敘述成立。FinMind 合法 dataset 全清單、TWSE 143 paths、TPEx 225 paths 全部掃過，沒有 |
| **頻率高** | 本文未重新評估，但抽樣掃描的逐年分布（見 §3.2）是一項可用的新事實 | 本文未查證 |
| **不做會靜默出錯** | 本文未評估（屬決策範圍） | 同左 |

**要點是**：#19 的結論建立在「減資與換股**綁在一起**沒有 feed」。本次查證把這兩者拆開了 —— **換股／合併那一半仍然成立，減資那一半不成立**。#19 的結論本身可能仍然正確（三條件缺一即否，「頻率高」與「不做會靜默出錯」本文沒碰），但**支撐它的那條理由對減資已經不成立**。

同一段敘述也出現在 [`20-corporate-actions.md`](../briefing/20-corporate-actions.md) §3.1(b)、§3.2 選項 A 的代價欄與 §3.3 第 1 項。

### 5.2 ⚠️ `20-corporate-actions.md` §4.1(e)「資料集屬性未經充分驗證」已解

原文標記 `TaiwanStockSplitPrice` 是快照或全歷史「未能查證」。**§1 已解：是全歷史，但下限 2019-09-09。** 對應地，§4.3 第 1 項與「可以脫離主線、獨立處理的兩件事」表格中的同一項，都可以劃掉。

### 5.3 ⚠️ 待決 2 選項 A 的適用範圍要縮小到「分割」

[`20-corporate-actions.md`](../briefing/20-corporate-actions.md) §2.2 選項 A 的剩餘風險寫的是「實測樣本僅 0050 一檔，尚未跨標的交叉驗證」。本文的補充是：

- **對分割／面額變更**：§2.1 的 TWSE 公式（`恢復買賣參考價 = 停止買賣前最後收盤價 / 分割比率`）是**恆等式不是經驗規律**，跨標的交叉驗證這個顧慮可以消掉。
- **對減資**：§3.3 顯示公式不同，`after/before` 混入現金退款。**若待決 3 選了「三者共用一套機制」，這條公式會在減資場合給出錯的比率。**

### 5.4 `alerts.md` 的除權息公式仍完好，但兩張表的欄位名不同

[`alerts.md`](../spec/alerts.md) §4 的規則是「除權息日將 `peak_price` 乘上 `reference_price / before_price`」。`TaiwanStockSplitPrice` **沒有** `reference_price` 欄位（本次覆核與 [`20-corporate-actions.md`](../briefing/20-corporate-actions.md) §2.1(d) 於 2026-08-08 的查證一致），減資表則叫 `PostReductionReferencePrice`。三張表對「調整後參考價」用了**三個不同的欄位名**：

| dataset | 調整前 | 調整後 |
|---|---|---|
| `TaiwanStockDividendResult` | `before_price` | `after_price` / `reference_price`（0050 全歷史 32/32 相等） |
| `TaiwanStockSplitPrice` | `before_price` | `after_price` |
| `TaiwanStockCapitalReductionReferencePrice` | `ClosingPriceonTheLastTradingDay` | `PostReductionReferencePrice` |

### 5.5 `pending_action.source` 的既有範例是 TWSE 端點，分割只能填 FinMind

[`data-model.md`](../spec/data-model.md) 第 241 行對 `pending_action.source` 的說明是「產生來源，如 `twse_TWT48U_ALL`」—— 即除權息那條路徑的來源是**政府資料開放授權側的官方端點**。

本文查證的結果是：**分割與減資沒有等價的官方端點**（§4.2、§4.4），可程式化的來源只有 FinMind。這代表若沿用同一個 `source` 欄位，分割類 `pending_action` 的值會是 `finmind_TaiwanStockSplitPrice` 之類 —— 而 FinMind 的資料再散布授權是 §7 第 7 項的未決風險。**兩條路徑的來源在授權性質上並不對等**，這是事實陳述，不是建議。

### 5.6 未受影響、本文查證後仍成立的既有敘述

- [`tw-benchmark-and-fx-sources.md`](./tw-benchmark-and-fx-sources.md) §B.4 對 0050 的所有數字（2025-06-18、188.65、47.16、停止買賣 5 個交易日、2025-06-10 收盤 188.65）**逐項與官方公告吻合**。
- 同文附錄 G 記載 `TaiwanStockSplitPrice`（0050）1 列、`TaiwanStockCapitalReductionReferencePrice`（0050）0 列 —— **本次複驗完全相同**。
- 「停止買賣期間 `TaiwanStockPrice` 缺列、不補列」在 9 個案例中全部成立。

---

## 6. FinMind 免費層（無 token）的權限矩陣與限流

### 6.1 「不帶 `data_id` 全市場拉取」只有三個 dataset 放行

同一個問題（`?dataset=X&start_date=2026-08-01`，不帶 `data_id`）對八個 dataset 各打一次：

| dataset | 結果 |
|---|---|
| `TaiwanStockSplitPrice` | ✅ HTTP 200 |
| `TaiwanStockParValueChange` | ✅ HTTP 200（且**只能**這樣打，見 §3.5） |
| `TaiwanStockDelisting` | ✅ HTTP 200 |
| `TaiwanStockCapitalReductionReferencePrice` | ❌ HTTP 400 |
| `TaiwanStockDividendResult` | ❌ HTTP 400 |
| `TaiwanStockDividend` | ❌ HTTP 400 |
| `TaiwanStockPrice` | ❌ HTTP 400 |
| `TaiwanStockSuspended` | ❌ HTTP 400（整個 dataset 屬付費層，本文未再試 `data_id` 形式） |

HTTP 400 的回應原文一致：

```json
{"msg":"Your level is free. Please update your user level. Detail information:https://finmindtrade.com/analysis/#/Sponsor/sponsor","status":400,"token_tail":""}
```

> **`TaiwanStockSplitPrice` 能不帶 `data_id` 拉全市場，是一個不尋常的例外** —— §1 之所以能一次拿到全歷史 32 列並找出重複標的，靠的就是這個。**這不是可以指望的通則**：同一族的減資與除權息 dataset 都被擋。（FinMind 是否會改變這個政策，本文無從查證。）

### 6.2 實際觀察到的限流：HTTP 402，且回應標頭沒有任何線索

**本次執行的實測門檻**：無 token 的情況下，**第 366 個累計請求開始被擋**（§F2 的第 327 檔，`stock_id=6928`）。該節在 **20.8 秒**內送出 327 個請求，狀態碼分布 `{200: 326, 402: 1}`。

> ⚠️ **366 這個數字不是官方額度**，它是「本次執行到被擋為止的累計請求數」。額度的計算窗口（滾動一小時？固定小時？）、以及是否含之前節次的請求，本文**未能查證**。

回應標頭全文（HTTP 200 時）：

```
Access-Control-Allow-Origin: *
Content-Length: 198
Content-Type: application/json
Date: Sun, 09 Aug 2026 11:06:10 GMT
Server: uvicorn
```

**沒有任何 `X-RateLimit-*`、`Retry-After` 或類似欄位** —— 用量只能自己數，或靠 402 回頭修正。這與 [`tw-fundamental-chip-data-sources.md`](./tw-fundamental-chip-data-sources.md) §8 記載的「600 req/hr **with token**」是兩件事：本文測的是**無 token** 的情形。

被擋時的回應原文：

```json
{"msg":"Requests reach the upper limit. https://finmindtrade.com/","status":402,"token_tail":""}
```

> 注意 status code 是 **402 Payment Required**，不是慣例的 429。任何「重試遇到 429 才退避」的邏輯都會漏接。

---

## 7. 未能查證，需人工確認

1. **`TaiwanStockSplitPrice` 為何回溯下限是 2019-09-09** —— 是 TWSE 該張公告表的線上保存範圍，還是 FinMind 的抓取起點？本文未向任何一方求證。
2. **一般個股（非 ETF）的 `date` 是否等於「換發基準日」** —— 已確定等於「恢復買賣日」；法規把基準日定義為另一個日期，但個股逐案基準日不在任何可程式化端點上（§2.4）。
3. **`TaiwanStockSplitPrice` 每日更新的時點** —— 是恢復買賣當日盤後，還是隔日？本文未做跨日觀測，因此「有沒有提前示警窗口」無法從實測回答（§4.4）。
4. **`type` 欄位為空字串（`00631L` 2026-03-31）的原因** —— 是 FinMind 抓取遺漏，還是 TWSE 原始公告該欄即為空？未查證。
5. **`max_price=9999.95` / `min_price=0.01` 是否為 TWSE 對「首日無漲跌幅」的正式表達** —— 本文標為推論（§1.5）。
6. **`ReasonforCapitalReduction` 為何中英文混用** —— 是 TWSE 原始資料在某個時點改過語言，還是 FinMind 兩條管線並存？未查證（§3.4）。
7. **FinMind 資料再散布授權** —— [`tw-fundamental-chip-data-sources.md`](./tw-fundamental-chip-data-sources.md) §7 第 3 項的既有未決項，**本文沿用，未重新查證**。本專案為 public repo，此風險同時涵蓋本文列出的全部 FinMind dataset。
8. **FinMind 無 token 的官方額度數字** —— 官方文件未見公告；本文只有 §6.2 的實測觀察，不是官方值。
9. **換股／合併是否存在本文查證範圍以外的可程式化來源** —— 本文掃過 FinMind、`openapi.twse.com.tw`、`www.tpex.org.tw/openapi` 三處。券商 API（Fugle 等）、集保結算所等其他來源**未查證**。
10. **個股（非 ETF）的面額變更／減資有沒有官方預告表** —— 本文只在 `/zh/announcement/change/` 與 `/zh/announcement/reduction/` 下找到「恢復買賣參考價格」，未窮舉 TWSE 站上所有公告頁（§4.4）。

---

## 8. 附錄：本文用到的端點與文件

**FinMind**（皆未帶 token 實測，`https://api.finmindtrade.com/api/v4/data`）

```
?dataset=TaiwanStockSplitPrice&start_date=1990-01-01              32 列 / 2019-09-09 起 / 全市場（免費可用）
?dataset=TaiwanStockSplitPrice&data_id=6548                       2 列  ← 同一標的多列的證明
?dataset=TaiwanStockSplitPrice&data_id=8932                       2 列  ← 同上
?dataset=TaiwanStockParValueChange&start_date=1990-01-01           16 列 / 2019-09-09 ~ 2025-08-25 / 不接受 data_id
?dataset=TaiwanStockCapitalReductionReferencePrice&data_id=2603    1 列  / 2022-09-19 / 需帶 data_id
?dataset=TaiwanStockDelisting                                      340 列 / 2001-01-20 起 / 僅三欄
?dataset=TaiwanStockPrice&data_id=<代號>&start_date=&end_date=      §2.2 逐案核對用
?dataset=TaiwanStockSuspended                                      ❌ HTTP 400「Your level is free」
（不存在的 dataset 名稱 → HTTP 422，回應內含全部合法 dataset 清單）
```

**TWSE／TPEx OpenAPI**（政府資料開放授權側）

```
https://openapi.twse.com.tw/v1/swagger.json                        143 paths，無公司行動參考價端點
https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU               集中市場暫停交易證券，實測 1 列
https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml    終止上市公司，實測 264 列
https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL           除權息預告表（對照組），實測 117 列
https://www.tpex.org.tw/openapi/swagger.json                       225 paths，同樣沒有
https://www.tpex.org.tw/openapi/v1/tpex_spendi_history             暫停/恢復交易，實測 360 列
https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost            除權息預告表（對照組），實測 145 列
```

**一手文件**（人工查閱，未以程式存取）

```
https://www.twse.com.tw/zh/ETFortune/announcement?company=A00005&date=20250617&seq=1&fund=0050&type=all
                                                   元大投信 2025-06-17 公告：0050 分割時程與 47.16 參考價
https://www.twse.com.tw/zh/announcement/split/twtcau.html          ETF分割(反分割)恢復買賣參考價格（含公式）
https://www.twse.com.tw/zh/announcement/split/twtc9u.html          ETF分割(反分割)預告表 ← 官方唯一的前瞻表
https://www.twse.com.tw/zh/announcement/change/twtb8u.html         變更股票面額恢復買賣參考價格
https://www.twse.com.tw/zh/announcement/reduction/twtauu.html      股票減資恢復買賣參考價格（含三條公式）
https://twse-regulation.twse.com.tw/m/LawContent.aspx?FID=FL007110 上市公司換發有價證券作業程序（106.08.31）
https://finmind.github.io/tutor/TaiwanMarket/DataList/             FinMind 台股資料集清單（93 個）
```

**顯名標示**：本文若有任何結論被實作採用並對外呈現，`openapi.twse.com.tw` 與 `tpex.org.tw/openapi` 部分沿用 [`tw-benchmark-and-fx-sources.md`](./tw-benchmark-and-fx-sources.md) §H 的頁尾標示格式；FinMind 部分的標示義務**取決於 §7 第 7 項的未決授權問題**。
