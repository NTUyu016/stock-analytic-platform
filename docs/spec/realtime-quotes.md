# 即時報價的擷取與扇出架構 v1

決策來源：[issue #13](https://github.com/NTUyu016/stock-analytic-platform/issues/13)。名詞定義見 [`CONTEXT.md`](../../CONTEXT.md)，技術棧見 [`tech-stack.md`](./tech-stack.md)，介面規則見 [`dashboard-ui.md`](./dashboard-ui.md)。

前置研究：[#2 台股即時報價來源選型](../research/tw-realtime-quote-sources.md)、[Fugle 免費層能力逐項查證](../research/fugle-free-tier-capabilities.md)。

> 本文回答的是：**行情從資料源進來之後，怎麼流到瀏覽器。** 與 `tech-stack.md` 的分工是——那份決定「有 `api` 與 `quote-worker` 兩個部署單元」這個形狀，本文決定它們之間、以及它們對外的每一條通道。

---

## ⚠️ 2026-08-06 事實更正：本文有三處對 Fugle 免費層能力的敘述經查證為錯

#13 定案時，Fugle 免費層各頻道的實際能力**從未被逐項查證**——當時的依據是 #2 的研究，而 #2 的主題是 Shioaji，Fugle 只是備援。2026-08-06 的[逐項查證](../research/fugle-free-tier-capabilities.md)（來源為富果官方 `llms-full.txt` 全文檔）發現三處錯誤。

**本節只更正事實，不重新決策。** 受影響的決策標示為「待重新決定」，由 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 一併處理。

| # | 本文原本說 | 查證後的事實 | 後果 |
|---|---|---|---|
| 1 | 「Fugle 免費層沒有快照 API」，故 §7 第 3 層降級走 **yfinance（延遲 15 分鐘）** | **不支援的只有全市場快照 `/snapshot/*`。單一標的的 `GET /intraday/quote/{symbol}` 免費層可用，60 次/分鐘**，回傳含最佳五檔、累計量、暫停交易旗標，且與 WebSocket **同源同定義** | §7 第 3 層走 yfinance 是**不必要的降級**：異機構、異定義、延遲 15 分鐘，換來的東西 Fugle 本來就給。<br>`supports_snapshot: bool` **粒度不足**，至少要拆成 `supports_symbol_quote` 與 `supports_market_snapshot`。<br>⚠️ 更危險的是 §2 稱這個布林值讓「轉 Shioaji 時快照路徑自動可用」——**布林值定義錯了，那個「自動」就自動到錯的地方去**，Fugle 會被永久標成 `False`，明明有能力卻永遠降級。<br>**→ 待重新決定** |
| 2 | 「訂閱上限 **5 檔**」（§2/§3/§5/§10 共四處） | 官方定義是「每個訂閱數對應 **1 檔股票 × 1 種資料類型（Channel）**」。5 個額度 = **5 個 (標的, 頻道) 配對** | **5 檔持股只能訂一個頻道。** `trades`＋`books` 就是 10 個，超過一倍。<br>`max_subscriptions` 的**單位有歧義**：核心程式拿它跟「持股檔數」比大小，只在「每檔恰好訂一個頻道」時才對；Shioaji 的額度單位是「檔」，兩家不同——正是 §2 要求 adapter 吸收的那類差異，但目前欄位名沒表達出來。<br>**→ 待重新決定**（見下方「新暴露的取捨」） |
| 3 | 「盤中零股是 Shioaji **才**具備的能力，Fugle 未查證，不押注」（§8、§10 條目 5） | Fugle 的 `trades`/`books`/`candles`/`aggregates` **四個頻道都有 `intradayOddLot` 參數**，REST 有 `type=oddlot`，未標付費專屬 | **「Shioaji 才有」這句話不成立**，`supports_odd_lot: fugle_free=False` 是錯的。<br>但 **§8 的結論（09:00–13:35，不涵蓋盤後零股）仍然正確**——爭議時段是 13:40–14:30 的**盤後**零股，那個在 Fugle 文件裡仍然查不到；且額度也擠不出來。<br>**要改的是理由，不是結論**：§10 條目 5 的解除條件不是「轉 Shioaji」，而是**訂閱額度**。 |

### 新暴露的取捨：`trades` 與 `aggregates` 互斥

這是 5 個額度造成的、#13 定案時不知道的選擇：

| 選 `trades`（5 訂閱） | 選 `aggregates`（5 訂閱） |
|---|---|
| ✅ **逐筆**成交，帶流水號與微秒時間戳 | ❌ 聚合後的當前狀態，**逐筆流消失** |
| ✅ 「穿越門檻」與「單筆大量」警示可行 | ❌ 上述兩種警示的 worker 端優勢**歸零** |
| ❌ 不含最佳五檔 | ✅ 含最佳五檔、內外盤量、成交筆數 |
| ❌ 漲跌幅需自行由 `previousClose` 算 | ✅ provider 算好 `change`/`changePercent`（但**含試撮**） |

> **它同時是 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15)（警示）與 [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14)（分析頁）之間一條未被記錄的耦合**：選 `trades` = 警示精度優先，選 `aggregates` = 畫面資訊量優先。額度不允許兩者兼得。

### 三處經查證**成立**的敘述（不是更正，是確認）

| 出處 | 敘述 | 結果 |
|---|---|---|
| §6 | 統一 Quote 的量一律為**當日累積成交量** | ✅ 成立**且零成本**——`trades.volume` 直接就是累積量，adapter 不需自行累加，也沒有「worker 重啟累加值歸零」的坑 |
| §8 | Fugle 每 30 秒送 heartbeat，用來區分休市與斷線 | ✅ 官方明文成立 |
| §2 | SDK callback 不在 event loop 上，只能 `call_soon_threadsafe` | ✅ **原始碼層級佐證**成立（SDK 用 `Thread(target=run_forever)`） |

### 另外兩件必須寫進 adapter 的事（原文完全沒有）

1. **`isTrial` 試撮旗標必須濾掉。** 08:30–09:00 與 13:25–13:30 的試撮價會照常推送。未濾會用**不會成交的假價格**觸發警示——且不會有任何錯誤訊息。
2. **`trades.volume` 是非必填欄位**，官方範例中盤後定價那筆就缺席。**缺席不可當 0**（當 0 會讓「累積量」倒退，任何以量為基準的判斷都會錯亂）。

### §9 的退避參數沒有 Fugle 依據

§9 整套推導（登入額度百分比、「停權期間反覆重試會延長停權」）**來源全部是 Shioaji**。Fugle 對重連頻率與停權機制**零公布**。這不是錯誤，但現行行文會讓讀者以為那些數字對現行 provider 也有官方依據——**§9 需加註依據來源與適用 provider**。

---

## 總覽

| 項目 | 結論 |
|---|---|
| 誰連行情源 | **只有 `quote-worker`**，`api` 與瀏覽器都不連 |
| adapter 形式 | **原生 binding**（`import` SDK），不跑 sidecar |
| 額度的表達 | `ProviderCapabilities`，**核心程式不得寫死數字** |
| worker → api | **Postgres `LISTEN/NOTIFY`**（雙向） |
| api → 瀏覽器 | **SSE**（`text/event-stream`） |
| 訂閱範圍 | 持股中的台股標的，不含自選股與指數 |
| 節流 | worker 端 conflation，**全域 800ms 節拍批次送** |
| 開頁取價 | 四層階梯，第 2 層向 worker 索取全量快照 |
| worker 開機時段 | **09:00–13:35**（不含盤後零股） |
| 重連 | **指數退避 1s→300s + jitter**，穩定 60 秒才重置 |

---

## 0. 資料流全景

```
                     ┌──────────── 只在 09:00–13:35 開機 ────────────┐
                     │                                              │
  Fugle WebSocket ──▶│  quote-worker                                │
  (wss://, 5 檔)     │   ├─ adapter（吸收 provider 差異）             │
                     │   ├─ 800ms 節拍 conflation                    │
                     │   └─ 記憶體：最新報價表                        │
                     └───────────────┬──────────────────────────────┘
                                     │
                       NOTIFY 'quote_updates'   ◀── 每 800ms 一則批次
                       LISTEN 'quote_request'   ──▶ api 索取全量快照
                                     │
                              ┌──────┴──────┐
                              │  PostgreSQL │   ← 只是傳話筒，報價不落地
                              └──────┬──────┘
                                     │
                     ┌───────────────┴──────────────────────────────┐
                     │  api（scale-to-zero，有人用才醒）              │
                     │   ├─ LISTEN 連線（有 SSE 連線時才持有）         │
                     │   └─ 記憶體：最新報價表                        │
                     └───────────────┬──────────────────────────────┘
                                     │
                              SSE (text/event-stream)
                                     │
                                 瀏覽器
```

**三個要注意的性質：**

1. **箭頭方向決定了成本。** worker 從不主動連 `api`——tick 只是丟進 Postgres，`api` 醒著才收得到。這讓「沒人在看就不花錢」由架構保證，而不是靠額外機制去補（§3）。
2. **Postgres 在這條路上不是儲存，是傳話筒。** 報價全程只存在於兩個行程的記憶體裡，符合 `CONTEXT.md` 對 Quote 的定義「具時效性且不落地」與 `data-model.md`「刻意不做 `quote` 表」。
3. **`quote-worker` 整條路徑都可以不存在。** `tech-stack.md` §4 已定它是可選元件，本文的每個機制都必須在它缺席時有明確的降級行為（§7）。

---

## 1. 連線模型：只有 `quote-worker` 連行情源

### 決定

`quote-worker` 是**唯一**持有行情源連線的行程。`api` 不連、瀏覽器更不連。

### 為什麼

這題其實被兩把刀同時判死，沒有討論空間：

| 刀 | 出處 |
|---|---|
| Fugle 免費層**同時連線數 = 1** | [#2 §2.1](../research/tw-realtime-quote-sources.md) |
| 券商行情**不得轉供第三人**，富果條款明文禁止「傳送予第三人」 | [#2 §2.6](../research/tw-realtime-quote-sources.md) |

瀏覽器直連還會多一個問題：API Key 必須發到前端，等於公開。

### 連帶結論：本機開發預設不接真行情

`1 條連線` 是**帳號級**的，不是行程級的。**開發機與正式站不能同時跑 `quote-worker`**——第二個連上去不是排隊，是其中一個被拒或被踢。

而開發時一定會反覆重啟 worker，正式站的 worker 又正在線上。所以：

> **本機 `quote-worker` 預設使用 fake provider**（重播錄製的 tick 檔）。要接真行情必須顯式開旗標，且開旗標前必須確認正式站 worker 已停。

**被淘汰的兩條路：**

| 選項 | 輸在哪 |
|---|---|
| 靠排程互斥（正式站只在盤中開，開發就避開盤中） | **賭紀律**，而盤中正是唯一能觀察真實 tick 行為的時段——等於永遠測不到要測的東西 |
| 申請第二組憑證 | 富果條款明載「**每位使用者僅限申請及使用一個帳號**」，且禁止「註冊多個帳號規避使用限制」。**直接違約** |

**fake provider 不是為了測試而多做的東西**，它有三個既有需求剛好共用同一批錄製檔：

1. `tech-stack.md` §4 要求「adapter 必須從第一天就可換」——fake provider 是這個介面的**第一個消費者**，會在真的換 Shioaji 之前就先驗證抽象層是否抽對。
2. `tech-stack.md` §7 的契約測試需要「錄真實回應當 fixture」，本來就要有這些檔案。
3. 它可以宣告 `max_subscriptions=3` 來在本機重現額度耗盡（§5），不必等到真的買第六支股票才發現那條路徑沒寫對。

**未來轉 Shioaji 後這條規矩更重要，不是更不重要**：Shioaji 的懲罰是**停權**而非拒絕，且官方明載「停權期間反覆重試 `login()` 會延長停權」（[#2 §2.4](../research/tw-realtime-quote-sources.md)）。

---

## 2. adapter：原生 binding，能力用宣告的

### 決定

`quote-worker` 直接 `import` provider 的 Python SDK，**不跑本機 HTTP sidecar**。

### 為什麼

`tech-stack.md` §1 曾記載 Shioaji 可以用 `shioaji server start` 起一個本機 HTTP + SSE server。但這條路在 v1 走不通，理由是**Fugle 根本沒有這個東西**——它只有 `wss://` WebSocket。

選 sidecar 等於「Fugle 走 WebSocket、Shioaji 走 SSE」，兩個 provider 是**兩種形狀完全不同的介面**，而 `tech-stack.md` §4 要求所有 provider 專屬結構止於 adapter 邊界。原生 binding 反而讓兩家統一成同一種形狀：**都是 SDK 給你一個 callback**。

至於 sidecar 的行程隔離好處（Rust core 崩潰不會拖垮 worker）：那換不到東西。`api` 已被規定必須能在 worker 缺席時降級運作，**worker 崩潰與 worker 沒開機對系統而言是同一個狀態**，已經有處理路徑。多養一個行程去保護一個「已經允許失效」的元件，是白付成本。

### ⚠️ 硬性規則：callback 不在 event loop 上

Fugle 與 Shioaji 的 SDK **都是從自己的背景執行緒**呼叫 callback 的，不在 asyncio event loop 上。

> **callback 內只做一件事：`loop.call_soon_threadsafe(...)` 把 tick 交回 event loop。其餘一律不做。**

在 callback 裡直接碰 asyncio 物件（queue、connection）是 race condition，而且是「本機測沒事、盤中量大才炸」的那種——這是選原生 binding 必須付的帳。

### ⚠️ 硬性規則：額度也是 provider 的屬性

`tech-stack.md` §4 規定了「資料格式差異必須被 adapter 吸收」，但只講到欄位命名與列舉值。**額度限制同樣是 provider 的屬性，同樣不能滲進核心。**

```python
@dataclass(frozen=True)
class ProviderCapabilities:
    max_subscriptions: int    # fugle_free=5      shioaji=200   fake=3
    max_connections: int      # fugle_free=1      shioaji=5
    supports_snapshot: bool   # fugle_free=False  shioaji=True
    supports_odd_lot: bool    # fugle_free=False  shioaji=True
```

> **`src/core/` 內不得出現字面量 `5`。** 所有「是否超過訂閱額度」的判斷一律讀 `capabilities.max_subscriptions`。

**這條同時修好了一個既有的洞**：`tech-stack.md` §4 發現「Fugle 免費層沒有快照 API，所以降級路徑改用 yfinance」，但當時是**寫死成另一條路徑**在處理。改成讀 `supports_snapshot` 之後，轉 Shioaji 時快照路徑會自動可用，**不需要有人記得回來改**。

### ⚠️ 硬性規則：統一 Quote 型別的量必須是「當日累積」

理由屬於 §6，但約束落在 adapter 邊界上，故一併記於此：**兩家 provider 的原始成交量欄位語意由 adapter 統一為「當日累積成交量」，不得向核心交出「單筆成交量」。**

---

## 3. `quote-worker` → `api`：Postgres `LISTEN/NOTIFY`

### 決定

用 Postgres 的 `LISTEN/NOTIFY`，**不引入 Redis**。

### 先把量級算出來

| | 值 | 來源 |
|---|---|---|
| 訂閱標的 | 5 檔 | Fugle 免費層上限 |
| 節流節拍 | 800ms | `dashboard-ui.md` §4 |
| **上界** | **1.25 則/秒**（批次，見 §6） | 推導 |

這個數字小到所有候選方案都能跑。**所以選型不該用效能決定，該用元件數與失效語意決定。**

### 為什麼不是 Redis

Redis 的 pub/sub 語意與 `LISTEN/NOTIFY` 完全一樣（都是 fire-and-forget），效能優勢在 1.25 則/秒下毫無意義。它真正的價值是可以順便當「最新報價快取」——但 §7 的方案不需要跨行程快取，**那是還沒發生的需求**。

現在為一個假設的未來多養一個付費元件，與 issue #1「成本越低越好」的前提相衝突。若日後真的需要共享快取，再把本節換掉，adapter 邊界內的改動很小。

### 為什麼不是 worker 直接連 `api`

**這條有致命傷。** #17 已定方向是 `api` 走 **scale-to-zero**。worker 若直接往 `api` 推 tick，那些請求**會把 `api` 叫醒**——即使此刻根本沒有人在看網站。盤中 4.5 小時 `api` 被自己的行情流強制常駐，scale-to-zero 直接失效。

`LISTEN/NOTIFY` 的性質正好相反：**`api` 必須先醒著、先持有 `LISTEN` 連線，才收得到 tick。** 「沒人在看就不該花錢」由架構保證，不需要額外機制。

### 丟掉 tick 是正確行為，不是妥協

若沒有任何 `api` 在聽，代表沒人在看盤，此時 tick 應該消失。**持久化佇列在這裡是有害的**——它會在 20 分鐘後把一則早已過期的報價送達。`CONTEXT.md` 明定 Quote「具時效性」，過期的 tick 比沒有 tick 更糟。

### ⚠️ 硬性規則：listener 必須有 keepalive 與重新 `LISTEN`

`LISTEN` 需要一條持續開著的連線，而閒置的 TCP 連線會被 NAT、負載平衡器或雲端網路無聲切斷。更陰險的是這個情境：

> **盤中、`api` 醒著、使用者正盯著螢幕看報價跳——此時資料庫看起來是完全靜止的。**

因為畫面上在動的每個數字都走 SSE，**沒有任何 HTTP 查詢打到 DB**。會自動休眠的託管資料庫只看到「十分鐘沒有 query」，於是休眠，順手掐掉 listener。而這恰好是報價最該通的時刻。

因此：

1. **listener 連線必須有應用層 keepalive**（定期在同一條連線上發一個輕量查詢）。
2. **重連後必須重新 `LISTEN`。**
3. **listener 中斷必須反映到前端連線狀態指示器**，不可只監看行情源那一端——否則畫面會顯示「即時連線」而價格靜止。
4. **`api` 在沒有任何 SSE 連線時不持有 `LISTEN`**，省掉閒置連線，也讓 keepalive 只在真的有人看時才跑。

> 這與 [#2 §2.7](../research/tw-realtime-quote-sources.md) 記載永豐官方 Pro App 的「SSE 重連後自動重新訂閱全部商品」是同一個形狀：**斷線是常態，重連後的重建是必要設計，不是例外處理。**

#### 2026-08-06 查證：上面那段預言是字面成立的，而且門檻更短

[託管平台排程與 DB 休眠查證](../research/scheduling-and-db-sleep.md) §4 證實 Neon 官方 compatibility 文件幾乎是為這個情境寫的：

> "…**notifications and listeners defined using NOTIFY/LISTEN commands only exist for the duration of the current session and are lost when the session ends.**"
> "**The Neon cloud service automatically closes idle connections after a period of inactivity.**"

門檻是 **5 分鐘**（不是本文原本假設的十分鐘），且 **Neon Free plan 的 scale-to-zero 設定是固定的、關不掉**（關閉需付費方案，而關掉就等於 24/7 計費）。

**上面第 1 條的 keepalive 確實擋得住**——判準是「有沒有 query」而不是「有沒有連線」。代價是 keepalive 讓 compute 在盤中永不休眠，開始消耗免費層額度。

### ⚠️ 硬性規則：listener 一律走 direct connection，不得走 pooled endpoint

這是 2026-08-06 查證新增的規則，#13 定案時未知。

**transaction 模式的連線池會在每個 transaction 結束後把連線收回池子，`LISTEN` 因此完全失效**——而預算內的託管方案幾乎都是 transaction 模式：

| 託管方案 | pooler 模式 | pooled endpoint 支不支援 `LISTEN/NOTIFY` |
|---|---|---|
| Neon | PgBouncer **transaction** | **❌ 官方明列不支援**（可用去掉 `-pooler` 後綴的 direct 連線繞過） |
| Render Postgres 付費 | PgBouncer **transaction** | **❌ 官方明列不支援**，官方把 `LISTEN`/`NOTIFY` 列為必須繞過連線池的功能 |
| Supabase（Supavisor） | 6543 transaction／5432 session | ⚠️ **未能查證**——官方只講 prepared statements，對 `LISTEN/NOTIFY` 隻字未提 |
| Fly Managed Postgres | PgBouncer **預設 session** | ✅ **唯一官方明文說可用**，direct URL 文件直接寫 "Use this for migrations, advisory locks, or `LISTEN/NOTIFY`" |

**為什麼必須寫成規則而不是備註**：「serverless 就該用 pooled connection」是一條非常強的直覺，日後任何人（包含 agent）依它把連線字串改回 pooled，**報價扇出會在完全沒有錯誤訊息的情況下靜止**——`LISTEN` 指令本身不會報錯，只是永遠收不到通知。這與本專案反覆點名的靜默失效形態相同。

> 連線數不是問題：Neon 的 `max_connections` 最小也有 100 條。

### 頻道

| 頻道 | 方向 | 內容 |
|---|---|---|
| `quote_updates` | worker → api | 每 800ms 一則批次（§6），以及全量快照回應（§7） |
| `quote_request` | api → worker | `api` 索取全量快照 |

`NOTIFY` 的 payload 上限為 8000 bytes。5 檔標的的批次遠低於此，但**這是 provider 換成 Shioaji（200 檔）後會撞到的天花板**，屆時需改為分批送出——列入 §10。

---

## 4. `api` → 瀏覽器：SSE

### 決定

Server-Sent Events（`text/event-stream`），**不用 WebSocket**。

### 先釐清一個長期的詞彙混淆

「WebSocket」在本專案裡一直同時指兩個不同層的東西，而它們從未被分開討論：

| 出處 | 講的是哪一層 |
|---|---|
| #5 研究票標題「常駐 **WebSocket** 後端」 | **上游**：worker ↔ 行情源 |
| Fugle 端點 `wss://api.fugle.tw/...` | **上游** |
| #10「瀏覽器 WebSocket API 不支援自訂 header」 | **下游**：api ↔ 瀏覽器 |

**#5 自己就抓到過這個混淆一次**，其結論欄寫著「後端是 WebSocket **client** 不是 **server**」。上游那條**必然**是 WebSocket（Fugle 只給 `wss://`，沒得選），而它與「瀏覽器怎麼收報價」是**完全獨立的兩個決定**。本節決定的是下游，這是它第一次被真正選擇。

（#10 的認證決策雖提到 WebSocket，但它問的是「session 怎麼帶」，而 **cookie 對 SSE 與 WebSocket 一樣有效**——兩者的 handshake 都是同源 HTTP 請求。所以那張票沒有把下游鎖死。）

### 為什麼是 SSE

把教科書上的差異逐項對到本專案，八項裡有五項是平手或不成立：

| 面向 | 差異 | 在本專案成不成立 |
|---|---|---|
| 方向 | WS 雙向，SSE 單向 | ❌ 上行需求為零，見下 |
| 每則開銷 | WS 省幾 bytes | ❌ 1.25 則/秒，差距是奈米級 |
| 二進位 | WS 支援 | ❌ 我們送 JSON |
| 連線數上限 | SSE 在 HTTP/1.1 下同網域 6 條 | ❌ Caddy 對 TLS 預設走 HTTP/2，多工後限制消失 |
| 認證 | 兩者都吃 cookie | ❌ 打平 |
| **除錯** | SSE 可 `curl -N` 直接看 | ✅ **成立且重要** |
| **代理** | SSE 是純 HTTP，Caddy 零設定 | ✅ 成立 |
| **重連** | SSE 內建 | ⚠️ 成立，但是雙面刃 |

**上行需求為零這點是決定性的**：瀏覽器唯一要送給後端的是「我現在在看哪些標的」，而那本來就該是一個普通的 HTTP 請求——可快取、可重試、有狀態碼、進得了 access log。把它塞進長連線的自訂訊息格式裡，等於自己發明一套沒有 HTTP 語意的 RPC。

**除錯能力在單人維運的專案上是實打實的資產**：當報價不動時，要回答的問題是「tick 到底有沒有出 `api`」，而 SSE 的答案是**一行 `curl -N`，在正式站上就能跑**。`dashboard-ui.md` §9 記錄的三個原型 bug 全是「畫面看起來正常但底下壞掉」，這種除錯手段不是便利，是可維護性本身。

**還有一點常被忽略**：`dashboard-ui.md` §4 已把節流下限定在 800ms。**當你已經決定把資料放慢到 800ms 一次，再去選一個「每則省 4 bytes、少幾微秒」的協定就沒有意義了**——需求本身把 WebSocket 的強項消掉了。

### 「未來要下單所以需要雙向」不成立

issue #1 的 Out of scope 明列「**自動下單／程式交易：本圖只到看盤與記錄，不碰任何下單路徑**」。而且即使日後要做，下單也該是一個有冪等鍵、有 HTTP 狀態碼、進得了 access log 的 `POST`，不該塞進長連線。

### ⚠️ 硬性規則：三條

**（a）非交易時段前端主動 `close()`。**

`EventSource` 的自動重連是**無條件且不退避的**（預設約 3 秒一次，永遠不停）。分頁開著過夜 + `api` scale-to-zero = **整夜每 3 秒把機器叫醒一次**——與否決「worker 直推 api」是同一個理由。`dashboard-ui.md` §3 已有「非交易時段」這個一級狀態，前端本來就知道現在該不該連。

**（b）server 以 `retry:` 欄位控制重連間隔。** 這是 SSE 協定內建的、由 server 指定 client 下次等多久。收盤時送一個大的 `retry:` 值再關閉串流。

**（c）不使用 `Last-Event-ID` 重播。**

SSE 有內建續傳：server 給每則訊息一個 `id:`，client 重連時瀏覽器自動帶 `Last-Event-ID`，server 據此補送。**看起來剛好解掉「斷線期間的價格怎麼補」，但它在這裡沒有價值**——報價要的是「現在多少」，不是「剛剛經過哪些價位」。斷線 30 秒後補送 12 則過期 tick，只會讓畫面倒著跑一遍再跳到現價。

**寫下這條的目的是防止日後有人（包括 agent）看到這個欄位就以為該用它。** 重連後只送當前快照（§7）。

### 待實作驗證

反向代理若緩衝回應，SSE 會變成「累積一大塊才一次吐出」。nginx 需要 `proxy_buffering off;`；**Caddy 對 `text/event-stream` 是否自動關閉緩衝，本文未經第一手查證**，列為實作時必須驗證的項目。驗證方法就是上面那行 `curl -N`——看數字是否逐筆出現。

SSE 也沒有內建 heartbeat，需定期送註解行（`: keepalive\n\n`）撐住連線。

---

## 5. 訂閱範圍

### 決定

**訂閱集合 = 持股中市場屬於 `TWSE` / `TPEX` 的標的。** 不含自選股、不含大盤指數、**不做動態換入換出**。

### 額度的算式

| 事實 | 來源 |
|---|---|
| Fugle 免費層訂閱上限 5 檔 | [#2 §2.1](../research/tw-realtime-quote-sources.md) |
| 使用者持股在 5 檔以內 | issue #1 已定調前提 |
| 美股不需即時，走 yfinance 盤後 | issue #1 |
| 儀表板四個面板**沒有大盤指數** | `dashboard-ui.md` §1 |

美股不佔額度是唯一的餘裕來源；不需要 `indices` 訂閱則省下一格。

### 為什麼不做動態換入換出

「開個股分析頁就臨時把該檔換進來」聽起來很自然，但：

1. **額度沒有餘裕**，換進來就得踢掉一檔持股，而被踢掉那檔的價格會在使用者沒察覺的情況下靜止。
2. **頻繁 subscribe/unsubscribe 是停權風險。** [#2 §2.4](../research/tw-realtime-quote-sources.md)：Shioaji「持續違規將暫停該 IP 及 ID 使用權」；富邦文件明寫「短時間內建立大量 Socket 連線會被判定為惡意攻擊」。**為了瀏覽便利去反覆敲一個會停權的介面，風險報酬比是負的。**
3. **它會把 `quote-worker` 耦合到「使用者此刻在看哪一頁」**——那是 session 狀態，屬於 `api`，而 `api` 隨時可能睡著。讓常駐元件依賴一個會消失的東西來決定訂閱什麼，是把可選關係接反了。

### ⚠️ worker 自己從資料庫算出訂閱清單

`quote-worker` **不問 `api`**：Transaction 是唯一事實來源，worker 有 DB 連線就推導得出 Position。這讓 worker 完全自足——`api` 睡著時它照跑，`api` 重啟時它不受影響。

### 超過額度時：明確中斷，不優雅降級

> worker 啟動時若算出應訂閱標的數 > `capabilities.max_subscriptions`，**訂閱其中 N 檔（依 `instrument_id` 這類確定性順序即可），並產生一則明確的警示告訴使用者「行情額度已滿，請啟動 #8」。**

**刻意不做的事**：不按市值挑「最重要的」、不做逐列降級 UI、不修訂 `dashboard-ui.md`。

理由是這個狀態**不該存在超過幾天**。issue #1 已把「持股 ≤5 檔」列為已定調前提，並明寫持股超過 5 檔就是**啟動 #8（轉 Shioaji）的信號**——它是前提失效的信號，不是要優雅降級的常態。為一個過渡狀態付出永久的規格、實作與測試成本，方向是錯的。

這也符合本專案一貫的立場：#19 定「當沖與信用交易一律**中斷匯入**」「標的反查未命中就**中斷問人**」，`dashboard-ui.md` 定「永遠亮著等於沒有」。**前提破了就明確停下來告訴人，不要悄悄挑一個看起來合理的行為繼續跑。**

### ⚠️ 交給 #15 的限制

**v1 的即時警示只能設在持股標的上。** 非持股標的沒有訂閱額度，就沒有即時報價可以觸發警示，只能以每日收盤價評估（變成「收盤後才通知」）。

**這不是 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 可以自己選的**，是被行情額度決定的。

---

## 6. 節流：worker 端 conflation，全域 800ms 節拍

### 決定

在 `quote-worker` 內、進 `NOTIFY` 之前，以 **800ms 為全域節拍**把該窗口內有變動的標的**合併成一則訊息**送出。窗口內同一檔的中間值**直接丟棄**。

### 為什麼是 800ms

`dashboard-ui.md` §4 定 tick 直條 800ms 淡出，並明寫「推播節流頻率**快過這個數字沒有意義**——眼睛還沒看完上一次閃動，下一次已經蓋上來」。**800ms 是下界（不能更快），不是效能目標。**

### 為什麼要節流

台股盤中逐筆撮合，熱門股單秒可能數十筆成交。不節流則每筆都要發一次 `NOTIFY`（而 `NOTIFY` 在 commit 時要取全域鎖）、每筆都觸發一次前端重繪。`tech-stack.md` §3 花了整段講「持股表必須每列各自訂閱，否則每個 tick 重繪整棵子樹」——**節流是同一個問題的上游解法，兩者都要做。**

### 為什麼在 worker 端

往下游每多走一步，能省的東西就少一樣。在源頭砍掉，`NOTIFY` 次數、`api` 處理、SSE 位元組、瀏覽器重繪**全部一起省**。未來若有第二個 `api` 實例，worker 節流一次，兩邊都受益。

### 為什麼是全域節拍而非每檔各自計時

| | 每檔各自 800ms | **全域 800ms 批次** |
|---|---|---|
| 訊息數 | 約 6 則/秒 | **1.25 則/秒** |
| 前端 | 5 次獨立更新，各列閃動時間錯開 | **1 次批次更新，可對齊單一 `requestAnimationFrame`** |

畫面上那幾支股票本來就該同時更新——使用者看的是一張表，不是 5 個獨立的東西。`dashboard-ui.md` §9 已要求高頻重繪以 `requestAnimationFrame` 合併、每影格至多一次；後端按節拍送，前端就自然只有一個合併點。

**窗口內完全沒變動的標的不出現在訊息裡**（不送「沒變」）。

### ⚠️ conflation 的前提：量必須是累積量

conflation 只有在「**每則報價都是完整的當前狀態**」時才是無損的。

若統一 Quote 型別的成交量是「**這一筆**成交量」，丟掉中間值就等於丟掉成交量——**而且不會有任何錯誤，只會讓數字默默偏小**。這正是本專案反覆在防的靜默錯誤形態（#19 的 `status` 欄、#10 的 `user_id`、#4 的 put/call ratio）。

> **統一 Quote 型別的量一律為「當日累積成交量」，不得使用單筆量。** provider 原始欄位差異由 adapter 吸收（§2）。

### 交給 #15 的事實

worker 端在 conflation **之前**看得到完整未節流的價格流，`api` 只看得到取樣後的。[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 待決事項 3 要選「警示在串流管線裡即時比對還是獨立排程」時，這是關鍵差異——**在 worker 評估看得到瞬間穿越門檻的價格，在 `api` 評估則會漏掉。**

---

## 7. 開頁取價：四層階梯

### 問題

SSE 只送**有變動的**報價（§6）。但使用者開頁的瞬間什麼都還沒變，因此什麼都收不到——冷門股可能十分鐘沒成交，畫面就空十分鐘。

更關鍵的是：`api` 走 scale-to-zero，早上打開網站時它是**剛醒來**的，記憶體一片空白。

### 決定：四層階梯

| 順位 | 來源 | 何時用到 |
|---|---|---|
| 1 | `api` 記憶體中的最新報價表 | 已連著看一陣子 |
| 2 | **向 worker 索取全量快照**（`NOTIFY 'quote_request'`） | `api` 剛醒來 |
| 3 | **yfinance 延遲報價** | 盤中但 worker 缺席 |
| 4 | **`daily_close` 收盤價** | 非交易時段 |

第 2 層等一個短逾時（約 1 秒）無回應即往下掉。

### 為什麼第 2 層是「主動索取」

`LISTEN/NOTIFY` 是**雙向**的，§3 只用了一個方向。第 2 層就是把另一個方向用起來：

```
api 醒來  ──NOTIFY 'quote_request'───▶  worker
api      ◀──NOTIFY 'quote_updates'────┘  （回送記憶體中的最新報價全量）
```

**零新元件**——用的還是那條已經開著的 Postgres 連線。而且 worker 記憶體裡**本來就有**最新報價（§6 的節拍窗口就是靠它比對「有沒有變」），不需要為此多存任何東西。

**這沒有違反「Quote 不落地」**：資料全程在記憶體，Postgres 只是傳話筒。

**被淘汰的選項：**

| 選項 | 輸在哪 |
|---|---|
| worker 每 30 秒無條件廣播全量 | 沒人在看也一直廣播；且新醒來的 `api` 仍可能要等 30 秒 |
| 開頁時去 yfinance 抓延遲報價墊著 | 外部 HTTP 慢、有速率限制；**明明隔壁有新鮮的卻去拿冷凍的**。它是第 3 層降級，不是第一選擇 |

### ⚠️ 第 3、4 層必須外顯

`dashboard-ui.md` §3 規定降級要**同時**做兩件事：顯示橫幅說明 **＋ 報價數字降透明度**。第 3 層（yfinance 延遲 15 分鐘）在畫面上與即時價**長得一模一樣**，不標示的話使用者會盯著 15 分鐘前的價格做判斷。

---

## 8. 交易時段與休市判斷

### 決定

`quote-worker` 開機時段 **09:00 – 13:35**，**不涵蓋盤後零股**（13:40–14:30）。

### 為什麼不涵蓋盤後零股

| | 開機時段 | 每日時長 |
|---|---|---|
| **選定** | 09:00–13:35 | 4h35m |
| 被淘汰 | 09:00–14:35 | 5h35m（**+22%**） |

1. **零股成交價通常貼著當日收盤價**，即時盯著它的資訊價值極低。
2. 更硬的一點：**盤中零股是 Shioaji 才明確具備的能力**（`intraday_odd` 參數，[#2 §2.3](../research/tw-realtime-quote-sources.md)），**Fugle 免費層的支援情況研究票未查證**。涵蓋它等於押注一個沒查證的能力。

零股持倉的市值仍然完全正確，只是收盤後才以當日收盤價更新。

### 休市判斷：三層

| 層 | 做法 | 擋掉什麼 |
|---|---|---|
| 1 | **週六日不開機** | 一半的日子，零成本 |
| 2 | 查 **TWSE 官方休市日曆**（`openapi.twse.com.tw`，[#3](../research/tw-fundamental-chip-data-sources.md) 已確認屬政府資料開放授權） | 國定假日 |
| 3 | **連得上但收不到資料 = 休市** | **颱風假等臨時停市** |

### ⚠️ 「沒資料」與「斷線」必須用連線狀態區分

「這支股票十分鐘沒動」與「斷線了」在畫面上長得一模一樣，但一個正常、一個故障。搞錯的後果正是 `dashboard-ui.md` §3 最在意的：把正常狀態報成異常，久了使用者就學會忽略警告。

好在有乾淨的判準——**Fugle 每 30 秒送 heartbeat**（[#2 §2.3](../research/tw-realtime-quote-sources.md)）：

> **連得上、heartbeat 還在、但沒有成交資料 → 正常**（休市或該檔無人交易）。worker 若持續無資料，過一段時間自行關機省錢。
> **連不上或 heartbeat 停止 → 異常**，即 `dashboard-ui.md` §3 的「盤中斷線」（琥珀色）。

第 3 層解掉的正是「颱風假沒有 API 可查」的問題——**不需要知道為什麼沒資料，行為是一樣的：省錢關機，並且不謊報成故障。**

### ⚠️ `daily_close` 的產生責任不屬於 `quote-worker`

`tech-stack.md` §4 已定 worker 是**可選元件**。若收盤價由 worker 順手寫入，那麼把 worker 關掉一週就會讓**歷史資料缺一週的洞**——而 `daily_close` 是 [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 歷史績效的唯一價格來源（`data-model.md`：「歷史資產曲線由 Transaction + `daily_close` + `exchange_rate` 重算」）。

> **可選元件不能持有必要資料的產生責任。**

因此收盤價走獨立的盤後排程。**但「那個排程跑在哪裡」是 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) 的題目**——`api` 會 scale-to-zero，排程不能單純寫在它裡面。本文只負責定下這條分工。

---

## 9. 斷線與重連

### 決定

**指數退避**：`base = 1s`，逐次加倍，**上限 300s**，實際等待再乘上 `random(0.5, 1.0)` 的抖動。

```
1s → 2s → 4s → 8s → 16s → 32s → 64s → 128s → 256s → 300s → 300s → ...
```

從斷線爬到上限約 8.5 分鐘。**不主動放棄，一路重試到收盤。**

### 為什麼上限是 5 分鐘

| 上限 | 盤中最多嘗試 | 佔 Shioaji 每日 1000 次登入額度 |
|---|---|---|
| **300s（選定）** | 約 54 次 | **5%** |
| 30s（被淘汰） | 約 540 次 | **54%** |

30 秒上限看似「恢復比較快」，但那是錯覺——盤中斷線通常不是 30 秒能自癒的，多出來的 486 次重試絕大多數是白費，卻吃掉一半以上的登入額度。而該額度是**全天共用**的：若當天還重啟過 worker、或程式陷入重啟迴圈，就會在下午撞到上限**被鎖到隔天**。

[#2 §2.4](../research/tw-realtime-quote-sources.md) 的原文是這條規則的來源：

> 持續違規將暫停該 IP 及 ID 使用權……**停權期間反覆重試 `login()` 無法解除限制，反而可能延長停權時間。**

**重連寫得太積極，會把「暫時斷線」變成「帳號被鎖」——從能修的問題變成不能修的問題。**

### 為什麼要抖動

單一 client 的情境下抖動不是為了避免驚群效應，而是**避免與對方的週期性行為同步**：若行情源每分鐘整點做某件事而導致斷線，完全規律的重試排程可能每次都撞在同一時間點，讓人誤判成自己的問題。

### ⚠️ 最容易寫錯的地方：退避計數不可在連線成功時立刻重置

直覺寫法是「連上了 → 計數器歸零」。但考慮：

```
連線成功 → 0.3 秒後被踢掉 → 計數器已歸零 → 等 1 秒重試 → 又連上 → 又被踢 → ...
```

**退避完全失效，變成每秒重連一次**——正是上面那條警告的場景。

> **連線必須穩定維持 60 秒才重置退避計數。** 斷斷續續的連線在退避的眼中仍算「還在故障中」。

這個 bug 在正常情況下**永遠不會出現**，只有在行情源出狀況（也就是最需要退避保護的時候）才觸發。

`tech-stack.md` §7 已把「用假時鐘測退避序列」列為必測項目，原文是「唯一『寫錯會導致外部帳號被鎖』的邏輯」。**該測試必須包含 flapping 案例**，否則測不出這個 bug。

### ⚠️ 重連成功後必須重新訂閱全部標的

不可假設訂閱還在。[#2 §2.7](../research/tw-realtime-quote-sources.md) 記載永豐官方自家 Pro App 就是這樣做的（「SSE 重連後自動重新訂閱全部商品、斷線期間鎖定下單按鈕」）——**等於官方承認斷線是常態、重新訂閱是必要設計。**

### 斷線期間的畫面

`dashboard-ui.md` §3 已定，此處不重複規定：「盤中斷線 最後報價 11:42」、旋轉方塊、琥珀色，**且所有報價數字降透明度**。§3 特別強調兩件事要同時做——只掛個小標記的話，使用者會盯著不動的價格好幾分鐘才發現。

---

## 10. 暫時性妥協與解除條件

> **本段是給後續 agent 讀的。** 以下每一條都不是技術判斷的結果，而是被外部條件（多半是「Shioaji 要開戶很麻煩」）逼出來的權宜。**看到這些限制時不要當成架構意圖去延伸或加固它們**——要做的是檢查解除條件是否已成立。

| # | 現在是什麼狀態 | 為什麼被迫如此 | 解除條件 | 解除時要做什麼 |
|---|---|---|---|---|
| 1 | 同時只能訂閱 **5 檔** | Fugle 免費層額度。**選 Fugle 純粹因為 Shioaji 需要開戶與強制下單測試（數個工作天），不是技術判斷** | [#8](https://github.com/NTUyu016/stock-analytic-platform/issues/8) 開通 Shioaji | 只改 `ProviderCapabilities` 的設定值（→200）。**若此時需要改動核心邏輯，代表 §2 的規則沒被遵守** |
| 2 | 即時警示**限持股標的** | 額度剛好被持股用完（§5） | 同上 | 解除 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 的標的限制 |
| 3 | 本機**不接真行情**，預設 fake provider | Fugle 免費層 **1 連線且是帳號級**（§1） | Shioaji 給 5 連線 | 可放寬本機直連；但 fake provider 仍應保留（契約測試與額度測試需要） |
| 4 | 開頁降級路徑走 **yfinance** 而非 provider 快照 API | Fugle 免費層「快照」欄位為不支援（[#2 §2.1](../research/tw-realtime-quote-sources.md)） | 同 #1 | 讀 `supports_snapshot` 即自動可用，**不需改程式** |
| 5 | 不涵蓋**盤後零股**時段 | Fugle 免費層零股支援未查證，不押注（§8） | 轉 Shioaji（有 `intraday_odd`）**且**確認使用者確有零股即時需求 | 延長 worker 開機至 14:35，成本 +22% |
| 6 | `NOTIFY` payload 單則上限 **8000 bytes** | Postgres 限制。5 檔遠低於此，故 v1 不處理 | 訂閱數增至 200 檔後會撞到 | 批次改為分段送出 |

**同類條目散落在其他文件中**（`quote-worker` 可選、v1 只支援現股、開放註冊降級為驗收標準……）。是否集中成一份 repo 層級清冊，由 [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 決定文件形狀時處理。

---

## 11. 對其他文件的修訂

| 文件 | 修訂 |
|---|---|
| [`tech-stack.md`](./tech-stack.md) §4 | 補上「**額度限制也是 provider 屬性**」；把「Fugle 無快照 → 改走 yfinance」從寫死路徑改為 `supports_snapshot` 能力宣告 |
| [`tech-stack.md`](./tech-stack.md) §10 | #13 的三個待決項（扇出機制、WS vs SSE、節流頻率）已答，指向本文 |
| [`dashboard-ui.md`](./dashboard-ui.md) §10 | 推播節流已定為 800ms 全域節拍，指向本文 |

---

## 12. 留給其他票

| 議題 | 票 |
|---|---|
| 警示在 worker（未節流）還是 `api`（已取樣）評估；即時警示限持股標的 | [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) |
| `daily_close` 盤後排程跑在哪裡（`api` 會 scale-to-zero）；worker 開關機排程的實作；資料庫是否可自動休眠 | [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) |
| 「暫時性妥協」條目是否集中成 repo 層級清冊 | [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) |
| 個股分析頁是否需要即時報價（目前額度不支援） | [#14](https://github.com/NTUyu016/stock-analytic-platform/issues/14) |
