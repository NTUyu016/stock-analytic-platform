# 台股即時報價來源選型

> 對應 issue: [#2 研究：台股即時報價來源選型](https://github.com/NTUyu016/stock-analytic-platform/issues/2)（parent: #1）
> 調查日期：2026-08-01
> 撰寫語言：繁體中文（zh-tw）

---

## 0. 研究方法與時效性聲明

- 本文所有結論以**第一手來源**為準：官方 API 文件、券商官網簽署頁、交易所法規原文與收費頁、官方 GitHub repo。
- 所有費率、額度、條款皆於 **2026-08-01 當日重新查證**。凡查不到現況者，一律標註「**未能查證，需人工確認**」，不以記憶填空。
- 二手部落格僅用於「找出官方頁面在哪裡」，不作為任何結論依據。文中若出現二手來源，均已明確標示。

### 兩個必須先更正的前提

1. **「富邦 Fugle」是兩個不同的東西。**
   - **Fugle 富果**是獨立的 fintech 公司，其行情 API 由**時報資訊**與富果技術團隊共同開發（[來源](https://developer.fugle.tw/docs/data/intro/)）。
   - **富邦證券**有自己的「**新一代 API**」（Fubon Neo），是富邦證券與富果**技術合作**的產物，但屬於富邦證券的服務（[富邦金控新聞稿 2025-07-17](https://www.fubon.com/financialholdings/news/news_1250717_716035.htm)）。
   - 富果原本綁定的券商是**玉山證券**（交易 API 網域為 `fugletradingapi.esunsec.com.tw`），不是富邦。
2. **富果的「交易」側已經退場，「行情」側仍在。**
   - 玉山證券與富果的異業合作於 **2024-12-31 19:00 終止**（[富果公告 2024-10-21](https://support.fugle.tw/fugle-announcement/15335/)）。
   - **富果交易 API 於 2025/11 起不再更新**，官方要求「下單需求請轉移到合作券商 SDK」（[來源](https://developer.fugle.tw/docs/trading/intro/)）。
   - 富果**行情 API** 仍持續營運並有現行公開價目表。本文只把富果當作**行情來源**評估，不當作交易通道。

---

## 1. 比較表

| 項目 | **永豐金 Shioaji** | **Fugle 富果行情 API** | **富邦新一代 API (Neo)** | **台新（原元富）Nova API** | **元大 SPARK API** | **群益 Capital API** | **TWSE 官方（簽約資訊廠商）** | **TWSE OpenAPI / MIS** |
|---|---|---|---|---|---|---|---|---|
| 費用 | 官方頁面未列 API 費用（對永豐客戶免費）；**流量額度依成交金額分級** | 基本 免費／開發者 **NT$1,499/月**／進階 **NT$2,999/月** | **對富邦證券客戶免費** | 官網未載明費用 | 官網未載明費用 | 未能查證（官網下載頁擋抓取） | 傳輸授權費 **NT$60,000/月** 起＋各通路費 | 免費 |
| 需開戶？ | **需要**（永豐電子交易帳戶） | **不需要**，富果會員即可申請 API Key | **需要**（富邦證券帳戶） | **需要** | **需要**（無財力／交易量門檻） | **需要**＋向營業員申請 | 不需開戶，但**需與 TWSE 簽約**且非證券商／期貨商 | 不需要 |
| 線上可完成？ | 可（線上簽署＋線上測試） | 可（純線上，5 步驟） | 可（線上簽署＋連線測試），但憑證工具為 Windows | 可（線上簽署＋線上認證） | 可（線上簽署＋測試上傳），需聯繫營業員開通 | 需簽署同意書（線上／營業員） | 需書面契約與文件審查 | 直接呼叫 |
| Sandbox / 模擬 | **有**（`simulation=True`） | 無模擬環境（免費方案即可試） | 有連線測試工具 | **有**（驗證環境＋模擬交易所） | **有**（UAT，需申請固定 IP） | 有連線測試小程式 | 無 | 無 |
| 推播方式 | `api.subscribe()` 推播 ／ **HTTP + SSE** ／ CLI | **WebSocket** ＋ REST | **WebSocket** ＋ Web API | WebSocket ＋ Web API | 訂閱行情推播（元件） | ActiveX/COM 事件回呼 | 專線／IP 行情網路 | **僅輪詢** |
| 行情內容 | Tick（逐筆成交）／BidAsk（五檔）／Quote／KBar 1分／盤中零股 | trades／books（五檔）／candles／aggregates／indices | trades／books（五檔）／indices | 同 Fugle 系列 | 即時行情（細節未公開） | 即時行情（細節未公開） | 完整揭示資料 | 快照式 |
| 訂閱檔數上限 | **200**（每帳號） | 基本 **5**／開發者 **300**／進階 **2000** | **200／連線** | **300**（元富文件另載預設 50 檔） | 未公開 | 未能查證 | 依契約 | 無正式規範 |
| 同時連線數 | **5**（同一 ID） | 基本 **1**／付費 **2** | **5** | **2** | 未公開 | 未能查證 | 依契約 | 無 |
| 請求配額 | 行情查詢 10 秒 50 次；帳務 5 秒 25 次；委託 10 秒 250 次；登入 1000 次/日 | 日內 60／600／2000 req/min（依方案）；歷史一律 60/min | 日內 300／快照 300／歷史 60 req/min | 日內 600／快照 600／歷史 60 req/min | 未公開 | 未能查證 | 依契約 | 無正式規範 |
| 每日流量 | **500MB / 2GB / 10GB**（依前期成交金額分級）；**訂閱推播不計流量** | 未公開流量上限 | 未公開流量上限 | 未公開 | 未公開 | 未能查證 | 依契約 | 無 |
| SDK 語言 | **Python 原生 + HTTP/SSE（任何語言）+ CLI**；Rust core | **Python、Node.js** | **Python、Node.js、C#** | **Python、C#** | Python、C#（COM/Delphi/WPF 僅維護） | **ActiveX/COM，Windows Only** | 自行實作 | 任何語言 |
| 憑證需求 | 行情**不需憑證**（僅 API Key/Secret）；下單才需 | 不需 | **需要憑證**（`.pfx`，CATool 產生於 `C:\CAFubon\`） | 需認證 | 需測試憑證 | 需憑證 | N/A | N/A |
| 可否轉供第三方 | **不可**（受 TWSE 管理辦法 §14／§27 約束） | **明文禁止** | **不可**（同上） | **不可** | **不可** | **不可** | **原則不可，需 TWSE 同意** | 條款未能查證 |

---

## 2. 逐項回答

### 2.1 費用

**永豐金 Shioaji**
- 永豐金證券的簽署中心 API 頁面與 Shioaji 官方文件**均未列出任何 API 使用費**，屬於「證券帳戶附帶服務」（[簽署中心](https://www.sinotrade.com.tw/newweb/signCenter/S_openAPI/)）。
- 但**免費有價**：每日行情流量額度直接綁定成交量級距（[使用限制](https://sinotrade.github.io/zh/tutor/limit/)）：

  | 現貨成交金額 | 每日流量 |
  |---|---|
  | 0 元成交 | 500 MB |
  | 1 元 ~ 1 億元 | 2 GB |
  | > 1 億元 | 10 GB |

  期貨側對應 0 口 / 1~1000 大台（4000 小台）/ >1000 大台，同樣是 500MB / 2GB / 10GB。
- 關鍵緩解事實：官方明載「**盤中即時資料請使用行情訂閱（`api.subscribe()` 或 SSE 串流），訂閱推播不計入流量**」。也就是零成交量帳號的 500MB/日，只吃在 REST 查詢（snapshots/ticks/kbars）上，**串流訂閱不計費**。這對本專案「盤中秒級即時報價」的主場景幾乎無痛。

**Fugle 富果行情 API**（[價目表](https://developer.fugle.tw/docs/pricing/)，2026-08-01 查證）

| 方案 | 月費 | WS 訂閱數 | WS 連線數 | 日內 API | 快照 | 歷史 | 技術指標 | 股務事件 |
|---|---|---|---|---|---|---|---|---|
| 基本用戶 | **免費** | 5 | 1 | 60/min | 不支援 | 60/min | 不支援 | 不支援 |
| 開發者 | **NT$1,499/月** | 300 | 2 | 600/min | 600/min | 60/min | 60/min | 30/min |
| 進階用戶 | **NT$2,999/月** | 2000 | 2 | 2000/min | 2000/min | 60/min | 60/min | 30/min |

另有「更客製化方案（專屬 API 伺服器、不限連線數）」需洽詢業務。

**富邦新一代 API**：官方上線公告明載「富邦證券客戶**免費申請使用**」（[公告 2024-03-21](https://www.fbs.com.tw/wcm/new_web/trade/trade_20240321_004527.html)）。

**元大 SPARK API**：「申請元大 SPARK API 沒有財力或交易量門檻限制，只要是元大證券客戶即可提出申請」；**官網未載明費用**（[來源](https://www.yuanta.com.tw/file-repository/content/API/page/index.html)）。

**台新（原元富）Nova API**：官網未載明費用（[來源](https://mlapi.tssco.com.tw/web_api/service/home)）。註：`mlapi.masterlink.com.tw` 現已 307 轉址至 `mlapi.tssco.com.tw`，元富證券已整併入台新綜合證券品牌。

**群益 Capital API**：官方下載頁 `https://www.capital.com.tw/web/#/download/ApiTrading/ApiTradinginfo` 回應 403，**未能查證費用與額度，需人工確認**。

**TWSE 官方管道（成為簽約資訊廠商）**（[即時交易資訊](https://wwwc.twse.com.tw/zh/products/information/real-time.html)，新臺幣／月）
- 傳輸授權費：**60,000 元/月**
- 網際網路（自動更新）：**10 萬元/月**（≤5,000 戶）或 **12 元/戶/月**（>5,000 戶）
- 網際網路（非自動更新）：5 萬元/月（<20 萬戶）或 10 萬元/月（≥20 萬戶）
- 行動電話：2 萬元/家/月；有線電視翻頁式：3 萬元/月；證券語音：0.1 元/分鐘/月（上限 3 萬元/月）
- 數據專線：按設備數量分級定額計費
- 繳費期限：每月 15 日前繳付前月費用

**即時股價指數資訊**（[來源](https://wwwc.twse.com.tw/zh/products/information/stock.html)）
- TAIEX 等系列指數：**60,000 元／半年**（預付）
- 臺灣 50 等系列指數：國內傳輸暫不收費，海外使用須洽富時公司
- 申請對象：已與 TWSE 簽約的「即時交易資訊廠商」，**不含證券商、期貨商**

> 完整收費標準另有 PDF 附表（[table_fee.pdf](https://www.twse.com.tw/downloads/zh/products/table_fee.pdf)）。該 PDF 本次工具無法解析文字，**證券商／期貨商適用的附表三、四級距未能查證，需人工確認**。

**付費行情商**
- **TEJ TQuant Lab**：定位為量化回測與基本面／籌碼面資料庫，**非盤中秒級行情源**；坊間流傳月費 NT$488 / 888 / 1,200 三級距為二手來源（QuantPass），**未能於 TEJ 官方頁面查證，需人工確認**。
- **嘉實資訊 XQ 全球贏家**：為終端看盤軟體（[產品頁](https://www.sysjust.com.tw/Products/XQ.aspx)），其對外**行情 API 授權方案與報價未公開**，**未能查證，需人工確認**。
- **CMoney**：官網宣稱提供 API 串接與彈性授權（法人系統／數據貓頭鷹），但**企業方案報價完全未公開**，**未能查證，需人工確認**。

---

### 2.2 開通門檻

**永豐金 Shioaji**（[條款簽署與測試](https://sinotrade.github.io/zh/tutor/prepare/terms/)、[簽署中心](https://www.sinotrade.com.tw/newweb/signCenter/S_openAPI/)、[金鑰與憑證](https://sinotrade.github.io/zh/tutor/prepare/token/)）
- **需要永豐金證券電子（網路）交易帳戶**。
- 官方原文：「受限於台灣金融法規，新用戶首次使用需簽署相關文件並在測試模式完成測試報告才能進行正式環境的使用」。
- 簽署文件：**API 電子交易風險預告書暨使用同意書**，**證券與期貨需分別簽署**；線上逐條詳閱、勾選、等待閱讀秒數後始能簽署。
- 測試報告：需在模擬模式完成 **登入測試 + 下單測試**（證券、期貨各一，間隔 ≥1 秒）。
- 測試服務時間：**平日 08:00–20:00**，其中 **18:00–20:00 限台灣 IP**。API 測試紀錄**當日審核完畢**。
- 金鑰申請：登入永豐理財網 API 管理頁面 → 手機/信箱 2FA → 設定到期時間、權限（**行情/資料、帳務、交易、正式環境**）與 IP 限制 → 取得 API Key / Secret Key（Secret 僅建立時可見）。
- **Sandbox：有。** 初始化時 `simulation=True` 即進入模擬（paper trading）環境，模擬模式可略過憑證啟用。
- **重要**：行情／歷史等非個資資料**僅需登入驗證**；憑證（CA）只有下單與帳務個資才需要。

**Fugle 富果行情 API**（[申請教學](https://support.fugle.tw/fugle-special/5164/)）
- **完全不需開立證券帳戶**。官方原文：只需擁有富果會員帳號即可「免費申請行情 API Key」。
- 五步驟：登入富果 → 文件 ＞ 行情 → 右上「金鑰申請」→ 新增 API Key → 保存。
- **無獨立 sandbox**，但免費「基本用戶」方案本身即可作為驗證環境。
- **今日唯一可在數分鐘內、零開戶完成 PoC 的來源。**

**富邦新一代 API**（[事前準備](https://www.fbs.com.tw/TradeAPI/en/docs/trading/prepare/)）
- 需要：**富邦證券帳戶 + 數位憑證 + 已簽署 API 協議**。
- 憑證流程需下載 **CATool**，經身分驗證與 OTP 後產生 `身分證字號.pfx`，存放於 `C:\CAFubon\` — **此工具為 Windows 路徑，對 Linux/容器部署是實務摩擦點**。
- 線上簽署 API 協議後，執行連線測試工具（Windows）或直接透過 SDK 測試。

**台新（原元富）Nova API**（[來源](https://mlapi.tssco.com.tw/web_api/service/home)）
- 流程：自行開發並嵌入 API 元件 → 線上簽署風險預告書 → 線上認證（於驗證環境進行委託測試）→ **認證通過後次一工作日可使用**。
- **有驗證環境與模擬交易所**：證券類盤中 08:30–13:30 採即時行情撮合，其他時段採櫃號規則撮合；行情與下單 API 全天候開放（除轉檔時段）。

**元大 SPARK API**（[來源](https://www.yuanta.com.tw/file-repository/content/API/page/index.html)）
- 「沒有財力或交易量門檻限制，只要是元大證券客戶即可提出申請」；需簽署風險預告書、完成 API 測試上傳、聯繫營業員開通。
- **有 UAT 測試環境**，但**需申請固定 IP 防火牆**並使用測試憑證 — 對家用動態 IP 開發者是額外門檻。

**群益 Capital API**
- 需開戶並向營業員申請 API 資格、簽署契約後方能下載元件；已是群益客戶者可線上簽署〔證券 API 服務下單聲明書〕與〔期貨 API 下單聲明書〕。以上流程描述來自二手整理（[群益期貨營業員部落格](https://www.topbroker.tw/blog.php?act=view&id=61)），**官方頁面 403 無法查證，需人工確認**。

**TWSE 官方管道**
- 需依《臺灣證券交易所股份有限公司交易資訊使用管理辦法》第八～十一條提交申請書、公司登記證明、財務報告等文件並簽訂使用契約（[法規原文](https://twse-regulation.twse.com.tw/m/LawContent.aspx?FID=FL007129)）。
- 即時股價指數資訊之申請對象限「已與本公司簽約之申請使用者（即時交易資訊廠商）」，且**不含證券商、期貨商**。
- **結論：個人／小型團隊實務上不可行。** 這是給資訊廠商與媒體的通道，不是給應用開發者的。

---

### 2.3 報價形式與延遲

**Shioaji**（[股票即時行情](https://sinotrade.github.io/zh/tutor/market_data/streaming/stocks/)）
- 三種介面：**Python SDK `api.subscribe()`**、**CLI `shioaji data stream`**、**HTTP/SSE**。
- 四種 quote type：
  - `Tick`：**逐筆成交**（價、量、內外盤方向）
  - `BidAsk`：**最佳五檔**
  - `Quote`：成交＋委託簿的綜合快照
  - `KBar`：1 分鐘 K（僅股票）
- 支援 `intraday_odd` 參數區分整股／**盤中零股**。
- 指數行情僅有 `Quote` 一種，無 Tick 與 BidAsk（[指數行情](https://sinotrade.github.io/zh/tutor/market_data/streaming/)）。

**Fugle**（[WebSocket 開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started)）
- WebSocket endpoint：`wss://api.fugle.tw/marketdata/v1.0/stock/streaming`，送 API Key 認證。
- 五個頻道：`trades`（最新成交）、`candles`（分 K）、`books`（委託簿五檔）、`aggregates`（聚合）、`indices`（指數）。
- 伺服器每 **30 秒**送 heartbeat。
- REST base URL：`https://api.fugle.tw/marketdata/v1.0/stock/`，以 `X-API-KEY` header 認證（[REST 開始使用](https://developer.fugle.tw/docs/data/http-api/getting-started/)）。

**富邦 Neo**（[WebSocket](https://www.fbs.com.tw/TradeAPI/en/docs/market-data/websocket-api/getting-started/)）
- 三個頻道：`trades`、`books`（最佳五檔）、`indices`。
- 兩種模式：**Speed Mode（預設，低延遲）**與 **Normal Mode（多資訊）**。
- 30 秒 heartbeat；client 每 5 秒 ping。內建斷線重連與重新訂閱機制。

**TWSE 原生揭示頻率**（[集中市場交易制度](https://www.twse.com.tw/zh/products/system/trading.html)）
- 開盤前試算行情：自 09:00 起第一次揭示，其後**每 5 秒**試算撮合後揭露模擬成交價量與最佳五檔。
- 盤中逐筆交易：當筆委託逐次撮合後**即時揭露**成交價量，並於最後一次撮合後揭露未成交最佳五檔。
- 收盤前資訊揭露頻率比照盤中集合競價撮合頻率（**約 5 秒**）。
- **這是所有下游來源的物理上限**：交易所本身在盤中是「撮合後即時推送」，任何券商 API 的延遲都是在此之上疊加。

**TWSE OpenAPI / MIS**
- `https://openapi.twse.com.tw/` 為 Swagger UI，內容以**盤後／前一日資料**為主；本次抓取僅取得 Swagger 外殼，**條款與配額未能查證，需人工確認**。
- `https://mis.twse.com.tw/stock/api/getStockInfo.jsp` 是市況報導網站的內部端點，**TWSE 從未正式文件化**，無公開 SLA、無條款、無配額保證。**不可作為正式服務的行情源。**

**延遲量級 — 未能查證**
- **Shioaji、Fugle、富邦、元大、台新皆未公開任何端到端延遲數字或 SLA。**
- 可引用的一手事實只有：Shioaji 官方宣稱其 **Rust core 達到微秒級行情處理**（[Shioaji 總覽](https://sinotrade.github.io/zh/)），但這是**單機處理效能**，不等於交易所到用戶端的端到端延遲。
- 富邦有 **Speed Mode / Normal Mode** 的分檔設計，暗示延遲差異存在，但未給出數字。
- **建議：實測。** 訂閱同一檔股票，比對 tick 的交易所時戳與本地收到時戳，量測 P50/P95/P99。這是唯一可靠的取數方式，也應列為「開通帳號」票的驗收項目。

---

### 2.4 連線與流量限制

**Shioaji**（[使用限制](https://sinotrade.github.io/zh/tutor/limit/)）
- 訂閱數上限：**200 個**
- 同一 ID 最多連線數：**5 個**
- 登入：每天上限 **1000 次**
- 行情查詢（`snapshots` / `ticks` / `kbars` 等）：**總次數 10 秒上限 50 次**；盤中 `ticks` 不超過 10 次、`kbars` 不超過 270 次
- 帳務查詢：**5 秒上限 25 次**
- 委託操作：**10 秒上限 250 次**
- 每日流量：500MB / 2GB / 10GB（依成交量級距，見 §2.1）
- 超限行為：超流量時行情查詢**回傳空值**；超次數**暫停服務一分鐘**；**持續違規將暫停該 IP 及 ID 使用權**。官方明確警告：停權期間反覆重試 `login()` 無法解除限制，反而可能延長停權時間。

**Fugle**：見 §2.1 表格。超限回 **429**，等 1 分鐘後可繼續；超日限則隔日再試。

**富邦 Neo**（[Rate Limit](https://www.fbs.com.tw/TradeAPI/en/docs/market-data/rate-limit/)）
- Web API：日內 **300 req/min**、快照 **300 req/min**、歷史 **60 req/min**
- WebSocket：**每連線 200 訂閱**、**5 連線**（實質可達 1000 檔訂閱）
- 超限回 `429`；WebSocket 超訂閱回錯誤碼 `1001`（Maximum number of connections reached）
- **短時間內建立大量 Socket 連線會被判定為惡意攻擊並封鎖連線請求（404 Not Found）**

**台新 Nova API**（[Rate Limit](https://ml-fugle-api.tssco.com.tw/FugleSDK/docs/market-data/rate-limit/)）
- Web API：日內 **600/min**、快照 **600/min**、歷史 **60/min**
- WebSocket：**300 訂閱 / 2 連線**
- 註：台新／元富的 API 專區另載「系統預設最多可訂閱 **50 檔**行情報價資料」（[來源](https://mlapi.tssco.com.tw/web_api/service/home)）。**兩份官方文件數字不一致（50 vs 300），需人工向台新確認實際生效值。**

**元大 SPARK / 群益**：訂閱與連線上限**未於官方頁面公開，未能查證，需人工確認**。

---

### 2.5 SDK 與語言（直接約束後端技術棧）

這是本研究對架構影響最大的一項。

| 來源 | 官方 SDK | 是否綁 Python | 是否可從非 Python 後端直連 |
|---|---|---|---|
| **Shioaji** | Python 原生 bindings、**HTTP API（含 OpenAPI 互動文件 + SSE 串流 + Dashboard）**、CLI、Linux/macOS/Windows 獨立安裝檔 | **否** | **可**。官方明示可用 JavaScript/TypeScript、Go、C/C++、C#、Rust、Java/Kotlin 等任何能呼叫 HTTP 的語言 |
| **Fugle** | Python（`fugle-marketdata-python`）、Node.js（`fugle-marketdata-node`） | 否 | **可**（WebSocket + REST 均為標準協定，無 SDK 也能直連） |
| **富邦 Neo** | Python 3.7+、Node.js 16+、C#（.NET 7 / .NET Framework 4.7.2+） | 否 | 部分。SDK 登入綁憑證，非 SDK 語言需自行處理認證 |
| **台新 Nova** | Python、C# | 否 | 未公開 |
| **元大 SPARK** | Python、C#（COM/Delphi/WPF 僅維護既有功能，新功能只在 Python 與 C#） | 否 | 未公開 |
| **群益 Capital** | **ActiveX / COM 元件** | 否，但 **綁 Windows** | 否 |

**結論**：
- **群益因 COM/Windows 綁定，直接被排除**於任何 Linux 容器化後端架構之外。
- **Shioaji 是唯一提供官方 HTTP + SSE 的券商 API**，意味著後端語言可以自由選擇（Go / Node / Rust 皆可），Python 只是「其中一個選項」而非約束。
- Fugle 的 WebSocket + REST 也是語言中立的，但它是行情源、不含交易。
- Shioaji GitHub repo 維持 **14 天發版節奏**，並宣稱是「首個支援 AI Coding Agent（Claude Code / Codex）的台灣交易 API」（[repo](https://github.com/Sinotrade/Shioaji)）。

---

### 2.6 授權條款 — **這是本研究最重要的一節**

**核心結論：目前市面上所有可實務取得的台股即時行情來源，都不允許把行情轉供第三方或在對外服務中呈現。**

#### 法源：臺灣證券交易所交易資訊使用管理辦法

（[法規原文](https://twse-regulation.twse.com.tw/m/LawContent.aspx?FID=FL007129)）

- **第 14 條**：申請使用者「**非經本公司同意，不得再將本公司交易資訊出租、出售或轉讓他人，或以任何方式再轉接至他處**」。
- **第 14-1 條**：證券商「**不得將交易資訊轉接至其營業處所外**」（經同意者除外）；資訊源傳輸僅限內部使用，合作廠商不得改變傳輸格式或從事轉接業務。
- **第 27 條**：資訊用戶「**不得將本公司交易資訊出租、出售或轉讓他人**」。
- 第 24 條：申請使用者應定期申報揭示與**非揭示用途**之用戶資訊。
- 第 28 條：須依收費標準繳付費用及權利金；第 29 條：盤後資訊經核准得免費提供。

#### 富果的條款原文（最明確的下游條文）

（[富果即時行情 API 使用規範](https://developer.fugle.tw/docs/data/intro/)）

> 「使用者應遵守臺灣證券交易所股份有限公司交易資訊使用管理辦法……如有盜接、轉接交易資訊，或以其他方式**出售、出租、轉讓、再授權交易資訊**，或將交易資訊另行取樣並**編製指數、其他衍生性商品或將之傳送予第三人**，應負違約及侵權之相關民、刑事責任。」

同頁另載：

> 「為維護服務品質與公平性，**每位使用者僅限申請及使用一個帳號**。使用者不得以任何方式（包括但不限於註冊多個帳號、使用虛假身份或借用他人身份）規避本服務所設定之任何使用限制。」
>
> 「透過本服務取得之行情資料**僅供參考**，成交值及成交量不含零股及鉅額交易，使用者依本資料交易發生交易損失需自行負責。」

#### 永豐金 Shioaji

- 永豐金證券簽署中心的〈API 電子交易風險預告書暨使用同意書（證券）〉線上頁面僅顯示八項摘要條款（涵蓋 API 使用風險、程式交易、密碼保管、資訊免責），**未在公開頁面呈現行情智慧財產權／再散布條款**（[簽署中心](https://www.sinotrade.com.tw/newweb/signCenter/S_openAPI/)）。
- 完整條文須登入下載 PDF 副本。**Shioaji 同意書中關於「行情轉供第三人」的具體文字，未能於公開管道查證，需人工在簽署時逐條確認。**
- 但**這不影響結論**：永豐作為 TWSE 簽約端，其行情必然受管理辦法 §14-1 拘束（不得將交易資訊轉接至營業處所外），下游客戶自然不可能取得比上游更寬的授權。

#### 對「未來上架給別人用」的實務結論

1. **用券商 API 的行情去做對外 SaaS／公開網站即時報價牆 → 不合法。** 無論永豐、富果、富邦、元大、台新皆然。
2. 合法路徑只有三條：
   - **(a)** 自己成為 TWSE **簽約資訊廠商**：傳輸授權費 **6 萬元/月**起，加上網際網路通路費（自動更新 10 萬元/月起），且須通過資格審查與契約簽訂。**這是唯一能對外散布即時行情的合法路徑，成本量級是每月十萬元起跳。**
   - **(b)** 對外只呈現**延遲 20 分鐘以上**的資訊或盤後資料（TWSE 明列延遲資訊與盤後資訊為獨立、較寬鬆的產品線）。
   - **(c)** 對外只呈現**衍生結論**（訊號、評分、排行），不呈現原始報價。**但富果條款明文禁止「將交易資訊另行取樣並編製指數、其他衍生性商品」，這條路的邊界需個案法務確認。**
3. **架構建議**：把「即時行情」定位為**內部運算輸入**（自用、非揭示用途），而不是產品的對外呈現層。這樣選型就能以自用便利性為唯一考量，把授權問題往後推到真正要商業化時再解。

---

### 2.7 穩定性風評

**Shioaji**（[GitHub Issues](https://github.com/Sinotrade/Shioaji/issues)，2026-08-01 查得 26 個 open issues）

近期一手回報（皆為官方 repo 上的 open issue）：

| Issue | 日期 | 內容 |
|---|---|---|
| #213 | 2026-07-29 | 期貨帳戶 `list_positions()` 失敗，`Unit.Common error` |
| #212 | 2026-07-23 | `api.kbars()` 歷史資料回傳空值，約 286 個合約受影響（`api.ticks()` 正常） |
| #209 | 2026-06-23 | 持倉數量計算錯誤：整張與零股混合成交時，零股被誤算為整張（×1000） |
| #211 | — | 模擬環境成交價超出行情範圍（微型臺指期貨） |
| #201 | — | 盤中 ticks/kbars 查詢限制規則需澄清 |

其他已知模式：
- 官方 QA 記載常見「行情只能收幾行就斷掉」，但根因是 Python script 訂閱後立即結束，解法是加 `Event().wait()` — **非服務端問題**（[QA](https://sinotrade.github.io/qa/)）。
- 社群長期回報閒置過夜後出現 `connection lost`（[Issue #26](https://github.com/Sinotrade/Shioaji/issues/26)）。
- **限流即停權的風險是真實的**：官方明載持續超限會暫停 IP 與 ID 使用權，且停權期間反覆 `login()` 會延長停權。**任何實作都必須內建 backoff，不能無腦重試。**
- 正面訊號：官方自家的 Shioaji Pro App 內建「斷線自愈」（SSE 重連後自動重新訂閱全部商品、斷線期間鎖定下單按鈕），代表**官方承認斷線是常態，並已把重連視為必要設計**（[shioaji-pro-app](https://github.com/Sinotrade/shioaji-pro-app)）。

**Fugle**
- **最大風險不是技術，是商業關係變動**：玉山證券合作於 2024-12-31 終止、交易 API 於 2025/11 停更。行情 API 雖仍在營運且技術輸出給富邦與台新，但**單一 fintech 供應商的服務存廢風險高於券商本體**。
- 未找到官方 status page 或維護公告頁，**服務中斷歷史未能查證**。技術支援管道為 Discord、GitHub、`tech.support@fugle.tw`（[FAQ](https://developer.fugle.tw/docs/faq/intro/)）。

**富邦 Neo**
- 官方文件明載內建重連與重新訂閱機制，並警告「短時間大量建立 Socket 連線會被視為惡意攻擊並封鎖」。
- 未找到公開 incident 紀錄，**穩定性風評未能查證**。

**台新／元大／群益**：**未能查證，需人工確認。**

---

## 3. 推薦

### 推薦方案：**主用永豐金 Shioaji，並在開通期間先用 Fugle 免費方案做 PoC**

#### 3.1 主線：永豐金 Shioaji

**推薦理由**

1. **唯一提供官方 HTTP API + SSE 的券商行情源。** 這直接解除了本專案後端技術棧的約束 —— 後端可以是 Go / Node / Rust，Python 只是選項之一。其他所有券商 API 都只給語言特定的 SDK。（[來源](https://sinotrade.github.io/zh/)）
2. **行情不需要憑證，只需 API Key/Secret。** 憑證只綁下單與帳務。這代表行情擷取服務可以純 Linux 容器部署，無 Windows 依賴。富邦的 `.pfx` + `C:\CAFubon\` CATool 流程在這點上明顯落後。
3. **串流訂閱不計流量。** 對「盤中秒級即時報價」這個主場景，即使是零成交量帳號的 500MB/日 額度也幾乎不會被觸及 —— 流量只吃在 REST 查詢上。（[使用限制](https://sinotrade.github.io/zh/tutor/limit/)）
4. **行情類型最完整**：Tick 逐筆成交、BidAsk 五檔、Quote、1 分 KBar，且原生支援盤中零股（`intraday_odd`）。多數競品沒有 KBar 與零股區分。
5. **有真正的模擬環境**（`simulation=True`），可在不動用真實資金的前提下驗證完整流程。
6. **免費**（對永豐客戶），且 200 訂閱 / 5 連線對本專案初期規模綽綽有餘。
7. **官方維護積極**：14 天發版節奏、公開 changelog、Telegram/Discord 社群、自家 Pro App 吃自己的狗糧。

**已知代價（接受，但要設計對應）**
- 必須開立永豐金證券帳戶並完成模擬測試報告 —— 一次性成本，線上可完成。
- 流量額度綁成交量：零成交帳號只有 500MB/日。**設計上必須嚴守「串流訂閱為主、REST 查詢為輔」的原則。**
- 限流即停權：**必須內建指數退避，禁止失敗後無腦重試 `login()`。**
- 近期有 kbars 回傳空值等 open issue（#212）——**歷史 K 線不應單一依賴 Shioaji，需有備援資料源。**

#### 3.2 過渡／備援：Fugle 富果行情 API（基本用戶，免費）

**用途定位**：**今天就能開始寫程式的 PoC 資料源**，以及 Shioaji 故障時的第二意見來源。

- **不需開任何證券戶**，富果會員 5 步驟即可拿到 API Key（[來源](https://support.fugle.tw/fugle-special/5164/)）。
- 免費層 5 訂閱 / 1 連線，足以驗證 WebSocket 串接、資料格式、延遲量測方法論。
- 若 PoC 階段就需要 300 檔以上訂閱，NT$1,499/月 的開發者方案是市面上**唯一不需開戶就能買到的 300 檔即時串流**。

**但不推薦為主線**，理由見 §3.3。

#### 3.3 被否決者與否決理由

| 來源 | 否決理由 |
|---|---|
| **Fugle 富果（作為主線）** | **商業關係穩定性不足**：玉山合作已於 2024-12-31 終止、交易 API 於 2025/11 停更。免費層僅 **5 檔訂閱 / 1 連線**，不足以支撐任何實用的多標的監控；要達到 300 檔須付 NT$1,499/月，而 Shioaji 給 200 檔是免費的。且富果純為行情商，**未來若要加上下單，仍得回頭接券商 API**，等於多維護一套整合。 |
| **富邦新一代 API** | 技術規格其實**很強**（5 連線 × 200 訂閱 = 1000 檔、Speed Mode、Python/Node/C# 三 SDK、對富邦客戶免費），是最接近的次選。否決點有二：**(a)** 行情存取需憑證，且憑證產生工具 CATool 明確走 Windows 路徑（`C:\CAFubon\`），對 Linux 容器化部署是實質摩擦；**(b)** 無官方 HTTP/SSE 通用介面，後端語言被 SDK 綁死在 Python/Node/C#。**建議列為第一備援**，若 Shioaji 開通受阻或穩定性不符預期即切換。 |
| **台新（原元富）Nova API** | 官方文件**自相矛盾**：API 專區寫「預設最多訂閱 50 檔」，Nova API rate limit 頁寫 300 訂閱 / 2 連線。50 檔對本專案明顯不足，而在未釐清前不能承擔此風險。加上元富併入台新的品牌／網域遷移（`masterlink.com.tw` → `tssco.com.tw`）仍在進行中，服務穩定性有額外不確定性。 |
| **元大 SPARK API** | 開通門檻其實最低（無財力／交易量門檻），但**訂閱上限、連線數、費用、行情協定全部未公開**，無法在紙面上完成評估。UAT 測試環境**需申請固定 IP 防火牆**，對開發階段是不必要的摩擦。**未能查證的項目過多，不宜作為主線。** |
| **群益 Capital API** | **直接出局**：ActiveX / COM 元件、綁 Windows，與 Linux 容器化後端架構根本不相容。且官方下載頁 403 無法查證規格。 |
| **TWSE 官方簽約管道** | **成本與門檻與專案階段完全不匹配**：傳輸授權費 6 萬元/月起，網際網路通路另計 10 萬元/月起，並須通過資格審查、簽訂契約、定期申報用戶資訊。**唯一值得記住的是：這是未來要對外提供即時行情時的唯一合法路徑**，應在商業化評估時重新拿出來算。 |
| **TWSE OpenAPI（openapi.twse.com.tw）** | 內容以盤後／前一日資料為主，**不是盤中秒級行情源**，不符本票需求。 |
| **TWSE MIS（`getStockInfo.jsp`）** | **絕對不可用於正式服務**：TWSE 從未正式文件化此端點，無條款、無配額保證、無 SLA，隨時可能變更或封鎖。所有關於「5 秒更新一次」的說法均為社群逆向觀察，非官方承諾。作為個人玩具尚可，作為產品基礎是不可接受的風險。 |
| **TPEx 官方管道** | 資訊購買頁面（`www.tpex.org.tw/web/service/info_service/info_service.php`）本次抓取回應 403，**產品、資格與收費全部未能查證**。惟依 TWSE 同構的制度設計推斷，門檻與成本量級應相當，同樣不適合本階段。**需人工確認。** |
| **TEJ TQuant Lab** | **定位不符**：是量化回測與基本面／籌碼面資料庫，非盤中秒級即時行情源。 |
| **嘉實資訊 XQ 全球贏家** | 產品形態是**終端看盤軟體**而非開放 API；對外 API 授權方案與報價未公開。**未能查證，需人工確認。** |
| **CMoney** | 官網宣稱提供 API 串接與彈性授權，但**報價、額度、條款全部未公開**，需經業務洽談。對本階段而言不可評估、不可預算。**未能查證，需人工確認。** |

---

## 4. 開通清單：永豐金 Shioaji

> 對應「開通台股行情源帳號與憑證」票（#8 / #12 / #13）。
> ⚠️ 本 repo 為 public。以下任何步驟產出的 API Key、Secret Key、身分證字號、憑證檔案**一律不得進入 git**。請以環境變數或本機 `.env`（已列入 `.gitignore`）保存。

### 步驟 A — 開立證券帳戶（若尚無）
1. 線上開立**永豐金證券電子（網路）交易帳戶**。API 功能以此帳戶為前提。
2. 一併確認開通期貨帳戶與否 —— 若未來需要台指期行情／下單，證券與期貨的 API 同意書**必須分別簽署**。

### 步驟 B — 線上簽署 API 同意書
3. 前往 [永豐金證券簽署中心 — API](https://www.sinotrade.com.tw/newweb/signCenter/S_openAPI/)。
4. 逐條詳閱〈API 電子交易風險預告書暨使用同意書〉，勾選確認，**等待閱讀倒數完成**後簽署。
5. **在此步驟務必下載 PDF 副本並人工檢視「行情資訊之智慧財產權／再散布」相關條文** —— 本研究無法在公開管道取得此段文字，需在簽署當下補上（見 §2.6）。
6. 證券／期貨如都需要，分別完成簽署。

### 步驟 C — 申請 API 金鑰
7. 登入永豐理財網「API 管理」頁面。
8. 完成手機或信箱 **2FA**。
9. 設定：
   - **到期時間**
   - **權限**：至少勾選「**行情 / 資料**」；若之後要下單再開「交易」「帳務」「正式環境」
   - **IP 限制**（官方建議設定以提高安全性；若部署在雲端請填固定出口 IP）
10. 取得 **API Key** 與 **Secret Key**。⚠️ **Secret Key 僅在建立當下可見，之後無法重新取得**，請立刻存入密鑰管理處（不是 repo）。

### 步驟 D — 模擬環境驗證
11. 安裝 SDK：`pip install shioaji`（或 CLI／獨立安裝檔）。
12. 以 `simulation=True` 初始化，模擬模式可略過憑證啟用。
13. 完成官方要求的**測試報告**：
    - **登入測試**
    - **下單測試**（證券、期貨各一，兩筆間隔 ≥ 1 秒）
14. ⚠️ **測試服務時間：平日 08:00–20:00；其中 18:00–20:00 僅限台灣 IP。** 請勿在境外 VPN 或非營業日嘗試。
15. 測試紀錄**當日審核完畢**。

### 步驟 E — 確認正式權限
16. 於正式環境查詢帳號狀態，確認 `signed` 欄位顯示已核可（可透過簽署中心或 `api.list_accounts()` 驗證）。
17. 若出現 `Account not acceptable`，代表簽署或測試流程尚未完成（[QA](https://sinotrade.github.io/qa/)）。

### 步驟 F —（僅下單需要）憑證
18. 行情**不需要**此步驟。若之後要下單，從**新理財網**（推薦，跨平台）或 **eleader**（僅 Windows）下載電子憑證，並在下單前呼叫 `api.activate_ca()`。

### 步驟 G — 實作與驗收
19. 訂閱設計原則：**串流優先**（`api.subscribe()` 或 SSE），**嚴禁**用輪詢 `snapshots`/`ticks`/`kbars` 取代即時行情 —— 這是流量與停權風險的主要來源。
20. 內建**指數退避重連**；收到限流或斷線時**不得無腦重試 `login()`**。
21. 監控自身用量，確保遠低於：200 訂閱、5 連線、行情查詢 10 秒 50 次、每日流量額度。
22. **驗收項目：實測端到端延遲。** 比對 tick 的交易所時戳與本地接收時戳，記錄 P50 / P95 / P99。這是本研究無法從文件取得、必須實測的唯一關鍵數字。

### 平行步驟 — Fugle PoC（可今天就做，零門檻）
23. 註冊[富果會員](https://developer.fugle.tw/)（不需開證券戶）。
24. 登入 → 文件 ＞ 行情 → 右上「金鑰申請」→ 建立 API Key。
25. 用免費「基本用戶」方案（5 訂閱 / 1 連線）串接 `wss://api.fugle.tw/marketdata/v1.0/stock/streaming`，先把延遲量測方法論與資料模型驗證完成，等 Shioaji 開通後直接沿用。

---

## 5. 未能查證項目彙總（需人工確認）

| # | 項目 | 阻礙 | 建議做法 |
|---|---|---|---|
| 1 | 各家**端到端延遲**數字 / SLA | 所有業者皆未公開 | 開通後實測，列為驗收項目 |
| 2 | 永豐 API 同意書中**行情再散布**條文原文 | 公開頁僅顯示八項摘要，完整條文需登入下載 PDF | 簽署時逐條檢視並截圖存證 |
| 3 | TWSE **收費標準附表三、四**（證券商／期貨商級距） | [table_fee.pdf](https://www.twse.com.tw/downloads/zh/products/table_fee.pdf) 本次工具無法解析 | 人工開啟 PDF 或洽 TWSE 數位資安部 (02)8101-3393 |
| 4 | **TPEx** 資訊服務產品／資格／收費 | [資訊購買頁](https://www.tpex.org.tw/web/service/info_service/info_service.php?l=zh-tw) 回應 403 | 人工瀏覽或致電 (02)2369-9555 |
| 5 | **群益 Capital API** 費用、訂閱與連線上限 | [官方下載頁](https://www.capital.com.tw/web/#/download/ApiTrading/ApiTradinginfo) 回應 403 | 已因 Windows/COM 綁定否決，優先度低 |
| 6 | **台新 Nova API** 訂閱上限 50 vs 300 矛盾 | 兩份官方文件數字不一致 | 洽台新 API 窗口確認實際生效值 |
| 7 | **元大 SPARK API** 費用、訂閱與連線上限 | 官網未載明 | 若要列為備援則須洽營業員 |
| 8 | **XQ（嘉實資訊）** 對外 API 授權方案與報價 | 未公開 | 需業務洽談 |
| 9 | **CMoney** 企業 API 方案報價與條款 | 未公開 | 需業務洽談 |
| 10 | **TEJ TQuant Lab** 現行方案價格 | 僅查到二手來源 | 若未來要用歷史資料再查證；非本票主軸 |
| 11 | **TWSE OpenAPI** 使用條款與配額 | Swagger UI 未載明 | 若要用於盤後資料需另行查證 |
| 12 | **Fugle / 富邦** 服務中斷歷史 | 未找到公開 status page | 開通後自行建立可用性監控 |

---

## 6. 來源清單（全部為第一手）

### 永豐金 Shioaji
- [Shioaji 總覽（官方文件）](https://sinotrade.github.io/zh/)
- [使用限制](https://sinotrade.github.io/zh/tutor/limit/)
- [條款簽署與測試](https://sinotrade.github.io/zh/tutor/prepare/terms/)
- [金鑰與憑證申請](https://sinotrade.github.io/zh/tutor/prepare/token/)
- [股票即時行情](https://sinotrade.github.io/zh/tutor/market_data/streaming/stocks/)
- [即時行情總覽](https://sinotrade.github.io/zh/tutor/market_data/streaming/)
- [官方 QA](https://sinotrade.github.io/qa/)
- [GitHub: Sinotrade/Shioaji](https://github.com/Sinotrade/Shioaji) ／ [Issues](https://github.com/Sinotrade/Shioaji/issues)
- [GitHub: Sinotrade/shioaji-pro-app](https://github.com/Sinotrade/shioaji-pro-app)
- [永豐金證券簽署中心 — API](https://www.sinotrade.com.tw/newweb/signCenter/S_openAPI/)

### Fugle 富果
- [富果即時行情 API 介紹與使用規範](https://developer.fugle.tw/docs/data/intro/)
- [台股行情方案及價格](https://developer.fugle.tw/docs/pricing/)
- [WebSocket API 開始使用](https://developer.fugle.tw/docs/data/websocket-api/getting-started)
- [REST API 開始使用](https://developer.fugle.tw/docs/data/http-api/getting-started/)
- [富果交易 API（2025/11 停更公告）](https://developer.fugle.tw/docs/trading/intro/)
- [常見問答](https://developer.fugle.tw/docs/faq/intro/)
- [如何申請使用富果即時行情 API](https://support.fugle.tw/fugle-special/5164/)
- [【重大權益變更通知】玉山證券富果帳戶專屬功能變動之富果聲明（2024-10-21）](https://support.fugle.tw/fugle-announcement/15335/)

### 富邦證券
- [Market Data API 介紹](https://www.fbs.com.tw/TradeAPI/en/docs/market-data/intro/)
- [Rate Limit](https://www.fbs.com.tw/TradeAPI/en/docs/market-data/rate-limit/)
- [WebSocket API 開始使用](https://www.fbs.com.tw/TradeAPI/en/docs/market-data/websocket-api/getting-started/)
- [Web API 開始使用](https://www.fbs.com.tw/TradeAPI/en/docs/market-data/http-api/getting-started/)
- [事前準備](https://www.fbs.com.tw/TradeAPI/en/docs/trading/prepare/)
- [富邦新一代 API 上線公告（2024-03-21）](https://www.fbs.com.tw/wcm/new_web/trade/trade_20240321_004527.html)
- [富邦金控新聞稿：富邦證券聯手富果推出新一代 Python API（2025-07-17）](https://www.fubon.com/financialholdings/news/news_1250717_716035.htm)

### 台新（原元富）／元大
- [台新數位 API 專區](https://mlapi.tssco.com.tw/web_api/service/home)
- [Nova API 速率限制](https://ml-fugle-api.tssco.com.tw/FugleSDK/docs/market-data/rate-limit/)
- [元大 SPARK API](https://www.yuanta.com.tw/file-repository/content/API/page/index.html)

### 交易所與法規
- [TWSE 資訊服務總覽](https://www.twse.com.tw/zh/products/information/information.html)
- [TWSE 即時交易資訊（含月費表）](https://wwwc.twse.com.tw/zh/products/information/real-time.html)
- [TWSE 即時股價指數資訊](https://wwwc.twse.com.tw/zh/products/information/stock.html)
- [TWSE 交易資訊使用管理辦法、契約、收費標準](https://wwwc.twse.com.tw/zh/products/information/use.html)
- [交易資訊使用管理辦法 法規原文（含 §14 / §14-1 / §27）](https://twse-regulation.twse.com.tw/m/LawContent.aspx?FID=FL007129)
- [TWSE 收費標準 PDF](https://www.twse.com.tw/downloads/zh/products/table_fee.pdf)
- [TWSE 集中市場交易制度介紹（揭示頻率）](https://www.twse.com.tw/zh/products/system/trading.html)
- [TWSE OpenAPI](https://openapi.twse.com.tw/)
- [TPEx 資訊購買](https://www.tpex.org.tw/web/service/info_service/info_service.php?l=zh-tw)（本次 403）
- [TAIFEX 相關網站 — 行情資訊](https://www.taifex.com.tw/cht/13/realTimeInfoLink)

### 其他
- [嘉實資訊 XQ 全球贏家產品頁](https://www.sysjust.com.tw/Products/XQ.aspx)
- [群益 API 下載頁](https://www.capital.com.tw/web/#/download/ApiTrading/ApiTradinginfo)（本次 403）

> 二手來源（僅用於定位官方頁面，未作為結論依據）：[群益期貨營業員部落格 — 申請 API](https://www.topbroker.tw/blog.php?act=view&id=61)
