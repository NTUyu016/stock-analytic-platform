# 部署、環境與成本上限 v1

> 對應 issue：[#17 部署、環境與成本上限](https://github.com/NTUyu016/stock-analytic-platform/issues/17)
> 定案日期：**2026-08-09**
> 上桌前準備：[`docs/briefing/17-deployment.md`](../briefing/17-deployment.md)（含 2026-08-09 事實更正欄）
> 查證來源：[`scheduling-and-db-sleep.md`](../research/scheduling-and-db-sleep.md)（2026-08-05~06）、[`deployment-facts-2026-08-09.md`](../research/deployment-facts-2026-08-09.md)、[`local-deployment-facts.md`](../research/local-deployment-facts.md)
> 匯率：1 USD = 32.315 TWD（2026-08-05 中央銀行牌告）

---

## 總覽

| 項目 | v1 決定 |
|---|---|
| 部署位置 | **使用者自己的電腦**：Windows 11 → **WSL2 → Docker Engine + Compose**（**不用 Docker Desktop**，理由見 §1.1） |
| 對外存取 | **Tailscale 私有網路**，路由器不開任何埠；憑證走 `.ts.net`，**Caddy 零設定** |
| 資料庫 | **同機自架 `postgres:17-bookworm` 容器**，直連、無 pooler、不休眠 |
| 排程 | **Windows 工作排程器觸發**，容器內不跑 cron。⚠️ **補跑機制不可信任，所有排程必須是回補式** |
| 監控 | **Healthchecks.io 免費層 → Discord**（反向心跳）＋ 排程自我斷言 |
| 機密 | 單一 `.env`（已在 `.gitignore`） |
| 環境 | local dev + prod **同機、兩個 Compose project**，不做 staging |
| CI/CD | GitHub Actions **只跑測試，不部署**；部署是本機一行指令 |
| 月費 | **NT$0** |

---

## 0. 這張票最後決定的東西，跟它上桌前假設的完全不同

[`17-deployment.md`](../briefing/17-deployment.md) 的九個待決事項全部建立在一個共同前提上：**「選哪一家雲」**。使用者在 2026-08-09 的 grilling 中把這個前提換掉了——

> 「先跑自己電腦，未來再考慮付費 DB v2」

這不是「選了選項 B 而不是 A」，而是換了一個座標系。上桌前準備的九題有六題因此**答案完全不同**，而不是「選了另一個選項」。

### 這個決定一次消掉的七個地雷

以下每一條，在任何一個雲端組合裡都是必須處理的問題；在本機部署下它們**不是被解決，是不存在**：

| # | 雲端組合下的地雷 | 出處 |
|---|---|---|
| 1 | Neon Free 的 compute **5 分鐘閒置就 scale-to-zero、免費層不可關閉**，會在盤中把 `LISTEN` 訂閱狀態整個丟掉且不報錯，只能靠應用層 keepalive 撐住 | `deployment-facts-2026-08-09.md` §3.3；`realtime-quotes.md` §3 |
| 2 | 為了擋住 ①，compute 盤中永不休眠，開始吃 **100 CU-hours/月**；用罄後**整個 project 的 compute 被 suspend 到下個帳期，既有連線被切斷** | `deployment-facts-2026-08-09.md` §3.1 |
| 3 | transaction 模式的 pooler 會讓 `LISTEN` **完全失效且不報錯**，必須記得走 direct connection | `realtime-quotes.md` §3 |
| 4 | `api` scale-to-zero 的冷啟動延遲、與跨服務 RTT——**#16 移交過來的兩項，至今沒有任何實測數字**，只有官方文件的模糊描述 | `17-deployment.md` 開頭的測量缺口小節 |
| 5 | **四家沒有任何一家提供帳號總支出硬上限**；Fly 官方明文「We don't support billing alerts (yet), so budget accordingly」——連事後通知都沒有 | `deployment-facts-2026-08-09.md` §5 |
| 6 | 「任何人送一個 HTTP request 都能喚醒機器，喚醒發生在應用程式跑起來之前，**認證擋不住它**」，而網域一進 CT log 上線數小時內必有掃描器來敲 | issue #17 第 3 則留言；`tech-stack.md` §8 |
| 7 | Neon Free 的可還原時間窗**只有 6 小時**、僅 1 個手動 snapshot；Render Postgres Free **無 PITR、無備份保留且 30 天到期** | `deployment-facts-2026-08-09.md` §3.4、§2.6 |

**特別值得記下的是第 5 條與第 7 條的組合**：在 NT$50–100/月的預算裡，唯一放得進去的資料庫全是免費層，而免費層之所以能當作「支出硬上限」，**是因為它結構上不產生帳單，不是因為它有 cap 這個功能**。代價就是第 7 條——那個 6 小時的還原窗，正好撞上 issue #17 body 自己點名的紅線：「持股與交易紀錄遺失不可接受」。

### 但也誠實記下：這個決定沒有解決什麼

| 沒解決的事 | 說明 |
|---|---|
| **電腦沒開的時段完全沒有服務** | 盤中不在線就沒有即時報價與即時警示，且**那段時間的警示是真的漏掉，補不回來**（歷史價格補得回來，見 §4） |
| **備份從「別人的問題」變成「你的問題」** | 雲端至少有個 6 小時的還原窗；本機是 0，除非自己做。見 §3.3 |
| **可用性完全綁在一台個人電腦上** | 它會更新重開、會睡眠、會當機、硬碟會壞 |

---

## 1. 部署位置：使用者自己的電腦

### 決定

**v1 的正式站跑在使用者自己的 Windows 11 電腦上，但整套系統跑在 WSL2 裡**：

```
Windows 11 Home
└── WSL2（Ubuntu，systemd 開啟）
    ├── tailscaled              ← systemd service，見 §2
    └── Docker Engine（不是 Docker Desktop）
        └── docker compose （prod project）
            ├── db          postgres:17-bookworm   ← named volume 持久化
            ├── api         python:3.13-slim       ← FastAPI
            ├── caddy       caddy:<版本>           ← 靜態檔、反向代理 /api/*、TLS
            └── quote-worker（profile: intraday）   ← 只在盤中被排程啟停
```

`quote-worker` 放在獨立的 Compose profile，**預設不啟動**——這讓 `tech-stack.md` §4「`quote-worker` 是可選元件」從一條紀律變成預設行為。

### 1.1 為什麼是「WSL2 裡的 Docker Engine」，而不是 Docker Desktop

**這一條是被 2026-08-09 的查證改掉的。** 原本的預設是 Docker Desktop（WSL2 backend），但查證發現 **Docker 官方安裝頁對 Windows 11 Home 的支援狀態自相矛盾**：

- 系統需求段落列的是「Windows 11 64-bit: **Enterprise, Pro, or Education** version 23H2」——**沒有 Home**（已 grep 原始 HTML 確認不是抽取遺漏，全頁只出現這一次）。
- **同一頁**另一處卻寫「**Windows Home** or Education editions only allow you to run Linux containers」。

兩句不可能同時成立，而**使用者的機器正是 Windows 11 Home**。

> **決定：不賭這一題，改用 WSL2 內的 Docker Engine。** 這不是「退而求其次」——它在四個方向上都更好：
>
> | 理由 | 說明 |
> |---|---|
> | **繞開授權與支援的模糊地帶** | Docker Engine 是 Apache-2.0 的 OSS，沒有 Docker Desktop 那條「<250 員工且 <$10M 營收」的商用門檻要判斷 |
> | **所有官方文件的「Linux 做法」直接適用** | 這一條比看起來重要得多——見 §2.4：Caddy 取 Tailscale 憑證的權限機制**官方只寫了 Linux**，Windows 路徑兩邊都沒寫。跑在 WSL2 裡就不需要那份不存在的文件 |
> | **少一個會自己跳更新的常駐 GUI 元件** | Docker Desktop 是這套系統裡唯一一個會自動更新並要求重啟的東西 |
> | **與 v2 上雲的環境更接近** | §10 的遷移路徑吃的是 OCI image，跑在 Linux 上 |

**代價**（誠實記下）：

- WSL2 需要在 `/etc/wsl.conf` 開啟 `systemd=true`，且 **WSL2 發行版不會在開機時自動啟動**——需要一個登入時觸發的工作排程器項目把它叫起來。這是 §4 排程的前置條件，**漏掉它的話所有排程都不會跑，而且不會有錯誤訊息**（記在 §12）。
- 所有排程指令要透過 `wsl.exe -d <distro> -- ...` 進入。
- 沒有 Docker Desktop 的 GUI，一切走 CLI。對這位使用者（Python/SQL 背景、懂一點 nginx）這不是問題，但實作票要附上手指令。

### 1.2 為什麼要容器化，而不是直接裝 Python 與 PostgreSQL

| 理由 | 說明 |
|---|---|
| **與 `tech-stack.md` §9 已定的硬約束一致** | §9 明訂 base image 必須是 Debian（`python:3.13-slim`），不可用 Alpine，因為 `shioaji` 只出 manylinux（glibc）wheel。這條規則只有在容器裡才有意義 |
| **v2 上雲時形狀不用重畫** | 遷移是換執行位置，不是換打包方式 |
| **一鍵啟停，符合成本偏好的精神** | issue #1 的偏好是「能中途停掉比 24/7 最便宜更重要」。本機的「停掉」就是 `docker compose stop` |
| **`quote-worker` 的啟停有現成的表達方式** | `docker compose --profile intraday up -d` / `stop`，不需要自己寫行程管理 |

### 被淘汰的選項輸在哪

| 選項 | 月費 | 輸在哪 |
|---|---|---|
| **Fly.io 全套**（`api` scale-to-zero + `worker` 只開盤中 + Neon Free） | 以 nrt 官方費率重算 **≈US$0.83 ≈ NT$27** | 不是輸在錢，是輸在 §0 表格的七條。最致命的是第 7 條：**Neon Free 的還原窗只有 6 小時**，而這個系統存的是使用者的交易紀錄。「幾乎免費」買到的資料保護比自己 `pg_dump` 還弱 |
| **Render 全包** | ≈NT$32 起 | Cron Job **沒有 Free 檔位**（最低 Starter，且有 $1/月最低消）；Free Postgres 無 PITR、無備份保留、**30 天到期**（等於每月搬一次家）；節點僅新加坡 |
| **Fly + Render Cron + Neon Free** | ≈NT$56 | 三個供應商、三份帳號與 secret 機制。它買到的東西（排程失敗告警）在本機用 Healthchecks.io 免費層就有，見 §5 |
| **VPS（Vultr/Linode 東京）** | NT$162（超上限 62%） | 官方明文關機照收費——**VPS 沒有「停掉」這個檔位，只有「刪掉」**，與 issue #1 的成本偏好正面衝突 |
| **Fly Managed Postgres** | NT$1,228 | 唯一官方明文保證 `LISTEN/NOTIFY` 正常運作的託管 Postgres。純粹輸在價格；若日後預算鬆綁，這是風險最低的選項 |

> **這些盤點沒有白做。** 它們降級為 §10 的遷移路徑材料，且 2026-08-09 的複查已把當時「未能查證」的六項補成官方數字——上雲那天不用重查一遍。

---

## 2. 對外存取：Tailscale，路由器一個埠都不開

### 決定

**用 Tailscale 把使用者的電腦與他的手機／筆電放進同一個私有網路（tailnet），網站只在 tailnet 內可達。家用路由器不開任何 port forwarding。**

### 2.1 這推翻了 issue #1 的一條已定調前提

issue #1「已定調前提」表裡的**暴露面**寫的是「**公開在網際網路上**」（2026-08-02 定調）。本票推翻它。**推翻一條已定調前提需要說明為什麼可以推翻**：

當初定「公開」的**唯一理由不是需求，是技術難度**（`tech-stack.md` §8「憑證怎麼來」原文）：

> 內網自簽方案（`tls internal`）需要在每台裝置上手動安裝並信任自簽 CA，iOS 上尤其繁瑣……公開 + Let's Encrypt 由 Caddy 全自動處理，**反而是難度較低的路徑**。

也就是說，#10 當時是在「自簽 CA」與「公開上網」兩個選項之間選了難度低的那個。**Tailscale 是當時沒有被放上桌的第三個選項，而它同時避開了兩者的代價**：裝置端不需要安裝任何自簽 CA（憑證是公開信任的），而網站不需要暴露在公網。

**前提改變也是推翻的正當理由**：#10 做這個決定時，執行位置預設是「雲端某台可拋棄的機器」。現在執行位置是**使用者自己的個人電腦**，「把 443 開給全世界」這件事的風險量級完全不同——被打進去的不是一台重建只要五分鐘的雲端機器。

### 2.2 這一併消掉了兩條既有的約束

| 原本的約束 | 現況 |
|---|---|
| 「`api` scale-to-zero 代表**任何人送一個 HTTP request 都能喚醒機器**，喚醒發生在認證中介層跑起來之前，**認證擋不住它**」——issue #17 第 3 則留言把它列為必須處理的成本項 | **消失。** 沒有公開入口，喚醒不了，也沒有 scale-to-zero 這件事 |
| 「網域一進 CT log，上線數小時內必有掃描器來敲」——`tech-stack.md` §8、`auth.md` | **大幅弱化**，細節見 §2.4 |

### 2.3 #10 的哪些結論仍然完全成立（不得放寬）

**Tailscale 是第二道防線，不是認證的替代品。** 以下規則一條都不放寬：

1. **Google OIDC（主）+ GitHub OAuth（備援）照做**，session 走伺服器端 session + cookie，不用 JWT（`auth.md`）。
2. **授權必須自查 allowlist、不自動建帳號**（`auth.md`）。
3. **任何未登入即可存取的路由都不得包含即時報價**（`tech-stack.md` §8，來源是 TWSE 管理辦法，法遵而非技術）。

**為什麼不趁機省掉登入**：
- 這三條裡有一條是**法遵**，不因網路拓樸改變而消失；
- §10 的遷移路徑第一項就是「改回公開」，若 v1 省掉認證，那天要補的不是設定而是整套授權模型；
- 資料模型自始帶 `user_id`（#9）的理由與此同形——**預留比事後補便宜**。

> **一個順帶的好消息**：Tailscale 讓「行情不得轉供第三人」這條法遵約束從「靠應用層規則保證」變成「網路層本來就進不來」。**這是防禦深度的增加，不是把應用層規則換掉。**

### 2.4 憑證：`.ts.net`，而且 Caddy 什麼都不用設

`tech-stack.md` §8 的 Caddyfile 範例依賴一件事：**Caddy 看到網域就自動申請 Let's Encrypt 憑證**。那條標準 ACME 路徑在不開埠的前提下**定義上就走不通**（Caddy 官方原文）：

| Challenge | 官方需求 | 在本形狀下 |
|---|---|---|
| HTTP-01 | 「requires port `80` to be **externally accessible**」 | ❌ |
| TLS-ALPN | 「requires port `443` to be **externally accessible**」 | ❌ |
| DNS-01 | 「does not require any open ports」 | ⚠️ 可行，但要有自己控制的網域 |

**但 Tailscale 提供了第四條路，而且比原設計更乾淨。** 2026-08-09 查證（[`local-deployment-facts.md`](../research/local-deployment-facts.md)）：

1. **`*.ts.net` 的憑證由 Let's Encrypt 簽發**，Tailscale 代為建立 TXT 記錄走 **DNS-01**，**不需要任何開放埠**；私鑰只在本機產生。
2. **Caddy 2.5+ 看到 `.ts.net` 網域就不跑 ACME**，改在 TLS handshake 當下向**本機的 tailscaled** 取憑證——**Caddyfile 零額外設定，且續期自動**。

> **`tech-stack.md` §8 擔心的「憑證會在半夜三點過期時咬你」，在這條路上不存在。** 它只在「用 `tailscale cert` 手動寫出憑證檔」那條路上成立——官方對那條路明文寫著「**you are responsible for renewing**」（90 天）。
>
> **因此規定：走 Caddy 自動取用那一條，不得用 `tailscale cert` 寫檔。** 兩條路看起來都能work，但其中一條會在三個月後的某天靜默過期。

**前置條件**（實作票要逐項打勾）：tailnet 開啟 MagicDNS、開啟 HTTPS、完成一次「我知道網域名稱會被公開」的同意動作；Caddy 需以 root 執行或設 `TS_PERMIT_CERT_UID`。

> ⚠️ **這正是 §1.1 選 WSL2 的回報**：`TS_PERMIT_CERT_UID` 這個權限機制**官方只寫了 Linux 的做法，Windows 路徑 Caddy 與 Tailscale 兩邊都沒有文件**。跑在 WSL2 裡，「Linux 做法」就是我們的做法。
>
> **仍未查證的一格**：Caddy 在容器內、tailscaled 在 WSL2 主機上時，容器如何取得 tailscaled 的 socket（預期是 bind mount `/var/run/tailscale/tailscaled.sock`，但官方未直接記載此組合）。**列為階段 0 實作票的第一個驗收項**——它是整條路徑上唯一沒有官方文件背書的接點。

### 2.5 為什麼還是用 Caddy，而不是 `tailscale serve`

`tailscale serve` **本身就是反向代理，且內建自動配發的 TLS 憑證**（官方原文），還附帶 identity headers（`Tailscale-User-Login` 等，且會剝除偽造）。它是一個真實的選項——用它就不需要 Caddy。

**但它輸在三個查不到答案的地方，而這三個剛好都是本專案一定會用到的**：

| 需求 | 出處 | `tailscale serve` 官方文件 |
|---|---|---|
| **SPA catch-all fallback**（`try_files {path} /index.html`） | `tech-stack.md` §8 | **未提及** |
| **SSE 長連線**（api → 瀏覽器的報價扇出） | `realtime-quotes.md` §4 | **未提及** |
| 壓縮、快取標頭、access log | 一般需求 | **未提及** |

**決定：用 Caddy。**「官方文件沒寫」不等於不支援，但**在一條沒有官方保證的路上押三個必要功能**，代價是實作到一半才發現要換回來。Caddy 這三項都是文件化的標準行為，而它在本形狀下的額外成本已經被 §2.4 那條「零設定取憑證」抵銷了。

> `caddy-tailscale` 外掛**不使用**：它自稱 experimental，**不在 Caddy 官方套件登錄檔內**（2026-08-09 實查 `caddyserver.com/api/packages` 確認），其 README 自己就寫「你多半不需要它」。

### 2.6 CT log 在私網情境下的實際後果

`tech-stack.md` §8 與 `auth.md` 記載的「網域一進 CT log，上線數小時內必有掃描器來敲」——**前半段仍然成立，後半段不成立**。Tailscale 官方對此有專章（2026-08-09 查）：

- **會進 CT log 的是 `<機器名>.<tailnet DNS 名>.ts.net`。**
- **tailnet 名是隨機十六進位或隨機字組**，官方明說設計目的就是「avoid publicizing your organization name, such as your corporate domain, email address, or GitHub username」——**tailnet 名本身不洩漏身分**。
- **但機器名是原樣公開的**，官方明確警告不要放敏感資訊。
  > **硬性規則：機器名不得包含姓名、帳號、券商名稱或任何可識別個人的字串。**
- 官方對後果的原文：「The public ledger only provides information about the names of the TLS certificates; **access to your devices is still restricted by Tailscale as normal**」。

⚠️ **一格未查證**：只開憑證、未開 Funnel 時，`*.ts.net` 是否有公開的 DNS 記錄——官方沒答（Funnel 明確有，一般節點未寫）。這不影響存取控制，只影響「別人能不能從名字推知這台機器存在」。

### 2.7 兩顆會靜默失效的定時炸彈

兩者都**不會產生任何失敗紀錄**，形狀與已記載的「GitHub Actions public repo 60 天自動停用」完全相同：

| # | 炸彈 | 引信 | 拆法 |
|---|---|---|---|
| 1 | **Tailscale 金鑰預設 180 天到期**，不重新認證就斷線 | 半年 | 可**逐台關閉金鑰到期**。實作票必須包含這個設定動作 |
| 2 | **Windows 上的 Tailscale 預設隨登入使用者跑，重開機不會自動連線**（除非開 "Run unattended"） | 下一次重開機 | 本形狀把 tailscaled 放進 **WSL2 的 systemd service**，繞開這個預設；但 WSL2 本身仍需開機自啟（§1.1） |

### 被淘汰的選項輸在哪

| 選項 | 輸在哪 |
|---|---|
| **照原計畫公開**（DuckDNS + Caddy 自動 HTTPS + 路由器開 443） | 被敲的是使用者的個人電腦。且 2026-08-09 查證確認 **Cloudflare 沒有「免費子網域」這種服務**（Free plan 是已擁有網域的 DNS 託管），這條路上 DuckDNS 是唯一真免費的選項，選擇比原本以為的少一半 |
| **只開 localhost** | 出門完全看不到持股，且 #10 的整套認證在 v1 形同虛設——那會讓 §10 遷移那天要補的東西變多 |
| **Cloudflare Tunnel** | **#10 已否決，理由在本形狀下依然成立**：`cloudflared` 靠一條常駐外連維持隧道，機器一停隧道就斷。它同時也把流量交給第三方，與「私有」的目的相反 |
| **自簽 CA（`tls internal`）** | 就是 #10 當初否決的那個——每台裝置手動安裝並信任自簽 CA，iOS 尤其繁瑣 |

---

## 3. 資料庫：同機自架 PostgreSQL 容器

### 決定

**PostgreSQL 跑在同一台機器的 Docker 容器裡，資料放 named volume，`api` 與 `quote-worker` 直連，不放任何 pooler。**

### 3.1 為什麼：三條既有的硬性規則在這裡自動成立

| 既有規則 | 在本形狀下 |
|---|---|
| 「**listener 一律走 direct connection，不得走 pooled endpoint**」（`realtime-quotes.md` §3；寫成規則的理由是「serverless 就該用 pooled」是一條很強的直覺，依它改回去報價扇出會靜止且不報錯） | **自動成立**——沒有 pooler 可走錯 |
| 「託管 DB 會在盤中休眠、順手掐掉 listener」（`realtime-quotes.md` §3 的預言，在 Neon 上字面成立且門檻只有 5 分鐘） | **不適用**——自架不休眠，keepalive 這條應用層規則在 v1 是不必要的（**但不要刪掉，見 §11**） |
| 「`api` 醒來時 PostgreSQL 必須是可達的」（`auth.md`，因為 session 存資料庫） | **自動成立**——DB 與 `api` 同機、同生命週期 |

**版本：釘死 `postgres:17-bookworm`，不用 `latest`。**

`latest` 目前是 **18.4 / 18-trixie**（2026-08-09 查）。**刻意不用 18**，理由是一個會靜默吃掉資料的變更：

> **PostgreSQL 官方 image 自 18 起把 `PGDATA` 改成 `/var/lib/postgresql/18/docker`，`VOLUME` 宣告改成 `/var/lib/postgresql`**；17 以下則是 `/var/lib/postgresql/data`。
>
> **掛錯路徑不會報錯**——容器照常啟動、資料庫照常運作，只是資料寫進一個**匿名 volume**，`docker compose down` 或重建容器的那一天全部消失。

v1 用 17 的理由不是「18 不好」，而是**這個專案的所有既有實測、所有範例、以及使用者將來會 Google 到的多數文件，都還停在 `/var/lib/postgresql/data` 這個心智模型上**。等到需要升上 18 時，那是一次有意識的遷移，而不是一個 `latest` 帶來的意外。

> #16 的效能實測是在 PostgreSQL **16.2** 上做的（`16-performance.md`）。那些數字的結論由**查詢寫法**主導而非版本（整段曲線 306→97ms、子區間樸素寫法 1,491ms→增量寫法 45.9ms，**32 倍**），故 16→17 不影響結論。但 `performance.md` §1.5 的門檻「切換期間時單次載入 < 200 ms」**應在實際版本與實際硬體上重測一次**，見 §13。

**持久化用 named volume，不用 bind mount。** Docker 官方原文：「**Volumes are the preferred mechanism**」。另有一條 WSL2 專屬的理由：Docker 官方最佳實務明文**不要 bind mount `/mnt/c` 底下的路徑**（效能差，且沒有 inotify 事件）——而在 WSL2 裡跑 Docker 時，那正是最容易誤選的位置。

### 3.3 備份：本機部署下唯一真正變糟的一件事

這是這個決定的最大代價，必須正面處理。issue #17 body 原文自己點名的紅線是「**持股與交易紀錄遺失不可接受**」，而 `data-model.md` 全文沒有出現「備份」兩個字——**在本票之前，這個專案沒有任何備份規格**。

**決定**：

1. **每日一次 `pg_dump`**（自訂格式 `-Fc`），與盤後排程同一批（§4），**成功與否納入同一套心跳監控**（§5）。
2. **保留策略**：本機保留最近 14 份 + 每月 1 份共 12 個月。
3. **至少一份離機**：dump 檔同步到使用者既有的雲端硬碟資料夾（Google 帳號已因 #10 的 OIDC 存在，不新增供應商）。
4. **每季一次還原演練**：把最新的 dump 還原到 dev 環境（§7），跑一次 `performance.md` §8A 的不變量測試。**沒有演練過的備份不算備份**——`pg_dump` 回傳 0 只證明它寫出了一個檔案。

> **為什麼還原演練不是可選的**：這正是本專案反覆點名的形狀——備份每天成功、每天產生一個大小合理的檔案、**而它從來沒有被還原過**。與 §12 表格裡其他幾條一樣，錯的時候沒有任何錯誤訊息。

### 3.4 硬性規則：備份檔是個人財務資訊

**`pg_dump` 的輸出含實際持股、成交價與金額。**

- **不得放進 repo 的任何位置**（本 repo 為 public）。備份目錄必須在 repo 之外，並在 `.gitignore` 另加一條防呆。
- **不得貼進 issue、PR、或任何公開討論**——這與 issue #1「所有金鑰一律走 `.env`」是同一條規則的延伸，只是保護的東西不同。
- 同步到雲端硬碟的資料夾**不得設為公開連結分享**。

---

## 4. 排程：主機層觸發，且必須是回補式

### 決定

**排程由 Windows 工作排程器觸發，經 `wsl.exe -d <distro> -- docker compose run --rm ...` 執行一次性任務；容器內不跑 cron、不留常駐排程行程。**

排程清單：

| 任務 | 時機 | 內容 |
|---|---|---|
| **WSL2 喚起** | 登入時 | 把發行版叫起來（`systemd` 隨之啟動 tailscaled 與 Docker）。**§1.1 已說明：漏掉這項，以下全部不會跑** |
| `quote-worker` 開機 | 交易日 09:00 | `docker compose --profile intraday up -d` |
| `quote-worker` 關機 | 交易日 13:35 | `docker compose --profile intraday stop` |
| **盤後批次**（**單一任務，內含九個步驟**） | 每日 22:00 之後 | ① `daily_close` 回補 ② `benchmark_series` 回補 ③ `exchange_rate` 回補 ④ **除權息預告 → `pending_action` + `EX_DIVIDEND_AHEAD` 提醒** ⑤ **除權息參考價 → `peak_price` 調整** ⑥ **分割／減資偵測 → `pending_action`** ⑦ **成交量異常評估** ⑧ **`MI_INDEX` 每日快照 → `market_index_daily`（⚠️ 這一步補不回來，見下）** ⑨ **美股 `daily_close`（走 yfinance）** ⑩ 每日總結 Discord（14:00 前那則除外，見 [`alerts.md`](./alerts.md) §5） |
| 備份 | 每日，盤後批次之後 | `pg_dump`（§3.3） |

> **十個步驟為什麼是一個排程而不是十個**：它們共用同一個「回補到最新交易日」的游標，而**拆開之後每一個都要各自記住自己補到哪一天**——那是十份可以各自落後的狀態。合成一個之後，心跳只要看一個成功訊號（§5.2）。
>
> **⑨ 美股是 [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 補的**：issue #1 早已定調「美股不需即時，改走 yfinance 盤後拉取」，但**沒有任何一份規格把它放進排程清單**——而 `market='US'` 與中性 CSV 都是開著的。使用者目前無美股持股，故它是一個**跑起來會是空集合的步驟**，這正是它容易被漏掉的原因。⚠️ **美股的交易日曆與台股不同**，回補游標必須各市場各一個（`performance.md` §2.2 的「聯集日曆」是曲線用的，不是回補用的）。
>
> ⚠️ **這張清單是 2026-08-09 由 [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 的冷讀驗收補齊的**：④⑤⑦⑧ 四項分別由 [`alerts.md`](./alerts.md) §11 與 [`analysis-dimensions.md`](./analysis-dimensions.md) 明文交辦給 #17，⑥ 由 [`corporate-actions.md`](./corporate-actions.md) 交辦，而本文初版的清單**一項都沒有列**。交辦後沒人接的排程，就是一個永遠不會被實作的排程。
>
> **步驟之間的失敗處理**：任一步驟失敗即整批標記失敗（打 `/fail`），**已成功的步驟不回滾**——它們都是冪等的回補，下次跑會補上。**不得因為某一步失敗就跳過後面的步驟**，否則一個長期壞掉的除權息來源會連帶讓收盤價也永遠不更新。
>
> ⚠️ **步驟 ⑧ 是這張清單裡唯一一個「回補做不到」的**。`MI_INDEX` 官方只給最新一日，歷史端點在禁爬側——**漏跑一天就是永久缺一天**，而它的表現是「產業比較不可用」，看起來像資料還在累積、不像漏跑。因此它比其他步驟多一條規則：**比對 `market_index_daily` 與 `benchmark_series` 的最新交易日，中間有斷點就明確告警**。詳見 [`data-model.md`](./data-model.md) `market_index_daily`。
>
> **這一步同時是 §4.1「回補式」硬性規則的唯一例外，而例外必須被寫下來**——否則實作者會照著規則把它寫成回補式，然後在一個永遠補不到東西的迴圈裡以為自己補好了。

> 盤後批次的時點：`tw-benchmark-and-fx-sources.md` 目前**只有一個樣本**（T+13.75h 時已有當日資料），保守下界取 **22:00**。精確時點需在盤後 15:00 / 17:00 / 19:00 / 22:00 分別取樣，見 §14。

### 4.0 ⚠️ 工作排程器的「補跑」不能被信任，這改變了 §4.1 的地位

2026-08-09 查證 Microsoft Learn（`local-deployment-facts.md`）發現三件事，合起來的結論是**「錯過的排程會自動補跑」這個假設不成立**：

| # | 事實 | 影響 |
|---|---|---|
| 1 | `StartWhenAvailable`（「Run task as soon as possible after a scheduled start is missed」）**預設為 False**，且補跑是「排進服務佇列、延遲後啟動，**預設延遲 10 分鐘**」 | 要顯式開啟，且不是立即補 |
| 2 | **官方文件自相矛盾**：兩份說它「只適用於有結束時間、或設成無限重複的時間型工作」，schema 那份說「只適用於 timed tasks」。若前者為準，**一個「每交易日 22:00、無結束時間、無無限重複」的觸發程序可能根本不在適用範圍內** | ⚠️ **未能查證，需人工確認** |
| 3 | **睡眠／關機恢復後會不會補跑，官方完全沒寫。** `WakeToRun` 唯一能找到的第一手旁證是 `powercfg /waketimers`「wakes the system from **sleep and hibernate** states」——**沒有涵蓋關機** | 電腦關機期間錯過的排程，**沒有任何官方保證的補救行為** |

> **這正是 §4.1 那條規則從「好習慣」升格為「必要條件」的原因。** 如果補跑機制可靠，回補式排程只是防禦性設計；**既然它不可靠，回補就是唯一的補救路徑**——排程下次跑起來時把中間全部補齊，是這個系統能容忍關機的唯一機制。
>
> 這同時說明了 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 承諾的「警示 30 分鐘內送達」在 v1 有一個結構性的例外：**電腦沒開的時候，那個承諾不成立**，且沒有任何排程設定能修好它。記在 §11。

### 4.1 硬性規則：所有排程必須冪等，且是「回補到最新」而不是「抓今天」

**這是本票最重要的一條實作規則。**

理由是本機部署的一個結構性事實，不是例外狀況：**這台電腦會關機、會睡眠、會因為 Windows 更新重開。** 排程一定會錯過，而且會經常錯過。

因此：

> **每一個排程任務的語意都必須是「把資料補齊到最新的交易日」，而不是「抓今天的資料」。** 任務必須先查資料庫裡最新一筆的日期，補齊中間所有缺漏的交易日，然後才結束。重複執行同一天必須是無副作用的。

**如果寫成「抓今天」會怎樣**：週一沒開電腦，週一的 `daily_close` 就永遠是空的。而 `performance.md` 已定「曲線日曆為市場交易日聯集」、「部位推導一律用 `traded_on <= D` 不等式聚合」——**少一天收盤價不會讓任何查詢報錯**，圖上就是少一個點，總資產曲線在那天直接連過去。這與 #16 實測到的「等值 join 靜默吃掉 1.6% 的交易」是同一種形狀：**污染是永久的，而且看不出來**。

**連帶好處**：這條規則讓「電腦沒開」從**錯誤**降級為**延遲**。它也是 §10 上雲之後仍然該留著的規則——雲端排程一樣會被丟棄（GitHub Actions 官方明文「some queued jobs may be dropped」）。

**唯一補不回來的是盤中即時警示**：那需要當下在線。這是本機部署真正的功能損失，記在 §11。

> ### ⚠️ 但「回補」對只有最新快照的端點不成立——必須改走歷史型資料源
>
> `transaction-input.md` §8 已警告除權息預告端點（`TWT48U_ALL`、`tpex_exright_prepost`）**只有最新快照，漏跑一天就漏掉那批事件**。對這類端點，「回補到最新交易日」這條規則**寫得出來但做不到**。
>
> **因此每個排程任務都必須明確標示它的資料源屬於哪一類，並各自指定回補路徑**：
>
> | 資料源類型 | 例 | 回補方式 |
> |---|---|---|
> | **歷史型**（帶日期參數、可回溯） | `daily_close`、`benchmark_series`、`exchange_rate`、`TaiwanStockSplitPrice` | 直接依日期區間回補 |
> | **快照型**（只有最新一期） | 除權息**預告**表 | ❌ 補不回來。**必須另走歷史型的結果表**（`TaiwanStockDividendResult`）補齊，預告表只用於提前示警 |
>
> **這是本機部署把一個既有問題放大的地方**：在 24/7 的雲端上，漏跑快照型端點是偶發事故；在一台會關機的電腦上，它是常態。**任何只掛在快照型端點上的偵測，在 v1 都必須有一條歷史型的補救路徑，否則它就是一個會定期漏事件的設計。**

### 4.2 台灣沒有日光節約時間，而本機排程連換算都不用

`scheduling-and-db-sleep.md` §10.3 列的第一個坑是「把台北時間直接寫進 UTC cron，差 8 小時剛好落在傍晚到深夜，且完全沒有錯誤訊息」——Railway 與 Render 的 cron 都是 UTC only。

**本機排程直接用本地時間，這個坑不存在。** 但**上雲那天它會回來**，故記在 §10。

### 4.2.1 硬性規則：容器一律 `TZ=UTC`，日期判定一律顯式換算到 `Asia/Taipei`

> 2026-08-09 由 [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 補——**全部規格從頭到尾沒有一句話交代時區**，而 `traded_on`／`trade_date` 是 `date`、`created_at` 是 `timestamptz`，「今天是不是交易日」「最新交易日是哪一天」的答案會隨行程的 TZ 而變。

- **容器內 `TZ=UTC`**，所有 `timestamptz` 以 UTC 儲存（PostgreSQL 本來就是這樣存的）。
- **所有「哪一天」的判斷一律顯式寫成 `Asia/Taipei`**，不得依賴行程預設時區。`traded_on`、`trade_date`、`effective_on`、以及排程的「預期最新交易日」全部是**台北日曆日**。
- **`date` 欄位不做時區轉換**——它們是日曆日不是時間點，這也是它們用 `date` 而非 `timestamptz` 的原因。

**為什麼不把容器設成 `TZ=Asia/Taipei`**：那會讓「正確」依賴一個環境變數，而**漏設它的後果是台股 09:00 之前的 8 小時全部被算成前一天，且完全不報錯**。顯式換算的程式碼在任何 TZ 下都對，而寫錯時是壞在測試裡，不是壞在使用者的曲線上。這與 §5.3「排程自我斷言」是同一種取捨：**寧可讓錯誤發生在看得見的地方**。

### 4.3 交易日曆

開關機與盤後批次都需要知道「今天是不是交易日」。**排程本身一律每天觸發**，由任務自己判斷；`realtime-quotes.md` 已定的「連得上但無資料 = 休市」規則繼續適用（自動處理颱風假）。

**每天觸發、由任務自行判斷**這個形狀還有一個好處：心跳週期恆為 24 小時，與交易日曆脫鉤——見 §5.2。

---

## 5. 監控：三種失效模式，各一招

### 5.1 三種失效模式必須分開處理

`scheduling-and-db-sleep.md` §8.1 與 issue #17 第 5 則留言合起來識別出三種，**沒有任何單一機制能同時涵蓋**：

| 失效模式 | 為什麼平台告警抓不到 | v1 的對策 |
|---|---|---|
| **① 沒跑** | 排程根本沒被觸發時，不會產生一次「失敗的 run」，因此不觸發任何平台的失敗告警 | **Healthchecks.io 反向心跳** → Discord |
| **② 跑了但失敗** | 本機沒有平台告警可用 | 任務失敗時打 `/fail` 到同一個 Healthchecks endpoint |
| **③ 跑了、成功了、但錯了** | dead-man's switch 抓不到——排程確實跑了也成功了 | **任務自我斷言**（見 5.3） |
| （盤中）**斷線但畫面看起來正常** | 已由 #11／#13 規定 | 前端連線三態指示器，`realtime-quotes.md` §3 |

### 5.2 Healthchecks.io，以及心跳期限怎麼設才不會變成「永遠亮著」

**選 Healthchecks.io 免費層**，理由是它是唯一同時滿足三件事的：免費層 **20 個 job**（本專案用到 4 個）、**官方 Discord 整合**（#15 已定管道就是 Discord，不新增第五個通知管道）、**BSD-3 授權可自架**（日後想收回自己跑不用換服務）。

被淘汰的：Cronitor 免費層只有 5 monitors 且定價頁未明列 Discord 屬於免費檔；Better Stack 的整合清單**沒有 Discord**。

**期限設定**：

| 參數 | 值 | 理由 |
|---|---|---|
| Period | **24 小時** | §4.3 已讓排程每天觸發（含假日），心跳週期因此與交易日曆脫鉤——不需要教 Healthchecks 認識台股行事曆 |
| Grace | **36 小時** | 見下 |

**為什麼 grace 是 36 小時而不是更長**：這個數字是刻意選在「會吵到你」的位置。

- 設太短（如 2 小時）：晚上關機就告警，使用者會在兩週內學會忽略 Discord——這正是 #11「非交易時段用警告色會讓使用者學會忽略它」與 #19「永遠亮著的警告等同沒有警告」的第三次適用。
- 設太長（如一週）：那條線就不再是監控，只是一個延遲很久的訃聞。
- **36 小時的意義**：連續一天半沒有成功回補，資料就真的開始落後了。**那正是使用者應該被打擾的時刻**，不是誤報。

### 5.3 任務自我斷言（對付第 ③ 種）

`tw-benchmark-and-fx-sources.md` §D 實測發現 `openapi.twse.com.tw` 比 `www.twse.com.tw/...?response=open_data` 落後整整一個交易日。走 JSON 鏡像的排程會**每天成功、每天回 1,377 列、不產生任何失敗訊號**，但整條歷史序列永遠晚一天，且因為錯位一致，圖上看不出來。

**因此規定，盤後批次在標記成功之前必須自行斷言**：

1. **來源端點正確**：收盤與基準序列一律走 `www.twse.com.tw/...?response=open_data`，**不得走 `openapi.twse.com.tw` 鏡像**。這條要寫成程式碼裡的常數與一條契約測試，不能只寫在文件裡。

   > ⚠️ **這條禁令的適用範圍**（2026-08-09 由 #18 釐清）：它只適用於**有等價 `response=open_data` 來源的序列型資料**（收盤價、報酬指數）。本專案另有三處**指定使用 `openapi.twse.com.tw`** 的端點——標的反查 `STOCK_DAY_ALL`、除權息預告 `TWT48U_ALL`、產業比較 `MI_INDEX`——**那三個在 `openapi` 之外沒有開放授權側的等價來源，禁令不適用，否則等於禁掉功能本身**。
   >
   > **但代價要記下**：實測落後一個交易日的性質是**鏡像本身的**，那三個端點**很可能同樣落後**（未實測，見 §14）。而它們都是**快照型**、補不回來（§4.1）。因此對這三個端點，第 2 項的日期斷言**不是可選的**——它是唯一能發現「今天拿到的是昨天那批」的手段。
2. **回傳的日期 == 預期的最新交易日**，不符即視為失敗（打 `/fail`），不得寫入資料庫。
3. **列數落在合理範圍**（全市場量級約 1,377 檔）。
4. **回補後，資料庫最新交易日 == 預期最新交易日**，否則失敗。

**只有四項全過才 ping success。** 這使心跳的語意從「排程有跑」升級為「資料真的是最新的」——這才是使用者關心的事。

### 5.4 Healthchecks 的 ping URL 是機密

拿到 URL 的人可以偽造心跳，讓監控**永遠顯示綠燈**。放 `.env`（§6），與其他機密同級，**不得出現在 issue、commit 或任何公開討論**。

---

## 6. 機密注入：單一 `.env`

### 決定

**本機部署沒有平台原生 secret 機制可用，因此統一走 `.env`**（已在 `.gitignore`），由 Docker Compose 讀入。檔案權限收緊到只有使用者本人可讀。

需要注入的機密（從已定案的其他票推導）：

| 機密 | 來源票 |
|---|---|
| 行情 provider API key（Fugle／未來 Shioaji） | #13 |
| Google OIDC `client_secret` | #10 |
| GitHub OAuth `client_secret` | #10 |
| PostgreSQL 密碼 | 本票 |
| Discord webhook URL | #15 |
| Healthchecks.io ping URL | 本票 §5.4 |

### 為什麼不引入 `sops`/`age` 之類的工具

`17-deployment.md` §5.2 列了這個選項，優點是換平台時遷移成本低。**在本機部署下它是純粹的過度工程**：機密從來沒有離開過這台機器，加密進 repo 解決的是「機密要跨機器傳遞」的問題，而 v1 沒有這個問題。

**上雲那天改用平台原生機制**——Fly.io 的機制在既有查證中描述最完整（secret 加密存 vault、「API server 只能加密不能解密」、Machine 銷毀後 host 即失去存取權）。記在 §10。

---

## 7. 環境切分：同機兩個 Compose project，不做 staging

### 決定

**local dev 與 prod 跑在同一台機器上，用兩個 Docker Compose project 隔離**（不同 `COMPOSE_PROJECT_NAME`、不同 volume、不同對外 port、不同 `.env`）。**不做 staging。**

### 為什麼不做 staging

issue #17 body 原文自己就自問過「單人專案上 staging 可能是浪費」。更具體的理由：staging 的價值是**在正式資料上出事之前先驗證 migration**，而那個價值在本形狀下由兩件更便宜的事提供——**每日備份**（§3.3）與**還原演練**（§3.3 第 4 點，演練用的就是 dev 環境）。花一個環境去買一個已經買到的東西是浪費。

### 7.1 一條既有規則在本形狀下變得更尖銳

`realtime-quotes.md` §1：Fugle 免費層同時連線數 = **1 條，且是帳號級**，故本機開發機與正式站不能同時跑 `quote-worker`——第二個連上去不是排隊，是其中一個被拒或被踢。

**在 v1，dev 與 prod 是同一台機器。** 原本「兩台機器不要同時開」的紀律，現在是「同一台機器上兩個 Compose project 不要同時開」——**更容易誤觸**。

規則不變但要更嚴格地寫進實作：

> **dev 的 `quote-worker` 一律使用 fake provider（重播錄製的 tick 檔）。** 要接真行情必須顯式開旗標，且開旗標前必須先停掉 prod 的 worker。

### 7.2 Migration：Alembic

`tech-stack.md` §7 沒有涵蓋 migration 工具（`17-deployment.md` §3.3 已標為空白）。**本票補上：用 Alembic。**

理由：後端已定 Python + FastAPI，Alembic 是 SQLAlchemy 生態的標準解，也是這一層的業界最佳實踐；它產生的是**可版控、可前後移動的 migration 腳本**，而 schema 變更在本專案是可預期的——#20 就要新增 `SPLIT`。

**硬性規則**：

1. **prod 跑 migration 前必須先跑一次 `pg_dump`**，不論看起來多小的變更。
2. **不得用 `--autogenerate` 的產出直接上 prod**，必須人工檢查——autogenerate 對 `CHECK` 約束、generated column（`exchange_rate.rate` 是 generated，見 #16）與索引的偵測並不完整。

---

## 8. CI/CD：GitHub Actions 只跑測試，不部署

### 決定

- **push → GitHub Actions 跑 `tech-stack.md` §7 的分層測試**（錢的計算 TDD、資料源契約測試、退避邏輯測試）。public repo + 標準 runner **免費、無分鐘數上限**。
- **部署是本機的一行指令**：`git pull && docker compose up -d --build`。

### 為什麼不做自動部署

自動部署到一台家用電腦需要 self-hosted runner，那等於**把 GitHub 的 job 執行權接進家用網路**，而 §2 才剛決定不把這台機器暴露出去。風險與收益不成比例。

### 8.1 明確排除：不得用 GitHub Actions 當排程器

即使 v2 上雲，這條也成立。三個官方明文的理由：

1. **「In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days.」** 本 repo 是 public。一個「規格寫完、系統穩定跑著」的專案完全可能連續 60 天沒有 commit——**GitHub 會停用排程，而這不會產生任何一次失敗的 run**，是 §5.1 第 ① 種失效，且是可預期、有明確倒數的那一種。
2. 「The `schedule` event **can be delayed** during periods of high loads……**some queued jobs may be dropped**」，最小間隔 5 分鐘。
3. 「Scheduled workflows will **only run on the default branch**」。

---

## 9. 成本

| 項目 | 月費 |
|---|---|
| 運算與資料庫 | **NT$0**（使用者既有電腦，邊際電費） |
| Tailscale | **NT$0**（Personal：`$0 Free forever`、**最多 6 位使用者、裝置數不限**、**不需要信用卡**。官方明文限非商業用途，本專案符合） |
| Healthchecks.io | **NT$0**（免費層 20 jobs，本專案用 **3**：盤後批次、備份、`quote-worker` 開機。**關機不掛心跳**——沒關掉的後果是多付一點雲端費用或多留一條閒置連線，不是資料錯誤） |
| Discord webhook | **NT$0**（#15 已定） |
| 網域 | **NT$0**（用 Tailscale 提供的名稱，不需自購，也不需 DuckDNS） |
| GitHub Actions | **NT$0**（public repo + 標準 runner） |
| **合計** | **NT$0/月** |

**支出上限的答案**：v1 不需要 spending cap 機制，因為**沒有任何按用量計費的供應商**。這比任何一個雲端組合都乾淨——2026-08-09 查證確認四家雲端供應商**沒有一家提供帳號總支出硬上限**。

**上限的觸發條件寫在 §10**：哪天開始需要付錢，就是重開這張票的時候。

---

## 10. 上雲的解除條件與遷移路徑

### 10.1 什麼時候該重開這題

觸發**任何一條**就代表 v1 的部署形狀已經不夠用：

| # | 解除條件 | 為什麼它是分界線 |
|---|---|---|
| 1 | **開始因為「那天電腦沒開」而錯過想要的盤中警示** | 這是本機部署唯一補不回來的損失（§4.1） |
| 2 | **需要讓沒裝 Tailscale 的人看到**（家人、或想在別人的裝置上臨時看） | Tailscale 的模型就是「裝了才進得來」 |
| 3 | **這台電腦不再適合常開**（換機、搬家、長期外出） | 可用性直接歸零 |
| 4 | **要上架給他人使用** | 那是 issue #1「Not yet specified」裡明寫需要獨立一張圖的區域，**不是這張票的延伸**；且已知兩道法遵牆同時擋路（券商行情不得轉供第三人、FinMind 資料再散布授權未明示） |

### 10.2 遷移時哪些 v1 決策必須重做

| v1 決策 | 上雲後 | 要注意什麼 |
|---|---|---|
| Tailscale 私網 | 改回公開 + Google OIDC | #10 的認證在 v1 就已完整實作，**這是遷移最便宜的一項**（這也正是 §2 拒絕省掉登入的理由）。要重新處理的是 CT log 與掃描器叫醒機器的成本 |
| 同機自架 PostgreSQL | 託管或雲端自架 | **`LISTEN/NOTIFY` 是選型的第一道篩子**：direct connection、不可走 transaction 模式 pooler，且要能撐住閒置休眠（Neon Free 是 5 分鐘且不可關） |
| `.env` | 平台原生 secret 機制 | Fly.io 的機制描述最完整 |
| Windows 工作排程器 | 外部觸發器 | **Fly 原生排程表達不出「每交易日 09:00 Asia/Taipei」**，且設了 schedule 的 Machine 不能再被 API 手動啟動，兩種用法互斥。**不得用 GitHub Actions**（§8.1） |
| 本地時間排程 | UTC 換算 | Railway／Render 的 cron 都是 UTC only；台灣固定 −8 無 DST，但**手寫錯 8 小時完全沒有錯誤訊息** |
| `pg_dump` + 雲端硬碟 | 託管備份／PITR | 挑選時要看**還原窗**：Neon Free 只有 6 小時、1 個手動 snapshot；Render Postgres Free 完全沒有 |
| 無 keepalive | 可能需要 keepalive | 見 §11 |

### 10.3 已查證、上雲時可直接使用的雲端事實（2026-08-09）

不必重查。完整內容見 [`deployment-facts-2026-08-09.md`](../research/deployment-facts-2026-08-09.md)。

- **Fly.io 東京（nrt）官方區域係數 1.307692308**（第二貴，僅次於聖保羅）；shared-cpu-1x 512MB **US$4.18/月**、1GB **US$7.45/月**。停機只收 rootfs（US$0.15/GB/30 天），**但 volume 例外：掛在停機 Machine 上的 volume 照樣計費**。Asia Pacific egress US$0.04/GB。**新客戶沒有免費額度。**
- 本專案形狀的 Fly 月費重算：`worker` 512MB × 91.7h + 兩份 rootfs ≈ **US$0.83 ≈ NT$27**。
- **Neon Free**：100 CU-hours／0.5 GB 儲存／**5 GB 公網傳輸**（三者任一用罄都是**整個 project 的 compute 被 suspend 到下個帳期，既有連線被切斷**）；compute 範圍 0.25–2 CU；scale-to-zero **5 分鐘且不可關閉**；還原窗 **6 小時**、1 個手動 snapshot；**沒有東京，亞洲只有新加坡**。
- **Render**：Free web 750 小時/月，但「**spun-down services don't consume Free instance hours**」；Cron Job **無 Free 檔位**、$1/月最低消、**最小間隔官方未載明**；有 suspend/resume REST API；Free Postgres 無 PITR 且 30 天到期；節點僅新加坡。
- **Supabase**：**Supavisor 兩種模式（含 session mode, 5432）皆為免費的 IPv4**；但**是否支援 `LISTEN/NOTIFY` 官方兩次查證皆未載明**——這是選它的唯一、也是致命的未知。
- **支出上限**：四家皆無帳號總支出硬上限；**Fly 官方明文連 billing alert 都沒有**。
- **Fly Managed Postgres US$38/月**：唯一官方明文保證 `LISTEN/NOTIFY` 正常運作者，東京在可用區域內。

---

## 11. 暫時性妥協與解除條件

比照 [`realtime-quotes.md`](./realtime-quotes.md) §10 的做法，記錄**因當前部署形狀而非技術判斷造成的限制**：

| # | 妥協 | 解除條件 |
|---|---|---|
| 1 | **電腦沒開的時段沒有即時報價與即時警示**，且該時段的警示補不回來 | §10.1 條件 1 或 3 |
| 2 | **只有 tailnet 內的裝置看得到網站** | §10.1 條件 2 |
| 3 | **可用性綁在一台個人電腦上**，無 SLA、無異地備援 | §10.1 條件 3 |
| 4 | **應用層 keepalive 在 v1 不需要，但規則不刪除。** `realtime-quotes.md` §3 那條為託管 DB 休眠而設的規則，在自架 PostgreSQL 下沒有作用 | 上雲的那一刻立即需要。**刪掉它 = 上雲那天報價扇出會靜止且不報錯** |
| 5 | **`api` 不做 scale-to-zero**（本機沒有這個省錢動機） | 上雲時重新啟用，屆時 #16 移交的冷啟動與 RTT 兩項才會真正需要實測 |
| 6 | **憑證不走標準 ACME**（無對外 80/443），改由 Caddy 向本機 tailscaled 取 `.ts.net` 憑證 | 改回公開部署時恢復 `tech-stack.md` §8 的原設計 |
| 7 | **`tech-stack.md` §8 的 Caddyfile 範例在 v1 不可直接照抄** | 同上 |
| 8 | **[#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 的「警示 30 分鐘內送達」在電腦沒開時不成立**，且沒有任何排程設定能修好（§4.0） | §10.1 條件 1 或 3 |
| 9 | **PostgreSQL 釘在 17，不跟進 18**（§3） | 需要 18 的功能時，做一次有意識的遷移並處理 `PGDATA` 路徑變更 |

---

## 12. 會靜默出錯的地方

比照 [`performance.md`](./performance.md) §8。判準同樣是那一句：**「錯的時候，有沒有錯誤訊息？」** 以下每一條的答案都是**沒有**。

| # | 情境 | 為什麼不報錯 | 防線 |
|---|---|---|---|
| 1 | **排程寫成「抓今天」，而電腦那天沒開** | 少一天 `daily_close` 不會讓任何查詢報錯，曲線在那天直接連過去 | §4.1 的回補式硬性規則 + §5.3 的第 4 項斷言 |
| 2 | **盤後排程走了 `openapi.twse.com.tw` 鏡像** | 每天成功、每天 1,377 列，資料永遠晚一天，圖上看不出來 | §5.3 第 1、2 項；契約測試釘死端點 |
| 3 | **心跳 grace 設太長** | 監控看起來是綠的，因為它還在寬限期內 | §5.2 的 36 小時，且理由寫在規格裡防止日後有人「順手調寬」 |
| 4 | **心跳 grace 設太短** | 天天誤報 → 使用者學會忽略 → 真的出事時也被忽略。**這一條的失敗完全發生在使用者腦中，系統看起來一切正常** | 同上 |
| 5 | **dev 的 `quote-worker` 接了真行情** | Fugle 免費層 1 連線是**帳號級**——prod 的 worker 被踢掉，prod 那邊只看到一次斷線重連 | §7.1；dev 預設 fake provider |
| 6 | **`pg_dump` 每天成功，但還原不回來** | `pg_dump` 回傳 0 只證明它寫出了一個檔案 | §3.3 第 4 點的每季還原演練 |
| 7 | **Caddy 在沒有對外 80/443 的情況下嘗試 ACME** | 錯誤在 Caddy 的 log 裡，使用者只看到「連不上」 | §2.4 |
| 8 | **上雲時刪掉了「沒用到」的 keepalive** | 報價扇出靜止，前端連線狀態顯示正常（因為 SSE 還連著，只是沒有 tick） | §11 第 4 項；連線三態指示器須反映 listener 端而非只反映行情源端（`realtime-quotes.md` §3） |
| 9 | **Alembic `--autogenerate` 的產出直接上 prod** | 它對 `CHECK`、generated column、索引的偵測不完整，缺的東西不會有人通知你 | §7.2 |
| 10 | **備份檔被同步到公開分享的雲端資料夾** | 沒有任何系統會告訴你「你的持股明細現在是公開的」 | §3.4 |
| 11 | **PostgreSQL volume 掛在錯的路徑**（18 起 `PGDATA` 改了位置） | 容器照常啟動、資料庫照常運作，資料寫進**匿名 volume**，重建容器那天全部消失 | §3 釘死 `postgres:17-bookworm` |
| 12 | **WSL2 沒有在開機後被叫起來** | 所有排程「執行成功」（`wsl.exe` 會把發行版叫醒，但若失敗則靜默）、或根本沒被觸發，兩種都不會有人告訴你 | §1.1 的登入觸發項 + §5 的心跳（**心跳是這一條唯一的真防線**） |
| 13 | **Tailscale 金鑰 180 天後到期** | 半年後某天網站「連不上」，看起來像網站掛了 | §2.7 逐台關閉金鑰到期 |
| 14 | **走 `tailscale cert` 手動寫憑證檔** | 官方明文「you are responsible for renewing」，90 天後靜默過期 | §2.4 規定走 Caddy 自動取用那條 |
| 15 | **Tailscale 機器名取成「wife-laptop-securities」這類名字** | 它會原樣進入公開的 CT log，而且沒有任何提示 | §2.6 的硬性規則 |
| 16 | **`market_index_daily` 漏跑一天** | `MI_INDEX` 官方只給最新一日，回補做不到——漏跑的表現是「產業比較不可用」，看起來像資料還在累積、不像漏跑（[#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 補） | 步驟 ⑧ 的斷點告警（比對 `market_index_daily` 與 `benchmark_series` 的最新交易日），見 [`data-model.md`](./data-model.md) `market_index_daily` 與 [`analysis-dimensions.md`](./analysis-dimensions.md) §15.3 |

---

## 13. 必須寫成測試或驗收項的條目

| # | 條目 | 型態 |
|---|---|---|
| 1 | 盤後排程對同一天重複執行兩次，資料庫狀態與執行一次相同 | 測試（冪等性） |
| 2 | 資料庫刻意缺三個交易日後執行排程，三天全部補齊 | 測試（回補） |
| 3 | 收盤與基準序列的來源端點常數 == `www.twse.com.tw/...?response=open_data` | 契約測試 |
| 4 | 回傳日期 ≠ 預期最新交易日時，任務失敗且**不寫入資料庫** | 測試 |
| 5 | `api` 在 `quote-worker` 不存在時完整啟動並提供降級功能 | 測試（`tech-stack.md` §4 的既有要求，本票是第一個真的預設如此的環境） |
| 6 | `performance.md` §1.5 的「切換期間時單次載入 < 200 ms」在實際 PostgreSQL 版本與實際硬體上重測 | 驗收 |
| 7 | 每季還原演練：dump → 還原到 dev → 跑 `performance.md` §8A 的十一條不變量 | 驗收（定期） |
| 8 | 未登入時，所有回傳 Quote 的端點皆不可達 | 測試（法遵，`tech-stack.md` §8） |
| 9 | **Caddy 容器能取得 tailscaled 憑證**，從 tailnet 內的手機用 HTTPS 開得到首頁且無憑證警告 | 驗收（§2.4 的未查證接點，**階段 0 第一項**） |
| 10 | **重開機後**，不做任何手動操作，服務在 N 分鐘內自行恢復（WSL2 起來 → tailscaled 連上 → compose 服務就緒） | 驗收（§1.1、§2.7 兩顆定時炸彈的實測） |
| 11 | **PostgreSQL volume 確實掛在具名 volume 上**：`docker compose down && up` 後資料仍在 | 測試（§3 的第 11 條靜默失效） |

---

## 14. 仍未查證 / 留給實作階段

1. **盤後批次的最早可執行時點**——目前只有一個樣本（T+13.75h）。需在盤後 15:00 / 17:00 / 19:00 / 22:00 分別取樣，才能把 22:00 的保守下界往前挪。
2. **`performance.md` §1.5 的效能門檻在實際機器上的實測值**——#16 的數字來自本機 in-process PostgreSQL 16.2。
3. **#16 移交的兩項（`api` 冷啟動、跨服務 RTT）** ——**在 v1 不適用**（無 scale-to-zero、DB 同機）。上雲時才需要，屆時是原型票而非文件查證。
4. **Render Cron Job 的最小排程間隔**、**Supabase Supavisor 是否支援 `LISTEN/NOTIFY`**——兩次查證皆為「官方未載明」，只有實測能答。上雲選型時才需要。
5. **Caddy 容器如何取得 WSL2 主機上 tailscaled 的 socket**——官方未直接記載此組合。**列為階段 0 實作票的第一個驗收項**（§2.4）。
6. **工作排程器 `StartWhenAvailable` 是否適用於「無結束時間、無無限重複」的觸發程序**——官方文件互相矛盾（§4.0）。**這一項不影響設計**，因為 §4.1 的回補式規則不依賴補跑機制；但它決定了「電腦醒著卻錯過排程」時會不會自動補。
7. **睡眠／關機恢復後工作排程器的行為**——官方完全沒寫（§4.0）。
8. **只開憑證、未開 Funnel 時 `*.ts.net` 是否有公開 DNS 記錄**——官方未答（§2.6）。不影響存取控制。
9. **Docker 官方對 Windows 11 Home 的支援狀態**——安裝頁自相矛盾（§1.1）。**本形狀已繞開此題**（不用 Docker Desktop），保留紀錄是因為它會影響任何想改回 Docker Desktop 的人。
10. **WSL2 + Docker Engine 這套組合的實際資源佔用**——未量測。
