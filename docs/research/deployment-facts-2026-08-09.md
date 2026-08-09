# 部署事實補查：Fly/Render/Neon/Supabase 實價、支出上限、反向心跳、免費子網域

> 對應 issue：[#17 部署、環境與成本上限](https://github.com/NTUyu016/stock-analytic-platform/issues/17)
> 查證日期：**2026-08-09**（第三方定價與政策會變，逾期請重驗）
> 匯率：**1 USD = 32.315 TWD**。⚠️ 這是[`scheduling-and-db-sleep.md`](./scheduling-and-db-sleep.md) 沿用之 **2026-08-05** 中央銀行牌告（<https://www.cbc.gov.tw/tw/lp-645-1.html>），本次**未重新取得今日牌告**，時效需自行確認。
> 前置研究：[#5 常駐 WebSocket 後端的雲端部署選項與成本](./persistent-websocket-hosting.md)（2026-08-01）、[排程落腳處、scale-to-zero 喚醒、與託管資料庫休眠](./scheduling-and-db-sleep.md)（2026-08-05~06）
>
> **本文只列事實，不做任何決策、不給任何推薦。** 比較可以，選擇不行。
> **本次未開任何帳號、未綁任何金流、未實際部署。** 所有數字皆來自公開的官方文件、官方定價頁或官方 API，無登入。

---

## 0. 方法說明：兩個「JS 動態載入」的定價頁其實是靜態的

[`scheduling-and-db-sleep.md`](./scheduling-and-db-sleep.md) §9 第 1、8 項把 Fly.io 東京實價與 Render 實價列為「定價頁為 JS 動態載入，未能自第一手定價頁讀取」。**本次查證推翻了這個判斷**：

| 頁面 | 實際情形 | 取得途徑 |
|---|---|---|
| <https://fly.io/docs/about/pricing/> | **所有區域的價目表都已在 HTML 裡預先渲染完成**，只是用 CSS class `hidden` 藏起來，JS 只負責切換顯示哪一張表（`document.getElementById(\`started-machines-pricing-matrix-${regionSelect.value}\`).classList.remove("hidden")`）。同頁另有 `const regionMarkups = {...}` 常數，已含各區係數的實際數值 | `curl` 取原始 HTML，抽出 `started-machines-pricing-matrix-nrt` 表格與 `regionMarkups` 常數 |
| <https://render.com/pricing> | 價目表為**伺服器端渲染的 HTML `<table>`**，不需要執行 JS | `curl` 取原始 HTML，剝除標籤後直接讀表 |

也就是說，§9 的第 1、8 兩項**不是「查不到」，是先前的抓取方式抓錯層**。以下 §1、§2 的數字全部來自這兩個第一手頁面本身，非推算、非二手。

---

## 1. Fly.io 東京（nrt）實價

### 1.1 官方區域係數（第一手，直接取自定價頁 HTML 的 `regionMarkups` 常數）

<https://fly.io/docs/about/pricing/>（2026-08-09）

| 區域 | 係數 | | 區域 | 係數 |
|---|---|---|---|---|
| `iad`（Ashburn） | **1**（基準） | | `bom`（孟買） | 1.076923077 |
| `ewr`（New Jersey） | 1 | | `yyz`（多倫多） | 1.115384615 |
| `ams`（阿姆斯特丹） | 1.038461538 | | `cdg` / `lhr` | 1.134615385 |
| `arn`（斯德哥爾摩） | 1.038461538 | | `fra`（法蘭克福） | 1.153846154 |
| `sjc`（San Jose） | 1.192307692 | | `lax` | 1.199519231 |
| `ord` / `dfw` | 1.25 | | `sin`（新加坡） | 1.269230769 |
| `syd`（雪梨） | 1.269230769 | | **`nrt`（東京）** | **1.307692308** |
| `jnb`（約翰尼斯堡） | 1.302884615 | | `gru`（聖保羅） | 1.615384615 |

**`nrt` 是本表中第二貴的區域**（僅次於 `gru` 聖保羅），且比 `sin` 新加坡貴約 3.0%。

> 📌 **對既有推算的驗證**：`scheduling-and-db-sleep.md` §7.1 推算「nrt 對 ams 的隱含係數約 1.26×」。以官方係數計算：1.307692308 ÷ 1.038461538 = **1.259259**。**該推算是正確的**，本次只是把它換成官方數字。

### 1.2 shared-cpu-1x 各記憶體規格的 nrt 實價（第一手）

<https://fly.io/docs/about/pricing/>（2026-08-09）

| 規格 | Price/second | Price/hour | **Price/month** | 換算 NT$/月 |
|---|---|---|---|---|
| shared-cpu-1x / 256MB | $0.00000098 | $0.0035 | **$2.54** | NT$82 |
| shared-cpu-1x / 512MB | $0.00000161 | $0.0058 | **$4.18** | NT$135 |
| shared-cpu-1x / 1GB | $0.00000287 | $0.0103 | **$7.45** | NT$241 |
| shared-cpu-1x / 2GB | $0.00000540 | $0.0194 | **$13.99** | NT$452 |
| shared-cpu-2x / 2GB | $0.00000575 | $0.0207 | **$14.90** | NT$481 |

對照組（同頁，同日）：

| 規格 | `ams` | `sin` | `nrt` |
|---|---|---|---|
| shared-cpu-1x / 256MB | $2.02 | $2.47 | **$2.54** |
| shared-cpu-1x / 512MB | $3.32 | $4.05 | **$4.18** |
| shared-cpu-1x / 1GB | $5.92 | $7.23 | **$7.45** |
| shared-cpu-1x / 2GB | $11.11 | $13.58 | **$13.99** |

> 📌 **與 #5（2026-08-01）的複驗結果：完全一致。** [`persistent-websocket-hosting.md`](./persistent-websocket-hosting.md) §1 記載 nrt 512MB = US$4.18、1GB = US$7.45、shared-cpu-2x/2GB = US$14.90。**三個數字今日逐一吻合，八天內未調價。**

### 1.3 停機 Machine 是否真的不計 CPU/RAM

官方原文（<https://fly.io/docs/about/pricing/>，2026-08-09）：

> "**For stopped Machines we charge only for the root file system (rootfs) needed for each Machine. Each 1GB of rootfs for a Machine stopped for 30 days is $0.15.** The amount of rootfs needed is defined by your OCI image generated on your app plus a few containerd tweaks on the underlying file system."

**「只收 rootfs」＝ CPU 與 RAM 在停機期間不計費**，官方以「only for」明文表述。此點與 `scheduling-and-db-sleep.md` §5.2 的記載一致，本次複驗無變動。

⚠️ **但有一條先前未被記錄的重要例外**（同頁 Volumes 章節）：

> "**You'll be charged for volumes that you create, whether they are attached to a Machine or not, including when an attached Machine is stopped.**"

**Volume 不受停機影響，照樣按 provisioned 容量計費。** 也就是說「停機不計費」只適用於 CPU/RAM，**不適用於掛在該 Machine 上的 volume**。若採「在 Fly Machine 上自架 Postgres」的形狀，資料一定放在 volume 上，那部分的成本就與開關機無關。

⚠️ **`suspended` 狀態的計費規則官方定價頁未載明**——全頁只寫 `stopped`，未出現 `suspended` 的計費敘述。**未能查證。**

### 1.4 Volume、頻寬與其他

<https://fly.io/docs/about/pricing/>（2026-08-09）

| 項目 | 官方價 | 換算 NT$ | 是否隨區域變動 |
|---|---|---|---|
| Fly Volumes | **$0.15/GB per month of provisioned capacity**，pro-rated to the hour | NT$4.8/GB/月 | **官方頁未列區域差異** |
| Volume Snapshots | **$0.08/GB per month**，**First 10GB free each month**；按實際存量非 provisioned 量計、增量儲存 | NT$2.6/GB/月 | 同上 |
| 停機 rootfs | $0.15/GB/30 天 | NT$4.8 | 同上 |
| 共用 IPv4 + 不限量 Anycast IPv6 | **每個 app 免費**（"Each application receives a shared IPv4 address and unlimited Anycast IPv6 addresses"） | — | — |
| 專用 IPv4 | **$2/mo** | NT$65 | — |
| Managed SSL：單一 hostname 憑證 | $0.10/mo，**每個組織前 10 張免費** | — | — |
| Managed SSL：wildcard 憑證 | $1/mo | NT$32 | — |
| Static Egress IP for Machines | $0.005/hour（~$3.60/月），含一組 IPv4＋IPv6 | NT$116 | — |

**頻寬（Data transfer）**——官方原文：「**Fly.io pricing is per region group for outbound data transfer.**」

| Region group | Egress to public internet | Private network cross-region |
|---|---|---|
| North America、Europe | $0.02/GB | $0.006/GB |
| **Asia Pacific、Oceania、South America** | **$0.04/GB**（NT$1.29/GB） | **$0.015/GB** |
| Africa、India | $0.12/GB | $0.050/GB |

**免費的流量類型**（官方明列）：
> "All inbound data transfer" ／ "Data transfer between apps or Machines in the same region (for organizations using granular data transfer rates)" ／ "Data transfer from apps without an assigned IP address (for organizations not using granular data transfer rates)"

⚠️ 一條與新帳號直接相關的規則：
> "**Organizations created after July 18 2024 are automatically opted-in to use the granular data transfer rates**"，且 "You won't be able to return to using the non-granular data transfer rates once you opt in."

### 1.5 免費層、方案與其他同頁事實

- **新客戶沒有方案，也沒有免費額度**：「**Fly.io no longer offers plans to new customers.** If you purchased a Launch or Scale plan before October 7, 2024, you can remain on those plans...」。Legacy Free allowances（3 台 shared-cpu-1x 256mb VM、3GB volume、Asia Pacific 30GB egress）官方明列**只對 sunset 前既有組織 honored**。→ 與 `scheduling-and-db-sleep.md` §11.1「真免費層 ❌」一致。
- **Machine reservation blocks**（本次新查到，先前兩份研究皆未記載）：預付可拿 **40% 折扣**。Shared Machines 的最小級距是「**$36/year for $5/month of usage**」，攤提後等於每月 $3 換 $5 的用量額度，且「The credit applies only to CPU and additional RAM charges」、「The credit does not rollover」。
- **Unmanaged Fly Postgres**（官方標題明列為 **"Unsupported Products"**）：「The Machine price and volume price for Fly Postgres are the same as any other Machine and volume」、「the cost for the preset configurations is **about $2/month for a single node cluster for dev projects**」。
- **Managed Postgres（MPG）實價複驗**（<https://fly.io/docs/mpg/>，2026-08-09）：Basic（shared-2x/1GB）**$38.00**、Starter（shared-2x/2GB）$72.00、Launch $282.00、Scale $962.00、Performance $1,922.00；儲存「**$0.28 per provisioned GB for a 30-day month**」。**東京（Tokyo）在 12 個可用區域清單內。** 與 `scheduling-and-db-sleep.md` §7.1 記載一致，無變動。MPG 頁面**仍未提及 auto-suspend／scale-to-zero**，亦**未給出備份保留期數字**（只寫 "Automatic backups and recovery"）→ **仍未能查證**。

---

## 2. Render 的實價與能力

### 2.1 Instance 與 Postgres 實價（第一手，取自 <https://render.com/pricing> 的伺服器端 HTML 表格，2026-08-09）

**Web Services / Private Services / Background Workers**

| Instance Type | 月費 | RAM | CPU | 換算 NT$ |
|---|---|---|---|---|
| Free | **$0/month** | 512 MB | 0.1 | — |
| Starter | **$7/month** | 512 MB | 0.5 | NT$226 |
| Standard | **$25/month** | 2 GB | 1 | NT$808 |
| Pro | $85/month | 4 GB | 2 | NT$2,747 |
| Pro Plus | $175/month | 8 GB | 4 | — |

**Render Postgres**

| 層級 | 方案 | 月費 | CPU | RAM | 連線數 | 換算 NT$ |
|---|---|---|---|---|---|---|
| Free | Free | **$0（30-day limit）** | 0.1 | 256 MB | 100 | — |
| Basic | Basic-256mb | **$6/month** | 0.1 | 256 MB | 100 | NT$194 |
| Basic | Basic-1gb | **$19/month** | 0.5 | 1 GB | 100 | NT$614 |
| Basic | Basic-4gb | $75/month | 2 | 4 GB | 100 | — |
| Pro | Pro-4gb | $55/month | 1 | 4 GB | 100 | NT$1,777 |

**Cron Jobs**（**按分鐘計價，不是按月**）

| Instance Type | 單價 | RAM | CPU |
|---|---|---|---|
| Starter | **$0.00016/minute** | 512 MB | 0.5 |
| Standard | $0.00058/minute | 2 GB | 1 |
| Pro | $0.00197/minute | 4 GB | 2 |
| Pro Plus | $0.00405/minute | 8 GB | 4 |

搭配 <https://render.com/docs/cronjobs> 的「**There is a minimum monthly charge of $1 per cron job service.**」——一個每交易日跑 60 秒的 job（每月約 20 分鐘 × $0.00016 = $0.0032）**遠低於 $1 下限，實付即 $1/月 ≈ NT$32**。

> 📌 **與 #5（2026-08-01）的複驗結果：完全一致。** [`persistent-websocket-hosting.md`](./persistent-websocket-hosting.md) §1 記載 Starter US$7、Standard US$25、Postgres Basic-256mb US$6、Basic-1gb US$19。**四個數字今日逐一吻合。** `scheduling-and-db-sleep.md` §7.3 中三處「需人工複驗」的註記可以解除。

**其他同頁事實**：Render Key Value（Redis）Free $0 / 25 MB / 50 connections、Starter $10/月 / 256 MB。Bandwidth 超量費率 Starter $0.05/GB、Standard $0.20/GB。

### 2.2 Free instance 的 750 小時與 spin down（第一手，<https://render.com/docs/free>，2026-08-09）

官方原文，逐條：

> "Render grants **750 Free instance hours** to each workspace per calendar month"
> "A Free web service consumes these hours as long as it's running (**spun-down services don't consume Free instance hours**)."
> "**If you consume all of your Free instance hours during a given month, Render suspends all of your Free web services until the start of the next month.**"
> "At the start of each month, your Free instance hours reset to 750 (**remaining hours don't roll over**)."

spin down／spin up：

> "Render **spins down** a Free web service that goes 15 minutes without receiving any inbound traffic. **This includes both HTTP requests and WebSocket messages from existing connections.**"
> "A Free web service spins back up whenever it next receives an HTTP request or new WebSocket connection. **This process takes about one minute.**"

另有三條先前未被記錄的 Free instance 規則：

1. **「服務自己發出的流量」也可能觸發停權**：「**Render may suspend a Free web service that initiates an uncommonly high volume of traffic over the public internet.**」且「If your service is suspended this way, you can restore it by moving it to any paid instance type.」（原文未定義 "uncommonly high" 的門檻 → **未能查證具體閾值**）
2. **沒有付款方式時的行為**：「If you haven't added a payment method, Render instead suspends all of your Free services for the remainder of the month.」
3. **Render 會代為回應 robots.txt，且該請求不會喚醒服務**：「These requests to do not reach your service or trigger a spin-up.」（原文如此，含 typo）
4. **Free 服務為 ephemeral filesystem**：「any changes to your web service's filesystem... are lost every time the service redeploys, restarts, or **spins down**」

### 2.3 Cron Job 的最小排程間隔

**仍未能查證。** <https://render.com/docs/cronjobs>（2026-08-09）全文**未載明**任何最小間隔或頻率下限，也未說明是否允許 `*/1`。官方只提供 `*/10 * * * *` 這類範例，並寫「Full support for cron expressions」（定價頁行銷文案）。**官方未載明 ≠ 允許**，本文不做推論。

同頁其他可確認的事實：
> "**Render stops an active run after 12 hours.**"
> "Render guarantees that **at most one run of a given cron job is active at a given time**."
> "There is a minimum monthly charge of $1 per cron job service."

另據 <https://render.com/docs/compute-plans>：**Cron Job 的可選 instance type 不含 Free**（只有 Starter / Standard / Pro / Pro Plus），與 Web Service 不同。**Cron Job 沒有免費檔位。**

### 2.4 是否有「按排程 suspend/resume 一個既有服務」的 API —— **有**

<https://api-docs.render.com/reference/suspend-service-1>、<https://api-docs.render.com/reference/resume-service-1>（2026-08-09）

| 動作 | Method | Path |
|---|---|---|
| Suspend | `POST` | `/services/{serviceId}/suspend` |
| Resume | `POST` | `/services/{serviceId}/resume` |

官方描述：suspend 為「Suspend the service with the provided ID.」；resume 為「Resume the service with the provided ID (if it's currently suspended).」。兩者皆需 Bearer token。API base 為 `https://api.render.com/v1`（<https://render.com/docs/api>）。

⚠️ **官方 API 文件未明列這兩個端點適用於哪些 service type**（tag 為泛用的 "Services"）。→ **「是否可用於 Background Worker」未能查證。**

> 📌 這直接補上 [`17-deployment.md`](../briefing/17-deployment.md) §8.3 第 4 項與 `scheduling-and-db-sleep.md` §9 第 9 項的空白：**Render 確實有 suspend/resume service 的 REST API**，§5 表格中「Render：官方文件未提供按排程 suspend/resume 服務的做法 → 未能查證」這一格的敘述需要更新。

### 2.5 Render 區域

<https://render.com/docs/regions>（2026-08-09）：Oregon、Ohio、Virginia、Frankfurt、**Singapore**。**亞洲僅新加坡，無東京／無日本節點。** 與既有記載一致。

### 2.6 Render Postgres 的備份與 PITR

<https://render.com/docs/postgresql-refresh>（2026-08-09）：

> "**All paid databases receive point-in-time recovery (PITR) automatically.** Your retention period for PITR depends on your workspace's plan: **Hobby: 3 days; Pro or higher: 7 days.**"

定價頁（<https://render.com/pricing>）同步標示 Render Postgres 的「Logical backup retention (**paid only**)」與「Point-in-time-recovery (PITR) (**paid only**)」。

> **Free Postgres 沒有 PITR、沒有 logical backup retention**（且 30 天到期，見既有研究）。

---

## 3. Neon Free plan

### 3.1 額度與用罄後的行為（第一手，本節是本次查證資訊量最大的一節）

<https://neon.com/faqs/free-plan-limits-and-quotas>、<https://neon.com/docs/introduction/plans>（2026-08-09）

| 項目 | Free plan |
|---|---|
| Compute | **100 CU-hours of compute per project per month** |
| 儲存 | **0.5 GB per project** |
| **公網傳輸** | **5 GB of public network transfer per project per month** ← **先前兩份研究皆未記載的額度** |
| Projects | 100 |
| Branches | 10/project |
| Compute 大小上限 | 「computes with **up to 2 CU (8 GB of RAM)**」 |
| Scale-to-zero | **After 5 min**，且官方標記 **"cannot disable"** |
| 費用 | $0/month，**且 Free plan 不會產生任何超額帳單** |

**用罄後的行為（官方原文）**：

> CU-hours 用罄：「**the project's compute is suspended until the next billing period or until you upgrade. Existing connections drop and new ones can't open.**」
> 公網傳輸用罄：同上行為。
> 儲存超標：「**the project is suspended rather than billed.** Delete data or upgrade to continue writing.」
> Branch 超標：「branch creation fails until you delete one or upgrade.」
> 整體：「Compute drops to zero CU when suspended, so you don't pay for compute while idle.」

**答案是「停機」，不是「降速」也不是「單筆失敗」**——而且是**整個 project 的 compute 被 suspend 到下個帳期**，既有連線會被切斷、新連線開不起來。（`17-deployment.md` §2.3 第 2 項問的正是這個。）

⚠️ **注意 `neon.com/docs/introduction/plans` 對「儲存超標」的敘述與 FAQ 頁不完全相同**：plans 頁寫「Exceeding the 0.5 GB storage cap causes operations that increase storage (inserts, updates, and deletes) to fail」（寫入失敗），FAQ 頁寫「the project is suspended rather than billed」（專案暫停）。**兩頁措辭不一致，本文兩者並陳，不裁決哪一個是現行行為。**

### 3.2 Compute 大小上下限

<https://neon.com/docs/manage/computes>（2026-08-09）：

> Neon 支援的固定 compute 大小「**ranging from .25 CUs to 56 CUs**」；autoscaling「supports a range of **.25 CU to 16 CU**」。
> **「1 CU allocates approximately 4 GB of RAM」**（官方未給出每 CU 的 vCPU 數）。
> Free plan：「computes with **up to 2 CU (8 GB of RAM)**」。

**→ Free plan 的 compute 範圍是 0.25 CU（下限）到 2 CU（上限）。**

以此重算 `scheduling-and-db-sleep.md` §7.4 的試算（盤中 91.7 h/月）：

| compute 大小 | 月耗 CU-hours | 佔 100 CU-hours 額度 |
|---|---|---|
| 0.25 CU（Free 下限） | 22.9 | 23% |
| 1 CU | 91.7 | 92% |
| 2 CU（Free 上限） | 183.4 | **183% → 月中即用罄，compute 被 suspend** |

⚠️ **「新專案的預設 compute 大小是多少」官方文件未載明 → 未能查證。** 這個數字決定上表落在哪一列。

### 3.3 5 分鐘 scale-to-zero 是否免費層不可關閉 —— **是**

<https://neon.com/docs/introduction/plans>（2026-08-09）：Free plan 的 scale-to-zero 標示為 **"After 5 min"** 且 **"cannot disable"**。與 `scheduling-and-db-sleep.md` §4.2 記載一致，本次複驗無變動。

### 3.4 備份與 PITR 機制與保留期

<https://neon.com/docs/guides/backup-restore>、<https://neon.com/docs/introduction/plans>（2026-08-09）

Neon 的機制**不是傳統的定期 dump 備份**，而是「instant restore（即時還原到過去某個時間點）＋ snapshots」兩件事：

| 方案 | History window（可還原的時間窗） | 計費 | 手動 snapshot 數 |
|---|---|---|---|
| **Free** | **6 hours**，**capped at 1 GB-month of changes** | **No charge** | **1** |
| Launch | up to **7 days** | $0.20/GB-month | 100 |
| Scale | up to **30 days** | $0.20/GB-month | 100 |

**限制**：官方明列「Instant restore is **only supported for root branches**. Child branches do not support this feature.」

> **Free plan 的可還原時間窗只有 6 小時。** 對「持股與交易紀錄遺失不可接受」這條紅線（issue #17 body 原文）而言，這是一個具體的數字：**超過 6 小時前發生的誤刪，Neon Free 本身沒有任何機制可以還原。**

### 3.5 是否有東京（ap-northeast-1）區域 —— **沒有**

<https://neon.com/docs/introduction/regions>（2026-08-09），AWS 區域完整清單：

`aws-us-east-1`、`aws-us-east-2`、`aws-us-west-2`、`aws-eu-central-1`、`aws-eu-west-2`、**`aws-ap-southeast-1`（新加坡）**、`aws-ap-southeast-2`（雪梨）、`aws-sa-east-1`

**無 `aws-ap-northeast-1`（東京），亞洲只有新加坡。** Azure 區域「deprecated. You can no longer create new projects in Azure regions.」

⚠️ 同頁另一條與 Free plan 直接相關：「Projects on the Free plan that have been **inactive for 90 days or more are subject to deletion**」（該句出現在 Azure 區域段落，**是否為全域規則官方未明確界定 → 未能查證**）。

---

## 4. Supabase Free

### 4.1 Supavisor transaction mode 是否支援 `LISTEN/NOTIFY` —— **官方未載明**

查證了三個第一手頁面（2026-08-09），**三個頁面全文都沒有出現 `LISTEN` 或 `NOTIFY`**：

- <https://supabase.com/docs/guides/database/connecting-to-postgres>
- <https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI>
- <https://supabase.com/docs/guides/platform/ipv4-address>

官方對兩種模式的唯一功能性描述（Supavisor FAQ）：

> transaction mode：「In transaction mode, a client is allowed to **make a single query before being sent back to the figurative 'waiting room'**.」
> session mode：「In session mode, once the pooler assigns a direct connection, it **stays with that client until voluntarily surrendered**.」

官方對 transaction mode 唯一明列的不支援項目（connecting-to-postgres）：

> 「**Transaction mode does not support prepared statements.** To avoid errors, turn off prepared statements for your connection library.」

> **結論：Supabase 官方未載明 Supavisor transaction mode 是否支援 `LISTEN/NOTIFY`。** 本文不把「session mode 保持連線到 voluntarily surrendered」推論成「session mode 支援 `LISTEN/NOTIFY`」，也不把 PgBouncer 的一般原理推論成 Supabase 的事實。**這一項在 2026-08-06 與 2026-08-09 兩次查證後仍然是「官方未載明」。**

### 4.2 Direct connection 的 IPv4/IPv6 現況與費用 —— **有一條先前未被記錄的免費 IPv4 路徑**

<https://supabase.com/docs/guides/platform/ipv4-address>（2026-08-09），官方逐條列出三種連線方式的 IP 版本：

| 連線方式 | Port | 官方原文 |
|---|---|---|
| **Direct connection** | 5432 | 「**IPv6 unless IPv4 Add-On is enabled**」 |
| **Supavisor in transaction mode** | **6543** | 「**Always uses an IPv4 address**」 |
| **Supavisor in session mode** | **5432** | 「**Always uses an IPv4 address**」 |

以及：

> 「Supabase Postgres use IPv6 addresses **by default**. If your system doesn't support IPv6, you have the following options: **Supavisor Connection Strings: The Supavisor connection strings are IPv4-compatible alternatives to direct connections**；Supabase Client Libraries: These libraries are compatible with IPv4；**Dedicated IPv4 Add-On (Pro Plans+)**」

**IPv4 add-on 的價格**：該頁**未列價格**，只寫「refer to Manage IPv4 usage」，並明示僅 **"Pro Plans+"** 可用。`scheduling-and-db-sleep.md` §4.3 記載的 US$0.0055/小時 ≈ US$4/月 取自 <https://supabase.com/docs/guides/platform/manage-your-usage/ipv4>，本次**未重新複驗該價格頁**。

其他同頁事實：
- 「each database (including read replicas) receives an IPv4 address. **Each replica adds to the total IPv4 cost.**」
- 「actions like **pausing/unpausing the project** or enabling/disabling the add-on **can lead to a new IPv4 address**」
- 「**IPv4 addresses are guaranteed to be static for ingress traffic.** If your database is making outbound connections, the outbound IP address is not static and cannot be guaranteed.」

> 📌 **這修正了一個框架性的敘述。** [`17-deployment.md`](../briefing/17-deployment.md) §4.2 把「direct connection 走 IPv6，候選運算平台是否提供 IPv6 出站未逐一查證」列為 Supabase Free 的代價。事實是：**Supavisor 的兩種模式（含 session mode，port 5432）都「Always uses an IPv4 address」，且不需要付費 add-on。** 因此「IPv4 是隱形付費牆」這句話**只對 direct connection 成立，對 Supavisor session mode 不成立**。
>
> 但這**不等於問題解決**——因為「Supavisor session mode 是否支援 `LISTEN/NOTIFY`」正是 §4.1 那個官方未載明的空白。**免費的 IPv4 路徑存在，但那條路能不能跑 `LISTEN/NOTIFY` 仍然查不到答案。**

### 4.3 其他

<https://supabase.com/docs/guides/database/connecting-to-postgres>（2026-08-09）另列出一個先前未記載的選項：**Dedicated pooler（PgBouncer）transaction mode，port 6543**（與共用的 Supavisor 不同）。其方案限制與 `LISTEN/NOTIFY` 支援狀況**本次未查證**。

---

## 5. 各平台是否提供**硬性** spending cap

| 平台 | 有沒有硬性支出上限 | 官方依據（2026-08-09） |
|---|---|---|
| **Fly.io** | **❌ 兩者都沒有——連事後 billing alert 都沒有** | <https://fly.io/docs/about/cost-management/>：「**Free allowances don't cap your bill.** We may give you free credits and usage allowances... But **there's no soft ceiling. If you go over, we'll bill you. We don't support billing alerts (yet), so budget accordingly.**」官方給的替代做法是「look at what you've provisioned and do some quick math」與「**We recommend budgeting for the "always-on" cost.** You can get under that number with auto-stop or bursty usage, but **don't depend on it to hit your budget.**」 |
| **Render** | **⚠️ 有，但只涵蓋 build pipeline minutes，不是帳號總支出** | <https://render.com/docs/build-pipeline>：可「set a maximum amount to spend on **pipeline minutes** each month」；達上限時「Render stops running pipeline tasks (**including service builds!**) for the remainder of the current month」。**這是對 build 的硬性攔停，但對 instance/Postgres/cron 的經常性費用沒有任何上限機制。** |
| **Neon** | **⚠️ Free plan 是硬上限（但不是可設定的 cap）；付費層目前只有通知** | Free：<https://neon.com/faqs/free-plan-limits-and-quotas>「the project's compute is **suspended** until the next billing period」、「the project is **suspended rather than billed**」——**免費層在結構上就是硬上限，因為它根本不會產生帳單。**<br>付費層：<https://neon.com/docs/introduction/spending-limit>「Spending notifications are available on the **Launch and Scale** plans」；**目前只發信不攔停**——「**Projects continue to run, and charges continue to accumulate**, until you raise the threshold or the billing cycle resets」；官方標註「**Automatic project suspension is coming soon**: when the threshold is reached, projects' computes will pause」。檢查頻率「every 15 minutes」。<br>另有 API 層的 quota：<https://neon.com/docs/guides/consumption-limits> 可用 `quota` key 設定用量上限，達標時「all active computes for that project are automatically suspended」。 |
| **Supabase** | **⚠️ Spend Cap 是 Pro 專屬功能；Free plan 結構上不會產生費用** | <https://supabase.com/docs/guides/platform/spend-cap>：「The Spend Cap determines whether your organization can exceed your subscription plan's quota for any usage item.」「**This feature is available only with the Pro Plan. However, you will not be charged while using the Free Plan.**」Spend Cap 開啟時：「After exceeding the quota for a usage item, **further usage of that item is disallowed until the next billing cycle. You don't get charged for over-usage** but your services will be restricted according to our Fair Use Policy if you consistently exceed the quota.」 |

> **一句話的事實整理（非建議）**：本次查證的四家中，**沒有任何一家提供「對帳號總支出設一個上限、超過就自動停掉全部資源」的功能**。最接近的是 Neon 的 API quota（可 suspend 該 project 的 compute）與 Supabase Pro 的 Spend Cap（可停掉超額項目）；Render 的 spend limit 只管 build minutes；**Fly.io 官方明文連 billing alert 都還沒有。**

---

## 6. dead-man's switch（反向心跳）服務盤點

> 本節只盤點**免費層**，且只採信各家官方定價頁／官方文件。

| 服務 | 免費層 check/monitor 數 | 免費層價格 | **Discord** | 通用 webhook | 可自架 |
|---|---|---|---|---|---|
| **Healthchecks.io**（SaaS） | **20 jobs**（「Monitor **20 cron jobs** for free. No credit card required.」） | **$0/month**，另「100 log entries per job」 | **✅ 官方首頁整合清單明列 Discord** | ✅ Webhooks | ✅（見下列） |
| **Healthchecks**（自架） | 無上限（自己的機器） | 軟體本身 $0 | ✅ 同上 | ✅ | **✅ BSD 3-clause** |
| **Cronitor** | **5 monitors**（Hacker tier） | **$0** | **✅ 有官方 Discord 整合文件** | ✅ Webhooks | ❌（未見自架方案） |
| **Better Stack Uptime** | **10 monitors & heartbeats**（合計）、1 status page | **$0** | **⚠️ 官方整合清單未列 Discord** | ✅ Outgoing / Incoming webhooks | ❌ |

**細節與出處**：

- **Healthchecks.io 免費層**（<https://healthchecks.io/pricing/>，2026-08-09）：Hobbyist **$0/month**、「Monitor 20 jobs」、「100 log entries per job」。付費層：Supporter $5/月、Business $20/月、Business Plus $80/月。
- **Healthchecks.io 通知管道**（<https://healthchecks.io/>，2026-08-09 首頁整合清單）：Email、Webhooks、Slack、**Discord**、GitHub Issues、Google Chat、Gotify、Matrix、Mattermost、Microsoft Teams、ntfy、Opsgenie、PagerDuty、PagerTree、Phone Call、Prometheus、Pushbullet、Pushover、Rocket.Chat、Signal、SMS、Spike.sh、Telegram、Trello、Splunk On-Call、WhatsApp、Zulip。
- **Healthchecks 自架**（<https://healthchecks.io/docs/self_hosted/>，2026-08-09）：「Healthchecks is open-source, and is licensed under the **BSD 3-clause license**.」「As an alternative to using the hosted service at https://healthchecks.io, you have the option to host a Healthchecks instance yourself.」原始碼：<https://github.com/healthchecks/healthchecks>。**執行需求：Python 3.12+、Django 6.0、PostgreSQL 或 MySQL。**
  ⚠️ 自架本身就需要一台常駐機器 —— 這與「能中途停掉」的成本偏好之間的關係，本文不做評價。
- **Cronitor 免費層**（<https://cronitor.io/pricing>，2026-08-09）：Hacker tier 免費，含「5 monitors」、「1 included」dashboard user、「Email and Slack alerts」、「Webhooks」。付費 Business：monitors $2/月/個、額外 dashboard user $5/月。
  ⚠️ **定價頁的 Hacker tier 欄位只寫「Email and Slack alerts」＋「Webhooks」，未明列 Discord。** Discord 整合本身確實存在（<https://cronitor.io/docs/using-discord-with-cronitor>，設定路徑 Settings → Integrations → Create Integration → Discord，需 Webhook URL），但**「Discord 整合是否包含在免費 Hacker tier」官方定價頁未明確界定 → 未能查證**。（註：Discord 整合的機制就是 Discord Webhook URL，而免費層明列有 Webhooks——但這是推論，本文不當事實。）
- **Better Stack Uptime 免費層**（<https://betterstack.com/uptime/pricing>，2026-08-09）：「**10 monitors & heartbeats**, 1 status page」、「**Slack & e-mail alerts**」、$0/月。付費 Responder $34/月（年繳 $29/月）；額外 heartbeats $20/月（每 10 個）。
- **Better Stack 的 heartbeat 機制**（<https://betterstack.com/docs/uptime/cron-and-heartbeat-monitor/>，2026-08-09）：設定「Expect a heartbeat every」頻率與 grace period，排程結尾打 `curl https://uptime.betterstack.com/api/v1/heartbeat/<HEARTBEAT_TOKEN>`；逾期未收到即開 incident。可在 URL 後加 `/fail` 主動回報失敗。
- **Better Stack 整合清單**（<https://betterstack.com/docs/uptime/integrations/>，2026-08-09）：Slack、Microsoft Teams、On-call routing number、Email、Outgoing webhooks、Incoming webhooks，以及 Datadog / New Relic / Prometheus / Grafana / Zabbix / Intercom / AWS CloudWatch / Google Cloud / Jira / Zapier。**清單中未見 Discord。**

---

## 7. 免費子網域對 Caddy 自動 HTTPS 的相容性

### 7.1 Caddy 的自動 HTTPS 需要什麼（<https://caddyserver.com/docs/automatic-https>，2026-08-09）

| Challenge | 需求（官方原文） |
|---|---|
| **HTTP challenge（HTTP-01）** | 「requests a temporary cryptographic resource over port **80** using HTTP」、「**requires port `80` to be externally accessible**」 |
| **TLS-ALPN challenge** | 「requests a temporary cryptographic resource over port **443** using a TLS handshake」、「**requires port `443` to be externally accessible**」 |
| **DNS challenge（DNS-01）** | 「**does not require any open ports, and the server requesting a certificate does not need to be externally accessible**」 |

自動生效的條件（官方原文）：
> 「If your domain's **A/AAAA records point to your server**, ports `80` and `443` are open externally, Caddy can bind to those ports... then sites will be served over HTTPS automatically.」

需要 DNS-01 的時機（官方原文）：
> 「**Let's Encrypt requires the DNS challenge to obtain wildcard certificates**」；以及沒有對外開放的 80/443 時。

### 7.2 DuckDNS

<https://www.duckdns.org/spec.jsp>（2026-08-09）：

- 更新 API 可設定的記錄型別：**A（`ip` 參數）、AAAA（`ipv6` 參數）、TXT（`txt` 參數）**；另有 `verbose`、`clear` 參數。
- **官方規格未提供設定 CNAME 的方式。**
- **每帳號子網域數量上限：官方規格頁未載明 → 未能查證。**

**對 Caddy 的相容性（依上述兩頁的事實推導出的可行條件，非實測）**：

| 路徑 | 是否可行 | 依據 |
|---|---|---|
| **HTTP-01 / TLS-ALPN**（非 wildcard） | **條件成立即可行，不需要 DNS 外掛**——條件是能把 DuckDNS 的 **A 或 AAAA** 記錄指到伺服器的公開 IP，且 80／443 對外可達 | DuckDNS 支援 A/AAAA；Caddy 官方對 HTTP-01/TLS-ALPN 的要求只是「A/AAAA 指到你的 server + 80/443 對外開放」 |
| **DNS-01**（wildcard 或無開放埠時） | **可行，但需要為 Caddy 加裝 DuckDNS DNS 外掛**（標準 Caddy 不內含） | DuckDNS 支援 TXT 記錄；**`github.com/caddy-dns/duckdns` 已收錄在 Caddy 官方套件登錄檔**（<https://caddyserver.com/api/packages>，2026-08-09 實查回應中確認存在），可用官方下載頁或 `xcaddy` 建置 |
| **CNAME 到 PaaS 提供的主機名** | **不可行** | DuckDNS 官方規格未提供 CNAME |

⚠️ **這裡有一個對本專案具體的交互作用**：Fly.io 官方（<https://fly.io/docs/networking/custom-domain/>，2026-08-09）說「Use A and AAAA records for most direct connections to your app... If your app doesn't have IPv4 and IPv6 addresses, allocate them with `fly ips allocate`」，且「CNAME records... work well for subdomains」、「Setting CNAME records for the apex domain can be problematic」。DuckDNS 只給 A/AAAA，**這條路與 Fly 建議的 A/AAAA 做法方向一致**；但「Fly 的**共用** IPv4 是否能被指定為 A 記錄的目標、以及這樣是否能正常取得憑證」**官方文件未直接回答 → 未能查證**（專用 IPv4 為 $2/月，見 §1.4）。

### 7.3 Cloudflare —— **「Cloudflare 免費子網域」這個東西不存在**

<https://www.cloudflare.com/plans/>（2026-08-09）：

- Free plan 包含的項目為：「Fast, Easy-to-use **DNS**、Unmetered DDoS Protection、CDN、**Universal SSL Certificate**、Free Managed Ruleset、Web Application Firewall (WAF)、Role-based Account Control」。
- **Free plan 提供的是「幫你已經擁有的網域做 DNS 託管」，不是「送你一個子網域」。** 該頁**沒有任何**類似 DuckDNS 那種「在 Cloudflare 自有網域下配一個免費 hostname」的服務。
- Cloudflare Registrar 是**付費**的：「**At-cost domain registration with no markup pricing**」，起價 **$7.85**（頁面未標示計價週期，一般為年費 → **計價週期未能查證**）。

> 📌 **這推翻了 [`17-deployment.md`](../briefing/17-deployment.md) §7 的一項前提。** §7.1 與 §7.2 兩處都寫「免費子網域（DuckDNS／**Cloudflare 免費子網域**）」，把 Cloudflare 與 DuckDNS 並列為「免費子網域」的兩個選項。**Cloudflare 沒有這項服務。** 正確的敘述是：Cloudflare Free plan 提供的是**已擁有網域的免費 DNS 託管 + Universal SSL**，網域本身仍須付費取得（Cloudflare Registrar 起價 $7.85，at-cost）。

**若把 Cloudflare 理解為「自購網域 + Cloudflare 免費 DNS」**，則對 Caddy 的相容性為：

- HTTP-01 / TLS-ALPN：可行（Cloudflare DNS 可設任意 A/AAAA/CNAME）。⚠️ 但若開啟 Cloudflare 的 proxy（橘雲），流量會先經 Cloudflare，HTTP-01 與 TLS-ALPN 的行為會改變 —— **Cloudflare proxy 開啟時 Caddy 的 ACME challenge 行為，本次未查證。**
- DNS-01：可行，需 `github.com/caddy-dns/cloudflare` 外掛（**已確認收錄在 Caddy 官方套件登錄檔** <https://caddyserver.com/api/packages>，2026-08-09）。⚠️ 該外掛的設定選項本次**未能自 <https://caddyserver.com/docs/modules/dns.providers.cloudflare> 讀取**（該頁的模組明細為 JS 動態載入，與 §0 的兩個頁面不同，本次未破解）。

---

## 8. GitHub Actions `schedule` 的可靠度與免費額度（public repo）

### 8.1 可靠度（<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>，2026-08-09）

官方原文，逐條：

> **最小間隔**：「**The shortest interval you can run scheduled workflows is once every 5 minutes.**」
> **延遲**：「The `schedule` event **can be delayed during periods of high loads** of GitHub Actions workflow runs. **High load times include the start of every hour.**」
> **丟棄**：「**If the load is sufficiently high enough, some queued jobs may be dropped.**」
> **時區**：預設 UTC，可指定 IANA 時區字串。
> **分支**：「**Scheduled workflows will only run on the default branch.**」
> **⚠️ 60 天自動停用**：「**In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days.**」

> 📌 **最後一條是本次查證中對本專案最直接的新風險，兩份既有研究都沒有記載。**
> 本 repo 是 public。若盤後排程走 GitHub Actions `schedule`，而規格定案後有連續 60 天沒有 commit／issue 活動（一個「規格已寫完、系統穩定跑著」的專案完全可能如此），**GitHub 會自動停用該排程，而這不會產生任何一次「失敗的 run」**——它與 `scheduling-and-db-sleep.md` §8.1 描述的「沒跑」是同一種形狀的靜默失效，而且是可預期、有明確倒數的那一種。

### 8.2 免費額度（<https://docs.github.com/en/billing/concepts/product-billing/github-actions>，2026-08-09）

> 「GitHub Actions usage is **free** for **self-hosted runners** and for **public repositories** that use **standard GitHub-hosted runners**.」
> 「The use of standard GitHub-hosted runners is free: **In public repositories**」

- **public repo + 標準 runner ＝ 無分鐘數上限、免費。** 該頁的分鐘數表格只適用於 private repo。
- **larger runners 一律計費**，不論 repo 是否 public。
- ⚠️ **public repo 的併發（concurrency）上限官方該頁未載明 → 未能查證。**

---

## 9. 會推翻或需修正 `17-deployment.md` 既有敘述的發現

> **本節是本文最重要的一節。** 以下每一條都是「既有文件寫了 A，官方第一手來源顯示 B」。

| # | 位置 | 既有敘述 | 本次查證的事實 | 嚴重度 |
|---|---|---|---|---|
| **1** | §7.1、§7.2 | 「免費子網域（DuckDNS／**Cloudflare 免費子網域**）」，把 Cloudflare 當成免費子網域的提供者 | **Cloudflare 沒有免費子網域服務。** Free plan 提供的是已擁有網域的免費 DNS 託管；網域須自購（Cloudflare Registrar at-cost，起價 $7.85）。「先用免費子網域上線」這條路上，**DuckDNS 是唯一一個真的免費的選項**，不是兩個 | **推翻前提** |
| **2** | §1.2 選項 D、§1.1(f) | 「**750 小時上限對『一台 24/7』而言毫無餘裕**（一個月約 730 小時），若 `api` 意外被留在醒著狀態超過閾值會直接撞頂」 | 官方明文：「**spun-down services don't consume Free instance hours**」。本專案的 `api` 走 scale-to-zero，**大部分時間是 spun-down，不消耗額度**。750 小時對「一台 24/7」確實沒餘裕，但**對一台 scale-to-zero 的服務，這條風險的形狀完全不同**。既有敘述把它描述成一個近乎必然撞頂的限制，這與官方規則不符 | **需重寫** |
| **3** | §8.3 第 4 項；`scheduling-and-db-sleep.md` §5 表格、§9 第 9 項 | 「Render 是否有『按排程 suspend/resume 一個服務』的 API —— **未查證**」／「官方文件未提供按排程 suspend/resume 服務的做法 → 未能查證」 | **有。** `POST /v1/services/{serviceId}/suspend` 與 `POST /v1/services/{serviceId}/resume` 皆為官方 API。（仍未查證：是否適用於 Background Worker 型別） | **從「未能查證」改為「已查證：有」** |
| **4** | §2.3 第 2 項；`scheduling-and-db-sleep.md` §7.4、§9 第 10 項 | 「Neon Free plan 的 compute 大小上下限，以及 100 CU-hours 用罄後的行為（是否停機、降速、或直接失敗）—— 未查證」 | **兩項都查到了。** 大小：**0.25 CU 到 2 CU**。用罄行為：**「the project's compute is suspended until the next billing period」「Existing connections drop and new ones can't open」——是停機，不是降速** | **從「未能查證」改為「已查證」** |
| **5** | §4.2 Supabase Free 那一列 | 「direct connection 走 IPv6，**候選運算平台是否提供 IPv6 出站未逐一查證**」被列為 Supabase Free 的主要代價 | **Supavisor 的兩種模式（含 session mode，port 5432）官方明文「Always uses an IPv4 address」，且不需要付費 add-on。** IPv4 只對 **direct connection** 是付費牆。既有敘述把 IPv6 出站描述成使用 Supabase Free 的門檻，但**免費的 IPv4 路徑一直存在**——真正的未知仍然是那條路支不支援 `LISTEN/NOTIFY` | **需修正框架** |
| **6** | §1.3 第 1、2 項；`scheduling-and-db-sleep.md` §9 第 1、8 項 | 「Fly.io / Render 定價頁皆為 JS 動態載入，**未能自第一手定價頁讀取**，需人工複驗」 | **兩個頁面的價目表其實都在靜態 HTML 裡**（Fly 是全區域預渲染後用 CSS 藏；Render 是伺服器端渲染的 `<table>`）。本次已直接讀出。**nrt 官方係數 1.307692308、shared-cpu-1x 各規格 nrt 月費、Render 全部 instance 與 Postgres 月費**，皆已取得 | **從「未能查證」改為「已查證」** |
| **7** | §1.1(f) 的 NT$28 | 「Fly：`api` scale-to-zero + `worker` 只開盤中 + Neon Free（**東京 nrt 係數為推算**）≈ NT$28」 | **推算結果是對的，但現在有官方數字。** 以 nrt 官方費率重算：worker 512MB × 91.7h × $0.0058/h = **$0.532**；worker rootfs $0.15；api rootfs $0.15 → 合計 **≈ $0.83/月 ≈ NT$27**。與 NT$28 差 1 元，**結論方向不變** | **數字微調，結論不變** |
| **8** | 全文（新增，非推翻） | 未記載 GitHub Actions 對 public repo 的 60 天停用規則 | 「**In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days.**」對「規格寫完後系統自己跑著」的專案是一個可預期的靜默失效點，且不會產生任何失敗 run | **新增風險** |
| **9** | 全文（新增，非推翻） | 未記載 Neon Free 的公網傳輸額度 | Neon Free 另有 **5 GB public network transfer per project per month**，用罄的行為與 CU-hours 相同（**compute suspended**）。這是第二條會導致月中停機的額度 | **新增限制** |
| **10** | §2.2 選項二 | 「依平台原生機制設定 spending cap / billing alert —— 若平台有提供，可在接近上限時自動通知或攔停」 | **Fly.io 官方明文連 billing alert 都沒有**（「We don't support billing alerts (yet), so budget accordingly」）；Render 的 spend limit 只管 build pipeline minutes；Neon 付費層的 spending limit **目前只發信不攔停**（自動暫停標註為 "coming soon"）。**四家中沒有任何一家提供「帳號總支出硬上限」** | **需修正：此選項在 Fly 上不存在** |
| **11** | §1.1(c)、§4.1 | 「Fly.io 停機真的不計費」（未區分 volume） | 官方明文 volume **例外**：「You'll be charged for volumes that you create, whether they are attached to a Machine or not, **including when an attached Machine is stopped**」。若在 Fly Machine 上自架 Postgres，volume 費用與開關機無關 | **需補充例外** |
| **12** | §4.3 第 1 項 | 「Neon／Supabase／Fly MPG 各自的備份機制與 RPO/RTO —— 完全未查證」 | **Neon 已查到**：Free plan 為「instant restore，history window **6 hours**，capped at 1 GB-month」＋ **1 個手動 snapshot**；Launch 7 天、Scale 30 天。**Render Postgres 也已查到**：PITR 僅付費層，Hobby 3 天／Pro 以上 7 天，**Free 無 PITR、無 logical backup retention**。（Fly MPG、Supabase **仍未查證**） | **部分補上** |

---

## 10. 未能查證清單（誠實標註）

1. **Fly.io `suspended` 狀態的計費規則** — 官方定價頁全文只寫 `stopped`，未出現 `suspended` 的計費敘述。
2. **Fly Volume / rootfs / snapshot 價格是否隨區域變動** — 定價頁只在 Machine 價目表提供區域切換，volume 與 rootfs 只給單一數字，未說明是否套用 `regionMarkups`。
3. **Fly Managed Postgres 的備份保留期與 RPO/RTO** — <https://fly.io/docs/mpg/> 只寫 "Automatic backups and recovery"，無數字。
4. **Fly Managed Postgres 是否有 auto-suspend / scale-to-zero** — 官方文件仍完全未提及（2026-08-06 與 2026-08-09 兩次查證皆然）。
5. **Fly 的共用 IPv4 是否可作為 A 記錄目標並正常取得憑證** — 官方 custom domain 文件未直接回答。
6. **Render Cron Job 的最小排程間隔** — <https://render.com/docs/cronjobs> 全文未載明是否允許 `*/1`（2026-08-06 與 2026-08-09 兩次查證皆然）。
7. **Render suspend/resume API 適用於哪些 service type** — API 文件的 tag 為泛用的 "Services"，未明列 Background Worker 是否可用。
8. **Render 對 Free web service「uncommonly high volume of outbound traffic」的具體閾值** — 官方未定義。
9. **Neon 新專案的預設 compute 大小** — 官方文件未載明；這個數字決定 100 CU-hours 夠不夠用。
10. **Neon 儲存超標的實際行為** — `plans` 頁寫「寫入操作失敗」，`FAQ` 頁寫「專案被 suspend」，**兩份官方文件措辭不一致**，本文不裁決。
11. **Neon Free「閒置 90 天可能被刪除」是否為全域規則** — 該句出現在 Azure 已棄用區域的段落，適用範圍未明確界定。
12. **Supabase Supavisor（session 或 transaction mode）是否支援 `LISTEN/NOTIFY`** — 三個第一手頁面全文皆未出現 `LISTEN`／`NOTIFY`。**這是本專案最關鍵、且連續兩次查證都查不到的一項。**
13. **Supabase Dedicated pooler（PgBouncer, port 6543）的方案限制與 `LISTEN/NOTIFY` 支援** — 本次未展開查證。
14. **Supabase IPv4 add-on 的現行價格** — <https://supabase.com/docs/guides/platform/ipv4-address> 未列價，本次未複驗價格頁；沿用 2026-08-06 記載的 US$0.0055/小時 ≈ US$4/月。
15. **Supabase 的備份機制與保留期** — 本次未查證。
16. **Cronitor 免費 Hacker tier 是否包含 Discord 整合** — 定價頁該欄只列「Email and Slack alerts」與「Webhooks」，未明列 Discord。
17. **DuckDNS 每帳號的子網域數量上限** — 官方規格頁未載明。
18. **Cloudflare proxy（橘雲）開啟時 Caddy 的 ACME challenge 行為** — 未查證。
19. **`caddy-dns/cloudflare` 外掛的設定選項** — <https://caddyserver.com/docs/modules/dns.providers.cloudflare> 的模組明細為 JS 動態載入，本次未取得；僅確認該套件存在於 Caddy 官方套件登錄檔。
20. **Cloudflare Registrar $7.85 的計價週期** — 定價頁未標示（一般為年費，但本文不推論）。
21. **GitHub Actions 對 public repo 的併發（concurrency）上限** — 計費文件未載明。
22. **匯率時效** — 1 USD = 32.315 TWD 沿用 2026-08-05 牌告，本次**未取得 2026-08-09 的當日牌告**。
23. **各節點對台灣的實測 RTT** — 本次仍未實測（#5、`scheduling-and-db-sleep.md` 亦皆未實測）。
24. **`api` scale-to-zero 冷啟動延遲、以及跨服務 RTT**（#16 移交的兩項） — **本次授權範圍不含實測**，維持未能查證。

---

## 11. 來源清單（皆為第一手官方頁面／官方 API，2026-08-09 查證）

**Fly.io**
- 定價（含 `regionMarkups` 常數與各區預渲染價目表）：<https://fly.io/docs/about/pricing/>
- 成本管理（明文無 billing alert、無 spending cap）：<https://fly.io/docs/about/cost-management/>
- Managed Postgres 總覽與定價：<https://fly.io/docs/mpg/>
- 自訂網域 DNS 設定：<https://fly.io/docs/networking/custom-domain/>

**Render**
- 定價（伺服器端渲染的價目表）：<https://render.com/pricing>
- Free tier（750 小時、spin down、suspend 行為）：<https://render.com/docs/free>
- Cron Jobs：<https://render.com/docs/cronjobs>
- Instance types（含 cron job 無 Free 檔位）：<https://render.com/docs/compute-plans>
- Postgres 方案與 PITR 保留期：<https://render.com/docs/postgresql-refresh>
- Build pipeline（spend limit 僅涵蓋 pipeline minutes）：<https://render.com/docs/build-pipeline>
- 區域：<https://render.com/docs/regions>
- API 總覽：<https://render.com/docs/api>
- Suspend service：<https://api-docs.render.com/reference/suspend-service-1>
- Resume service：<https://api-docs.render.com/reference/resume-service-1>

**Neon**
- 方案總表（Free 各項額度、scale-to-zero "cannot disable"、history window）：<https://neon.com/docs/introduction/plans>
- Free plan 限制與配額 FAQ（用罄後 suspend 的明文）：<https://neon.com/faqs/free-plan-limits-and-quotas>
- Compute 大小（.25–56 CU、1 CU ≈ 4 GB RAM、Free 上限 2 CU）：<https://neon.com/docs/manage/computes>
- 備份與還原：<https://neon.com/docs/guides/backup-restore>
- 區域清單（無東京）：<https://neon.com/docs/introduction/regions>
- Spending limit（Launch/Scale、目前僅通知）：<https://neon.com/docs/introduction/spending-limit>
- Consumption limits（API quota）：<https://neon.com/docs/guides/consumption-limits>

**Supabase**
- 連線方式與 port：<https://supabase.com/docs/guides/database/connecting-to-postgres>
- Supavisor FAQ（session／transaction 模式定義）：<https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI>
- IPv4 add-on（Supavisor 兩模式皆為 IPv4 的明文）：<https://supabase.com/docs/guides/platform/ipv4-address>
- Spend Cap：<https://supabase.com/docs/guides/platform/spend-cap>

**反向心跳／監控服務**
- Healthchecks.io 定價：<https://healthchecks.io/pricing/>
- Healthchecks.io 首頁（整合清單，含 Discord）：<https://healthchecks.io/>
- Healthchecks 自架與授權（BSD 3-clause）：<https://healthchecks.io/docs/self_hosted/>
- Healthchecks 原始碼：<https://github.com/healthchecks/healthchecks>
- Cronitor 定價：<https://cronitor.io/pricing>
- Cronitor Discord 整合：<https://cronitor.io/docs/using-discord-with-cronitor>
- Better Stack Uptime 定價：<https://betterstack.com/uptime/pricing>
- Better Stack cron / heartbeat monitor：<https://betterstack.com/docs/uptime/cron-and-heartbeat-monitor/>
- Better Stack 整合清單：<https://betterstack.com/docs/uptime/integrations/>

**網域與 HTTPS**
- Caddy 自動 HTTPS（challenge 與 port 需求）：<https://caddyserver.com/docs/automatic-https>
- Caddy 官方套件登錄檔（確認 `caddy-dns/duckdns`、`caddy-dns/cloudflare` 收錄）：`https://caddyserver.com/api/packages`
- DuckDNS API 規格：<https://www.duckdns.org/spec.jsp>
- Cloudflare 方案：<https://www.cloudflare.com/plans/>

**GitHub**
- Actions `schedule` 事件（5 分鐘下限、延遲與丟棄、public repo 60 天停用）：<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows>
- Actions 計費（public repo + 標準 runner 免費）：<https://docs.github.com/en/billing/concepts/product-billing/github-actions>

**匯率**
- 中央銀行新臺幣對美元收盤匯率：<https://www.cbc.gov.tw/tw/lp-645-1.html>（**沿用 2026-08-05 牌告，本次未重取**）

**專案內既有文件（複驗對象）**
- [`docs/research/persistent-websocket-hosting.md`](./persistent-websocket-hosting.md)（#5，2026-08-01）
- [`docs/research/scheduling-and-db-sleep.md`](./scheduling-and-db-sleep.md)（#17 前置研究，2026-08-05~06）
- [`docs/briefing/17-deployment.md`](../briefing/17-deployment.md)（#17 上桌前準備，2026-08-08）
