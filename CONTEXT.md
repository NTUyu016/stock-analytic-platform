# 台股持股儀表板

一個以台股為主、美股為輔的個人持股儀表板網站。使用者手動記錄自己的交易，系統據以推導部位、計算損益、呈現即時行情與歷史績效。

本檔案是**詞彙表**，只定義名詞是什麼，不記錄實作方式。資料表設計見 [`docs/spec/data-model.md`](./docs/spec/data-model.md)。

## Language

### 使用者與身分

**User（使用者）**：
擁有 Portfolio、Transaction 與 Alert 的那個人。v1 只會有一位，但所有個人資料自始以 `user_id` 歸屬於他。
_Avoid_: Account, 帳號, Owner

**Identity（身分）**：
User 用來登入的其中一個外部帳號，由「provider + 該 provider 給的穩定識別碼」唯一確定。**一個 User 可以有多個 Identity**（Google 與 GitHub 是兩個 Identity，同一個人）。這是備援登入成立的前提。
_Avoid_: Login, 帳號, Credential

**Provider（身分提供者）**：
簽發 Identity 的外部服務，如 `google`、`github`。與 Provider Symbol 的「資料源」是不同概念，勿混用。
_Avoid_: IdP, 登入方式

**Session（工作階段）**：
一次登入的存續狀態，落地儲存因此**可被撤銷**。與 Identity 的差別：Identity 是「你是誰」（長期不變），Session 是「你現在登入著」（隨時可作廢）。
_Avoid_: Token, Cookie, 登入狀態

### 標的與市場

**Instrument（標的）**：
一個可被持有與報價的交易對象，由「市場 + 代號」唯一確定。台積電的台股普通股與其美股 ADR 是**兩個不同的 Instrument**。
_Avoid_: Ticker, Symbol, 股票, 商品

**Symbol（代號）**：
Instrument 在其所屬市場中的對外識別字串，如 `2330`、`NVDA`、`BTC-USD`。單獨的 Symbol 不足以識別一個 Instrument，必須搭配 Market。
_Avoid_: Ticker, Code

**Market（市場）**：
Instrument 掛牌交易的場所，決定其幣別、交易時段與交易日曆。目前有 `TWSE`（上市）、`TPEX`（上櫃）、`US`、`CRYPTO`。
_Avoid_: Exchange, 交易所, 板別

**Provider Symbol（資料源代號）**：
同一個 Instrument 在某個外部資料源中的代號。台積電在 yfinance 是 `2330.TW`、在 Shioaji 是 `2330`。這是資料源的細節，不是 Instrument 的身分。
_Avoid_: External ID, Vendor code

### 持有與交易

**Portfolio（投資組合）**：
一組交易紀錄的歸屬單位，代表使用者心中一個獨立管理的帳本（如「長期存股」「短線」）。同一支 Instrument 出現在不同 Portfolio 時，是兩個各自獨立計算成本的 Position。
_Avoid_: Account, 帳戶, 帳號, Watchlist

**Transaction（交易紀錄）**：
一筆已經發生、會改變持有狀態的事件。是本系統**唯一的事實來源** —— 部位、成本、損益全都由它推導而來，不另行儲存。
_Avoid_: Trade, Order, Deal, 委託

**Transaction Type（交易類型）**：
Transaction 的種類，決定它如何影響股數與成本：`BUY`、`SELL`、`CASH_DIVIDEND`（現金股利）、`STOCK_DIVIDEND`（股票股利）、`ADJUSTMENT`（通用調整）。
_Avoid_: Action, Side, 買賣別

**Adjustment（通用調整）**：
一種 Transaction Type，直接指定股數與成本的增減並附註原因，用於系統未內建專屬邏輯的公司行動（減資、換股、合併）。它是刻意保留的逃生門，不是資料錯誤的修補工具。
_Avoid_: Correction, Fix, 修正

**Position（部位）**：
在某個時間點，某個 Portfolio 中某支 Instrument 的持有狀態（股數、成本基礎、未實現損益）。Position 是**推導值**，不儲存。
_Avoid_: Holding, 庫存, 持股

