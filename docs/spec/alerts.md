# 警示的觸發模型與通知管道 v1

決策票：[決策：警示的觸發模型與通知管道](https://github.com/NTUyu016/stock-analytic-platform/issues/15)
相關規格：[`realtime-quotes.md`](./realtime-quotes.md)、[`data-model.md`](./data-model.md)、[`dashboard-ui.md`](./dashboard-ui.md)、[`transaction-input.md`](./transaction-input.md)

---

## 總覽

| 項目 | 結論 |
|---|---|
| 通知管道 | **Discord webhook**，通知內文**不含任何金額與百分比** |
| 盤中評估者 | **`quote-worker`**，在 conflation **之前**逐筆評估 |
| 盤後評估者 | 既有盤後排程，與 `daily_close` 同班車 |
| 訂閱頻道 | **`trades`**（逐筆成交），非 `aggregates` |
| 去重策略 | **回歸重置**（hysteresis 0.5%），非一次性、非時間冷卻 |
| 規則類型 | 盤中 4 種（價格門檻、當日漲跌幅、未實現報酬率、追蹤停損）＋ 盤後 2 種（成交量異常、除權息事前提醒） |
| 送達時限 | 盤中 ≤30 分鐘（實際為秒級）；盤後總結 14:00 前 |
| 靜音時段 | **不需要** —— 盤中警示結構上只在 09:00–13:35 產生 |
| 規則量級 | 5–10 條 → 面板平鋪，不摺疊、不分頁 |

**一句話的代價**：警示與即時報價綁在同一個開關上。關掉 `quote-worker` 省錢，盤中警示就跟著消失。使用者已明確接受，但**這件事必須在介面上外顯**（§9）。

---

## 0. 兩條路徑，不是一條

驅動來源本質不同，所以是兩套機制，共用資料模型與通知管道：

```
┌─ 盤中路徑（09:00–13:35，quote-worker）──────────────────────┐
│                                                              │
│  Fugle trades ──> adapter ──> 逐筆 Quote                     │
│                                  │                           │
│                    ┌─────────────┴─────────────┐             │
│                    ▼                           ▼             │
│              警示評估（逐筆）            conflation 800ms     │
│                    │                           │             │
│                    ▼                           ▼             │
│           notification + Discord POST    LISTEN/NOTIFY → SSE │
└──────────────────────────────────────────────────────────────┘

┌─ 盤後路徑（排程，與 daily_close 同班車）──────────────────────┐
│  FinMind 日線 ──> daily_close ──> 成交量異常評估              │
│  TWSE/TPEx 除權息預告 ──────────> 除權息事前提醒              │
│                                        │                     │
│                                        ▼                     │
│                            每日總結一則 Discord（14:00 前）   │
└──────────────────────────────────────────────────────────────┘
```

### ⚠️ 硬性規則：兩條路徑的分岔點在 conflation 之前

盤中警示**必須讀未經 conflation 的逐筆 Quote**。

**為什麼**：Fugle 免費層的 5 個額度是「5 個 (標的 × 頻道) 配對」，5 檔持股只夠訂**一個**頻道，本專案選了 `trades` 以換取逐筆精度（§10）。若警示掛在 conflation 之後，看到的就只有每 800ms 的當下價格 —— 那正是 `aggregates` 的行為。**等於付了 `trades` 的代價、得到 `aggregates` 的結果，而且不會有任何錯誤訊息。**

畫面推播照舊走 conflation（`realtime-quotes.md` §6），兩條路在 worker 內分岔，互不影響。

---

## 1. 規則類型：六種，不用開放式運算式

### 決定

| # | 類型 | `rule_type` | 參數 | 誰評估 |
|---|---|---|---|---|
| 1 | 價格門檻 | `PRICE_ABOVE` / `PRICE_BELOW` | `threshold` 價格 | 盤中，逐筆 |
| 2 | 當日漲跌幅 | `CHANGE_PCT_ABOVE` / `CHANGE_PCT_BELOW` | `threshold` 百分比 | 盤中，逐筆 |
| 3 | 未實現報酬率 | `RETURN_PCT_ABOVE` / `RETURN_PCT_BELOW` | `threshold` 百分比 | 盤中，逐筆 |
| 4 | 追蹤停損 | `TRAILING_STOP` | `threshold` 回落百分比 | 盤中，逐筆（§4） |
| 5 | 成交量異常 | `VOLUME_SPIKE` | `threshold` 倍數 | **盤後** |
| 6 | 除權息事前提醒 | `EX_DIVIDEND_AHEAD` | `threshold` 提前交易日數，預設 **3** | **盤後** |

### 為什麼不做開放式條件運算式

「讓使用者自己組合欄位與運算子」聽起來更彈性，但它把**規則的合法性**從資料庫與型別系統移交給執行期字串解析。本專案已經在 #19、#13、#10 三次撞到同一個形狀：**寫錯不報錯**。開放式運算式是這個形狀最大的溫床 —— 一個打錯的欄位名在多數實作裡會求值為 null，然後規則永遠不觸發，而畫面上它一直亮著「監控中」。

六種具名類型能覆蓋 5–10 條規則的實際需求，且每一種都能在 `CHECK` 與 Pydantic 兩層被完整驗證。

### ⚠️ 硬性規則：類型 3 與 4 依賴持股，刪倉必須連帶處理

`RETURN_PCT_*` 與 `TRAILING_STOP` 的語意建立在「使用者持有這檔」之上。當股數歸零：

- `TRAILING_STOP` 的峰值**重置**（§4）
- 兩者的規則**自動轉為停用**並在面板上標示原因，**不可靜默保留**

一條算不出值的規則若還顯示為啟用中，就是 `dashboard-ui.md` §3「永遠亮著等於沒有」的變形。

---

## 2. 資料模型

### 2.1 `alert`：使用者意圖，具名欄位不用裸 `jsonb`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK NOT NULL | |
| `instrument_id` | `bigint` FK NOT NULL | |
| `rule_type` | `text` NOT NULL | §1 的六種之一，`CHECK (rule_type IN (...))` |
| `threshold` | `numeric(20,8)` NOT NULL | 語意隨 `rule_type` 而異，見 §1 |
| `is_enabled` | `boolean` NOT NULL DEFAULT true | |
| `is_deleted` | `boolean` NOT NULL DEFAULT false | **軟刪除**，沿用 `instrument.is_active` 先例 |
| `created_at` | `timestamptz` NOT NULL | |

**這是對 [`data-model.md`](./data-model.md) `alert` 表的修訂** —— 原本的 `condition jsonb` 佔位欄位由 `rule_type` + `threshold` 取代。

#### 為什麼不是 `jsonb`

原本擔心的「`jsonb` 裡的數字是浮點數會掉精度」**經查證是錯的**：PostgreSQL 官方文件 Table 8.23 明載 JSON `number` 存成 `numeric`，`599.99` 在資料庫裡是精確的（見 [`postgres-jsonb-constraints.md`](../research/postgres-jsonb-constraints.md)）。

**但風險換了個位置**：psycopg 預設用標準庫 `json.loads`，實測（Python 3.13）反序列化出來是 `float`，`Decimal(599.99)` 會變成 `Decimal('599.990000000000009094947017729282379150390625')`。官方有解（`set_json_loads(partial(json.loads, parse_float=Decimal))`），**但這一行漏寫不會有任何錯誤訊息**。

具名 `numeric` 欄位的精度保證是**零設定**的，與既有的 `price numeric(20,8)`、`fee numeric(20,4)` 同源。

另一個決定性理由：**`CHECK` 約束對 NULL 放行**。官方原文寫 constraint「satisfied if the check expression evaluates to **true or the null value**」。所以 `condition->>'operator' IN ('gt','lt')` 這種寫法在鍵名打錯時求值為 NULL，**照樣放行**。而「用 CHECK 保護 jsonb」這件事本身，就是一個漏寫不報錯的活動。

**不採用 `pg_jsonschema`**：它是唯一能在 DB 層做真 schema 驗證的路，但 **Fly Managed Postgres 與 Render 都不支援**，選它等於在 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) 上砍掉部署選項。

