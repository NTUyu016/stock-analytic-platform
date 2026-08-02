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
| `provider` | `text` | `yfinance` / `shioaji` / `fugle` / `twse_openapi` |
| `provider_symbol` | `text` | `2330.TW` / `2330` |

- PK `(instrument_id, provider)`；UNIQUE `(provider, provider_symbol)`
- **這張表是換資料源不用搬資料庫的關鍵**。行情源尚未定案（[#2](https://github.com/NTUyu016/stock-analytic-platform/issues/2) / [#8](https://github.com/NTUyu016/stock-analytic-platform/issues/8)），此設計讓該決策不污染核心模型。

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
| `created_at` | `timestamptz` | |

- INDEX `(portfolio_id, instrument_id, traded_on)` — 推導 Position 的主要查詢路徑
- INDEX `(user_id, traded_on)` — 歷史資產曲線
- 各類型的欄位語意：
  - `BUY` / `SELL`：`quantity` + `price` + `fee` + `tax`
  - `CASH_DIVIDEND`：只有 `cash_amount`，不改股數，**降低成本基礎**
  - `STOCK_DIVIDEND`：只有 `quantity`，總成本不變 → 均價被稀釋
  - `ADJUSTMENT`：`quantity` 與 `cash_amount` 可正可負，`note` 必填

> 費用與稅的實際計算規則待 [issue #6](https://github.com/NTUyu016/stock-analytic-platform/issues/6) 的研究結論；本表只保證欄位存在。

### `daily_close`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `instrument_id` | `bigint` FK | |
| `trade_date` | `date` | |
| `close` | `numeric(20,8)` | |
| `prev_close` | `numeric(20,8)` | 算當日漲跌幅用，避免回查前一交易日 |
| `source` | `text` | 資料來源，供日後校正 |

- PK `(instrument_id, trade_date)`
- 新增標的時回補歷史，之後每日盤後排程追一筆。
- 量級：10 支標的 × 10 年 ≈ 2.5 萬列。

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
| `user_id` | `bigint` FK | |
| `instrument_id` | `bigint` FK | |
| `condition` | `jsonb` | 條件內容 |
| `is_enabled` | `boolean` | |

> 條件的具體模型、去重與冷卻策略待 [issue #15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)。此處先以 `jsonb` 佔位，避免現在就把規則形狀鎖死。

### `notification`
| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `bigserial` PK | |
| `alert_id` | `bigint` FK | |
| `triggered_at` | `timestamptz` | |
| `channel` | `text` | 送達管道 |
| `payload` | `jsonb` | |

> 管道選型見 [issue #7](https://github.com/NTUyu016/stock-analytic-platform/issues/7) 的研究結論。

## 刻意不做的表

| 沒有這張表 | 原因 |
|---|---|
| `position` | Position 是推導值。存了就會與 Transaction 不一致，且改一筆舊交易後歷史就錯了。 |
| `lot`（批次） | 成本基礎採加權平均，不需追蹤個別批次。日後要改 FIFO 時，從 Transaction 重建即可，不需要現在就存。 |
| `quote`（即時報價） | 具時效性，落地無價值且量大。活在記憶體與快取中。 |
| `portfolio_snapshot` | 歷史資產曲線由 Transaction + `daily_close` + `exchange_rate` 重算。存快照就無法在修正舊交易後自動修正歷史。效能待 [issue #16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 評估，若真的需要則以**快取**而非事實來源的形式加入。 |

## 已知待補

- 認證流程的完整規格（provider 接法、逃生階梯、cookie 屬性） → [`auth.md`](./auth.md)
- 費用與稅欄位的計算規則 → [#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6)
- `alert.condition` 的具體結構 → [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)
- 個股分析結果要不要落地快取 → [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)
- 績效演算法（TWR / XIRR）需要哪些額外欄位 → [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16)