**Cost Basis（成本基礎）**：
Position 中每股的取得成本，以**加權平均**計算，並計入手續費與交易稅。與券商對帳單上的「均價」對應。
**現金股利不沖減它**，股票股利則因總成本不變、股數增加而稀釋它（[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16)）。
⚠️ **注意詞彙衝突**：國泰證券對帳單有一欄叫「成本」，那是**單筆成交總額**（股數 × 成交價），與本詞完全無關。匯入時它映射為成交金額，不是 Cost Basis。
_Avoid_: Average price, 成本價, 買進價

**Realized P&L（已實現損益）**：
賣出時，賣出淨額與所賣股數之成本基礎的差額。已離開持有狀態，不再隨市價變動。
**只含價差，不含股利** —— 股利是 Dividend Income，兩者刻意分開。
_Avoid_: Profit, 獲利, 實現利益

**Dividend Income（股利收益）**：
現金股利的**實收淨額**（宣告總額扣除配息當下的補充保費與就源扣繳）。它與 Cost Basis 無關、與 Realized P&L 並列，是 Total Return 的第三個組成。
_Avoid_: 股息, 配息, 股利（單講「股利」時指的是事件，不是這個金額）

**Total Return（總報酬）**：
`Realized P&L ＋ Dividend Income ＋ Unrealized P&L`。涵蓋**全部歷史**，包含已經清倉出場的 Instrument —— 只算當前持股會讓賠錢出場的部位從分母消失。首頁的主數字就是它，且**以絕對金額呈現**。
_Avoid_: 總損益, 累積報酬, 績效

### 績效指標

**Benchmark（比較基準）**：
用來回答「我自己選股有沒有比買指數好」的對照序列。因使用者的績效含股利，基準也**必須含息**，否則等於每年系統性地送自己 3–4 個百分點。
_Avoid_: 大盤, 指數, Index

**TWR（時間加權報酬率）**：
逐日報酬鏈式相乘、**排除資金進出影響**的報酬率。用於與 Benchmark 比較 —— 指數沒有資金進出，只有排除了進出的指標才與它同構。
_Avoid_: 累積報酬率, 幾何報酬率

**XIRR（金額加權報酬率）**：
使全部現金流折現後等於現值的年化利率，**把投入的時點與金額都算進去**，回答「我的錢實際年化賺了多少」。無解析解，只能迭代求根，因此**使用者無法自行驗算** —— 呈現它的前提是同時提供現金流明細。
_Avoid_: IRR, 年化報酬率（單講「年化」時未指定演算法，容易誤指 CAGR）

**External Cash Flow（外部現金流）**：
錢進出**投資組合**的事件：買進為流入、賣出與股利為流出。TWR 要把它扣掉，XIRR 要把它當輸入。
⚠️ 交割帳戶裡的閒置現金**不是**外部現金流 —— 它沒有被投資，不屬於投資組合。
_Avoid_: 資金流, 現金流（未限定「外部」時語意過寬）

**Unrealized P&L（未實現損益）**：
Position 目前市值與其成本基礎總額的差額。隨市價逐筆變動。
_Avoid_: Paper gain, 帳面損益, 浮動損益

### 輸入與對帳

**Import（匯入）**：
把一份外部檔案（券商對帳單或中性格式 CSV）轉成 Transaction 的一次操作。**具原子性——全成功或全不進**，不存在進了一半的狀態。
_Avoid_: Upload, 上傳, 同步

**External Ref（來源自然鍵）**：
一筆 Transaction 在其匯入來源中的唯一識別，由「券商 + 成交日 + 委託書號」組成。它讓重複匯入同一份檔案不會產生重複列。手動輸入的 Transaction 沒有 External Ref。
_Avoid_: Import ID, 外部 ID, 交易編號

**Pending Action（待確認項）**：
系統推測出、但尚未經使用者確認的一筆變動，如自動偵測到的除權息。**它不是 Transaction** —— 只有確認之後才會成為 Transaction。這個區分是刻意的：Transaction 表裡每一列都必須是事實。
_Avoid_: Draft, 草稿, 暫存交易

**Reconciliation（對帳）**：
拿券商的庫存股數與系統推導出的 Position 比對的一次事件，結果落地為稽核紀錄。**只比股數不比均價**，因為股數無歧義而均價有定義分歧。對帳結果不是事實來源，只是一次比對的紀錄。
_Avoid_: Sync, 校驗, 盤點

### 價格

