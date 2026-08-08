# 決策簡報：issue #20「公司行動（分割／減資／換股）的型別與偵測」

> 產出日期：2026-08-08
> 用途：**上桌前準備**。本文只盤點事實與選項，**不做任何決策**——決策由使用者在 grilling session 親自做。
> 引用規則：所有事實附出處（檔案＋章節／行號、或 issue 編號）。查不到者一律標「**未能查證，需人工確認**」。
> 用詞依 [`CONTEXT.md`](../../CONTEXT.md)：Transaction（交易紀錄）、Transaction Type（交易類型）、Adjustment（通用調整）、Pending Action（待確認項）、Peak（峰值）。

**本票的特殊之處**：issue #20 body 自己已經把「已知事實」整理成一張表，來源是 [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 定案時的查證，並明寫「阻塞：無」。本文**不重新查證那張表**，只做兩件事：（1）依本專案簡報格式重新組織成待決事項逐項展開；（2）核對現行 `docs/spec/` 內容，標出事實表與規格現況之間的落差（見各節「⚠️」標記）。

---

## 0. 開場前必須放在桌上的既有約束

| # | 約束 | 出處 |
|---|---|---|
| 1 | **`Adjustment` 是刻意保留的逃生門，不是資料錯誤的修補工具**，用於「系統未內建專屬邏輯的公司行動（減資、換股、合併）」——定義**沒有列「分割」** | `CONTEXT.md` 第 59–61 行 |
| 2 | **`transaction.type` 現況列舉**：`BUY` / `SELL` / `CASH_DIVIDEND` / `STOCK_DIVIDEND` / `ADJUSTMENT`，**沒有 `SPLIT`** | `data-model.md` 第 102 行 |
| 3 | **`ADJUSTMENT` 的既有語意**：`quantity` 與 `cash_amount` 可正可負，`note` 必填 | `data-model.md` 第 122 行 |
| 4 | **#16 已定案的最小要求**：「盤後排程必須納入分割偵測並產生 `pending_action`」——這件事**已經決定**，不在 #20 的待決範圍內；#20 要決的是型別、峰值調整規則、減資換股是否比照，以及這個既定方向下的參數（範圍／頻率／未確認風險窗口） | `performance.md` §8.6 第 807 行；§11 第 866–877 行 |
| 5 | **`pending_action` 存在的唯一理由，是不要在 `transaction` 加 `status`**——這與 [#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) 對 `user_id` 的警告同形：漏寫 `WHERE status = 'confirmed'` 不會有任何錯誤訊息 | `data-model.md` 第 245 行 |
| 6 | **資產曲線用「未還原收盤價 × 當時實際股數」在分割面前是對的**：分割當天股數變 4 倍、股價變 1/4，乘積不變——這件事已經定案，`daily_close` 不做任何股價還原 | `performance.md` §8.6 第 777–781 行 |
| 7 | **費率一律不得硬編碼**（可能被引用於「偵測門檻」等參數，但選不選、怎麼選仍是使用者的事） | [#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6)；`tech-stack.md` 第 279 行 |

---

## 待決事項 1：`transaction.type` 要不要新增 `SPLIT`？

### 1.1 已知事實

**（a）issue body 事實表已查證的部分**（原樣引用，出處已核對無誤）：
- FinMind `TaiwanStockSplitPrice` 提供 0050 於 **2025-06-18** 一拆四，分割前參考價 **188.65**、分割後 **47.16**（比例 4.0002 → 1 拆 4）——`tw-benchmark-and-fx-sources.md` §B.4 第 290–297 行、`performance.md` §8.6 第 769 行。
- 忽略分割的代價：CAGR 從 **14.609% → 7.934%**（6.7 pp/年），十年累積 3.91 倍 vs 2.15 倍——同上 §B.4 第 314 行、`performance.md` 第 793 行。
- **不會有任何錯誤訊息**：47.57 是合法價格，`numeric(20,8)` 收得下——同上。
- 可偵測性佳：全 5,684 列中，相鄰兩日收盤比值落在 `[0.85, 1.18]` 之外的只有這一天（0.2522）——`tw-benchmark-and-fx-sources.md` 第 313 行、`performance.md` 第 795 行。

**（b）`ADJUSTMENT` 的既有語意與分割的落差**：`ADJUSTMENT` 只有 `quantity`／`cash_amount`（可正可負）＋ `note`（必填），**沒有專屬欄位存分割比例**（`data-model.md` 第 122 行）。若走這條路，分割比例（4.0002）只能寫在 `note` 自由文字裡，或靠「調整前後股數差」反推——issue body 已指出這點：「具名型別的好處：分割比率是第一類值，不需要從股數變化量反推」。

**（c）⚠️ 落差發現：`transaction.type` 目前沒有文件化的 `CHECK` 約束**。issue body 選項盤點的措辭是「逃生門的好處：綱要不動、`CHECK` 列舉不用改」，但核對 `data-model.md` 發現：只有 `alert.rule_type` 明文寫著「六種具名類型之一，`CHECK` 列舉」（第 193 行）；`transaction.type` 那一列**只在說明欄列出五個值，沒有寫 `CHECK`**（第 102 行）。**這點其實不需要「人工確認」——`git ls-files` 確認本 repo 除 `docs/` 外只有 `.gitignore`／`CONTEXT.md`，沒有任何 DDL 或程式碼，schema 尚未實作，所以「現況沒有 `CHECK`」是確定的事實，不是查不到答案。** 正確的說法是：規格文件本身未規定 `transaction.type` 要有 `CHECK`（`alert.rule_type` 有明文規定，`transaction.type` 沒有），這是規格層級的不一致，而非「文件遺漏了已存在的約束」。因此「選具名型別 vs 逃生門」在 schema 變更成本上的差距，確實會比 issue body 描述的更小——新增 `SPLIT` 值時要不要順手補一條 `CHECK`，本身也是待決 1 的一個附帶子問題。

**（d）`performance.md` §8A 的不變量 #10** 要求「分割日前後的該檔市值連續（股數 × 未還原價）」，這條測試不論走 `SPLIT` 或 `ADJUSTMENT` 都必須滿足——型別選擇不影響這條不變量本身，但影響**測試要 `WHERE type = ?` 哪個值**。

### 1.2 選項盤點

| 選項 | 內容 | 代價 | 「做錯日後會很痛」的地方 |
|---|---|---|---|
| **A. 新增具名 `SPLIT`** | `transaction.type` 增加一個列舉值，比例可設計成第一類值（例如另存 `note` 之外的結構化欄位，或直接由 `quantity` 前後差推導） | 依（c）現況沒有 `CHECK` 約束，這裡不用改既有約束，但**若要比照 `alert.rule_type` 補上明文 `CHECK`**（值得順手做，理由見（c）），實作時要記得加；`CONTEXT.md` 的 Transaction Type 與 Adjustment 兩條詞彙定義需要同步修訂（依 issue #1 的規矩：新名詞要同步補進 `CONTEXT.md`） | 若日後待決 2（`alert_state.peak_price` 分割調整）需要程式化讀取分割比例，具名型別能讓比例直接可查；若沒設計專屬欄位存比例，這個好處就落空 |
| **B. 繼續走 `ADJUSTMENT` 逃生門** | 不動綱要，分割記在 `note`，`quantity` 改變量即分割效果 | `CONTEXT.md` 明訂 `ADJUSTMENT` 是「不是資料錯誤的修補工具」，而分割是**已知、可偵測、會反覆發生**的事件（issue body 語），長期塞在逃生門裡是語意上的拉扯 | **與待決 2 直接連鎖**：若走 B，分割比例不是 `transaction` 的結構化欄位，待決 2 若要自動調整 `peak_price`，比例必須另外從 `pending_action.proposed`（確認前）或 `daily_close` 比值（確認後，反推）取得，不能直接查 `transaction` |

**與型別無關、但兩個選項都要面對的一筆帳**：#19 拒絕在 `transaction` 加 `status` 欄的理由是「漏寫 `WHERE` 不報錯」（`data-model.md` 第 245 行、[#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10)）。若選 A 且日後有查詢邏輯遺漏處理 `type = 'SPLIT'`（例如某段程式碼只枚舉了 `BUY`/`SELL`），會是同一形狀的靜默失效——這不是否定選 A，而是選 A 之後要記得把 `SPLIT` 補進所有型別枚舉的地方。

### 1.3 仍未查證的空白

1. ~~`transaction.type` 現況是否真的有資料庫層 `CHECK` 約束~~——**已於（c）解掉：確定沒有**（本 repo 尚無任何 DDL／程式碼實作，不是查不到答案）。真正待決的是「新增 `SPLIT` 時要不要順手比照 `alert.rule_type` 補一條明文 `CHECK`」，這是待決 1 本身的附帶子問題，不是查證缺口。
2. 若新增 `SPLIT`，是否也要同步修訂 `CONTEXT.md` 的 Transaction Type 與 Adjustment 兩條定義——這本身是待決 1 的下游結果，不在本文預先判斷。

---

## 待決事項 2：`alert_state.peak_price` 的分割調整規則

### 2.1 已知事實

**（a）`alert_state` 現況 schema**：`peak_price`（僅 `TRAILING_STOP`）、`peak_since`（建倉日），且明訂「**峰值可重建，且必須有重建路徑**」——`data-model.md` 第 202–212 行、`alerts.md` 第 287–289 行。

**（b）#15 現行的除權息調整規則**（issue body 已引用，核對無誤）：峰值必須在除權息日按 `reference_price / before_price` 比率下調，觸發源是 FinMind `TaiwanStockDividendResult`（含 `before_price`／`after_price`／`reference_price`）——`alerts.md` 第 261–275 行。實測案例：2330 於 2026-06-11 除息，`close` 從 2255 掉到 2250，未還原則峰值會「墊在一個加總了歷史股息的位置」，最終「長期黏在已觸發狀態，且不會有任何錯誤訊息」（同上第 265–271 行）。

**（c）#15 自己已標記分割走不到這條路徑**（issue body 已引用，核對無誤）：分割在 `TaiwanStockSplitPrice`，是另一個 dataset；`alerts.md` 已於 2026-08-07（由 #16）補上這段缺口說明，**明寫「本規格暫不修改」，型別與調整規則另開票**——即本票——處理（`alerts.md` 第 277–285 行）。

**（d）✅ 2026-08-08 直接呼叫 FinMind API 覆核，原「落差發現」的方向有誤，現已釐清**：本文初版曾寫「`TaiwanStockSplitPrice` 比 `TaiwanStockDividendResult` 少一個 `reference_price` 欄位」，但這個說法本身依據的是兩份研究文件互相矛盾的欄位清單（`tw-fundamental-chip-data-sources.md` §3.5 說 `TaiwanStockDividendResult` 有 `reference_price`；`tw-benchmark-and-fx-sources.md` 第 265 行的欄位列舉只寫了三欄，未列 `reference_price`）。2026-08-08 直接呼叫 `GET https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockDividendResult&data_id=0050` 覆核（無 token，公開端點），結果：
- `TaiwanStockDividendResult`（0050，2003-01-01~2026-08-08，**32 列**）**確實含 `reference_price` 欄位**，且**32/32 列 `reference_price` 與 `after_price` 數值完全相等**（例：2025-01-17 一列 `after_price=195.35`、`reference_price=195.35`；2025-07-21 一列 `after_price=51.09`、`reference_price=51.09`）。
- `TaiwanStockSplitPrice`（0050，同期間，**1 列**）欄位為 `date`／`stock_id`／`type`／`before_price`／`after_price`／`max_price`／`min_price`／`open_price`，**確實沒有 `reference_price` 欄位**——`tw-benchmark-and-fx-sources.md` 第 265 行原查證正確。

**結論**：真正的落差不在「分割少一欄」，而是兩份研究文件對 `TaiwanStockDividendResult` 欄位清單本身互相矛盾，`tw-benchmark-and-fx-sources.md` 那份漏列了 `reference_price`。但由於 `reference_price` 在 0050 全歷史（32/32）與 `after_price` 數值相等，**#15 公式 `reference_price/before_price` 與待決事項 2 選項 A 提議的 `after_price/before_price` 在 0050 的實測樣本上是等價的**——這代表選項 A「套用 #15 既有公式」在語意對等這一點上，已有實測支持，不再是純推論。

### 2.2 選項盤點

| 選項 | 內容 | 代價／風險 |
|---|---|---|
| **A. 比照 #15 公式，改用 `after_price/before_price` 當調整比率** | 複用「除權息日調整」的既有程式路徑，只換觸發源（`TaiwanStockSplitPrice`）與比率欄位 | （d）已用 0050 全歷史（32/32 列）實測驗證 `reference_price == after_price`，語意對等有實測支持，非未查證的假設；剩餘風險降為：實測樣本僅 0050 一檔，尚未跨標的交叉驗證是否恆成立 |
| **B. 峰值調整方式綁定待決 1 的型別選擇** | 若走具名 `SPLIT`（待決 1 選項 A）且比例是結構化欄位，調整邏輯可直接讀 `transaction`；若走 `ADJUSTMENT`（選項 B），比例需另從 `pending_action.proposed` 或 `daily_close` 比值反推 | 這是待決 1 選項 B 代價欄已指出的連鎖——兩票放在一起看才完整 |
| **C. 不自動調整，偵測到分割時只在 `pending_action` 附帶「峰值需人工複核」提示** | 成本最低，不碰計算邏輯 | 違反 `alerts.md` 已明訂的「峰值可重建，且必須有重建路徑」精神——若分割不納入重建公式，這條路徑就不完整，且回到 #15 當初列出的「永久黏在已觸發」問題 |

**「做錯日後會很痛」**：這條路徑的失效模式（峰值錯位、越久越偏、規則永久黏在已觸發）**不會有任何錯誤訊息**——這是 #15 已經用真實數據驗證過的既定事實，不是推測。若調整公式本身寫錯（例如誤用未經驗證語意對等的欄位），代價與「完全不調整」相同，但看起來像是「已經修好了」，複查成本更高。

### 2.3 仍未查證的空白

1. ~~`TaiwanStockSplitPrice` 的 `after_price/before_price` 比率，其語意是否與 #15 公式所用的 `reference_price/before_price` 比率一致~~ **已於 2026-08-08 用 0050 全歷史（32/32 列）實測確認 `reference_price == after_price`，見（d）。剩餘缺口縮小為：只驗證過 0050 一檔，未跨標的交叉驗證。**
2. `TaiwanStockSplitPrice` 的 `date` 欄位，其語意（生效日／基準日）是否與 #15 除權息規則所指的「除權息日」在觸發時序上對齊——本文未逐筆核對，**未能查證**。

---

## 待決事項 3：減資與換股是否共用同一套機制？

### 3.1 已知事實

**（a）#19 現況決定**（issue body 已引用，核對無誤）：除權息走自動偵測＋`pending_action`；**減資、換股、合併走手動 `ADJUSTMENT`**——`transaction-input.md` §8 第 271–276 行。

**（b）#19 判定「只有除權息值得自動化」的三條件**（缺一即否）：頻率高、有官方資料源、不做會靜默出錯。減資與換股被判定「一年難得一次、沒有乾淨的官方 feed（[#3](https://github.com/NTUyu016/stock-analytic-platform/issues/3) 已將 MOPS 列為不建議程式化存取）」——`transaction-input.md` 第 278–286 行。

**（c）本文查證範圍內，未見減資／換股的可程式化資料源盤點**。#16／#3 相關研究只查證了分割專用的 `TaiwanStockSplitPrice`；減資與換股的資料源狀況，issue body 也沒有提供新事實，只是提出「要不要共用機制」這個問題。

### 3.2 選項盤點

| 選項 | 內容 | 代價／風險 |
|---|---|---|
| **A. 三者共用一套新機制**（型別與偵測都統一） | 一致性最高 | #19 否決減資／換股自動化的三條件判準（沒有乾淨官方 feed）**沒有被 #16 的研究推翻**——除非能找到減資／換股的可程式化資料源，否則「自動偵測」這一半做不到，只能做到「型別」這一半（改用具名值，但仍手動輸入） |
| **B. 只有分割獨立處理，減資／換股維持 #19 現狀（手動 `ADJUSTMENT`）** | 不需重新論證 #19 已做過的判斷 | 三種公司行動在型別系統裡待遇不一致；日後查「這個部位所有的非交易事件」需要同時查 `type = 'SPLIT'` 與 `type = 'ADJUSTMENT'` 加 `note` 關鍵字比對 |
| **C. 型別層面統一，偵測層面不統一**（例如都歸在同一個具名值，但只有分割有自動偵測） | 資料模型一致，重建／查詢邏輯只需認一種 type | 若三者共用型別但意義不同（有無比例欄位、有無自動偵測），需要額外欄位區分子類——這是否與 #19 否決 `transaction.status` 的理由同形（漏寫子類判斷不報錯），需要在 grilling 時具體界定，本文不代為判斷 |

### 3.3 仍未查證的空白

1. 減資與換股是否存在可程式化取得的官方或 FinMind 資料源——**未能查證，需人工確認**（或需另開研究票）。
2. #19「MOPS 不建議程式化存取」的判斷所依據的 [#3](https://github.com/NTUyu016/stock-analytic-platform/issues/3) 研究時效性——本文沿用既有結論引用，未重新查證。

---

## 待決事項 4：偵測的觸發與確認流程

### 4.1 已知事實

**（a）已定案、不在待決範圍內的部分**：「盤後排程必須納入分割偵測並產生 `pending_action`」——`performance.md` §8.6 第 807 行。本待決事項要決的是這個既定方向下的**參數**：掃描範圍、頻率、使用者未確認時的處理。

**（b）除權息偵測的既有先例**（可作參照，非分割的既定答案）：
- 排程掛載：「排程搭在 [#9](https://github.com/NTUyu016/stock-analytic-platform/issues/9) 既有的『每日盤後追一筆 `daily_close`』上，不新增排程元件」——`transaction-input.md` 第 297 行。
- 掃描範圍：「盤後排程比對**持有標的**與官方預告」——`transaction-input.md` 第 275 行，即只掃持股，不掃全市場。

**（c）issue body 事實表已查證的資料源**：FinMind `TaiwanStockSplitPrice` 免費可用，含 `before_price`／`after_price`／`type`——核對 `tw-benchmark-and-fx-sources.md` 第 265、677 行，欄位列表一致，**本文追加查到還有 `date` 欄位**（同上第 265 行原文 `{"date":"2025-06-18","type":"分割",...}`）。

**（d）⚠️ 落差發現：`pending_action.effective_on` 的既有欄位註解是股利語意**。`data-model.md` 第 239 行對 `effective_on` 的說明是「**除權息基準日**」，`CONTEXT.md` 對 Pending Action 的定義舉例也只寫「如自動偵測到的除權息」（`CONTEXT.md` 第 119–121 行）。`pending_action.kind` 雖然已經有通用的 `CORPORATE_ACTION` 值（`data-model.md` 第 237 行），schema 本身不需要新增列舉即可沿用，**但欄位層級的文件措辭尚未擴充涵蓋「分割生效日」**——這是文件沒跟上，還是除權息的「基準日」與分割的「生效日」在觸發時序上本來就有語意差異，本文不下結論。

**（e）⚠️ `TaiwanStockSplitPrice` 的資料集屬性未經充分驗證**：研究文件對 0050 查到的是**單一標的 1 列**（`tw-benchmark-and-fx-sources.md` 第 265 行：「1 列」）。這只代表 0050 歷史上只分割過一次，**不足以判斷這個 dataset 本身是「僅最新快照」還是「全歷史」**——與其他官方端點（如 §2.1(a) 那類「僅最新一期」的 OpenAPI）性質可能不同，也可能相同。本文查證範圍內沒有找到對多次分割標的的交叉驗證。

**（f）既有的、非本票新增的風險**：FinMind 套件本身 Apache-2.0，但「資料本身」未見再散布授權聲明（`tw-fundamental-chip-data-sources.md` 第 292 行，列為原研究票的未能查證項）；速率限制 600 req/hr（帶 token，同上第 335 行）。這兩點因為本票的偵測機制依賴同一個 FinMind API，一併列出，但不是本票新產生的問題。

**（g）issue body 自己指出的核心風險**：「未確認的分割會讓股數持續錯 4 倍」。本文查證範圍內，**沒有找到既有規格對「`pending_action` 逾期未確認」的處理機制**（無到期日、無升級提醒）——這在除權息場景已經是懸而未決的通用缺口，分割場景只是把後果量級從「股利金額算錯」放大到「股數與市值差 4 倍」。

### 4.2 選項盤點

| 選項 | 內容 | 代價／風險 |
|---|---|---|
| **A. 掃描範圍比照除權息先例，只掃持股標的** | 與 #19 既有機制一致，成本低 | 若分割公告與生效之間時間很短（0050 案例的停止買賣期只有 5 個交易日），提前示警窗口可能不足；本文未查證分割公告的提前期一般是多久 |
| **B. 擴大掃描到自選股／曾經持有標的** | 涵蓋更廣 | 除權息本來就只掃持股（#19 既有判斷），若要擴大，目前沒有既存論證支持，需要在 grilling 現場重新論證 |
| **C1. 未確認風險不特別處理，靠既有機制事後抓** | 零額外成本 | `reconciliation`（對帳）只在使用者主動貼庫存股數時才觸發，屬於被動偵測；在那之前，總資產曲線與 `peak_price` 全部沿用錯誤股數 |
| **C2. 儀表板提供顯眼的 `pending_action` 清單／badge** | 提高可見度 | `alerts.md` §9「規則面板」目前只涵蓋 `alert` 規則的呈現，**未提及 `pending_action` 的呈現方式**——這是尚未定義的介面缺口，不只是本票的問題 |
| **C3. 分割類 `pending_action` 給比除權息更高的視覺優先權** | 對應「4 倍股數錯誤」比「除權息金額誤差」更嚴重的量級差異 | 需要 `pending_action` 表或呈現層有辦法區分嚴重度，目前 schema 沒有這個欄位（`kind` 只分 `CORPORATE_ACTION`／`IMPORT_CONFLICT`，不分子類與嚴重度） |

**「做錯日後會很痛」**：若分割未被及時確認，`reconciliation` 雖然抓得到「股數對不上」（issue body 已指出這是 #19 對帳機制「只比股數」帶來的意外紅利），但那要等使用者**主動觸發一次對帳**才會發現。在那之前，總資產曲線、Total Return、`alert_state.peak_price` 的推導全部沿用錯誤股數——且 `transaction-input.md` 已用過同一條原則（「永遠亮著的警告等同沒有警告」，第 338 行）：若 `pending_action` 清單長期堆積不處理，也會變成同樣的問題。這條原則對「要不要設計一個未確認到期機制」是相關的既有先例，但選不選仍是使用者的事。

### 4.3 仍未查證的空白

1. `TaiwanStockSplitPrice` 是「僅最新快照」還是「全歷史」資料集——本次查證只看到 0050 單一標的的 1 列證據，不足以推論資料集屬性。**未能查證，需人工確認**（需要另一檔曾多次分割的標的做交叉驗證，比照 `tw-benchmark-and-fx-sources.md` 對 TAIEX／匯率所做的交叉驗證方法）。
2. `pending_action.effective_on` 用於分割生效日時，其語意是否與既有「除權息基準日」用法完全對稱——**未能查證，需人工確認**。
3. FinMind 資料再散布授權——`tw-fundamental-chip-data-sources.md` §7 已列為未能查證項，本票沿用同一個未決風險，不重新查證。
4. `pending_action` 逾期未確認的處理機制（提醒升級、有效期、清單呈現）——本專案目前規格中未見相關決定，這個缺口同時存在於除權息場景，不是分割獨有，但 #20 若要正面回答「使用者沒確認時該怎麼辦」，可能需要一併處理這個更底層、原本該由 #19 或 #15 解決但沒解決的缺口。

---

## 建議的提問順序

```
Q1 待決 1（SPLIT 具名型別 vs ADJUSTMENT 逃生門）
   │  最先問：待決 2、3 的選項都依賴這個答案——
   │  具名型別讓分割比例成為可程式化查詢的第一類值，
   │  逃生門則把比例留在 note 自由文字或股數變化量裡。
   ▼
Q2 待決 3（減資／換股是否共用同一套機制）
   │  待決 1 的直接延伸：若 #19 否決減資換股自動化的
   │  理由（沒有乾淨資料源）依然成立，這一題至少有一半
   │  答案已經被既有研究框住，可以先問「有沒有新資料源」
   │  把選項砍掉一批。
   ▼
Q3 待決 2（alert_state.peak_price 分割調整規則）
   │  依賴 Q1 的答案決定比例如何程式化取得。§2.1(d) 原本的
   │  欄位落差疑慮已於 2026-08-08 用 0050 全歷史實測解掉
   │  （after_price/before_price 與 #15 公式的 reference_price/
   │  before_price 等價），這裡不用再當場查證，只需要拍板
   │  選項 A/B/C。
   ▼
Q4 待決 4（偵測範圍、頻率、未確認風險窗口）
   │  #16 已經定了大方向（盤後排程 + pending_action），
   │  這裡只剩參數細節，且部分子問題（pending_action 逾期
   │  未確認的處理）是全專案尚未回答過的通用缺口，
   │  可視討論時間決定是否留到下一票。
```

### 可以脫離主線、獨立處理的兩件事

| 事項 | 說明 |
|---|---|
| **`CONTEXT.md` 的新詞彙／既有詞彙修訂** | 若待決 1 選具名型別，Transaction Type 與 Adjustment 兩條定義都要修；`Pending Action` 的舉例也可能要從「如自動偵測到的除權息」擴充。這是定案後的固定動作，不影響 grilling 討論順序。 |
| **FinMind 資料再散布授權、`TaiwanStockSplitPrice` 是否為全歷史資料集** | 兩者皆為未能查證項，前者是既有的、非本票新增的風險，後者建議另外花時間查證（找一檔多次分割的標的交叉驗證），**不該在 grilling 當場拍板**。 |

---

## 附錄：本文引用的第一手來源

**GitHub**
- [issue #20](https://github.com/NTUyu016/stock-analytic-platform/issues/20)（本票，body 含事實表，0 則留言）
- issue #1（地圖）、[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16)（已定案，觸發本票）、[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)（已關，追蹤停損峰值）、[#19](https://github.com/NTUyu016/stock-analytic-platform/issues/19)（已關，交易輸入與 pending_action 骨架）、[#3](https://github.com/NTUyu016/stock-analytic-platform/issues/3)（資料源研究）、[#6](https://github.com/NTUyu016/stock-analytic-platform/issues/6)（費率不可硬編碼）、[#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10)（`user_id` 同型警告）

**專案內文件**（皆在 `C:\Users\user\claude\stock-analytic-platform`）
- `CONTEXT.md`
- `docs/spec/data-model.md`（`transaction`、`daily_close`、`alert_state`、`pending_action` 各表定義與核心原則）
- `docs/spec/alerts.md` §4（追蹤停損峰值與其分割缺口標記）
- `docs/spec/transaction-input.md` §8（公司行動處理現況）、§9（漏輸入偵測與對帳）
- `docs/spec/performance.md` §8.6（0050 分割案例的完整分析）、§8A（不變量 #10）、§11（本票的緣起）
- `docs/research/tw-benchmark-and-fx-sources.md` §B.4（0050 分割查證細節）、附錄 G（`TaiwanStockSplitPrice`／`TaiwanStockDividendResult` 欄位清單）
- `docs/research/tw-fundamental-chip-data-sources.md`（FinMind 授權與速率限制未能查證項）
