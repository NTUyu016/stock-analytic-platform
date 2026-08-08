# 決策簡報：issue #17「部署、環境與成本上限」

> 產出日期：2026-08-08
> 用途：**上桌前準備**。本文只盤點事實與選項，**不做任何決策**——決策由使用者在 grilling session 親自做。
> 引用規則：所有事實附出處（檔案＋章節／issue 留言／第一手 URL）。查不到者一律標「**未能查證，需人工確認**」。
> 匯率：**1 USD = 32.315 TWD**（[`scheduling-and-db-sleep.md`](../research/scheduling-and-db-sleep.md) 沿用之 2026-08-05 中央銀行牌告）。第三方定價與政策會變，引用前請確認時效。

---

## 0. 開場前必須放在桌上的七條既有約束

這七條不是本票要決定的，但九個待決事項幾乎每一個都會撞到它們。

| # | 約束 | 出處 |
|---|---|---|
| 1 | **成本偏好：越低越好，且「能中途停掉」比「24/7 最便宜」更重要。** 這條反轉了 #5 對 VPS 的推薦——VPS 按月計費，「停掉」等於「刪掉」 | issue #1 已定調前提；issue #17 第 1 則留言 |
| 2 | `quote-worker` 是**可選元件**，`api` 必須在其缺席時降級運作；`api` 走 **scale-to-zero**，`quote-worker` 只在 **09:00–13:35** 開機 | `tech-stack.md` §4；`realtime-quotes.md` §8、總覽 |
| 3 | `quote-worker` → `api` 走 **Postgres `LISTEN/NOTIFY`**，且 `api` **只在有 SSE 連線時才持有 `LISTEN`** | `realtime-quotes.md` §3 |
| 4 | `daily_close` 的產生責任**明確不屬於 `quote-worker`**，走獨立盤後排程，**但「排程跑在哪」是本票的題目** | `realtime-quotes.md` §8 |
| 5 | [#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 已定案：**不建 `portfolio_snapshot`，連快取形式都不建**；效能門檻寫成「切換期間時單次載入 **< 200 ms**」；本機 PostgreSQL 16.2 warm cache 下常用區間落在 9.3–97 ms | `performance.md` §1.5；`16-performance.md` 檔首更正欄 |
| 6 | 網站**公開在網際網路上**；Caddy 申請憑證時網域會被寫進 Certificate Transparency log，**上線數小時內必有掃描器來敲**；`api` scale-to-zero 代表**任何人送一個 HTTP request 都能喚醒機器，喚醒發生在應用程式跑起來之前，認證擋不住它** | `tech-stack.md` §8；`auth.md`「這張票真正在保護什麼」；issue #17 第 3 則留言 |
| 7 | **台灣全年固定 UTC+8，無日光節約時間**——這讓「只支援 UTC」的排程平台不構成正確性風險，只剩換算負擔；真正的風險是**手寫錯 8 小時** | `scheduling-and-db-sleep.md` §1.4、§10.3 |

---

## ⚠️ 貫穿待決 1 與待決 4 的一個測量缺口：#16 移交的兩項至今沒有任何實測數字

[#16](https://github.com/NTUyu016/stock-analytic-platform/issues/16) 定案時（2026-08-07）留下兩個效能問題，因為「正式部署位置」是本票的題目而無法在 #16 內回答，於是明文移交給本票（issue #17 第 5 則留言；`16-performance.md` 檔首更正欄同步記載）：

| # | 缺口 | #16 的既有數字（下界，不是答案） |
|---|---|---|
| **① `api` scale-to-zero 冷啟動後，第一次查詢有多慢** | #16 的效能門檻是「切換期間時單次載入 **< 200 ms**」；本機 PostgreSQL 16.2 上最常用區間落在 **9.3–97 ms**（`performance.md` §1.5）。但那個數字是**單連線、暖快取**（`16-performance.md` §1.4 R5），**沒有扣掉冷啟動**——使用者實際開頁遇到的是冷啟動＋冷快取的那一次，不是量到的那一次 |
| **② DB 與 `api` 不同機時，每次查詢要加一次網路 RTT** | #16 的數字是**本機 in-process PostgreSQL，無網路延遲**（`16-performance.md` §1.4 R1）。若照目前傾向的組合（Fly 運算 + Neon Free 東京/新加坡），每次查詢都要加一次跨服務 RTT |

**目前能找到的唯一數字，全部來自官方文件的模糊描述，不是實測**（`scheduling-and-db-sleep.md` §3）：

| 平台 | 官方說法 |
|---|---|
| Render Free instance 冷啟動 | 「This process takes about one minute.」——**三家運算平台（Fly／Railway／Render）中唯一有絕對數字的一家** |
| Fly.io 冷啟動 | 只有「suspended 比 stopped 快」的比較級，**沒有絕對值** |
| Railway 冷啟動 | 只有「first request may return 502」的警告，**沒有絕對值** |
| Neon compute 喚醒 | 「Activation generally takes a few hundred milliseconds」；若閒置逾 7 天會更久（DB，非運算平台，與上三列不同性質） |

> **這兩項本文明確標記為「未能查證，需人工確認」，不在本次查證的授權範圍內補測。** 實測需要真的把候選平台（Fly.io / Render / Neon 等）跑起來，涉及開帳號、綁金流卡、實際部署——這是有金流與帳號風險的外部動作，超出本次查證的授權範圍，留給使用者或未來的原型票執行。
>
> 若日後要補這個缺口，[`docs/briefing/bench/`](./bench/)（#16 用來量測快照 vs 重算的丟棄式腳本與原始輸出）是一個可參考的既有先例——**但要注意 bench_16 系列量的是本機 SQL 效能，不是跨網路的冷啟動延遲，兩者的量測方法完全不同**，不能照搬腳本本身，只能照搬「留下腳本與原始輸出、任何人都能重跑驗證」這個做法。這只是一個可以考慮的方向，不是本文的建議。

---

## 待決事項 1：平台定案

### 1.1 已知事實

**（a）#5（2026-08-01）的原始推薦已被使用者的成本偏好反轉**

#5 建議「自用階段選東京 VPS（Vultr/Linode，US$5 ≈ NT$162/月）」，前提是 `quote-worker` 需要 24/7 常駐。#13 定案後 worker 只在 09:00–13:35 開機，且 issue #1 的成本偏好明確是「能中途停掉」比「24/7 最便宜」更重要——這直接反轉了 #5 的結論方向（issue #17 第 1、5 則留言；`persistent-websocket-hosting.md` §4）。

**（b）VPS 官方明文：關機不等於省錢**

- Vultr：「instances in a stopped state continue to reserve dedicated system resources... and therefore **incur charges until the virtual machine is destroyed**」
- Akamai/Linode：「Charges will accrue for any service present on an account, **even if it is powered off**」

**VPS 沒有「停掉」這個檔位，只有「刪掉」**（`scheduling-and-db-sleep.md` §5.1）。

**（c）Fly.io 是本次查證唯一「停機真的不計費」的候選**，但也是唯一沒有內建排程失敗告警、且原生排程精度只到「大約一天一次」的（`scheduling-and-db-sleep.md` §11.3 第 1 點）：

> "Fly.io **doesn't include built-in alerting on metrics**, so you'll need to set up alerting yourself against the Prometheus endpoint."（Fly 官方 Metrics 文件）

**（d）Fly.io 原生排程表達不出「每交易日 09:00 Asia/Taipei」**

`--schedule` 只接受 fuzzy 的 `hourly|daily|weekly|monthly`、**沒有時區設定**；官方明文：「**Scheduled machines cannot be started via flyctl or Machines API commands**, they will only run according to the schedule」——設了 schedule 的機器不能再被 API 手動叫起來，兩種用法互斥（`scheduling-and-db-sleep.md` §1.1）。要精準開關 `quote-worker` 就需要外部觸發器（GitHub Actions／另一台常駐 Cron Manager／Render Cron），這是原本沒算到的成本與失效點。

**（e）四平台能力對照（2026-08-05 查證，`scheduling-and-db-sleep.md` §11.1）**

| | Fly.io | Railway | Render | VPS（Vultr/Linode 東京） |
|---|---|---|---|---|
| 最近節點 | 東京 nrt | 僅新加坡 | 僅新加坡 | 東京／大阪 |
| scale-to-zero | ✅ Machine stop/suspend，停機不計 CPU/RAM | ✅ 但判準是 outbound 封包，DB 連線可能讓它睡不著 | 僅 Free instance（15 分鐘） | ❌ 關機照樣計費 |
| 排程時區 | 無（未提供） | UTC only | UTC only | 可設 `Asia/Taipei` |
| 排程失敗告警 | ❌ 官方明文無內建 alerting | ⚠️ 有 webhook／crash email，run 層級未能查證 | ✅ email／Slack／webhook | ❌ |
| 託管 PG 的 `LISTEN/NOTIFY` | ✅ pooler 預設 session 模式，官方明文支援；另有 direct URL | 未能查證（Railway PG 為 template，未查 pooler） | ⚠️ pooler 為 transaction，官方明列不支援 | ✅ 原生 |
| 真免費層 | ❌（新組織無免費額度） | ❌（US$5/30 天為**試用**，非免費層） | ✅ Hobby workspace US$0 | ❌ |

**（f）落在 NT$50–100/月預算內的三個組合（issue #17 第 4 則留言；`scheduling-and-db-sleep.md` §11.2）**

| 組合 | 月費 NT$ |
|---|---|
| Fly：`api` scale-to-zero + `worker` 只開盤中 + Neon Free（東京 nrt 係數為推算） | ≈ 28 |
| Render：Free web + Cron Job + Neon Free | ≈ 32 ⚠️ **Free instance 每月僅 750 小時、無 SLA** |
| Fly（運算）+ Render Cron Job（排程與告警）+ Neon Free | ≈ 56 |

### 1.2 選項盤點

| 選項 | 內容 | 代價 | 「做錯日後會很痛」的地方 |
|---|---|---|---|
| **A. Fly.io 全套**（`api` scale-to-zero + `worker` 只開盤中 + 外接 Neon Free） | 最省（≈NT$28/月） | **零內建排程失敗告警**（見待決 8）；原生排程精度不足以表達「09:00 Asia/Taipei」，需要一台額外的觸發器或常駐 Cron Manager——而「養一台常駐機器來跑排程」與「能中途停掉」的偏好直接衝突 | Scheduled Machine 一旦設定就不能再被 API 手動啟動，**日後想臨時手動觸發一次補跑會發現做不到**，屆時才發現這個互斥會是最糟的時機 |
| **B. VPS（Vultr/Linode 東京）全自架** | 24/7 一切自理，無冷啟動、無 pooler 陷阱、排程可設 `Asia/Taipei` 時區 | 關機不省錢，**與「能中途停掉」的偏好正面衝突**；OS／DB 維運全部自理；US$5 ≈ NT$162/月，比 NT$100/月上限**超出 62%**（非「略超」） | 若日後想靠關機省錢，會發現這條路在 VPS 上**從一開始就不存在**——這是 VPS 這個選項本質上的天花板，不是配置問題 |
| **C. Fly（運算）+ Render Cron Job（排程與告警）+ Neon Free** | 補上 Fly 缺的排程精度與失敗告警 | 三個供應商，故障排查要在三個 dashboard 之間切換；月費升到 ≈NT$56，仍在預算內 | 三供應商代表三份帳號管理、三份 secret 機制（見待決 5），複雜度是這個選項真正的隱藏成本 |
| **D. Render 全包**（Free web + Cron Job + Neon Free） | 兩個供應商（與 A 並列最少）、**四家中唯一有內建排程失敗告警**（見待決 8）、月費 ≈NT$32（比 A 貴，但比 C 便宜） | **Free instance 每月僅 750 小時、無 SLA**；節點僅新加坡，對台灣延遲劣於東京 | 750 小時上限對「一台 24/7」而言毫無餘裕（一個月約 730 小時），若 `api` 意外被留在醒著狀態超過閾值會直接撞頂 |
| **E. Railway 全包** | 標準 cron 語法（比 Fly 原生排程精確）；scale-to-zero 判準涵蓋 outbound 封包 | **沒有真免費層**（US$5/30 天為一次性試用額度，超出預算上限）；判斷「閒置」的準則是 outbound 封包而非 inbound request——若 `api` 的 DB 連線池留一條閒置連線，Railway **永遠不會判定它閒置**，scale-to-zero 會在沒有任何錯誤訊息的情況下失效，帳單誠實反映這件事 | 這個失效模式不會報錯，只會在月底看到帳單比預期高——與本專案反覆點名的「靜默出錯」是同一形狀 |

### 1.3 仍未查證的空白

1. **Fly.io 東京（nrt）的官方區域係數與實價**——定價頁區域切換為 JS 動態載入，靜態內容只有 ams（阿姆斯特丹）。§11.2 表中的 NT$28 是用 #5（2026-08-01）的舊查證數字推算隱含係數（約 1.26×）得出，**不是今日官方數字**。**未能查證，需人工確認**（`fly platform vm-sizes` 或登入 dashboard 才能取得）。
2. **Render / Fly 的 instance 與 Postgres 實價**——兩家定價頁皆為 JS 動態載入；表中數字沿用 #5 於 2026-08-01 的查證，**需人工複驗**。
3. **各節點對台灣的實測 RTT**——#5 與本次查證都只列節點地理位置，**未實測毫秒數**。
4. **#16 移交的兩項（`api` 冷啟動延遲、跨服務 RTT）**——見上方獨立小節，**未能查證，需人工確認**，且不建議由本次查證直接動手實測。

---

## 待決事項 2：成本上限

### 2.1 已知事實

- issue #1 已定調前提：「成本越低越好，自用初期『幾乎免費』是明確目標」。
- issue #17 第 2 則留言粗估落在 **NT$50–100/月**（先前給的 NT$39 只算了 `quote-worker`，未含 `api` 24/7 可達的成本、也未含網域費）。
- issue #17 第 4 則留言的算術事實：**NT$50–100/月 ＝ US$1.55–3.10/月**。在這個預算裡，**任何託管 PostgreSQL 的付費方案都放不進去**（最便宜的 Render Basic-256mb US$6 就已超標）——這使資料庫選項實質上被壓縮到 Neon Free／Supabase Free／自架三個（詳見待決 4）。
- issue #17 第 3 則留言新增了一個原本沒被算進預算的成本項：**`api` 走 scale-to-zero，代表任何人送一個 HTTP request 都能喚醒機器**，喚醒發生在認證中介層跑起來之前，認證擋不住它。這是「掃描器把機器叫醒」造成的請求量／執行秒數，與經常性月租費是兩種不同性質的支出。

### 2.2 選項盤點

| 選項 | 內容 | 代價／風險 |
|---|---|---|
| **只設一個總金額上限（如 NT$100/月），超過靠人工發現後介入** | 最簡單，符合單人自用的維運量級 | 若沒有任何告警機制搭配（見待決 8），**超支要等到月底看帳單才會發現**，那時成本已經發生 |
| **依平台原生機制設定 spending cap / billing alert** | 若平台有提供，可在接近上限時自動通知或攔停 | 本次查證主要聚焦在「經常性月費」的計算，**各平台是否提供硬性支出上限（而非只是事後 billing alert）尚未逐一查證** |
| **在 Caddy 層對掃描器流量做初步防禦**（如速率限制、只允許特定 method） | 直接處理「掃描器叫醒機器」這個成本的源頭 | 這已經是應用程式／基礎設施層的實作細節，**是否屬於本票範圍、還是留給實作階段自行決定，本文不下判斷** |

### 2.3 仍未查證的空白

1. **各平台（Fly/Railway/Render/Neon）是否提供硬性支出上限（spending cap）而非只是事後 billing alert**——未能查證，需人工確認。
2. **Neon Free plan 的 compute 大小上下限，以及 100 CU-hours 用罄後的行為**（是否停機、降速、或直接失敗）——`scheduling-and-db-sleep.md` §9 第 10 項已列為未查證項，直接影響 keepalive 策略是否會在月底撞頂。

---

## 待決事項 3：環境切分

### 3.1 已知事實

**這題在既有研究與規格文件中幾乎沒有被直接觸及**，唯一相關的既有事實來自即時報價架構：

> `realtime-quotes.md` §1：Fugle 免費層同時連線數 = **1 條，且是帳號級**，故**本機開發機與正式站不能同時跑 `quote-worker`**——第二個連上去不是排隊，是其中一個被拒或被踢。因此**本機 `quote-worker` 預設使用 fake provider**（重播錄製的 tick 檔），要接真行情必須顯式開旗標，且開旗標前必須確認正式站 worker 已停。

這意味著「本機開發」與「正式站」在 `quote-worker` 這一層**已經是事實上互斥的兩個環境**，不管本票怎麼決定「環境切分」的答案，這條規則都成立且優先。

issue #1 已定調的相關前提：單人使用但資料模型自始帶 `user_id` 外鍵（#9）；認證選 Google OIDC + GitHub OAuth 備援（#10）。

### 3.2 選項盤點

| 選項 | 代價 | 風險 |
|---|---|---|
| **只有 production**（本機直接改、deploy 即上線） | 零額外基礎設施 | Migration 或設定出錯沒有中間驗證環境，**直接打在正式資料上**；持股與交易紀錄「遺失不可接受」是 issue #17 body 原文自己點名的紅線 |
| **local dev + prod，無 staging** | 差異已天然存在於 `quote-worker` 的 fake/real provider 切換；多一組雲端環境變數與一份本機 `.env` | 需要清楚定義「dev 連哪個資料庫」——本機 `pgserver`（MEMORY 記載的既有跑法）還是共用同一個雲端 Neon Free 專案 |
| **local dev + staging + prod 三層** | 部署與設定的心智模型最完整 | issue #17 body 原文已自問「單人專案上 staging 可能是浪費」；且 staging 若要接近正式行為，需要獨立一份託管 DB 與平台帳號，直接撞上待決 2 的預算上限 |

### 3.3 仍未查證的空白

1. **整個「環境切分」題目本身在既有研究/規格中沒有任何前置查證**——這是純粹的待決策偏好題，不是有既定事實但沒查到的空白。
2. **本機開發要接同一個雲端 Neon Free 專案做整合測試、還是完全隔離用本機 `pgserver`**——未查證，也未在其他票中被提及。
3. **Migration 工具與流程**（如 Alembic）不在 `tech-stack.md` 涵蓋範圍內，未查證。

---

## 待決事項 4：資料庫託管

### 4.1 已知事實

**（a）硬性規則：listener 必須走 direct connection，不得走 pooled endpoint**

`realtime-quotes.md` §3 已定：transaction 模式的連線池會在每個 transaction 結束後把連線收回，`LISTEN` 因此完全失效。這條在 2026-08-06 查證後被寫成規則，因為「serverless 就該用 pooled connection」是一條很強的直覺，依它改回去，**報價扇出會在沒有任何錯誤訊息的情況下靜止**。

**（b）四家託管 Postgres 的休眠與 `LISTEN/NOTIFY` 支援（`scheduling-and-db-sleep.md` §4.1，2026-08-05~06 查證）**

| 託管 DB | 閒置休眠 | pooler 模式 | pooler 支不支援 `LISTEN/NOTIFY` | 備註 |
|---|---|---|---|---|
| **Neon Free** | 會，**5 分鐘**，免費層**不可關閉** | PgBouncer transaction | ❌ 官方明列不支援（可用去掉 `-pooler` 後綴的 direct 連線繞過） | scale-to-zero 會把 `LISTEN` 訂閱狀態整個丟掉（官方原文：「notifications and listeners... are lost when the session ends」） |
| **Supabase Free** | 會，低活躍 **7 天**後整個專案暫停 | Supavisor：6543 transaction／5432 session | **未能查證**（官方文件只講 prepared statements，未提 `LISTEN/NOTIFY`） | direct connection 走 IPv6，IPv4 需付費 add-on（僅 Pro 以上可買，US$4/月）；每天有排程寫入天然不會被暫停 |
| **Render Postgres Free** | 不休眠，但 **30 天到期** | 不提供 pooling | 不適用 | **本專案不可用**（每月搬一次家） |
| **Fly Managed Postgres** | 官方文件未提及，**推定不休眠但未查證** | PgBouncer，**預設 session** | ✅ **唯一官方明文支援**：「Full PostgreSQL feature compatibility... `LISTEN/NOTIFY`... all work normally」 | **US$38/月 ≈ NT$1,228，超預算 12 倍** |
| **VPS 自架** | 不休眠 | 自己決定（可不裝 pooler） | ✅（不經 pooler） | 唯一沒有 pooler 陷阱的選項，代價是備份與 OS 維運自理 |

**（c）算術事實再次點名（issue #17 第 4 則留言）**：NT$50–100/月的預算裡放不進任何付費託管 Postgres，**資料庫選項實質上只剩 Neon Free、Supabase Free、自架三個，而三者各自有 `LISTEN/NOTIFY` 的陷阱**。

**（d）Neon 的具體地雷細節（`scheduling-and-db-sleep.md` §4.2）**：`realtime-quotes.md` §3 早先的預言（「盤中、`api` 醒著、使用者正盯著螢幕看報價跳——此時資料庫看起來是完全靜止的……會自動休眠的託管資料庫只看到『十分鐘沒有 query』，於是休眠，順手掐掉 listener」）**在 Neon 上字面成立，且門檻比預言更短（5 分鐘，不是十分鐘）**。既有的應用層 keepalive 規則（定期在同一條連線發輕量查詢）能擋住這件事，代價是 compute 在盤中永不休眠，開始消耗 Free plan 的 100 CU-hours/project 額度。

**（e）備份策略：目前完全沒有既有規格**。已 grep 確認 `data-model.md` 全文未出現「備份」字樣。唯一相關的既有建議來自 #5（`persistent-websocket-hosting.md` §2.5，VPS 情境下）：「自用階段直接在同一台機器上自架 Postgres，每日 `pg_dump` 到物件儲存」——但這是 2026-08-01 針對 VPS 情境給的建議，**不是定案，也未評估託管方案（Neon/Supabase）各自的備份／PITR 機制**。

### 4.2 選項盤點

| 選項 | 代價 | 「做錯日後會很痛」的地方 |
|---|---|---|
| **Neon Free** | US$0；listener 需 keepalive 讓 compute 永不休眠，開始耗 100 CU-hours 免費額度（是否夠用未查證，見 §2.3）；節點僅新加坡（無東京）（`persistent-websocket-hosting.md` §2.5） | scale-to-zero 門檻只有 5 分鐘且免費層關不掉，**若忘記加 keepalive，`LISTEN` 會在完全沒有錯誤訊息的情況下靜止**——這正是 §4.1(d) 描述的情境 |
| **Supabase Free** | 每組織上限 2 個 active project；direct connection 走 IPv6，**候選運算平台是否提供 IPv6 出站未逐一查證**；Supavisor transaction mode 對 `LISTEN/NOTIFY` 的支援狀況官方文件隻字未提 | 若最終選了 transaction mode（因為誤以為它跟其他家一樣可繞過），且它其實不支援 `LISTEN/NOTIFY`，**這是一個連查證都查不到答案、只能實測才知道的地雷** |
| **Fly Managed Postgres** | US$38/月，超預算 12 倍 | 是四個選項中**唯一**官方文件把 `LISTEN/NOTIFY` 明確列為「works normally」的，若日後預算鬆綁，這是風險最低的選項 |
| **VPS 自架 / 或掛在同一台 Machine 上自架** | 無 pooler 陷阱、無休眠；備份與維運全部自理 | 若 DB 與 `quote-worker`／`api` 不同機，仍要面對 RTT 未知（見上方測量缺口）；若同機自架，則 DB 需要一直開著才能讓 `api` 醒來時可達——**這與「`api` scale-to-zero 省成本」的設計目標互相牽制**，因為機器本身不能真的完全關機 |

**備份策略的選項（目前皆無查證支持）**：

| 選項 | 說明 |
|---|---|
| `pg_dump` 排程 + 物件儲存 | #5 曾在 VPS 情境下建議，但「多開一個排程」又繞回待決 8（監控）同一組「怎麼知道排程有沒有跑」的問題 |
| 託管方案自帶的備份／PITR | Neon／Supabase／Fly MPG 各自的備份機制與 RPO/RTO **本次完全未查證** |
| 依賴 Transaction 是唯一事實來源＋使用者手上的原始對帳單 | `transaction-input.md` 已定 CSV 匯入為主，使用者手上本就留有原始對帳單，理論上可視為一份「影子備份」——但這只是推論，不是任何票的既有規格 |

### 4.3 仍未查證的空白

1. **Neon Free / Supabase Free / Fly MPG 各自的備份機制與 RPO/RTO**——完全未查證，本次查證範圍只涵蓋休眠與 `LISTEN/NOTIFY`。
2. **Supabase Supavisor transaction mode 是否支援 `LISTEN/NOTIFY`**——官方文件只講 prepared statements，未提 `LISTEN/NOTIFY`（按 PgBouncer 一般原理推論應為不支援，但本文不把推論當事實）。
3. **各運算平台是否提供 IPv6 出站**（決定 Supabase Free 的 direct connection 能否使用）——未逐平台查證。
4. **Fly Managed Postgres 是否有自動休眠／scale-to-zero**——官方文件完全未提及，以其定價形狀推定為常駐，但推定不是事實。
5. **#16 移交的 RTT 缺口**（見上方獨立小節）——`api` 醒來時 PostgreSQL 必須可達（`auth.md` 已指出這一點），若 DB 本身也 scale-to-zero（如 Neon），`api` 冷啟動 + DB 冷啟動疊加的延遲是這裡最直接相關的未解問題。

---

## 待決事項 5：機密注入

### 5.1 已知事實

- issue #1：所有 API 金鑰與憑證一律走 `.env`（已在 `.gitignore`）；本 repo 為 public，任何票的討論、規格、範例都不得包含實際金鑰。
- `auth.md`：行情源 API 金鑰在 `.env` 不在資料庫，要取得須先拿到機器本身；code → token 交換須在伺服器端用 `client_secret` 完成（Google/GitHub OAuth 的 client secret 因此也是一項機密）。
- 需要注入的機密清單（可從已定案的其他票推導）：行情 provider API key（Fugle／未來 Shioaji）、Google OIDC `client_secret`、GitHub OAuth `client_secret`、Postgres 連線字串（**須是 direct，非 pooled**——見待決 4）、Discord webhook URL（#15 已定管道）。
- `persistent-websocket-hosting.md` §2.7 逐平台 secret 機制查證（2026-08-01）：

| 平台 | 機制 |
|---|---|
| **Fly.io** | `fly secrets set`，secret 加密存在 vault，**「API server 只能加密不能解密」**，值永不進 log；Machine 開機時由 agent 解密注入為環境變數，**Machine 銷毀後 host 即失去存取權**。「這是本次比較中機制描述最完整的一家」 |
| Cloud Run | Secret Manager；前 6 個 active version 免費，之後 US$0.06/version/月 |
| Railway | 服務變數＋共用變數，支援 `${{NAMESPACE.VAR}}` 跨服務引用；**加密細節官方未載明** |
| Render | 環境變數；**Secret Files 細節本次未逐項查證** |
| VPS | 完全自理；建議 `systemd` unit 的 `EnvironmentFile=`（`chmod 600`）或 `sops`/`age` 加密進 repo |

### 5.2 選項盤點

| 選項 | 代價 | 風險 |
|---|---|---|
| **依平台選定後直接用其原生機制** | 摩擦最低，Fly.io 的機制描述在本次查證中最完整 | Secret 管理與平台選型綁死，日後換平台等於重建整批 secret |
| **平台無關的 secret 工具（如 `sops`/`age` 加密進 repo）** | 換平台時遷移成本低 | 對單人自用專案，多一層自己維護的加解密機制可能是過度工程 |
| **開發用 `.env`（本機檔案，已 gitignore），正式站用平台原生機制** | 與現有規則（issue #1）自然銜接 | 兩套心智模型；文件必須明確寫出「哪個環境用哪種方式」，否則會有人（包括未來的 agent）在錯的地方找 secret |

### 5.3 仍未查證的空白

1. **Railway / Render 的 secret 加密實作細節**——`persistent-websocket-hosting.md` §7 第 8 項已列未查證。
2. **若選 Fly.io，Machine 開機時解密注入 secret 的動作是否會拉長 scale-to-zero 冷啟動時間**——未查證，且與上方獨立小節的冷啟動缺口是同一組未解問題的延伸。

---

## 待決事項 6：CI/CD

### 6.1 已知事實

- 本 repo 為 public（issue #1）。
- `tech-stack.md` §7 已定分層測試策略：錢的計算（成本基礎、損益、報酬率）嚴格 TDD；外部資料源 adapter 走契約測試；行情重連退避邏輯用假時鐘測；**分析維度評分、API 端點、前端 v1 不寫測試**（#14 已於 2026-08-08 定案六維，但結論不變：v1 沒有回測能力、評等切點靠主觀設定，此時寫死的 assertion 意義仍不大，見 [`analysis-dimensions.md`](../spec/analysis-dimensions.md)）。這代表任何 CI 部署閘門能卡住的測試範圍，本來就只有前三層。
- `scheduling-and-db-sleep.md` §1：GitHub Actions `schedule` 事件對 public repo 免費，但官方明文「can be delayed during periods of high loads……**some queued jobs may be dropped**」，最小間隔 5 分鐘。
- **待決 1 已記載的一條交互規則**：若最終選 Fly.io 且 `quote-worker` 走原生 `--schedule`，該 Machine **就不能再被 API（含 CI/CD 的自動部署）啟動**——這對「push 即自動部署 worker」的流程是一個必須當場注意的互斥。

**這題的部署流程本身（手動 push vs GitHub Actions 自動部署）在既有研究與規格文件中完全沒有被討論過**——不是查不到答案，是根本沒有人問過這個問題。

### 6.2 選項盤點

| 選項 | 代價 | 風險 |
|---|---|---|
| **手動 deploy**（如本機執行 `fly deploy`） | 零額外基礎設施，單人專案最簡單 | 沒有部署前的自動化測試閘門，容易手滑推錯環境；`tech-stack.md` §4 已提過「開發時一定會反覆重啟 worker」，部署時機的判斷（是否為盤中）目前完全靠人工記得 |
| **GitHub Actions 全自動部署**（push 到 main 即測試＋deploy） | 常見最佳實踐，部署有測試閘門把關 | 能卡的測試範圍有限（見上）；若目標是 `quote-worker` 且平台選了 Fly 原生 `--schedule`，**自動部署會直接撞上待決 1 的互斥規則** |
| **GitHub Actions 跑測試，部署仍手動觸發**（如 `workflow_dispatch`） | 折衷：保留人工把關部署時機的能力，同時有自動化測試 | 需要額外設定一道人工確認步驟，比純自動部署多一點摩擦 |

### 6.3 仍未查證的空白

1. **整個 CI/CD 題目未經任何前置查證**——這是純待決策的偏好題，不是有既定事實但沒查到的空白。
2. **GitHub Actions 是否適合部署 `quote-worker`**——需考慮待決 1 中 Fly.io schedule 與 deploy 互斥的規則，這條交互在 grilling 現場需要被明確提出，否則容易被忽略到實作階段才發現。

---

## 待決事項 7：網域與 HTTPS

### 7.1 已知事實

- `tech-stack.md` §8：Caddy 只要看到網域名稱就自動申請並續期 Let's Encrypt 憑證，零額外設定；已定調公開在網際網路上。
- **#10 已經鬆綁了這一題的急迫性**（issue #17 第 3 則留言引用）：原本的顧慮是 WebAuthn 綁 origin，換網域會讓 passkey 全數作廢；但 #10 選定 Google OIDC + GitHub OAuth 後，這個約束消失——**換網域只需到 provider console 改一行 redirect URI，既有登入不受影響**。因此本票**可以先用免費子網域（DuckDNS／Cloudflare 免費子網域）上線，日後想換再換**，網域費從「必須先付」降為「想付再付」。
- 同則留言：**Cloudflare Access／Tunnel 已被 #10 否決**，不必再評估——`cloudflared` 靠常駐外連維持隧道，機器一停隧道就斷，加 Tunnel 等於把「否決 serverless」的邏輯（#5 的核心論點）從 `quote-worker` 搬到 `api` 頭上，會讓本票選定的 `auto_stop_machines` 直接失效。
- 約束 6（見 §0）：無論用哪個網域，Caddy 申請憑證都會讓網域進 Certificate Transparency log，上線數小時內必有掃描器來敲。

### 7.2 選項盤點

| 選項 | 代價 | 風險 |
|---|---|---|
| **免費子網域（DuckDNS／Cloudflare 免費子網域）** | NT$0，符合成本偏好；已由 #10 論證換網域成本低，不必一次選對 | 免費子網域是否支援 Caddy 的 ACME 自動化流程（HTTP-01 或 DNS-01 challenge）——**未查證** |
| **自購網域**（.com／.tw 等） | 較「正式」，但 #10 已明確論證此非必要前提 | 年費行情本文未查證 |
| **平台附贈的預設網域**（如 `*.fly.dev`） | 免額外設定 | 同樣會進 CT log，**不能迴避掃描器問題**；是否可直接綁自訂憑證、是否滿足「公開 + HTTPS」的其他約束未查證 |

### 7.3 仍未查證的空白

1. **免費子網域（DuckDNS／Cloudflare）是否支援 Caddy 的 ACME 自動化流程**——未查證。
2. **自訂網域的實際年費行情**——未查證，非本次查證範圍。

---

## 待決事項 8：監控

### 8.1 已知事實

**（a）四平台原生排程失敗告警對照**（`scheduling-and-db-sleep.md` §8）

| 平台 | 內建「排程失敗」告警 |
|---|---|
| **Render** | ✅ 四家中唯一有——email／Slack／webhook，webhook 投遞失敗會重試最多 8 次 |
| **Railway** | ⚠️ 有 deploy/crash 層級 webhook，但「這一次 cron run 失敗」層級的告警**官方文件未明確涵蓋**，未能查證 |
| **Fly.io** | ❌ 官方明文「doesn't include built-in alerting on metrics」 |
| **VPS** | ❌ 需自建 |

**（b）所有平台共通的盲點：「沒跑」與「跑了但失敗」是兩件事**

Render／Railway 的告警都是「這次 run 失敗了」。但本專案真正該怕的是「排程根本沒被觸發」——例如 GitHub Actions 高負載時 job **被丟棄**（官方明文）、Railway 上一次還沒結束時本次 **直接被跳過**（官方明文：「Railway will skip the new cron job」）、Fly Scheduled Machine 啟動時資源不足報錯。**這三種情況都不會產生一次「失敗的 run」，因此不會觸發任何平台的失敗告警。** 要偵測它們只能靠反向心跳（dead-man's switch），且這需要一個第四方服務，本次未查證選項與價格（`scheduling-and-db-sleep.md` §8.1）。

**（c）issue #17 第 5 則留言新增的第三種失效模式：「跑了、成功了、但錯了」**

`tw-benchmark-and-fx-sources.md` §D 實測發現：`openapi.twse.com.tw` 比 `www.twse.com.tw/...?response=open_data` **落後整整一個交易日**（**單一時點樣本，T+13.75h；是否恆定、會不會在別的時點追上，同文列為未查證項**，此處引用其作為「跑了但錯了」這個失效模式的具體例證，不代表已證實為恆定行為）。走 JSON 鏡像的盤後排程會**每天成功、每天回 1,377 列、不產生任何失敗訊號**，但整條歷史序列永遠晚一天，且因為錯位一致，圖上看不出來（同文 §D E-3）。**dead-man's switch 抓不到它**——排程確實有跑、確實成功了。**唯一的防法是排程自己斷言回傳的日期 == 預期交易日，不符即失敗**；這條屬於應用程式邏輯，但它應該被算進本票對「怎麼知道排程出事了」的答案裡。

**（d）盤中即時連線狀態已由 #13 規定，但只涵蓋盤中**：`realtime-quotes.md` §3 已定「listener 中斷必須反映到前端連線狀態指示器，不可只監看行情源那端」——否則畫面顯示「即時連線」而價格靜止。這條解決的是**盤中**的靜默失效，不涵蓋盤後排程。

**（e）半夜通知的三個真實出錯途徑**（`scheduling-and-db-sleep.md` §10.3）：把台北時間直接寫進 UTC cron（差 8 小時剛好落在傍晚到深夜，且完全沒有錯誤訊息）；GitHub Actions 高負載延遲導致 job 被丟棄，累積的通知隔天一次送一堆；outbox 積壓後掛掉數小時再恢復，累積的通知一次全部送出。

### 8.2 選項盤點

| 選項 | 涵蓋的失效模式 | 代價／限制 |
|---|---|---|
| **依附選定平台的原生告警**（如選 Render 用其 email/Slack webhook） | 「跑了但失敗」 | 免費或低成本，但**涵蓋不到「沒跑」與「跑了但錯了」** |
| **接第四方 dead-man's switch 服務** | 「沒跑」 | 選項與價格本次完全未查證；多一個外部依賴與帳號 |
| **排程自行斷言（如 `openapi` 回傳日期 == 預期交易日）** | 「跑了但錯了」 | 零額外基礎設施成本（屬應用邏輯），但只對「已知會發生」的錯誤模式有效，無法涵蓋未知的資料錯誤 |
| **前端連線狀態指示器** | 盤中「斷線但看起來正常」 | 已由 `realtime-quotes.md` §3 規定必須做，但**不涵蓋盤後排程**這個獨立的失效面 |

**沒有任何單一選項能同時涵蓋三種失效模式**——這三個選項分別針對三個不同的失效面，需要組合使用。

### 8.3 仍未查證的空白

1. **第四方 dead-man's switch 服務的選項與價格**——完全未查證（`scheduling-and-db-sleep.md` §9 第 12 項）。
2. **Render Cron Job 的最小排程間隔**——官方文件只給了 `*/10 * * * *` 範例，未載明是否允許 `*/1`。
3. **Railway cron run 層級的失敗告警是否存在**——未能查證。
4. **Render 是否有「按排程 suspend/resume 一個服務」的 API**——未查證，與待決 1 中「worker 只在盤中開機」的觸發機制選擇有關。

---

## 待決事項 9：從自用到上架，哪些部署決策現在做錯，日後會很痛

### 9.1 已知事實

- issue #1「Not yet specified」已把「上架給他人使用」列為**獨立於本圖範圍之外**的區域，並記載已知的重大約束：**券商行情不得轉供第三人**，合法路徑只剩三條——自行簽約成為資訊廠商（傳輸授權 6 萬/月起、網際網路通路 10 萬/月起）、只呈現延遲 20 分鐘以上資料、或只呈現衍生結論不呈現原始行情。這三條路的取捨足以決定產品形態，issue #1 明寫「需要獨立一張圖」——**不在本票範圍內，但本票的部署決策要意識到它的存在**。
- 同段另記載：`daily_close` 的歷史（收盤價、日高低、成交量）與除權息參考價**唯一乾淨的來源是 FinMind**，其資料再散布授權未明示；自用無虞，但對外提供服務時會與「券商行情不得轉供第三人」同時擋路。
- `realtime-quotes.md` §10「暫時性妥協與解除條件」已記錄多條與 provider 額度／開戶相關的限制（訂閱 5 檔上限、即時警示限持股標的等）——這些不是本票直接管轄的範圍，但部署規模若擴大（如同時服務多人）會放大這些額度限制。
- Neon Free（0.5 GB／project）、Supabase Free（每組織 2 個 active project）等資源上限是為單人自用估的，**多人使用會直接撞頂**。
- `auth.md` 已定：開放註冊清單降級為驗收標準（v1 只承諾「不寫死」），**法遵才是真阻擋者**——這條直接點名，若本票現在把平台／DB 選型寫死成「只夠一人」的形狀，日後要改的不會只是設定值。
- `data-model.md`（#9）已為 `user_id` 預留外鍵，但這只解決**資料庫層級**的多租戶問題，不解決部署／成本／法遵層級的問題。

### 9.2 選項盤點

| 選項 | 代價 | 風險 |
|---|---|---|
| **現在就把平台選型做成「可水平擴展」的形狀**（如選原生支援多實例的方案） | 換取未來擴展彈性 | 當下付出更高成本與複雜度，與「越低越好」的成本偏好直接衝突 |
| **現在專注解自用（單人、最低成本），明確記錄「哪些是暫時性妥協」**（比照 `realtime-quotes.md` §10 的既有做法） | 符合 issue #1「這張圖只產出決策與規格」的定位，且「上架給他人使用」已被列為獨立範圍 | 若記錄不完整，日後開新票處理上架時要重新盤點一次哪些決策是權宜之計 |
| **選型時對「換供應商代價」做輕量評估，但不為此多花錢** | #12／#13 已在 provider adapter 層做了類似的事（`ProviderCapabilities`），部署層若比照這個模式做「低摩擦換供應商」的設計，理論上代價不高 | 部署層是否有等價的抽象設計，**本票尚未有人明確盤點過**，是一個新的工作項而非既有結論的延伸 |

### 9.3 仍未查證的空白

1. **資訊廠商簽約（傳輸授權 6 萬/月起）的門檻與程序細節**——未查證，非本文範圍（issue #1 已明確列為獨立票的範圍）。
2. **若選 Fly.io/Neon Free 等單人配置方案，日後遷移到多租戶/多人方案的實際遷移成本**（停機時間、資料搬遷）——完全未查證。

---

## 建議的提問順序

### 依賴關係

```
Q1 待決 2（成本上限的具體數字，NT$50–100/月是否為最終上限？）
   │
   ▼
Q2 待決 1（平台定案）──────────┐
   ⚠️ 現場點名：#16 移交的兩項  │
      仍無實測數字，只有官方文件 │
      的模糊描述               │
                               ├──▶ Q3 待決 4（資料庫託管與備份）
                               │      ⚠️ 同一個 ⚠️ 缺口在此再次浮現
                               │      （跨服務 RTT）
                               │
                               ├──▶ Q4 待決 5（機密注入）
                               │      （原生機制 vs 平台無關工具）
                               │
                               └──▶ Q5 待決 6（CI/CD）
                                      ⚠️ 需檢查是否撞上 Fly
                                      schedule／deploy 互斥

Q6 待決 3（環境切分）── 相對獨立，隨時可問
Q7 待決 7（網域與 HTTPS）── 已由 #10 大幅鬆綁，相對獨立
Q8 待決 8（監控）── 依賴 Q2/Q3 的平台與 DB 選擇（哪家有原生告警）
Q9 待決 9（自用轉上架的地雷）── 建議放最後，回顧前面八題各自留下的暫時性妥協
```

### 逐題理由

| 順位 | 問什麼 | 為什麼在這個位置 |
|---|---|---|
| **Q1** | 待決 **2**：NT$50–100/月是否為最終上限，還是仍有彈性 | 這個數字直接決定待決 1 有幾個選項可談——一旦鬆綁到能接受 Fly MPG 的 US$38/月，待決 4 整個選項盤點都會不同 |
| **Q2** | 待決 **1**（平台定案） | 錨定其他六題（DB／secret／CI/CD／監控的可用選項都隨平台而變）。**這裡必須明確點名 #16 移交的兩項至今無實測數字**，讓使用者知道這個決策是在缺口尚未補上的情況下做的 |
| **Q3** | 待決 **4**（資料庫託管與備份） | 與待決 1 高度耦合（Fly MPG／Neon／Supabase／自架的選項本身就是平台選擇的延伸）。**跨服務 RTT 的缺口在此再次相關**，因為它是 DB 選型的直接後果 |
| **Q4** | 待決 **5**（機密注入） | 依平台選擇而定（Fly.io 有本次查證中機制描述最完整的 secret 系統） |
| **Q5** | 待決 **6**（CI/CD） | 依待決 1 的平台選擇而定，且**若選 Fly.io 需要在此檢查 schedule／deploy 互斥規則是否影響自動部署 `quote-worker` 的設計** |
| **Q6** | 待決 **3**（環境切分） | 相對獨立，且是一題完全沒有既有查證支撐的偏好題，可以隨時插入討論 |
| **Q7** | 待決 **7**（網域與 HTTPS） | 已由 #10 大幅鬆綁急迫性（換網域成本低），相對獨立，可放在後段快速定案 |
| **Q8** | 待決 **8**（監控） | 依賴 Q2/Q3 已定的平台與 DB，才知道有哪些原生告警可用；**三種失效模式（沒跑／跑了但失敗／跑了但錯了）建議在此逐一點名**，避免只解決其中一種就結束討論 |
| **Q9** | 待決 **9**（自用轉上架的地雷） | 最後回顧。前八題每一題都可能留下「暫時性妥協」，此時集中記錄一次，比照 `realtime-quotes.md` §10 的既有做法 |

---

## 附錄：本文引用的第一手來源

**專案內文件**（皆在 `C:\Users\user\claude\stock-analytic-platform`）

- `CONTEXT.md`
- `docs/spec/tech-stack.md`、`docs/spec/realtime-quotes.md`、`docs/spec/performance.md`、`docs/spec/auth.md`、`docs/spec/data-model.md`
- `docs/research/persistent-websocket-hosting.md`（#5，2026-08-01）
- `docs/research/scheduling-and-db-sleep.md`（#17 前置研究，2026-08-05~06）
- `docs/research/tw-benchmark-and-fx-sources.md` §D（openapi.twse.com.tw 落後一天的實測）
- `docs/briefing/16-performance.md`（#16 上桌前準備，含 R1/R5 移交註記）
- `docs/briefing/bench/`（#16 的丟棄式量測腳本先例）

**GitHub**

- [issue #1](https://github.com/NTUyu016/stock-analytic-platform/issues/1)（地圖，含已定調前提與 Not yet specified）
- [issue #17](https://github.com/NTUyu016/stock-analytic-platform/issues/17)（本票，含 5 則留言）
- [issue #16](https://github.com/NTUyu016/stock-analytic-platform/issues/16)（移交本票兩項效能問題的來源）

**官方定價與文件頁**（第一手，經 `scheduling-and-db-sleep.md` 與 `persistent-websocket-hosting.md` 查證，完整清單見該二文各自的「來源清單」章節）

- Fly.io：<https://fly.io/docs/about/pricing/>、<https://fly.io/docs/launch/autostop-autostart/>、<https://fly.io/docs/mpg/client-configuration/>、<https://fly.io/docs/monitoring/metrics/>
- Railway：<https://docs.railway.com/reference/cron-jobs>、<https://docs.railway.com/deployments/serverless>
- Render：<https://render.com/docs/cronjobs>、<https://render.com/docs/free>、<https://render.com/docs/postgresql-connection-pooling>
- Neon：<https://neon.com/docs/reference/compatibility>、<https://neon.com/docs/introduction/compute-lifecycle>、<https://neon.com/docs/connect/connection-pooling>
- Supabase：<https://supabase.com/docs/guides/platform/free-project-pausing>、<https://supabase.com/docs/guides/database/connecting-to-postgres>
- 中央銀行新臺幣對美元收盤匯率：<https://www.cbc.gov.tw/tw/lp-645-1.html>
