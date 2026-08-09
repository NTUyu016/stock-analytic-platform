# v1 技術規格

> 這是 [issue #1「地圖：v1 台股持股儀表板網站 — 技術規格」](https://github.com/NTUyu016/stock-analytic-platform/issues/1) 的交付物索引。
> 決定於 [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18)（規格文件的形狀與交付）。

## 這份規格是給誰看的

**一個沒有參與過任何討論的實作者**——很可能是一個新開 session 的 agent。

**驗收標準**（#18 定）：把這份規格交給一個乾淨的 session，它應該能直接開始實作，**中途不需要回頭問人**。它問得出來的問題，就是規格的缺口。

---

## 先讀這三份

| 順序 | 文件 | 為什麼在這個位置 |
|---|---|---|
| 1 | [`../../CONTEXT.md`](../../CONTEXT.md) | **詞彙表。** 所有文件用的名詞在這裡定義，包含「刻意避免的講法」。用了衝突的講法要當場提出 |
| 2 | [`data-model.md`](./data-model.md) | **領域模型與資料表綱要。** 其他每一份文件都在講「怎麼把東西寫進這些表、怎麼從這些表推導出來」 |
| 3 | [`tech-stack.md`](./tech-stack.md) | **技術選型與 repo 結構。** 決定了程式碼放哪、用什麼寫、怎麼測 |

**最重要的一句話**（`data-model.md`）：**Transaction 是唯一的事實來源**。Position、成本、損益、歷史曲線全都是推導值，一律不落地。

---

## 全部文件

### 架構與基礎設施

| 文件 | 內容 | 票 |
|---|---|---|
| [`tech-stack.md`](./tech-stack.md) | Python 3.13 + FastAPI、uv、React + Vite 純靜態 SPA、兩個部署單元、Caddy、分層測試策略、base image 必須 Debian | [#12](https://github.com/NTUyu016/stock-analytic-platform/issues/12) |
| [`realtime-quotes.md`](./realtime-quotes.md) | 行情擷取與扇出：只有 `quote-worker` 連行情源、worker→api 走 Postgres `LISTEN/NOTIFY`、api→瀏覽器走 SSE、800ms 節拍 | [#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) |
| [`auth.md`](./auth.md) | Google OIDC + GitHub OAuth 備援、伺服器端 session、allowlist 自查、不自動建帳號 | [#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) |
| [`deployment.md`](./deployment.md) | v1 跑本機、Tailscale 私網、同機自架 Postgres、回補式排程、三種失效模式各一招的監控、上雲遷移路徑 | [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) |

### 領域邏輯

| 文件 | 內容 | 票 |
|---|---|---|
| [`data-model.md`](./data-model.md) | 資料表綱要與核心原則 | [#9](https://github.com/NTUyu016/stock-analytic-platform/issues/9) |
| [`transaction-input.md`](./transaction-input.md) | CSV 匯入為主、手動表單為輔、去重自然鍵、漏輸入偵測三層、對帳只比股數 | [#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) |
| [`performance.md`](./performance.md) | 每次從 Transaction 重算、XIRR 與 TWR、基準含息、曲線日曆、**§8 七個會靜默出錯的地方**、**§8A 十一條不變量** | [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) |
| [`corporate-actions.md`](./corporate-actions.md) | `SPLIT` 具名型別與比率、峰值分割調整、減資／換股的分流、偵測與未確認處理 | [#20](https://github.com/NTUyu016/stock-analytic-platform/issues/20) |
| [`alerts.md`](./alerts.md) | 六種具名規則類型、回歸重置去重、追蹤停損完整版、管道 Discord 且內文不含金額 | [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) |
| [`analysis-dimensions.md`](./analysis-dimensions.md) | 個股分析頁六維、Coverage 取代 confidence、資料不足一律明說 | [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) |

### 介面

| 文件 | 內容 | 票 |
|---|---|---|
| [`dashboard-ui.md`](./dashboard-ui.md) | 側欄 + 單頁三層、顏色只保留給價格方向、連線三態、tick 用細直條、交易明細依市場拆表 | [#11](https://github.com/NTUyu016/stock-analytic-platform/issues/11) |

### 支援材料（不是規格，不可據以實作）

| 目錄 | 是什麼 |
|---|---|
| [`../research/`](../research/) | 決策所依據的第一手查證。**規格與研究衝突時以規格為準**，但研究裡記著「為什麼」 |
| [`../briefing/`](../briefing/) | 決策票的上桌前準備（事實查證、選項盤點）。**刻意不含結論**；已定案者一律以本目錄為準 |

---

## 跨文件的硬性規則

這些規則寫在某一份文件裡，但**違反它們的後果會出現在別的地方**，而且大多不會報錯。實作前逐條看過。

| # | 規則 | 出處 | 違反的後果 |
|---|---|---|---|
| 1 | **部位推導一律用 `traded_on <= D` 不等式聚合，不得 join 日曆** | `performance.md` | 實測靜默吃掉 1.6% 的交易，**且污染是永久的**（該標的股數從那天起永遠少一截） |
| 2 | **不建 `portfolio_snapshot`，連快取形式都不建** | `performance.md` §1.4 | 歷史被補登改寫時，實測 57% 的曲線靜默地錯 |
| 3 | **`LISTEN` 一律走 direct connection，不得走 pooled endpoint** | `realtime-quotes.md` §3 | 報價扇出在沒有任何錯誤訊息的情況下靜止 |
| 4 | **任何未登入即可存取的路由都不得包含即時報價** | `tech-stack.md` §8 | 法遵（TWSE 管理辦法：券商行情不得轉供第三人） |
| 5 | **Discord 通知內文不得含任何金額與百分比**（報酬率最容易漏） | `alerts.md` | 違反 Discord Developer Policy 第 16 條 |
| 6 | **`src/core/` 不得出現任何 provider 專屬命名或字面量 `5`**（額度是 provider 屬性） | `tech-stack.md` §4、`realtime-quotes.md` §2 | 換行情源時要改的不只是設定 |
| 7 | **費率一律不得硬編碼** | `tech-stack.md`、[#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6) | 三個落日條款，最近的一個 2026-12-31 到期 |
| 8 | **不在 `transaction` 加 `status` 欄** | `data-model.md`、`transaction-input.md` | 漏寫 `WHERE status` 不會有任何錯誤訊息 |
| 9 | **所有依 `transaction.type` 分支的程式碼必須是窮舉式的** | `corporate-actions.md` §1.6 | 漏處理 `SPLIT` 是同一種靜默失效 |
| 10 | **所有排程必須冪等，且語意是「回補到最新交易日」而非「抓今天」** | `deployment.md` §4.1 | 這台電腦會關機，漏跑是常態不是例外 |
| 11 | **盤後排程必須自我斷言「回傳日期 == 預期交易日」** | `deployment.md` §5.3 | 走錯端點會每天成功、資料永遠晚一天、圖上看不出來 |
| 12 | **Quote 的量必須是當日累積量，不是單筆量** | `realtime-quotes.md` | 用單筆量會讓 conflation 默默弄丟成交量 |
| 13 | **退避計數必須穩定 60 秒才重置** | `realtime-quotes.md` | 連上即重置會讓 flapping 時退避完全失效——那正是導致帳號停權的路徑 |
| 14 | **`pg_dump` 的輸出是個人財務資訊，不得進 repo 或任何公開位置** | `deployment.md` §3.4 | 本 repo 為 public |

---

## 「錯的時候有沒有錯誤訊息？」

這個問題在整張地圖上被問了幾十次，答案幾乎都是**沒有**。三份文件各有一個集中列表，實作時當檢查清單用：

- [`performance.md`](./performance.md) **§8「七個會靜默出錯的地方」** 與 **§8A「十一條必須寫成測試的不變量」**
- [`deployment.md`](./deployment.md) **§12「會靜默出錯的地方」**（十條）
- [`corporate-actions.md`](./corporate-actions.md) **§8「必須寫成測試的條目」**（十二條）

---

## 暫時性妥協與解除條件

以下限制**不是技術判斷的結果**，是當前的外部條件（免費層額度、未開通的帳號、單人自用的部署形狀）造成的。每一條都有明確的解除條件——**解除條件成立時要回頭改，不要讓它們變成永久的架構**。

| 文件 | 妥協的來源 |
|---|---|
| [`realtime-quotes.md`](./realtime-quotes.md) §10 | 六條因 **Fugle 免費層**（5 個「標的×頻道」配對、1 條帳號級連線）而非技術判斷造成的限制。解除條件是開通 [#8](https://github.com/NTUyu016/stock-analytic-platform/issues/8)（永豐 Shioaji） |
| [`alerts.md`](./alerts.md) | 訂閱頻道與即時警示範圍的限制，同上；另有一道未關的法遵問題（FinMind 資料再散布授權） |
| [`performance.md`](./performance.md) | 資料源與計算範圍的限制 |
| [`deployment.md`](./deployment.md) §11 | 七條因 **v1 跑在本機**造成的限制，含「電腦沒開就沒有即時警示」與「只有 tailnet 內看得到」。§10.1 列了四個解除條件 |

### 兩道會同時擋在「上架給他人使用」路上的法遵牆

**這不在本地圖範圍內**（issue #1 明寫需要獨立一張圖），但實作時不要做出讓它們更難解的決定：

1. **券商行情不得轉供第三人**（TWSE《交易資訊使用管理辦法》）。合法路徑只剩三條：自行簽約成為資訊廠商（傳輸授權 6 萬/月起）、只呈現延遲 20 分鐘以上的資料、或只呈現衍生結論不呈現原始行情。
2. **FinMind 的資料再散布授權未明示**（套件本身 Apache-2.0，資料不是）。`daily_close`（個股 OHLCV）、除權息參考價、分割與減資**唯一的乾淨來源都是它**。自用無虞。

---

## 這份規格的形狀是怎麼決定的（[#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18)）

| 待決事項 | 決定 | 理由 |
|---|---|---|
| **單一 `SPEC.md` 還是多份？** | **多份，本文件是索引** | 十一份規格共約 5,000 行，單檔沒有人（包括 agent）能有效導覽。更關鍵的是**一份文件對一張票**——`git log` 與 issue 討論因此可以逐份追溯到「當初為什麼這樣決定」，合成一份會把這條線切斷 |
| **顆粒度要多細？** | **細到能讓沒有上下文的 agent 直接實作** | 這是 issue #1 對終點的原始定義。判準不是行數，是下一欄的驗收 |
| **要不要一併切成實作票？** | **要**，見 [`implementation-plan.md`](./implementation-plan.md) | 切票會逼出規格的缺口——「這張票的驗收條件是什麼」答不出來的地方，就是規格沒寫清楚的地方。這是免費的一次自我檢查 |
| **上架的升級路徑寫多深？** | **只寫到「哪些決定日後會痛」**，不寫方案 | issue #1 已把「上架給他人使用」列為需要獨立一張圖的區域。兩道法遵牆（見上）足以決定產品形態，在這裡預先設計等於猜 |
| **怎麼驗收「規格夠完整」？** | **找一個乾淨 session 讀規格，看它問出哪些問題** | 問得出來的就是缺口。這比作者自己檢查有效，因為作者知道太多沒寫進去的東西 |

> **關於「支援材料」的下場**：`docs/briefing/` 在對應的票定案後就失去作用，但**保留不刪**。理由是它們記著「被淘汰的選項輸在哪」與「哪些事實當時查不到」——而本專案已經發生過兩次「後來的查證推翻了當初的理由，但結論仍然成立」（#20 的減資、#17 的 Render 750 小時）。**刪掉簡報會讓那類複查失去比對基準。**

## 這份規格沒有回答的事

誠實列出，避免實作者以為自己漏讀了：

| 項目 | 狀態 |
|---|---|
| 盤後排程的最早可執行時點 | 只有一個樣本（T+13.75h），保守取 22:00。需在 15:00/17:00/19:00/22:00 分別取樣 |
| 手續費與證交稅元以下的進位規則 | **已解**（[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19) 用真實對帳單反推：皆為無條件捨去，零誤差） |
| `TaiwanStockSplitPrice` 每日更新的時點 | 未做跨日觀測。決定偵測延遲是 T+0 還是 T+1 |
| 分割的提前示警 | **做不到**。官方預告表不在開放授權側，且 FinMind 無對應 dataset |
| 一般個股的「換發基準日」 | 不在任何可程式化端點上。`corporate-actions.md` §4.6 已用另一個定義繞開 |
| 美股與加密貨幣的分析頁 | **v1 不做**（使用者目前無對應持股，不為不存在的資料先設計架構） |
| 券商 API 自動同步持股、回測與選股器、行動端、AI 分析 | issue #1「Not yet specified」，需另開圖 |
