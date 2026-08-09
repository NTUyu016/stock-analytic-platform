# 本機部署事實查證：Tailscale、Caddy 憑證、Windows 工作排程器、Docker Desktop、PostgreSQL image

> 對應 issue：[#17 部署、環境與成本上限](https://github.com/NTUyu016/stock-analytic-platform/issues/17)（已定案為「v1 跑在使用者自己的 Windows 11 電腦上，對外靠 Tailscale 私有網路，不在路由器開任何埠」）
> 查證日期：**2026-08-09**（第三方定價、方案與文件會變，逾期請重驗）
> 同批查證的姊妹文件：[`deployment-facts-2026-08-09.md`](./deployment-facts-2026-08-09.md)（雲端 PaaS 那一側），本文沿用其格式與規則
>
> **本文只列事實，不做任何決策、不給任何推薦。** 比較可以，選擇不行。
> **本次未安裝 Tailscale、未開任何帳號、未改動任何系統設定、未實際部署。** 所有內容皆取自公開的官方文件頁面，無登入。
> 本文不含任何金鑰、帳號、tailnet 名稱或憑證。文中出現的 `tail<ID>.ts.net`、`yak-bebop.ts.net`、`pango-lin.ts.net`、`amelie-workstation` 等字串**全部是 Tailscale 官方文件自己的示例佔位字串**，與本專案無關。

---

## 0. 方法說明

本次全部以 `curl` 取原始 HTML、剝除標籤後閱讀，未依賴任何二手整理。這對三類頁面特別重要：

| 頁面 | 情形 |
|---|---|
| Tailscale KB／Docs | 內容為伺服器端渲染的靜態 HTML，`curl` 可完整讀取（頁面本身也提供 "View as Markdown"） |
| <https://hub.docker.com/_/postgres> | **Docker Hub 的說明是 JS 動態載入，`curl` 讀不到 tag 清單。** 改讀官方 image 說明的原始來源 <https://raw.githubusercontent.com/docker-library/docs/master/postgres/README.md>（Docker Hub 頁面的內容即由此產生） |
| <https://caddyserver.com/api/packages> | 官方套件登錄檔，回傳 JSON，可直接檢索某模組是否被官方收錄 |

---

## 1. Tailscale 免費方案（Personal）

### 1.1 額度（第一手，<https://tailscale.com/pricing>，2026-08-09）

定價頁 Personal 欄位原文：

| 項目 | 原文 |
|---|---|
| 價格 | **「$0 Free forever」** |
| 裝置數 | **「Unlimited user devices」** |
| 使用者數 | **「Up to 6 users」** |
| ACL 群組 | 「Up to 3 ACL groups」 |
| Tagged resources | 「Up to 50 tagged resources to start」 |
| Ephemeral resources | 「1,000 mins per month for ephemeral resources」 |
| 功能範圍 | 「Access nearly all of Tailscale's features」 |

同頁下方 "Compare plans" 表格逐格複述：Users 欄 Personal =「**$0 for up to 6 users**」；User Devices（"Computers, phones, etc."）欄 =「**Unlimited**」；ACL Groups = 3。

**「裝置」在 Tailscale 的計價模型裡分三種**，官方 FAQ 原文：

> 「A **user device** is simply anything that is not tagged as a resource! **User devices are free and unlimited.**」
> 「A **tagged resource** is a device that is owned by a tag rather than a user identity. You should tag resources like servers, subnet routers, app connectors, and other shared infrastructure.」
> 「**Ephemeral resources** are devices tagged as short-running resources... If an ephemeral device is present in the tailnet for more than four hours, it will not count against the minute pool, and will instead be counted as a standard tagged resource.」

超額價格（同頁 Add-ons）：**「Add more tagged resources ... $1 Per month for every tagged resource」**。

### 1.2 是否需要信用卡 —— **不需要**

<https://tailscale.com/kb/1182/billing-information>（2026-08-09）官方原文：

> 「**Billing information is only required for paid plans such as Standard, Premium, and Enterprise. If you're using the Personal plan, no billing details are needed.**」

### 1.3 誰會被判定為 Personal（這條會影響本專案）

<https://tailscale.com/pricing> FAQ 原文：

> 「Our Personal plan is for individuals who want to use Tailscale at home. This is a free plan and is **only suitable for non-commercial use** of Tailscale.」
> 「**If you create a tailnet with a public domain, such as Gmail, Apple, or a personal GitHub account, it's treated as personal use. These tailnets are automatically enrolled in the free Personal plan.**」
> 「**If you create a tailnet with a custom domain, it's considered business use, and you'll be automatically enrolled in a free trial.**」（可在 admin console 主動退出試用，退出後落到 Personal plan）
> 「If you sign up for Tailscale with your work email or other custom domains (e.g., @acme.com), then the Tailscale account is owned by the company or organization that owns and controls that email domain, regardless of which plan you are on.」

> 📌 使用者的登入信箱為 Gmail（`@gmail.com`），依上述原文屬 "public domain" → **自動落在 Personal plan**。

### 1.4 閒置裝置回收政策

| 問題 | 官方文件說什麼 |
|---|---|
| **一般（非 ephemeral）裝置會不會因閒置被自動移除** | **官方文件未載明任何自動回收機制。** <https://tailscale.com/docs/features/access-control/device-management/how-to/remove>（2026-08-09）全篇描述的都是**人工**移除：admin console 手動移除、或用 Tailscale API `DELETE /api/v2/device/{id}`。該頁甚至提供一段「依 last seen 日期批次刪除」的**範例腳本**，意即這件事需要使用者自己做。同頁另一條相關原文：「**If the Tailscale client is uninstalled on a device without any removal action, the device will not be removed from the tailnet**」 |
| **ephemeral 節點** | <https://tailscale.com/docs/features/ephemeral-nodes>（2026-08-09）：「They are **auto-removed from your network after a short period of inactivity**.」「They are immediately removed from your network if you run `tailscale logout`.」「They can only be created using **ephemeral auth keys**... or by running the `tailscaled` daemon with the `state=mem:` flag.」→ **必須主動使用 ephemeral auth key 才會變成 ephemeral 節點**，一般安裝不會 |
| **金鑰到期（最接近「會自己斷掉」的機制）** | <https://tailscale.com/kb/1028/key-expiry>（2026-08-09）：「users need to periodically reauthenticate on each of their devices. **By default, new domains are set with an expiry period of 180 days.**」「**If reauthentication does not occur, keys expire and connections to/from the given endpoint will stop working.**」可逐台「Disable Key Expiry」（**所有方案皆可用**），亦可在 Device management 頁把週期設為 1–180 天。**Tagged 裝置**：「When you apply a tag to a device for the first time and authenticate it, the tagged device will have **key expiry disabled by default**」 |

> **對本專案形狀最直接的一條**：一台 24/7 的家用伺服器若維持預設設定，**180 天後金鑰到期、連線停止工作**，而且這是靜默的（不會有失敗的排程 run）。官方提供的解法是逐台關閉 key expiry。這與 `deployment-facts-2026-08-09.md` §8.1 記載的「GitHub Actions public repo 60 天自動停用」是同一種形狀的可預期靜默失效。

### 1.5 一條與「Windows 上跑 24/7」直接相關的事實

<https://tailscale.com/kb/1088/run-unattended>（2026-08-09）原文：

> 「On Linux, Tailscale runs as the system, and is available even when no users are logged in. **For other platforms Tailscale runs as the logged in user, not as the system. This means that if a device is restarted, or multiple users are logged in at the same time, Tailscale won't automatically connect.**」
> 「On Windows, you can solve this by using "**Run Unattended**" mode. This configures Tailscale to run as the system instead of the currently logged in user.」
> 設定路徑：系統匣圖示 → Preferences → Run unattended；或命令列 `tailscale up --unattended=true`。「You may be required to be logged in as a user with elevated permissions for this to work properly.」

---

## 2. Tailscale 的 HTTPS 憑證

**主要來源**：<https://tailscale.com/kb/1153/enabling-https>（頁面標示 Last validated: Dec 10, 2025）與 <https://tailscale.com/kb/1080/cli/cert>（Last validated: Jul 30, 2026），皆於 2026-08-09 讀取。

### 2.1 啟用前提（tailnet 層設定，**必須開**）

官方步驟原文：

> 1. Open the DNS page of the admin console.
> 2. **Enable MagicDNS if not already enabled for your tailnet.**
> 3. Under **HTTPS Certificates**, select **Enable HTTPS**.
> 4. **Acknowledge that your machine names and your tailnet DNS name will be published on a public ledger.**
> 5. For each machine you are provisioning with a TLS certificate, run `tailscale cert` on the machine to obtain a certificate.

**→ 是的，需要開啟 tailnet 層的 HTTPS 設定，而且需要開 MagicDNS，而且第 4 步是一個明確的「我知道名字會被公開」的同意動作。**

同頁另一條：

> 「You **cannot** obtain an HTTPS URL to go to a bare hostname, such as `https://machine-name`. If you obtain a TLS certificate for a node using MagicDNS, it will be accessible at both `https://machine-name.tail<ID>.ts.net`, using HTTPS, and also at `http://machine-name`, **without HTTPS** but using MagicDNS as a DNS nameserver.」

### 2.2 `tailscale cert` 產出什麼

<https://tailscale.com/kb/1080/cli/cert>（2026-08-09）原文與旗標：

> 「**Generate Let's Encrypt certificate and key files on the host** for HTTPS certificates in your tailnet.」
> 「If you are trying to serve a folder of files or reverse proxy to an HTTP service, **use the `tailscale serve` command instead**.」
> 用法：`tailscale cert hostname.<tailnet>.ts.net`
> 「Alternatively, if you want to save the certificate and private key to files, you can use the `--cert-file` and `--key-file` arguments」：`tailscale cert --cert-file=cert.pem --key-file=key.pem hostname.<tailnet>.ts.net`

| 旗標 | 官方說明 |
|---|---|
| `--cert-file=<cert>` | Specify the certificate output path. |
| `--key-file=<key>` | Specify the private key output path. |
| `--min-validity=<duration>` | Request a specified minimum remaining validity on the returned certificate（可用 `time.ParseDuration` 格式；「If you specify a duration longer than the certification lifetime set by Let's Encrypt, it uses the maximum lifetime set by Let's Encrypt」） |
| `--serve-demo` | Serve on port `:443` using the cert as a demo, instead of writing out the files to disk. |

**→ 產出的是「憑證檔 + 私鑰檔」兩個檔案，路徑由 `--cert-file` / `--key-file` 指定。**
⚠️ **不給旗標時的預設輸出檔名與路徑，官方兩個頁面都未載明 → 未能查證。**（官方示例一律顯式指定 `cert.pem` / `key.pem`。）

### 2.3 簽發者、有效期、續期

| 問題 | 官方原文 |
|---|---|
| 是否 Let's Encrypt | **是。**「Using `tailscale cert` (with sudo as needed), Tailscale will automatically request a certificate for this machine on this domain, **using Let's Encrypt**.」 |
| 驗證方式 | 「Tailscale creates a `*.ts.net` DNS **TXT** record for your nodes to complete their **DNS-01 challenges**.」→ **不需要任何對外開放的埠** |
| 私鑰去向 | 「Your certificate's private key and your Let's Encrypt (ACME) account's private key are **generated and stored locally on your machine and Tailscale never sees them**.」 |
| 有效期 | 「The certificates provided by Let's Encrypt have a **90 day expiry** and require periodic renewal.」 |
| **續期（關鍵）** | 「When a certificate is delivered as files on disk which you then move to an install location, **such as when using `tailscale cert`, the `tailscaled` daemon doesn't know where to place a renewed certificate nor how to install it. So for any certificates that you create using `tailscale cert`, you are responsible for renewing the certificate.**」 |
| 什麼情況會自動續期 | 「**If a certificate is handled without the user initiating any file-based certificate installation, such as when using the Caddy integration of Tailscale, then the certificate will automatically be renewed without the user doing anything.**」 |
| 速率限制 | 「It is possible to frequently request a new certificate and exceed Let's Encrypt's rate limits. As a result, **you may find yourself waiting 34 hours until you can try again.**」 |
| 停用 HTTPS 的後果 | 「If HTTPS is disabled, **the certificates for your machines are not revoked**... **You also cannot invalidate a certificate for a single machine.**」 |

> 📌 **這裡有一個乾淨的二分，值得原文照抄進規格**：`tailscale cert` 寫檔 → **自己負責續期**；由程式向本機 tailscaled 取憑證（官方明列的例子就是 Caddy 整合）→ **自動續期**。90 天到期日這件事，[`tech-stack.md`](../spec/tech-stack.md) §8 已經寫過「TLS 憑證的申請與續期是那種『會在半夜三點過期時咬你』的東西」——在 Tailscale 情境下，這句話只對「寫檔」那一半成立。

### 2.4 Certificate Transparency：`*.ts.net` 會不會進 CT log，會洩漏什麼

**會進。** <https://tailscale.com/kb/1153/enabling-https> 有一整節在講這件事，逐句原文：

> 「**All TLS certificates on the web are recorded in the Certificate Transparency (CT) append-only public ledger, which anyone can access to verify the validity of public certificates. Notably, this includes the fully qualified domain name of your devices.**」
> 「**To avoid publicizing your organization name, such as your corporate domain, email address, or GitHub username, Tailscale provides you with a tailnet name.** Each tailnet has a tailnet DNS name like `tail<NNNN>.ts.net` or `tailnet-<NNNN>.ts.net`, but you can also generate and select a randomized tailnet DNS name generated by Tailscale, like `yak-bebop.ts.net`.」
> 「TLS certificates are issued based in your tailnet name. Right now, **we don't permit changing your tailnet name** (other than between your default tailnet DNS name and your randomly generated tailnet name).」
> 「**Although the certificate domain obscures the owner of the tailnet, the machine names are still published in the public ledger. Do not enable the HTTPS feature if any of your machine names contain sensitive information.** You can edit your machine name before obtaining a certificate.」
> 「**The public ledger only provides information about the names of the TLS certificates; access to your devices is still restricted by Tailscale as normal.** Additionally, **only devices where you run `tailscale cert` will have their certificate in the public ledger.**」

**tailnet DNS name 長什麼樣**（<https://tailscale.com/docs/concepts/tailnet-name>，2026-08-09）：

> 「When you create a new tailnet, Tailscale assigns it a DNS name with the format **`tail<ID>.ts.net`, where `<ID>` is a randomly generated hexadecimal string**」；亦可改成隨機字組（如官方示例 `cat-crocodile.ts.net`）。
> 「**After you use a randomized name for HTTPS certificates, you cannot re-generate it.**」

**所以進 CT log 的具體字串是**：`<機器名>.<tailnet DNS 名>.ts.net`，其中 tailnet DNS 名對 Gmail 註冊者而言是**隨機十六進位字串或隨機字組**，不含使用者的 email、網域或 GitHub 帳號；機器名則是**使用者自訂、且會原樣公開**。

**對既有記載「網域進 CT log 後數小時內必有掃描器」的交互作用（只列事實，不裁決）**：

[`auth.md`](../spec/auth.md)「要付的帳」一節寫：「Caddy 申請 Let's Encrypt 憑證時，網域名稱會被寫進 Certificate Transparency log，公開可查詢，且有人專門監看 CT log 尋找新上線的網域。上線後數小時內一定會有掃描器來敲 `/wp-login.php`、`/.env`、`/admin`。」對照本次查到的官方事實：

| 環節 | 官方可查證的事實 |
|---|---|
| 名字會不會被公開 | **會。**「All TLS certificates on the web are recorded in the CT append-only public ledger」「this includes the fully qualified domain name of your devices」 |
| 公開的名字會不會洩漏「這是誰」 | 官方明文設計成不會：tailnet 名是隨機字串，「To avoid publicizing your organization name, such as your corporate domain, email address, or GitHub username」。**但機器名會原樣公開**，官方明文警告「Do not enable the HTTPS feature if any of your machine names contain sensitive information」 |
| 掃描器拿到名字之後能不能連上 | 官方對此的唯一表述是：「**access to your devices is still restricted by Tailscale as normal**」。另據 <https://tailscale.com/docs/reference/dns-in-tailscale>（2026-08-09）在講「把 Tailscale 位址發佈到自己的公開 DNS」時的原文：「The DNS names can be looked up (converted to a private IP address) by anyone on the internet, but **because Tailscale IP addresses are only accessible to users of your network, this is relatively harmless.**」 |
| **`<機器名>.<tailnet>.ts.net` 這個名字在公開 DNS 上解不解得出來** | ⚠️ **未能查證。** MagicDNS 的官方描述是 tailnet 內的解析機制（「MagicDNS automatically registers DNS names for devices in your network」；`dns-in-tailscale` 亦稱 MagicDNS 在本機解析）。而 Funnel 文件明確提到會有**公開 DNS 記錄**（「Public DNS records can take up to **10 minutes** to show up for your tailnet domain」）。**「只開 HTTPS 憑證、沒開 Funnel 的節點，其 `*.ts.net` 名稱是否存在公開 DNS 記錄」官方文件未直接回答。** |

> **一句話的事實整理（非結論）**：CT log 這條路徑在 Tailscale 情境下**依然成立**（名字照樣公開），但官方明文主張其後果被兩件事限縮——tailnet 名是隨機的、以及裝置的可達性由 Tailscale 而非網域名稱決定。**「掃描器敲得到嗎」這一步取決於上表最後一列那個未查證的問題。**

---

## 3. Caddy 如何使用 Tailscale 憑證

### 3.1 做法 A：什麼都不做（Caddy 原生支援，官方雙邊都有文件）

**Caddy 官方**（<https://caddyserver.com/docs/automatic-https>，2026-08-09，"Activation → Special cases" 節）原文：

> 「**Domains ending in `.ts.net` will not be managed by Caddy. Instead, Caddy will automatically attempt to get these certificates at handshake-time from the locally-running Tailscale instance. This requires that HTTPS is enabled in your Tailscale account and the Caddy process must either be running as root, or you must configure `tailscaled` to give your Caddy user permission to fetch certificates.**」

**Tailscale 官方**（<https://tailscale.com/kb/1190/caddy-certificates>，Last validated: Jan 5, 2026，2026-08-09 讀取）原文：

> 「Starting with the beta release of **Caddy 2.5**, Caddy supports Tailscale. **When Caddy gets an HTTPS request for a `*.ts.net` site, it gets the HTTPS certificate from the machine's local Tailscale daemon. There's no configuration required for the certificate.**」
> 官方示例 Caddyfile（原樣）：
> ```
> machine-name.domain-alias.ts.net
> root * /var/www
> file_server
> ```
> 「**Provide non-root users with access to fetch certificate** — If Caddy is running as a non-root user, such as when it runs on **Debian** as `caddy`, you need to modify `/etc/default/tailscaled` to grant the user access to fetch the certificate. In `/etc/default/tailscaled`, set the **`TS_PERMIT_CERT_UID`** environment variable to the name or ID of the non-root user：`TS_PERMIT_CERT_UID=caddy`」

**這條路的性質**：憑證由 Caddy 在 TLS handshake 當下向本機 tailscaled 取得，**不寫檔**，因此落在 §2.3 那句「automatically be renewed without the user doing anything」的那一半——`tailscale cert` 的手動續期責任不適用。Tailscale 的 §2.3 原文正是以 "such as when using the Caddy integration of Tailscale" 作為自動續期的例子。

**已知限制／未載明處**：
- 需要 tailnet 已開啟 HTTPS（§2.1）。
- 權限模型只有 Linux 路徑的文件（`/etc/default/tailscaled`、`TS_PERMIT_CERT_UID`、Debian 的 `caddy` 使用者）。**Windows 上 Caddy 以何種身分才能向本機 tailscaled 取憑證，兩邊官方文件皆未載明 → 未能查證。**
- 「Caddy 跑在容器內、tailscaled 跑在 Windows 主機上」時能否取得憑證，**官方文件未載明 → 未能查證**（官方措辭一律是 "the machine's local Tailscale daemon" / "locally-running Tailscale instance"）。

### 3.2 做法 B：Caddyfile 手動指定 `tls <cert> <key>`

技術上與 §2.2 的 `tailscale cert --cert-file=... --key-file=...` 直接對應（Caddy 的 `tls` 指令屬標準 Caddyfile directive，見 <https://caddyserver.com/docs/caddyfile/directives/forward_auth> 頁尾的標準指令清單中列有 `tls`）。

**代價是官方明文的**：走寫檔路徑 → §2.3「**you are responsible for renewing the certificate**」，且 90 天到期。
⚠️ **Caddy 官方文件未把「搭配 `tailscale cert` 手動指定憑證」列為一種受支援的用法**（`.ts.net` 在 Caddy 那裡是被特別處理成做法 A 的）。此組合**官方未載明 → 未能查證其行為**（例如手動 `tls` 是否會與 `.ts.net` 的 special case 互相覆蓋）。

### 3.3 做法 C：`caddy-tailscale` 外掛

<https://github.com/tailscale/caddy-tailscale>（README，2026-08-09）：

> 徽章：**`status: experimental`**；內文：「**This plugin is still very experimental.**」
> 「The Tailscale plugin for Caddy allows **running a Tailscale node directly inside of the Caddy web server**. This allows a caddy server to join your Tailscale network directly **without needing a separate Tailscale client**.」
> 提供四件東西：network listener、proxy transport、authentication provider、subcommand。
> **官方自己在 README 的 "Why" 一節說明何時「不需要」它**：「It's important to note that **you don't necessarily need this plugin to use Caddy with Tailscale.** With Tailscale installed on a machine, Caddy can already bind to the Tailscale network interface, proxy requests to other Tailnet nodes, **get automatic certificates**, and authenticate Tailscale users. However, there may be cases where it is inconvenient to install Tailscale on a machine... Or, you may want to serve multiple sites, each connected as a separate Tailnet node.」
> 建置方式：`xcaddy build v2.9.1 --with github.com/tailscale/caddy-tailscale`（需 `TS_AUTHKEY`）。

⚠️ **本次查 <https://caddyserver.com/api/packages>（Caddy 官方套件登錄檔，2026-08-09）：全檔中與 tailscale 相關的項目只有第三方的 `go.akpain.net/caddy-tailscale-auth`，`github.com/tailscale/caddy-tailscale` 不在登錄檔內。** 也就是說**這個外掛不能從 Caddy 官方下載頁勾選建置**，只能自行 `xcaddy`。

### 3.4 做法 D（不是憑證，是身分）：Caddy `forward_auth` + `tailscale-nginx-auth`

<https://caddyserver.com/docs/caddyfile/directives/forward_auth>（2026-08-09）內含一段官方 Tailscale 範例，透過 unix socket（`...tailscale.nginx-auth.sock`）向 `/auth` 驗證，並以 `copy_headers` 把 `Tailscale-User` / `Tailscale-Name` / `Tailscale-Login` / `Tailscale-Tailnet` / `Tailscale-Profile-Picture` 轉成 `X-Webauth-*`。官方註記該元件「currently named `nginx-auth`, but it still works with Caddy」。

> 這與憑證無關，列在這裡是因為它與 §4 的 `tailscale serve` identity headers 是同一類機制的兩種實作。**本文不評價它與 [`auth.md`](../spec/auth.md) §1「認證發生在應用層」決策的關係。**

### 3.5 沒有公開的 80/443 埠時，HTTP-01 與 TLS-ALPN 為何走不通

直接引用 [`deployment-facts-2026-08-09.md`](./deployment-facts-2026-08-09.md) §7.1 已查證的 Caddy 官方原文（<https://caddyserver.com/docs/automatic-https>）：

| Challenge | 官方原文的埠需求 |
|---|---|
| **HTTP challenge（HTTP-01）** | 「requests a temporary cryptographic resource over port **80** using HTTP」、「**requires port `80` to be externally accessible**」 |
| **TLS-ALPN challenge** | 「requests a temporary cryptographic resource over port **443** using a TLS handshake」、「**requires port `443` to be externally accessible**」 |
| **DNS challenge（DNS-01）** | 「**does not require any open ports, and the server requesting a certificate does not need to be externally accessible**」 |

以及自動 HTTPS 生效的條件原文：「If your domain's **A/AAAA records point to your server**, ports `80` and `443` are open externally, Caddy can bind to those ports... then sites will be served over HTTPS automatically.」

**→ 在「不在路由器開任何埠」的前提下，HTTP-01 與 TLS-ALPN 兩者的官方前置條件（80／443 externally accessible）在定義上就不成立。** 剩下的兩條官方路徑是：
1. **DNS-01**（官方明文「does not require any open ports」）——適用於自有的公開網域，需對應的 `caddy-dns/*` 外掛。
2. **`.ts.net` 的 special case**（§3.1）——Caddy 根本不跑 ACME，改向本機 tailscaled 拿；而 Tailscale 自己那一側用的也是 DNS-01（§2.3），由 Tailscale 代為建立 `*.ts.net` TXT 記錄。

---

## 4. `tailscale serve` 與 `tailscale funnel`

來源：<https://tailscale.com/kb/1312/serve>（Last validated: Jan 20, 2026）、<https://tailscale.com/kb/1242/tailscale-serve>（Last validated: Jan 26, 2026）、<https://tailscale.com/kb/1223/funnel>（Last validated: Jan 20, 2026），皆 2026-08-09 讀取。

### 4.1 兩者的差別

| | `tailscale serve` | `tailscale funnel` |
|---|---|---|
| 對誰開放 | 「route traffic **from other devices on your Tailscale network**」——**僅 tailnet 內**（含被 share 的外部使用者） | 「route traffic **from the broader internet**」——**公開網際網路，對方不需要 Tailscale** |
| 預設狀態 | 需 tailnet 開啟 HTTPS；CLI 會引導開啟 | 「**Tailscale Funnel is disabled by default**」；另需 tailnet policy file 的 `funnel` node attribute |
| 成熟度 | 未標註 beta | 「Tailscale Funnel is currently **in beta**」；「available for **all plans**」 |
| 可用埠 | 未限制（`--https=<port>` / `--http=<port>` / `--tcp=<port>`） | 「Funnel can only listen on ports **443, 8443, and 10000**」 |
| 身分標頭 | **有**：`Tailscale-User-Login`、`Tailscale-User-Name`、`Tailscale-User-Profile-Pic`（v1.92+ 另有 `Tailscale-App-Capabilities`）。「If Serve finds the following headers on an incoming request, **it will remove them for security reasons, to avoid header spoofing**」 | **沒有**：「Funnel traffic, which is publicly available, **does not include identity headers**」 |
| 頻寬 | 未提及限制 | 「Traffic sent over a Funnel is subject to **non-configurable bandwidth limits**」（未給數字） |
| DNS | 「DNS names are **restricted to your tailnet's domain name** (`device-name.tailnet-name.ts.net`)」 | 同樣限於 tailnet 網域；且「**Public DNS records can take up to 10 minutes**」 |
| 同一埠 | 官方明文：「**The same port number cannot be used for Serve and Funnel at the same time.** If the most recent command to configure the port was `serve`, then the port will be **completely private**. If... `funnel`, then the port will be **completely public**.」 |

### 4.2 `serve` 是否已內建 HTTPS 與反向代理 —— **兩者都是，官方明文**

<https://tailscale.com/kb/1242/tailscale-serve>（2026-08-09）原文：

> 「The serve offers an **HTTPS and HTTP server** that has a few modes: **a reverse proxy, a file server, and a static text server**. **HTTPS traffic uses an automatically provisioned TLS certificate. By default, the device's Tailscale daemon terminates the HTTPS connection.**」

官方示例輸出（原樣）：

```
tailscale serve 3000
Available within your tailnet:
https://amelie-workstation.pango-lin.ts.net
|-- / proxy http://127.0.0.1:3000
Press Ctrl+C to exit.
```

**能力清單（逐條原文）**：

| 能力 | 原文 |
|---|---|
| 反向代理 | 「To serve as a reverse proxy to a local backend, provide the location of the `<target>` argument... **Note that only `http://127.0.0.1` is supported for proxies.**」目標可寫成 `3000`、`localhost:3000`、`tcp://localhost:3000/foo`、`https+insecure://localhost:3000/foo` |
| 路徑掛載 | `--set-path=<path>`：「Is a slash-separated URL path. The root-level mount point would be `/`... **For more information on how these path patterns are matched, refer to the Go `ServeMux` documentation. Our mount points behave similarly.**」 |
| 靜態檔 | 「Provide a full, absolute path to the file or directory of files you wish to serve. **If you specify a directory, this renders a directory listing with links to files and subdirectories.**」（macOS 上僅 open source variant 可用） |
| 純文字 | `text:"Hello, world!"` |
| TCP／TLS 終結 | `--tcp=<port>`、`--tls-terminated-tcp=<port>`、`--proxy-protocol=<version>` |
| 背景執行與重開機 | 「If you use the `tailscale serve` command with the **`-bg`** flag, it runs persistently in the background until you disable it. **When you reboot the device or restart Tailscale... Serve automatically resumes sharing.**」「**If you use the `tailscale serve` command without the `-bg` flag, then reboot the device... you must restart Serve manually.**」 |
| 憑證續期 | 落在 §2.3 的「非寫檔」那一半：`tailscale cert` 的 CLI 頁面自己就寫「If you are trying to serve a folder of files or reverse proxy to an HTTP service, **use the `tailscale serve` command instead**」 |

**官方文件中「未出現」的能力（誠實標註，不做推論）**：
- `tailscale serve` 的文件**未出現** SPA fallback（Caddy 的 `try_files {path} /index.html`，見 [`tech-stack.md`](../spec/tech-stack.md) §8）這類重寫規則；靜態目錄的行為官方描述為 "**renders a directory listing**"。**「serve 能否做到 SPA 的 catch-all 回 `index.html`」官方未載明 → 未能查證。**
- **未出現** gzip/brotli 壓縮、快取標頭、自訂 header、access log 等反向代理／靜態伺服器常見設定的說明。**未能查證。**
- WebSocket：serve 文件**未提及** WebSocket 是否受支援（[#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) 的推播機制會用到）。**未能查證。**

> **本節只列事實，不下結論。** 「本專案是否還需要 Caddy」屬於決策，不在本文範圍。

---

## 5. Windows 11 工作排程器

> 工作排程器 UI 的中文／英文選項名稱，在官方 API 文件中對應的是屬性名稱。以下三份第一手文件描述的是同一個設定：UI 的「**Run task as soon as possible after a scheduled start is missed**」＝ XML 的 `<StartWhenAvailable>` ＝ COM 的 `ITaskSettings::StartWhenAvailable` ＝ 指令碼的 `TaskSettings.StartWhenAvailable`。

### 5.1 `StartWhenAvailable`（錯過排程後補跑）

<https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-startwhenavailable>（2026-08-09）原文：

> 「If **True**, the property indicates that the Task Scheduler **can start the task at any time after its scheduled time has passed**. **The default is False.**」
> 「**This property applies only to time-based tasks with an end boundary or time-based tasks that are set to repeat infinitely.**」
> 「**Tasks that are started after the scheduled time has passed (because of the `StartWhenAvailable` property being set to True) are queued in the Task Scheduler service's queue of tasks and they are started after a delay. The default delay is 10 minutes.**」

<https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-itasksettings-get_startwhenavailable>（2026-08-09）的 Remarks **逐字相同**。

⚠️ **兩份官方文件對「適用範圍」的措辭不一致**：
- 上述兩頁：「applies only to time-based tasks **with an end boundary** or time-based tasks that are set to **repeat infinitely**」
- <https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-startwhenavailable-settingstype-element>（2026-08-09）：「**This property applies only to timed tasks.**」（無附加條件）

**本文兩者並陳，不裁決哪一個是現行行為。** 但這個差異有實務後果：若前者為準，一個「每個交易日 14:00 執行、沒有結束時間、也沒有設成無限重複」的觸發程序**可能不在該設定的適用範圍內**。**→ 需人工確認。**

⚠️ **「電腦從睡眠／關機恢復後會不會補跑」——官方 Task Scheduler 文件未直接回答 → 未能查證。** 三份頁面只說明「排入服務佇列、延遲後啟動、預設延遲 10 分鐘」，**未描述開機、resume-from-sleep 或 resume-from-hibernate 時的行為**。（Microsoft Q&A 上有大量社群討論，但那不是第一手官方文件，本文不採信。）

### 5.2 `WakeToRun`（喚醒電腦執行）

<https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-waketorun> 與 <https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-waketorun-settingstype-element>（皆 2026-08-09），Remarks 逐字相同且**極短**：

> 「If **True**, the property indicates that the **Task Scheduler will wake the computer when it is time to run the task**.」
> 「**When the Task Scheduler service wakes the computer to run a task, the screen may remain off even though the computer is no longer in the sleep or hibernate mode.** The screen will turn on when Windows Vista detects that a user has returned to use the computer.」

**官方 Task Scheduler 文件對 `WakeToRun` 就只有這些。** 沒有提到電源設定的相依性、沒有提到硬體需求、沒有提到關機（S5）狀態。

**唯一可用的第一手補充**來自電源工具文件 <https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options>（2026-08-09），`/waketimers` 的說明：

> 「Enumerates the active wake timers. **If enabled, the expiration of a wake timer wakes the system from sleep and hibernate states.**」

**→ 官方對 wake timer 的作用範圍明文寫的是「sleep and hibernate states」，未包含關機（shutdown）。** 但**「`WakeToRun` 是否即以 wake timer 實作、以及它是否受『允許使用喚醒計時器』電源原則管轄」，Task Scheduler 官方文件未載明 → 未能查證。**

⚠️ **「電腦已關機時 `WakeToRun` 會不會開機」——官方文件未載明 → 未能查證。**

### 5.3 相關但本次未展開

`schtasks` 命令列的對應旗標（<https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create>）本次**未逐一查證**。

---

## 6. Docker Desktop on Windows 11 Home

### 6.1 授權：個人使用免費（第一手，<https://docs.docker.com/subscription/desktop-license/>，2026-08-09）

官方原文：

> 「Docker Desktop is licensed under the **Docker Subscription Service Agreement**. When you download and install Docker Desktop, you're asked to agree to these terms.」
> 「The Docker Subscription Service Agreement states: **Docker Desktop is free for:**
> - **Small businesses (fewer than 250 employees AND less than $10 million in annual revenue)**
> - **Personal use**
> - **Education**
> - **Non-commercial open source projects**」
> 「**Docker Desktop requires a paid subscription for:** Professional use in larger organizations／Government entities／Commercial use beyond the free tier limits」
> 「Paid subscriptions that include Docker Desktop: Docker Pro, Team, and Business subscriptions」

**→ 門檻是「員工數 < 250 **且** 年營收 < US$10M」的小型企業，或**個人使用**。本專案是個人自用 → 落在 "Personal use"。**

### 6.2 Windows 11 **Home** 是否受支援 —— **官方頁面自相矛盾，需人工確認**

<https://docs.docker.com/desktop/setup/install/windows-install/>（2026-08-09）。同一頁上有兩段互相牴觸的敘述：

**(a) 「System requirements → WSL 2 backend, x86_64」分頁列出的作業系統版本**（原文）：

> 「WSL version 2.1.5 or later... **Windows 10 64-bit: Enterprise, Pro, or Education version 22H2 (build 19045). Windows 11 64-bit: Enterprise, Pro, or Education version 23H2 (build 22631) or higher.** The Windows Server service (LanmanServer) must be enabled and its start mode set to Automatic. Turn on the WSL 2 feature on Windows.」
> 硬體：「64-bit processor with Second Level Address Translation (SLAT)／**8GB system RAM**／Enable hardware virtualization in BIOS/UEFI」

**→ 這份清單裡沒有 Home。** 本次以 `grep` 檢查該頁原始 HTML，全頁只出現一次 `Windows 11 64-bit:` 字串，內容即上引，**確認不是文字抽取遺漏**。

**(b) 同一頁「Important」提示框**（原文）：

> 「To run **Windows containers**, you need Windows 10 or Windows 11 **Professional or Enterprise** edition. **Windows Home or Education editions only allow you to run Linux containers.**」

**→ 這句話的前提是 Home 版可以跑 Linux 容器。**

⚠️ **兩段敘述無法同時成立，官方頁面未加以協調。**「Windows 11 **Home** + WSL 2 backend 是否為官方支援組態」**未能查證，需人工確認**（例如向 Docker 官方支援求證，或以實機安裝結果為準——**本次授權範圍不含安裝**）。

### 6.3 其他同頁事實（安裝模式，2026-08-09）

| | Per-user（官方標為 recommended，安裝程式預設） | All users |
|---|---|---|
| 安裝位置 | `%LOCALAPPDATA%\Programs\DockerDesktop` | `C:\Program Files\Docker\Docker` |
| 安裝所需管理員權限 | **Not required** | Required |
| 更新所需管理員權限 | **Not required** | Required |
| Linux 容器後端 | **WSL 2 only** | WSL 2 or Hyper-V |
| Windows 容器 | Not supported | Supported |
| 安全性 | 「Smaller attack surface; **no privileged system service installed**」 | 「Requires privileged system service; broader access to host resources」 |

另兩條原文：

> 「Note that **Hyper-V is only available with all-users installation**. If you install Docker Desktop in per-user mode, **WSL 2 is the only supported backend**.」
> 「Docker only supports Docker Desktop on Windows for those versions of Windows that are still within **Microsoft's servicing timeline**.」

⚠️ **本文未查證「不裝 Docker Desktop、直接在 WSL2 內裝 Docker Engine」這條路徑的官方立場**（Docker Engine 為 Apache-2.0 的開源專案，授權與 Docker Desktop 不同——同頁 Note 原文：「**The licensing and distribution terms for Docker and Moby open-source projects, such as Docker Engine, aren't changing.**」）。**本文不評價這條路徑，僅記錄其存在與上述原文。**

---

## 7. PostgreSQL 官方 Docker image

**來源**：<https://raw.githubusercontent.com/docker-library/docs/master/postgres/README.md>（Docker Hub `_/postgres` 頁面的內容來源，2026-08-09 讀取）。

### 7.1 目前的穩定主版本與 Debian 基底標籤

| 主版本 | 代表標籤 | Debian（Trixie = Debian 13） | Debian（Bookworm = Debian 12） |
|---|---|---|---|
| **18**（`latest`） | `18.4`、`18`、**`latest`** | `18.4-trixie`、`18-trixie`、`trixie` | `18.4-bookworm`、`18-bookworm`、`bookworm` |
| 17 | `17.10`、`17` | `17.10-trixie`、`17-trixie` | `17.10-bookworm`、`17-bookworm` |
| 16 | `16.14`、`16` | `16.14-trixie`、`16-trixie` | `16.14-bookworm`、`16-bookworm` |
| 15 | `15.18`、`15` | `15.18-trixie`、`15-trixie` | `15.18-bookworm`、`15-bookworm` |
| 14 | `14.23`、`14` | `14.23-trixie`、`14-trixie` | `14.23-bookworm`、`14-bookworm` |
| 19（**beta**） | `19beta2`、`19beta2-trixie` | — | `19beta2-bookworm` |

- **`latest` 目前指向 `18.4` / `18-trixie`，即 Debian Trixie 基底。**
- 官方對這些代號的說明（原文）：「Some of these tags may have names like **bookworm** or **trixie** in them. These are the **suite code names for releases of Debian** and indicate which release the image is based on. **If your image needs to install any additional packages beyond what comes with the image, you'll likely want to specify one of these explicitly to minimize breakage when there are new releases of Debian.**」
- Alpine 變體同時存在（`18-alpine3.24` 等），官方對其警告原文：「The main caveat to note is that **it does use musl libc instead of glibc and friends**, so software will often run into issues depending on the depth of their libc requirements/assumptions.」→ 與 [`tech-stack.md`](../spec/tech-stack.md) §9「base image 必須是 Debian」的理由同源。**預設（無字尾）的 `postgres` 標籤本身就是 Debian 基底，非 Alpine。**

### 7.2 PostgreSQL 18 起 `PGDATA` 與 `VOLUME` 路徑改變（會直接影響掛載寫法）

官方 README 的 **Important Change** 原文：

> 「the `PGDATA` environment variable of the image was changed to be **version specific in PostgreSQL 18 and above**. For 18 it is **`/var/lib/postgresql/18/docker`**. Later versions will replace `18` with their respective major version... **The defined `VOLUME` was changed in 18 and above to `/var/lib/postgresql`. Mounts and volumes should be targeted at the updated location.** This will allow users upgrading between PostgreSQL major releases to use the faster `--link` when running `pg_upgrade` and mounting `/var/lib/postgresql`.」

以及對 **17 以下** 的 Important Note 原文：

> 「(for PostgreSQL 17 and below) **Mount the data volume at `/var/lib/postgresql/data` and not at `/var/lib/postgresql`** because mounts at the latter path **WILL NOT PERSIST database data** when the container is re-created. The Dockerfile that builds the image declares a volume at `/var/lib/postgresql/data` and **if no data volume is mounted at that path then the container runtime will automatically create an anonymous volume that is not reused across container re-creations. Data will be written to the anonymous volume rather than your intended data volume and won't persist when the container is deleted and re-created.**」

> 📌 **這是一個版本相依的陷阱**：掛載路徑在 PG 18 前後不同，掛錯會導致「看起來有掛、其實寫進匿名 volume、重建容器就沒了」。

另一條同頁的執行參數：

> 「the default `/dev/shm` size for containers is **64MB**. If the shared memory is exhausted you will encounter `ERROR: could not resize shared memory segment...: No space left on device`. You will want to pass **`--shm-size=256MB`** for example to `docker run`, or alternatively in `docker compose`.」

### 7.3 資料持久化：named volume vs bind mount

**postgres 官方 image 文件的立場：兩者並陳，未表態。** README「Where to Store Data」原文：

> 「**We encourage users of the `postgres` images to familiarize themselves with the options available**, including:
> - Let Docker manage the storage of your database data by writing the database files to disk on the host system using its own internal volume management. **This is the default and is easy and fairly transparent to the user. The downside is that the files may be hard to locate for tools and applications that run directly on the host system**, i.e. outside containers.
> - Create a data directory on the host system (outside the container) and mount this to a directory visible from inside the container. **This places the database files in a known location on the host system**... **The downside is that the user needs to make sure that the directory exists, and that e.g. directory permissions and other security mechanisms on the host system are set up correctly.**」
> 「The Docker documentation is a good starting point for understanding the different storage options... **We will simply show the basic procedure here for the latter option**」：`docker run --name some-postgres -v /my/own/datadir:/var/lib/postgresql -e POSTGRES_PASSWORD=... -d postgres:tag`

**Docker 本身的立場則有明確傾向**（<https://docs.docker.com/engine/storage/volumes/>，2026-08-09）：

> 「**Volumes are the preferred mechanism for persisting data generated by and used by Docker containers.** While bind mounts are dependent on the directory structure and OS of the host machine, **volumes are completely managed by Docker.**」
> 「**Volumes are easier to back up or migrate than bind mounts.**」「Volumes work on both Linux and Windows containers.」「When your application requires **high-performance I/O**.」
> 「**Volumes are not a good choice if you need to access the files from the host**, as the volume is completely managed by Docker. **Use bind mounts if you need to access files or directories from both containers and the host.**」

### 7.4 Windows／WSL 2 的 bind mount 已知問題

⚠️ **postgres 官方 image 文件全文未出現 "Windows" 一字 → 該文件沒有針對 Windows bind mount 的已知問題說明，未能查證。**

**但 Docker Desktop 官方對 WSL 2 的 bind mount 有明確警告**（<https://docs.docker.com/desktop/features/wsl/best-practices/>，2026-08-09）原文：

> 「**Optimise file system performance with bind mounts** — To get the best out of the file system performance when bind-mounting files, **store source code and other data that is bind-mounted into Linux containers... in the Linux file system, rather than the Windows file system.**」
> 「Linux containers **only receive file change events, "inotify events", if the original files are stored in the Linux filesystem.**」
> 「**Performance is much higher when files are bind-mounted from the Linux filesystem, rather than accessed from the Windows host filesystem. Therefore avoid `docker run -v /mnt/c/users:/users` where `/mnt/c` is mounted from Windows.** Instead, from a Linux shell use a command like `docker run -v ~/my-project:/sources <my-image>`」

同頁另兩條：

> 「**Always use the latest version of WSL. At a minimum you must use WSL version 2.1.5**, otherwise Docker Desktop may not work as expected.」（舊版可能導致：Docker Desktop 週期性當住、`vmmem.exe` 吃光記憶體、GPU 失效等，官方逐條列出）
> 「If you have concerns about CPU or memory usage, configure limits on the memory, CPU, and swap size allocated to the WSL 2 utility VM.」

> 📌 **把 §7.3 與 §7.4 併讀可得的事實（非建議）**：Docker 官方推薦 named volume；而在 Windows 上，named volume 由 Docker 管理、位於 WSL 2 的 Linux 檔案系統內，bind mount 若指向 `C:\...`（即 `/mnt/c/...`）則落在官方明文警告的那一類。**「named volume 的資料在 Windows 主機上要怎麼備份／取出」本文未查證。**

---

## 8. 未能查證清單（誠實標註）

1. **`tailscale cert` 不給 `--cert-file` / `--key-file` 時的預設輸出檔名與路徑** — KB 1153 與 CLI 參考頁皆未載明，官方示例一律顯式指定。
2. **`<機器名>.<tailnet>.ts.net` 在「只開 HTTPS 憑證、未開 Funnel」時是否存在公開 DNS 記錄** — 官方文件未直接回答。這決定了「CT log 曝光 → 掃描器能否連上」這條鏈的最後一步。
3. **Tailscale ephemeral 節點「a short period of inactivity」的確切分鐘數** — 官方 ephemeral nodes 頁未給數字。
4. **Personal plan 的「Unlimited user devices」是否有隱含的公平使用上限** — 定價頁未載明任何上限。
5. **Windows 上 Caddy 需要何種身分／設定才能向本機 tailscaled 取得 `.ts.net` 憑證** — Caddy 官方只寫「running as root, or configure `tailscaled` to give your Caddy user permission」，Tailscale 官方只給 Linux（Debian `/etc/default/tailscaled` + `TS_PERMIT_CERT_UID`）的做法。**Windows 路徑兩邊皆未載明。**
6. **Caddy 跑在容器內、tailscaled 跑在 Windows 主機上時，能否取得 `.ts.net` 憑證** — 官方措辭一律是 "the machine's local Tailscale daemon"，未涵蓋跨容器邊界的情形。
7. **在 Caddyfile 用 `tls <cert> <key>` 手動指定 `tailscale cert` 產出的檔案，是否會與 Caddy 對 `.ts.net` 的 special case 衝突** — Caddy 官方未把此組合列為受支援用法。
8. **`tailscale serve` 是否支援 SPA 的 catch-all fallback（等同 Caddy `try_files {path} /index.html`）** — serve 文件對目錄的描述是 "renders a directory listing"，未提及重寫規則。
9. **`tailscale serve` 是否支援 WebSocket 代理** — serve 文件全文未提及 WebSocket（[#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) 會用到）。
10. **`tailscale serve` 是否支援壓縮、快取標頭、自訂 header、access log** — 文件未提及。
11. **Tailscale Funnel 的「non-configurable bandwidth limits」具體數值** — 官方未給數字（本專案不擬用 Funnel，列此為完整性）。
12. **`StartWhenAvailable` 的適用範圍** — 兩份 Microsoft 官方頁面措辭不一致：「time-based tasks **with an end boundary** or... **repeat infinitely**」vs.「applies only to **timed tasks**」。**本文不裁決，需人工確認**；若前者為準，一個「每交易日固定時間、無結束時間、無無限重複」的觸發程序可能不適用該設定。
13. **電腦從睡眠／休眠／關機恢復後，錯過的工作是否會補跑、以及補跑的時序** — Microsoft Task Scheduler 文件只描述「排入服務佇列、延遲後啟動、預設延遲 10 分鐘」，**未描述 resume 或開機後的行為**。
14. **`WakeToRun` 是否受「允許使用喚醒計時器」電源原則管轄、以及在關機（S5）狀態下是否有效** — Task Scheduler 文件對 `WakeToRun` 只有兩句話（都在講螢幕）。唯一相關的第一手敘述是 `powercfg /waketimers`：「wakes the system from **sleep and hibernate** states」，**未涵蓋關機**。
15. **`schtasks` 命令列旗標與上述設定的對應** — 本次未查證。
16. **Windows 11 Home + Docker Desktop（WSL 2 backend）是否為官方支援組態** — 官方安裝頁的系統需求清單只列 Enterprise/Pro/Education，同頁另一段又說「Windows Home or Education editions only allow you to run Linux containers」。**兩段互相牴觸，需人工確認。**
17. **不裝 Docker Desktop、直接在 WSL 2 內使用 Docker Engine 的可行性與限制** — 本次未展開查證（僅記錄 Docker 官方「Docker Engine 等開源專案的授權與散布條款未改變」的原文）。
18. **postgres 官方 image 在 Windows 上使用 bind mount 的已知問題** — 該 image 的官方說明**全文未提及 Windows**。相關的第一手警告只有 Docker Desktop 的 WSL 2 最佳實務（效能與 inotify），**不是 postgres 專屬的問題陳述**。
19. **Docker named volume 的資料在 Windows 主機上如何備份／取出** — 本次未查證。這與 issue #17 body「持股與交易紀錄遺失不可接受」那條紅線直接相關。
20. **Tailscale 對台灣的實際連線品質／DERP 中繼節點位置** — 本次未查證，亦未實測。

---

## 9. 來源清單（皆為第一手官方頁面／官方檔案，2026-08-09 查證）

**Tailscale**
- 定價與 FAQ（Personal 額度、seat 模型、個人 vs 商業用途判定）：<https://tailscale.com/pricing>
- 免費方案與折扣：<https://tailscale.com/docs/account/manage-plans/free-plans-discounts>
- 帳務資訊（Personal 不需帳務資料）：<https://tailscale.com/kb/1182/billing-information>
- 啟用 HTTPS（CT log、Let's Encrypt、續期責任）：<https://tailscale.com/kb/1153/enabling-https>
- `tailscale cert` CLI 參考：<https://tailscale.com/kb/1080/cli/cert>
- CLI 總覽：<https://tailscale.com/kb/1080/cli>
- Caddy certificates on Tailscale：<https://tailscale.com/kb/1190/caddy-certificates>
- Tailscale Serve（概念與限制）：<https://tailscale.com/kb/1312/serve>
- `tailscale serve` 命令參考（旗標、反向代理、`-bg` 與重開機）：<https://tailscale.com/kb/1242/tailscale-serve>
- Tailscale Funnel（beta、埠限制、公開 DNS）：<https://tailscale.com/kb/1223/funnel>
- MagicDNS：<https://tailscale.com/kb/1081/magicdns>
- Tailnet 名稱與類型（`tail<ID>.ts.net` 隨機十六進位）：<https://tailscale.com/docs/concepts/tailnet-name>
- DNS in Tailscale（公開 DNS 記錄與「relatively harmless」原文）：<https://tailscale.com/docs/reference/dns-in-tailscale>
- 金鑰到期（預設 180 天）：<https://tailscale.com/kb/1028/key-expiry>
- Ephemeral nodes：<https://tailscale.com/docs/features/ephemeral-nodes>
- 移除裝置（人工／API，無自動回收）：<https://tailscale.com/docs/features/access-control/device-management/how-to/remove>
- Run unattended（Windows 預設隨使用者登入才連線）：<https://tailscale.com/kb/1088/run-unattended>

**Caddy**
- 自動 HTTPS（`.ts.net` special case、三種 challenge 的埠需求）：<https://caddyserver.com/docs/automatic-https>
- `forward_auth` 指令（Tailscale 身分標頭範例、標準指令清單）：<https://caddyserver.com/docs/caddyfile/directives/forward_auth>
- 官方套件登錄檔（確認 `tailscale/caddy-tailscale` **不在**其中）：`https://caddyserver.com/api/packages`
- `caddy-tailscale` 外掛 README（experimental）：<https://github.com/tailscale/caddy-tailscale>

**Microsoft**
- `TaskSettings.StartWhenAvailable`：<https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-startwhenavailable>
- `ITaskSettings::get_StartWhenAvailable`：<https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-itasksettings-get_startwhenavailable>
- `StartWhenAvailable`（schema element，措辭不一致的那一份）：<https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-startwhenavailable-settingstype-element>
- `TaskSettings.WakeToRun`：<https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-waketorun>
- `WakeToRun`（schema element）：<https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-waketorun-settingstype-element>
- `powercfg` 命令列選項（`/waketimers`：sleep 與 hibernate）：<https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options>

**Docker**
- Docker Desktop 授權條款（250 員工／US$10M 門檻、Personal use）：<https://docs.docker.com/subscription/desktop-license/>
- Windows 安裝與系統需求（Home 版矛盾之處、per-user vs all-users）：<https://docs.docker.com/desktop/setup/install/windows-install/>
- WSL 最佳實務（bind mount 效能與 inotify）：<https://docs.docker.com/desktop/features/wsl/best-practices/>
- Volumes（「preferred mechanism」原文）：<https://docs.docker.com/engine/storage/volumes/>
- Bind mounts：<https://docs.docker.com/engine/storage/bind-mounts/>

**PostgreSQL 官方 image**
- 官方 image 說明原始檔（Docker Hub `_/postgres` 內容來源）：<https://raw.githubusercontent.com/docker-library/docs/master/postgres/README.md>
- （Docker Hub 頁面本身為 JS 動態載入，`curl` 無法取得 tag 清單）：<https://hub.docker.com/_/postgres>

**專案內既有文件（交叉對照對象）**
- [`docs/research/deployment-facts-2026-08-09.md`](./deployment-facts-2026-08-09.md)（同批查證，雲端側；§7.1 的 Caddy challenge 埠需求原文引自此）
- [`docs/spec/tech-stack.md`](../spec/tech-stack.md) §8（Caddy 與憑證）、§9（base image 必須 Debian）
- [`docs/spec/auth.md`](../spec/auth.md)（CT log 與掃描器的既有記載）
