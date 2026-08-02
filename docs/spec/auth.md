# 認證與授權 v1

決策來源：[issue #10](https://github.com/NTUyu016/stock-analytic-platform/issues/10)。名詞定義見 [`CONTEXT.md`](../../CONTEXT.md)，資料表綱要見 [`data-model.md`](./data-model.md)，技術棧見 [`tech-stack.md`](./tech-stack.md)。

> 本文除了記錄「選了什麼」，也記錄「**為什麼**、被淘汰的選項輸在哪」。選型不附理由，日後就沒人敢改。
>
> §3 與 §5.3 是刻意寫進來的**背景解釋**（OAuth 2.0 vs OIDC、JWT vs session）。它們不是決策，是讓日後要改這些決策的人有足夠基礎能判斷。

---

## 總覽

| 項目 | 結論 |
|---|---|
| 認證發生的層 | **應用層**。不使用 Cloudflare Access 等邊界閘門 |
| 認證機制 | **Google OIDC**（主）+ **GitHub OAuth 2.0**（備援，預先註冊） |
| 授權 | 自有資料庫 allowlist。**不自動建立帳號** |
| Session | 伺服器端 session + cookie，狀態存 PostgreSQL |
| Cookie 屬性 | `HttpOnly` + `Secure` + `SameSite=Lax`，30 天滑動續期 |
| 使用者身分模型 | `app_user`（人）與 `user_identity`（身分）分離，key 為 `(provider, subject)` |
| 第一個帳號 | CLI 指令建立 |
| 最終逃生門 | CLI 直接發 session |
| WebSocket 驗證 | 握手時查同一份 session cookie，不通過即拒絕升級協定 |

---

## 1. 認證發生在哪一層：應用層

### 決定

自己的登入流程、自己的 session。Caddy 只做 TLS 與反向代理，不參與身分判斷。**不在前面放 Cloudflare Access / Tunnel 之類的邊界閘門。**

### 為什麼不用邊界閘門

**1. 它會直接砍掉 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) 選定的省錢槓桿。**

Cloudflare Tunnel 靠 `cloudflared` 維持一條**由內向外的常駐連線**。機器一停，隧道就斷，Cloudflare 只會回 502 —— **沒有 inbound request 可以喚醒它**。

