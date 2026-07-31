# 台股基本面與籌碼面資料來源研究

> 對應 issue：[#3 研究：台股基本面與籌碼面資料來源](https://github.com/NTUyu016/stock-analytic-platform/issues/3)（Part of #1）
> 查證日期：**2026-08-01**（所有端點、條款、額度均於當日實測／實查）
> 實測環境：`uv run --with yfinance`，yfinance **v1.5.2**

---

## 0. 一句話結論

- **籌碼面**：官方 OpenAPI 只給「最新一天快照」且**缺個股三大法人**；要歷史序列，官方途徑只剩交易所網站的非公開 JSON 端點，而該途徑被 TWSE／TPEx 使用條款的**爬蟲禁止條款**明文涵蓋。實務上籌碼面歷史應走 **FinMind**。
- **基本面**：TWSE／TPEx OpenAPI 的財報／月營收／股利同樣**只有最新一期**（實測：綜合損益表僅 115Q1、月營收僅 11506、股利僅 114–115 年度），適合當「權威校驗基準」而非歷史倉庫。
- **yfinance `.TW`/`.TWO`**：**價格與財報數字準確度出乎意料地高**（2330 2026Q1 逐項與 TWSE OpenAPI 完全吻合），但**籌碼面 0 覆蓋、月營收 0 覆蓋、ETF 與金融股欄位大量錯誤或缺漏、債券 ETF 完全查不到**，且 Yahoo 條款寫明「personal use only」。既有 skill 可沿用的是「價格 + 個股財務報表 + 現金股利」，籌碼面與 ETF 面必須另建。

---

## 1. 來源總覽比較表

| 來源 | API 形式 | 費用 | 歷史深度 | 更新頻率 | 速率限制 | 授權 | 適用性 |
|---|---|---|---|---|---|---|---|
| [TWSE OpenAPI](https://openapi.twse.com.tw/) | REST，JSON／CSV，**無任何 query 參數** | 免費 | **僅最新一期快照** | 日更／季更（依表） | 文件未載明（**未能查證**） | 上架 data.gov.tw 者為[政府資料開放授權條款-第1版](https://data.gov.tw/license)（可商用、可散布、須顯名） | 校驗基準、最新快照、清單類 |
| [TPEx OpenAPI](https://www.tpex.org.tw/openapi/) | REST，JSON／CSV，**無任何 query 參數** | 免費 | 多數僅最新一期；少數（當沖統計）給整月 | 日更／月更／季更 | 文件未載明（**未能查證**） | 同上（櫃買條款亦有 data.gov.tw 除外條款） | 上櫃／興櫃補位 |
| TWSE 網站 JSON（`www.twse.com.tw/rwd/zh/...`） | 非公開文件的 REST，`?date=YYYYMMDD&response=json` | 免費 | 深（T86 回溯至 **2012-05-02**；當沖 **2014-01-06**） | 日更 | 未公告（**未能查證**） | **不在開放資料授權範圍**，受[使用條款](https://www.twse.com.tw/zh/terms/use.html)爬蟲禁止條款拘束 | 高風險，僅供人工／一次性查證 |
| TPEx 網站 JSON（`www.tpex.org.tw/www/zh-tw/...`） | 同上，`?date=YYYY/MM/DD&response=json` | 免費 | 深（未逐一實測下限） | 日更 | 未公告（**未能查證**） | 同上，見[櫃買使用條款](https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html) | 高風險 |
| [FinMind](https://finmind.github.io/) | REST `https://api.finmindtrade.com/api/v4/data`＋Python SDK | 免費層可用；Backer／Sponsor 需付費（**金額未能查證**） | **深且齊全**（財報 1990、融資融券 2001、三大法人 2005、當沖 2014） | 盤後當日（各 dataset 有明列時間） | **600 req/hr（帶 token）／300 req/hr（不帶）**，超限回 HTTP 402 | 套件為 Apache-2.0；**資料本身再散布授權未明示（需人工確認）** | 主力歷史資料來源 |
| [公開資訊觀測站 MOPS](https://mops.twse.com.tw/) | 改版後為 SPA，背後 `/mops/api/*` **無公開文件** | 免費 | 深 | 依申報時程 | 未公告 | 未見獨立資料授權說明 | **不建議程式化存取**；其內容已由 OpenAPI `t187apXX` 系列重發 |
| yfinance（Yahoo Finance） | Python 套件（非官方包裝 Yahoo 私有 API） | 免費 | 價格深（2330 自 2000-01-04，6608 列） | 日更＋盤中延遲 | 未公告，Yahoo 端會 429 | 套件 Apache-2.0；**資料端 Yahoo 條款寫明 personal use only** | 價格＋財報可用；籌碼面完全不可用 |
| 交易所付費資訊服務（[TWSE 網路資訊商店](https://www.twse.com.tw/zh/products/information/introduce.html)／[櫃買資訊購買](https://www.tpex.org.tw/zh-tw/service/data/overview.html)） | 檔案／專線 | 付費（**費率未能查證**） | 深 | 即時／日更 | — | 商業授權 | 若日後需商業散布，這是唯一乾淨路徑 |

---

## 2. 籌碼面：逐項來源（含實測驗證）

### 2.1 三大法人買賣超（個股別）

**關鍵發現：TWSE OpenAPI 根本沒有這張表。** 實測掃過 `swagger.json` 全部 **143 個 path**（TPEx 為 225 個），在 TWSE spec 全文搜尋 `法人` / `T86` / `BFI82U` 皆 **0 命中**。

| 市場 | 端點 | 實測結果 |
|---|---|---|
| 上市（快照 ✗） | TWSE OpenAPI | **不存在** |
| 上市（歷史 ✓，高風險） | `https://www.twse.com.tw/rwd/zh/fund/T86?date=20260731&selectType=ALL&response=json` | 200，1.5 MB，19 欄（外陸資／外資自營商／投信／自營自行／自營避險／合計）。實測 `date=20200102` OK；`date=20120102` 回 `查詢日期小於101年05月02日` → **歷史下限 2012-05-02** |
| 上市大盤 | `https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate=20260731&type=day&response=json` | 200，五類法人買賣金額 |
| 上櫃（快照 ✓） | `https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading` | 200，854 KB，**僅最新一日（1150731）** |
| 上櫃（歷史 ✓，高風險） | `https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=2026/07/31&response=json` | 200，25 欄 |
| **建議** | FinMind `TaiwanStockInstitutionalInvestorsBuySell` | 2005-01-01 起，涵蓋上市／上櫃／興櫃，週一至五 20:00 更新，免費層帶 `data_id` 即可 |

> 註：FinMind 免費層可查**單一個股**；「不帶 data_id 取當日全市場」需 Backer／Sponsor。

### 2.2 融資融券餘額

| 市場 | 端點 | 實測 |
|---|---|---|
| 上市快照 | `https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN` | 200，266 KB，**僅最新交易日**，含融資買進／賣出／現償／前日餘額／今日餘額／限額 |
| 上市歷史 | `https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=YYYYMMDD&selectType=ALL&response=json` | 200，實測 `20200731`、`20260731` 皆 OK |
| 上櫃快照 | `https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance` | 200，542 KB，僅最新日，含使用率 `MarginPurchaseUtilizationRate` |
| 上櫃歷史 | `https://www.tpex.org.tw/www/zh-tw/margin/balance?date=2026/07/31&response=json` | 200，20 欄（含資使用率／券使用率） |
| **建議** | FinMind `TaiwanStockMarginPurchaseShortSale` | **2001-01-01** 起，週一至五 21:00 更新 |

### 2.3 借券賣出

台股「借券」有兩個不同概念，容易混淆，務必分清：

| 概念 | 端點 | 實測 |
|---|---|---|
| **當日可借券賣出股數**（額度） | `https://openapi.twse.com.tw/v1/SBL/TWT96U` | 200，128 KB，**同時含上市（TWSECode）與上櫃（GRETAICode）** |
| **借券賣出餘額**（部位，上市） | `https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date=YYYYMMDD&response=json`（信用額度總量管制餘額表） | 200，後半 6 欄即借券賣出：前日餘額／當日賣出／當日還券／當日調整／當日餘額／次一營業日可限額。實測 `20200102` OK |
| **借券賣出餘額**（部位，上櫃） | `https://www.tpex.org.tw/openapi/v1/tpex_margin_sbl`（快照）／`https://www.tpex.org.tw/www/zh-tw/margin/sbl?date=2026/07/31&response=json`（歷史） | 皆 200 |
| **借券成交明細**（費率、還券日） | FinMind `TaiwanStockSecuritiesLending` | **2001-05-01** 起，含 `fee_rate`、`original_return_date`、`original_lending_period`；週一至五 15:00 更新 |

> `https://www.twse.com.tw/rwd/zh/SBL/TWT60U`（有價證券借貸成交明細）多種參數組合實測皆回 **404**，正確端點**未能查證，需人工確認**。若需借券費率，走 FinMind。

### 2.4 當沖比

| 層級 | 端點 | 實測 |
|---|---|---|
| 上市大盤當沖比 | `https://www.twse.com.tw/rwd/zh/dayTrading/TWTB4U?date=20260731&response=json` | 200，第一張表即「當日沖銷交易統計資訊」：2026-07-31 當沖成交股數 **2,710,674 千股、占市場 19.62%**，買進金額占比 27.79%。實測 `date=20140102` 回 `查詢日期小於103年1月6日` → **歷史下限 2014-01-06** |
| 上市個股當沖 | 同上回應的第二張表 | 含個股當沖成交股數與買賣金額 |
| 上市 OpenAPI（**注意陷阱**） | `https://openapi.twse.com.tw/v1/exchangeReport/TWTB4U` | 200，但**只有 `Date/Code/Name/Suspension` 四欄** —— 這是「可否當沖」的標的名單，**不是**當沖量值統計。不要誤用 |
| 上櫃大盤當沖比 | `https://www.tpex.org.tw/openapi/v1/tpex_intraday_trading_statistics` | 200，**罕見地回傳整月逐日**（1150701 起），含 `DayTradingVolumeOfTheMarket` 百分比字串 |
| **建議** | FinMind `TaiwanStockDayTrading` | **2014-01-01** 起，涵蓋上市上櫃，標的名單盤前可得、量值約 21:30 更新 |

### 2.5 主力進出（券商分點）

- **官方無個股分點 API**。TWSE 分點資料在 [`bsr.twse.com.tw`](https://bsr.twse.com.tw/bshtm/)，需輸入驗證碼，**技術上只能繞驗證碼爬取 → 明確違反使用條款，不建議**。
- TPEx OpenAPI 只有排行類：`tpex_active_broker_volume`（熱門股券商進出排行）、`tpex_daily_broker1/2`（各券商當日營業金額）。
- FinMind `TaiwanStockTradingDailyReport`（台股分點資料表，2021-06-30 起）與 `TaiwanStockTradingDailyReportSecIdAgg`（券商分點統計，2021-06-30 起）皆為 **Sponsor 付費層**，專屬 endpoint 不走 `/api/v4/data`。
- **建議**：v1 不做分點主力；若要做，用外資／投信買賣超 + 融資融券變化 + 借券餘額組合成「籌碼面代理指標」，避開分點資料。

---

## 3. 基本面：逐項來源（含實測驗證）

### 3.1 季報／年報財務數字

| 來源 | 實測 |
|---|---|
| TWSE OpenAPI `opendata/t187ap06_L_ci`（綜合損益表，一般業） | 200，1046 筆，**`年度`／`季別` 分組後只有 `115-Q1` 一組** → **只有最新一季，零歷史** |
| 同系列 | `t187ap06_L_{basi,bd,fh,ins,mim}`（金融／證期／金控／保險／異業）、`t187ap07_L_*`（資產負債表）—— 依產業分表，欄位不同，整合時必須做產業別 schema 分派 |
| TPEx OpenAPI | `mopsfin_t187ap06_O_*` / `mopsfin_t187ap07_O_*`（上櫃）、`..._U_*`（興櫃） |
| **無現金流量表** | TWSE／TPEx OpenAPI **都沒有現金流量表**；只有損益表與資產負債表 |
| **建議** | FinMind `TaiwanStockFinancialStatements`（綜合損益表，**1990-03-01** 起）／`TaiwanStockBalanceSheet`（2011-12-01 起）／`TaiwanStockCashFlowsStatement`（**2008-06-01** 起），皆涵蓋上市／上櫃／興櫃 |

### 3.2 EPS

- TWSE OpenAPI 綜合損益表已含 `基本每股盈餘（元）`（實測 2330 115Q1 = **22.08**）。
- 產業彙總：`opendata/t187ap14_L`（上市公司各產業 EPS 統計）。
- 歷史序列走 FinMind 財報表（`type` 欄含 EPS 科目）。

### 3.3 月營收

| 來源 | 實測 |
|---|---|
| TWSE OpenAPI `opendata/t187ap05_L` | 200，1082 筆，**`資料年月` 分組只有 `11506` 一組** → 只有最新月。2330 當月營收 442,679,969 千元、YoY +67.87%、附「因先進製程產品需求增加所致」備註 |
| TWSE `opendata/t187ap05_P` | 公開發行公司（非上市）月營收 |
| TPEx `mopsfin_t187ap05_O`（上櫃）／`t187ap05_R`（興櫃） | 200，同樣只有最新月 |
| **建議** | FinMind `TaiwanStockMonthRevenue`，**2002-02-01** 起，涵蓋三市場 |

> **yfinance 完全沒有月營收。** 這是台股分析的核心指標之一，也是既有 skill 最大的空缺。

### 3.4 股利政策

| 來源 | 實測 |
|---|---|
| TWSE OpenAPI `opendata/t187ap45_L`（上市公司股利分派情形） | 200，1 MB，`股利年度` 分組：**114 年度 1110 筆、115 年度 36 筆** → 約當年度，非長期歷史。欄位極細（盈餘分配現金／資本公積現金／盈餘轉增資配股／董事會日／股東會日） |
| TPEx OpenAPI `mopsfin_t187ap39_O`（上櫃股利分派-董事會通過） | 200，2.3 MB，實測含 **107 年度**資料 → 上櫃這張表歷史反而較深 |
| **建議** | FinMind `TaiwanStockDividend`（股利政策表，**2005-05-01** 起，含員工紅利、盈餘／公積來源拆分、`StockExDividendTradingDate`） |

### 3.5 除權息日程與結果

| 用途 | 端點 | 實測 |
|---|---|---|
| 上市除權息**預告** | `https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL` | 200，含 `Exdividend`（息／權）、`StockDividendRatio`、`CashDividend`、`SubscriptionPricePerShare` |
| 上櫃除權息**預告** | `https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost` | 200 |
| 上櫃除權息**結果**（參考價） | `https://www.tpex.org.tw/openapi/v1/tpex_exright_daily` | 存在（未逐欄實測） |
| **建議** | FinMind `TaiwanStockDividendResult`（除權除息結果表，**2003-05-01** 起，含 `before_price`／`after_price`／`reference_price`） |

### 3.6 本益比／殖利率／股價淨值比

- 官方口徑：`https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL`，實測 2330（1150730）**PEratio 29.65 / DividendYield 1.00 / PBratio 9.71**。
- 歷史：FinMind `TaiwanStockPER`（**2005-10-01** 起，週一至五 18:00 更新）。
- **與 yfinance 口徑不同**（見 §5.4），前端顯示時務必標明資料來源與口徑。

---

## 4. 爬蟲風險評估

### 4.1 法律面：條款原文

**TWSE 使用條款**（<https://www.twse.com.tw/zh/terms/use.html>，2026-08-01 擷取）

> 【下載軟體或資料】非依臺灣證券交易所同意之方式或經臺灣證券交易所同意者，**禁止透過包括但不限於自動化裝置、指令碼、自動程式、蜘蛛程式、爬蟲程式或擷取程式等方式下載本網站之軟體或資料。**

> 【智慧財產權…】任何人除非事前取得台灣證券交易所或其他權利人之書面同意，不得逕自使用、修改、重製、公開播送、改作、散布、發行、公開發表…，**但臺灣證券交易所已授權「政府資料開放平臺」提供公眾使用之本網站資料，不在此限。**您如要引用或轉載本網站內容，請以適當方式清楚註明資料來源，並確保資料完整性，不得任意增刪。

**櫃買中心使用條款**（<https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html>，2026-08-01 擷取）—— 五、下載軟體或資料條款文字幾乎一字不差；七、智慧財產權亦有「但櫃檯買賣中心已授權『政府資料開放平臺』(http://data.gov.tw) 提供公眾使用之本網站資料，不在此限」。

### 4.2 由此推導出的分界線

| 存取路徑 | 法律定位 | 建議 |
|---|---|---|
| `openapi.twse.com.tw/v1/*`、`tpex.org.tw/openapi/v1/*`、data.gov.tw 上架資料集 | 落在「政府資料開放平臺」除外條款 → 適用[政府資料開放授權條款-第1版](https://data.gov.tw/license)：**不限目的（含商業）、免授權金、可重製散布改作、可再授權**，但**未盡顯名標示義務者視為自始未取得授權** | ✅ 可用於 public repo 與對外服務，**務必在頁面標註來源** |
| `www.twse.com.tw/rwd/zh/*`、`www.tpex.org.tw/www/zh-tw/*` 的 JSON | **不在**開放資料清單內 → 落入「禁止自動化程式下載」條款 | ⚠️ 高風險。不要放進定時排程；僅供人工／一次性研究 |
| `mops.twse.com.tw/mops/api/*` | 改版後 SPA 的內部 API，**無公開文件、無授權說明**（實測 `GET /mops/api/t05st09_2` 回 `{"code":406,"message":"查無相符資料"}`，參數格式須逆向） | ❌ 不使用。其內容已由 OpenAPI `t187apXX` 系列重新發布 |
| `bsr.twse.com.tw`（分點） | 有驗證碼保護 → 繞過屬明確規避技術措施 | ❌ 不碰 |

**robots.txt 與條款不一致**：TWSE `robots.txt` 只 `Disallow: /epaper/` 與 `/FTSE/`，其餘 `Allow: /`（含 `/rwd/`）；TPEx **無 robots.txt**（回 404）。但 robots.txt 是技術建議，使用條款是契約義務，**以條款為準**。

### 4.3 穩定性風險（已有實證）

1. **路徑漂移**：TWSE 2023 年改版把 `www.twse.com.tw/exchangeReport/...` 遷移到 `/rwd/zh/...`。data.gov.tw 上的資料集頁面（如 [dataset/11549](https://data.gov.tw/dataset/11549)）**至今仍寫舊路徑** `https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data` —— 官方文件與實際端點已不同步。
2. **官方文件連結本身會壞**：TPEx `swagger.json` 的 `info.description` 指向的使用條款連結 `https://www.tpex.org.tw/web/inc/gtsm_disclaimer.php?l=zh-tw` **實測 404**（正確為 `/zh-tw/gtsm_disclaimer.html`）。
3. **回應格式不一致**：TWSE `/rwd/` 端點有時回 `{"stat","fields","data"}`，有時回 `{"stat","tables":[...]}`（如 `MI_MARGN`、`TWTB4U` 一次回多張表）；錯誤時**回 HTTP 200 + HTML 404 頁面**（不是 4xx），parser 必須顯式檢查 `stat`。
4. **無版本化、無 rate limit 文件**：兩家 OpenAPI 的 swagger 皆 **0 個 query parameter**、**無 rate limit 說明**（**未能查證，需人工確認**），無從得知被限流的門檻。
5. **民國年 + 千分位字串**：所有官方端點回傳 `"1150731"`（民國）與 `"1,134,103"`（含逗號字串），必須集中做正規化層，否則錯誤會散落全專案。

### 4.4 建議架構

```
[官方 OpenAPI]  → 每日拉最新快照 → 當作「今日真值」與「對帳基準」
[FinMind]       → 拉歷史序列與回補    → 當作「時間序列倉庫」
[yfinance]      → 僅價格 K 線 + 個股財報（且需與 OpenAPI 對帳）
[/rwd/, MOPS]   → 不進排程；僅人工查證用
```
每日對帳：用 OpenAPI 當日快照校驗 FinMind 當日值，落差寫進 data quality log。

---

## 5. yfinance 對 `.TW` / `.TWO` 的涵蓋度與品質（實測報告）

實測 yfinance **v1.5.2**，2026-08-01，標的：`2330.TW`（台積電）、`2603.TW`（長榮）、`6488.TWO`（環球晶）、`00878.TW`（國泰永續高股息）、`2884.TW`（玉山金）、`2412.TW`（中華電）、`8069.TWO`（元太）、`9958.TW`（世紀鋼）、`6180.TWO`（橘子）、`00679B.TW`（元大美債20年）、`1258.TWO`。

yfinance 對台股沒有任何特殊處理 —— `yfinance/const.py` 中僅有 `'ROCO': 'TWO', 'XTAI': 'TW',  # Taiwan` 與 `'tw': {'TAI','TWO'}` 兩處，就是普通的交易所代碼對照。

### 5.1 ✅ 可信的欄位（實測有交叉驗證）

| 欄位 | 證據 |
|---|---|
| **日 K 線** | `2330.TW` `history(period="max")` 回 **6608 列，2000-01-04 ~ 2026-07-31**；`6488.TWO` 2859 列自 2014-10-30 |
| **季／年財報數字** | **與 TWSE OpenAPI 逐項吻合**。2330 2026Q1：<br>營收 yfinance `1,134,103,440,000` vs 官方 `1,134,103,440`（千元）✅<br>毛利 `751,295,421,000` vs `751,295,421` ✅<br>歸母淨利 `572,479,752,000` vs `572,479,752` ✅<br>基本 EPS `22.08` vs `22.08` ✅<br>（僅營業利益 `658,948,859` vs `658,966,142` 千元，差 0.003%，屬科目定義差異） |
| **現金股利序列** | 2330 44 筆自 2004-06-14；2603 17 筆自 2001-09-07；除息還原正確（2026-06-11 除息 6.0，除息前 `Adj Close` < `Close`，除息後兩者相等） |
| **股票股利／減資** | 以 `Stock Splits` 表達（2330 2004 年 1.1409 = 股票股利；2603 2022-09-07 的 `0.4` = 六成減資），價格還原方向正確 |
| **分析師預估** | `analyst_price_targets`、`earnings_estimate`、`recommendations` 對大型股有值且幣別標 `TWD`（2330：32 位分析師、目標價中位數 3160） |

### 5.2 ❌ 完全沒有的欄位

- **所有籌碼面**：三大法人、融資融券、借券、當沖、分點。實測列出 `Ticker` 全部公開屬性（96 個），無任何一項與台股籌碼相關。
- **月營收**：不存在。
- **除權息預告日程**：只有 `calendar['Ex-Dividend Date']` 一個未來日期，無完整表。

### 5.3 ⚠️ 存在但**不可信**的欄位

| 欄位 | 實測問題 |
|---|---|
| `institutional_holders` | 2330 只回 **1 筆「Pacer Advisors, Inc.」129,443 股、`pctHeld` = 0.0**；2603 直接空表。這是美股 13F 概念，對台股毫無意義 |
| `heldPercentInstitutions` / `major_holders` | 2330 顯示 **43.089%**，與台股實際外資持股比率不符（外資持股請改用 TWSE `fund/MI_QFIIS_*` 或 FinMind `TaiwanStockShareholding`） |
| ETF `funds_data`（00878.TW） | `top_holdings`／`sector_weightings` 看起來合理，但 **`Annual Report Expense Ratio` = 0.0（錯）**、**`equity_holdings` Price/Earnings = 0.053（錯，數量級不對）**、`categoryName` = None |
| ETF `info` 自相矛盾 | 00878.TW **`dividendYield` = 5.61 但 `trailingAnnualDividendYield` = 0.0**；`marketCap`／`sharesOutstanding`／`bookValue`／`exDividendDate` 全數缺漏；`info` 只有 88 key（個股為 153–172） |
| `insider_transactions` / `sustainability` | 全部標的皆回空 DataFrame |
| 停止買賣期間 | 2603.TW 2022-09-07 ~ 09-14（減資換發新股停止買賣）**仍產生 8 列 OHLC 全為 202.00 的資料列**，會污染波動率、報酬率與技術指標 |
| `earnings_dates` | 拋 `ImportError('Import lxml failed')`，需額外裝 `lxml` |

### 5.4 ⚠️ 缺漏與落後（資料完整性）

| 問題 | 實測 |
|---|---|
| **季報有洞** | 2330 `quarterly_income_stmt` 的 `Total Revenue` 在 **2025-03-31、2024-12-31 為 None**；`Basic EPS` 在 **2025-09-30 為 None**。`6488.TWO` **整個 2025Q3 那一欄不存在** |
| **最新季別落後不一** | 2330 已有 2026Q2，`6488.TWO` 最新只到 2026Q1 |
| **年報期數不一** | 2330 有 5 年，`2603.TW` 只有 4 年（2022–2025） |
| **金融股欄位大缺** | `2884.TW` 季報只有 **34 列**（一般業 45–57 列）—— IFRS 金融業表格套不進美式模板 |
| **債券 ETF 完全查無** | `00679B.TW` 回 `Quote not found for symbol`，`info` 只有 1 個 key。帶英文字尾的代碼（`00679B`、`00400A` 等）Yahoo 不收 |
| **冷門標的查無** | `1258.TWO` 回 `possibly delisted`，`info` 12 key |
| **本益比口徑不同** | yfinance `trailingPE` **32.93** / `trailingEps` **73.65**；TWSE `BWIBBU_ALL` 同期 `PEratio` **29.65**。`priceToBook` 9.78 vs 官方 `PBratio` 9.71（PB 較接近，PE 差 11%） |

### 5.5 授權風險

yfinance README「Legal Stuff」明文：

> yfinance is **not** affiliated, endorsed, or vetted by Yahoo, Inc. It's an open-source tool that uses Yahoo's publicly available APIs, and is intended for research and educational purposes. You should refer to Yahoo!'s terms of use … for details on your rights to use the actual data downloaded.

套件本身 Apache-2.0，但**資料端受 Yahoo 條款拘束**（其中明列 personal use）。本專案為 public repo，若對外提供服務，**不應把 yfinance 當作對外展示資料的唯一來源**。

### 5.6 對既有 stock-analysis skill 的結論

| 既有 skill 的能力 | 台股可沿用？ |
|---|---|
| 價格 K 線、報酬率、技術指標 | ✅ 可沿用，但需處理「停止買賣期間重複價格列」 |
| 財務比率（毛利率、營益率、ROE、負債比） | ✅ 數字準確，但**需容忍季報缺格**，且金融股要另走 OpenAPI 金融業表 |
| 現金股利、殖利率、除息還原 | ✅ 可沿用（現金股利）；股票股利要從 `Stock Splits` 反推 |
| 法人／機構持股分析 | ❌ **必須整段重寫**，改用 TWSE `MI_QFIIS_*` / FinMind |
| ETF 分析 | ❌ 費用率、PE、NAV 皆錯或缺；改用 TPEx／投信官網／FinMind |
| 月營收動能 | ❌ 完全沒有，需新建 |
| 籌碼面（三大法人／融資券／借券／當沖） | ❌ 完全沒有，需新建 |

---

## 6. 個股分析頁：每一類資料 → 建議來源對照表

| 分析頁區塊 | 資料類別 | 首選來源 | 校驗／備援 | 備註 |
|---|---|---|---|---|
| 價格走勢 | 日 K、成交量 | FinMind `TaiwanStockPrice`（1994-10-01 起） | TWSE OpenAPI `exchangeReport/STOCK_DAY_ALL`（當日）／yfinance | 停止買賣日需標記，勿補值 |
| 價格走勢 | 還原股價 | yfinance `history(auto_adjust=True)` | FinMind `TaiwanStockDividendResult` 自行還原 | 減資／股票股利以 `Stock Splits` 表達 |
| 估值 | PE／PB／殖利率 | TWSE `exchangeReport/BWIBBU_ALL`（當日，官方口徑） | FinMind `TaiwanStockPER`（2005-10 起歷史） | **不要用 yfinance `trailingPE`**，口徑不同 |
| 估值 | 市值 | FinMind `TaiwanStockMarketValue`（Backer 層） | yfinance `info['marketCap']`（個股尚可，ETF 缺） | |
| 基本面 | 綜合損益表 | FinMind `TaiwanStockFinancialStatements`（1990-03 起） | TWSE `opendata/t187ap06_L_*`／TPEx `mopsfin_t187ap06_O_*`（最新季，作對帳） | 產業別分表，需 schema 分派 |
| 基本面 | 資產負債表 | FinMind `TaiwanStockBalanceSheet`（2011-12 起） | TWSE `opendata/t187ap07_L_*` | |
| 基本面 | 現金流量表 | FinMind `TaiwanStockCashFlowsStatement`（2008-06 起） | **無官方 OpenAPI**；yfinance `quarterly_cashflow` 可交叉 | 官方 OpenAPI 缺這張表 |
| 基本面 | EPS | 財報表內 `基本每股盈餘` | TWSE `opendata/t187ap06_L_ci` 直接有欄位 | |
| 基本面 | **月營收** | FinMind `TaiwanStockMonthRevenue`（2002-02 起） | TWSE `opendata/t187ap05_L`／TPEx `mopsfin_t187ap05_O`（最新月） | yfinance 完全沒有；台股特色指標，優先度高 |
| 股利 | 股利政策（配息配股） | FinMind `TaiwanStockDividend`（2005-05 起） | TWSE `opendata/t187ap45_L`／TPEx `mopsfin_t187ap39_O` | 官方表欄位更細（公積 vs 盈餘來源） |
| 股利 | 除權息**預告日程** | TWSE `exchangeReport/TWT48U_ALL` + TPEx `tpex_exright_prepost` | yfinance `calendar['Ex-Dividend Date']`（僅下一次） | 這是官方 OpenAPI 少數勝過 FinMind 的地方（前瞻資料） |
| 股利 | 除權息**結果／參考價** | FinMind `TaiwanStockDividendResult`（2003-05 起） | TPEx `tpex_exright_daily` | |
| 籌碼 | 三大法人買賣超 | **FinMind `TaiwanStockInstitutionalInvestorsBuySell`**（2005-01 起，三市場） | TPEx `tpex_3insti_daily_trading`（當日快照）；**TWSE OpenAPI 無此表** | 上市歷史官方途徑僅 `/rwd/` T86（高風險） |
| 籌碼 | 融資融券餘額／使用率 | **FinMind `TaiwanStockMarginPurchaseShortSale`**（2001-01 起） | TWSE `exchangeReport/MI_MARGN` + TPEx `tpex_mainboard_margin_balance`（當日） | |
| 籌碼 | 借券賣出餘額 | TWSE `/rwd/` `TWT93U`（上市）+ TPEx `tpex_margin_sbl`（上櫃） | FinMind `TaiwanStockSecuritiesLending`（成交明細＋費率，2001-05 起） | 官方 OpenAPI 只有「可借券股數」`SBL/TWT96U`，非餘額 |
| 籌碼 | 當沖比 | **FinMind `TaiwanStockDayTrading`**（2014-01 起） | TWSE `/rwd/` `dayTrading/TWTB4U`；TPEx `tpex_intraday_trading_statistics`（含整月） | 勿誤用 TWSE OpenAPI `TWTB4U`（只是標的名單） |
| 籌碼 | 外資持股比率 | FinMind `TaiwanStockShareholding`（2004-02 起） | TWSE `fund/MI_QFIIS_cat`、`fund/MI_QFIIS_sort_20` | **勿用 yfinance `heldPercentInstitutions`** |
| 籌碼 | 股權分散（持股分級） | FinMind `TaiwanStockHoldingSharesPer`（Backer 層，2010-01 起） | — | 千張大戶指標的來源 |
| 籌碼 | 主力／分點 | FinMind `TaiwanStockTradingDailyReport`（**Sponsor 付費**，2021-06 起） | 無免費合法替代 | **v1 建議不做** |
| 公司資訊 | 基本資料、產業別 | TWSE `opendata/t187ap03_L` / TPEx `mopsfin_t187ap03_O` | FinMind `TaiwanStockInfo` | |
| 公司資訊 | 重大訊息 | TWSE `opendata/t187ap04_L` / TPEx `mopsfin_t187ap04_O` | — | 每日更新 |
| 公司資訊 | 董監持股、內部人轉讓 | TWSE `opendata/t187ap11_L`、`t187ap12_L`、`t187ap02_L` | — | |
| 風險標記 | 注意／處置股、變更交易 | TWSE `announcement/notice`、`announcement/punish`、`exchangeReport/TWT85U` | TPEx `tpex_trading_warning_information`、`tpex_disposal_information` | 分析頁應顯眼標示 |
| ETF 專頁 | 成分股、產業權重 | yfinance `funds_data`（**僅權重可參考**） | 投信官網 / TPEx | 費用率、PE 必須另找，yfinance 值是錯的 |
| ETF 專頁 | 配息紀錄 | yfinance `dividends`（00878 實測 23 筆自 2020-11 正確） | FinMind | |

---

## 7. 未能查證，需人工確認

1. **TWSE／TPEx OpenAPI 的速率限制**：兩家 swagger 皆無 rate limit 說明，官網亦未見公告。建議自行保守設定（例如 ≤ 1 req/sec）並監控 429/5xx。
2. **FinMind 付費方案價格**：贊助方案頁 `https://finmindtrade.com/analysis/#/Sponsor/sponsor` 為 SPA，無 JS 無法取得金額；搜尋到的數字均為二手部落格，**不採信**。需人工開瀏覽器確認。
3. **FinMind 資料再散布授權**：GitHub repo LICENSE 為 Apache-2.0（涵蓋**程式碼**），文件中未見對「資料本身」的授權聲明。若要把 FinMind 資料對外展示／散布，需先確認。
4. **TWSE 借券成交明細（TWT60U）的正確 JSON 端點**：多組參數組合實測皆 404。
5. **上櫃「個股」當沖成交量值的官方端點**：TPEx OpenAPI 只找到市場合計（`tpex_intraday_trading_statistics`）與標的資訊（`tpex_securities`），個股量值未實測到。
6. **交易所付費資訊服務費率**：TWSE 網路資訊商店／櫃買資訊購買的實際費率未查證。
7. **TPEx `/www/zh-tw/` 各端點的歷史下限**：僅實測 2026-07-31 可用，未逐一測試回溯上限。

---

## 8. 附錄：已實測可用的端點速查

> 全部於 2026-08-01 實測回應 HTTP 200 且內容正確。

**TWSE OpenAPI**（`https://openapi.twse.com.tw/v1`，僅最新快照，無參數）
```
/exchangeReport/STOCK_DAY_ALL      個股日成交
/exchangeReport/BWIBBU_ALL         個股 PE / 殖利率 / PB
/exchangeReport/MI_MARGN           融資融券餘額
/exchangeReport/TWTB4U             當沖「標的名單」(非量值)
/exchangeReport/TWT48U_ALL         除權除息預告表
/SBL/TWT96U                        當日可借券賣出股數 (含上櫃欄位)
/opendata/t187ap05_L               上市月營收 (最新月)
/opendata/t187ap06_L_{ci,fh,ins,bd,mim,basi}   綜合損益表 (最新季)
/opendata/t187ap07_L_{...}         資產負債表 (最新季)
/opendata/t187ap45_L               股利分派情形
/opendata/t187ap03_L               上市公司基本資料
/opendata/t187ap04_L               每日重大訊息
/fund/MI_QFIIS_cat, /fund/MI_QFIIS_sort_20     外資陸資持股
```

**TPEx OpenAPI**（`https://www.tpex.org.tw/openapi/v1`，僅最新快照，無參數）
```
/tpex_3insti_daily_trading         上櫃三大法人買賣明細
/tpex_mainboard_margin_balance     上櫃融資融券餘額
/tpex_margin_sbl                   上櫃融券借券賣出餘額
/tpex_intraday_trading_statistics  上櫃當沖統計 (回傳整月逐日)
/tpex_exright_prepost              除權息預告
/tpex_exright_daily                除權息計算結果
/tpex_mainboard_peratio_analysis   上櫃 PE / 殖利率 / PB
/mopsfin_t187ap05_O                上櫃月營收
/mopsfin_t187ap39_O                上櫃股利分派 (歷史較深)
/mopsfin_t187ap06_O_*, _07_O_*     上櫃財報
```

**FinMind**（`https://api.finmindtrade.com/api/v4/data`，600 req/hr with token）
```
TaiwanStockPrice / TaiwanStockPER / TaiwanStockMarketValue
TaiwanStockInstitutionalInvestorsBuySell / TaiwanStockMarginPurchaseShortSale
TaiwanStockSecuritiesLending / TaiwanStockDayTrading / TaiwanStockShareholding
TaiwanStockFinancialStatements / TaiwanStockBalanceSheet / TaiwanStockCashFlowsStatement
TaiwanStockMonthRevenue / TaiwanStockDividend / TaiwanStockDividendResult
用量查詢：GET https://api.web.finmindtrade.com/v2/user_info  (Authorization: Bearer <token>)
```

**⚠️ 高風險（受爬蟲禁止條款拘束，僅列為人工查證用）**
```
https://www.twse.com.tw/rwd/zh/fund/T86?date=&selectType=ALL&response=json          (≥2012-05-02)
https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate=&type=day&response=json
https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=&selectType=ALL&response=json
https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date=&response=json
https://www.twse.com.tw/rwd/zh/dayTrading/TWTB4U?date=&response=json                (≥2014-01-06)
https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date=&response=json
https://www.tpex.org.tw/www/zh-tw/margin/balance?date=&response=json
https://www.tpex.org.tw/www/zh-tw/margin/sbl?date=&response=json
```

---

## 9. 顯名標示範例（使用開放資料時必須放）

依[政府資料開放授權條款-第1版](https://data.gov.tw/license)，未盡顯名標示義務者「視為自始未取得開放資料之授權」。建議頁尾固定放：

> 本頁資料來源：臺灣證券交易所、財團法人中華民國證券櫃檯買賣中心（依政府資料開放授權條款-第1版釋出）。資料僅供參考，不構成投資建議。