**Quote（報價）**：
Instrument 在盤中的最新成交價與相關即時欄位。**具時效性且不落地** —— 只存在於記憶體與快取中，重啟即消失。
_Avoid_: Price, Tick, 即時價

**Daily Close（每日收盤價）**：
Instrument 在某個交易日的**日 OHLCV**（開高低收與成交量），落地儲存。歷史資產曲線與績效計算的唯一價格來源，也是追蹤停損峰值與成交量異常的唯一歷史來源。名稱雖為「收盤價」，內容不只收盤價。
_Avoid_: Close price, EOD, 歷史價, OHLC

**Exchange Rate（匯率）**：
某一日某個幣別對台幣的換算率，落地儲存。歷史績效一律使用**當日**匯率，不使用當前匯率回溯換算。
_Avoid_: FX, 匯價

**Base Currency（基準幣別）**：
所有跨幣別加總與呈現時換算的目標幣別，固定為台幣（TWD）。Transaction 與 Cost Basis 一律以**原幣別**儲存，只在顯示層換算。
_Avoid_: Display currency, 主幣別

### 警示

**Alert（警示）**：
使用者定義的一條條件，當 Quote 滿足它時觸發通知。
_Avoid_: Notification, Trigger, 提醒

**Notification（通知）**：
Alert 觸發後實際送出的一則訊息。一個 Alert 可對應多則 Notification（重複觸發）與多個送達管道。
_Avoid_: Alert, Message, 推播

**Armed（武裝）**：
Alert 目前處於「條件一旦成立就會觸發」的狀態。觸發後轉為解除，直到價格回到門檻另一側（含緩衝）才重新武裝。武裝與否是 Alert 的**運行狀態**，不是使用者設定 —— 使用者設的是 `is_enabled`。
_Avoid_: Active, Enabled, 啟用中, 監控中

**Peak（峰值）**：
追蹤停損所記的「持有以來最高價」，自建倉日起算、清倉即重置、除權息日按參考價比率下調。它是**可重建的快取**，不是事實 —— 隨時可從 Transaction 與 Daily Close 重算。
_Avoid_: High, Max, 最高點, 歷史高

### 個股分析

**Analysis Dimension（分析維度）**：
個股分析頁裡，針對某個面向（如財報意外、基本面）產生的一組分數與說明文字，是 Analysis Result 的組成單位。v1 有六個：財報意外、基本面、動能、分析師評等、大盤環境、產業比較（[#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)）。
_Avoid_: Signal, Factor, 指標（單講「指標」時容易與券商慣用的技術指標混淆）

**Rating（評等）**：
一次分析結果彙總後呈現的五級分類：strong buy / buy / hold / sell / strong sell。與 yfinance 提供的「分析師共識評等」字面相同但**來源不同**——畫面上用不同措辭區分兩者，本站中文五級固定為「**大幅偏多／偏多／中性／偏空／大幅偏空**」，分析師共識維持原文英文，避免使用者誤讀成同一件事。
_Avoid_: Recommendation, Grade, 建議, 級距（同一件事不要兩種講法）；不要用 Score／「分數」指稱 Rating 本身——「分數」是各 Analysis Dimension 得分的標準用詞（見 Analysis Result），Rating 是彙總後的五級分類，兩者不同層級

**Analysis Result（分析結果）**：
一次個股分析的完整輸出：各 Analysis Dimension 的分數與說明、彙總後的 Rating、下修原因（若有）。**每一維各自帶時間戳**（哪個時間點的資料算出來的），不是只有一個籠統的整包時間。v1 每次開頁即時算，**不落地快取**——具時效性，不是事實來源。
_Avoid_: Signal（舊 stock-analysis skill 用 `Signal` dataclass 同時裝 `recommendation`／`confidence`／`final_score` 三個欄位，本專案刻意把這些概念拆開，不要把同樣的混用搬進來）

**Coverage（維度覆蓋率）**：
一次 Analysis Result 實際用上了幾個 Analysis Dimension（滿分為 Analysis Dimension 總數）。取代舊 skill 的 `confidence`——舊 skill 的 `confidence` 其實就是最終分數的絕對值，跟 Rating 是同一個數字重複呈現兩次，本專案不用這個詞。若 Coverage 過低，直接不給 Rating 並說明缺什麼資料，不硬湊結論。
_Avoid_: Confidence, 信心度