這正是 [#5](../research/persistent-websocket-hosting.md) 否決 serverless 的理由，而它原本只適用於 `quote-worker`（WebSocket client，喚不醒）。加上 Tunnel 等於把同一個問題搬到 `api` 頭上，`auto_stop_machines` 直接失效。

（不走 Tunnel、只用 Access 反向代理一個公開 origin 可以避開這點，但那樣仍得公開 origin，「不開 inbound port」這個賣點也就沒了。）

**2. 身分會變成租來的。** `app_user` 的身分將取決於「Cloudflare 說你是誰」。而 Access 的模型是**組織內部成員清單**，日後若要開放註冊，這一層完全不適用，得整個拆掉重寫 —— 與本票「預留是否足夠」的目標直接衝突。

**3. 它防的攻擊，我們本來就沒有。** Access 主要擋密碼暴力破解與掃描器。而 §2 選定的機制**結構上沒有密碼可以爆破**。用一個外部服務去防一個不存在的攻擊面，不划算。

### 要付的帳（誠實記錄）

`api` 直接暴露在公開網際網路上。而且「沒人知道我的網址」是**不成立的**：Caddy 申請 Let's Encrypt 憑證時，網域名稱會被寫進 **Certificate Transparency log**，公開可查詢，且有人專門監看 CT log 尋找新上線的網域。

**上線後數小時內一定會有掃描器來敲 `/wp-login.php`、`/.env`、`/admin`。** 這不是針對性攻擊，是背景輻射，但它把「認證機制必須夠強」從偏好變成硬需求。

### 這張票真正在保護什麼（威脅盤點）

把資產按「真的損失多少」排，可以看出認證的守備範圍其實有限 —— 這值得寫下來，避免日後在錯的地方加強：

| 資產 | 真實損失 | 認證守得到嗎 |
|---|---|---|
| 行情源 API 金鑰 | 帳號被停權（[#2](../research/tw-realtime-quote-sources.md)：持續違規暫停 IP 及 ID），重新開通要數個工作天 | **守不到**。金鑰在 `.env` 不在資料庫，要取得須先拿到機器本身 |
| 雲端帳單 | scale-to-zero 的另一面：任何人送一個 HTTP request 就能喚醒機器 | **守不到**。喚醒發生在應用程式跑起來之前 → 屬 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) 的支出上限議題 |
| 交易紀錄（持股、成本、損益） | **隱私外洩，不是金錢損失** —— 本圖 out of scope 明確不碰下單路徑 | ✅ |
| 法遵：未登入端點洩漏行情 | 違反 TWSE《交易資訊使用管理辦法》 | ✅ |

**認證真正守的是隱私與法遵這兩項。** 前兩項要靠別的手段（`.env` 檔案權限、平台層的支出上限）。

---

## 2. 認證機制：Google OIDC（主）+ GitHub OAuth（備）

### 決定

- **主**：Google OIDC，scope 只要 `openid` / `email` / `profile`
- **備**：GitHub OAuth 2.0，**必須在還登得進去的時候就預先註冊好**
- 兩者皆為 `user_identity` 的一列，地位對等 —— 「主/備」是使用習慣，不是程式邏輯

### 為什麼不自建密碼

走密碼的最小可接受清單如下，而且**漏掉任何一項，前面全部白做**：

1. Argon2id 雜湊（不是 bcrypt、更不是 SHA-256），參數要調對且**每隔幾年要調高**
2. 速率限制，且要**同時**按 IP 與按帳號限（只限 IP 擋不住分散式嘗試）
3. 密碼長度下限 + 比對已外洩密碼庫
4. 防帳號列舉：失敗訊息一致、**回應時間也要一致**
5. session cookie 的安全屬性
6. 2FA —— 否則密碼一旦外洩就結束了
7. 密碼重設流程 —— 而它本身又是一個新的攻擊面

**七項，而且是持續成本。** 委外給 OIDC provider 後，第 1～4、6～7 項**消失**（不是變簡單，是不存在）。

工具成熟度不是選型依據：`argon2-cffi`（25.1.0）與 `py_webauthn`（3.0.0，2026-06-29，`requires_python >=3.10`）都在維護中。**淘汰理由是持續維護成本，不是可行性。**

### 為什麼不用 Passkey（WebAuthn）

Passkey 一度是本票的推薦方案，被推翻的關鍵是：

> **OAuth 把「你的網站有多安全」外包給「你的 Google 帳號有多安全」。而如果那個 Google 帳號本身已經用 passkey 或 2FA 保護，你就已經取得了 passkey 的抗釣魚性 —— 只是透過 Google 拿到，且不必自己實作。**

抗釣魚性這一格因此大致打平，於是剩下的比較全部倒向 OAuth：

| 面向 | Passkey | Google OIDC |
|---|---|---|
| 換網域 | **所有 credential 全部作廢**（WebAuthn 綁 origin），要逐台裝置重新註冊 | 改一行 redirect URI |
| 每台新裝置 | 各註冊一把（除非有跨裝置同步） | 直接登入 |
| 多人化時的註冊流程 | email 驗證、帳號啟用、重複註冊、忘記密碼**四塊都要自己寫** | Google 全包 |
| 實作量 | challenge-response 兩支端點 + bootstrap 機制 | redirect + code exchange |

**「換網域」那一列有直接的下游影響**：它讓 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) 可以先用免費子網域上線、日後再換正式網域，不必為了認證而一次選對。

**Passkey 仍然勝出的地方**（記錄下來，日後情境改變時可重新評估）：

1. **可用性單點** —— Google 帳號被誤判停權是有記載且申訴無門的現象。這是唯一無法用技術抵銷的一項，靠 §7 的逃生階梯處理。
2. **元資料隱私** —— Google 會知道你每次登入這個網站的時間點。內容看不到，但行為資料看得到。
3. **少一個會改政策、改定價、改 API 的第三方。**

### 為什麼備援是 GitHub，而不是 Apple / Facebook

