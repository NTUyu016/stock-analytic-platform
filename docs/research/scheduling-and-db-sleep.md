# 排程落腳處、scale-to-zero 喚醒、與託管資料庫休眠

> 對應 issue：[#17 部署與成本](https://github.com/NTUyu016/stock-analytic-platform/issues/17)（同時解鎖 [#15 警示](https://github.com/NTUyu016/stock-analytic-platform/issues/15)）
> 查證日期：**2026-08-05 ~ 2026-08-06**（第三方定價與政策會變，逾期請重驗）
> 匯率：**1 USD = 32.315 TWD**（中央銀行公布之新臺幣對美元銀行間成交收盤匯率，**2026/08/05**，來源：<https://www.cbc.gov.tw/tw/lp-645-1.html>）
> 前置研究：[#5 常駐 WebSocket 後端的雲端部署選項與成本](./persistent-websocket-hosting.md)（2026-08-01）
>
> **本文不下推薦結論。** 定案由使用者在 grilling 中做。

---

## 0. 進場前的邊界

### 0.1 這份文件回答什麼

三個同時擋住 #15 與 #17 的空白：

1. **盤後排程（`daily_close` + 除權息預告 + outbox 排空）跑在哪裡**
2. **會不會出現半夜通知**
3. **outbox 排空機制是否可行**（延伸出「`api` 被叫醒送一則通知」的延遲下界）

### 0.2 已被 #5 淘汰、本文不再走的路

| 已淘汰 | 理由（#5） |
|---|---|
| AWS App Runner | 官方公告已不對新客戶開放 |
| Zeabur | 2026 年起 Shared Cluster 停用，改 BYOS，公開文件無價目表 |
| DigitalOcean | 亞洲只到新加坡/邦加羅爾，無日本節點 |
| Cloud Run Service（request-based） | 長連線全時段算 active，US$61/月 |

**但 #5 的總結論已被反轉。** #5 推薦「東京 VPS US$5/月」的前提是 `quote-worker` 需要 24/7 常駐；#13 定案後 worker 只在 **09:00–13:35** 開機，且 issue #1 的成本偏好明確是「**能中途停掉比 24/7 最便宜更重要**」。本文因此把重心放回 Fly.io / Railway / Render 這類可 scale-to-zero 的平台，VPS 只當對照組。

### 0.3 本專案的三個硬約束（會決定下面每一格是否可用）

| # | 約束 | 出處 |
|---|---|---|
| A | `api` 與 `quote-worker` 之間走 **Postgres `LISTEN/NOTIFY`** | [`realtime-quotes.md` §3](../spec/realtime-quotes.md) |
| B | `api` 走 **scale-to-zero**，且只在有 SSE 連線時持有 `LISTEN` | 同上 |
| C | 警示須在 **30 分鐘內**送達 Discord | issue #15（2026-08 已答） |

**約束 A 是本文最危險的一條。** 它讓「託管 Postgres 的 pooler 是什麼模式」從瑣事升級成**架構存亡問題**——詳見 §4。

---

## 1. 平台原生排程（Q1）

| 平台 | 有沒有原生 cron | 語法 | 最小間隔 | 時區 | 計費 |
|---|---|---|---|---|---|
| **Fly.io（Scheduled Machines）** | 有，但**不是 cron** | `--schedule=hourly\|daily\|weekly\|monthly` | **1 小時** | **無時區設定（官方文件未提供）** | 依 Machine 執行秒數計，無額外排程費 |
| **Fly.io（Cron Manager / Supercronic）** | 非平台功能，是**你自己養的一台常駐 Machine** | 標準 crontab | 1 分鐘 | 由容器內 TZ 決定（官方文件未載明） | 常駐機器費 + 各 job 的 Machine 費 |
| **Railway** | **有，內建** | 標準 5 欄 crontab | **5 分鐘** | **UTC only** | 依執行秒數計入一般用量費率，無獨立排程費 |
| **Render** | **有，內建 Cron Job 服務型別** | 標準 crontab | **未能查證**（官方文件未載明下限） | **UTC only** | **每個 job 每月最低 US$1**，其餘按秒計；單次上限 12 小時 |
| **VPS（Vultr / Linode 東京）** | `cron` / `systemd timer` | 標準 crontab | 1 分鐘 | **可設 `Asia/Taipei`**（`CRON_TZ=` 或 systemd `OnCalendar` 的時區欄位） | US$0（含在機器費裡） |
| **GitHub Actions（跨平台外部觸發）** | 有 | 標準 crontab | **5 分鐘** | 預設 UTC，**可指定 IANA 時區字串** | public repo 免費 |

### 1.1 Fly.io：原生排程**表達不出 09:00 Asia/Taipei**

這是本節最重要的發現。官方 `fly machine run` 文件：

> The flag sets the Machine's `config.schedule` property to start on a **"fuzzy `hourly`, `daily`, `weekly`, or `monthly` cycle."**
> "The Machine is started the first time when you run `fly machine run`, and again **once per (approximate) hour, day, week, or month**."

以及一條更硬的限制：

> **"Scheduled machines cannot be started via flyctl or Machines API commands, they will only run according to the schedule."**

官方 blueprint 也自承精度不足：

> "you don't get fine-grained control—**just interval buckets**" ／ 適用於 "anything where **'roughly once a day' is good enough**"

**推論**：Fly 的 Scheduled Machines **無法**表達「每個交易日 09:00 Asia/Taipei 開機」，也**無法**表達「盤後 14:30 跑批次」。它只能保證「大約一天一次」。而且一旦設了 schedule，那台 Machine 就**不能**再用 API 手動叫起來——等於同一台機器不能既是排程機又是可喚醒機。

Fly 官方給的替代路徑有兩條，兩條都**需要一台常駐機器**：
- **Cron Manager**：官方稱最 production-hardened，「a small Fly app that spins up temporary Machines—one per job—and tears them down afterward」；它自己得一直開著看 `schedules.json`。
- **Supercronic**：官方文件明講要 `fly scale count cron=1`，即**固定一台常駐**。

> ⚠️ 「養一台常駐機器來跑排程」與「能中途停掉比 24/7 便宜更重要」的偏好直接衝突。這不是說不能做，而是必須當作一個**明確的成本項**擺上桌（§7 有算式）。

來源：<https://fly.io/docs/machines/flyctl/fly-machine-run/>、<https://fly.io/docs/blueprints/task-scheduling/>、<https://fly.io/docs/blueprints/supercronic/>

### 1.2 Railway：UTC + 5 分鐘下限 + 必須自己 exit

官方原文：

> **"The shortest time between successive executions of a cron job cannot be less than 5 minutes."**
> **"Schedules are based on UTC (Coordinated Universal Time)."** 需自行「account for timezone offsets」。
> 服務必須「terminate as soon as they are done」並「close any connections, such as database connections, to exit properly」。
> **"If a previous execution remains active, Railway will skip the new cron job."**

最後一句是靜默失效的溫床：**上一次沒跑完，這一次直接被跳過，而且不會有錯誤。** 對「outbox 排空」而言，這代表一次卡住的 HTTP POST 會讓後續所有排空全部被跳過。

來源：<https://docs.railway.com/reference/cron-jobs>

### 1.3 Render：UTC，且有真正的「按次落地」計費下限

官方原文：

> **"All day and time ranges use UTC."**
> **"There is a minimum monthly charge of $1 per cron job service."**
> "Billing is prorated by the second, based on active running time during a given month."
> **"Render stops an active run after 12 hours."**
> 「guarantees that only one run of a given cron job is active at any time」

**最小間隔未能查證**——官方文件只給了 `*/10 * * * *` 這類範例，未載明是否允許 `*/1`。**需人工確認。**

來源：<https://render.com/docs/cronjobs>

### 1.4 時區這件事對台股其實是好消息

**台灣沒有日光節約時間，全年固定 UTC+8。** 所以「只支援 UTC」對本專案**不構成正確性風險**，只是換算負擔：

| 台北時間 | UTC crontab |
|---|---|
| 09:00（worker 開機） | `0 1 * * 1-5` |
| 13:35（worker 關機） | `35 5 * * 1-5` |
| 14:30（盤後批次） | `30 6 * * 1-5` |

真正的風險不是 DST，而是**寫錯 8 小時**——而寫錯 8 小時的後果剛好就是「半夜通知」（§10.3）。

---

## 2. scale-to-zero 的機器能不能被排程喚醒（Q2）

| 平台 | 喚醒機制 | 排程能不能喚醒 |
|---|---|---|
| **Fly.io** | **Fly Proxy 收到 inbound request 時自動啟動 stopped/suspended Machine**；另有 Machines API `POST /v1/apps/{app}/machines/{id}/start` | **可以。** 兩條路都通：外部排程打一個 HTTPS 請求（走 proxy 自動喚醒），或直接呼叫 Machines API start。⚠️ 但**設了 `--schedule` 的 Machine 不能用 API 啟動**（§1.1），兩者互斥 |
| **Railway** | **"A service is woken when it receives traffic from the internet or from another service in the same project through the private network."** | **可以**（HTTP 請求即可）。⚠️ 官方警告 **"The first request sent to a slept service may return a 502 Bad Gateway response."**——排程觸發器必須把 502 當成「要重試」而不是「失敗」 |
| **Render** | Free instance「15 分鐘無 inbound traffic 即 spin down」，下次有請求時自動 spin up | **可以**，但只有 Free instance 會 spin down；付費 instance 不縮到零（也就沒有要喚醒的問題） |
| **VPS** | 無此概念，機器一直開著 | 不適用 |

### 2.1 Fly.io 官方對喚醒機制的說法

`auto_start_machines` 的定義是「Whether Fly Proxy should automatically start Machines based on requests and capacity」，且「Fly Proxy will automatically start stopped Machines when needed」。

來源：<https://fly.io/docs/launch/autostop-autostart/>、<https://fly.io/docs/machines/api/machines-resource/>

### 2.2 Railway 的「睡著」判準會反咬本專案

Railway 的 Serverless 不是看有沒有 inbound 請求，而是看 **outbound 封包**：

> **"Inactivity is based on the detection of any outbound packets, which could include network requests, database connections, or even NTP."**
> **"If no packets are sent from the service for over 10 minutes, the service is considered inactive."**
> 會阻止睡著的東西包含：**"Keeping active database connections open, such as a database connection pooler."**

**這對本專案是一把雙面刃：**

- 好的一面：`realtime-quotes.md` §3 已規定「`api` 在沒有任何 SSE 連線時不持有 `LISTEN`」，所以沒人看盤時 `api` 確實可能睡著。
- 壞的一面：`api` 是 FastAPI + SQLAlchemy，**只要連線池留著一條閒置 DB 連線、或有任何背景 keepalive，Railway 就永遠不會判定它閒置**。scale-to-zero 會在完全沒有錯誤訊息的情況下失效，而帳單會誠實反映這件事。

來源：<https://docs.railway.com/deployments/serverless>

---

## 3. 冷啟動的官方數字（Q3）

> **本節刻意只收官方文件的說法。二手 benchmark 一律不引用。**

| 平台 | 官方有沒有給數字 | 官方原文 |
|---|---|---|
| **Fly.io** | **沒有。未能查證。** | 只說「Starting a Machine from a `suspended` state is **faster than** starting a Machine from a `stopped` state, but there are some caveats」——**只有比較級，沒有絕對值** |
| **Railway** | **沒有。未能查證。** | 只警告「The first request sent to a slept service **may return a 502 Bad Gateway response**」 |
| **Render（Free instance）** | **有** | 「Render spins down a Free web service that goes 15 minutes without receiving any inbound traffic」／spin up **"This process takes about one minute."** |
| **Neon（資料庫）** | **有** | 「Activation generally takes **a few hundred milliseconds**」；但「if your project has been idle for over 7 days, activation may take longer」且「initial queries may take longer until the memory buffers are warmed」 |
| **Supabase（暫停專案還原）** | **沒有。未能查證。** | 文件只描述還原步驟，未給耗時 |

> **結論（要寫進 #15）**：**除了 Render Free 的「about one minute」之外，沒有任何平台公布一個 Python 容器從 zero 到能處理請求的官方數字。** 任何「Fly 大約 X 秒」的說法都是二手 benchmark，本文不採信、也不轉述。要知道就得自己實測 P50/P95。

來源：<https://fly.io/docs/launch/autostop-autostart/>、<https://docs.railway.com/deployments/serverless>、<https://render.com/docs/free>、<https://neon.com/docs/introduction/compute-lifecycle>

---

## 4. 託管 PostgreSQL：休眠、連線數、與 `LISTEN/NOTIFY`（Q4）★

> **這一節是本文的核心，也是唯一可能讓現有架構走不通的地方。**

### 4.1 一句話總表

| 託管 DB | 閒置休眠 | 休眠會不會殺掉既有 `LISTEN` 連線 | pooler 模式 | pooler 支不支援 `LISTEN/NOTIFY` | 有沒有 direct（非 pooled）連線 |
|---|---|---|---|---|---|
| **Neon Free** | **會**，5 分鐘，**免費層不可關閉** | **會（官方明文）** | PgBouncer **transaction** | **❌ 官方明列不支援** | ✅ 有（去掉 `-pooler` 後綴） |
| **Neon 付費** | 可關閉（但即 24/7 計費） | 同上 | 同上 | 同上 | ✅ |
| **Supabase Free** | **會**，低活躍 **7 天**後整個專案被暫停 | 專案暫停＝連線全斷 | Supavisor：6543 **transaction**、5432 **session** | **未能查證**（官方文件只講 prepared statements） | ✅ 但**direct 走 IPv6**，IPv4 需付費 add-on（Pro 以上） |
| **Supabase Pro（US$25/月起）** | **不會**（「Paid projects cannot be paused」） | 不適用 | 同上 | 同上（未能查證） | ✅（IPv4 add-on 約 US$4/月） |
| **Render Postgres Free** | 不休眠，但 **30 天到期** | 不適用 | **不提供 pooling** | 不適用 | ✅（只有 direct） |
| **Render Postgres 付費** | 不休眠 | 不適用 | PgBouncer **transaction** | **❌ 官方明列不支援** | ✅ |
| **Fly Managed Postgres** | **官方文件未提及自動休眠 → 未能查證，但無 scale-to-zero 產品說明，推定不休眠** | 不適用 | PgBouncer，**預設 session** | **✅ 官方明文支援** | ✅ |
| **VPS 自架 Postgres** | 不休眠 | 不適用 | 自己決定（可不裝 pooler） | ✅（不經 pooler） | ✅ |

### 4.2 Neon：兩個獨立的地雷，兩個都踩得到

**地雷一：pooled endpoint 完全不支援 `LISTEN/NOTIFY`。**

Neon 官方 Connection pooling 文件明列 pooled connection 不支援的 session 層功能：

> `SET` / `RESET`（session variables）、**`LISTEN` / `NOTIFY`**、`WITH HOLD CURSOR`、`PREPARE` / `DEALLOCATE`、temporary tables、`LOAD`、session-level advisory locks

原因是 `pool_mode=transaction`：「connections are returned to the pool after each transaction completes」。

**這是可以繞過的**——用 direct connection string（主機名去掉 `-pooler` 後綴）即可。但**繞過這件事必須被明文寫進規格**，否則日後有人依「serverless 就該用 pooled」的直覺改回去，報價扇出會在沒有錯誤訊息的情況下靜止。

**地雷二：scale-to-zero 會把 `LISTEN` 的訂閱狀態整個丟掉，而免費層關不掉。**

Neon 官方 compatibility 文件（這段幾乎是為本專案寫的）：

> "When connections are closed, anything that exists within a session context is forgotten and must be recreated before being used again. For example, parameters set for a specific session, in-memory statistics, temporary tables, prepared statements, advisory locks, and **notifications and listeners defined using NOTIFY/LISTEN commands only exist for the duration of the current session and are lost when the session ends.**"
> "**The Neon cloud service automatically closes idle connections after a period of inactivity**, as described in Compute lifecycle."
> 解法是「disable Neon's Scale to Zero feature, **which is possible on any of Neon's paid plans**. However, disabling scale to zero also means that your compute will run 24/7.」

compute lifecycle 文件補上時間：

> "**If there are no active queries for 5 minutes**, which is the scale to zero setting in Neon, your compute is automatically placed into an idle state."

而 Neon Free plan 的設定是**固定的**：「For Neon Free plan users, this setting is fixed. Paid plan users can disable the scale-to-zero setting」。

> ⚠️ **這正是 `realtime-quotes.md` §3 早就預言的情境**，原文：「盤中、`api` 醒著、使用者正盯著螢幕看報價跳——此時資料庫看起來是完全靜止的……會自動休眠的託管資料庫只看到『十分鐘沒有 query』，於是休眠，順手掐掉 listener。」
> **本文查證的結果是：那條預言在 Neon 上是字面成立的，而且門檻比預期短（5 分鐘，不是 10 分鐘）。**

`realtime-quotes.md` §3 已規定的應用層 keepalive（定期在同一條連線上發輕量查詢）**確實能擋住這件事**——因為「no active queries」的判準是 query，不是連線。但代價是：**keepalive 讓 compute 在盤中永遠不休眠**，於是免費層的 100 CU-hours/project 就開始被消耗（試算見 §7.4）。

Neon 的連線數不是問題：`max_connections = max(100, min(4000, floor(compute_size × 419.66)))`，最小也有 100 條。

來源：<https://neon.com/docs/connect/connection-pooling>、<https://neon.com/docs/reference/compatibility>、<https://neon.com/docs/introduction/compute-lifecycle>、<https://neon.com/docs/introduction/scale-to-zero>

### 4.3 Supabase：暫停門檻寬鬆，但 IPv4 是隱形的付費牆

**暫停規則**（官方 Project Pausing 文件）：
- Free 專案在**「low activity over a 7-day period」**後被暫停，暫停前約一週會寄警告信。
- **「a few user requests to the database each day over the previous week is enough to keep the project from being paused」**——本專案每天都有盤後排程寫入，**天然不會被暫停**。
- Free plan 每個組織上限 **2 個 active project**。
- 「**Paid projects cannot be paused** and are not subject to pausing for inactivity」。

**連線模式與 `LISTEN/NOTIFY`**：
- direct connection：port **5432**，「Direct connections are on **IPv6**, or on IPv4 if the project has the **IPv4 add-on**」。
- Supavisor session mode：port 5432；transaction mode：port **6543**。
- 官方對 transaction mode 只寫了「**Transaction mode does not support prepared statements**」，**全文未提 `LISTEN/NOTIFY`** → **未能查證，需人工確認**。
  （按 PgBouncer/Supavisor 的一般原理，transaction mode 不可能支援 `LISTEN/NOTIFY`，但**本文不把推論當事實**。）
- ⚠️ Supavisor **已於 2025-02-28 在 port 6543 上停用 session mode**，session mode 客戶端要改用 5432。

**IPv4 add-on**：US$0.0055/小時 ≈ **US$4/月**，且**僅 Pro 以上方案可用**。

> ⚠️ **這是 Supabase Free 對本專案的真正障礙**：免費層要走 direct connection（唯一確定支援 `LISTEN/NOTIFY` 的路）就必須有 **IPv6 出口**。`quote-worker` 與 `api` 所在平台是否提供 IPv6 出站——**本文未逐平台查證，需人工確認**。走 Supavisor 6543（transaction）則落回上一條的未知。

來源：<https://supabase.com/docs/guides/platform/free-project-pausing>、<https://supabase.com/docs/guides/database/connecting-to-postgres>、<https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI>、<https://supabase.com/docs/guides/platform/ipv4-address>

### 4.4 Render Postgres：免費層直接出局，付費層要繞開 pooler

官方 connection pooling 文件：

> **"Render-managed PgBouncer uses transaction-level pooling (`pool_mode = transaction`)."**
> 需要以下 session 層功能的 client 必須繞過連線池：「Custom session variables (`SET SESSION …`)」、「Temporary tables」、**「`LISTEN`/`NOTIFY`」**、「Session-level advisory locks」
> **"Connection pooling is not available for free databases."**

免費層另外兩條：
- **「Free Render Postgres databases expire 30 days after creation.」**（到期後另有 14 天可升級，逾期資料刪除）
- 每個帳號同時只能有 1 個免費資料庫；免費層不支援 managed connection pooling。

> **結論：Render Postgres Free 在本專案不可用**（30 天到期＝每月搬一次家）。付費層可用，但**必須用非 pooled 的連線字串**。

來源：<https://render.com/docs/postgresql-connection-pooling>、<https://render.com/docs/free>、<https://render.com/changelog/free-postgresql-instances-now-expire-after-30-days-previously-90>

### 4.5 Fly Managed Postgres：唯一官方明文說「`LISTEN/NOTIFY` 可以用」的託管方案

官方 client configuration 文件（**本節最有價值的引用**）：

> Pooled URL「routes through PgBouncer. Use this for your application.」
> Direct URL「**bypasses PgBouncer. Use this for migrations, advisory locks, or `LISTEN/NOTIFY`.**」
> **Session mode 是預設**：「A PgBouncer connection is held for the entire client session. **Full PostgreSQL feature compatibility — prepared statements, advisory locks, `LISTEN/NOTIFY`, and multi-statement transactions all work normally.**」
> Transaction mode（非預設）：「**`LISTEN/NOTIFY` doesn't work**」

也就是說 Fly MPG **走 pooler（預設 session mode）或走 direct，兩條路都支援 `LISTEN/NOTIFY`**——這是本次查證的所有託管 Postgres 中，唯一一家在官方文件裡把 `LISTEN/NOTIFY` 明確列為「works normally」的。

**但價格是硬傷**：Basic **US$38/月 ≈ NT$1,228**（Starter US$72、Launch US$282、Scale US$962、Performance US$1,922），儲存另計 US$0.28/provisioned GB/30 天，上限 1 TB。東京有節點。

**是否自動休眠 → 未能查證**（官方文件未提及 scale-to-zero；以其定價形狀推定為常駐，但本文不把推定當事實）。

來源：<https://fly.io/docs/mpg/client-configuration/>、<https://fly.io/docs/mpg/>

### 4.6 VPS 自架

無休眠、無 pooler（除非自己裝）、`LISTEN/NOTIFY` 原生可用、連線數自己設。**唯一沒有任何 pooler 陷阱的選項**，代價是備份與 OS 維運自理，且機器費是 24/7 固定支出（§7.5）。

---

## 5. 讓 worker 只在每天固定時段開機（Q5）

需求：**每個交易日 09:00–13:35 Asia/Taipei**，約 4h35m/天 × 約 20 個交易日 ≈ **91.7 小時/月**（相當於 730 小時的 **12.6%**）。

| 平台 | 做法 | 誰來觸發 | 停機期間的費用 |
|---|---|---|---|
| **Fly.io** | `fly machine start` / `stop`，或 Machines API `POST .../machines/{id}/start` 與 `/stop` | **必須外部觸發**（GitHub Actions 或另一台常駐 Cron Manager）。**原生 `--schedule` 不可用**：只有 fuzzy hourly/daily，且設了 schedule 的機器無法用 API 啟動（§1.1） | 只付 rootfs：「Each 1GB of rootfs for a Machine stopped for 30 days is **$0.15**」，**CPU/RAM 不計費** |
| **Railway** | 沒有「按時段開關機」的原生 API 文件；Serverless 是「10 分鐘無 outbound 就睡」。worker 持續連著 Fugle WS＝一直有 outbound → **永遠不會睡** | — | 依實際用量計費（worker 一直在跑就是一直計費） |
| **Render** | 付費 instance 不縮到零，**官方文件未提供按排程 suspend/resume 服務的做法** → **未能查證**（Render 有 REST API，但本次未查證是否有 suspend/resume service 端點） | — | 未能查證 |
| **VPS** | 機器一直開著，只用 `systemd` timer 起停**行程** | 本機 cron（可設 `Asia/Taipei`） | **無差別**——Vultr 與 Linode 官方均明示**關機仍照常計費** |

### 5.1 VPS 關機省不了錢（官方明文）

- Vultr：「instances in a stopped state continue to reserve dedicated system resources (RAM, SSD storage, IP addresses, and vCPU) and therefore **incur charges until the virtual machine is destroyed**」
- Akamai/Linode：「Charges will accrue for any service present on an account, **even if it is powered off** or otherwise not actively being used」

> **這正是 issue #1「能中途停掉比 24/7 最便宜更重要」這條偏好把 VPS 推下神壇的地方**：VPS 沒有「停掉」這個檔位，只有「刪掉」。

來源：<https://docs.vultr.com/support/platform/billing/are-stopped-instances-still-billed-on-vultr>、<https://techdocs.akamai.com/cloud-computing/docs/understanding-how-billing-works>

### 5.2 Fly.io 是唯一「停機真的不計費」的候選

「For stopped Machines we charge only for the root file system (rootfs) needed for each Machine. Each 1GB of rootfs for a Machine stopped for 30 days is **$0.15**.」

但要注意：**觸發器得住在別的地方**。可行的外部觸發器有三種，各有代價：

| 觸發器 | 成本 | 代價 |
|---|---|---|
| GitHub Actions `schedule` | public repo 免費 | ⚠️ 官方明文：「The `schedule` event **can be delayed** during periods of high loads……**some queued jobs may be dropped**」。開機晚 10 分鐘 = 少 10 分鐘行情；**被丟棄 = 當天完全沒開機，而且不會有人通知你** |
| Fly Cron Manager / Supercronic Machine | 一台常駐 shared-cpu-1x/256MB ≈ US$2.02/月（ams 費率） | 常駐＝與「能停掉」的偏好衝突，且它自己壞掉沒人會發現 |
| Render Cron Job 打 Fly Machines API | US$1/月/job | 跨平台，多一個供應商；但 Render 有內建失敗告警（§8） |

---

## 6. 出站 HTTP 限制（Q6）

需求：`worker`（或任何送出者）要對外 **POST Discord webhook**（HTTPS / port 443）。

| 平台 | 限制 | 結論 |
|---|---|---|
| **Fly.io** | 官方文件未載明出站 port 封鎖；出站流量計入頻寬費 | **未見限制**（未能查證是否有 SMTP 類封鎖，但與本專案無關） |
| **Railway** | 官方未載明 port 封鎖；**egress US$0.05/GB** | **未見限制** |
| **Render** | **Free web services 禁止出站到 SMTP ports 25 / 465 / 587**（2025-09 生效）；升級到任何付費 instance 即解除。**443 不受影響** | **Discord webhook 不受影響** |
| **VPS** | 無限制 | 無限制 |

> Discord webhook 走 HTTPS 443，**四個平台全部可用**。唯一要記住的是：如果日後把備援管道改成自架 SMTP 寄信，Render Free 會擋。

來源：<https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports>、<https://railway.com/pricing>

---

## 7. 價格（Q7，2026-08-05 官方定價頁；1 USD = 32.315 TWD）

### 7.1 Fly.io

| 項目 | 官方價（**ams 阿姆斯特丹**） | 換算 NT$ |
|---|---|---|
| shared-cpu-1x / 256MB | US$2.02/月 | NT$65 |
| shared-cpu-1x / 512MB | US$3.32/月 | NT$107 |
| shared-cpu-1x / 1GB | US$5.92/月 | NT$191 |
| shared-cpu-1x / 2GB | US$11.11/月 | NT$359 |
| 停機 Machine rootfs | US$0.15/GB/30 天 | NT$4.8 |
| Volume | US$0.15/GB/月 | NT$4.8 |
| Managed Postgres Basic | US$38/月 | **NT$1,228** |
| MPG 儲存 | US$0.28/provisioned GB/30 天 | NT$9 |
| 方案費 | **無**。「Fly.io no longer offers plans to new customers」，新組織一律 pay-as-you-go、**無月費下限** | — |
| 支援 | Community 免費／Standard US$29/月／Premium US$199/月 | — |

> ⚠️ **上表是 ams 的數字。** 官方定價頁的區域切換是 JS 動態載入（頁面裡只有一個 `regionMarkups` 變數），**本次未能取得 nrt 東京的官方係數 → 未能查證**。
> 參考：[#5](./persistent-websocket-hosting.md)（2026-08-01）曾取得 nrt 的 512MB = US$4.18、1GB = US$7.45，對照今日 ams 數字隱含係數約 **1.26×**。**這是推算，不是官方數字，使用前請自行在 dashboard 確認。**

**「只在盤中開機」的實算（以 ams 費率、512MB）：**
```
時薪   = $3.32 / 730h            = $0.004548/h
月用量 = 4h35m × 20 交易日        = 91.7 h
運算費 = 91.7 × $0.004548        = $0.417/月  ≈ NT$13
停機費 = 1GB rootfs               = $0.15/月  ≈ NT$5
小計                              ≈ $0.57/月  ≈ NT$18
（若 nrt 係數 1.26） ≈ $0.68/月  ≈ NT$22
```

**「常駐」對照**：512MB 24/7 = US$3.32 ≈ NT$107（nrt 推算 ≈ US$4.18 ≈ NT$135）。
→ **只在盤中開機省下約 83%。**

來源：<https://fly.io/docs/about/pricing/>、<https://fly.io/docs/mpg/>

### 7.2 Railway

| 項目 | 官方價 | 換算 NT$ |
|---|---|---|
| Free Trial | US$5 額度／30 天（**試用，非免費層**） | — |
| **Hobby** | **US$5/月，含 US$5 額度** | NT$162 |
| Pro | US$20/月/workspace，含 US$20 額度 | NT$646 |
| CPU | US$0.00000772/vCPU-秒＝**US$0.0277/vCPU-小時** | — |
| RAM | US$0.00000386/GB-秒＝**US$0.0139/GB-小時** | — |
| Egress | US$0.05/GB | — |

**盤後批次（假設每次 60 秒、0.5 vCPU + 0.5 GB、每月 20 次）：**
```
CPU : 0.5 × (60/3600) × $0.0277 × 20 = $0.0046
RAM : 0.5 × (60/3600) × $0.0139 × 20 = $0.0023
小計                                  ≈ $0.007/月（幾乎為零，落在 Hobby 的 $5 額度內）
```
→ **Railway 的排程本身幾乎免費，成本是 US$5/月的方案費（NT$162）。**

> **Railway 沒有真正的免費層**——Free Trial 是一次性 US$5 額度／30 天。

來源：<https://railway.com/pricing>、<https://docs.railway.com/reference/cron-jobs>

### 7.3 Render

| 項目 | 官方價 | 換算 NT$ | 備註 |
|---|---|---|---|
| Hobby workspace | US$0 | — | **真免費層** |
| Free web service | US$0，每 workspace 每月 750 free instance hours | — | 15 分鐘無流量 spin down，spin up 約 1 分鐘 |
| Free Postgres | US$0，1 GB | — | **30 天到期**、無 pooling、每帳號限 1 個 |
| **Cron Job** | **每 job 每月最低 US$1**，其餘按秒 | **NT$32** | 官方文件明文 |
| Starter instance | US$7/月（0.5 CPU / 512 MB） | NT$226 | ⚠️ 定價頁為 JS 動態載入，本次**未能自定價頁直接讀取**；此數字取自 Render 官方文章與 [#5](./persistent-websocket-hosting.md) 於 2026-08-01 的查證，**需人工複驗** |
| Standard instance | US$25/月（1 CPU / 2 GB） | NT$808 | 同上，需複驗 |
| Postgres Basic-256mb / Basic-1gb | US$6 / US$19 | NT$194 / NT$614 | 同上，**本次未能複驗，需人工確認** |

來源：<https://render.com/docs/cronjobs>、<https://render.com/docs/free>、<https://render.com/pricing>（JS 動態）

### 7.4 Neon / Supabase

| 項目 | 官方價 | 換算 NT$ |
|---|---|---|
| **Neon Free** | US$0；**100 CU-hours/project**、**0.5 GB/project**；scale-to-zero 5 分鐘且**不可關閉** | — |
| Neon Launch | US$0.106/CU-hour（含 500 GB egress/project） | — |
| Neon Scale | US$0.222/CU-hour | — |
| **Supabase Free** | US$0；500 MB DB、**2 個 active project**、低活躍 7 天暫停 | — |
| Supabase Pro | **US$25/月起**（含 US$10 compute credit＝1 台 Micro） | NT$808 |
| Supabase IPv4 add-on | US$0.0055/小時 ≈ **US$4/月**（**Pro 以上才有**） | NT$129 |

**Neon Free 的 CU-hours 夠不夠用（試算）：**
```
假設：盤中 api 持有 LISTEN 並跑 keepalive → compute 在盤中不會休眠
盤中時數 = 4h35m × 20 = 91.7 h/月
若 compute = 0.25 CU  → 91.7 × 0.25 = 22.9 CU-hours
若 compute = 1 CU     → 91.7 × 1    = 91.7 CU-hours（幾乎用光 100）
```
> ⚠️ **Neon Free plan 的實際 compute 大小上下限本次未查證** → **未能查證，需人工確認**。若免費層的 compute 不是 0.25 CU 而是 1 CU，keepalive 策略會在月底把額度用光，而額度用光的行為（停機？降速？）本次亦未查證。

來源：<https://neon.com/pricing>、<https://supabase.com/pricing>、<https://supabase.com/docs/guides/platform/manage-your-usage/ipv4>

### 7.5 VPS（對照組，2026-08-05 官方 API 實查）

Vultr（**東京 nrt 供應**，`https://api.vultr.com/v2/plans`）：

| 方案 | 規格 | 月費 | NT$ |
|---|---|---|---|
| `vc2-1c-1gb` | 1 vCPU / 1 GB / 25 GB | **US$5** | NT$162 |
| `vhf-1c-1gb` | High Frequency 1 vCPU / 1 GB / 32 GB | US$6 | NT$194 |
| `vc2-1c-2gb` | 1 vCPU / 2 GB / 55 GB | US$10 | NT$323 |
| `vc2-2c-2gb` | 2 vCPU / 2 GB / 65 GB | US$15 | NT$485 |

Linode / Akamai（`https://api.linode.com/v4/linode/types`）：

| 方案 | 規格 | 月費 | NT$ |
|---|---|---|---|
| `g6-nanode-1` | 1 vCPU / 1 GB / 25 GB | **US$5.00** | NT$162 |
| `g6-standard-1` | 1 vCPU / 2 GB / 50 GB | US$12.00 | NT$388 |

> **最便宜的 VPS（US$5 ≈ NT$162）已經超出 NT$50–100/月的預算上限，而且關機也不會變便宜（§5.1）。**

---

## 8. 監控：怎麼知道排程沒跑（Q8）

| 平台 | 內建「排程失敗」告警 | 官方說法 |
|---|---|---|
| **Render** | **✅ 有，這是四家中唯一的** | Cron job 以非 0 狀態碼結束即記為 failed，可經 **Email / Slack** 通知；另有 **Webhooks**（事件 payload 帶 `status`：succeeded / failed / canceled）。Webhook 投遞失敗會重試最多 8 次，第 3 次失敗後寄 email，最後一次約在首次後 33 小時 |
| **Railway** | ⚠️ 部分 | 有 **Webhooks**（deploy succeeded/failed、crashed）與 crash email；**但「cron job 這一次 run 失敗」層級的告警，官方文件未明確涵蓋 → 未能查證** |
| **Fly.io** | **❌ 沒有（官方明文）** | 「**Fly.io doesn't include built-in alerting on metrics, so you'll need to set up alerting yourself against the Prometheus endpoint.**」建議自行接 Grafana alerting 或自架 Prometheus + Alertmanager |
| **VPS** | ❌ 沒有 | 只有 `systemd` 的 `OnFailure=` 可以自己接；需自建 dead-man's switch |

### 8.1 所有平台共通的盲點：**「沒跑」與「跑了但失敗」是兩件事**

Render / Railway 的告警都是**「這次 run 失敗了」**。但本專案真正怕的是**「排程根本沒被觸發」**——例如：

- GitHub Actions 的 job 在高負載時**被丟棄**（官方明文，§5.2）
- Railway 的 cron 因為上一次還沒結束而**被跳過**（官方明文：「Railway will skip the new cron job」，§1.2）
- Fly Scheduled Machine 在啟動時資源不足而報錯（官方明文警告）

**這三種情況都不會產生一次「失敗的 run」，因此不會觸發任何平台的失敗告警。** 要偵測它們只能靠**反向心跳**（排程跑完主動打一個外部 dead-man's switch，該服務在時限內沒收到心跳就叫你）——而**這需要一個第四方服務，本文未查證其選項與價格**。

來源：<https://render.com/docs/notifications>、<https://render.com/docs/webhooks>、<https://docs.railway.com/observability/webhooks>、<https://fly.io/docs/monitoring/metrics/>、<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>

---

## 9. 未能查證清單（誠實標註）

1. **Fly.io 東京（nrt）的官方區域係數與實價** — 定價頁區域切換為 JS 動態載入，靜態內容只有 ams。**需登入 dashboard 或用 `fly platform vm-sizes` 確認。**
2. **Fly.io 冷啟動的絕對秒數** — 官方只有「suspended 比 stopped 快」的比較級。
3. **Railway 冷啟動的絕對秒數** — 官方只有「first request may return 502」。
4. **Fly Managed Postgres 是否有自動休眠 / scale-to-zero** — 官方文件完全未提及。
5. **Supabase Supavisor transaction mode 是否支援 `LISTEN/NOTIFY`** — 官方文件只講 prepared statements，**未提 `LISTEN/NOTIFY`**。（原理上應為不支援，但本文不把推論當事實。）
6. **Supabase 專案暫停後還原所需時間** — 官方未給數字。
7. **Render Cron Job 的最小排程間隔** — 官方文件未載明是否允許 `*/1`。
8. **Render 的 instance / Postgres 實際月費** — 定價頁為 JS 動態載入，本次未能自第一手定價頁讀取；表中數字取自官方文章與 #5（2026-08-01），**需人工複驗**。
9. **Render 是否有「按排程 suspend / resume 一個服務」的 API** — 未查證。
10. **Neon Free plan 的 compute 大小上下限、以及 100 CU-hours 用罄後的行為** — 未查證。
11. **各運算平台是否提供 IPv6 出站**（決定 Supabase Free 的 direct connection 能否使用） — 未逐平台查證。
12. **第四方 dead-man's switch 服務的選項與價格** — 未查證。
13. **Fly Cron Manager / Supercronic 容器內的時區設定方式** — 官方文件未載明。
14. **各平台節點對台灣的實測 RTT** — 本文與 #5 皆未實測。

---

## 10. 對 issue #15 的影響

### 10.1 outbox 排空排程有沒有地方落腳？——**有，而且不只一處**

| 落腳處 | 最小間隔 | 月費 | 內建失敗告警 |
|---|---|---|---|
| **Render Cron Job**（打 `api` 的排空端點） | 未能查證下限（範例最細 `*/10`） | **US$1 ≈ NT$32** | **有**（email / Slack / webhook） |
| **Railway Cron**（同 project 內叫醒 `api`） | **5 分鐘** | 含在 Hobby US$5 ≈ NT$162 內 | 部分（未能查證 run 層級） |
| **GitHub Actions `schedule`**（打 `api` 的 HTTPS 端點） | **5 分鐘** | **US$0**（public repo） | **無**，且 job **可能被丟棄** |
| **VPS `cron`** | 1 分鐘 | 含在 US$5 ≈ NT$162 內 | 無 |
| **Fly 原生 Scheduled Machine** | **1 小時，且無時區、不可手動啟動** | 幾乎為零 | **無** |
| **Fly Cron Manager / Supercronic** | 1 分鐘 | 一台常駐 256MB ≈ US$2.02 ≈ NT$65 | **無** |

**與 30 分鐘送達要求（約束 C）的關係**：
```
最壞延遲 ≈ 排空間隔 + api 冷啟動 + Discord API 往返
         ≈ 5–10 分鐘 + 未知 + 秒級
```
**只要排空間隔設在 5–10 分鐘，就有非常大的餘裕**（30 分鐘要求下還剩 20 分鐘以上緩衝），**即使冷啟動是分鐘級也撐得住**。
→ **outbox 方案（#15 待決 8 選項 D）在成本與延遲上都是可行的**，它不會被 #17 的平台選擇卡死。

⚠️ 但有兩個必須寫進規格的陷阱：

1. **Railway 的「跳過」語意**（§1.2）：上一次排空卡住（例如 Discord 回應慢），這一次會被**靜默跳過**。排空任務必須有**自己的逾時**，不能靠平台救。
2. **Fly 原生排程不能用來排空 outbox**：1 小時的粒度會讓最壞延遲逼近 30 分鐘上限，且它沒有時區、也不能手動觸發補跑。走 Fly 就必須額外養一台 cron 機器或用外部觸發器。

### 10.2 `api` 冷啟動送一則通知的延遲下界是什麼量級？——**沒有官方數字**

> **除了 Render Free instance 的「about one minute」之外，Fly.io 與 Railway 都沒有公布任何 Python 容器從 zero 到能處理請求的官方數字。**

- **Fly.io**：只有「suspended 比 stopped 快」的比較級，無絕對值 → **未能查證**。
- **Railway**：只有「first request may return 502」的警告 → **未能查證**。
- **Render Free**：**「This process takes about one minute.」**（官方明文）
- **資料庫端**：Neon「a few hundred milliseconds」（官方明文），閒置逾 7 天會更久。

**寫給 #15 的話**：任何「大約 X 秒」的說法，本文查不到官方依據，因此**不提供這個數字**。若延遲下界對決策重要，就必須自己實測 P50/P95（`realtime-quotes.md` §4 已有 `curl -N` 的實測手法可沿用）。
**好消息是**：在 30 分鐘的送達預算下，冷啟動即使是分鐘級也不是瓶頸——**瓶頸是排空間隔，那是可控的旋鈕。**

### 10.3 會不會出現半夜通知？——**結構上不會，但有三個真實的出錯途徑**

**結構上不會**的理由：
- 台灣**沒有日光節約時間**，全年固定 UTC+8。所有平台的 UTC-only cron 都能**精確**對應台北時間，不存在「夏令時間漂移」這種經典半夜通知來源。
- worker 只在 09:00–13:35 開機（`realtime-quotes.md` §8），盤中即時警示天然被限制在白天。
- 盤後批次若排在 14:30 台北（`30 6 * * 1-5` UTC），仍是白天。

**三個會真的產生半夜通知的途徑：**

| # | 途徑 | 為什麼危險 |
|---|---|---|
| 1 | **把台北時間直接寫進 UTC cron** | 寫 `0 9 * * *` 以為是早上 9 點，實際是**台北 17:00**；寫 `30 14 * * *` 以為是下午，實際是**台北 22:30**。**差 8 小時剛好落在傍晚到深夜**。這是本專案最可能發生的半夜通知來源，而且**不會有任何錯誤訊息**（排程有跑、通知有送，只是時間錯了） |
| 2 | **GitHub Actions 的高負載延遲** | 官方明文：「can be delayed during periods of high loads……**some queued jobs may be dropped**」。延遲本身不至於推到半夜，但**被丟棄會讓通知累積到下一次排空**，若下一次排空恰在隔日，就變成隔天早上一次送一堆 |
| 3 | **outbox 積壓後的一次性排空** | 若排空器本身掛掉數小時後恢復，累積的通知會**一次全部送出**。`15-alerts.md` 待決 6 選項 C 已預見這個形狀（「累積的通知在早上送達時可能已經過期」）。**這需要 outbox 有過期策略，不是排程本身能解的** |

> **給 grilling 的具體建議（非結論，是待答題）**：既然三家平台的原生 cron 都是 UTC-only，「排程時間一律以 UTC 表示並在同一行註記對應台北時間」是否要當成 repo 層級的硬性規則？途徑 1 是本專案唯一「靜默、可預期、且成本為零就能防」的半夜通知來源。

---

## 11. 對 issue #17 的影響

> **本節只擺事實與成本，不下推薦。**

### 11.1 平台能力對照表（2026-08-05 查證）

| | **Fly.io** | **Railway** | **Render** | **VPS（Vultr / Linode 東京）** |
|---|---|---|---|---|
| **最近節點** | 東京 nrt | **僅新加坡** | **僅新加坡** | 東京 / 大阪 |
| **原生排程** | 只有 fuzzy hourly/daily/weekly/monthly | **cron，5 分鐘下限** | **cron 服務型別** | cron / systemd timer |
| **排程時區** | **無**（未提供） | **UTC only** | **UTC only** | **可設 Asia/Taipei** |
| **排程最小間隔** | 1 小時 | 5 分鐘 | 未能查證 | 1 分鐘 |
| **排程計費** | 依 Machine 秒數 | 依用量（幾近零） | **每 job 月最低 US$1** | US$0 |
| **scale-to-zero** | ✅ Machine stop/suspend，**停機不計 CPU/RAM** | ✅ Serverless，**但看 outbound 封包，DB 連線會讓它睡不著** | 僅 **Free** instance（15 分鐘） | ❌ **關機照樣計費** |
| **排程能否喚醒** | ✅ HTTP 經 Fly Proxy，或 Machines API start | ✅ HTTP（首次可能 502） | ✅ HTTP（Free） | 不適用 |
| **冷啟動官方數字** | **未能查證** | **未能查證** | **約 1 分鐘**（Free） | 無冷啟動 |
| **worker 只開盤中** | ✅ 外部觸發 start/stop | ⚠️ 無按時段 API；WS 連線讓它不會睡 | **未能查證** | ❌ 省不了錢 |
| **託管 PG 休眠** | 未能查證（推定不休眠） | 資料庫服務不適用 Serverless 判準 | 不休眠（Free 30 天到期） | 不休眠 |
| **託管 PG 的 `LISTEN/NOTIFY`** | **✅ pooler 預設 session，官方明文支援**；另有 direct URL | 未能查證（Railway PG 為 template，未查 pooler） | ⚠️ pooler 為 transaction，**官方明列不支援**；需用非 pooled 連線 | ✅ 原生 |
| **出站 HTTPS 443** | ✅ | ✅（egress US$0.05/GB） | ✅（Free 只擋 SMTP 25/465/587） | ✅ |
| **排程失敗告警** | **❌ 官方明文無內建 alerting** | ⚠️ 有 webhook / crash email，run 層級未能查證 | **✅ email / Slack / webhook** | ❌ |
| **真免費層** | ❌（新組織無免費額度） | ❌（US$5/30 天為**試用**） | ✅ Hobby workspace US$0 | ❌ |

### 11.2 月費對照（1 USD = 32.315 TWD；預算參考線 **NT$50–100/月**）

| 組合 | 明細 | 月費 US$ | **月費 NT$** | 是否落在預算內 |
|---|---|---|---|---|
| **Fly：api 常駐 512MB + worker 只開盤中 + Neon Free** | $3.32（api, ams）+ $0.57（worker）+ $0（Neon Free） | ≈ **$3.89** | ≈ **NT$126** | ❌ 略超 |
| **Fly：api scale-to-zero + worker 只開盤中 + Neon Free** | api 幾近 $0 + rootfs $0.15；worker $0.57 | ≈ **$0.72** | ≈ **NT$23** | ✅ |
| 　↑ 同上但用 nrt 東京（推算 ×1.26） | — | ≈ **$0.87** | ≈ **NT$28** | ✅ |
| **Fly 全套 + Fly Managed Postgres Basic** | 上列 + $38 + 儲存 | ≈ **$38.9** | ≈ **NT$1,257** | ❌ **超 12 倍** |
| **Fly（運算）+ Render Cron Job（排程與告警）+ Neon Free** | $0.72 + $1 | ≈ **$1.72** | ≈ **NT$56** | ✅ 勉強 |
| **Railway Hobby 全包 + Neon Free** | $5 方案費（含 $5 額度） | ≈ **$5.00** | ≈ **NT$162** | ❌ |
| **Render：Free web + Cron Job + Neon Free** | $0 + $1 | ≈ **$1.00** | ≈ **NT$32** | ✅ ⚠️ 但 Free instance 每月僅 750 小時、無 SLA |
| **Render：Starter + Cron Job + Postgres Basic-256mb** | $7 + $1 + $6（**需複驗**） | ≈ **$14.0** | ≈ **NT$452** | ❌ |
| **VPS：Vultr `vc2-1c-1gb` 東京（全自架）** | $5 | ≈ **$5.00** | ≈ **NT$162** | ❌ 且**沒有「停掉」這個檔位** |

> **一個必須被看見的算術事實**：NT$50–100/月 ＝ **US$1.55–3.10/月**。
> 在這個預算裡，**任何託管 PostgreSQL 的付費方案都放不進去**（最便宜的 Render Basic-256mb US$6 就已超標）。這代表 #17 的資料庫選項實質上只有三個：**Neon Free**、**Supabase Free**、**自架**——而三者都各自有 §4 記載的 `LISTEN/NOTIFY` 陷阱。

### 11.3 三組彼此衝突的事實（留給 grilling）

1. **「停機真的不計費」目前只有 Fly.io 有**（VPS 官方明文關機照收；Railway 的判準是 outbound 封包，WS client 永遠不會睡；Render 只有 Free 會 spin down）。但 **Fly 同時是唯一沒有任何內建排程告警的平台**，且**原生排程精度只到「大約一天一次」**。省錢與可觀測性在這裡是反向的。
2. **唯一官方明文支援 `LISTEN/NOTIFY` 的託管 Postgres（Fly MPG）是最貴的一個**（US$38/月，超預算 12 倍）；而預算內的三個選項全部需要繞開 pooler 或承擔休眠。
3. **唯一內建「排程沒跑成功」告警的平台是 Render**（US$1/月/job），但 Render 的節點只到新加坡，且它的 scale-to-zero 只存在於 Free instance（每月 750 小時、無 SLA）。

---

## 12. 來源清單（皆為第一手官方頁面，2026-08-05 ~ 06 查證）

**Fly.io**
- 定價：<https://fly.io/docs/about/pricing/>
- `fly machine run`（`--schedule`）：<https://fly.io/docs/machines/flyctl/fly-machine-run/>
- 任務排程 blueprint（Cron Manager）：<https://fly.io/docs/blueprints/task-scheduling/>
- Supercronic：<https://fly.io/docs/blueprints/supercronic/>
- autostop / autostart：<https://fly.io/docs/launch/autostop-autostart/>
- Machines API：<https://fly.io/docs/machines/api/machines-resource/>
- Managed Postgres 總覽與定價：<https://fly.io/docs/mpg/>
- **Managed Postgres client configuration（`LISTEN/NOTIFY` 明文）**：<https://fly.io/docs/mpg/client-configuration/>
- Metrics（明文無內建 alerting）：<https://fly.io/docs/monitoring/metrics/>

**Railway**
- 定價：<https://railway.com/pricing>
- Cron jobs：<https://docs.railway.com/reference/cron-jobs>
- Serverless（app sleeping）：<https://docs.railway.com/deployments/serverless>
- 區域：<https://docs.railway.com/reference/regions>
- Webhooks：<https://docs.railway.com/observability/webhooks>

**Render**
- Cron Jobs：<https://render.com/docs/cronjobs>
- Free tier：<https://render.com/docs/free>
- **Postgres connection pooling（`LISTEN/NOTIFY` 不支援明文）**：<https://render.com/docs/postgresql-connection-pooling>
- Postgres 方案：<https://render.com/docs/postgresql-refresh>
- 免費 Postgres 30 天到期公告：<https://render.com/changelog/free-postgresql-instances-now-expire-after-30-days-previously-90>
- Free 服務封鎖 SMTP 公告：<https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports>
- 通知：<https://render.com/docs/notifications>、<https://render.com/docs/webhooks>
- 定價（JS 動態，未能直讀）：<https://render.com/pricing>

**Neon**
- 定價：<https://neon.com/pricing>
- **Compatibility（`NOTIFY/LISTEN` 隨 session 消失明文）**：<https://neon.com/docs/reference/compatibility>
- Compute lifecycle（5 分鐘閒置、啟動數百毫秒）：<https://neon.com/docs/introduction/compute-lifecycle>
- Scale to zero：<https://neon.com/docs/introduction/scale-to-zero>
- **Connection pooling（pooled 不支援 `LISTEN/NOTIFY` 明文）**：<https://neon.com/docs/connect/connection-pooling>

**Supabase**
- 定價：<https://supabase.com/pricing>
- Free project pausing：<https://supabase.com/docs/guides/platform/free-project-pausing>
- 連線方式與 port：<https://supabase.com/docs/guides/database/connecting-to-postgres>
- Supavisor FAQ：<https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI>
- IPv4 add-on：<https://supabase.com/docs/guides/platform/ipv4-address>、<https://supabase.com/docs/guides/platform/manage-your-usage/ipv4>

**VPS**
- Vultr 方案（官方 API）：`https://api.vultr.com/v2/plans`
- Vultr 停機仍計費：<https://docs.vultr.com/support/platform/billing/are-stopped-instances-still-billed-on-vultr>
- Linode 機型（官方 API）：`https://api.linode.com/v4/linode/types`
- Akamai/Linode 計費：<https://techdocs.akamai.com/cloud-computing/docs/understanding-how-billing-works>

**其他**
- GitHub Actions `schedule`（時區、5 分鐘下限、可能被丟棄）：<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>
- 中央銀行新臺幣對美元收盤匯率：<https://www.cbc.gov.tw/tw/lp-645-1.html>
