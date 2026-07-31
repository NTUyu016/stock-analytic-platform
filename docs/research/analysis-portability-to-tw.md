# 既有 stock-analysis skill 8 維度分析邏輯 —— 台股可移植性盤點

> 研究票：[#4](https://github.com/NTUyu016/stock-analytic-platform/issues/4)｜隸屬 wayfinder 地圖 [#1](https://github.com/NTUyu016/stock-analytic-platform/issues/1)
> 撰寫日期：2026-08-01
> 被研究對象：`~/.claude/skills/stock-analysis`（SKILL.md 標示 v5.0；`scripts/analyze_stock.py` 共 2504 行）
>
> **本文不做取捨。** 這裡只產出「現況清單 + 三分類 + 候選對應表」，「v1 要放哪幾維」屬於決策票 [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)。

---

## 0. 結論摘要

- 既有 8 維度中，**4 維（基本面、分析師情緒、動能、產業比較）可在改指數／改基準後沿用**；**2 維（財報意外、歷史財報型態）意外地能沿用 yfinance 既有資料**（實測台股大型股有 EPS 預估與實際值）；**1 維（大盤環境）需整組換成台股指標**；**1 維（市場情緒）的 5 個子指標中有 3 個必須換來源、1 個在美股版就是壞的、1 個台股無等價資料**。
- 逐指標看，真正「不適用／無台股等價」的只有 **put/call ratio（個股層級）** 與 **junk bond demand**；其餘全部找得到台股第一手替代來源。
- 情緒維度的核心發現：**`get_vix_term_structure()` 從頭到尾沒有抓期貨期限結構**（只用 VIX 現貨水準硬編碼分箱），且 **`get_put_call_ratio()` 因為讀取不存在的 `data.ticker_obj` 而永遠回傳 None** —— 這兩個「美股專屬」的移植難題，實際上有一個是幻覺、一個是死碼。
- 台股反而多出美股沒有的高頻資料：**每月營收（月頻基本面）、三大法人買賣超、融券／借券賣出餘額、當沖比、注意處置股、外資持股比率**，全部有證交所／期交所官方 OpenAPI。
- **地緣風險映射必須反轉**：既有邏輯是「台海緊張 → 美國半導體股扣分」，把標的換成台股後，台海風險變成**整個市場的系統性因子**而非單一類股因子，須改成大盤層級的風險開關 + 出口／內需的相對曝險分層。

---

## 1. 方法與範圍

**第一部分（指標清單）**：逐行閱讀 `analyze_stock.py`（2504 行）、`SKILL.md`、`TODO.md`，指標定位精確到函式與行號。此部分不涉及網路查證。

**第二部分（台股替代查證）**：只採信第一手來源（證交所 / 櫃買中心 / 期交所 / 原始學術資料網站），每個宣稱附可點擊 URL。凡查不到現況者一律標註「未能查證」。

**額外實測**：以 `uv` 執行 yfinance，實地測試 `2330.TW`、`2317.TW`、`2603.TW`、`6488.TWO`、`00878.TW` 與對照組 `AAPL`，逐一檢查 `analyze_stock.py` 實際讀取的每個欄位是否存在。同時以 `curl` 直接打證交所 / 櫃買 OpenAPI 端點確認欄位形狀（本文標示「實測」者均指此）。

---

## 2. 現有指標完整清單（含程式碼位置）

所有行號皆指 `~/.claude/skills/stock-analysis/scripts/analyze_stock.py`。

### 2.0 資料取得層

| 項目 | 程式碼位置 | 來源 | 說明 |
|---|---|---|---|
| 主資料抓取 | `fetch_stock_data()` L230–286 | `yfinance` | 3 次重試 + 指數退避；抓 `stock.info`、`stock.earnings_dates`、`stock.recommendations`、`stock.analyst_price_targets`、`stock.history(period="1y")` |
| ticker 有效性判定 | L242 | `info["regularMarketPrice"]` 是否存在 | |
| 資產類型判定 | `detect_asset_type()` L65–72 | ticker 以 `-USD` 結尾即視為 crypto | |
| 快取 | `_get_cached()` / `_set_cache()` L1303–1314 | 行程內 dict，TTL 3600 秒（L1300） | 只快取 market_context、breaking_news、fear_greed、vix_structure |
| 宣告相依 | L2–11 | `yfinance`、`pandas`、`fear-and-greed`、`edgartools`、`feedparser` | **未宣告 `lxml`**，見 §6 缺陷 D5 |

### 2.1 維度一：Earnings Surprise（權重 0.30）

`analyze_earnings_surprise()` **L289–335**

| 指標 | 來源欄位 | 計算方式 | 評分 |
|---|---|---|---|
| EPS 意外幅度 | `stock.earnings_dates` 的 `Reported EPS`、`EPS Estimate`（L299） | `surprise_pct = (actual - expected) / abs(expected) * 100`（L306） | >10%→1.0；>5%→0.7；>0→0.3；>-5%→-0.3；>-10%→-0.7；else -1.0（L309–320） |

取最近 10 筆中第一筆兩欄皆非 NaN 者（L296–299）；`expected == 0` 則跳過（L303）。
註：SKILL.md L105 宣稱含「revenue beats/misses」，**程式碼並未實作營收意外**。

### 2.2 維度二：Fundamentals（權重 0.20）

`analyze_fundamentals()` **L338–409**（crypto 走 `analyze_crypto_fundamentals()` L412–503）

| 指標 | `stock.info` 欄位 | 門檻與評分 | 行號 |
|---|---|---|---|
| 本益比 | `trailingPE` 或 `forwardPE` | <15→+0.5；>30→-0.3；否則 +0.1 | L347–357 |
| 營業利益率 | `operatingMargins` | >0.15→+0.5；<0.05→-0.5 | L360–368 |
| 營收年增率 | `revenueGrowth` | >0.20→+0.5；<0.05→-0.3；否則 +0.2 | L371–381 |
| 負債權益比 | `debtToEquity` | <50→+0.3；>200→-0.5 | L384–391 |

最終取算術平均後夾在 [-1, 1]（L397–398）。
Crypto 版（L412–503）改用 `marketCap` 分級、`volume/marketCap` 換手率、`circulatingSupply`、硬編碼的 `CRYPTO_CATEGORIES`（L41–62）、對 BTC 的 30 日報酬相關係數（L456–466）。

### 2.3 維度三：Analyst Sentiment（權重 0.20）

`analyze_analyst_sentiment()` **L506–576**

| 指標 | 欄位 | 用法 | 行號 |
|---|---|---|---|
| 共識評等 | `recommendationKey` | 映射 `strong_buy`1.0 / `buy`0.7 / `hold`0 / `sell`-0.7 / `strong_sell`-1.0 | L523, L535–543 |
| 目標價上檔空間 | `targetMeanPrice` vs `regularMarketPrice` | `upside_pct = (target - price)/price*100` | L517, L532 |
| 分析師家數 | `numberOfAnalystOpinions` | 僅顯示於文字，不計分 | L520 |

上檔空間調整：>20%→+0.3；>10%→+0.15；<-10%→-0.3（L546–551）。

### 2.4 維度四：Historical Patterns（權重 0.10）

`analyze_historical_patterns()` **L579–650**

| 指標 | 來源 | 計算 | 行號 |
|---|---|---|---|
| 近 4 季擊敗預期次數 | `earnings_dates` 前 4 列 | `actual > expected` 計數 | L589–600 |
| 財報當日股價反應 | `price_history` 中財報當日的 `(Close-Open)/Open` | 平均值，僅顯示 | L603–611, L637 |

beat rate 評分：1.0→0.8；≥0.75→0.5；≥0.5→0；≥0.25→-0.5；else -0.8（L622–631）。

### 2.5 維度五：Market Context（權重 0.10）

`analyze_market_context()` **L653–795**（**全市場共用、與個股無關**，1 小時快取）

| 指標 | ticker | 計算 | 評分 | 行號 |
|---|---|---|---|---|
| VIX 水準 | `^VIX` | `info.regularMarketPrice` | <20 calm +0.2；<30 elevated 0；≥30 fear -0.5 | L667, L679–687 |
| S&P 500 10 日趨勢 | `SPY` | `history("1mo")` 最新 vs 倒數第 10 筆 | — | L690–699 |
| Nasdaq 100 10 日趨勢 | `QQQ` | 同上 | — | L701–703 |
| 市場情境 | SPY/QQQ 平均 | >3% bull +0.3；<-3% bear -0.4；否則 choppy -0.1 | L706–716 |
| 黃金 5 日漲跌 | `GLD` | `history("10d")` | risk-off 判定用 | L732, L741–744 |
| 長天期公債 5 日漲跌 | `TLT` | 同上 | 同上 | L733, L746–749 |
| 美元指數 5 日漲跌 | `UUP` | 同上 | 同上 | L734, L751–754 |
| Risk-off 偵測 | GLD≥+2% 且 TLT≥+1% 且 UUP≥+1% | 布林 | 總分再 -0.5 | L757–761 |

維度總分 = `(vix_score + regime_score) / 2`，再視 risk-off 扣 0.5（L719, L761）。

### 2.6 維度六：Sector Performance（權重 0.15）

`analyze_sector_performance()` **L1017–1101**；映射表 `get_sector_etf_ticker()` **L798–815**

| 指標 | 來源 | 計算 | 行號 |
|---|---|---|---|
| 類股 ETF 對照 | `info["sector"]` → 12 檔 SPDR 類股 ETF（XLF/XLK/XLV/XLY/XLP/XLU/XLB/XLRE/XLC/XLI/XLE） | 硬編碼字典 | L800–813 |
| 個股 1 月報酬 | `price_history` 倒數第 22 筆 vs 最新 | 百分比 | L1044–1046 |
| 類股 1 月報酬 | 類股 ETF `history("3mo")` 倒數第 22 筆 | 百分比 | L1048–1050 |
| 相對強度 | `stock_return_1m / sector_return_1m` | **除法**（見缺陷 D3） | L1053 |
| 類股 10 日趨勢 | 類股 ETF | >5% strong uptrend … <-5% downtrend | L1056–1068 |

評分：相對強度 >1.05 →+0.3、<0.95 →-0.3；類股 10 日 >5% →+0.2、<-5% →-0.2（L1074–1083）。

### 2.7 維度七：Momentum（權重 0.15）

`analyze_momentum()` **L1207–1290**；`calculate_rsi()` **L1178–1204**

| 指標 | 來源 | 計算 | 評分 | 行號 |
|---|---|---|---|---|
| RSI(14) | `price_history["Close"]` | **簡單移動平均**版 RSI（非 Wilder 平滑，L1192–1199） | >70 →-0.5；<30 →+0.5 | L1214, L1256–1262 |
| 52 週區間位置 | `info.fiftyTwoWeekHigh` / `fiftyTwoWeekLow` | `(price-low)/(high-low)*100` | >90 近高 -0.3；<10 近低 +0.3 | L1227–1243, L1264–1269 |
| 量能比 | `price_history["Volume"]` | 近 5 日均量 / 近 60 日均量 | 僅顯示，>1.5 提示 | L1247–1250, L1271–1272 |
| 相對強度 vs 類股 | — | **硬寫 None，未實作** | — | L1284 |

### 2.8 維度八：Sentiment Analysis（權重 0.10，5 子指標並行）

`analyze_sentiment()` **L1615–1756**（`asyncio.gather` + 每項 10 秒逾時 L1649–1656；**至少要 2/5 可用** L1726）

| # | 子指標 | 函式 | 資料來源 | 計算 / 評分 |
|---|---|---|---|---|
| 1 | CNN Fear & Greed | `get_fear_greed_index()` L1317–1359 | `fear_and_greed` 套件（抓 CNN） | 反向：≤25→+0.5；≤45→+0.2；≤55→0；≤75→-0.2；else -0.5（L1345–1353） |
| 2 | 放空比例 | `get_short_interest()` L1362–1392 | `info["shortPercentOfFloat"]`、`info["shortRatio"]` | >20% 且 days-to-cover>10 →+0.4；>20% 否則 -0.3；<5% →+0.2（L1380–1388） |
| 3 | VIX 期限結構 | `get_vix_term_structure()` L1395–1443 | **只有 `^VIX` 現貨**（L1408–1412） | 依現貨水準硬編碼 structure/slope：<15 contango +0.3；<20 +0.1；>30 backwardation -0.3；else 0（L1422–1437）。**並未讀任何期貨** |
| 4 | 內部人交易 | `get_insider_activity()` L1446–1560 | SEC EDGAR Form 4（`edgartools`，identity 設於 L1466） | 近 90 天、最多 50 筆 filing；彙總 `common_stock_purchases` / `common_stock_sales` 股數與金額（L1512–1527）；淨買 >10 萬股或 >$1M →+0.8 … 淨賣 <-10 萬股或 <-$1M →-0.8（L1537–1546） |
| 5 | Put/Call Ratio | `get_put_call_ratio()` L1563–1612 | `data.ticker_obj.option_chain()` | **`StockData`（L75–82）沒有 `ticker_obj` 欄位 → AttributeError → 永遠回傳 None**（缺陷 D1）。設計評分為反向：>1.5→+0.3；>1.0→+0.1；>0.7→-0.1；else -0.3 |

維度總分 = 可用子指標分數的算術平均（L1732）。

### 2.9 非維度的訊號調節器

| 調節器 | 程式碼位置 | 資料來源 | 效果 |
|---|---|---|---|
| 財報時點 | `analyze_earnings_timing()` L1104–1175 | `earnings_dates` 索引 | 距財報 ≤14 天 → confidence ×0.7 且 BUY 降 HOLD（L1144–1147, L1850–1852）；財報後 5 天內漲逾 15% → BUY 降 HOLD（L1151–1161, L1854–1857） |
| 超買防呆 | L1860–1863 | RSI>70 且近 52 週高 | BUY→HOLD，confidence ×0.7 |
| Risk-off 罰則 | L1866–1868 | GLD/TLT/UUP | BUY confidence ×0.7 |
| 突發新聞 | `check_breaking_news()` L871–951 | **Google News RSS**（英文查詢字串 L893–894），24 小時內，比對 `CRISIS_KEYWORDS`（L823–829，5 類約 27 個英文關鍵字） | 最多 3 則，1 小時快取，輸出至 caveats |
| 地緣風險映射 | `check_sector_geopolitical_risk()` L954–1014 + `GEOPOLITICAL_RISK_MAP` L832–868 | 上述新聞標題文字比對 | ticker 命中名單 → confidence ×0.7（L996）；只有 sector 命中 → ×0.85（L1007） |
| 綜合權重 | `synthesize_signal()` L1759–2059 | — | 權重 L1781–1812；缺項自動正規化 L1829–1830；BUY>0.33 / SELL<-0.33（L1836–1841）；至少 2 個維度才給訊號（L1815） |

`GEOPOLITICAL_RISK_MAP`（L832–868）含 5 個事件：`taiwan`（keywords: taiwan / tsmc / strait → sectors: Technology, Communication Services → tickers: NVDA/AMD/TSM/INTC/QCOM/AVGO/MU）、`china`、`russia_ukraine`、`middle_east`、`banking_crisis`。

### 2.10 投組層（非分析維度）

`generate_portfolio_summary()` L2354–2423、`calculate_portfolio_period_return()` L2426–2455、`print_portfolio_summary()` L2458–2500：總成本 / 現值 / 損益、期間報酬（daily…yearly，L2386–2392）、單一資產 >30% 集中度警告（L2402）。全部只靠 `yfinance` 價格 → 天然可移植。

---

## 3. 三分類總表

分類定義：**可直接沿用**＝概念與資料來源都能原封不動用於台股（最多改 ticker 後綴）；**需替代**＝概念通用但資料來源／基準／語義必須換掉；**不適用**＝美股或美國制度專屬，台股無對等物。

| # | 指標 | 程式碼位置 | 分類 | 理由（含實測結果） |
|---|---|---|---|---|
| 1 | EPS 意外（actual vs estimate） | L289–335 | **可直接沿用** | 實測 `2330.TW`／`2317.TW`／`2603.TW`／`6488.TWO` 的 `earnings_dates` 皆有 25 列且含 `EPS Estimate`＋`Reported EPS`（例：2330.TW 2026-07-16 預估 24.23、實際 27.25、+12.48%） |
| 2 | 近 4 季 beat rate | L579–650 | **可直接沿用** | 同上資料 |
| 3 | 財報當日股價反應 | L603–611 | **可直接沿用** | 但台股 ±10% 漲跌幅限制會截斷單日反應（見 §7.3） |
| 4 | 財報時點（前 14 / 後 5 日） | L1104–1175 | **可直接沿用** | `earnings_dates` 含未來一筆預估日（實測 2330.TW 首列 2026-10-15）；台股財報法定期限與美股不同，門檻需重調 |
| 5 | 本益比 | L347 | **可直接沿用**（另有更好的官方源） | yfinance 有值；證交所 `BWIBBU_ALL` 另提供官方本益比／殖利率／股價淨值比 |
| 6 | 營業利益率 | L360 | **可直接沿用** | 實測 2330.TW = 0.603、2317.TW = 0.0357 |
| 7 | 營收年增率 | L371 | **可直接沿用**（可再強化） | 實測皆有值；台股另有月營收可做更高頻版本（§7.2 I） |
| 8 | 負債權益比 | L384 | **可直接沿用** | 實測 2330.TW = 15.17 |
| 9 | 分析師共識評等 | L523 | **可直接沿用（覆蓋率有風險）** | 2330.TW = `strong_buy`、6488.TWO = `buy`、2317.TW = `buy`，但 **2603.TW = `'none'`**（有 9 位分析師卻無評等）、ETF 00878.TW 全空 |
| 10 | 目標價上檔空間 | L517 | **可直接沿用（覆蓋率有風險）** | 2330.TW mean = 3117.26（35 位）、2317.TW = 314.35（17 位）；ETF 無 |
| 11 | RSI(14) | L1178–1204 | **可直接沿用** | 純價格計算 |
| 12 | 52 週高低位置 | L1227–1243 | **可直接沿用** | 實測台股 `fiftyTwoWeekHigh/Low` 皆有值 |
| 13 | 量能比（5 日 / 60 日） | L1247–1250 | **可直接沿用** | 純成交量計算 |
| 14 | 投組損益／期間報酬／集中度 | L2354–2500 | **可直接沿用** | 只用價格 |
| 15 | 類股相對強度 | L1017–1101 | **需替代** | 基準 XLK/XLF… 是美股 ETF；台股需換成證交所產業類指數（§4.5） |
| 16 | 類股趨勢 | L1056–1068 | **需替代** | 同上 |
| 17 | VIX 水準 | L667–687 | **需替代** | 換成期交所 TAIWAN VIX（§4.2） |
| 18 | SPY 10 日趨勢 | L690–699 | **需替代** | 換成加權指數（`^TWII` 或證交所指數端點） |
| 19 | QQQ 10 日趨勢 | L701–703 | **需替代** | 換成半導體類指數／櫃買指數（`^TWOII`） |
| 20 | GLD/TLT/UUP risk-off | L732–761 | **需替代** | 台幣資產的避風港組合不同（§4.7） |
| 21 | CNN Fear & Greed | L1317–1359 | **需替代** | 台股無官方等價指數，需民間指數或自建（§4.1） |
| 22 | 放空比例 `shortPercentOfFloat` | L1362–1392 | **需替代** | **實測台股全部為 `None`**（對照 AAPL = 0.01）；台股改用融券／借券賣出餘額（§4.6） |
| 23 | days to cover `shortRatio` | L1376 | **需替代** | 實測台股 `None`（對照 AAPL = 2.28）；需自算 |
| 24 | VIX 期限結構 | L1395–1443 | **需替代（且原實作是幻覺）** | 台灣無 VIX 期貨；但原碼本來就只用現貨，等價替換即可（§4.3） |
| 25 | SEC Form 4 內部人 | L1446–1560 | **需替代** | 換成證交所「內部人持股轉讓事前申報」，但語義不對稱（§4.4） |
| 26 | Google News RSS 突發新聞 | L871–951 | **需替代** | 英文查詢＋英文關鍵字；需中文新聞源＋證交所重大訊息（§4.8） |
| 27 | 地緣風險 → 類股映射 | L832–1014 | **需替代（且需反轉）** | 見 §5 |
| 28 | Put/Call Ratio（個股選擇權） | L1563–1612 | **不適用** | **實測台股 `Ticker.options` 皆為空 tuple**（對照 AAPL 有 3 個以上到期日）；台灣個股選擇權流動性遠低於指數選擇權。**但指數層級的 TXO P/C ratio 可用**（§4.6、§7.2 T） |
| 29 | Crypto 全套（分類、BTC 相關性等） | L412–503, L2213–2238 | **不適用（超出台股範疇）** | 屬另一資產類別 |
| 30 | 垃圾債利差（F&G 子元件） | 隱含於 #21 | **不適用** | 未能查證到台灣公開日頻高收益債利差來源 |

**8 維度存活統計**：完全沿用 3 維（財報意外、歷史型態、動能）＋ 換基準後沿用 2 維（基本面、分析師）＋ 必須整組換來源 2 維（大盤環境、產業比較）＋ 需重建 1 維（市場情緒，5 個子指標中僅結構可保留）。

---

## 4. 「需替代」指標的台股候選對應

### 4.1 CNN Fear & Greed Index → 台股市場情緒

**查證結果：台灣沒有官方編製的恐懼貪婪指數。** 候選如下（不做取捨）：

| 候選 | 提供者 | 性質 | 取得方式 | 來源 |
|---|---|---|---|---|
| MM 台灣恐懼與貪婪指數 | MacroMicro 財經 M 平方（民間） | 0–100，依股價表現、下跌幅度、波動率、寬幅編製 | 網頁；**是否有免費 API 未能查證** | https://www.macromicro.me/series/46964/taiwan-mm-fear-and-greed-index |
| 國泰金「國民經濟信心調查」股市樂觀指數／風險偏好指數 | 國泰金控（民間） | 月頻問卷 | 新聞稿／PDF，**無 API** | https://www.cathayholdings.com/holdings/information-centre/intro/gdp_news/index |
| 自建台股版（仿 CNN 七元件） | 自行計算 | 見下表 | 全部第一手官方資料 | 見下表 |

**自建台股版的元件可得性（逐一查證）**：

| CNN 原元件 | 台股對應 | 官方來源 | 狀態 |
|---|---|---|---|
| 股價動能（指數 vs 125 日均線） | 加權指數 vs 125 日均線 | 證交所 `/indicesReport/MI_5MINS_HIST`（發行量加權股價指數歷史資料）或 yfinance `^TWII` | 可得 |
| 股價強度（52 週新高／新低家數） | 同概念 | **未能查證到證交所官方日頻端點**（143 個 OpenAPI 端點中無此項） | 需自建（用日 K 自算） |
| 股價廣度 | 漲跌家數統計 | 證交所 `/opendata/twtazu_od`（集中市場漲跌證券數統計表）—— **實測回傳「出表日期 1150605」，落後約 2 個月**；日頻版見 https://www.twse.com.tw/zh/trading/historical/mi-index.html | OpenAPI 版有時效性問題 |
| Put/Call Ratio | 臺指選擇權 Put/Call Ratio | 期交所 https://www.taifex.com.tw/cht/3/pcRatio （含賣權／買權成交量、買賣權成交量比率%、賣權／買權未平倉量、買賣權未平倉量比率%，可 Excel 匯出）；政府資料開放平臺 https://data.gov.tw/dataset/11322 | 可得 |
| 市場波動（VIX） | TAIWAN VIX | 期交所 https://www.taifex.com.tw/cht/7/vixQA | 可得 |
| 避險需求（股 vs 債 20 日報酬） | 台股 vs 台債 ETF | 無官方指數，可用台債 ETF 價格自算 | 需自建 |
| 垃圾債需求 | — | 台灣無公開日頻高收益債利差 | **未能查證到來源** |

→ 自建版最多可還原 **5/7 元件**。

### 4.2 VIX 水準 → TAIWAN VIX

- **臺指選擇權波動率指數（TAIWAN VIX）**：期交所 2006-12-18 推出，官方說明「參考 CBOE VIX 指數方法，及臺指選擇權(TXO)市場特性編製」，採 TXO 近月及次近月契約波動率插補計算，**09:00:00 起每 15 秒揭示 1 次至 13:45:00**。
  來源：https://www.taifex.com.tw/cht/7/vixQA ｜編製手冊 PDF：https://www.taifex.com.tw/file/taifex/CHINESE/files/7/VIX_book.pdf
- 免費下載（期交所官網）：當月 https://www.taifex.com.tw/cht/7/vixMinNew ｜前 3 個月每日收盤 https://www.taifex.com.tw/cht/7/vixDaily3MNew
- 即時行情：https://mis.taifex.com.tw/futures/VolatilityQuotes/
- **是否有官方 REST API：未能查證**（VIX 頁面未載明）。付費管道為期交所「期貨智慧資訊商店」：https://edatashop.taifex.com.tw/zh/product/detail/40283ab7890b3664018924255bf2000f
- 分箱門檻不可照抄美股（20/30）——TAIWAN VIX 的歷史分布與 CBOE VIX 不同，門檻須以台股自身分位數重訂。

### 4.3 VIX 期限結構 → 台指期正逆價差 / TXO 近次月 IV 價差

- **台灣沒有 VIX 期貨或選擇權**：期交所說明 VIX 指數特性較複雜，目前尚未推出相關衍生性商品，故 contango/backwardation 無法直接複製。來源：https://www.taifex.com.tw/cht/7/vixQA
- 候選替代（皆為第一手期交所資料）：
  1. **台指期近月／次月價差（正逆價差）**：https://www.taifex.com.tw/cht/3/futDailyMarketReport
  2. **TXO 近月 vs 次近月隱含波動率差**（需自下載後自算）：https://www.taifex.com.tw/cht/3/optDailyMarketView
  3. **TXO 未平倉量 Put/Call 比**：https://www.taifex.com.tw/cht/3/pcRatio
- **重要提醒**：既有 `get_vix_term_structure()`（L1395–1443）根本沒抓期貨，只是把 `^VIX` 現貨再分箱一次，與維度五的 `vix_score`（L679–687）**重複計算同一變數**。台股版直接以 TAIWAN VIX 現貨替換即等價，且可順手修掉此重複。

### 4.4 SEC Form 4 → 內部人持股轉讓事前申報

**已第一手驗證的證交所 OpenAPI 端點**（base：`https://openapi.twse.com.tw/v1`）：

| 端點 | 名稱 | 實測回傳欄位（節錄） |
|---|---|---|
| `/opendata/t187ap12_L` | 上市公司每日內部人持股轉讓事前申報表-**持股轉讓**日報表 | 出表日期、公司代號、公司名稱、申報人身分、姓名、預定轉讓方式及股數-轉讓方式／轉讓股數、每日於盤中交易最大得轉讓股數、受讓人、目前持有股數-自有持股／保留運用決定權信託股數、預定轉讓總股數、預定轉讓後持股、有效轉讓期間 |
| `/opendata/t187ap13_L` | 同上-**持股未轉讓**日報表 | 申報後未實際轉讓者 |
| `/opendata/t187ap11_L` | 上市公司董監事持股餘額明細資料 | 月頻持股餘額 |
| `/opendata/t187ap02_L` | 上市公司持股逾 10% 大股東名單 | |
| `/opendata/t187ap09_L` | 董監事質權設定占實際持有股數彙總表 | 質押比，台股特有風險訊號 |

Swagger 入口：https://openapi.twse.com.tw/ ｜上櫃版：https://www.tpex.org.tw/openapi/ ｜原始揭露平台（公開資訊觀測站）：https://mops.twse.com.tw/

**語義差異（移植時最大的坑）**：
1. 台灣是**事前申報預定轉讓**，非美國 Form 4 的「成交後 2 個交易日內申報」→ 拿到的是**意向**而非成交事實；`t187ap13_L`（申報後未轉讓）正是補這個落差用的。
2. 台灣制度**只涵蓋「轉讓（賣出）」方向**，沒有對稱的「內部人買進」日報表 → **無法計算 `net_shares = bought − sold`**（L1533），既有淨額邏輯必須改寫成單邊的「賣壓強度」訊號。
3. 內部人買進只能由 `t187ap11_L` 董監持股餘額的**月變動**間接推得，頻率與精度皆低於 Form 4。

### 4.5 美股類股 ETF（XLE/XLF…）→ 證交所產業類指數

**已第一手驗證**：`GET https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX` 單次回傳 267 檔指數，其中**產業類指數 37 檔**：

> 水泥窯製、塑膠化工、機電、水泥、食品、塑膠、紡織纖維、電機機械、電器電纜、化學生技醫療、化學、生技醫療、玻璃陶瓷、造紙、鋼鐵、橡膠、汽車、電子工業、**半導體**、電腦及週邊設備、光電、通信網路、電子零組件、電子通路、資訊服務、其他電子、建材營造、航運、觀光餐旅、金融保險、貿易百貨、油電燃氣、綠能環保、數位雲端、運動休閒、居家生活、其他（皆為「〜類指數」）

- 每日（僅最新一日）：https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX
- **歷史查詢**（已實測 `date=20260630&type=IND` 可取回當日全部類指數）：`https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=YYYYMMDD&type=IND&response=json`
- 其他可用基準：`/indicesReport/TAI50I`（臺灣 50 指數歷史）、`/indicesReport/FRMSA`（寶島股價指數）、`/indicesReport/MI_5MINS_HIST`（加權指數歷史）、`/indicesReport/MFI94U`（加權股價**報酬**指數，含息，做長期相對強度較正確）
- **對照關係是主要工作量**：yfinance 給台股的 `sector` 仍是 GICS 英文分類（實測 2330.TW → `Technology`/`Semiconductors`、2603.TW → `Industrials`/`Marine Shipping`），與證交所產業別（`/opendata/t187ap03_L`、`/opendata/t187ap05_L` 的「產業別」欄，如「水泥工業」）**不是一對一**，需自建映射表。
- 櫃買（上櫃）需另走櫃買 OpenAPI：https://www.tpex.org.tw/openapi/ （已實測 `tpex_mainboard_daily_close_quotes` 回 200 且含 Close/Open/High/Low/TradingShares 等欄位）

### 4.6 放空比例 → 融券餘額 / 借券賣出餘額

**實測前提**：`shortPercentOfFloat` 與 `shortRatio` 在 2330.TW／2317.TW／2603.TW／6488.TWO **全為 `None`**（對照 AAPL 為 0.01 與 2.28）。此路完全不通。

**已第一手驗證的台股替代**：

| 資料 | 端點 | 實測欄位 |
|---|---|---|
| 融資融券餘額（個股日頻） | `https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN` | 股票代號、名稱、融資買進／賣出／現金償還／前日餘額／**今日餘額**／限額、融券買進／賣出／現券償還／前日餘額／**今日餘額**／限額、資券互抵、註記 |
| 融券＋**借券賣出餘額**（信用額度總量管制餘額表） | `https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date=YYYYMMDD&response=json` | 融券：前日餘額／賣出／買進／現券／**今日餘額**／次一營業日限額；借券：**前日餘額／當日賣出／當日還券／當日調整／當日餘額**／次一營業日可限額 |
| 當日可借券賣出股數 | `https://openapi.twse.com.tw/v1/SBL/TWT96U` | 借券賣出上限 |
| 停資停券預告 | `https://openapi.twse.com.tw/v1/exchangeReport/BFI84U` | 除權息／股東會前信用交易停止，導致融券強制回補（軋空事件源） |
| 借券資訊總覽（網頁） | https://www.twse.com.tw/zh/page/trading/exchange/TWT72U.html | |

**可導出的台股版指標（皆需自算）**：
- 「空方比例」≈ (融券今日餘額 + 借券賣出餘額) / 發行股數（發行股數見 `/opendata/t187ap03_L` 或 yfinance `sharesOutstanding`）
- 「days to cover」≈ 上式分子 / 近 N 日均量（均量自 `/exchangeReport/STOCK_DAY_ALL` 或 yfinance 日 K）
- 台股特有：**券資比**（融券／融資餘額）、**資券相抵（當沖）**，美股無對應概念
- **語義差異**：融券受漲跌幅、平盤下放空限制、除權息／股東會強制回補等制度約束，水準與美股 short interest 不可直接比較，原碼門檻（20% / 5%）必須重訂。

### 4.7 GLD / TLT / UUP risk-off → 台幣資產版避風港

原邏輯是「美元資產避險三件套」。台股投資人的避險流向不同，候選（**本次未做量化驗證，僅列候選**）：

| 原指標 | 台股版候選 | 取得 |
|---|---|---|
| GLD（黃金） | 可沿用黃金，或改新台幣計價黃金 | yfinance `GLD`／`GC=F` |
| TLT（美長債） | 台灣公債殖利率／台債 ETF | yfinance 台股 ETF；中央銀行 https://www.cbc.gov.tw/ |
| UUP（美元指數） | **USD/TWD 匯率** —— 外資流向的直接反映，台幣貶值常伴隨外資賣超 | yfinance `TWD=X`；央行牌告 |
| （新增）外資期貨淨部位 | 期交所三大法人台指期未平倉 | https://www.taifex.com.tw/cht/3/callsAndPutsDate |
| （新增）外資現貨買賣超 | 證交所三大法人買賣超日報 | `https://www.twse.com.tw/rwd/zh/fund/T86?date=YYYYMMDD&selectType=ALL&response=json`（已實測 200 OK） |

### 4.8 Google News RSS 突發新聞 → 中文新聞源 + 重大訊息

- 現況：查詢字串（L893–894）為 `stock+market`、`economy+crisis`，參數 `hl=en-US&gl=US&ceid=US:en`，關鍵字表（L823–829）全英文 → 對台股完全失效。
- 候選：
  1. Google News RSS 改中文參數（`hl=zh-TW&gl=TW&ceid=TW:zh-Hant`）＋中文關鍵字表；既有 feedparser 程式結構可原封不動沿用。
  2. **證交所「上市公司每日重大訊息」**：`https://openapi.twse.com.tw/v1/opendata/t187ap04_L` —— 官方、結構化、個股層級，比新聞關鍵字精準。
  3. **證交所注意／處置股**：`/announcement/notice`、`/announcement/punish`、`/announcement/notetrans`；另有「投資理財節目異常推介個股」`/Announcement/BFZFZU_T`（台股特有的炒作訊號）。

---

## 5. 地緣風險映射：標的本身是台股時，邏輯要如何反轉

### 5.1 既有邏輯（美股視角）

`GEOPOLITICAL_RISK_MAP["taiwan"]`（L833–839）：關鍵字 `taiwan` / `tsmc` / `strait` → sectors `Technology`、`Communication Services` → affected_tickers `NVDA, AMD, TSM, INTC, QCOM, AVGO, MU`，impact 為「Semiconductor supply chain disruption」；命中 ticker 扣 30% confidence（L996），只命中 sector 扣 15%（L1007）。

隱含假設：**台灣是「事件發生地」，美股標的是「遠端受影響者」，曝險程度依供應鏈連結而異，因此是類股層級的選擇性折價。**

### 5.2 反轉後（台股視角）需要的四項調整

**(1) 從「類股因子」升級為「市場因子」。**
台海事件對台股不是某幾個類股的問題，而是全市場的系統性風險（外資撤資、匯率、流動性、極端情況下休市）。移植時 `taiwan` 這一條**不應留在 `check_sector_geopolitical_risk()`（個股層級）**，而應上移到 `analyze_market_context()`（大盤層級），成為對所有台股一律生效的風險開關。留在個股層只會產生「電子股扣分、水泥股不扣分」這種在台海情境下沒有意義的區分。

**(2) 曝險軸從「產業」換成「地緣營運結構」。**
反轉後真正有區別力的分層不是 GICS 產業，而是：

| 分層 | 說明 | 相對曝險 | 可用資料 |
|---|---|---|---|
| 海外產能占比高 | 產能分散於美／日／星／德者衝擊較小 | 較低 | 需自年報／MOPS 取得，**無結構化官方端點，未能查證** |
| 外資持股比率高 | 外資撤資時賣壓最大 | **最高** | 證交所 `/fund/MI_QFIIS_cat`（類股持股比率）、`/fund/MI_QFIIS_sort_20`（前 20 名） |
| 出口導向 vs 內需 | 內需（食品、金融、電信、公用）相對抗跌 | 依產業 | 證交所產業類指數（§4.5） |
| 中國營收占比高 | 兩岸情勢直接衝擊 | 高 | MOPS 財報附註「大陸投資」；**無日頻端點，未能查證** |
| 融資餘額高 | 斷頭賣壓放大跌幅 | 高 | `/exchangeReport/MI_MARGN`（§4.6） |

**(3) 事件方向可能反向，不能照抄符號。**
既有映射假設「台海／中國事件＝對相關個股利空」，但台股視角下有明確的反向情境：
- **中國／美中貿易戰**：對美股是「Tech 供應鏈利空」（L840–846），對部分台廠反而是**轉單利多**（脫鉤下的替代效應）。照抄符號會給出方向錯誤的訊號。
- **地緣衝突推升國防、資安、航運運價**：台股有明確受惠族群（航運類指數、資訊服務類指數）。罰則應改為**分方向的加減分**，而非單向的 confidence 折扣。

**(4) 需要新增「以台灣為對象」的風險量表。**
既有實作只有關鍵字比對，SKILL.md L184–186 自己也承認會有 false positive。第一手替代候選：

| 候選 | 說明 | 來源 | 狀態 |
|---|---|---|---|
| **GPR country-specific index：Taiwan** | Caldara & Iacoviello 地緣政治風險指數；country-specific 版涵蓋 44 國，**Asia and Oceania 分頁明確列出 Taiwan**；**月頻**，每月初更新（頁面標示 last update July 1, 2026）；Excel / Stata 免費下載 | https://www.matteoiacoviello.com/gpr_country.htm ｜下載 https://www.matteoiacoviello.com/gpr.htm ｜方法論 https://www.policyuncertainty.com/gpr.html | 可得，但**月頻對日頻訊號太慢** |
| TAIWAN VIX 跳升 | 台海事件會即時反映在 TXO 隱含波動率 | §4.2 | 日內頻 |
| 外資現貨買賣超／期貨淨部位 | 資金面即時反映 | §4.7 | 日頻 |
| USD/TWD 匯率 | 同上 | yfinance `TWD=X` | 日頻 |
| 中文新聞關鍵字（台海、共軍、演習、封鎖…） | 沿用 feedparser 架構改中文 | §4.8 | 可行，但同樣有 false positive |

**可行結構（描述，不做取捨）**：把「地緣風險」從「新聞關鍵字 → 類股罰則」改為三層：日頻市場訊號（TAIWAN VIX ＋ 外資動向 ＋ USD/TWD）為主、GPR-Taiwan 月頻為背景水位、中文新聞關鍵字為觸發旗標；罰則作用在**大盤層**，個股層只依「外資持股比率／融資餘額／內需外銷」做相對加權。

---

## 6. 讀 code 時發現的既有缺陷（會影響移植決策）

| # | 缺陷 | 位置 | 影響 |
|---|---|---|---|
| D1 | `get_put_call_ratio()` 讀 `data.ticker_obj`，但 `StockData` dataclass 沒有這個欄位 | L1570/1574/1579 vs L75–82 | AttributeError 被 L1590 的 `except` 吞掉 → **put/call 子指標在美股也永遠是 None**，實際只有 4/5 子指標可用 |
| D2 | `get_vix_term_structure()` 名為期限結構，實際只讀 `^VIX` 現貨並硬編碼 slope | L1405–1437 | 與維度五的 `vix_score`（L679–687）重複計算同一變數；「VIX 期限結構的移植難題」其實不存在 |
| D3 | 相對強度用**除法** `stock_return / sector_return` | L1053 | 分母為負時方向反轉（個股 −5%、類股 −10% → RS = 0.5 被判為落後，實際是超前）；台股版應改為相減 |
| D4 | beat rate 分母含尚未公布的季（`Reported EPS` 為 NaN 者也計入 `total_quarters`） | L615, L620 | 系統性低估 beat rate。台股 `earnings_dates` 同樣含未來一列（實測 2330.TW 首列 2026-10-15 的 Reported EPS 為 NaN），移植會照樣中招 |
| D5 | script header 未宣告 `lxml` | L2–11 | `stock.earnings_dates` 需要 lxml；未安裝時丟 `ImportError`，被 L248 的 `except` 吞掉 → **維度一、維度四與財報時點全部靜默失效**。本文實測特意補裝 lxml 才取得資料 |
| D6 | RSI 用簡單移動平均而非 Wilder 平滑 | L1192–1193 | 與台股主流看盤軟體的 RSI 數值不一致，70/30 門檻的意義會偏移 |
| D7 | `analyze_market_context()` 與個股無關卻在每檔股票的迴圈內呼叫 | L2259 | 靠 1h 快取遮掩；台股版重寫時應提到迴圈外 |

---

## 7. 台股版分析維度候選清單（不做取捨）

### 7.1 由既有 8 維度直接延續者

| 候選維度 | 組成 | 主要來源 |
|---|---|---|
| A. 財報意外 | EPS actual vs estimate、surprise% | yfinance `earnings_dates`（需補裝 lxml） |
| B. 基本面 | 本益比、營業利益率、營收年增率、負債權益比 | yfinance `info`；官方本益比／殖利率／PB 用 `/exchangeReport/BWIBBU_ALL` |
| C. 分析師情緒 | 共識評等、目標價上檔空間 | yfinance（大型股覆蓋佳，中小型與 ETF 無覆蓋） |
| D. 歷史財報型態 | 近 4 季 beat rate、財報日反應 | yfinance `earnings_dates` ＋日 K |
| E. 動能 | RSI(14)、52 週區間位置、量能比 | yfinance 日 K 或 `/exchangeReport/STOCK_DAY_ALL` |
| F. 大盤環境（台股版） | TAIWAN VIX、加權指數 10 日趨勢、櫃買／半導體類指數趨勢、risk-off（黃金／台債／USDTWD） | 期交所＋證交所＋yfinance |
| G. 產業比較（台股版） | 個股 vs 37 檔產業類指數的 1 月相對強度、類指數 10 日趨勢 | 證交所 `MI_INDEX` / `MI_INDEX?type=IND` |
| H. 市場情緒（台股版） | TAIWAN VIX 水準 ＋ TXO P/C ratio ＋ 融券／借券賣出比 ＋ 內部人轉讓申報 | 期交所＋證交所 |

### 7.2 台股特有、美股版沒有的新候選維度

| 候選維度 | 為何值得考慮 | 官方來源（本次實測驗證過回傳格式者標「實測 OK」） |
|---|---|---|
| I. **月營收動能** | 台股每月 10 日前公告單月營收，是全球罕見的**月頻基本面**，比季報早 2–3 個月反映轉折 | 實測 OK：`/opendata/t187ap05_L`（含當月營收、上月營收、去年當月營收、上月比較增減%、去年同月增減%、累計 YoY%、**產業別**） |
| J. **三大法人籌碼** | 外資／投信／自營商買賣超，台股最被廣泛使用的資金面訊號 | 實測 OK：`https://www.twse.com.tw/rwd/zh/fund/T86?date=…&selectType=ALL&response=json`（含外陸資、外資自營商、投信、自營自行／避險、三大法人合計） |
| K. **外資持股比率** | 反映國際資金部位與撤資風險 | `/fund/MI_QFIIS_cat`、`/fund/MI_QFIIS_sort_20` |
| L. **信用交易結構** | 融資餘額（散戶槓桿）、融券餘額、券資比、資券互抵（當沖） | 實測 OK：`/exchangeReport/MI_MARGN`、`TWT93U`；另 `/SBL/TWT96U`、`/exchangeReport/BFI84U` |
| M. **當沖比率** | 台股當沖占比極高，是投機熱度的直接量表 | `/exchangeReport/TWTB4U`（每日當日沖銷交易標的及統計）、`/exchangeReport/TWTBAU1`、`/exchangeReport/TWTBAU2` |
| N. **監理旗標** | 注意股、處置股、變更交易、投資理財節目異常推介 | `/announcement/notice`、`/announcement/punish`、`/announcement/notetrans`、`/exchangeReport/TWT85U`、`/Announcement/BFZFZU_T` |
| O. **股利與殖利率** | 台股以高殖利率為主要投資訴求，權重應高於美股 | 實測 OK：`/exchangeReport/BWIBBU_ALL`（Date/Code/Name/PEratio/DividendYield/PBratio）；另 `/opendata/t187ap45_L`（股利分派）、`/exchangeReport/TWT48U_ALL`（除權息預告） |
| P. **內部人結構風險** | 董監持股成數不足、董監質押比 —— 台股特有的公司治理風險訊號 | `/opendata/t187ap08_L`、`/opendata/t187ap10_L`、`/opendata/t187ap09_L` |
| Q. **財測達成度** | 上市公司財測與會計師查核數差異揭露 | `/opendata/t187ap15_L`、`/opendata/t187ap16_L` |
| R. **地緣風險（台股版）** | 見 §5 的三層結構 | 期交所 VIX ＋ T86 ＋ `TWD=X` ＋ GPR-Taiwan |
| S. **重大訊息旗標** | 取代英文 Google News RSS | `/opendata/t187ap04_L` |
| T. **期貨／選擇權籌碼** | 三大法人期貨未平倉、TXO P/C ratio、大額交易人部位 | https://www.taifex.com.tw/cht/3/callsAndPutsDate 、https://www.taifex.com.tw/cht/3/pcRatio |
| U. **產業 EPS 與營益分析** | 產業層級的獲利水位可做相對估值 | `/opendata/t187ap14_L`（各產業 EPS 統計）、`/opendata/t187ap17_L`（營益分析彙總） |

### 7.3 移植時必須額外處理的制度／資料差異（非指標，但會污染上述所有計算）

| 差異 | 影響的維度 |
|---|---|
| **漲跌幅限制 ±10%** | D（財報當日反應被截斷，可能連續數日跳板）、E（RSI 與波動分布不同） |
| **交易時段 09:00–13:30**，期交所另有夜盤 | F、H（盤中訊號的時間對齊） |
| **除權息造成的價格跳空**（台股除息幅度常達 5–8%） | E、G（須確認 yfinance history 是否已還原；**本次未測**） |
| **上市（.TW）／上櫃（.TWO）分屬證交所與櫃買中心** | 所有依賴證交所 OpenAPI 的維度都需要櫃買的平行實作（https://www.tpex.org.tw/openapi/ ） |
| **民國年日期格式**（實測官方端點回傳「1150730」＝2026-07-30） | 所有官方端點的資料處理層 |
| **ETF 無基本面與分析師資料**（實測 00878.TW：PEratio 有值但 sector／analyst／earnings 全空） | A、B、C、D、G 對 ETF 全數失效，需獨立的 ETF 分析路徑 |
| **yfinance 台股資料本身的一致性問題** | 實測 `^TWII` 的 `history()` 末日收盤 39933.30 與 `info.regularMarketPrice` 43119.75 不一致；`0050.TW` 的 `history()` 末筆 Close 為 NaN。→ 大盤與 ETF 層級不宜單靠 yfinance，應以證交所指數端點為準 |

---

## 8. 未能查證項目（明確標註，不以記憶填空）

1. **MacroMicro「台灣-MM 恐懼與貪婪指數」是否提供免費 API 或可程式化取得** —— 僅確認有網頁與圖表，未確認存取條件與授權。
2. **期交所 TAIWAN VIX 是否提供官方 REST API** —— 官網只載明網頁下載（當月／前 3 個月／每日收盤），未見 API 說明；付費管道為「期貨智慧資訊商店」。
3. **證交所是否有官方日頻的「52 週新高／新低家數」端點** —— 143 個 OpenAPI 端點清單中未找到。
4. **台灣個股選擇權的實際成交量數字** —— 已確認期交所有股票選擇權商品且提供每日行情下載頁，但本次未取得逐商品成交量以量化其流動性；僅以第一手實測「yfinance 對台股回傳的 `Ticker.options` 為空 tuple」佐證此路不通。
5. **台灣有無公開日頻的高收益債（junk bond）利差** —— 未找到來源，故 CNN F&G 的第 7 元件無法還原。
6. **個股層級的「中國營收占比」「海外產能占比」是否有結構化官方端點** —— MOPS 財報附註有揭露，但未找到結構化 API。
7. **`/opendata/twtazu_od`（漲跌證券數統計）的官方更新頻率** —— 實測回傳「出表日期 1150605」，明顯落後查詢當日（2026-07-31），但未查證其官方更新規則。
8. **yfinance 台股日 K 是否已還原除權息** —— 本次未測。
9. **櫃買中心 OpenAPI 是否有與證交所對等的內部人申報／融券借券／類指數端點** —— 僅實測 `tpex_mainboard_daily_close_quotes` 可用，其餘端點未逐一清點。

---

## 附錄：本文使用的第一手來源

**臺灣證券交易所**
- OpenAPI Swagger 入口：https://openapi.twse.com.tw/
- 融券借券賣出餘額（TWT93U）：https://www.twse.com.tw/zh/trading/margin/twt93u.html
- 當日可借券賣出股數（TWT96U）：https://www.twse.com.tw/zh/trading/margin/twt96u.html
- 借券資訊：https://www.twse.com.tw/zh/page/trading/exchange/TWT72U.html
- 報表索引：https://www.twse.com.tw/zh/report-index.html
- 每日收盤行情（含類指數）：https://www.twse.com.tw/zh/trading/historical/mi-index.html
- 公開資訊觀測站：https://mops.twse.com.tw/

**證券櫃檯買賣中心**
- OpenAPI：https://www.tpex.org.tw/openapi/
- 官網：https://www.tpex.org.tw/zh-tw/index.html

**臺灣期貨交易所**
- 臺指選擇權波動率指數 Q&A：https://www.taifex.com.tw/cht/7/vixQA
- VIX 編製手冊 PDF：https://www.taifex.com.tw/file/taifex/CHINESE/files/7/VIX_book.pdf
- VIX 資料下載：https://www.taifex.com.tw/cht/7/vixMinNew
- VIX 即時行情：https://mis.taifex.com.tw/futures/VolatilityQuotes/
- 臺指選擇權 Put/Call Ratio：https://www.taifex.com.tw/cht/3/pcRatio
- 三大法人選擇權買賣權分計：https://www.taifex.com.tw/cht/3/callsAndPutsDate
- 期貨每日交易行情：https://www.taifex.com.tw/cht/3/futDailyMarketReport
- 選擇權每日交易行情下載：https://www.taifex.com.tw/cht/3/optDailyMarketView

**政府資料開放平臺**
- 臺指選擇權 Put/Call 比：https://data.gov.tw/dataset/11322

**地緣政治風險指數**
- Country-specific GPR（含 Taiwan）：https://www.matteoiacoviello.com/gpr_country.htm
- GPR 資料下載：https://www.matteoiacoviello.com/gpr.htm
- 方法論：https://www.policyuncertainty.com/gpr.html

**其他（民間，僅列為候選）**
- MacroMicro 台灣-MM 恐懼與貪婪指數：https://www.macromicro.me/series/46964/taiwan-mm-fear-and-greed-index
- 國泰金控國民經濟信心調查：https://www.cathayholdings.com/holdings/information-centre/intro/gdp_news/index