| 候選 | 判定 |
|---|---|
| **GitHub** | ✅ **選定**。零費用、設定五分鐘。決定性理由：**本專案的 repo 就在 GitHub 上** —— 這個帳號一定有、一定在用、不可能忘記它存在。備援機制最常見的死法是「設好之後忘了，真要用時發現帳號早就登不進去」 |
| Apple | ❌ 網頁流程要建立 Services ID 與私鑰，需要**付費的 Apple Developer Program（US$99/年 ≈ NT$260/月）**。比整台機器還貴，與成本偏好正面衝突 |
| Facebook | ❌ 所有 provider 中**最惡名昭彰會無預警鎖帳號且申訴無門**。拿一個更不穩的東西去備援一個較穩的東西，方向錯了 |

### ⚠️ 設定層的必要條件：避免共同失效

多 provider 的前提是它們**獨立失效**。有一條路徑會讓兩者一起倒：

> **若 GitHub 帳號的註冊信箱或密碼重設信箱，就是那個 Google 帳號** —— Google 一停，GitHub 的復原路徑也跟著斷。表面上有兩個 provider，實際上只有一個。

**因此規定**（設定層的事，不是程式的事，但不寫下來就會漏）：

- 備援 provider 的帳號，其復原信箱**不得**是主 provider 的地址
- 該帳號必須開啟 2FA，且復原碼離線保存

### 被淘汰的方案彙總

| 選項 | 輸在哪 |
|---|---|
| 環境變數密碼 / HTTP Basic | 公開上網後從「夠用」變「勉強」；上面七項一項都沒做 |
| 自建密碼 + 2FA | 七項持續成本全額支付，換到的安全性不高於委外 |
| Passkey | 抗釣魚優勢被「Google 帳號本身有 2FA」抵銷後，剩下的比較全面落後；換網域全作廢是硬傷 |
| 備用 email magic link | 見 §7 |

---

## 3. 背景：OAuth 2.0 與 OIDC 的差別

> 這一節不是決策，是讓日後維護者能判斷「為什麼 Google 跟 GitHub 的接法不一樣」。

### OAuth 2.0 是**授權**協定，不是**認證**協定

這是所有混淆的源頭。OAuth 2.0 回答的是：

> 「這個應用程式，可不可以代表某人去存取某個資源？」

它**沒有**回答「這個人是誰」。比喻成飯店房卡：OAuth 2.0 給你一張**能開某扇門、但卡上沒有名字**的卡。

流程跑完，你手上是一個 **access token**。規格到此為止，**沒規定**要怎麼知道使用者是誰。於是各家自己發明端點：GitHub 是 `GET /user`、Facebook 是 `GET /me`。**接一家寫一次，格式全不同。**

### OIDC = OAuth 2.0 + 三樣標準化的東西

OIDC 不取代 OAuth 2.0，是疊在上面的一層薄標準層：

1. **ID token** —— 一個 JWT，直接帶著「這個人是誰」（`sub`、`email`、`iss`、`aud`、`exp`）。不用再打一次 API。
2. **Discovery** —— `https://accounts.google.com/.well-known/openid-configuration`，一個 URL 拿到所有端點位置，不用硬編。
3. **`scope=openid`** 這個關鍵字，以及各 claim 名稱的統一。

因此本專案兩家的接法必然不同：

```
Google  → 有 OIDC        → 拿 ID token，驗簽 → 直接得到 sub     （一次往返）
GitHub  → 只有 OAuth 2.0 → 拿 access token → 再打 /user        （兩次往返）
```

**這就是 §6 的 adapter 介面必須是 `-> (provider, subject, email)` 而不是 `-> id_token` 的原因** —— GitHub 根本不給你帶身分的 token。

### ⚠️ access token 不是給你讀的，ID token 才是

| | access token | ID token |
|---|---|---|
| 發給誰 | **資源伺服器** | **你的應用程式** |
| 你該怎麼對待 | 不透明字串，只負責轉交，**不要解析** | 驗簽、驗 `aud`、驗 `iss`、驗 `exp` 後讀取 |
| 有沒有「發給誰」的欄位 | **沒有** | 有（`aud`） |

