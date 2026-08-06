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
| `instrument_type` | `text` | `STOCK` / `ETF` / `CRYPTO` |
| `is_active` | `boolean` | 下市/下架後設 false，不刪除（歷史交易仍需引用） |

- UNIQUE `(market, symbol)`
- 台積電台股與其 ADR 是兩列。

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
| `type` | `text` | `BUY` / `SELL` / `CASH_DIVIDEND` / `STOCK_DIVIDEND` / `ADJUSTMENT` |
| `traded_on` | `date` | 成交日 |
| `quantity` | `numeric(20,8)` | 股數。`numeric` 而非整數：零股、加密貨幣、股票股利配發都會有小數 |
| `price` | `numeric(20,8)` | 每股價格，原幣別 |
| `fee` | `numeric(20,4)` | 手續費 |
| `tax` | `numeric(20,4)` | 證交稅 |
| `cash_amount` | `numeric(20,4)` | 現金股利總額（`CASH_DIVIDEND` 用） |
| `currency` | `char(3)` | 冗餘自 instrument，凍結交易當下的幣別 |
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
  - `ADJUSTMENT`：`quantity` 與 `cash_amount` 可正可負，`note` 必填

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
| `rate` | `numeric(20,8)` | 1 單位外幣 = ? TWD |

- PK `(currency, rate_date)`
- 歷史績效一律取當日匯率；查無當日（假日）時取前一個有值的日期。

### `alert`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `user_id` | `bigint` FK NOT NULL | |
| `instrument_id` | `bigint` FK NOT NULL | |
| `rule_type` | `text` NOT NULL | 六種具名類型之一，`CHECK` 列舉 |
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
| `updated_at` | `timestamptz` NOT NULL | |

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
| `effective_on` | `date` | 除權息基準日 |
| `proposed` | `jsonb` | 系統算出的預填值 |
| `source` | `text` | 產生來源，如 `twse_TWT48U_ALL` |
| `created_at` | `timestamptz` | |

- 待使用者確認的項目。**確認後才 INSERT 進 `transaction`，本表列刪除或標記已處理。**
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

## 已知待補

- 認證流程的完整規格（provider 接法、逃生階梯、cookie 屬性） → [`auth.md`](./auth.md)
- ~~費用與稅欄位的計算規則~~ → **已由 [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 補齊**，見 [`transaction-input.md`](./transaction-input.md) §2（含元以下進位規則，由實際對帳單反推）
- ~~`alert.condition` 的具體結構~~ → **已由 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 補齊**，見 [`alerts.md`](./alerts.md)（改具名欄位、新增 `alert_state`、`notification` 補四欄、`daily_close` 擴充為日 OHLCV）
- 個股分析結果要不要落地快取 → [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)
- ~~績效演算法（TWR / XIRR）需要哪些額外欄位~~ → **已由 [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 答畢：一欄都不用加。** TWR 與 XIRR 的輸入全部來自既有的 `transaction` + `daily_close` + `exchange_rate`。唯一的變動是 `CASH_DIVIDEND` 的 `tax` 欄語意（見上）與 `portfolio_snapshot` 的確定不做。詳見 [`performance.md`](./performance.md)