**疊加 Pydantic discriminated union 當 API 門衛**（必須 `extra='forbid'`，預設 `'ignore'` 會靜默丟掉多餘欄位）。它擋不住 migration 與手動 `psql`，但錯誤訊息最好，且 mypy 能在寫程式時就抓到分支不全。

### 2.2 `alert_state`：worker 的運行狀態，與意圖分表

| 欄位 | 型別 | 說明 |
|---|---|---|
| `alert_id` | `bigint` PK FK | 1:1 |
| `is_armed` | `boolean` NOT NULL DEFAULT true | 武裝中 / 已觸發等回歸 |
| `last_triggered_at` | `timestamptz` NULL | |
| `peak_price` | `numeric(20,8)` NULL | 僅 `TRAILING_STOP`，見 §4 |
| `peak_since` | `date` NULL | 僅 `TRAILING_STOP`，峰值起算日（建倉日） |
| `updated_at` | `timestamptz` NOT NULL | |

#### 為什麼分成兩張表

寫入者不同、生命週期不同，**而且可重建性不同**：

- `alert` 是使用者打的字，**毀了就沒了**
- `alert_state` 全部可以從 `transaction` + `daily_close` + 當前 Quote 重新算出來

分表之後，「狀態疑似錯亂」的修復動作是 `DELETE FROM alert_state` 然後重建 —— 一個安全、可重跑、不碰使用者資料的操作。若這些欄位長在 `alert` 上，同樣的修復就變成一次精準 `UPDATE`，得在使用者資料上動刀。