最後一列是關鍵。因為 access token 沒有 `aud`，**你無法判斷它原本是發給哪個應用程式的**。

這導致經典的 **token substitution attack**：攻擊者在自己的 app 上騙到某人的 access token，再把它送給你的網站；你拿去打 userinfo，provider 會**正常回應那個人的資料**，於是你以為攻擊者就是那個人。

**對本專案的實作意義（硬性規則）**：

> **code → token 的交換必須在伺服器端、用 `client_secret` 完成。絕不接受前端傳來的 access token 或 ID token 作為身分證明。**

只要交換是自己做的，token 確定是 provider 直接發給你的，此攻擊不成立。網路上有不少教學是「前端拿到 token 再 POST 給後端」，**不可照抄**。

---

## 4. 授權：allowlist，且不自動建立帳號

### 決定

登入流程是**兩段**，不可合併：

```
1. provider 告訴你 (provider, subject, email)     ← authentication，誰
2. 你自己查 user_identity 表確認此身分已登記      ← authorization，能不能進來
3. 查無此人 → 拒絕，且【不自動建立帳號】
```

### 為什麼這條必須明文寫下來

這是接 OAuth 最常見的錯誤，而且後果在本專案特別嚴重：

> **「用 Google 登入」的預設語意是「全世界任何一個 Google 帳號都能登入你的網站」。**

