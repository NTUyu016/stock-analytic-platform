# 技術棧選型 v1

決策來源：[issue #12](https://github.com/NTUyu016/stock-analytic-platform/issues/12)。名詞定義見 [`CONTEXT.md`](../../CONTEXT.md)，資料表綱要見 [`data-model.md`](./data-model.md)。

前置研究：[#2 台股即時報價來源](../research/tw-realtime-quote-sources.md)、[#5 常駐 WebSocket 後端部署](../research/persistent-websocket-hosting.md)、[#4 分析可移植性](../research/analysis-portability-to-tw.md)、[#6 交易成本與稅費](../research/tw-trading-costs-taxes.md)。

> 本文除了記錄「選了什麼」，也記錄「**為什麼**、被淘汰的選項輸在哪」。選型不附理由，日後就沒人敢改。

---

## 總覽

| 項目 | 結論 |
|---|---|
| 後端 | Python 3.13 + FastAPI |
| 套件管理 | uv（鎖定 `uv.lock`） |
| 前端 | React + Vite，純靜態 SPA |
| 資料庫 | PostgreSQL（[#9](https://github.com/NTUyu016/stock-analytic-platform/issues/9) 已定） |
| repo | 單一 repo，兩個部署單元：`api` + `quote-worker` |
| 前置 | Caddy（發靜態檔、TLS、反向代理） |
| 圖表 | `lightweight-charts` + `recharts` |
| 測試 | 分層取捨（見 §7） |
| 容器 base image | `python:3.13-slim`（**不可用 Alpine**） |

---

## 1. 後端：Python 3.13 + FastAPI

### 決定

單一 Python 後端。不採 TypeScript、不採 Go/Rust、不採「TS 主幹 + Python 分析服務」的混合架構。

### 為什麼

**1. yfinance 是載重相依，而它只有 Python。**

[#3](../research/tw-fundamental-chip-data-sources.md) 與 [#4](../research/analysis-portability-to-tw.md) 兩張研究票的結論全部建立在 yfinance 上——台股財報數字與官方逐項吻合、`earnings_dates` 可用、大型股有分析師目標價。換成 TypeScript 就得改用 `yahoo-finance2`，那些逐項比對的驗證結果**全部作廢重做**。這等於丟掉一張已完成的研究票。

**2. Shioaji 的「HTTP API」是本機 server，不是遠端端點。**

[#2](../research/tw-realtime-quote-sources.md) 的結論寫「Shioaji 有官方 HTTP + SSE，所以後端語言自由」，這句話成立但漏了代價。官方 README 的用法是：

```bash
shioaji server start              # 模擬環境
shioaji server start --production # 正式環境
curl http://localhost:8080/api/v1/health
```

OpenAPI 互動文件在 `http://localhost:8080/docs`，repo 內另有 `Dockerfile-server`。也就是說，**選 Go/Node 不是「省掉 Python」，而是「多一個常駐 sidecar 行程 + 多一層 loopback 跳躍」**。Python 後端可以直接 `import shioaji`，這一層完全不存在。

**3. 既有資產是 Python。** `analyze_stock.py` 2504 行的分析演算法（處置方式見 §5）。

### 被淘汰的選項

| 選項 | 輸在哪 |
|---|---|
| TypeScript / Node 單一後端 | yfinance 無等價替代；必須跑 Shioaji sidecar |
| TS 主幹 + Python 分析服務 | 行程數暴增（Node + Python + Shioaji server + Postgres），且多一套服務間契約要維護 |
| Go / Rust | 分析與基本面資料生態不存在，兩千多行分析邏輯要從零重寫 |

### 為什麼是 FastAPI

原生 async（行情與外部 API 都是 I/O bound）、以 Pydantic 做請求/回應驗證、**自動產生 OpenAPI schema**——最後這點是補上「前後端不同語言」這個缺口的關鍵，見 §3。

---

## 2. 套件管理：uv

### 決定

用 [uv](https://docs.astral.sh/uv/) 管理 Python 相依與虛擬環境，`uv.lock` 進版控。

### 為什麼

- **`pip` + `requirements.txt` 沒有真正的 lock。** `requirements.txt` 記錄的是你當初裝了什麼，不是完整的相依樹。換一台機器、隔三個月重裝，解出來的版本組合可能不同——這就是「在我機器上可以跑」的來源。
- **`uv.lock` 鎖定整棵相依樹並含雜湊值**，任何機器 `uv sync` 出來的環境位元級一致。
- Poetry 也有 lock，但 uv 以 Rust 實作，解析與安裝快一到兩個數量級，且同時取代了 `pyenv`（`uv python install`）、`venv`、`pip-tools`、`pipx`——**四個工具收斂成一個**。

### 上手指令

```bash
uv sync                    # 依 uv.lock 建立/同步環境（取代 pip install -r）
uv add fastapi             # 新增相依並更新 lock
uv add --dev pytest        # 開發相依
uv run pytest              # 在專案環境內執行，不需先 activate
uv python install 3.13     # 裝 Python 本身
```

**心智模型**：`uv sync` 之於 Python，等同 `npm ci` 之於 Node——以 lock 為準重建環境，不做版本解析。要改版本才用 `uv add`。

---

## 3. 前端：React + Vite，純靜態 SPA

### 決定

`vite build` 產出一包靜態檔，由 Caddy 直接發。**生產環境沒有任何 Node 行程**——Node 只存在於開發機與 CI。

### 為什麼不做 SSR

SSR 的三個賣點在這個 app 上全部失效：

1. **SEO**：所有頁面都在登入後，沒有爬蟲會看到。
2. **首屏內容**：畫面主體是即時報價，SSR 渲染出來的價格在瀏覽器收到的那一刻就已過期，前端仍得立刻用即時通道蓋掉。
3. **首屏速度**：沒有第三方訪客，這不是產品指標。

代價則很實在：Next.js 的常駐 Node server 要吃掉 100 MB 量級的記憶體，而它得跟 PostgreSQL 和行情接收器搶同一台小機器。

### 為什麼是 React 而不是 Svelte

誠實記錄：**Svelte 5 在這個場景有真正的技術優勢**。細粒度反應性天生適合「一張 50 列的持股表每秒有數十個 cell 在跳」，而 React 得靠設計才能避免整表重繪。

選 React 的理由是**圖表與表格元件生態明顯較廣**，而 [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)（分析頁）與歷史績效頁會壓上不小的視覺化需求。生態差距比反應性差距更難靠自己補。

**因此 React 這邊有一條硬性設計要求**：持股表的即時更新必須做成**每一列各自訂閱自己的 Instrument**，不可以把整包報價放在共同祖先的 state 裡——後者會讓每個 tick 觸發整棵子樹 re-render。這是選 React 換來生態、必須付的那筆帳，實作時不能忘。

### 前後端型別怎麼共用

FastAPI 自動產生 OpenAPI schema，前端由該 schema codegen 出 TypeScript 型別。後端改了欄位，前端 build 就會紅——「同語言才能共用型別」的優勢用這個方式補上，不需要整個後端遷就前端。

---

## 4. repo 結構與部署單元

### 決定

**單一 repo，兩個部署單元**，共用同一個 Python package：

```
/
├── pyproject.toml          # uv 專案根，單一相依樹
├── uv.lock
├── src/
│   ├── core/               # 領域模型、成本/損益計算、資料源 adapter（兩者共用）
│   ├── api/                # FastAPI 應用
│   └── quote_worker/       # 行情訂閱、重連、扇出
├── frontend/               # React + Vite
├── docs/
└── Caddyfile
```

### 為什麼分兩個單元

關鍵約束來自 [#2](../research/tw-realtime-quote-sources.md)：

> 訂閱上限 **200**、同一 ID 最多 **5 條連線**、登入每日上限 1000 次。
> 「持續違規將暫停該 IP 及 ID 使用權……停權期間反覆重試 `login()` 無法解除限制，反而可能延長停權時間。」

**行情連線是稀缺且脆弱的資源**——不能靠多開行程繞過限制，而反覆重連本身就是懲罰性的。

這跟 HTTP API 的生命週期完全相反：前端和 API 一天會改好幾次、重啟好幾次。兩者同一個行程，就等於**每次 deploy 都斷一次行情連線**，每次斷線重連都在消耗 Shioaji 的容忍度。

### `quote-worker` 是可選元件（硬性要求）

`api` **必須能在 `quote-worker` 完全不存在時正常運作**，只是降級：

| `quote-worker` | 報價來源 | 使用者體驗 |
|---|---|---|
| 有跑 | 即時串流 | 盤中秒級跳動、價格警示即時觸發 |
| 沒跑 | 開頁時抓一次快照 + 每日收盤價 | 功能完整，只是不即時；連線狀態需明確外顯 |

**為什麼要這條**：[#5](../research/persistent-websocket-hosting.md) 指出「盤中即時秒級推播」這條前提正是所有雲端成本的源頭——常駐才能收行情，常駐就不能 scale-to-zero。把 worker 做成可選，等於把「即時性」變成一個可以隨時開關的成本旋鈕，而不是綁死在架構裡的義務。這也是分兩個部署單元比「deploy 不斷行情」更實在的價值。

實作上這意味著：**任何讀取即時報價的程式碼路徑都必須有明確的「沒有即時報價」分支**，不可以假設 Quote 一定存在。

### 兩個單元之間怎麼傳 tick

**留給 [#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) 決定。** 已知選項：Postgres `LISTEN/NOTIFY`（零額外元件，Postgres 本來就在）或 Redis pub/sub。本文只確定「有兩個單元」這個形狀。

同樣留給 #13 的還有：瀏覽器端走 WebSocket 還是 SSE、`quote_worker` 內部用原生 binding 還是本機 HTTP server、推播節流頻率。

---

## 5. 既有 stock-analysis skill 的處置

### 決定

**只抄演算法重寫，不繼承檔案。** 舊碼放在手邊當參考規格逐段對照，但新 repo 不從它長出來。

### 帳實際上長這樣

`~/.claude/skills/stock-analysis/scripts/` 共 3052 行：

| 區塊 | 行數 | 命運 |
|---|---|---|
| `analyze_momentum`、`calculate_rsi`、`analyze_historical_patterns`、`analyze_earnings_surprise`、`analyze_fundamentals` 骨架 | ≈400 | **可沿用**（#4 判定「原封不動」的 3 維） |
| 市場情緒區塊（CNN Fear & Greed、put/call、VIX） | ≈450 | 全數重建——全是美股專屬 |
| 類股 ETF 對照、地緣風險圖譜 | ≈300 | 換來源（→ 證交所 `MI_INDEX` 37 檔產業類指數）＋**符號反轉** |
| `synthesize_signal` | ≈300 | 評分權重全部重新取捨（#14） |
| `main()` CLI ＋ `format_output_*` ＋ portfolio summary | ≈440 | 作廢（CLI → HTTP、文字 → JSON） |
| crypto 相關 | ≈100 | v1 不定（#1 列在 Not yet specified） |
| `portfolio.py` 全檔 | 548 | **全數作廢**——#9 已定 Transaction 為唯一事實來源，JSON 檔儲存模型整個被取代 |

**真正能直接沿用的約 400 行，佔 13%。**

### 為什麼不搬檔案

**主因是缺陷會跟著搬過來。** #4 已點名三個死碼缺陷：

1. put/call ratio 讀了一個**不存在的欄位**，因此在美股也永遠回傳 `None`；
2. VIX 期限結構實為現貨硬編碼，且與維度五重複計分；
3. 未宣告 `lxml` 相依，導致維度一與四可能靜默失效。

搬檔案就是把這三個缺陷一起搬進新專案，而且會因為「它本來就在那裡、看起來像能跑的」而不再被檢視——這正是它們能活過五個版本的原因。

**次因是資料流形狀不相容。** 舊碼是「一次一支、同步 fetch、快取只在行程記憶體」的 CLI（`fetch_stock_data` 是唯一入口，`_SENTIMENT_CACHE` 重啟即失）。網站要的是多支批次、跨行程快取、盤後預算——方向不同。

### 舊 skill 本身

繼續留在 `~/.claude/skills/stock-analysis` 服務美股 CLI 用途，不在本圖範圍內。上述三個缺陷是否回頭修，由使用者自行決定。

---

## 6. 圖表函式庫

### 決定

兩個庫並存，各吃一類需求。

| 需求 | 庫 | 特徵 |
|---|---|---|
| 金融時間序列：K 線、總資產曲線、報酬率曲線 | **`lightweight-charts`** | Canvas 繪製，`series.update(bar)` 只重畫最後一根，內建十字準星與縮放平移 |
| 統計圖：資產配置圓餅、貢獻度長條、雷達／分數卡 | **`recharts`** | React 原生宣告式，SVG |

### 為什麼不用同一個庫

這兩類圖的**更新頻率差了四五個數量級**：第一類盤中每秒都在動，第二類一天變一次。用同一個庫必然有一邊要將就。

Recharts 這類 SVG 宣告式庫處理第一類會很痛：每個 tick 觸發一次 React re-render 加整張 SVG diff。而 `lightweight-charts` **明確只做金融圖**，圓餅和雷達它不做。

ECharts 是唯一能一個庫全包的候選，代價是即時更新只能走 `setOption`（不如 `series.update()` 精準）且整包明顯較重。

### 要付的代價（記錄下來，別忘記）

- 兩套 API、兩套主題設定——**台股紅漲綠跌的配色要在兩邊各設一次**，必須抽成單一組色彩常數避免分歧。
- `lightweight-charts` 是 Apache 2.0 但**強制 attribution**：必須在使用者看得到的地方保留連到 TradingView 的標示。官方提供 `attributionLogo` 圖表選項直接滿足此要求，**不可關閉它**。

---

## 7. 測試策略

### 決定

**分層取捨**，不做全面 TDD，也不是不寫測試。

| 層 | 策略 | 為什麼 |
|---|---|---|
| 成本基礎、已實現/未實現損益、報酬率（TWR/IRR）、交易成本與稅費 | **嚴格 TDD**（先寫測試） | 純函式零 I/O，測起來最便宜；算錯錢最貴 |
| 外部資料源 adapter（yfinance / Shioaji / TWSE OpenAPI） | **契約測試**（錄真實回應當 fixture） | 這些來源會靜默壞掉 |
| 行情重連退避邏輯 | 用假時鐘測退避序列 | 唯一「寫錯會導致外部帳號被鎖」的邏輯 |
| 分析維度評分、API 端點、前端 | **v1 不寫** | #14 未定，現在寫的 assertion 多半會被推翻重寫 |

### 為什麼錢的計算值得先寫測試

[#6](../research/tw-trading-costs-taxes.md) 已指出這裡有真實陷阱：

- **費率一律不得硬編碼**（美國 SEC Section 31 於 2026-04-04 從歸零復徵即為證）。
- 三個落日條款，其中**債券 ETF／公司債證交稅停徵 2026-12-31 到期**——今年底就會撞到。
- 當沖證交稅減半 1.5‰ 延至 2027-12-31，但**限上市櫃股票且現款現券**，ETF 與資券相抵不適用。
- **手續費與證交稅的元以下進位規則無任何公開一手文件，需以實際交割單反推。**

最後這條最關鍵：**沒有測試，你根本無從知道自己反推對了沒。** 實際交割單就是最好的測試 fixture。

### 為什麼外部資料源值得契約測試

#4 已證明這些來源會**靜默地壞掉**：yfinance 的 ETF 欄位錯誤、減資期間會產生假 OHLC 列、籌碼面與月營收 0 覆蓋。而舊 skill 的 put/call 缺陷（讀不存在的欄位，永遠回傳 `None`）活過五個版本沒被發現——**一個最陽春的「這個 adapter 到底有沒有拿到值」的測試就會當場抓到。**

契約測試不驗證分析結果對不對，只驗證：欄位還在、型別沒變、值不是 `None`。

---

## 8. 前置：Caddy

### 決定

Caddy 在最前面，負責發前端靜態檔、終結 TLS、把 `/api/*` 反向代理給 FastAPI。

### 為什麼不讓 FastAPI 自己發靜態檔

因為**這個網站沒有「先用 HTTP 跑跑看」的選項**：[#7](../research/alert-notification-channels.md) 推薦的 Web Push 需要註冊 Service Worker，而 Service Worker 只能在 **secure context** 註冊。`localhost` 本身算 secure context，但用手機從區網連進來時就不是了。

TLS 憑證的申請與續期是那種「會在半夜三點過期時咬你」的東西，Caddy 把它變成零維護。此外 Python 發靜態檔的效率遠低於專用 server。

### 憑證怎麼來

[#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) 已定調**不公開在網際網路上**，因此 Let's Encrypt 不適用（它需要公開可達的網域才能完成驗證）。改用 Caddy 內建 CA：

```
# Caddyfile
your-host.local {
    tls internal              # Caddy 自簽 CA，自動產生並續期內網憑證

    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle {
        root * /srv/frontend
        try_files {path} /index.html   # SPA 路由：找不到檔案就回 index.html
        file_server
    }
}
```

> **給熟悉 nginx 的對照**：`reverse_proxy` 等同 `proxy_pass` 但預設就帶好了 `Host`、`X-Forwarded-*` 等標頭；`try_files {path} /index.html` 與 nginx 同名指令語意相同，是 SPA 前端路由的標準寫法；`tls internal` 沒有 nginx 對應物——nginx 要自己跑 certbot 或手動簽憑證再設 `ssl_certificate`。整份 Caddyfile 不需要 `server`/`location`/`upstream` 三層巢狀，也沒有 `listen 443 ssl` 這種樣板。

實際網域、憑證信任的散布方式、防火牆與成本上限，留給 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17)。

---

## 9. 容器 base image：必須是 Debian

### 決定

`python:3.13-slim`。**不可以用 Alpine。**

### 為什麼

`shioaji`（目前 1.7.1）發布的是 **manylinux binary wheel**，不是純 Python——它有 Rust core。manylinux 針對 **glibc**，而 Alpine 用的是 **musl**，wheel 直接裝不起來，只能退回從原始碼編譯整個 Rust 專案。

Alpine 幾乎是「我要小映像」的反射性預設，這個坑不寫下來，實作時一定會踩。

好消息是 Python 版本不構成約束：`shioaji` 的 `requires_python` 是 `>=3.7`，classifiers 一路列到 3.14，所以 3.13 是安全的。

---

## 10. 留給其他票

| 議題 | 票 |
|---|---|
| tick 從 `quote-worker` 到 `api` 到瀏覽器的扇出機制、WebSocket vs SSE、推播節流頻率 | [#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) |
| 分析維度取捨、五級建議（strong buy / buy / hold / sell / strong sell）的呈現與免責 | [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) |
| 快照 vs 重算、報酬率演算法、大盤比較基準 | [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) |
| 部署位置、網域、憑證散布、成本上限、開關機排程 | [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) |
| 認證機制、session、暴露面 | [#10](https://github.com/NTUyu016/stock-analytic-platform/issues/10) |
| 儀表板版面與視覺風格 | [#11](https://github.com/NTUyu016/stock-analytic-platform/issues/11) |
