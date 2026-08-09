# 資料表綱要 v1

決策來源：[issue #9](https://github.com/NTUyu016/stock-analytic-platform/issues/9)。名詞定義見 [`CONTEXT.md`](../../CONTEXT.md)。

資料庫：**PostgreSQL**。

## 核心原則

1. **Transaction 是唯一事實來源**。Position、Cost Basis、已實現損益、歷史資產曲線全部由它推導，不儲存。
2. **金額一律存原幣別**，每張表帶 `currency`；換算成台幣只發生在顯示層。
3. **即時報價不落地**；每日收盤價與每日匯率落地。
4. **參考資料與個人資料分離**：`instrument`、`daily_close`、`exchange_rate` 全域共用不帶 `user_id`；`portfolio`、`transaction`、`alert` 帶 `user_id`。
5. **所有涉及使用者資料的查詢，從第一天就帶 `WHERE user_id = ?`**。v1 只有一列使用者，此條件恆為真、是無害的冗餘；多人化時它是唯一的防線，且**漏掉不會有任何錯誤訊息**（[#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10)）。

## 表

### `app_user`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `email` | `text` | **聯絡用主 email，不是登入識別**。可為空 |
| `display_name` | `text` | |
| `created_at` | `timestamptz` | |

- v1 只會有一列，由 CLI 指令建立（見 [`auth.md`](./auth.md) §8）。
- **`email` 的 UNIQUE 約束已於 [#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) 移除** —— 登入識別移到 `user_identity`，本欄降為聯絡欄位。

### `user_identity`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK → `app_user` | **一個人可以有多列** |
| `provider` | `text` | `google` / `github` |
| `subject` | `text` | provider 給的**穩定識別碼** |
| `email` | `text` | 該身分當下的 email。**僅供顯示與人工比對，不參與任何判斷** |
| `created_at` | `timestamptz` | |
| `last_used_at` | `timestamptz` | |

- UNIQUE `(provider, subject)`
- 各 provider 的 `subject` 來源：`google` 取 ID token 的 `sub`；`github` 取 `GET /user` 回應的數字 `id`（**不可用 `login`，它可以改**）。
- **這張表是 [#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) 對本文件的修訂**。原設計 `app_user.email` UNIQUE 隱含「一個人 = 一個 email = 一種登入方式」，使得「換一個 provider 登入」等於改寫自己的身分列 —— 而那正是被鎖在門外時做不到的事。拆表後備援登入才成立。
- ⚠️ **key 絕不可用 email**。Google 官方明載 email 可變、且 Workspace 帳號刪除後同一 email 可再發給新的人，那個人會繼承存取權。詳見 [`auth.md`](./auth.md) §6。
- 它同時是「日後開放註冊」的預留：多人化時本表**一行都不用改**，只是列數變多。

### `session`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `text` PK | 隨機字串本身，非序號 |
| `user_id` | `bigint` FK | |
| `created_at` | `timestamptz` | |
| `expires_at` | `timestamptz` | 30 天滑動續期 |
| `last_seen_at` | `timestamptz` | |

- INDEX `(expires_at)` — 清理過期列
- **必須落地，不可存行程記憶體** —— `api` 走 scale-to-zero（[#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17)），停機重啟會把記憶體裡的 session 全部丟掉。理由不是「多機器共享」，是停機。
- 落地的另一個好處是**可撤銷**：刪一列即登出，這正是不用 JWT 的主因。詳見 [`auth.md`](./auth.md) §5。

### `instrument`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | 內部代理主鍵，與任何外部系統無關 |
| `market` | `text` | `TWSE` / `TPEX` / `US` / `CRYPTO` |
| `symbol` | `text` | `2330`、`NVDA`、`BTC-USD` |
| `name` | `text` | 台積電 |
| `currency` | `char(3)` | 該標的的報價幣別 |
| `instrument_type` | `text` | `STOCK` / `ETF` / `CRYPTO`。⚠️ **不得由反查自動決定**——它決定證交稅是 0.3% 還是 0.1%，見 [`transaction-input.md`](./transaction-input.md) §5 |
| `industry_code` | `text` NULL | 官方產業別代號（[#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) 補）。⚠️ **代號語意隨 `market` 而異，必須連 `market` 一起解讀**。ETF、美股、crypto 恆為 NULL |
| `is_active` | `boolean` | 下市/下架後設 false，不刪除（歷史交易仍需引用） |

- UNIQUE `(market, symbol)`
- FK `(market, industry_code)` → `industry_category(market, industry_code)`。**NULL 不受 FK 約束**——這正是 ETF 需要的行為，不必額外開洞。
- 台積電台股與其 ADR 是兩列。
- ⚠️ **`industry_code` 不可用 yfinance 的 `info["sector"]` 填。** 那是 GICS 英文分類（實測 `2330.TW → Technology / Semiconductors`），與證交所產業別不是一對一，**沒有任何一檔 MI_INDEX 類指數對應得上**。填錯的表現是「產業比較這一維永遠不可用」或「對到錯的指數」，兩種都不報錯。詳見 [`analysis-dimensions.md`](./analysis-dimensions.md) §15.1。

### `instrument_provider_symbol`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `instrument_id` | `bigint` FK | |
| `provider` | `text` | `yfinance` / `shioaji` / `fugle` / `twse_openapi` / `cathay_statement` |
| `provider_symbol` | `text` | `2330.TW` / `2330` / `台積電` |

- PK `(instrument_id, provider)`；UNIQUE `(provider, provider_symbol)`
- **這張表是換資料源不用搬資料庫的關鍵**。行情源尚未定案（[#2](https://github.com/NTUyu016/stock-analytic-platform/issues/2) / [#8](https://github.com/NTUyu016/stock-analytic-platform/issues/8)），此設計讓該決策不污染核心模型。
- **[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 擴充了它的用途**：券商對帳單只給中文簡稱、不給代號，因此把券商也當成一個 `provider`（`cathay_statement`），簡稱當成它的 `provider_symbol`。`UNIQUE (provider, provider_symbol)` 正好給出「一個券商簡稱只能對到一支標的」的保證。本表當初為「換行情源」而設計，未預料到此用途卻剛好接得住。
- ⚠️ **查詢順序必須是「先查本表，未命中才打官方 API」**，不可反過來。API 回的是今日快照會隨改名漂移，本表是凍結的歷史事實。詳見 [`transaction-input.md`](./transaction-input.md) §5。

### `portfolio`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK | |
| `name` | `text` | 「長期存股」 |
| `sort_order` | `int` | 首頁排序 |

- UNIQUE `(user_id, name)`
- 首頁預設跨 portfolio 加總；同一 Instrument 在不同 portfolio 各自獨立計算成本。

### `transaction`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK | 冗餘欄位，供查詢時免 join portfolio |
| `portfolio_id` | `bigint` FK | |
| `instrument_id` | `bigint` FK | |
| `type` | `text` | `BUY` / `SELL` / `CASH_DIVIDEND` / `STOCK_DIVIDEND` / **`SPLIT`** / `ADJUSTMENT`。**必須有 `CHECK` 列舉約束**（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20)） |
| `traded_on` | `date` | 成交日 |
| `quantity` | `numeric(20,8)` | 股數。`numeric` 而非整數：零股、加密貨幣、股票股利配發都會有小數 |
| `price` | `numeric(20,8)` | 每股價格，原幣別 |
| `fee` | `numeric(20,4)` | 手續費 |
| `tax` | `numeric(20,4)` | 證交稅 |
| `cash_amount` | `numeric(20,4)` | 現金股利總額（`CASH_DIVIDEND` 用） |
| `currency` | `char(3)` | 冗餘自 instrument，凍結交易當下的幣別 |
| `ratio` | `numeric(20,8)` | **分割比率**（`SPLIT` 專用）。`新股數 = 舊股數 × ratio`；1 拆 4 為 `4`、4 合 1 為 `0.25`（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20)） |
| `note` | `text` | `ADJUSTMENT` 必填原因 |
| `external_ref` | `text` | 匯入來源的自然鍵。可為空（手動輸入） |
| `created_at` | `timestamptz` | |

- INDEX `(portfolio_id, instrument_id, traded_on)` — 推導 Position 的主要查詢路徑
- INDEX `(user_id, traded_on)` — 歷史資產曲線
- UNIQUE `(user_id, external_ref)` WHERE `external_ref IS NOT NULL` — **匯入的冪等性靠它**（[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19)）
- `external_ref` 的內容是 `(券商, 成交日, 委託書號)` 的組合。**鍵裡必須有成交日** —— 委託書號在單日內唯一是確定的，跨日全域唯一則是未證實的假設（台股委託書號傳統上 5 碼且逐日回收）。加日期成本為零，賭錯的代價是靜默吃掉一筆真交易。詳見 [`transaction-input.md`](./transaction-input.md) §6。
- 各類型的欄位語意：
  - `BUY` / `SELL`：`quantity` + `price` + `fee` + `tax`（此處 `tax` 為證交稅）
  - `CASH_DIVIDEND`：`cash_amount`（宣告**總額**）+ `tax`（配息當下扣掉的**補充保費／就源扣繳**）。不改股數，**不改成本基礎**。實收淨額 = `cash_amount` − `tax`
  - `STOCK_DIVIDEND`：只有 `quantity`，總成本不變 → 均價被稀釋
  - `SPLIT`：**只有 `ratio`，`quantity` 必須是 NULL**。無現金流、總成本基礎不變。涵蓋分割／反分割／面額變更三種公告類型（三者共用同一條 TWSE 公式），**不涵蓋減資**
  - `ADJUSTMENT`：`quantity` 與 `cash_amount` 可正可負，`note` 必填。減資、換股、合併走這裡

> **[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 新增的硬性約束**：
> ```sql
> CHECK ((type = 'SPLIT') = (ratio IS NOT NULL))
> CHECK (ratio IS NULL OR ratio > 0)
> CHECK (type <> 'SPLIT' OR quantity IS NULL)
> ```
> 第一條**必須是雙向等式，不可寫成 `CHECK (type <> 'SPLIT' OR ratio IS NOT NULL)`。** 單向版本允許非 `SPLIT` 的列填入 `ratio`，而那正是 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 已識別過的形狀——**`CHECK` 對不該有值的欄位放行，不報錯**。
>
> 第三條是 2026-08-09 冷讀驗收（#18）撞出來的：**`SPLIT` 不得存股數增減量**。存 delta 等於把分割變成一個快照，而補登一筆分割日之前的舊交易時那個 delta 永遠不會被修正——`performance.md` §8.5「重算保證補登後歷史自動正確」在此處**靜默失效**。部位推導改為**比率縮放的不等式聚合**，詳見 [`corporate-actions.md`](./corporate-actions.md) §1.5。
>
> ⚠️ **`CHECK` 擋不住真正的風險**：它保證沒有非法的 type 值，但擋不住「某段程式碼只枚舉了 `BUY`/`SELL`，忘了 `SPLIT`」。因此規定**所有依 `type` 分支的程式碼必須是窮舉式的**（`match` + `case _: raise`），不得有靜默的 fall-through。

> **[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 修訂**：`CASH_DIVIDEND` 原記「**降低成本基礎**」，改為**不改成本基礎**、獨立累計為 Dividend Income。
> 決定性理由不是「跟券商對得上」（那只是好處），而是**沖減成本會靜默翻轉報酬率的正負號** —— 長期持有高殖利率標的時累計股利可超過原始成本，使成本基礎降到零以下，而報酬率 `(市值 − 成本)/成本` 的分母一旦為負，正負號整個翻過來且不報錯。詳見 [`performance.md`](./performance.md) §3。
> ⚠️ **`tax` 欄在不同 `type` 下語意不同**（證交稅／補充保費），這沿用本表 `quantity`、`cash_amount` 既有的分型別語意做法，但必須寫進欄位註解，否則日後會有人問「為什麼股利有證交稅」。

> 費用與稅的實際計算規則待 [issue #6](https://github.com/NTUyu016/stock-analytic-platform/issues/6) 的研究結論；本表只保證欄位存在。

### `daily_close`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `instrument_id` | `bigint` FK | |
| `trade_date` | `date` | |
| `open` | `numeric(20,8)` | |
| `high` | `numeric(20,8)` | 追蹤停損的峰值回補（[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)） |
| `low` | `numeric(20,8)` | |
| `close` | `numeric(20,8)` | |
| `prev_close` | `numeric(20,8)` | 算當日漲跌幅用，避免回查前一交易日 |
| `volume` | `bigint` | **單位：股**。成交量異常與量能比用（[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)、[#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)） |
| `source` | `text` | 資料來源，供日後校正 |

- PK `(instrument_id, trade_date)`
- 新增標的時回補歷史，之後每日盤後排程追一筆。
- 量級：10 支標的 × 10 年 ≈ 2.5 萬列。

> **[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 修訂**：表名維持 `daily_close`，但它現在裝的是**日 OHLCV**。
> - **回補範圍**：每檔回補到**該檔最早的建倉日**，非固定年數 —— 追蹤停損的直接要求。
> - **停止買賣日不補列、不寫 `volume = 0`**（減資期間 FinMind 直接沒有那些列；補成 0 會壓低均量約 12%，復牌後產生假爆量）。連帶：「六十日均量」一律指**最近 60 筆列**，不是 60 個日曆交易日。
> - **不可走 yfinance**：台股成交量實測 22.3% 的交易日誤差 ≥100 倍。唯一乾淨來源是 FinMind `TaiwanStockPrice`，詳見 [`alerts.md`](./alerts.md) §2.4。

### `exchange_rate`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `currency` | `char(3)` | 對 TWD |
| `rate_date` | `date` | |
| `cash_buy` | `numeric(20,8)` | 現金買入（原始牌價） |
| `cash_sell` | `numeric(20,8)` | 現金賣出（原始牌價） |
| `spot_buy` | `numeric(20,8)` | 即期買入（原始牌價） |
| `spot_sell` | `numeric(20,8)` | 即期賣出（原始牌價） |
| `rate` | `numeric(20,8)` **GENERATED** | `(spot_buy + spot_sell) / 2` STORED。1 單位外幣 = ? TWD |
| `source` | `text` | |

- PK `(currency, rate_date)`
- **`CHECK (spot_buy > 0 AND spot_sell > 0)`**
- 歷史績效一律取當日匯率；查無當日（假日）時取前一個有值的日期。**這是查詢端的責任 —— 絕不可在寫入時補列**（補了就無法區分「有掛牌且與昨天同價」與「沒開門」）。

> **[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 修訂**：原本只有單一 `rate` 欄，未定義口徑。
> - **口徑定為即期中價**。用途是**評價**不是換匯，買賣價差是交易成本不該計入；取單邊價的偏誤施加在**每一個評價日**上不會抵銷。取「即期」不取「現金」是因為現金牌價含鈔券運送保管成本（實測價差為即期的 **6.7 倍**）。**誤取現金買入 = 對每個歷史評價日打 98.76 折。**
> - **保留四個原始牌價、`rate` 改為 generated column**：`rate` 是推導值，只存它就無法事後換口徑或驗證。表僅五千列量級，欄位成本可忽略。
> - **`CHECK` 是必要的不是防禦性冗餘**：FinMind `TaiwanExchangeRate` 用 **`-1.0` 當缺值哨兵**（實測 22 列），且**分欄出現**（2010-12-30 是 `cash` 為 −1、2006-01-02 與 2012-01-02 是 `spot` 為 −1）。負匯率會讓外幣部位市值翻負且不報錯。`CHECK` 下在原始欄位上，在哨兵進表那一刻擋掉。
> - 來源：FinMind `TaiwanExchangeRate`，實測即台銀牌告，一次請求取回 2006-01-02 起 5,122 列。詳見 [`performance.md`](./performance.md) §2.3 與 [`../research/tw-benchmark-and-fx-sources.md`](../research/tw-benchmark-and-fx-sources.md) §C。

### `benchmark_series`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `benchmark_code` | `text` | `TAIEX_TR` = 發行量加權股價**報酬**指數（含息） |
| `trade_date` | `date` | |
| `index_value` | `numeric(20,8)` | |
| `source` | `text` | |

- PK `(benchmark_code, trade_date)`
- **[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 新增。** 它同時是**台股交易日曆**的來源（[`performance.md`](./performance.md) §2.2 規定日曆不可從自己持有的標的推導 —— 停止買賣期間 `daily_close` 沒有列，若持股集中在該檔，那幾天會整個從日曆消失且圖看起來完全正常）。
- ⚠️ **不把指數塞進 `daily_close`。** 那樣做的話，**所有掃 `daily_close` 算持股市值的查詢從此都必須記得排除指數列** —— 與 [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 拒絕 `transaction.status`、[#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) 對 `user_id` 的警告是同一個形狀。另立表讓 `daily_close` 維持不變量：**裡面每一列都是一支可持有標的的價格。**
- 主來源為 TWSE `www.twse.com.tw/indicesReport/MFI94U?response=open_data`（**政府資料開放授權條款－第 1 版**），FinMind `TaiwanStockTotalReturnIndex` 為備援（實測 5,807 列**逐列完全相同**）。回溯上限 2003-01-02。

### `industry_category`

參考資料，全域共用，**不帶 `user_id`**（核心原則 4）。[#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) 新增。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `market` | `text` | `TWSE` / `TPEX` |
| `industry_code` | `text` | 兩位代號，如 `24` |
| `industry_name` | `text` | 官方產業別名稱，如「半導體業」 |
| `industry_index_name` | `text` NULL | 對應的 MI_INDEX 類指數名稱。**NULL = 該產業別沒有對應的類指數** |

- PK `(market, industry_code)`
- **種子資料**：上市 33 列、上櫃 28 列（上櫃的 `industry_index_name` **全部為 NULL**）。完整對照見 [`analysis-dimensions.md`](./analysis-dimensions.md) §13.2。
- **這是人工確認過的種子資料，不是每日同步的鏡像**——「代號 → 名稱」沒有官方對照端點，「名稱 → 類指數」更是純人工比對（不是字串規則：「化學工業→化學類指數」要去掉「工業」，「紡織纖維→紡織纖維類指數」直接加）。
- ⚠️ **`industry_index_name` 是字串比對的鍵**，MI_INDEX 只給名稱沒有代號。**指數改名會讓對照默默失效**，而失效的表現是「這一維不可用」——看起來像資料還沒累積夠，不像設定壞了。**因此盤後排程必須斷言：每一個非 NULL 的 `industry_index_name` 都能在當日 `market_index_daily` 找到一列。**

### `market_index_daily`

參考資料，全域共用，不帶 `user_id`。[#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) 新增，來源 TWSE OpenAPI `MI_INDEX`。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `index_name` | `text` | 指數名稱，**原樣存 TWSE 的中文字串** |
| `trade_date` | `date` | 由 MI_INDEX 的民國日期轉西元 |
| `close_index` | `numeric(20,8)` | 收盤指數 |
| `change_point` | `numeric(20,8)` | **帶正負號**的漲跌點數。⚠️ 見下 |
| `change_pct` | `numeric(10,4)` | 漲跌百分比（來源已帶正負號） |
| `special_note` | `text` | 特殊處理註記，原樣保留 |
| `source` | `text` | `twse_openapi_MI_INDEX` |

- PK `(index_name, trade_date)`；INDEX `(trade_date)`
- **存全部 267 列，不是只存 37 檔類指數**：MI_INDEX **只給最新一日**，今天沒存的明天永遠補不回來（歷史端點在禁爬側）。這與 `daily_close` 根本不同——後者的缺列可以用 FinMind 回補，**本表不行**。6.5 萬列/年可忽略，而「當初沒存」是不可逆的。
- ⚠️ **最容易靜默出錯的一點：來源的 `漲跌點數` 是無正負號的絕對值，正負號在另一個欄位 `漲跌`（`"+"` / `"-"`），而 `漲跌百分比` 自己帶號**——同一列裡兩種慣例。直接存 `漲跌點數` 會讓**所有下跌日變成上漲日**，而因為 `close_index` 是對的，**指數走勢圖上完全看不出來**。寫入時必須換算並斷言 `sign(change_point) == sign(change_pct)`。
- ⚠️ **本表的排程比其他排程多一條規則**：其他排程的語意是「回補到最新交易日」，**但本端點只給最新一日，回補做不到**。漏跑一天就是永久缺一天，而它的表現是「產業比較不可用」——**看起來像還在累積，不像漏跑**。因此排程必須比對本表與 `benchmark_series` 的最新交易日，**中間有斷點就明確告警**，畫面上也要把「還在累積」與「中間漏了 N 天」分成兩句不同的話。
- **為什麼不塞進 `benchmark_series`**：那張表被 [`performance.md`](./performance.md) §2.2 當作**台股交易日曆**的來源，混進幾百檔指數後，任何忘記寫 `WHERE benchmark_code = 'TAIEX_TR'` 的查詢**仍會回傳一組合法的日期**——漏寫不報錯。且兩者覆蓋範圍不同（`benchmark_series` 有 2003 起的歷史，本表從部署當天才開始長），混在一起的跨年度查詢會**部分有值、部分沒有，而且看起來完全正常**。
- **為什麼不塞進 `daily_close`**：它的不變量是「每一列都是一支**可持有標的**的價格」，指數不可持有。這與本文為 `benchmark_series` 拒絕過的是同一個理由。

### `alert`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK NOT NULL | |
| `instrument_id` | `bigint` FK NOT NULL | |
| `portfolio_id` | `bigint` FK NULL | **依部位的規則（成本報酬率、追蹤停損）必須有值；純價格規則必須為 NULL**。`CHECK` 依 `rule_type` 雙向約束（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 補） |
| `rule_type` | `text` NOT NULL | 六種具名**類別**、展開為九個列舉值，`CHECK` 列舉（見 [`alerts.md`](./alerts.md) §1 的完整清單） |
| `threshold` | `numeric(20,8)` NOT NULL | 語意隨 `rule_type` 而異 |
| `is_enabled` | `boolean` NOT NULL DEFAULT true | |
| `is_deleted` | `boolean` NOT NULL DEFAULT false | 軟刪除，沿用 `instrument.is_active` 先例 |
| `created_at` | `timestamptz` NOT NULL | |

> **[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 修訂**：原 `condition jsonb` 佔位欄位由 `rule_type` + `threshold` 取代。
> 決定性理由不是 `jsonb` 掉精度（那經查證是錯的，官方存成 `numeric`），而是 **`CHECK` 約束對 NULL 放行** —— 用 `CHECK` 保護 `jsonb` 這件事本身就是一個漏寫不報錯的活動。詳見 [`alerts.md`](./alerts.md) §2.1。

### `alert_state`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `alert_id` | `bigint` PK FK | 1:1 |
| `is_armed` | `boolean` NOT NULL DEFAULT true | 武裝中 / 已觸發等回歸 |
| `last_triggered_at` | `timestamptz` NULL | |
| `peak_price` | `numeric(20,8)` NULL | 僅 `TRAILING_STOP` |
| `peak_since` | `date` NULL | 僅 `TRAILING_STOP`，峰值起算日（建倉日） |
| `suspended_reason` | `text` NULL | **系統暫停評估的原因**；NULL = 未暫停（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 新增） |
| `updated_at` | `timestamptz` NOT NULL | |

> **`suspended_reason` 為什麼不是去改 `alert.is_enabled`**：`CONTEXT.md` 明訂「**使用者設的是 `is_enabled`**」，系統去覆寫它等於抹掉使用者的意圖，而且使用者重新建倉後不會自動恢復。放在 `alert_state` 還有第二個理由——這張表的定位就是「**全部可以重算**」，而暫停與否本來就是從 `transaction` + `pending_action` 推導出來的，不是持久事實。
>
> 兩個已知的填值來源：**股數歸零時的類型 3／4**（[`alerts.md`](./alerts.md) §1）與**未確認且會改變股數的 `pending_action`**（[`corporate-actions.md`](./corporate-actions.md) §2.4）。兩者都必須在規則面板上顯示這個字串——[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 的原則是「用行為表達嚴重度」，而沒被看見的行為等於沒有發生。

> **[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 新增。** 與 `alert` 分表的理由是**可重建性不同**：`alert` 是使用者打的字，毀了就沒了；`alert_state` 全部可以從 `transaction` + `daily_close` + 當前 Quote 重算。分表後「狀態疑似錯亂」的修復是一次安全的整表重建，而非在使用者資料上動刀。

### `notification`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK NOT NULL | **新增**，核心原則 5 |
| `alert_id` | `bigint` FK NULL | 盤後總結不對應單一 alert，故可空 |
| `triggered_at` | `timestamptz` NOT NULL | |
| `channel` | `text` NOT NULL | 送達管道 |
| `payload` | `jsonb` NOT NULL | 站內呈現用，**可含金額**（Discord 通知不可） |
| `status` | `text` NOT NULL | `PENDING` / `SENT` / `FAILED` / `ABANDONED` |
| `attempts` | `smallint` NOT NULL DEFAULT 0 | |
| `delivered_at` | `timestamptz` NULL | |
| `last_error` | `text` NULL | **落地前必須遮蔽 webhook URL** |

> 管道選型見 [issue #7](https://github.com/NTUyu016/stock-analytic-platform/issues/7) 的研究結論，v1 定為 **Discord**（[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)）。
> 投遞狀態欄位與 [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 拒絕 `transaction.status` **不衝突**：`transaction` 是事實來源，加 `status` 會讓所有既有查詢必須記得過濾；`notification` 記的就是一次投遞嘗試，狀態是它的本質屬性。
> **不設保留期限** —— 5–10 條規則一年也就幾百列。

### `pending_action`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK | |
| `kind` | `text` | `CORPORATE_ACTION` / `IMPORT_CONFLICT` |
| `instrument_id` | `bigint` FK | 可為空 |
| `portfolio_id` | `bigint` FK | **`CORPORATE_ACTION` 必填**（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 補）。`transaction.portfolio_id` 是 NOT NULL，沒有這一欄就無法決定確認後要寫進哪一個 Portfolio |
| `resolved_at` | `timestamptz` NULL | 已處理時間；NULL = 待處理（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 補） |
| `notified_count` | `int` NOT NULL DEFAULT 0 | 已通知次數（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 補） |
| `last_notified_at` | `timestamptz` NULL | 同上 |
| `effective_on` | `date` | **該事件生效、市場開始以新股數與新價格交易的第一個交易日**（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 改寫；原記「除權息基準日」） |
| `proposed` | `jsonb` | 系統算出的預填值。**減資場合刻意不含比率**——官方資料源分離不出換股率 |
| `source` | `text` | 產生來源，如 `twse_TWT48U_ALL`、`finmind_TaiwanStockSplitPrice`。⚠️ **兩者的授權性質不對等**：除權息走政府資料開放授權的官方端點，分割與減資**只有 FinMind 這條路**（[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20)） |
| `created_at` | `timestamptz` | |

- 待使用者確認的項目。**確認後才 INSERT 進 `transaction`；本表列標記 `resolved_at`，不刪除。**

> **[#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) 把「刪除或標記」這個二選一選掉了：選標記。** 兩個理由：（a）[`corporate-actions.md`](./corporate-actions.md) §4.7 要求「超過 5 個交易日仍未確認再通知一次」，那需要記住已通知幾次，刪除的列記不住；（b）保留「系統偵測到什麼、使用者怎麼處理」的稽核軌跡。
>
> **這不違反「不在 `transaction` 加 `status`」的原則**——那條原則的理由是「漏寫 `WHERE status` **不報錯**」。這裡漏寫 `WHERE resolved_at IS NULL` 的後果是**畫面上多出已處理的項目**，看得見、會被抱怨，不是靜默失效。**判準從來不是「有沒有狀態欄」，是「漏寫的時候看不看得出來」。**

- **一次公司行動可能產生多列**：同一支 Instrument 在兩個 Portfolio 各有部位時，**逐 Portfolio 各產生一列**，各自算各自的股數，[`corporate-actions.md`](./corporate-actions.md) §1.4(d)「新股數必須是整數」也**逐 Portfolio 判定**（合計判定會讓兩個各 500 股的 Portfolio 在 `ratio=1.5` 時通過，而它們各自都算不出整數）。
- ⚠️ **這張表存在的唯一理由，是不要在 `transaction` 加 `status` 欄。** 加 `status` 會讓每個查詢都必須記得寫 `WHERE status = 'confirmed'`，而**漏寫不會有任何錯誤訊息** —— 只會讓未確認的股利偷偷混進損益與成本基礎。這與本文核心原則第 5 條、以及 [#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) 對 `user_id` 的警告是同一個形狀。
- 另立表則讓 `transaction` 維持「**裡面每一列都是事實**」的不變量，**現有查詢一行都不用改**。
- 決策來源：[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19)，詳見 [`transaction-input.md`](./transaction-input.md) §8。

### `reconciliation`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK | |
| `reconciled_at` | `timestamptz` | |
| `as_of_date` | `date` | 對帳基準日 |
| `is_balanced` | `boolean` | 平／不平 |
| `differences` | `jsonb` | 差異明細（標的、推導股數、券商股數） |

- 使用者貼上券商庫存股數後，系統與推導出的 Position 比對，把**結果**存為一筆稽核紀錄。
- **只比股數，不比均價。** 股數是整數且無歧義；均價有定義分歧（[#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6) §4.2、§5.2 的股利雙軌問題），拿它對帳會產生永遠對不平的雜訊，而永遠亮著的警告等同沒有警告。
- ⚠️ **不存庫存本身** —— 那等於偷偷建了下方明令不做的 `position` 表。本表存的是「一個已發生的比對事件」，不是可推導狀態的快照，故不違反核心原則第 1 條。
- 決策來源：[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19)，詳見 [`transaction-input.md`](./transaction-input.md) §9。

## 刻意不做的表

| 沒有這張表 | 原因 |
|---|---|
| `position` | Position 是推導值。存了就會與 Transaction 不一致，且改一筆舊交易後歷史就錯了。 |
| `lot`（批次） | 成本基礎採加權平均，不需追蹤個別批次。日後要改 FIFO 時，從 Transaction 重建即可，不需要現在就存。 |
| `quote`（即時報價） | 具時效性，落地無價值且量大。活在記憶體與快取中。 |
| `portfolio_snapshot` | 歷史資產曲線由 Transaction + `daily_close` + `exchange_rate` 重算。存快照就無法在修正舊交易後自動修正歷史。**[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 已評估完畢：v1 確定不加，連快取形式都不加。** 兩個理由——（1）拖曳選取區間操作的是瀏覽器裡已載入的序列，**不打後端**，`dashboard-ui.md` §7 對 60fps 的顧慮不成立；（2）資料量本來就小。解除條件見 [`performance.md`](./performance.md) §1.4。 |

## 綱要層級的通用規則（[#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 於 2026-08-09 補）

> 冷讀驗收指出：上面的表只給了欄位與型別，**沒有 nullability、沒有 FK 的 `ON DELETE`、沒有分型別的欄位約束**，而 [`implementation-plan.md`](./implementation-plan.md) 票 0.4 要求「所有 `CHECK` 都要寫」。以下把散在各表的通用規則集中成可直接照做的形式。

### N1. Nullability 的預設

**除非上表的說明欄明寫「可為空」／`NULL`，否則一律 `NOT NULL`。** 這個方向是刻意的：`NOT NULL` 寫錯會在第一次 `INSERT` 就爆，而漏寫 `NOT NULL` 的後果是半年後某個 `SUM()` 靜靜跳過那一列（`performance.md` §8.0 已實測過這個機制）。

### N2. `ON DELETE` 一律 `RESTRICT`，且 v1 不做實體刪除

| 情境 | 做法 |
|---|---|
| 標的不再持有 | `instrument.is_active = false`（既有的軟刪除） |
| 規則不要了 | `alert.is_deleted = true`（既有的軟刪除） |
| 交易輸入錯了 | **沖銷**（再輸一筆反向的），不 `DELETE` |
| 使用者要移除 | v1 不支援 |

**為什麼是 `RESTRICT` 而不是 `CASCADE`**：`CASCADE` 在這個資料模型上等於「刪一個 Portfolio 會靜靜帶走它底下所有交易紀錄」，而 Transaction 是**唯一事實來源**——它沒有第二份。`RESTRICT` 讓那個操作在資料庫層直接失敗，而失敗是這裡唯一正確的行為。

**唯二的例外**（1:1 從屬、且可完全重建）：`alert_state.alert_id` 與 `session.user_id` 可用 `CASCADE`。判準是「刪掉它會不會失去任何無法重算的東西」。

### N3. 分型別的欄位約束

`transaction` 各型別的必填欄位（語意見上方「各類型的欄位語意」）必須寫成 `CHECK`，不可只靠應用層：

| `type` | 必須有值 | 必須為 NULL |
|---|---|---|
| `BUY` / `SELL` | `quantity`, `price` | `cash_amount` |
| `CASH_DIVIDEND` | `cash_amount` | `quantity`, `price`, `ratio` |
| `STOCK_DIVIDEND` | `quantity` | `price`, `cash_amount`, `ratio` |
| `SPLIT` | `ratio` | `quantity`, `price`, `cash_amount` |
| `ADJUSTMENT` | `note` | `ratio` |

> **`ADJUSTMENT` 是刻意最寬鬆的那一列**——它是逃生門，`quantity` 與 `cash_amount` 可正可負也可缺。但 `note` 必填這一條不放寬：一筆沒有原因的 `ADJUSTMENT` 在半年後與資料錯誤無法區分。

### N4. 金額與數量一律 `numeric`，顯示路徑才可以是 `float8`

已散見於 `performance.md`，在此明文化：**任何進入成本、損益、報酬率、股數計算的值都是 `numeric`**。`float8` 只允許出現在「送去畫圖」的路徑上。這條連 §1.5 的分割比率乘積也適用（`corporate-actions.md` §1.5 明文禁止 `exp(sum(ln()))`）。

## 已知待補

- 認證流程的完整規格（provider 接法、逃生階梯、cookie 屬性） → [`auth.md`](./auth.md)
- ~~費用與稅欄位的計算規則~~ → **已由 [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 補齊**，見 [`transaction-input.md`](./transaction-input.md) §2（含元以下進位規則，由實際對帳單反推）
- ~~`alert.condition` 的具體結構~~ → **已由 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 補齊**，見 [`alerts.md`](./alerts.md)（改具名欄位、新增 `alert_state`、`notification` 補四欄、`daily_close` 擴充為日 OHLCV）
- ~~個股分析結果要不要落地快取~~ → **已由 [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) 答畢：v1 不落地快取，每次開頁即時算，不需要分析結果快取表**（見 [`analysis-dimensions.md`](./analysis-dimensions.md) §4）。⚠️ **但「不需要新增資料表」只對「分析結果」成立，對「分析所需的輸入資料」不成立**——「產業比較」這一維需要 `instrument.industry_code` 一欄與 `industry_category`、`market_index_daily` 兩張表，皆已補入本文
- ~~績效演算法（TWR / XIRR）需要哪些額外欄位~~ → **已由 [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 答畢：一欄都不用加。** TWR 與 XIRR 的輸入全部來自既有的 `transaction` + `daily_close` + `exchange_rate`。唯一的變動是 `CASH_DIVIDEND` 的 `tax` 欄語意（見上）與 `portfolio_snapshot` 的確定不做。詳見 [`performance.md`](./performance.md)