這也讓 `TRAILING_STOP` 專屬的兩個欄位不必以永遠為 NULL 的形式出現在其他五種規則的每一列上。

### 2.3 `notification`：補三個缺口

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK NOT NULL | **新增** |
| `alert_id` | `bigint` FK NULL | 盤後總結不對應單一 alert，故可空 |
| `triggered_at` | `timestamptz` NOT NULL | |
| `channel` | `text` NOT NULL | |
| `payload` | `jsonb` NOT NULL | 站內通知呈現用，**可含金額**（§6） |
| `status` | `text` NOT NULL | `PENDING` / `SENT` / `FAILED` / `ABANDONED` | 
| `attempts` | `smallint` NOT NULL DEFAULT 0 | |
| `delivered_at` | `timestamptz` NULL | |
| `last_error` | `text` NULL | **必須遮蔽 webhook URL**（§6） |

1. **`user_id`**：現行綱要沒有，違反 `data-model.md` 核心原則 5，而 `transaction` 早就為此刻意加了冗餘 `user_id`。漏掉不會有任何錯誤訊息。
2. **投遞狀態**：[#7](https://github.com/NTUyu016/stock-analytic-platform/issues/7) §8.3 明確要求。
   > ⚠️ 這與 [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 拒絕 `transaction.status` **不衝突**：`transaction` 是事實來源，加 `status` 會讓所有既有查詢必須記得過濾；`notification` 記的就是「一次投遞嘗試」，狀態是它的本質屬性。
3. **不設保留期限**：5–10 條規則的量級一年也就幾百列，加一個清理排程的維護成本高於它省下的空間。

### 2.4 `daily_close` 擴充為日 OHLCV

| 新增欄位 | 型別 | 用途 |
|---|---|---|
| `open` | `numeric(20,8)` | 完整性 |
| `high` | `numeric(20,8)` | **`TRAILING_STOP` 的峰值回補**（§4） |
| `low` | `numeric(20,8)` | 完整性 |
| `volume` | `bigint` | **`VOLUME_SPIKE` 的六十日均量**（§5）。單位：**股** |

> 表名維持 `daily_close`，但它現在裝的是日 OHLCV。`CONTEXT.md` 的 **Daily Close** 詞條需同步放寬措辭。

**這四個欄位是同一次 FinMind 請求的同一列**，邊際成本為零：

```
{'date': '2026-06-10', 'stock_id': '2330', 'Trading_Volume': 54194021,
 'Trading_money': 123146622990, 'open': 2285.0, 'max': 2300.0,
 'min': 2255.0, 'close': 2255.0, 'spread': -50.0, 'Trading_turnover': 510491}
```
（2026-08-06 實測，`api.finmindtrade.com/api/v4/data`，`TaiwanStockPrice`，未帶 token）

**回補範圍**：每檔標的**回補到該檔最早的建倉日**，而非固定年數。這是 `TRAILING_STOP` 的直接要求。

#### ⚠️ 硬性規則：停止買賣日不補列、不寫 `volume = 0`

FinMind 在減資／換股停止買賣期間**直接沒有那些列**（2603 於 2022-09-07～09-16 共 7 個交易日缺席）。yfinance 則**補出 7 列 OHLC 全等於 202.00、`Volume = 0` 的假列**。

**本專案採 FinMind 的做法：沒交易就沒有列。** 若補成 `volume = 0`，六十日均量會被壓低約 12%（7/60），復牌後產生假性爆量。

**連帶定義**：「六十日均量」一律指**最近 60 筆 `daily_close` 列**，不是「最近 60 個日曆交易日」。跨越停止買賣期間時兩者會差 7 天以上，必須擇一並全程一致。

#### ⚠️ 硬性規則：量的單位是「股」，跨來源必須驗

- FinMind `Trading_Volume` = **股**（官方文件 + 與 TWSE／TPEx 端點逐位元吻合）
- TPEx OpenAPI **同一份文件內就有三種單位**：`TradingShares` = 股、`AverageDailyTradingVolume` = 張、`TradingVolume` = 張
- Fugle `trades.volume` / `trades.size` 的單位**官方文件從未載明** ⚠️

混用差 **1,000 倍且不報錯**。`tech-stack.md` §7 的契約測試必須涵蓋單位斷言，Fugle 那一項在取得 API key 後**必須實測確認**（目前為未查證項）。

---

## 3. 去重：回歸重置

### 決定

觸發後 `is_armed` 轉 false。**價格回到門檻另一側並超出 0.5% 緩衝**後才重新武裝。

| 情境 | 行為 |
|---|---|
| 跌破 590 後一路跌到 560 | 響一次 |
| 跌破 590 → 彈回 610 → 又跌破 590 | 響兩次 |
| 在 590 上下抖動（589.9 / 590.1 / 589.8…） | 響一次（緩衝吸收） |

### 為什麼不是一次性、不是時間冷卻

**穿越是事件，不是狀態。** 一次性（觸發即停用）在「跌破 → 反彈 → 再跌破」時完全靜音，而且不會有任何錯誤訊息 —— 使用者以為規則還守著，實際上它上午就自己關掉了。時間冷卻則在單邊下殺時每 N 分鐘把同一件事再講一遍。

回歸重置是唯一兩種情境都答對的選項。代價是它要落地狀態，而 `alert_state`（§2.2）已經為此存在。

### ⚠️ 硬性規則：緩衝不可省

純粹的「回到門檻另一側就重新武裝」在價格貼著門檻抖動時仍會連環觸發。緩衝取 **0.5%**（相對於 `threshold`），方向與規則方向相反：

- `PRICE_BELOW 590` → 需 `price >= 590 × 1.005 = 593.0` 才重新武裝
- `PRICE_ABOVE 700` → 需 `price <= 700 × 0.995 = 696.5` 才重新武裝

### ⚠️ 硬性規則：規則建立時已處於觸發狀態，吞掉第一則

新建或重新啟用一條規則時，若當下條件已成立：**不送通知**，直接寫入 `is_armed = false`。

否則使用者一存檔，系統就對他吼一句他剛剛才親眼看到的事。這對 `TRAILING_STOP` 尤其明顯 —— 峰值一回補完就可能立刻低於停損線。

### ⚠️ 硬性規則：開盤時的武裝狀態必須重建，不可假設

`is_armed` 跨日保留（它記的是「上次觸發後價格還沒回來」，這件事會跨夜成立）。但 `quote-worker` 每天開機時**必須用 `/intraday/quote/{symbol}` 的快照重新判定一次**，因為隔夜跳空可能已經讓價格回到門檻另一側 —— 而那個回歸過程 worker 沒看見。

漏做這件事的後果：開盤跳空回來的規則整天不會武裝，而畫面顯示它「監控中」。

---

## 4. 追蹤停損

### 決定

`TRAILING_STOP` 的峰值 = **從建倉日至今的最高價**，`threshold` 為回落百分比。

- **起算點**：該標的股數從 0 變正的那一天（`peak_since`）
- **加碼不重置**
- **股數歸零即重置**：清空 `peak_price` / `peak_since`，規則轉停用（§1）
- **峰值來源**：歷史段取 `daily_close.high`，當日段取盤中逐筆最高價

### 為什麼是建倉日而非「加碼日」或「固定回看窗口」

「每次加碼都重置」會讓逐步加碼的部位停損線一路被往下拉 —— **越買越不保護**，與這條規則的目的相反。「固定回看 60 個交易日」則與使用者實際賺賠脫鉤，那是「近期高點回落」不是追蹤停損。

建倉日起算是「持有以來」最直接的讀法，且只需要一個日期，不依賴成本基礎的算法（加權平均 vs 其他），因此不會繼承 #19 已記錄的均價定義分歧。

### ⚠️ 硬性規則：峰值必須在除權息日按參考價比率下調

FinMind 與 TWSE／TPEx 的價格**都是原始值，不做任何還原**。

實測（2026-08-06）：2330 於 **2026-06-11 除息**，`close` 從 6/10 的 2255 掉到 6/11 的 2250。表面上跌 5 元，**實際除息 6 元、還原後是漲的**。

若峰值沿用未還原價：

1. 每次除權息，峰值都被墊在一個**加總了歷史股息**的位置上
2. 持有越久偏差越大，停損線越來越高
3. 最終規則**長期黏在「已觸發」狀態**，而且不會有任何錯誤訊息

**做法**：除權息日將 `peak_price` 乘上 `reference_price / before_price`。資料源為 FinMind `TaiwanStockDividendResult`（2003-05-01 起，含 `before_price` / `after_price` / `reference_price`，見 [`tw-fundamental-chip-data-sources.md`](../research/tw-fundamental-chip-data-sources.md) §3.5）。

此調整掛在盤後排程，與 [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 產生除權息 `pending_action` 的同一個事件上 —— **同一個事件、兩個消費者，不是兩次偵測**。

### ⚠️ 硬性規則：峰值可重建，且必須有重建路徑

`peak_price` 是快取不是事實。實作必須提供「從 `transaction` + `daily_close` 重算某條規則峰值」的操作，並在 worker 啟動時對 `peak_since` 為 NULL 者自動執行。

---

## 5. 盤後路徑

### 5.1 成交量異常：只在收盤後算，且明說是自訂規則

**評估**：`daily_close.volume` 當日值 > 最近 60 筆列的均量 × `threshold`（預設 5）。

**為什麼不做盤中即時**：盤中累積量要與六十日均量比較，得先回答「現在才 10:30，這個量算不算大」—— 而這個正規化規則**無任何公開一手依據**，只能自訂。這是本專案第二次遇到這個形狀（第一次是手續費元以下進位規則，由 #19 以實際交割單反推解掉）。成交量異常本來就不需要秒級反應，放進盤後總結就完全繞開它。

#### ⚠️ 硬性規則：UI 與通知必須註明「自訂規則，非證交所標準」

《臺灣證券交易所公布或通知注意交易資訊暨處置作業要點》（115.08.03 版）第 10 條的異常標準原文：

> 最近六個營業日（含當日）之日平均成交量較最近六十個營業日（含當日）之日平均成交量放大為**五倍以上**，且其放大倍數與**全體有價證券**…相差**四倍以上**

第二個條件需要當日**全市場約 1,377 檔各自的六十日均量**。本專案只存持股的歷史，**結構上算不出官方口徑**。借用「五倍」這個數字而不說明，就是誤稱官方標準。

**另兩件必須寫在同一處的事**：

- 條文第 4 條與第 10 條的除外情形**明文排除 ETF**（指數股票型基金受益憑證、主動式 ETF、ETN）。官方永遠不會因為量放大把 ETF 列為注意股，故對持股中的 ETF 而言「對齊官方定義」在定義上是空的 —— 自訂規則照樣可以跑，但不得暗示它有官方對應物。
- 歷史不足 60 筆列時（新上市、剛回補）**跳過該規則並在面板標示原因**，不得以不足的樣本計算均量。

#### 不採用「訂閱官方判定結果」

TPEx 的 `tpex_trading_warning_information` 端點實測回 29 筆，`TradingInformation` 欄位直接就是官方原文含數值（「當日之成交量較最近六十個營業日日平均成交量放大 10.11 倍(第三款)」），完全不需自算。

**但 TWSE（上市）那半今天拿不到**：`openapi.twse.com.tw/v1/announcement/notice` 兩次實測（2026-08-05 23:59、08-06 00:11）皆回傳**單一全空佔位列**而非空陣列 —— 天真的 `len(rows) > 0` 檢查會通過，然後拿到一列空資料。使用者持股四檔上市、一檔上櫃，捷徑通的剛好是只有一檔的那半。

> 若日後 TWSE 端點恢復正常，這是一條值得回頭走的路（§10）。

### 5.2 除權息事前提醒

**評估**：除息日前 `threshold`（預設 **3**）個交易日，送一則提醒。

**資料源**（皆已實測回 200，見 [`tw-fundamental-chip-data-sources.md`](../research/tw-fundamental-chip-data-sources.md) §3.5）：

| 市場 | 端點 |
|---|---|
| 上市 | `https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL` |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost` |

**為什麼要事前**：參與除息與否在除息日一到就木已成舟，而 [#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6) 查出的兩個門檻都在那之前才有決策空間 —— 股利合併 vs 分開計稅的臨界值為邊際稅率 **36.5%**，補充保費 2.11% 的門檻是「**單次給付**」達 2 萬（非年度累計）。

#### ⚠️ 硬性規則：與 `pending_action` 是兩件事，不可合併

[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 已定「除權息自動產待確認項但另立表」。事前提醒是**除息前**的決策輔助，`pending_action` 是**除息後**的入帳確認 —— 時間點、動作、生命週期全不同。合併會讓同一件事講兩遍且兩者可能不同步。

### 5.3 財報日提醒：v1 不做

yfinance `earnings_dates` 確實含未來一筆預估日（實測 2330.TW 首列 2026-10-15），但：

- 那是**預估日會漂移**，不是公告日。提醒了不準比不提醒更糟。
- 它的典型用途是「別在財報前重押」，而使用者是**已持有**部位，提醒了多半不會動作。
- 它需要 `lxml`，而 [#4](https://github.com/NTUyu016/stock-analytic-platform/issues/4) 已證實既有 skill 漏宣告 `lxml` 導致**兩個分析維度靜默失效**。把這條相依拉進盤後排程的必要路徑不划算。

> 個股分析頁仍會用 `earnings_dates` 做「距財報 ≤14 天降評」—— 那是分析不是警示，屬 [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)，與本決定不衝突。

### 5.4 每日總結

一則 Discord 訊息，**14:00 前**送達，包含：當日觸發過的警示摘要、成交量異常結果、三日內的除權息提醒。

`quote-worker` **完全不參與總結** —— 盤後排程自己取官方盤後資料即可。這與 [`realtime-quotes.md`](./realtime-quotes.md) §8「可選元件不能持有必要資料的產生責任」一致。

#### ⚠️ 排程時間必須讓開 TWSE 的延遲

實測（2026-08-06 00:11）：TWSE `STOCK_DAY_ALL` 在 2026-08-05 收盤後**逾 10.5 小時**仍只有 08-04 的資料，而同一時刻 TPEx 已有 08-05 的。

**這否證了「盤後排程當晚就拿得到當日量」。** 因此：

- `daily_close` 的每日增量走 **FinMind**（宣告週一至五 **17:30** 更新），不走 TWSE 端點
- 用 TWSE／TPEx 快照對帳 FinMind 時，**對帳必須允許延後一天**
- 每日總結的「當日成交量異常」因此依賴 FinMind 的 17:30 —— 而總結要在**隔日 14:00 前**送達，餘裕充足

---

## 6. 通知管道：Discord

### 決定

**Discord webhook**。不需 bot user、不需 authentication，官方原文："They do not require a bot user or authentication to use."

Webhook URL 走 `.env`。使用者需自建一個私人 server（webhook **綁定頻道、無法送 DM**）。

### ⚠️ 硬性規則：通知內文不含任何金額與百分比

Discord [Developer Policy](https://discord.com/developers/docs/policies-and-agreements/developer-policy) 第 16 條明文禁止 Application「transmit data to Discord … that includes … **financial information** … under applicable law」。條款對 "Application" 的定義是「**任何存取或使用我們 API 的應用程式**」—— **即使未在 Developer Portal 註冊、沒有 Application ID，`quote-worker` 打 webhook 就落在定義內**。

**如實說邊界**：條文寫的是 "under applicable law"，指依法認定的敏感資訊；立法意旨顯然是防開發者把一群使用者的資料倒進 Discord，而本專案是單人、資料主體＝傳送者本人。**但官方沒有為自用開任何例外**，條款文字裡沒有 personal use 或 self-hosted 豁免；Discord 是否曾對此表態，查遍官方文件皆無，**未能查證**。

因此通知只當敲門聲：

```
✅ 允許：代號、名稱、規則描述、當前價、觸發時間
❌ 禁止：未實現損益、市值、成本、報酬率、持有股數、任何百分比
```

> **報酬率規則是最容易漏的一格。** `RETURN_PCT_BELOW -10%` 觸發時，訊息只能寫「報酬率警示觸發」與當前價，**不可寫出實際報酬率** —— 那是由持有成本推導出的個人財務資訊，比損益金額更直接。

**附帶好處**：webhook URL 就是憑證（拿到 URL 的人**不需認證就能讀、改、永久刪除**這個 webhook）。文案裡沒有金額，URL 洩漏的損害面就小得多。

金額與完整資訊留在站內通知與儀表板，使用者點連結進網站看。

### ⚠️ 硬性規則：送出邏輯四條

1. **必須帶 `?wait=true`。** 預設回 `204 No Content`；官方原文：`wait` 預設 `false`，「when `false` a message that is not saved does not return an error」—— **預設的成功回應不代表訊息真的送出去了**。Telegram 是一律回 Message 物件，這是換管道後最容易寫錯的一行。
2. **`404` 是終局失敗，絕對不可重試。** 官方明文：「If a webhook returns a 404 status **you should not attempt to use it again** - repeated attempts to do so will result in a temporary restriction」。搭配 invalid-request limit（10 分鐘內 10,000 次 401/403/429 會被 Cloudflare 暫時封 IP）—— **沿用「無腦指數退避重試到成功」會在 webhook 被刪後連帶讓整個出站 IP 被封**。`404` 一律直接寫 `status = ABANDONED`。
3. **rate limit 不得硬編碼**，讀回應標頭。官方明文要求 "rate limits should not be hard coded into your app"，且官方**不公布**任何 per-webhook 數字（網傳的「30 則/分鐘」查無實據）。這與 [#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6)「費率一律不得硬編碼」同形。
4. **錯誤日誌與 traceback 必須遮蔽 webhook URL。** `httpx` / `requests` 預設會把完整 URL 塞進例外訊息，而 URL 就是憑證。`notification.last_error` 落地前同樣要過遮蔽。

### `ChannelCapabilities`：對稱於 `ProviderCapabilities`

管道抽象化，但**維度比原本設想的多**：

| 能力 | Discord | Telegram | 為什麼不能合併 |
|---|---|---|---|
| 靜音語意 | `SUPPRESS_NOTIFICATIONS`（完全不推播、只留 badge） | `disable_notification`（有通知但無聲） | 抽象成同一個布林值，換管道時會**默默改變行為** |
| 內文長度上限 | 2000 | 4096 | |
| 結構化色彩 | embed 有 `color`，紅漲綠跌可直接做 | 只能靠 emoji | |

### 需要人工驗收的一步

「新建 Discord server 的預設通知等級」**官方文件從未明文**（網傳說法不予採信）。因此 setup 步驟必須包含「**手動確認通知設定並實際送一則測試訊息**」這道人工驗收，不能假設預設值是對的。

---

## 7. 送達時限

| 路徑 | 需求 | 實際 |
|---|---|---|
| 盤中 | **≤30 分鐘**（硬上界） | 秒級（worker 逐筆評估後直接 POST） |
| 盤後總結 | 14:00 前 | 排程可控 |

30 分鐘是硬上界不是偏好 —— 使用者原話：「我們 9:47 發現警訊 可以在 30 分鐘內提醒嗎? 不然他確實有一點來不及」。

**這推翻了本票簡報曾主張的框架**：`docs/briefing/15-alerts.md` 待決 8 選項 D 曾說「一則『你的停損在 09:47 觸發了』的通知在 11:00 送達仍然有價值」，使用者當場否定。

因此 **v1 不做 outbox**。盤中路徑由 `quote-worker` 評估後直接送出，餘裕極大（30 分鐘的預算對上秒級的實際）。

---

## 8. 靜音時段：不需要

盤中警示結構上只在 **09:00–13:35** 產生（`quote-worker` 的開機窗口，見 [`realtime-quotes.md`](./realtime-quotes.md) §7），不可能落在深夜。盤後總結的送出時間由排程決定，本身就在合理時段。

**故 v1 不實作靜音時段。** 原簡報的待決 6 由 8/4 的「警示只在盤中做」實質消解。

---

## 9. 儀表板：規則面板

### 決定

第一層右欄的警示面板，開頁預設顯示**規則清單與其狀態**，非事件列表。

```
警示                              ● 即時
─────────────────────────────────────────
2330 台積電   跌破 590      現價 2310   武裝中
2330 台積電   追蹤停損 10%  距觸發 2.1%  武裝中
0050 元大台灣50 漲跌幅 +5%   現價 —      已觸發 09:47・等回歸
```

- 5–10 條規則 → **平鋪，不摺疊、不捲動、不分頁**
- 「今天響了什麼」走**側欄的通知列表**，不佔第一層右欄
- 顏色只用於價格方向，其餘一律墨色（`dashboard-ui.md` §2）

### 為什麼不是事件列表

一整天沒觸發時事件列表是空的，而它佔著第一層右欄最貴的位置。更重要的是：**回歸重置引入了一個使用者看不見就會誤判的狀態** —— 你以為 590 那條還守著，其實它上午觸發過、現在正等價格回上去。規則清單是唯一能把這個狀態外顯的形式。

### ⚠️ 硬性規則：`quote-worker` 未開機時面板必須顯示「未運作」

警示與即時報價綁在同一個開關上。worker 未開機時，面板頂端的狀態指示**必須明確顯示警示未運作**，且所有盤中規則不得顯示為「武裝中」。

> 「以為有人幫你看盤、其實沒有」比「知道自己沒有警示」危險得多，因為使用者會**依賴它而不自己看**。這是 [`realtime-quotes.md`](./realtime-quotes.md) §5「前提破了就明確停下來告訴人」與 [`dashboard-ui.md`](./dashboard-ui.md) §3「永遠亮著等於沒有」兩條既有原則的交集。

盤後規則（成交量異常、除權息提醒）不受影響，應與盤中規則在視覺上分區，否則使用者無從判斷哪些還活著。

---

## 10. 暫時性妥協與解除條件

沿用 [`realtime-quotes.md`](./realtime-quotes.md) 的形式 —— 以下限制**來自免費層或外部服務的當前狀態，不是技術判斷**：

| # | 妥協 | 成因 | 解除條件 |
|---|---|---|---|
| A-1 | 只訂 `trades`，畫面無最佳五檔即時推播 | Fugle 免費層 5 個 (標的×頻道) 配對，5 檔持股只夠一個頻道 | 轉 Shioaji（[#8](https://github.com/NTUyu016/stock-analytic-platform/issues/8)）後額度單位變成「檔」，`trades` 與 `books` 可同時訂 |
| A-2 | 需要五檔時走 REST `/intraday/quote/{symbol}` 輪詢，5 秒粒度 | 同上。免費層 60 次/分鐘 ÷ 5 檔 = 每 5 秒一輪 | 同 A-1 |
| A-3 | 成交量異常為自訂規則，無法對齊官方口徑 | 官方標準需全市場約 1,377 檔的六十日均量 | 取得全市場歷史量的合法來源；或 TWSE `announcement/notice` 端點恢復正常後改訂閱官方判定結果 |
| A-4 | 上市標的無法訂閱官方注意股判定 | TWSE `announcement/notice` 回傳單一全空佔位列 | TWSE 端點恢復正常 |
| A-5 | 財報日提醒不做 | yfinance `earnings_dates` 為預估日、會漂移 | 找到公告日的一手來源 |
| A-6 | Fugle `trades.volume` 單位未經證實 | 官方文件未載明 | 取得 API key 後實測，並寫進契約測試 |

### ⚠️ 一道未關的法遵問題：FinMind 進入必要路徑

本票讓 **FinMind 成為三樣東西的唯一乾淨來源**：`TRAILING_STOP` 的峰值回補、`VOLUME_SPIKE` 的量歷史、除權息參考價。加上 `daily_close` 本來就是歷史資產曲線的必要資料 —— **一個外部服務進入了必要路徑**。

而 [`tw-volume-anomaly-and-history.md`](../research/tw-volume-anomaly-and-history.md) §B.5 記著一道還開著的題：**FinMind 的資料再散布授權未明示**（套件本身是 Apache-2.0，資料不是）。

| 情境 | 狀態 |
|---|---|
| 自用抓取 | ✅ 沒問題 |
| 對外提供服務／散布資料 | ⚠️ **未能查證，需人工確認** |

本 repo 為 public，且「上架給他人使用」還在地圖的 **Not yet specified** 裡。**這道題會在那一天擋在路上**，屆時須連同 [#2](https://github.com/NTUyu016/stock-analytic-platform/issues/2) 的「券商行情不得轉供第三人」一併處理。

**對 v1 的具體要求**：

- `tech-stack.md` §7 的契約測試須涵蓋 FinMind 的 `Trading_Volume` / `max` / `min`（只驗證欄位還在、型別沒變、值不是 `None`）
- 回補完成後做一次**全序列離群掃描**（例如標記 > 60 日均量 50 倍者）並人工過目 —— FinMind 2330 於 2005-12-28 有 19.5 億股這種可疑列，且官方歷史在爬蟲禁止條款內、無法驗證
- 每日用 TWSE／TPEx 快照對帳 FinMind，**允許延後一天**（§5.4）

---

## 11. 對其他票的影響

| 票 | 影響 |
|---|---|
| [#16 歷史快照與績效計算](https://github.com/NTUyu016/stock-analytic-platform/issues/16) | **`daily_close` 的下界被本票釘死**：必須有 `open`/`high`/`low`/`close`/`volume`，且**回補到每檔的建倉日**（非固定年數）。#16 仍可自由決定是否加快取層，但不能把粒度定得比這更粗 |
| [#14 個股分析頁的台股指標集合](https://github.com/NTUyu016/stock-analytic-platform/issues/14) | ① Q1 選 `trades` → 分析頁**無即時五檔推播**，需要時走 REST 輪詢（A-2）<br>② `daily_close` 已有 OHLCV → 量能比（5 日/60 日）的資料基礎由本票備妥，且已確認**必須走 FinMind 不可走 yfinance** |
| [#17 部署、環境與成本上限](https://github.com/NTUyu016/stock-analytic-platform/issues/17) | ① 盤後排程新增三件事（除權息預告、除權息參考價、峰值調整），仍與 `daily_close` 同班車，不新增部署單元<br>② 每日增量改走 FinMind 17:30，排程時間不得早於此 |
| [`data-model.md`](./data-model.md) | `alert` 改具名欄位、新增 `alert_state`、`notification` 補四欄、`daily_close` 擴充四欄 |
| [`CONTEXT.md`](../../CONTEXT.md) | **Daily Close** 詞條需放寬為日 OHLCV；新增 **Armed（武裝）**、**Peak（峰值）** 兩個詞條 |
| [`realtime-quotes.md`](./realtime-quotes.md) | §6 需註明 conflation 之前有一條警示評估分支；「暫時性妥協」表新增 A-1／A-2 |
