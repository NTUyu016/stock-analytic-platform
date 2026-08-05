# Fugle 富果免費層（基本用戶）能力逐項查證

> 起因：[`docs/spec/realtime-quotes.md`](../spec/realtime-quotes.md) 只列出頻道名稱，未逐項查證免費層各頻道的實際可用性與欄位。此空白擋住 [issue #15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 的兩項決策。
> 調查日期：**2026-08-05**
> 撰寫語言：繁體中文（zh-tw）
> 前置研究：[#2 台股即時報價來源選型](./tw-realtime-quote-sources.md)

---

## 0. 研究方法與可信度標示

- 所有結論以**富果官方開發者文件**（`developer.fugle.tw`）與**官方 GitHub / PyPI 套件中繼資料**為第一手來源。
- 富果官網提供 [`llms.txt`](https://developer.fugle.tw/llms.txt) 與 `llms-full.txt`（官方自行產生的全文 Markdown 版本），本文的引文均取自 **2026-08-05 當日下載**的 `https://developer.fugle.tw/llms-full.txt`，內容與各頁 `.md` 版本一致。
- 凡官方文件未載明者，一律標註「**未能查證，需人工確認**」，**不推測、不以二手部落格填空**。
- 本文**未實際持有或使用任何 API key**，所有結論皆為文件層級查證；標註「**需實測驗證**」者代表必須在真的接上去之後才能確認。

| 可信度標記 | 意義 |
|---|---|
| ✅ **官方明文** | 官方文件有直接對應的敘述，本文附原文引用 |
| 🟡 **官方文件推導** | 由官方文件的兩處以上敘述合併推得，官方未直接寫出這句話 |
| ⚠️ **未能查證** | 官方文件完全沒提，需人工確認或實測 |
| 🔵 **原始碼佐證** | 來自官方 SDK 原始碼（`fugle-dev/fugle-marketdata-python`），非文件承諾，版本升級可能改變 |

---

## 1. 免費層（基本用戶）的完整權限表

**來源**：[行情方案及價格](https://developer.fugle.tw/docs/pricing/)（2026-08-05 查證）

官方表格原文（節錄基本用戶欄）：

| 項目 | **基本用戶** | 開發者 | 進階用戶 |
|---|---|---|---|
| 台股即時行情 WebSocket | **5 訂閱數 / 1 連線數** | 300 訂閱數 / 2 連線數 | 2000 訂閱數 / 2 連線數 |
| 台股日內行情 API（呼叫次數/分鐘） | **60/min** | 600/min | 2000/min |
| 台股日內行情快照（呼叫次數/分鐘） | **✘ 不支援** | 600/min | 2000/min |
| 台股歷史行情（呼叫次數/分鐘） | **60/min** | 60/min | 60/min |
| 台股技術指標（呼叫次數/分鐘） | **✘ 不支援** | 60/min | 60/min |
| 台股股務事件（呼叫次數/分鐘） | **✘ 不支援** | 30/min | 30/min |
| 期權即時行情 WebSocket | ✘ 不支援 | 300 訂閱數 / 2 連線數 | 2000 訂閱數 / 2 連線數 |
| 價格 | **註冊富果會員即可免費使用** | NT$1499/月 | NT$2999/月 |

**✅ 官方明文** — 同頁「行情方案說明」原文：

> 台股可追蹤標的包含興櫃、上市櫃個股及指數、權證、ETF、ETN

> 訂閱數：每個訂閱數對應 1 檔股票 x 1 種資料類型（Channel），例如訂閱「2000 檔股票的最新成交資訊（Trades Channel）」，需要 2000 訂閱數。

> 連線數：每個 WebSocket 連線可支援多個訂閱數，例如進階用戶方案中，1 個連線最多支援 2000 訂閱數，最多可建立 2 條連線。

---

## 2. 問題一：免費層實際可訂閱哪些頻道？

### 結論：**五個頻道全部可用，沒有任何一個被方案鎖住。** 🟡 官方文件推導

**來源**：[WebSocket API 開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started/)

官方原文：

> 富果行情 WebSocket API 目前提供以下可訂閱頻道：
> * `trades` - 接收訂閱股票最新成交資訊
> * `candles` - 接收訂閱股票最新分鐘Ｋ
> * `books` - 接收訂閱股票最新最佳五檔委買委賣資訊
> * `aggregates` - 接收訂閱股票聚合數據的行情資訊
> * `indices` - 接收訂閱股票最新指數行情資料

| 頻道 | 免費層可用？ | 判斷依據 |
|---|---|---|
| `trades` | ✅ 是 | 見下方三項證據 |
| `books` | ✅ 是 | 同上 |
| `candles` | ✅ 是 | 同上 |
| `aggregates` | ✅ 是 | 同上 |
| `indices` | ✅ 是 | 同上 |

**推導的三項證據：**

1. 價目表把 WebSocket 只列成**一個項目**（「台股即時行情 WebSocket」），基本用戶欄的值是 `5 訂閱數 / 1 連線數`，**不是 `✘ 不支援`**。方案差異只表現在**數量**，沒有任何逐頻道的欄位。
2. 富果的文件對「方案專屬功能」有**固定的標示慣例**——凡是付費限定的端點，頁面開頭一定有一則 info 方塊，原文為：
   > 屬於 **開發者** 及 **進階用戶** 方案的專屬功能！

   全站僅 **6 個端點**帶有此標示：`/snapshot/quotes`、`/snapshot/movers`、`/snapshot/actives`，以及三個 `/corporate-actions/*`（後者另註「**基本用戶** 開放體驗至 2026/2/12」，該體驗期以今日 2026-08-05 計算**已過期**）。
   **五個 WebSocket 頻道頁面全部沒有這個標示。**
3. 「台股可追蹤標的包含興櫃、上市櫃個股及指數、權證、ETF、ETN」寫在方案說明的共通段落，未區分方案——`indices` 所需的指數標的因此涵蓋在內。

### ⚠️ 但「5 訂閱數」不等於「5 檔股票」——這是本文最容易被誤讀的一點

依官方定義「**每個訂閱數對應 1 檔股票 x 1 種資料類型**」，免費層的 5 個額度是這樣被吃掉的：

| 想要的東西 | 消耗訂閱數 | 免費層放得下嗎 |
|---|---|---|
| 5 檔持股的 `trades` | 5 | ✅ 剛好用完 |
| 5 檔持股的 `aggregates` | 5 | ✅ 剛好用完 |
| 5 檔持股的 `trades` **＋** `books` | **10** | ❌ 超過一倍 |
| 5 檔持股的 `trades` ＋ 1 個大盤 `indices` | **6** | ❌ 超過 |
| 2 檔持股的 `trades` ＋ `books` ＋ 1 檔 `trades` | 5 | ✅ |

> **免費層的真實含意是「5 個 (標的, 頻道) 配對」，也就是：若要看滿 5 檔持股，只能選一個頻道。**

技術指標（`/technical/*`）雖然價目表標「✘ 不支援」，但其五個端點頁面**未帶付費專屬標示**，與價目表不一致。**以價目表為準（不支援），此為文件內部矛盾，需人工確認。** ⚠️

---

## 3. 問題二：`trades` 頻道是否提供逐筆成交？完整欄位是什麼？

### 結論：**是，逐筆（每筆成交一則訊息），且帶流水號與微秒時間戳。** ✅ 官方明文

**來源**：[Trades 頻道](https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/trades/)

頁面說明原文：「**接收訂閱股票最新成交資訊**」。訊息帶有 `serial`（流水號）與微秒級 `time`，且 `isContinuous` 標示「最後成交為逐筆交易：`true`」——逐筆撮合的每一筆成交各自推送一則。

### 完整欄位清單（官方 Response 表格逐字）

| 欄位 | 型別 | 官方說明 |
|---|---|---|
| `symbol`\* | string | 股票代號 |
| `type`\* | string | Ticker 類型 |
| `exchange`\* | string | 交易所 |
| `market` | string | 市場別 |
| `time`\* | number | 時間 |
| `serial`\* | number | 流水號 |
| `bid` | number | 成交買價 |
| `ask` | number | 成交賣價 |
| `price` | number | 成交價格 |
| **`size`** | number | **成交單量** |
| **`volume`** | number | **成交總量** |
| `isLimitDownPrice` | boolean | 最後成交價為跌停價：`true` |
| `isLimitUpPrice` | boolean | 最後成交價為漲停價：`true` |
| `isLimitDownBid` | boolean | 最佳一檔委買跌停價：`true` |
| `isLimitUpBid` | boolean | 最佳一檔委買漲停價：`true` |
| `isLimitDownAsk` | boolean | 最佳一檔委賣跌停價：`true` |
| `isLimitUpAsk` | boolean | 最佳一檔委賣漲停價：`true` |
| `isLimitDownHalt` | boolean | 暫緩撮合且瞬間趨跌：`true` |
| `isLimitUpHalt` | boolean | 暫緩撮合且瞬間趨漲：`true` |
| **`isTrial`** | boolean | **試撮階段：`true`** |
| `isDelayedOpen` | boolean | 延後開盤信號：`true` |
| `isDelayedClose` | boolean | 延後收盤信號：`true` |
| `isContinuous` | boolean | 最後成交為逐筆交易：`true` |
| `isOpen` | boolean | 開盤信號：`true` |
| `isClose` | boolean | 收盤信號：`true` |

（`*` 為官方標示的必填欄位。）

官方範例 payload：

```json
{
  "event": "data",
  "data": {
    "symbol": "2330", "type": "EQUITY", "exchange": "TWSE", "market": "TSE",
    "bid": 567, "ask": 568, "price": 568,
    "size": 4778, "volume": 54538,
    "isClose": true,
    "time": 1685338200000000, "serial": 6652422
  },
  "id": "<CHANNEL_ID>", "channel": "trades"
}
```

### ⚠️ `isTrial` 是本專案必須處理的欄位

試撮（模擬撮合）階段會推送 `isTrial: true` 的成交訊息。台股在 **08:30–09:00** 與 **13:25–13:30** 有試撮，其揭示價可以離真實成交價很遠。

> **若不濾掉 `isTrial: true`，價格警示會在開盤前被試撮價觸發。** 這是「不報錯但結果錯」的靜默錯誤形態，與 `realtime-quotes.md` 反覆在防的是同一類。

`aggregates` 頻道另外把試撮與真實成交拆成兩個獨立物件（`lastTrade` / `lastTrial`），語意上更難搞錯。

---

## 4. 問題三（最關鍵）：成交量欄位的語意

### 結論：**單筆量與當日累積量兩者都有，且是兩個獨立欄位。** ✅ 官方明文

| 欄位 | 官方說明 | 語意 |
|---|---|---|
| `size` | 「成交單量」 | **這一筆**的成交量 |
| `volume` | 「成交總量」 | **當日累積**成交量 |

### 三項互相獨立的佐證

**佐證 1 — 與 `aggregates` 的累積欄位數值一致。**
`aggregates` 頻道明確有一組 `total.*` 統計欄位：

| 欄位 | 官方說明 |
|---|---|
| `total.tradeValue` | 累計成交金額 |
| `total.tradeVolume` | **累計成交量** |
| `total.tradeVolumeAtBid` | 累計內盤成交量 |
| `total.tradeVolumeAtAsk` | 累計外盤成交量 |
| `total.transaction` | 累計成交筆數 |

官方 `aggregates` 範例中，同一時刻（`time: 1685338200000000`）的 `total.tradeVolume` = **54538**，而 `lastTrade.size` = **4778**。
官方 `trades` 範例中同一筆的 `volume` = **54538**、`size` = **4778**。
→ **`trades.volume` 就是 `aggregates.total.tradeVolume`（累計成交量）**，`trades.size` 就是 `lastTrade.size`（最後一筆成交數量）。

**佐證 2 — REST `/intraday/trades` 的時間序列證明 `volume` 單調遞增。**
官方 [Intraday Trades](https://developer.fugle.tw/docs/data/http-api/intraday/trades/) 範例（降冪，時間由新到舊）：

```json
{ "price": 568, "size": 4778, "volume": 54538, "time": 1685338200000000, "serial": 6652422 },
{ "price": 566, "size": 1,    "volume": 49760, "time": 1685337899721587, "serial": 6622549 }
```

較早的一筆 `volume` 較小（49760 < 54538），而 `size` 沒有這個性質（1 vs 4778）。→ **`volume` 是累積量，不是單筆量。**

**佐證 3 — 欄位命名與 REST 快照一致。** `/intraday/quote/{symbol}` 的 `total.tradeVolume` 說明同樣是「累計成交量」，`lastTrade.size` 是「最後一筆成交數量」。三個介面用同一套語意。

### ✅ 對現有規格的影響：**`realtime-quotes.md` §6 的硬性規則成立且可直接實作**

規格原文：

> **統一 Quote 型別的量一律為「當日累積成交量」，不得使用單筆量。** provider 原始欄位差異由 adapter 吸收（§2）。

這條規則**不需要重新設計**。adapter 只要把 `trades.volume`（或 `aggregates.total.tradeVolume`）對應到統一型別的量欄位即可，**不需要任何累加運算**，也就沒有「worker 重啟後累加值歸零」這個常見的坑。§6 擔心的 conflation 靜默丟量問題在 Fugle 上**不會發生**。

### ⚠️ 但有四個必須寫進 adapter 的陷阱

**（a）`volume` 不是必填欄位，可能缺席。**
官方 Response 表格中 `volume` **沒有** `*` 標記（`symbol` / `type` / `exchange` / `time` / `serial` 才有）。且官方 REST 範例的第一筆（`serial: 99999999`、時間 `1685341800000000` 換算為 14:30，推測為盤後定價交易）**完全沒有 `volume` 欄位**：

```json
{ "price": 568, "size": 32, "time": 1685341800000000, "serial": 99999999 }
```

> adapter 讀 `volume` 必須容許缺席，且**缺席時不可當成 0**——當成 0 會讓儀表板的成交量瞬間歸零，並可能誤觸「量能異常」警示。

**（b）單位是「張」不是「股」，且視標的類型而變。** ✅ 官方明文（但只寫在 `candles` 頁）
`candles` 頻道的 `volume` 欄位說明原文：

> Ｋ線成交量（整股：成交張數；興櫃股票及盤中零股：成交股數；指數：成交金額）

`trades` 頁面的 `size` / `volume` **沒有**對應的單位說明 ⚠️。**合理推測**（🟡）三個介面單位一致，但**需實測驗證**。這會直接影響任何「與歷史均量比較」的計算。

**（c）成交量不含零股與鉅額交易。** ✅ 官方明文
[富果行情 API v1.0 使用規範與聲明](https://developer.fugle.tw/docs/data/intro/) 原文：

> 透過本服務取得之行情資料僅供參考，**成交值及成交量不含零股及鉅額交易**，使用者依本資料交易發生交易損失需自行負責。

> 這代表 Fugle 的累積量**與 TWSE 每日總計、與 yfinance 的日成交量在定義上不同**。任何「今日量 vs. 過去 20 日均量」的比較，若基準線取自別的資料源，就會有系統性偏差。詳見 §12。

**（d）試撮階段的 `volume` 語意未載明。** ⚠️
`isTrial: true` 的訊息是否也帶 `volume`、該值是否計入累積，官方文件未說明。**未能查證，需實測驗證。**

---

## 5. 問題四：REST 快照 API 免費層能不能用？

### 結論：**分成兩種東西，一種能用、一種不能用。現有規格把兩者混為一談了。**

| 富果的兩種「快照」 | 端點 | 免費層 | 依據 |
|---|---|---|---|
| **單一標的即時報價** | `GET /intraday/quote/{symbol}` | ✅ **可用，60 次/分鐘** | 屬價目表的「台股**日內行情** API」，基本用戶 60/min；端點頁面**無**付費專屬標示 |
| **全市場行情快照** | `GET /snapshot/quotes/{market}`<br>`GET /snapshot/movers/{market}`<br>`GET /snapshot/actives/{market}` | ❌ **不支援** | 價目表「台股日內行情**快照**」= ✘ 不支援；三個端點頁面均標「屬於 **開發者** 及 **進階用戶** 方案的專屬功能！」 |

### `/intraday/quote/{symbol}` 回傳的是一份完整的當前狀態

**來源**：[Intraday Quote](https://developer.fugle.tw/docs/data/http-api/intraday/quote/)

一次呼叫即取得（節錄）：`referencePrice` 今日參考價、`previousClose` 昨日收盤價、`openPrice`/`highPrice`/`lowPrice`/`closePrice`、`avgPrice` 當日成交均價、`change`/`changePercent`/`amplitude`、`lastPrice`/`lastSize`、**完整最佳五檔 `bids`/`asks`**、**`total.tradeVolume` 累計成交量**、`lastTrade` 最後一筆成交、`lastTrial` 最後一筆試撮、`tradingHalt.isHalted` 暫停交易旗標，以及全套漲跌停／暫緩撮合布林欄位。

呼叫方式（官方 cURL 範例）：

```sh
curl -X 'GET' \
  'https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/2330' \
  -H 'X-API-KEY: <YOUR_API_KEY>'
```

> **5 檔持股 = 5 次呼叫，佔 60 次/分鐘額度的 8.3%。** 每分鐘輪詢一次全部持股都還有 11 倍餘裕。

**這與 `realtime-quotes.md` 的兩處敘述直接矛盾，見 §11。**

---

## 6. 問題五：額度的精確定義

| 子問題 | 結論 | 可信度 |
|---|---|---|
| 5 檔是「同時訂閱的 symbol 數」嗎？ | **不是。是「5 個 (股票 × 頻道) 配對」**，官方原文見 §1 | ✅ 官方明文 |
| 1 連線是帳號級還是 API key 級？ | **未能查證** | ⚠️ |
| 超過額度時 API 的實際行為？ | **未能查證** | ⚠️ |

### 關於「1 連線」的層級

官方文件只寫「連線數：每個 WebSocket 連線可支援多個訂閱數」，**從未說明這 1 條連線是按帳號、按方案訂閱、還是按 API key 計算**。

唯一相關的官方敘述在[使用規範與聲明](https://developer.fugle.tw/docs/data/intro/)：

> 為維護服務品質與公平性，**每位使用者僅限申請及使用一個帳號**。使用者不得以任何方式（包括但不限於註冊多個帳號、使用虛假身份或借用他人身份）**規避本服務所設定之任何使用限制，特別是針對免費行情之取得**。如經發現使用者有違反本規範之行為，本服務有權**不經通知終止其所有相關帳號之使用權限**，並保留追究相關責任的權利。

🟡 **官方文件推導**：方案是掛在「富果會員」帳號上（升級方案的入口是[富果進階功能訂閱](https://www.fugle.tw/setting/subscribe-service?referrer=api)頁，屬會員設定），且條款明文禁止用多帳號規避限制，因此**額度在實務上是帳號級的**。

⚠️ **但「同一帳號下開多把 API key，是否各自享有 1 條連線」官方完全沒寫。未能查證，需人工確認（可寫信 `tech.support@fugle.tw` 或問[官方 Discord](https://discord.gg/sdGQ3v8mEv)）。**

> **對 `realtime-quotes.md` §1「1 條連線是帳號級的，不是行程級的」的評價**：結論方向與條款一致，但**「帳號級」三個字並非官方明文**，是推導。§1 據此推出的「本機開發預設不接真行情」仍然是正確的保守做法——因為不確定性本身就站在保守那一邊。

### 超過額度時會發生什麼

⚠️ **官方 [WebSocket API 文件](https://developer.fugle.tw/docs/data/websocket-api/getting-started/)只定義了一種 error 事件**：

```json
{ "event": "error", "data": { "message": "Invalid authentication credentials" } }
```

[錯誤代碼](https://developer.fugle.tw/docs/data/error_codes/)頁只列 HTTP 狀態碼（401 / 403 / 404 / 429），**沒有任何 WebSocket 層的錯誤碼表**。官方 Python SDK 原始碼也只針對 `Invalid authentication credentials` 這一則做特別處理，其餘 error 事件一律丟給泛用的 `message` 事件（🔵 原始碼佐證，見 §9）。

> **「訂閱第 6 檔會被拒絕、被斷線、還是被停權」官方完全沒有規範。未能查證，必須實測。**
>
> 這對 `realtime-quotes.md` §5「超過額度時明確中斷，不優雅降級」的實作有直接影響：規格假設 worker **自己**先算出超額並停下，這是對的做法；但**若實作依賴伺服器回錯誤才發現超額，就沒有依據**。

坊間搜尋結果曾出現 `{"event":"error","data":{"code":1001,"message":"Maximum number of connections reached"}}` 這則訊息，**但本文無法在富果任何官方頁面上找到它**（已對富果官方全文檔比對 `1001` / `Maximum number` / `reached`，零命中）。**不採信、不列為結論。**

---

## 7. 問題六：重連與退避的官方規範

### 結論：**富果行情 API 沒有公布任何重連頻率限制，也沒有公布停權機制。** ⚠️ 未能查證

已查證的範圍：

| 查了哪裡 | 有沒有 |
|---|---|
| [WebSocket API 開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started/) | ❌ 只有連線／驗證／訂閱格式與 heartbeat，無重連規範 |
| [REST API 開始使用](https://developer.fugle.tw/docs/data/http-api/getting-started/) | ❌ 只寫「如果您 API 請求超過了限制，將收到帶有狀態碼 `429` 的回應」 |
| [錯誤代碼](https://developer.fugle.tw/docs/data/error_codes/) | ❌ 只有 401/403/404/429 |
| [行情方案及價格](https://developer.fugle.tw/docs/pricing/) | ❌ 只有數量額度 |
| [使用規範與聲明](https://developer.fugle.tw/docs/data/intro/) | 🟡 只有針對「多帳號規避限制」的終止權（見 §6），**未提及重連或連線行為** |
| [最佳實踐](https://developer.fugle.tw/docs/trading/best_practice/) | 🟡 屬**交易 API**（已停止更新）的頁面，非行情 API |
| [使用限制](https://developer.fugle.tw/docs/trading/reference/rate_limit/) | 🟡 同上，屬交易 API |

**唯一與行情有關的官方建議**，出現在交易 API 的最佳實踐頁：

> 如果您需要在盤中追蹤股價，建議優先使用 WebSocket API。WebSocket API 提供即時的行情報價，**避免頻繁發送 HTTP 請求**。

### ⚠️ 對 `realtime-quotes.md` §9 的評價

§9 的退避參數（1s→300s、佔登入額度 5% vs 54% 的算式、「停權期間反覆重試會延長停權」）**全部推導自 Shioaji 的官方規則**，不是 Fugle 的。

> **這不是錯誤，是無依據。** Fugle 沒有公布任何懲罰機制，所以「積極重連會被鎖帳號」在 Fugle 上**既無法證實也無法證偽**。
>
> 保守退避在此仍是對的——因為**未來要換 Shioaji**（[#8](https://github.com/NTUyu016/stock-analytic-platform/issues/8)），而 Shioaji 的懲罰是明文的。但 §9 目前的寫法讓人以為那些數字對 Fugle 也有依據，**應改為註明「此參數的依據來自 Shioaji，Fugle 未公布」**。

---

## 8. 問題七：盤中零股、盤後零股、興櫃

| 標的 | 免費層涵蓋？ | 可信度 | 依據 |
|---|---|---|---|
| **盤中零股** | ✅ **有明確的 API 支援，且未見方案限制** | 🟡 | 見下 |
| **盤後零股（13:40–14:30）** | ⚠️ **官方文件完全沒提，未能查證** | ⚠️ | 見下 |
| **興櫃** | ✅ **明確涵蓋** | ✅ | 見下 |

### 盤中零股：WebSocket 與 REST 都有專屬參數

**WebSocket** — [開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started/)原文：

> 在 `data` 指定 `"intradayOddLot": true` 可訂閱盤中零股行情。

`trades` / `books` / `candles` / `aggregates` **四個頻道的 Parameters 表格都列有**這個參數：

| Name | Type | Description |
|---|---|---|
| `intradayOddLot` | boolean | `intradayOddLot` true: 盤中零股, false: 股票, default: false |

**REST** — `/intraday/quote`、`/intraday/trades`、`/intraday/candles`、`/intraday/volumes`、`/intraday/ticker` 均有參數「`type`：類型，可選 `oddlot` 盤中零股」；`/intraday/tickers` 的 `type` 參數可選值含「`ODDLOT` 盤中零股」。

**沒有任何一處標示盤中零股為付費專屬功能。** 🟡

> ⚠️ **但零股訂閱要不要另外吃額度，官方沒寫。** 依「1 訂閱數 = 1 檔股票 × 1 種資料類型」的定義，最合理的推測是「同一檔的整股與零股是兩個不同的訂閱」，**但這是推測，需實測**。若成立，免費層根本擠不出額度同時看整股與零股。

### 盤後零股：查不到

搜遍富果全站文件，**「盤後」二字只出現在期權（futopt）文件的 `AFTERHOURS` 盤後交易時段參數上**，台股股票側完全沒有任何盤後零股（13:40–14:30）的敘述。

> ⚠️ **未能查證，需人工確認。** `realtime-quotes.md` §8 決定「不涵蓋盤後零股」的理由是「Fugle 免費層零股支援情況未查證，不押注」——**現在查證了：盤中零股有明文，盤後零股仍然查不到。** §8 的決定結果不變，但理由要改寫，見 §11。

### 興櫃：明確涵蓋

- 價目表方案說明：「台股可追蹤標的**包含興櫃**、上市櫃個股及指數、權證、ETF、ETN」（✅ 官方明文，未區分方案）
- `/intraday/tickers` 的 `market` 參數可選值：「`TSE` 上市；`OTC` 上櫃；**`ESB` 興櫃一般板**；**`TIB` 臺灣創新板**；**`PSB` 興櫃戰略新板**」
- `/intraday/ticker` 有多個欄位標註「（興櫃股不適用）」：`limitUpPrice` 漲停價、`limitDownPrice` 跌停價、`canDayTrade` 可買賣現沖、`matchingInterval` 撮合循環秒數等——**反證興櫃資料確實會回，只是這些欄位無值。**
- ⚠️ 但**歷史行情不含興櫃**：方案說明原文「台股歷史行情目前僅支援上市櫃個股及 ETF」。

---

## 9. 問題八：WebSocket 心跳／keepalive，以及「休市無資料」vs「連線異常」

### 官方 heartbeat：每 30 秒，由 server 主動送 ✅ 官方明文

[開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started/)原文：

> 每隔 30 秒 WebSocket server 會送出一個 heartbeat 訊息：
> ```json
> { "event": "heartbeat", "data": { "time": "<Timestamp>" } }
> ```

### 官方 Ping/Pong：由 client 主動送，server 回應 ✅ 官方明文

> 將以下 JSON 格式訊息發送到 WebSocket Server (`state` 為可選)：
> ```json
> { "event": "ping", "data": { "state": "<ANY>" } }
> ```
> WebSocket Server 會回應以下訊息 (若 ping 未送 `state` 則不會有該欄位)：
> ```json
> { "event": "pong", "data": { "time": "<TIMESTAMP>", "state": "<ANY>" } }
> ```

### ✅ `realtime-quotes.md` §8 的「休市 vs 斷線」判準成立

規格原文：

> **連得上、heartbeat 還在、但沒有成交資料 → 正常**（休市或該檔無人交易）。
> **連不上或 heartbeat 停止 → 異常**

**這條完全成立**，heartbeat 每 30 秒一則是官方承諾。但實作上有兩個坑（🔵 原始碼佐證）：

**坑 1：官方 Python SDK 不把 heartbeat 當成獨立事件。**
SDK 只定義五種事件：`connect` / `disconnect` / `message` / `error` / `authenticated`（`unauthenticated` 為內部用）。heartbeat 訊息是走**泛用的 `message` 事件**送出來的。

> worker 必須自己在 message handler 裡判斷 `data['event'] == 'heartbeat'` 並更新「最後 heartbeat 時間」，**SDK 不會幫你做**。

**坑 2：SDK 內建的 health check 預設是關閉的。**
`fugle_marketdata/websocket/client.py` 中：

```python
class HealthCheckConfig:
    def __init__(self, enabled: bool = False, ping_interval: int = 30000, max_missed_pongs: int = 2):
```

`enabled` 預設 `False`，且要透過 `health_check` 設定物件才會啟用。**不明確開啟就完全沒有 ping/pong 保活。**

⚠️ 該機制本身還有兩個可疑之處（🔵）：`__send_ping()` 是先 `self.missed_pongs += 1` 再檢查、且超標時在 `threading.Timer` 執行緒裡 `raise`（該例外不會傳到主執行緒）。**建議自行實作 heartbeat 監看，不要依賴 SDK 的 health check。**

### ⚠️ 額外發現：SDK 會改動行程層級的全域狀態

`client.py` 第 19 行（模組載入時就執行）：

```python
websocket.setdefaulttimeout(5)
```

> `import fugle_marketdata` 會把 `websocket-client` 的**全域**預設 socket timeout 改成 5 秒，影響同一行程內所有其他 websocket-client 的使用。v1 只有一個 WebSocket 用途，暫時無害，但屬於「adapter 的副作用滲出邊界」，值得記一筆。

---

## 10. 問題九：官方 Python SDK 的現況與 wheel 問題

### 結論：**有官方 SDK，維護活躍，且是純 Python wheel——Alpine base image 沒有 `shioaji` 那種問題。** ✅

**來源**：[PyPI `fugle-marketdata`](https://pypi.org/project/fugle-marketdata/)（2026-08-05 查證）、[GitHub `fugle-dev/fugle-marketdata-python`](https://github.com/fugle-dev/fugle-marketdata-python)

| 項目 | 值 |
|---|---|
| 最新穩定版 | **2.4.1** |
| 最新版發布時間 | **2026-08-04**（本文調查日的前一天） |
| Python 版本需求 | `>=3.7, <4.0` |
| 發行檔 | **`fugle_marketdata-2.4.1-py3-none-any.whl`** ＋ sdist |
| 授權 | MIT |
| 官方 Node.js SDK | [`fugle-marketdata-node`](https://github.com/fugle-dev/fugle-marketdata-node) / `@fugle/marketdata` |

### wheel／Alpine 相容性逐項查證

`fugle-marketdata` 本身是 **`py3-none-any`（純 Python，無編譯擴充）**，所以問題全部落在依賴上：

```
requests<3.0.0,>=2.28.2
websocket-client<2.0.0,>=1.5.1
pyee<10.0.0,>=9.0.4    (python <= 3.11.0)
pyee<12.0.0,>=11.1.0   (python >  3.11.0)
orjson<4.0.0,>=3.9.0
```

| 依賴 | 有無編譯擴充 | musllinux（Alpine）wheel |
|---|---|---|
| `requests` | 無（純 Python） | 不需要 |
| `websocket-client` | 無（純 Python） | 不需要 |
| `pyee` | 無（純 Python） | 不需要 |
| **`orjson`** | **有（Rust）** | ✅ **有** |

`orjson` 最新版 **3.11.9** 的發行檔中確認存在
`orjson-3.11.9-cp310-cp310-musllinux_1_2_x86_64.whl`、`...musllinux_1_2_aarch64.whl`、`...musllinux_1_2_armv7l.whl`、`...musllinux_1_2_i686.whl`，
且 musllinux 支援自 3.10.0 起即完整覆蓋（全套件共 930 個 musllinux wheel）。

> **結論：Fugle Python SDK 在 Alpine base image 上可以純靠 wheel 安裝，不需要 Rust toolchain，沒有 `shioaji` 的問題。** ✅

### 🔵 SDK 原始碼層級的三個實作事實（非官方承諾，版本升級可能改變）

**（a）SDK 完全沒有自動重連。**
`connect()` 的全部內容是：

```python
def connect(self):
    Thread(target=self.__ws.run_forever).start()
    while True:
        if self.auth_status in [AuthenticationState.AUTHENTICATED, AuthenticationState.UNAUTHENTICATED]:
            break
    ...
```

`run_forever()` 未帶 `reconnect=` 參數，斷線後只會觸發 `disconnect` 事件然後結束。
> **`realtime-quotes.md` §9 的整套退避重連必須由本專案自己實作，SDK 一點忙都幫不上。這反而是好事——退避策略完全在我們掌控中，可被假時鐘測試。**

**（b）`connect()` 是忙碌等待（busy-wait），會空轉燒掉一顆 CPU 核心。**
上面的 `while True:` 迴圈**沒有 sleep**，從連線建立到驗證完成期間持續空轉。正常情況只有幾十毫秒；**但若驗證卡住，最長會空轉 5 秒**（`auth_timer = Timer(5, ...)`）。每次重連都要付一次。
> 在 scale-to-zero／小規格機器上這是可觀察的成本，且**重連迴圈越頻繁越糟**。列入實作注意事項。

**（c）callback 在 SDK 自己的背景執行緒上。**
`Thread(target=self.__ws.run_forever).start()` — 所有 `message` / `error` / `disconnect` handler 都在這條執行緒上被呼叫。
> ✅ **這第一手驗證了 `realtime-quotes.md` §2 的硬性規則**：「callback 內只做一件事：`loop.call_soon_threadsafe(...)`」。該規則原本是推測，現在有原始碼佐證。

---

## 11. ⚠️ 與既有規格的矛盾

以下逐條列出與 [`docs/spec/realtime-quotes.md`](../spec/realtime-quotes.md) 的出入。**本文不做決策，只陳述事實與代價。**

### 矛盾 1：「Fugle 免費層沒有快照 API」——錯誤，或至少是嚴重的措辭不精確

| 出處 | 現有敘述 |
|---|---|
| §2 | 「`supports_snapshot: bool   # fugle_free=False`」 |
| §2 | 「`tech-stack.md` §4 發現『Fugle 免費層沒有快照 API，所以降級路徑改用 yfinance』」 |
| §7 | 四層階梯的第 3 層＝「**yfinance 延遲報價**」（盤中但 worker 缺席） |
| §10 條目 4 | 「開頁降級路徑走 **yfinance** 而非 provider 快照 API；Fugle 免費層『快照』欄位為不支援」 |

**事實**（§5）：免費層**不支援的是全市場快照 `/snapshot/*`**；**單一標的的即時報價 `/intraday/quote/{symbol}` 是支援的，60 次/分鐘**，且回傳內容比 yfinance 完整得多（含最佳五檔、累計成交量、暫停交易旗標、微秒時間戳）。

**代價一覽：**

| 面向 | 現行設計（第 3 層走 yfinance） | 若改走 `/intraday/quote` |
|---|---|---|
| 資料新鮮度 | **延遲 15 分鐘** | **即時** |
| 額度 | yfinance 無正式額度，隨時可能被擋 | 5 檔 = 60/min 的 8.3% |
| 資料源一致性 | 與盤中即時價**來自不同機構、不同定義** | **與 WebSocket 同源同定義** |
| UI 負擔 | §7 規定第 3 層必須顯示橫幅＋降透明度 | 若即時，理論上不需降級標示 |
| 對 `ProviderCapabilities` | `supports_snapshot: bool` | **布林值不夠用**，至少要拆成 `supports_symbol_quote` 與 `supports_market_snapshot` |

> **附帶影響**：§2 稱這條規則「同時修好了一個既有的洞……轉 Shioaji 時快照路徑會自動可用，不需要有人記得回來改」。但**若 `supports_snapshot` 這個布林值本身的定義是錯的，那個「自動」會自動到錯的地方去**——Fugle 免費層會被永久標成 `False`，明明有能力卻永遠走降級路徑。

### 矛盾 2：「5 檔」的單位不精確——是 5 個 (標的×頻道) 配對，不是 5 檔股票

| 出處 | 現有敘述 |
|---|---|
| §2 | 「`max_subscriptions: int    # fugle_free=5`」 |
| §3 | 「訂閱標的｜5 檔｜Fugle 免費層上限」 |
| §5 | 「Fugle 免費層訂閱上限 5 檔」 |
| §10 條目 1 | 「同時只能訂閱 **5 檔**」 |

**事實**（§1、§2）：官方定義是「每個訂閱數對應 1 檔股票 x 1 種資料類型（Channel）」。

**代價：** 5 檔持股**只能訂閱其中一個頻道**。這對現有規格產生三處未被討論的後果：

1. **`ProviderCapabilities.max_subscriptions` 的語意有歧義。** 核心程式若拿它跟「持股檔數」比大小，只有在「每檔恰好訂一個頻道」時才正確。轉 Shioaji（額度定義為 200 檔）時，**兩家的單位不同**——這正是 §2 要求 adapter 吸收的那類差異，但目前的欄位名沒有表達出來。
2. **`dashboard-ui.md` 若需要最佳五檔，就撞牆了。** `trades` 不含五檔；要五檔得訂 `books`（再吃 5 個額度）或改訂 `aggregates`。
3. **`aggregates` 是被忽略的第三條路。** 它一則訊息就同時包含最後成交價、最佳五檔、`total.tradeVolume` 累計量、`change`/`changePercent`——**用 1 個訂閱數拿到 `trades` + `books` 的內容**。代價是它**不是逐筆**（是聚合後的當前狀態快照），會直接消滅 §6「worker 看得到未節流逐筆流」這項優勢。詳見 §12。

### 矛盾 3：「Fugle 免費層零股支援未查證」——盤中零股已查證為有支援

| 出處 | 現有敘述 |
|---|---|
| §2 | 「`supports_odd_lot: bool   # fugle_free=False  shioaji=True`」 |
| §8 | 「盤中零股是 Shioaji **才**明確具備的能力（`intraday_odd` 參數），**Fugle 免費層的支援情況研究票未查證**。涵蓋它等於押注一個沒查證的能力。」 |
| §10 條目 5 | 「Fugle 免費層零股支援未查證，不押注」；解除條件「轉 Shioaji（有 `intraday_odd`）」 |

**事實**（§8）：Fugle 的 `trades`/`books`/`candles`/`aggregates` 四個頻道都有 `intradayOddLot` 參數，REST 側有 `type=oddlot`，且**未標示為付費專屬**。「盤中零股是 Shioaji 才有的能力」這句話**不成立**。

**但 §8 的決定（開機時段 09:00–13:35，不涵蓋盤後零股）結論仍然正確**，因為：

- §8 涵蓋的時段爭議是 **13:40–14:30 的盤後零股**，而**盤後零股在 Fugle 文件裡完全查不到**（仍是 ⚠️ 未能查證）。
- 即使盤中零股可用，**額度也擠不出來**（推測需另計訂閱數，§8）。

> **要改的是理由與 `supports_odd_lot` 的值，不是結論。** §10 條目 5 的「解除條件＝轉 Shioaji」也不再準確——盤中零股不需要等 Shioaji，等的是**訂閱額度**。

### 矛盾 4：§9 的退避參數在 Fugle 上沒有依據（非矛盾，是無依據）

§9 的整套推導（登入額度百分比、「停權期間反覆重試會延長停權」）**來源全部是 Shioaji**。Fugle 對重連頻率、停權機制**零公布**（§7）。

> 這不是錯誤，但目前的行文會讓後續讀者以為那些數字對現行 provider 也有官方依據。**建議在 §9 加一行註明依據來源與適用 provider。**

### 對照：三處**經查證成立**的敘述（不是矛盾，是確認）

| 出處 | 敘述 | 查證結果 |
|---|---|---|
| §6 | 「統一 Quote 型別的量一律為**當日累積成交量**」 | ✅ **成立且零成本**——`trades.volume`（成交總量）直接就是累積量，adapter 不需累加運算（§4） |
| §8 | 「Fugle 每 30 秒送 heartbeat」→ 用來區分休市與斷線 | ✅ **官方明文成立**（§9） |
| §2 | 「callback 不在 event loop 上，只能 `call_soon_threadsafe`」 | ✅ **原始碼佐證成立**——SDK 用 `Thread(target=run_forever)`（§10） |

---

## 12. 對 issue #15 的影響

> [issue #15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 被擋住的兩項是：**（甲）成交量異常警示是否可行**、**（乙）未節流逐筆成交是否真的拿得到**（決定警示在 `quote-worker` 評估相對於在 `api` 評估是否有價值）。以下只陳述事實與代價，**不做決策**。

### 甲、成交量異常警示：**技術上可行，但有四道必須先處理的關卡**

**可行的部分（✅ 官方明文）：**

- `trades` 頻道**每一筆成交都帶 `volume`（當日累積成交量）**，警示不需要自行累加，也不會被 §6 的 conflation 弄丟（§4）。
- `aggregates` 頻道另外提供 `total.tradeValue`（累計成交金額）、`total.transaction`（累計成交筆數）、`total.tradeVolumeAtBid` / `total.tradeVolumeAtAsk`（累計內／外盤成交量）——**「爆量」以外的量能形態（如內外盤失衡）也拿得到**。
- 免費層可用的 `/intraday/quote/{symbol}`（60/min）也帶 `total.tradeVolume`，**即使 `quote-worker` 沒開機，也有一條不靠 WebSocket 的取量途徑**（§5）。

**四道關卡：**

| # | 關卡 | 嚴重度 | 說明 |
|---|---|---|---|
| 1 | **基準線的資料源必須與 Fugle 同定義** | 🔴 高 | 官方明文「**成交值及成交量不含零股及鉅額交易**」（§4c）。若「過去 N 日均量」取自 yfinance／TWSE（含零股與鉅額），而「今日量」取自 Fugle（不含），**比值會有系統性偏低**，導致爆量警示該響不響。這是**不會報錯的靜默偏差**，與專案一貫在防的錯誤形態相同。 |
| 2 | **單位（張 vs 股）未在 `trades` 頁載明** | 🟠 中 | 官方只在 `candles` 頁寫「整股：成交張數；興櫃股票及盤中零股：成交股數；指數：成交金額」（§4b）。`trades.volume` 的單位**需實測驗證**。若基準線用「股」而即時值用「張」，會差 1000 倍。 |
| 3 | **`volume` 可能缺席，且不可當 0** | 🟠 中 | 非必填欄位，官方 REST 範例中盤後定價那筆就沒有它（§4a）。當 0 會讓量能瞬間歸零並可能誤觸警示。 |
| 4 | **試撮訊息的量語意未知** | 🟡 低 | `isTrial: true` 的訊息是否帶 `volume`、是否計入累積，官方未寫（§4d）。**需實測**。 |

**額度代價：** 若要同時做價格警示與量能警示，`trades` 一個頻道就同時給 `price` 與 `volume`，**不需要額外訂閱數**。✅

**時間範圍代價：** 依 `realtime-quotes.md` §8，`quote-worker` 只在 **09:00–13:35** 開機。**盤後零股與盤後定價時段的量不會進入即時警示路徑**（且盤後零股本身在 Fugle 查不到，§8）。

### 乙、未節流逐筆成交：**確定拿得到，§6 交給 #15 的那句話成立**

`realtime-quotes.md` §6 的原文是：

> worker 端在 conflation **之前**看得到完整未節流的價格流，`api` 只看得到取樣後的。……**在 worker 評估看得到瞬間穿越門檻的價格，在 `api` 評估則會漏掉。**

**✅ 這是事實，不是推測。** `trades` 頻道是**每筆成交推一則訊息**，帶 `serial` 流水號與微秒 `time`（§3）。worker 收到的就是完整的逐筆成交流；經 800ms conflation 之後只剩下每 800ms 一則。

**兩者的實際差距有多大：** 台股逐筆撮合，熱門股單秒可數十筆成交（§6 已述）。在 800ms 窗口內，**中間的所有價格都會被丟棄**。因此：

| 警示型態 | worker 端（未節流） | `api` 端（800ms 取樣） |
|---|---|---|
| 「價格跌破 X」（**穿越型**） | 每一筆都比對，不會漏 | **會漏**掉窗口內短暫穿越又彈回的情形 |
| 「現價低於 X」（**狀態型**） | 同左 | 幾乎等價（最多晚 800ms） |
| 「累積量超過 Y」 | 每一筆都比對 | **幾乎等價**——因為 `volume` 是累積量，取樣不會丟失（§4） |
| 「單筆大量（`size` > Z）」 | 每一筆都比對，不會漏 | **會漏**——`size` 是單筆量，conflation 直接丟掉中間筆 |
| 漲跌停 / 暫緩撮合 | `isLimitUpPrice` 等布林欄位逐筆可見 | 布林為狀態型，取樣後仍看得到 |

> **關鍵區分：警示條件若只依賴「累積量」與「當前價」這類狀態量，在 `api` 端評估幾乎沒有損失；若依賴「穿越」或「單筆量」，就必須在 worker 端評估。**

**在 worker 端評估要付的三筆帳：**

1. **`quote-worker` 是可選元件。** `tech-stack.md` §4 定它可選，`realtime-quotes.md` §8 更立下規則：「**可選元件不能持有必要資料的產生責任**」（該規則正是用來把 `daily_close` 趕出 worker 的）。**把警示評估放進 worker，等於讓一個允許缺席的元件承擔警示送達責任**——與該規則的形狀相同。這是 #15 必須正面回答的張力，本文不代答。
2. **試撮必須先濾掉。** 未濾 `isTrial: true` 會在 08:30–09:00、13:25–13:30 用試撮價觸發警示（§3）。這在 worker 端與 `api` 端都要做，但 worker 端因為看到逐筆，**暴露面更大**。
3. **`realtime-quotes.md` §5 已定的限制不變**：即時警示只能設在**持股標的**上，因為非持股標的沒有訂閱額度。且**額度僅 5 個 (標的×頻道) 配對**（§2），所以「訂 `trades` 做警示」與「訂 `aggregates` 拿完整儀表板資料」**是互斥的**——

| 選 `trades`（5 訂閱） | 選 `aggregates`（5 訂閱） |
|---|---|
| ✅ 逐筆，穿越型與單筆量警示可行 | ❌ 聚合後的狀態快照，**逐筆流消失**，穿越型警示的 worker 優勢歸零 |
| ❌ 無最佳五檔 | ✅ 含最佳五檔、`change`/`changePercent`、內外盤量、成交筆數 |
| 需自行由 `previousClose` 算漲跌幅（`trades` 不含） | ✅ 漲跌幅由 provider 算好（但**含試撮**，見 §3） |

> **這是 #15 與 [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)（個股分析頁）之間一個尚未被記錄的耦合**：選 `trades` 就等於選了「警示精度優先」，選 `aggregates` 就等於選了「畫面資訊量優先」。5 個額度不允許兩者兼得。

---

## 13. 待實測驗證清單

以下每一項都**無法從文件確認**，必須在真的接上 API 之後才能回答。列此供實作階段逐項打勾。

| # | 待驗證 | 影響誰 |
|---|---|---|
| 1 | `trades.size` / `trades.volume` 的單位是「張」還是「股」 | #15 量能警示（§4b） |
| 2 | 訂閱第 6 個 (標的×頻道) 時 server 的實際回應：拒絕？斷線？無聲忽略？ | `realtime-quotes.md` §5 超額行為（§6） |
| 3 | 同一帳號多把 API key 是否各自享有 1 條連線 | `realtime-quotes.md` §1 本機開發策略（§6） |
| 4 | 盤中零股訂閱是否另計訂閱數 | `realtime-quotes.md` §8、#15 涵蓋範圍（§8） |
| 5 | 盤後零股（13:40–14:30）是否有資料 | `realtime-quotes.md` §8（§8） |
| 6 | `isTrial: true` 的訊息是否帶 `volume`，該值是否計入累積 | #15 量能警示（§4d） |
| 7 | 休市日（含颱風假）連上後的實際行為：仍送 heartbeat 嗎？ | `realtime-quotes.md` §8 三層休市判斷（§9） |
| 8 | `/intraday/quote/{symbol}` 在免費層是否真的回 200（而非 403） | §11 矛盾 1 的解法可行性（§5） |
| 9 | 第二條 WebSocket 連線建立時，第一條是被踢還是新的被拒 | `realtime-quotes.md` §1（§6） |

---

## 14. 來源清單

**富果官方文件**（全部於 2026-08-05 查證）

- [富果行情 API v1.0（含使用規範與聲明）](https://developer.fugle.tw/docs/data/intro/)
- [台股行情方案及價格](https://developer.fugle.tw/docs/pricing/)
- [WebSocket API 開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started/)
- [WebSocket — Trades](https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/trades/)
- [WebSocket — Books](https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/books/)
- [WebSocket — Candles](https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/candles/)
- [WebSocket — Aggregates](https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/aggregates/)
- [WebSocket — Indices](https://developer.fugle.tw/docs/data/websocket-api/market-data-channels/indices/)
- [REST API 開始使用](https://developer.fugle.tw/docs/data/http-api/getting-started/)
- [REST — Intraday Quote](https://developer.fugle.tw/docs/data/http-api/intraday/quote/)
- [REST — Intraday Trades](https://developer.fugle.tw/docs/data/http-api/intraday/trades/)
- [REST — Intraday Tickers](https://developer.fugle.tw/docs/data/http-api/intraday/tickers/)
- [REST — Snapshot Quotes](https://developer.fugle.tw/docs/data/http-api/snapshot/quotes/)（付費專屬）
- [REST — Snapshot Movers](https://developer.fugle.tw/docs/data/http-api/snapshot/movers/)（付費專屬）
- [REST — Snapshot Actives](https://developer.fugle.tw/docs/data/http-api/snapshot/actives/)（付費專屬）
- [錯誤代碼](https://developer.fugle.tw/docs/data/error_codes/)
- [常見問答](https://developer.fugle.tw/docs/faq/intro/)
- [服務狀態](https://developer.fugle.tw/docs/data/status/)
- 全文檔快照：[`https://developer.fugle.tw/llms-full.txt`](https://developer.fugle.tw/llms-full.txt)（官方提供，本文引文的取得管道）

**官方套件與原始碼**

- [PyPI `fugle-marketdata` 2.4.1](https://pypi.org/project/fugle-marketdata/)（發布於 2026-08-04）
- [GitHub `fugle-dev/fugle-marketdata-python`](https://github.com/fugle-dev/fugle-marketdata-python) — 特別是 `fugle_marketdata/websocket/client.py`、`fugle_marketdata/constants.py`
- [GitHub `fugle-dev/fugle-marketdata-node`](https://github.com/fugle-dev/fugle-marketdata-node)
- [PyPI `orjson` 3.11.9](https://pypi.org/project/orjson/)（musllinux wheel 查證）

**官方支援管道**（供 §13 待驗證項目人工確認用）

- 技術客服：`tech.support@fugle.tw`
- 官方技術社群：[Discord](https://discord.gg/sdGQ3v8mEv)
- [富果客服中心 API 專區](https://support.fugle.tw/tag/api/)

**刻意未採信的來源**

- 搜尋結果中出現的 WebSocket 錯誤碼 `1001 / "Maximum number of connections reached"`：無法在富果任何官方頁面上比對到，疑似來自富邦新一代 API（Fubon Neo）或其他同技術夥伴的文件。**未列為結論**（§6）。
