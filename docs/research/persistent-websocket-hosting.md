# 常駐 WebSocket 後端的雲端部署選項與成本

> 對應 issue：[#5](https://github.com/NTUyu016/stock-analytic-platform/issues/5)（parent: #1）
> 查證日期：**2026-08-01**
> 匯率：**1 USD = 32.292 TWD**（中華民國中央銀行公布之新臺幣對美元銀行間成交收盤匯率，2026-07-31，來源：<https://www.cbc.gov.tw/tw/lp-645-1.html>）
> 所有價格均取自各平台**官方定價頁或官方文件**，並以「1 個實例 24/7 常駐、730 小時/月」為基準實算，非行銷用的「起價」數字。

---

## 0. 這個工作負載的關鍵特徵（先釐清，才不會選錯架構）

台股行情後端的真實形狀是：

1. **它是 WebSocket 的 _client_，不是 server。** 程式主動撥出去連券商/資料商的行情 WS，然後在盤中（09:00–13:30）持續收 tick。
2. 因此它**不需要對外的 HTTP 入口**，也不需要 Load Balancer。
3. 它必須**能在沒有任何 inbound request 的情況下持續執行**。

這一點直接淘汰了一整類「request-driven」的 serverless 產品，也讓「inbound WebSocket 逾時上限」這件事在自用階段其實**不適用**（那是給 WS server 用的限制）。真正致命的限制是「**沒有 request 就會被 scale to zero / 凍結 CPU**」。

未來若要「上架」，才會多出一個對外的 API/前端服務，那時 inbound WS 逾時與 LB 成本才變成議題。本文兩種情境分開評估。

---

## 1. 平台總表

| 平台 | WebSocket / 長連線 | 常駐月費（實算） | 冷啟動 / 縮到零 | 對台灣最近的節點 | 託管 PostgreSQL | 排程機制 | Secret 管理 | Python/Node 差異 |
|---|---|---|---|---|---|---|---|---|
| **Google Cloud Run — Worker Pool** | 無 HTTP endpoint，純背景常駐，**不受 request timeout 限制**；適合當 WS client | **US$25.95 ≈ NT$838**（1 vCPU + 512 MiB，asia-east1，已扣免費額度） | 手動指定 instance 數，**不會 scale to zero**（也不支援 autoscaling） | **asia-east1＝台灣**（Tier 1 定價） | Cloud SQL（本次未查證價格）／建議外接 Neon | Cloud Scheduler：3 個 job 免費，之後 US$0.10/job/月 | Secret Manager：前 6 個 active version 免費，之後 US$0.06/version/月；access 前 1 萬次免費，之後 US$0.03/萬次 | 容器化，語言無差別 |
| **Google Cloud Run — Service（instance-based billing）** | 原生支援 inbound WS，但**受 request timeout 上限 60 分鐘**，且會因負載平衡被導到不同 instance | **US$44.71 ≈ NT$1,444**（1 vCPU + 512 MiB，min=1） | min-instances 可保溫，但官方明言只是 **best-effort**，不保證永遠有實例 | asia-east1＝台灣 | 同上 | 同上 | 同上 | 容器化，語言無差別 |
| **Google Cloud Run — Service（request-based billing）** | 同上；且**連線開著的整段時間都算 active**，最貴 | **US$61.14 ≈ NT$1,974** | 可縮到零，但縮到零＝行情斷線，**不可行** | asia-east1＝台灣 | 同上 | 同上 | 同上 | 同上 |
| **Fly.io** | Machine 是完整 VM，無平台層連線逾時 | **US$4.18 ≈ NT$135**（shared-cpu-1x/512MB，nrt 東京）<br>**US$7.45 ≈ NT$241**（1GB）<br>**US$14.90 ≈ NT$481**（shared-cpu-2x/2GB） | 預設 `auto_stop_machines="stop"`，**必須關掉**否則會被停機；停機/suspend 期間不計 CPU/RAM | **nrt 東京**、sin 新加坡（無台灣、無香港、無首爾） | Managed Postgres：Basic（shared-2x/1GB）**US$38 ≈ NT$1,227**、Starter（shared-2x/2GB）US$72；storage US$0.28/GB/月；東京有節點 | **未能查證**官方 cron 產品；實務上在 Machine 內跑排程或用外部觸發 | `fly secrets set`，vault 加密儲存，開機時注入為環境變數；API server 只能加密不能解密 | Dockerfile 為主，語言無差別 |
| **Railway** | 服務即長駐容器，無平台層連線逾時 | 依**實際用量**計費：CPU US$0.0278/vCPU-h、RAM US$0.013896/GB-h。<br>滿載 1 vCPU + 1 GB 24/7＝**US$30.44 ≈ NT$983**；低負載（均 0.1 vCPU + 0.5 GB）＝**US$7.10 ≈ NT$229**。Hobby 方案 US$5/月含 US$5 額度 | 服務常駐，不會自動縮到零 | **僅新加坡**（`asia-southeast1-eqsg3a`），無東京 | 用同一組 usage rate 計費（無獨立方案表） | **內建 cron**，最短間隔 5 分鐘；跑完必須 exit，前次未結束會跳過 | 服務變數／共用變數，支援 `${{NAMESPACE.VAR}}` 引用 | Railpack/Nixpacks 或 Dockerfile，Python/Node 皆支援 |
| **Zeabur** | 依附於你自己的 server，無平台層限制 | **方案費**：Free US$0、Dev US$5、Pro US$19、Team US$79/3 seats。<br>**運算費另計**：2026 年起 Shared Cluster 已**停用**，改成 BYOS／向 Zeabur 買機器，實際機器月費需登入 dashboard 才看得到 → **未能查證具體數字** | Free 方案**閒置自動休眠**，喚醒有數秒冷啟動 → 盤中接行情不可用；Dev 以上才可 24/7 | BYOS：機器你自己挑（合作 AWS/GCP/Hetzner/Linode/DO/阿里/騰訊/火山），理論上可放東京 | 以 template 部署在自己 server 上 | 官方文件導覽**未列** cron/排程專章 → 未能查證 | 服務環境變數（`/docs/deploy/config/environment-variables`） | 官方文件列有 Django/Flask/Reflex 與 Node 全家桶 |
| **Render** | 付費 instance 常駐；**Free instance 15 分鐘無流量即 spin down**，重啟約 1 分鐘，每月 750 free hours | Starter（0.5 CPU / 512 MB）**US$7 ≈ NT$226**<br>Standard（1 CPU / 2 GB）**US$25 ≈ NT$807**<br>Workspace：Hobby US$0 / Pro US$25 | 付費 instance 不縮到零；Free 會縮 → 不可用 | **僅新加坡**（其餘為 Oregon / Ohio / Virginia / Frankfurt） | Render Postgres：Basic-256mb **US$6**、Basic-1gb **US$19**、Pro-4gb **US$55**；擴充儲存 US$0.30/GB | **內建 Cron Job**，按秒計費，**每個 job 每月最低 US$1**；單次執行上限 12 小時 | 環境變數（本次未逐項查證 Secret Files 細節） | 官方明列原生支援 Node、Python、Go、Rust、Ruby、Elixir，另可用 Docker |
| **AWS App Runner** | — | — | — | — | — | — | — | ⚠️ **官方公告：App Runner 已不對新客戶開放**（existing customers 才能續用，AWS 亦明言不再新增功能）。**新專案不可選。** AWS 建議改用 ECS Express Mode |
| **AWS ECS on Fargate（東京 ap-northeast-1）** | Task 為長駐容器，無平台層連線逾時 | Linux/x86：vCPU US$0.05056/h、RAM US$0.00553/h<br>→ 0.25 vCPU + 0.5 GB＝**US$11.25 ≈ NT$363**<br>→ 0.5 vCPU + 1 GB＝**US$22.50 ≈ NT$727**<br>ARM/Graviton：US$0.04045/h + US$0.00442/h → 0.25 vCPU + 0.5 GB＝**US$8.99 ≈ NT$290**<br>＋公網 IPv4 US$0.005/h＝**US$3.65 ≈ NT$118/月** | desired count 固定，不縮到零 | **ap-northeast-1 東京** | RDS（本次未查證價格） | EventBridge Scheduler 觸發 ECS Task（本次未查證價格） | Secrets Manager / SSM Parameter Store（本次未查證價格） | 容器化，語言無差別 |
| **AWS ECS Express Mode** | 同上，但**會自動幫你開一台 ALB** | Fargate 費用＋ALB **US$0.0243/h＝US$17.74 ≈ NT$573/月**＋LCU US$0.008/LCU-h | 同上 | 東京 | 同上 | 同上 | 同上 | 同上 |
| **VPS：Akamai / Linode（東京、大阪）** | 完整 VM，無任何限制 | Nanode 1GB（1 vCPU / 1 GB / 25 GB / 1 TB 流量）**US$5 ≈ NT$162**<br>Linode 2GB（1 vCPU / 2 GB / 50 GB / 2 TB）**US$12 ≈ NT$387**<br>Linode 4GB（2 vCPU / 4 GB）**US$24** | 無冷啟動 | **ap-northeast（Tokyo 2）、jp-tyo-3（Tokyo 3）、jp-osa（大阪）**；另有 ap-south / sg-sin-2（新加坡）。API 回傳中 Tokyo **無區域加價** | 自架（US$0）或外接 | `cron` / `systemd timer`（US$0） | 自行管理（.env + 權限、systemd `EnvironmentFile`） | 完全自由 |
| **VPS：Vultr（東京、大阪、首爾）** | 完整 VM，無任何限制 | Regular Cloud Compute：1 vCPU/1 GB **US$5 ≈ NT$162**、1 vCPU/2 GB **US$10 ≈ NT$323**、2 vCPU/4 GB **US$20**<br>High Frequency：1 vCPU/2 GB **US$12 ≈ NT$387**<br>High Performance：1 vCPU/2 GB **US$12** | 無冷啟動 | **nrt 東京、itm 大阪、icn 首爾、sgp 新加坡**（API 確認上述機種在 nrt/itm 皆供應） | 自架或外接 | cron（US$0） | 自行管理 | 完全自由 |
| **VPS：DigitalOcean** | 完整 VM，無任何限制 | Basic：1 vCPU/1 GB **US$6 ≈ NT$194**、1 vCPU/2 GB **US$12**、2 vCPU/4 GB **US$24** | 無冷啟動 | ⚠️ **亞洲只有 Singapore 與 Bangalore，沒有東京、沒有台灣** → 對台灣延遲劣於 Linode/Vultr | Managed Postgres（本次未查證價格） | cron（US$0） | 自行管理 | 完全自由 |

---

## 2. 逐項細節

### 2.1 WebSocket / 長連線支援

- **Cloud Run Service**：官方文件明確支援 WebSocket，但「WebSocket 串流就是 HTTP request」，因此受 request timeout 管制，**上限 60 分鐘**（預設 5 分鐘）。官方同時提醒：即使開了 session affinity 也只是 best-effort，client 仍可能被導到不同 instance，需自備 reconnect 邏輯。
- **Cloud Run Worker Pool**：官方定位為「continuous background work」，**沒有 load-balanced endpoint、不支援 autoscaling、採手動指定 instance 數**。這正好是行情接收器要的形狀，而且完全繞開 60 分鐘 timeout。
- **Fly.io / Railway / Render 付費 instance / ECS Fargate / VPS**：都是長駐 process，平台不會主動掐斷你**主動撥出**的連線。
- **Render Free instance**：官方文件說明「15 分鐘沒有 inbound traffic 就 spin down」，而且**既有 WebSocket 連線上的訊息也算 traffic**——理論上行情不斷就不會休眠，但每月 750 free hours 的上限（一台 24/7 需要約 730 小時，只夠一台且毫無餘裕）與缺乏 SLA，使它不適合當正式的盤中接收器。
- **Zeabur Free**：官方明示「閒置自動休眠、喚醒有數秒冷啟動」→ 不可用。

### 2.2 常駐成本（計算過程）

以 730 小時／月＝2,628,000 秒計。

**Cloud Run Worker Pool（asia-east1，Tier 1，1 vCPU + 512 MiB）**
```
CPU : 2,628,000 vCPU-s × $0.000011244 = $29.55
RAM : 1,314,000 GiB-s × $0.000001235 = $ 1.62
小計                                   = $31.17
免費額度：384,204 vCPU-s (=$4.32) + 728,744 GiB-s (=$0.90)
實付                                   = $25.95/月 ≈ NT$838
```

**Cloud Run Service（instance-based billing，min=1，1 vCPU + 512 MiB）**
```
CPU : 2,628,000 × $0.000018  = $47.30
RAM : 1,314,000 × $0.000002  = $ 2.63
免費：240,000 vCPU-s + 450,000 GiB-s = -$5.22
實付                          = $44.71/月 ≈ NT$1,444
```
> 注意：官方文件明言「instance-based billing 即使 min instances 設為 0，仍以標準費率計費整個生命週期」。

**Cloud Run Service（request-based billing）** —— WS 連線期間全部算 active time：
```
CPU active : 2,628,000 × $0.000024  = $63.07
RAM active : 1,314,000 × $0.0000025 = $ 3.29
免費：180,000 vCPU-s + 360,000 GiB-s = -$5.22
實付                                  = $61.14/月 ≈ NT$1,974
```
idle 費率雖低（CPU/RAM 皆 $0.0000025/秒），但**只在沒有 in-flight request 時適用**；長連線讓它幾乎永遠是 active，所以 request-based 是三者中最貴的，**不要用**。

**Railway（Singapore）**
```
CPU $0.00000772/vCPU-s = $0.0277920/vCPU-h
RAM $0.00000386/GB-s   = $0.0138960/GB-h

滿載 1 vCPU + 1 GB × 730h = $20.29 + $10.15 = $30.44/月 ≈ NT$983
低負載 0.1 vCPU + 0.5 GB  = $ 2.03 + $ 5.07 = $ 7.10/月 ≈ NT$229
```
Railway 是**按實測用量**計費而非按配額，一個大多數時間在等 tick 的 WS client CPU 用量極低，所以真實帳單會接近下面那個數字。但這也代表**帳單不可預測**——盤中忙、盤後閒，需要用 Project Budget 設上限。Hobby 方案 US$5/月已含 US$5 額度。

**AWS Fargate 東京**
```
x86 : 0.25 vCPU×730×$0.05056 + 0.5 GB×730×$0.00553 = $9.23 + $2.02 = $11.25/月
ARM : 0.25 vCPU×730×$0.04045 + 0.5 GB×730×$0.00442 = $7.38 + $1.61 = $ 8.99/月
公網 IPv4（若 task 放 public subnet）: 730×$0.005 = $3.65/月
```
Fargate 最小規格是 0.25 vCPU / 0.5 GB，對純 WS client 夠用；但 AWS 的隱藏成本（NAT Gateway 或 public IPv4、CloudWatch Logs、ECR）會讓實際帳單高於運算費本身。

### 2.3 冷啟動與「縮到零」

**結論：對盤中持續接行情而言，縮到零＝功能失效，不是省錢手段。**

- 縮到零之後沒有任何 inbound request 可以把它叫醒——因為喚醒它的事件（行情 tick）來自一條**已經被切斷**的外撥連線。
- 唯一可行的「省錢」是**按台股交易日與時段開關機**：09:00 前開、13:35 後關，一天約 5 小時，一週 5 天 ≈ 每月 110 小時，約為 24/7 的 15%。
  - Fly.io 特別適合這招：停機的 Machine **不計 CPU/RAM**，只付 rootfs（US$0.15/GB per 30 days）。用 `fly machine start/stop` 排程可把 shared-cpu-1x/1GB 從 US$7.45 壓到 US$1.2 左右。
  - Cloud Run Worker Pool 手動改 instance count 為 0/1 也可比照。
  - VPS 則無此彈性（按月計費），但 VPS 本來就只要 US$5。
- Cloud Run Service 的 min-instances 官方僅承諾 **best-effort**（會因基礎架構 rebalancing、崩潰、配額、區域容量而低於設定值），所以就算付了保溫錢，**仍需自備 reconnect 與健康檢查**。

### 2.4 對台灣的網路延遲與節點位置

| 平台 | 最近節點 |
|---|---|
| Google Cloud Run | **asia-east1 = 台灣**（且屬 Tier 1 定價，與 us-central1 同價）；asia-northeast1 = 東京亦為 Tier 1 |
| Fly.io | nrt 東京 |
| AWS Fargate | ap-northeast-1 東京 |
| Linode / Akamai | Tokyo 2、Tokyo 3、大阪（東京無區域加價） |
| Vultr | 東京 nrt、大阪 itm、首爾 icn |
| Railway | **僅新加坡** |
| Render | **僅新加坡** |
| DigitalOcean | **僅新加坡 / 邦加羅爾**（無日本節點） |
| Zeabur | BYOS，取決於你買哪家的機器 |

> **只有 Google Cloud 有台灣境內節點（asia-east1，彰化）。** 這是 GCP 在此題唯一的、但相當實質的優勢：行情源（台灣券商/資料商）與運算節點同在台灣，是延遲最短的組合。
> 其次是東京/大阪（Fly.io、AWS、Linode、Vultr）；新加坡（Railway、Render、DO）在地理上明顯較遠。
> ⚠️ 本文**未實測 RTT**，不提供具體毫秒數字；上線前建議自行從目標節點 ping 行情端點驗證。

### 2.5 資料庫

| 選項 | 價格 | 節點 | 備註 |
|---|---|---|---|
| **自架 Postgres 在 VPS 上** | **US$0**（共用同一台 VPS） | 同 VPS | 自用階段最划算；需自己做備份 |
| Neon（Launch） | 運算 US$0.106/CU-hour、儲存 US$0.35/GB/月；Free 方案每 project 100 CU-hours + 0.5 GB | **僅新加坡 `aws-ap-southeast-1`（無東京）** | 閒置 scale-to-zero＝US$0，很適合「盤後才查」的分析型讀取 |
| Supabase | Free US$0（**閒置 1 週自動暫停**、每組織上限 2 個 active project）；Pro **US$25/月**（含 US$10 compute credit＝1 台 Micro：2-core ARM/1 GB RAM、8 GB disk、250 GB egress）；Small US$15、Medium US$60 | 官方定價頁未列區域 → **未能查證** | Free 的自動暫停對「每天盤後寫入」的節奏是可以接受的，但不保證 |
| Render Postgres | Basic-256mb **US$6**、Basic-1gb **US$19**、Basic-4gb US$75、Pro-4gb US$55；擴充儲存 US$0.30/GB | 新加坡 | 只有選 Render 部署時才划算 |
| Fly Managed Postgres | Basic（shared-2x/1GB）**US$38**、Starter（shared-2x/2GB）US$72；儲存 US$0.28/GB/月 | **東京有** | 內含 HA/備份/連線池，但對自用而言 **US$38 太貴**，不如在 Fly Machine 上自架或外接 Neon |
| Cloud SQL / RDS | **未查證** | — | — |

**建議**：自用階段直接在同一台機器上自架 Postgres（US$0），每日 `pg_dump` 到物件儲存。上架階段再視需要換成 Neon（新加坡）或 Fly Managed Postgres（東京）。

### 2.6 排程任務（盤後批次、每日快照）

| 平台 | 機制 | 費用 |
|---|---|---|
| VPS | `cron` / `systemd timer` | US$0 |
| Railway | **內建 cron**（Settings → Cron Schedule），最短間隔 **5 分鐘**；服務必須跑完就 exit，前次未結束會直接跳過本次 | 按執行秒數計 usage |
| Render | **內建 Cron Job** 服務，按秒計費，**每個 job 每月最低 US$1**；單次執行上限 12 小時；保證同一 job 同時只有一個 run；**不能掛 persistent disk** | Starter US$0.00016/分鐘，月最低 US$1 |
| Cloud Run | Cloud Run Jobs ＋ **Cloud Scheduler**（每月 **3 個 job 免費**，之後 **US$0.10/job/月**）。Jobs 費率同 Service instance-based：CPU US$0.000018/vCPU-s、RAM US$0.000002/GiB-s，另有 240,000 vCPU-s + 450,000 GiB-s 免費額度 | 幾乎免費（盤後批次每天跑幾分鐘） |
| Fly.io | 官方 cron 產品 **未能查證**；實務做法是在 Machine 內跑 crond，或用外部觸發（GitHub Actions / Cloud Scheduler）打 API | — |
| AWS | EventBridge Scheduler → ECS RunTask（價格本次未查證） | — |

> 跨平台通用的省錢做法：**用 GitHub Actions 的 `schedule` 觸發**盤後批次，運算費用歸零（public repo 免費），代價是排程觸發時間不精準。

### 2.7 機密（secret）管理

- **Fly.io**：`fly secrets set`。官方說明 secret 加密後存在 vault，**API server 只能加密不能解密**，值永不進 log；Machine 開機時由 agent 解密注入為環境變數，Machine 銷毀後 host 即失去存取權。build-time 需另用 build secrets。**這是本次比較中機制描述最完整的一家。**
- **Cloud Run**：Secret Manager 掛載為環境變數或檔案。前 6 個 active secret version 免費，之後 **US$0.06/version/月**；access 前 10,000 次/月免費，之後 US$0.03/萬次。以本專案的規模（券商 API key、DB 密碼、幾把 token）**幾乎必然落在免費額度內**。
- **Railway**：服務變數 + 共用變數，支援 `${{NAMESPACE.VAR}}` 跨服務引用；官方 reference 頁**未載明**加密細節與 sealed variable → 該部分未能查證。
- **Render**：環境變數（Env Groups / Secret Files 之細節本次未逐項查證）。
- **Zeabur**：`/docs/deploy/config/environment-variables`。
- **VPS**：完全自理。建議 `systemd` unit 的 `EnvironmentFile=` 指向 `chmod 600` 的檔案，或用 `sops`/`age` 加密進 repo。
- ⚠️ 本 repo 為 public，**任何情況下都不要把金鑰、憑證檔（如券商 CA `.pfx`）commit 進 git**。券商憑證應以 base64 放進平台 secret，開機時寫到容器內的 tmpfs。

### 2.8 Python 與 Node 的支援差異

實測結論：**在本題的候選平台中，Python 不會讓任何一家變得不划算。**

- Fly.io、Cloud Run、ECS Fargate 都以 **Dockerfile / 容器映像**為主要交付單位，語言完全無差別。
- Render 官方定價頁明列原生支援 **Node、Python、Go、Rust、Ruby、Elixir**，另可用 Docker。
- Railway 以 Railpack/Nixpacks 自動偵測，Python 與 Node 皆為一級公民；亦可用 Dockerfile。
- Zeabur 官方框架文件同時列有 Django / Flask / Reflex 與整套 Node 生態。
- 已停止收新客的 AWS App Runner 才有「managed runtime 版本綁定」的問題，但它已不可選。

**真正會影響部署選擇的，不是 Python vs Node，而是 SDK 的 OS 與連線模型：**

- **富果 Fugle Market Data**：官方同時提供 **Node.js SDK（`fugle-marketdata-node`）與 Python SDK（`fugle-marketdata-python`）**，並提供 WebSocket 即時行情 API。語言選擇自由。
- **永豐 Shioaji**：官方首頁標榜 cross-language / cross-platform，提供 Python、HTTP API、CLI 三種介面，安裝說明涵蓋 **Linux / macOS / Windows**；官方未提供 Docker image（需自行寫 Dockerfile）。憑證設定另有「Token & Certificate」專章。
- ⚠️ **若最終選用的是以 Windows COM 元件形式發布的券商 API（部分台灣券商如此），則本文所有 Linux 容器平台全部不適用**，必須改用 Windows VM。這件事應在選 SDK 時就先確認，是本題最大的架構分岔點。本文未逐一查證各家券商 API 的 OS 需求。

---

## 3. 推薦方案

### 情境 A：自用階段（單人、成本敏感、只有自己會用）

**首選：Vultr 或 Linode 東京 VPS，1 vCPU / 1 GB — US$5/月 ≈ NT$162**

| 項目 | 選擇 | 月費 |
|---|---|---|
| 運算 | Vultr `vc2-1c-1gb`（東京 nrt）或 Linode Nanode 1GB（Tokyo） | US$5.00 |
| 資料庫 | 同機自架 PostgreSQL | US$0 |
| 排程 | systemd timer / cron | US$0 |
| Secret | systemd `EnvironmentFile`（chmod 600） | US$0 |
| 備份 | `pg_dump` → 物件儲存（Cloudflare R2 免費額度內） | US$0 |
| **合計** | | **US$5.00 ≈ NT$162/月** |

理由：無冷啟動、無連線逾時、無平台限制、帳單固定可預測、東京節點對台灣延遲可接受。1 GB RAM 對「一個 WS client + Postgres + 排程」是夠的（若嫌緊，升到 2 GB＝Vultr US$10 / Linode US$12）。代價是要自己維護 OS 更新。

**次選（不想碰 OS 維運）：Fly.io 東京 — US$7.45/月 ≈ NT$241**

`shared-cpu-1x / 1GB @ nrt` US$7.45，加上 `fly secrets` 的 secret 管理與 `fly deploy` 的部署流程。DB 一樣在同一台 Machine 上自架（配一顆 10 GB volume：US$1.50/月），總計 **US$8.95 ≈ NT$289/月**。
⚠️ 部署時務必把 `auto_stop_machines` 關掉，否則 Machine 會被停機。
若採「只在交易時段開機」，Fly 的停機不計 CPU/RAM 特性可把運算費壓到約 US$1.2/月（≈NT$39），但要自己寫開關機排程。

**若堅持要台灣境內節點：Cloud Run Worker Pool @ asia-east1 — US$25.95/月 ≈ NT$838**

這是唯一能把運算放在台灣島內的選項，延遲最佳、且 worker pool 完全繞開 60 分鐘 timeout。但**比 VPS 貴約 5 倍**。除非實測證明東京節點的延遲真的會影響策略，否則自用階段不建議付這個溢價。

**明確不推薦（自用階段）**

- **Render / Railway / DigitalOcean**：亞洲節點只到新加坡，對台股行情而言地理位置最差。
- **Render Free / Zeabur Free**：會自動休眠，功能上不可行。
- **Cloud Run Service（request-based）**：長連線讓它全時段計 active，US$61/月，最貴。
- **AWS App Runner**：**已不對新客戶開放**。
- **AWS ECS Fargate**：US$11–22/月看似還好，但加上 public IPv4／NAT、CloudWatch、ECR 之後不會比 VPS 便宜，維運複雜度卻高得多。

---

### 情境 B：未來上架階段（多使用者、需要對外 API、要 HA 與備份）

此時多出三個需求：對外 HTTP/WS 入口、託管 DB（要有備份與 PITR）、行情接收器與 API 服務解耦。

**方案 B-1（推薦，平衡）：Fly.io 東京全套 — 約 US$52.4/月 ≈ NT$1,693**

| 元件 | 規格 | 月費 |
|---|---|---|
| 行情接收 worker | shared-cpu-1x / 1GB @ nrt | US$7.45 |
| API / 前端服務 | shared-cpu-1x / 512MB @ nrt | US$4.18 |
| 託管 PostgreSQL | Fly Managed Postgres Basic（shared-2x / 1GB，含 HA、備份、連線池） | US$38.00 |
| 儲存 | 10 GB @ US$0.28/GB | US$2.80 |
| **合計** | | **US$52.43 ≈ NT$1,693/月** |

優點：全部在東京同一區、私有網路互通、secret 機制完整、單一供應商。
缺點：Managed Postgres 的 US$38 是整包裡最大一筆；若不需要 HA，可改成自架 Postgres Machine（shared-cpu-1x/2GB US$13.99 + volume）省下約 US$21。

**方案 B-2（最省）：Vultr / Linode 東京 VPS 2 vCPU / 4 GB — US$20–24/月 ≈ NT$646–775**

Vultr `vc2-2c-4gb` US$20 或 Linode 4GB US$24，一台跑完 worker + API + Postgres + Caddy(TLS)。加一顆快照/備份約 US$1–2。
**合計約 US$21–26 ≈ NT$678–840/月。**
適合「上架但流量仍小」的階段，成本只有 B-1 的一半，代價是 HA 與備份要自己做。

**方案 B-3（台灣境內、GCP 原生）：Cloud Run Worker Pool + Service @ asia-east1 — 約 US$30–40/月 ≈ NT$970–1,290（不含 DB）**

| 元件 | 規格 | 月費 |
|---|---|---|
| 行情接收 | Worker Pool 1 vCPU / 512 MiB，instance=1 | US$25.95 |
| 對外 API | Cloud Run Service，request-based，可 scale to zero | 低流量下接近 US$0（免費額度 180,000 vCPU-s + 200 萬 requests） |
| 盤後批次 | Cloud Run Jobs + Cloud Scheduler（3 job 免費） | ≈ US$0 |
| Secret | Secret Manager（6 個 version 內免費） | US$0 |
| DB | 外接 Neon Launch（新加坡）或 Cloud SQL（未查證） | 依用量 |

優點：**唯一把行情接收放在台灣境內**的方案；API 可縮到零、批次幾乎免費；secret 與排程都在免費額度內。
缺點：worker pool 的 US$25.95 是硬成本；DB 若用 Neon 會跨到新加坡，抵銷部分延遲優勢。

---

## 4. 一句話結論

> **自用階段選東京 VPS（Vultr / Linode，US$5 ≈ NT$162/月）**——常駐 WS 這種工作負載，serverless 的所有優點（縮到零、按 request 計費）在這裡都失效，反而只剩缺點；不想碰 OS 就退一步用 **Fly.io 東京（US$7.45 ≈ NT$241/月）**。
> **上架階段選 Fly.io 東京全套（約 US$52 ≈ NT$1,693/月）**，或先用 **2 vCPU/4 GB VPS（約 US$21–26 ≈ NT$678–840/月）** 撐到流量真的長出來。
> **只有在實測證明「台灣節點 vs 東京節點」的延遲差異會影響策略時**，才值得為 Cloud Run Worker Pool @ asia-east1 多付 US$21/月。

---

## 5. 未能查證項目（誠實標註）

1. **Zeabur 實際伺服器月費** — 2026 年起 Shared Cluster 停用、改為 BYOS/代購伺服器，報價需登入 dashboard（`zeabur.com/servers`）才看得到，官方公開文件無價目表。
2. **Zeabur 是否有內建 cron/排程** — 官方文件導覽無此專章。
3. **Fly.io 是否有官方 cron 產品** — 官方文件中未找到。
4. **Supabase 的可用區域** — 官方定價頁未列出區域清單。
5. **Cloud SQL、AWS RDS、EventBridge Scheduler、AWS Secrets Manager 的價格** — 本次未展開查證（因其對應方案已非推薦選項）。
6. **Google Compute Engine（asia-east1）VM 價格** — 定價頁為 JS 動態載入，未能取得可信的靜態數字。若要在台灣境內用「VPS 型態」而非 Cloud Run，需另行以 GCP 定價計算機查證。
7. **各節點對台灣的實測 RTT** — 本文只列節點地理位置，未實測毫秒數。上線前應自行從候選節點 ping 行情端點。
8. **Railway / Render 的 secret 加密實作細節** — 官方公開文件未載明。
9. **各台灣券商行情 API 的 OS 需求** — 僅查證了富果（Node + Python SDK）與永豐 Shioaji（Linux/macOS/Windows 皆可）。若採用 Windows COM 型態的券商元件，本文結論需整個重來。

---

## 6. 來源清單（皆為第一手官方頁面）

**運算平台**
- Google Cloud Run 定價：<https://cloud.google.com/run/pricing>
- Cloud Run 區域與定價分級：<https://docs.cloud.google.com/run/docs/locations>
- Cloud Run WebSocket：<https://docs.cloud.google.com/run/docs/triggering/websockets>
- Cloud Run 最小實例：<https://docs.cloud.google.com/run/docs/configuring/min-instances>
- Cloud Run CPU 設定：<https://docs.cloud.google.com/run/docs/configuring/services/cpu>
- Cloud Run Worker Pools：<https://docs.cloud.google.com/run/docs/deploy-worker-pools>
- Cloud Run 配額與限制：<https://docs.cloud.google.com/run/quotas>
- Fly.io 定價：<https://fly.io/docs/about/pricing/>
- Fly.io 區域：<https://fly.io/docs/reference/regions/>
- Fly.io autostop/autostart：<https://fly.io/docs/launch/autostop-autostart/>
- Fly.io secrets：<https://fly.io/docs/apps/secrets/>
- Fly.io Managed Postgres：<https://fly.io/docs/mpg/>
- Railway 定價：<https://railway.com/pricing>
- Railway 方案：<https://docs.railway.com/reference/pricing/plans>
- Railway 區域：<https://docs.railway.com/reference/regions>
- Railway cron：<https://docs.railway.com/reference/cron-jobs>
- Railway 變數：<https://docs.railway.com/reference/variables>
- Zeabur 定價：<https://zeabur.com/pricing>、<https://zeabur.com/docs/en-US/pricing>
- Zeabur Free / Dev 方案：<https://zeabur.com/docs/en-US/pricing/free-plan>、<https://zeabur.com/docs/en-US/pricing/dev-plan>
- Zeabur Shared Cluster 停用公告：<https://zeabur.com/docs/en-US/server/shared-cluster>
- Zeabur 購買伺服器：<https://zeabur.com/docs/en-US/server/purchase>
- Render 定價：<https://render.com/pricing>
- Render 區域：<https://render.com/docs/regions>
- Render Free instance：<https://render.com/docs/free>
- Render Cron Job：<https://render.com/docs/cronjobs>
- AWS App Runner 定價：<https://aws.amazon.com/apprunner/pricing/>
- AWS App Runner 停止收新客公告：<https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html>
- AWS App Runner 架構與規格：<https://docs.aws.amazon.com/apprunner/latest/dg/architecture.html>
- AWS Fargate 東京費率（官方 Price List API）：`https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/ap-northeast-1/index.json`
- AWS ELB / 公網 IPv4 東京費率（官方 Price List API）：`.../AWSELB/current/ap-northeast-1/index.json`、`.../AmazonVPC/current/ap-northeast-1/index.json`

**VPS**
- Akamai/Linode 機型與價格（官方 API）：`https://api.linode.com/v4/linode/types`
- Akamai/Linode 區域（官方 API）：`https://api.linode.com/v4/regions`
- Vultr 方案（官方 API）：`https://api.vultr.com/v2/plans`
- Vultr 區域（官方 API）：`https://api.vultr.com/v2/regions`
- DigitalOcean Droplet 定價：<https://www.digitalocean.com/pricing/droplets>
- DigitalOcean Droplet 區域：<https://www.digitalocean.com/products/droplets>

**資料庫與周邊**
- Neon 定價：<https://neon.com/pricing>
- Neon 區域：<https://neon.com/docs/introduction/regions>
- Supabase 定價：<https://supabase.com/pricing>
- Google Cloud Scheduler 定價：<https://cloud.google.com/scheduler/pricing>
- Google Secret Manager 定價：<https://cloud.google.com/secret-manager/pricing>

**行情 SDK**
- 富果 Fugle Market Data：<https://developer.fugle.tw/docs/data/intro>
- 永豐 Shioaji：<https://sinotrade.github.io/>

**匯率**
- 中央銀行新臺幣對美元收盤匯率：<https://www.cbc.gov.tw/tw/lp-645-1.html>