只接上 OIDC 就收工，等於把持股資料與即時行情開放給全網 —— 這直接違反 [#2 §2.6](../research/tw-realtime-quote-sources.md) 查證的「券商行情不得轉供第三人」。

**OIDC 只答「你是誰」，它從不答「你可不可以進來」。** 後者永遠是你自己的責任。

### 與 `tech-stack.md` §8 那條規則的關係

`tech-stack.md` §8 已定：

> 任何未登入即可存取的頁面或 API 端點，都不得包含即時報價、五檔、逐筆成交或其衍生數值。

本節是它的另一半：**不只要「登入後才給」，還要「登入的人必須是登記過的人」。** 兩條合起來才構成完整的法遵防線。

---

## 5. Session：伺服器端 session + cookie

### 決定

登入成功後發一個**隨機 session id** 放進 cookie，狀態存 PostgreSQL。**不使用 JWT 當 session。**

| 項目 | 值 |
|---|---|
| Cookie 屬性 | `HttpOnly` + `Secure` + `SameSite=Lax` |
| 有效期 | 30 天，**滑動續期**（每次使用往後展延） |
| 狀態存放 | PostgreSQL，**不可存行程記憶體** |

### 5.1 三條實作規則與其理由

**`SameSite=Lax` 不可改成 `Strict`。** 從 Google／GitHub 導回來的那一跳是跨站導向，`Strict` 會讓瀏覽器不帶 cookie，**登入直接壞掉**。

**session 必須存 PostgreSQL，不可存行程記憶體。** 因為 [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) 選定 `api` 走 scale-to-zero —— 機器會停、會被喚醒，記憶體裡的 session 每次停機都會全丟，使用者會被隨機登出。注意這個理由**不是**常見的「多台機器要共享」，而是停機重啟。

**過期 session 要定期清理。** 一張只增不減的表。小事，但不做會長到很難看。

### 5.2 為什麼不用 JWT

三個理由，第三個是決定性的：

**1. JWT 的優勢在本架構下買不到東西。** 無狀態是為了「多個不共享狀態的服務各自驗證身分」而生。本專案只有一個 `api`，而它本來就連著 PostgreSQL。付出「不可撤銷」的代價，卻沒有換到任何好處 —— 這是最糟的一種取捨。

**2. 「省一次查詢」在此量級不是優勢。** 單人自用，那是一次主鍵查詢，與隨後的持股推導相比是雜訊。

**3. 決定性的一點：cookie 順便解決了 WebSocket 驗證。** 見 §8。

### 5.3 背景：JWT 與 session id 的限制

> 同樣不是決策，是給日後想改的人的判斷基礎。

本質差異：

> **Session ID 是一個「指標」，指向伺服器上的狀態。JWT 是「資料本身 + 防偽章」。**

**JWT 的限制**

| # | 限制 | 說明 |
|---|---|---|
| 1 | **不可撤銷** | 驗證 JWT 不需問任何人，因此**沒有任何地方可以宣告作廢**。登出、踢裝置、發現外洩 —— 都只能等 `exp`。業界補救是黑名單，但那就是每次請求查一次 DB：**你已經回到 session，還多背了一個 JWT** |
| 2 | payload 是**編碼**不是**加密** | base64 任何人都能解開讀完。簽章保證的是**不可竄改**，不是**不可讀**。這兩者常被混為一談 |
| 3 | 只反映**簽發當下**的狀態 | 把 `role: admin` 寫進 token 後降權，他手上那張在過期前仍是 admin。落後時間 = 有效期 |
| 4 | 為縮短窗口，會被迫做出 session | 標準解法是短效 access token + refresh token。而 **refresh token 是有狀態、可撤銷、要存 DB 的** —— 繞一圈還是 session，只是換了名字，而且現在有兩種憑證、兩套過期邏輯 |
| 5 | 放哪裡都尷尬 | `localStorage` 會被 XSS 讀走；放 cookie 就要處理 CSRF —— 而既然都放 cookie 了，放 session id 更好 |

**Session ID 的限制**（誠實列，不只打對方）

| # | 限制 | 在本專案是否構成問題 |
|---|---|---|
| 1 | 每次請求查一次儲存體 | 否。一次主鍵查詢，微秒級；PostgreSQL 本來就在 |
| 2 | 有狀態，水平擴展要共享儲存體 | 否。單機，且已存 PostgreSQL |
| 3 | 要清理過期資料 | 是，但只是一個排程 |
| 4 | **跨網域不方便** | 否。單一網域。**這是 JWT 唯一真正勝出的場景，而我們用不到** |

**JWT 真正對的場景**：多個獨立服務不共享資料庫、跨信任邊界傳遞身分、極高流量下 DB 查詢確實是瓶頸。

**收尾 —— 本專案確實會用到 JWT，但只用一次**：

> ID token 就是 JWT。登入那一刻 Google 發一個 JWT 給你，你驗簽、取出 `sub`，然後**丟掉它**，換成自己的 session cookie。
>
> 這正是 JWT 的正確用法：**跨信任邊界傳遞一次性的身分斷言**。它從來不是設計來當長期 session 的。

---

## 6. 使用者身分模型：`app_user` 與 `user_identity` 分離

### 決定（**這是對 [#9](https://github.com/NTUyu016/stock-analytic-platform/issues/9) 的修訂**）

拆成兩張表：`app_user` 是**人**，`user_identity` 是**登入身分**。一個人可以有多個身分。綱要見 [`data-model.md`](./data-model.md)。

### 為什麼原本的設計不夠

`data-model.md` 原本的 `app_user` 是 `id` / `email` UNIQUE / `created_at`，隱含「一個人 = 一個 email = 一種登入方式」。

在這個結構下，**「換一個 provider 登入」等於改寫自己的身分列 —— 而那正是你被鎖在門外時做不到的事。** 備援方案在此結構上無法成立。

### ⚠️ key 必須是 `subject`，絕不可以是 `email`

Google 官方文件明文：

> "When implementing your account management system, you **shouldn't** use the `email` field in the ID token as a unique identifier for a user."
>
> "Always use the `sub` field as it is unique to a Google Account **even if the user changes their email address**."
>
> —— <https://developers.google.com/identity/openid-connect/openid-connect>

除了「使用者改 email 就登不進去」之外，還有一個更難救的情境：

> **Google Workspace 帳號被刪除後，同一個 email 可以再發給新的人。** 用 email 當 key，那個人會直接繼承你的存取權。

GitHub 有完全對應的坑：**`login`（使用者名稱）是可以改的**，穩定識別碼是回應中的數字 `id`。

因此各 provider 填入 `subject` 的來源：

| provider | `subject` 來源 | 備註 |
|---|---|---|
| `google` | ID token 的 `sub` claim | |
| `github` | `GET https://api.github.com/user` 回應的 `id`（數字） | **不可用 `login`** |

`user_identity.email` 欄位**僅供顯示與人工比對，不參與任何判斷**。

### 這張表為什麼值得現在就做

它讓「多一家 provider」永遠只是**多一列資料**，不是多一條程式路徑。同一個形狀也直接滿足 §10 的預留要求 —— 多人化時它一行都不用改，只是列數變多。

---

## 7. 逃生階梯

### 決定

三層，愈下層愈少用、愈難被攻擊：

| 層 | 機制 | 依賴什麼 | 何時用 |
|---|---|---|---|
| 0 | Google OIDC | Google | 日常 |
| 1 | GitHub OAuth（**預先**註冊好） | GitHub | Google 帳號異常 |
| 2 | **CLI 直接發 session** | **只依賴「你有那台機器」** | 兩家都失效，或網站本身出問題 |

第 2 層不可省。它是唯一一條**完全不經過任何第三方**的路徑。

### 為什麼不做「備用 email magic link」

這個方案曾被提出（寄一次性登入連結到備用信箱），最後**主動移除**。它的代價不成比例：

> **magic link 把整個網站的安全性降到「備用信箱有多安全」。信箱被入侵 = 網站被入侵，且繞過了 provider 的 2FA。**
>
> 加了這一層之後，攻擊者不會去打 Google，他會去打那個備用信箱 —— **它會成為整條階梯裡最弱的一環。**

而它帶來的實作負擔也不小：Resend 網域驗證（[#7](../research/alert-notification-channels.md) 查證：必須驗證自有網域才能正式寄送）、送達率、一次性 token 的防重放與短效期。

**移除它同時讓系統變簡單且變安全** —— 這種選項不常見，遇到就該拿。連帶好處：本票不再相依於 [#15](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 是否採用 Resend。

**多 provider 之所以能取代它**，是因為 provider 帳號本身受 2FA 保護，而備用信箱通常不是。前提是 §2 那條「避免共同失效」的設定規則有被遵守。

---

## 8. CLI：bootstrap 與逃生門

### 決定

一支管理 CLI，至少兩個子指令：

```bash
uv run manage user create --email you@example.com     # 建立 app_user
uv run manage user grant-session --user-id 1          # 直接發一張有效 session
```

兩者共用同一個信任前提：**你有那台機器的存取權**。

### 為什麼第一個帳號用 CLI 建，而不是「首次登入者自動成為擁有者」

「首次登入自動建帳號」看起來最省事，但它有一個**具體可被利用的時間窗**：

> 從 Caddy 申請憑證那一刻起，網域就被寫進 **Certificate Transparency log**，公開可查詢，而有人專門監看 CT log 尋找剛上線的新網域。
>
> **在你第一次登入之前，那個「第一個登入的人自動成為擁有者」的入口，對全世界開著。**

只要有人比你早幾分鐘登入，他就是擁有者，而你變成登不進去的那個。窗口通常只有幾分鐘，但**單向不可逆** —— 被搶走只能砍掉資料庫重來。

被淘汰的另一個選項是「migration / seed 寫死一列」：身分資料混進 schema 版控，換人或加人都要改 migration。

**而 CLI 不是新東西** —— 逃生門本來就要它，`user create` 只是多一個子指令。選其他方案反而是**多引入一種機制**。

---

## 9. WebSocket 的身分驗證

### 決定

**WebSocket 握手就是一個普通的 HTTP 請求，同源 cookie 會自動帶上。** 因此：

> 握手時查同一份 session，通過才升級協定；不通過回 401，**拒絕升級**。

不發第二種憑證，不做另一套驗證邏輯。

### 為什麼這是 §5 選 session 的決定性理由

瀏覽器原生的 `WebSocket` API **不支援自訂 header** —— 你沒辦法送 `Authorization: Bearer <jwt>`。業界常見的醜解法是把 token 塞進 query string，而：

> **query string 會被寫進 Caddy 的 access log** —— 等於把憑證明文落地。

Cookie 沒有這個問題。這條同時天然滿足 `tech-stack.md` §8 的「所有回傳 Quote 的端點都在認證中介層之後，不可有例外路由」。

**交給 [#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) 的**：連線建立後，若 session 在連線存續期間被撤銷該怎麼處理（定期重查 vs 撤銷時主動斷線）。本票只定「握手時必驗、憑證不得走 query string」。

---

## 10. 硬性實作規則彙總

實作時逐條對照：

1. **code → token 交換必須在伺服器端用 `client_secret` 完成。** 絕不接受前端傳來的 access token / ID token 作為身分證明（§3）。
2. **身分的 key 是 `(provider, subject)`，永遠不是 email。** GitHub 用數字 `id` 不用 `login`（§6）。
3. **登入後必查自有 allowlist，且不自動建立帳號**（§4）。
4. **session 存 PostgreSQL，不可存行程記憶體**（§5.1）。
5. **cookie 必須 `SameSite=Lax`**，不可用 `Strict`（§5.1）。
6. **WebSocket 憑證不得出現在 query string**（§9）。
7. **所有涉及使用者資料的查詢，從第一天就帶 `WHERE user_id = ?`**（§11）。
8. 備援 provider 帳號的復原信箱不得是主 provider 的地址，且須開 2FA（§2）。

---

## 11. 開放註冊的預留：驗收標準，不是 v1 待辦

### v1 的承諾範圍

> **v1 只承諾「不寫死」，不承諾「已預留完整」。**

具體差別：**不**建立角色/權限模型（那是寫死了另一個方向），但**每個查詢從第一天就帶 `WHERE user_id = ?`**。

在 v1 這個條件恆為真，是無害的冗餘；多人化時它是唯一的防線，而且**漏掉不會有任何錯誤訊息，只能靠測試抓**。這就是「不寫死架構」的具體形狀：不做多人功能，但不留下「只有一個人」的假設。

### 不用改的（代表預留有效）

| 項目 | 為什麼不用改 |
|---|---|
| `user_identity` | 已經是多 provider、多身分的形狀，多人只是多列 |
| session 機制 | 本來就是 per-user |
| `portfolio` / `transaction` / `alert` | [#9](https://github.com/NTUyu016/stock-analytic-platform/issues/9) 自始帶 `user_id` |
| 認證中介層 | 判斷「有沒有登入」的邏輯不隨人數變 |

### 必須改的

1. **註冊流程**：CLI 建帳號 → 自助註冊。且「首次登入自動建帳號」必須是一個**明確的開關，預設關閉**（§8 排除的正是它）。
2. **授權模型** —— 最大的一塊，也最容易漏。現在是「在 allowlist = 全權」；多人後每個查詢都要回答「這筆資料是不是他的」。規則 7 就是為了讓這一步變成驗證而非改寫。
3. **配額**：行情訂閱是稀缺資源（Fugle 免費層 5 檔 / 1 連線）。第二個使用者加進來**當天就撞上限**。
4. **隱私政策、服務條款、投顧法免責聲明。**

### ⚠️ 最重要的一項不是程式

**法遵才是真正的阻擋者。** 依 [#2 §2.6](../research/tw-realtime-quote-sources.md)，券商行情**不得轉供第三人**，而「開放註冊」在定義上就是轉供第三人。

**上面四項全部做完，仍然不能開放註冊**，除非走 [#1](https://github.com/NTUyu016/stock-analytic-platform/issues/1) 已列的三條路之一（自行簽約成為資訊廠商／只呈現延遲 20 分鐘以上資料／只呈現衍生結論不呈現原始行情）。

**因此本節的正確定位是「必要但不充分」** —— 它保證 v1 的架構決策不會逼你重寫，但它不保證你可以開放註冊。

---

## 12. 留給其他票

| 議題 | 票 |
|---|---|
| 網域來源與費用（**可先用免費子網域**，OAuth 換網域只需改 redirect URI）、scale-to-zero 被陌生請求喚醒的支出上限 | [#17](https://github.com/NTUyu016/stock-analytic-platform/issues/17) |
| WebSocket 連線存續期間 session 被撤銷的處理方式 | [#13](https://github.com/NTUyu016/stock-analytic-platform/issues/13) |
| 開放他人使用的法遵路徑取捨 | [#1](https://github.com/NTUyu016/stock-analytic-platform/issues/1) — Not yet specified，需獨立一張圖 |
