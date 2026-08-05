# 研究：Discord 作為警示通知管道的第一手查證

- **對應 issue**：[#15 警示的觸發模型與通知管道](https://github.com/NTUyu016/stock-analytic-platform/issues/15)（隸屬 wayfinder 地圖 #1）
- **查證日期**：2026-08-05
- **緣由**：#15 原本的推論以 Telegram 為主推播管道，2026-08-04 使用者改口指定 Discord（原話：「可以用 discord 嗎? (ios 不用即時通知沒關係)」）。既有研究 [`alert-notification-channels.md`](./alert-notification-channels.md) 完全沒有涵蓋 Discord，本文補上。
- **來源政策**：僅採信第一手來源（`docs.discord.com` 官方開發者文件、`support.discord.com` / `support-dev.discord.com` 官方支援與法務條款、`discord.com/safety` 官方安全中心、`core.telegram.org` Telegram 官方文件）。**凡是只有部落格／論壇／第三方文章講得出來的數字，一律標註「未能查證，需人工確認」，不寫進結論。**
- **架構前提**（決定哪些事實重要）：送出者是一個常駐 `quote-worker`（Python，台股盤中 09:00–13:35 開機），直接發出站 HTTP；單人使用，每月數十到數百則；觸發到送達 ≤30 分鐘；repo 為 public，所有憑證走 `.env`。

> **本文只陳述事實與代價，不做決策。** 定案由使用者在 grilling 中親自做。

---

## 0. 結論摘要（TL;DR）

1. **Webhook 真的不需要 bot、不需要 authentication**，官方原文就是這句話。URL 裡的 `{webhook.token}` **本身就是唯一憑證**，請求不帶 `Authorization` header。
2. **URL 洩漏的後果比 Discord 自己的安全中心講得嚴重。** 安全中心說洩漏「只會有 spamming 這類非永久性問題」，但開發者文件明載 `DELETE /webhooks/{id}/{token}`「does not require authentication」——**任何拿到 URL 的人可以直接刪掉這個 webhook**，等於單向 DoS。兩份官方文件互相矛盾，以開發者文件為準。
3. **建立步驟純點擊，零程式、零自架 server**：Server Settings → Integrations → Create Webhook → 選頻道／命名 → Copy Webhook URL。使用者端不需要跑任何東西。
4. **官方不公布 per-webhook 的具體 rate limit 數字，而且明文禁止硬編碼**：「**rate limits should not be hard coded into your app**」。只有 global 限制有數字（50 req/s），且**在沒有 Authorization header 的情況下（webhook 正是如此）是按 IP 計算**。網路上流傳的「30 則/分鐘/webhook」**在官方文件中查不到，未能查證**。
5. **`content` 上限 2000 字元；embeds 最多 10 個；embed `description` 4096 字元；單則訊息所有 embed 文字欄位合計不得超過 6000 字元**。`color` 是 integer 欄位，**紅漲綠跌可以直接做**。Markdown 是官方支援的（「a subset of markdown」）。
6. **預設 `wait=false` 時的 `204 No Content` 不代表訊息存下來了**——官方原文：「when `false` a message that is not saved does not return an error」。**要拿到「Discord 已收下並建立訊息」的確認，必須帶 `?wait=true`**。即使如此，那也只代表存進 Discord，**沒有任何投遞到裝置的回執機制**。
7. **失敗判定有官方明文**：「If a webhook returns a **404** status you should not attempt to use it again」。webhook 被刪 → JSON error `10015 Unknown webhook`；token 錯 → `50027 Invalid webhook token provided`。
8. **查不到任何 Incoming Webhook 的棄用／落日公告**（截至 2026-08-05 的官方 Change Log）。但**有兩個真實的政策風險**：(a) Developer Policy 第 16 條禁止「transmit data to Discord … that includes … **financial information**, or other sensitive information under applicable law」——本專案送的正是個人持股損益；(b) Developer ToS 保留「terminate your Application's access tokens … that have not been used or accessed within at least the prior 30-day period」。
9. **推播行為官方講得很保守**：文件明說「Users can customize their notification settings through the Discord app, which might cause them to only receive a notification badge and no push notification」。**Discord 官方從不保證推播必達。** 另外 App 開著且在前景時不會有通知。
10. **Discord 有等同 Telegram `disable_notification` 的東西**：message flag `SUPPRESS_NOTIFICATIONS`（`1 << 12`），且 **Execute Webhook 明確允許設定這個 flag**。靜音時段方案兩邊都成立。

---

## 1. 認證模型：URL 就是憑證

### 1.1 官方原文：不需要 bot、不需要 authentication

Discord 開發者文件 Webhook Resource 開宗明義：

> "Webhooks are a low-effort way to post messages to channels in Discord. **They do not require a bot user or authentication to use.**"
>
> （Webhook 是一種低成本的方式，把訊息貼到 Discord 頻道。**使用上不需要 bot user，也不需要 authentication。**）

- 來源（第一手）：<https://docs.discord.com/developers/resources/webhook>

### 1.2 憑證在哪裡：在 URL 路徑裡

執行端點的路徑本身就含 id 與 token：

> `POST /webhooks/{webhook.id}/{webhook.token}`

Webhook 物件的 `token` 欄位定義：

> "`token?` | string | **the secure token of the webhook** (returned for Incoming Webhooks)"

Webhook 類型表，本專案要用的是 Type 1：

> "| 1 | Incoming | **Incoming Webhooks can post messages to channels with a generated token** |"

- 來源：<https://docs.discord.com/developers/resources/webhook>

**判定**：請求**不帶** `Authorization` header，憑證完全內嵌在 URL。這是「bearer URL」模型——**誰持有 URL，誰就是這個 webhook**。因此 URL 必須當作 secret 對待（`.env`，不進 public repo，不入 log，不入 error message）。

### 1.3 URL 洩漏的後果：官方兩份文件說法不一致

**Discord 安全中心（Safety Library）的說法（較輕描淡寫）**：

> "If webhook URL is leaked, only non-permanent problems may occur (e.g. spamming)"
>
> （webhook URL 若外洩，只會發生非永久性的問題，例如洗版。）

> "No authentication that data sent to webhook is from a trusted source."
>
> （沒有任何機制驗證送進 webhook 的資料來自可信來源。）

> "Easy to change webhook URL if needed"（必要時要換 webhook URL 很容易。）

- 來源：<https://discord.com/safety/using-webhooks-and-embeds>

**但開發者文件揭露了更嚴重的一面**——以下三個端點**只要有 token 就能呼叫，不需要任何權限**：

| 端點 | 官方原文 | 攻擊者可做的事 |
|---|---|---|
| `GET /webhooks/{id}/{token}` | "Same as above, except **this call does not require authentication** and returns no user in the webhook object." | 讀出 `guild_id`、`channel_id`、webhook 名稱與頭像 |
| `PATCH /webhooks/{id}/{token}` | "Same as above, except **this call does not require authentication**, does not accept a `channel_id` parameter in the body, and does not return a user in the webhook object." | 改掉 webhook 的預設名稱與頭像（可用於偽裝） |
| `DELETE /webhooks/{id}/{token}` | "Same as above, except **this call does not require authentication**." | **直接永久刪除這個 webhook** |

此外，token 也能編輯／刪除該 webhook 自己送出過的訊息：

> "**Edit Webhook Message** — `PATCH /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}` — Edits a previously-sent webhook message from the same token."
>
> "**Delete Webhook Message** — `DELETE /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}` — Deletes a message that was created by the webhook. Returns a `204 No Content` response on success."

- 來源：<https://docs.discord.com/developers/resources/webhook>

**判定**：安全中心那句「only non-permanent problems」**與開發者文件牴觸**。以開發者文件為準，洩漏的實際最壞後果是：

1. 洗版（安全中心已承認）；
2. **對方直接刪掉 webhook**，讓警示靜默失效——而且**你不會收到任何通知**，只會在下次送出時拿到 404；
3. 竄改／刪除歷史警示訊息，破壞稽核軌跡；
4. 洩漏 server 與 channel 的 snowflake ID。

**不會發生的事**（同樣依開發者文件推得）：webhook token **無法**讀取頻道歷史訊息、**無法**取得使用者資料、**無法**操作 server 的其他部分。損害範圍限縮在該 webhook 與其所屬頻道的貼文行為。

### 1.4 撤銷方式

- **持有伺服器管理權的一方**：`DELETE /webhooks/{webhook.id}`，官方原文「Delete a webhook permanently. **Requires the `MANAGE_WEBHOOKS` permission.** Returns a `204 No Content` response on success. Fires a Webhooks Update Gateway event.」實務上就是在 Discord App 的 Server Settings → Integrations 裡把該 webhook 刪掉、重建一個新的。
- **有沒有「不刪除、只換 token」的輪替（rotate）機制？** `Modify Webhook` 的 JSON Params 只有 `name`、`avatar`、`channel_id` 三個欄位，**沒有任何重新產生 token 的參數**；官方文件中也找不到 rotate 端點。
  - **未能查證，需人工確認**：Discord App UI 是否提供「Regenerate Webhook URL」之類的按鈕。官方文件與支援文章都沒寫。**目前唯一有官方依據的撤銷手段是「刪掉重建」，並同步更新 `.env`。**

---

## 2. 建立一個 webhook 需要使用者做什麼

Discord 官方支援文章「Intro to Webhooks」的原文步驟：

> "**Making a Webhook** — Open your **Server Settings** and head into the **Integrations** tab: Click the "**Create Webhook**" button to create a new webhook!"
>
> "You'll have a few options here. You can: **Edit the avatar**: By clicking the avatar next to the Name in the top left. **Choose what channel the Webhook posts to**: By selecting the desired text channel in the dropdown menu. **Name your Webhook**: Good for distinguishing multiple webhooks for multiple different services."
>
> "I'll grab the webhook URL for this channel by pressing the **Copy Webhook URL** button"

- 來源（第一手）：<https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks>

同一篇也點明 webhook 的「送出端」必須是別人（在本專案就是我們的 `quote-worker`）：

> "it's important to note that **webhooks require another website to use** (though **programming-inclined users can make their own tube schoomper themselves**)."
>
> （webhook 必須搭配另一個網站才能用，不過會寫程式的人可以自己做一個送出端。）

### 2.1 逐項回答

| 問題 | 答案 | 依據 |
|---|---|---|
| 需不需要自己開 server？ | **不需要。** Incoming webhook 是我們主動 POST 出去，Discord 不會回連我們。 | 官方 Webhooks 總覽頁：incoming webhooks 是「HTTP endpoints tied to a specific Discord channel. You POST a payload to the URL and the message appears in that channel.」且「**No bot or persistent connection required.**」<https://docs.discord.com/developers/platform/webhooks> |
| 需不需要註冊 application？ | **不需要。** 建立 webhook 只用 Discord App 的 Server Settings，不碰 Developer Portal。 | 上述支援文章的步驟裡完全沒有 Developer Portal |
| 需不需要 bot token？ | **不需要。** | 「They do not require a bot user or authentication to use.」 |
| 使用者要做幾件事？ | **四步：建立自己的私人 server（若無）→ Server Settings → Integrations → Create Webhook → Copy Webhook URL**，把 URL 貼進 `.env`。 | 同上 |
| 建立 webhook 需要什麼權限？ | `MANAGE_WEBHOOKS`。使用者在自己開的 server 是 owner，天然具備。 | "Create Webhook … Requires the `MANAGE_WEBHOOKS` permission." |

### 2.2 一個限制：webhook 只能貼到「頻道」，不能貼到 DM

Webhook 物件結構中：

> "`guild_id?` | ?snowflake | the guild id this webhook is for, if any"
> "`channel_id` | ?snowflake | **the channel id this webhook is for**, if any"

- 來源：<https://docs.discord.com/developers/resources/webhook>

**判定**：webhook 綁定在**某個 guild（server）的某個文字頻道**上。**沒有「webhook 直接送私訊（DM）」這條路。** 因此使用者的收訊模式必然是「開一個只有自己的私人 server，建一個 `#警示` 頻道」。這對本專案是可接受的，但要在文件裡寫清楚，避免使用者以為可以收 DM。

---

## 3. Rate limit：官方公布的與官方拒絕公布的

### 3.1 機制總則（含「不得硬編碼」的明文）

> "Rate limits exist across Discord's APIs to prevent spam, abuse, and service overload. Limits are applied to individual bots and users both **on a per-route basis and globally**. Individuals are determined using a request's authentication—for example, a bot token for a bot."

> "Because rate limits depend on a variety of factors and are subject to change, **rate limits should not be hard coded into your app**. Instead, your app should parse response headers to prevent hitting the limit, and to respond accordingly in case you do."

> "**Per-route rate limits** exist for many individual endpoints, and may include the HTTP method (`GET`, `POST`, `PUT`, or `DELETE`). In some cases, per-route limits will be shared across a set of similar endpoints, indicated in the `X-RateLimit-Bucket` header."

> "During calculation, per-route rate limits often account for **top-level resources** within the path using an identifier… Top-level resources are currently limited to channels (`channel_id`), guilds (`guild_id`), and **webhooks (`webhook_id` or `webhook_id + webhook_token`)**. This means that an endpoint with two different top-level resources may calculate limits independently."

- 來源（第一手）：<https://docs.discord.com/developers/topics/rate-limits>

**判定**：`webhook_id + webhook_token` **是 rate limit 的獨立計算單位**——這是官方唯一對「per-webhook 限制存在」的正面確認，但**沒有給數字**。

### 3.2 Global rate limit（唯一有數字的一項）

> "**All bots can make up to 50 requests per second to our API.** **If no authorization header is provided, then the limit is applied to the IP address.** This is independent of any individual rate limit on a route."

- 來源：同上

**這一句對本專案至關重要**：webhook 請求**不帶** `Authorization` header，所以 50 req/s 這個 global 限制**是按我們 `quote-worker` 的出站 IP 計算的**。單人每月數十到數百則，離 50 req/s 有數個數量級的餘裕，**不是瓶頸**；但若日後把 worker 放在共用出口 IP 的 PaaS 上，理論上會與同 IP 的其他租戶共享此額度（實務上不太可能觸及）。

### 3.3 回應標頭（官方完整列表）

官方給的範例與逐項說明：

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1470173023
X-RateLimit-Reset-After: 1
X-RateLimit-Bucket: abcd1234
```

> - "**X-RateLimit-Limit** - The number of requests that can be made"
> - "**X-RateLimit-Remaining** - The number of remaining requests that can be made"
> - "**X-RateLimit-Reset** - Epoch time (seconds since 00:00:00 UTC on January 1, 1970) at which the rate limit resets"
> - "**X-RateLimit-Reset-After** - Total time (in seconds) of when the current rate limit bucket will reset. Can have decimals to match previous millisecond ratelimit precision"
> - "**X-RateLimit-Bucket** - A unique string denoting the rate limit being encountered (non-inclusive of top-level resources in the path)"
> - "**X-RateLimit-Global** - Returned only on HTTP 429 responses if the rate limit encountered is the global rate limit (not per-route)"
> - "**X-RateLimit-Scope** - Returned only on HTTP 429 responses. Value can be `user` (per bot or user limit), `global` (per bot or user global limit), or `shared` (per resource limit)"

註記：「For **most** API requests made, we return **optional** HTTP response headers…」——**標頭是 optional，程式不能假設一定存在。**

### 3.4 429 的正確處理方式

> "In the case that a rate limit is exceeded, the API will return a HTTP 429 response code with a JSON body. **Your application should rely on the `Retry-After` header or `retry_after` field to determine when to retry the request.**"

429 回應主體結構：

| Field | Type | Description（官方原文） |
|---|---|---|
| `message` | string | "A message saying you are being rate limited." |
| `retry_after` | float | "The number of seconds to wait before submitting another request." |
| `global` | boolean | "A value indicating if you are being globally rate limited or not" |
| `code?` | integer | "An error code for some limits" |

官方三個範例回應（照抄）：

```
< HTTP/1.1 429 TOO MANY REQUESTS
< Content-Type: application/json
< Retry-After: 65
< X-RateLimit-Limit: 10
< X-RateLimit-Remaining: 0
< X-RateLimit-Reset: 1470173023.123
< X-RateLimit-Reset-After: 64.57
< X-RateLimit-Bucket: abcd1234
< X-RateLimit-Scope: user
{
  "message": "You are being rate limited.",
  "retry_after": 64.57,
  "global": false
}
```

```
< HTTP/1.1 429 TOO MANY REQUESTS
< Retry-After: 1337
< X-RateLimit-Scope: shared
{
  "message": "The resource is being rate limited.",
  "retry_after": 1336.57,
  "global": false
}
```

```
< HTTP/1.1 429 TOO MANY REQUESTS
< Retry-After: 65
< X-RateLimit-Global: true
< X-RateLimit-Scope: global
{
  "message": "You are being rate limited.",
  "retry_after": 64.57,
  "global": true
}
```

**注意 `retry_after` 是 float 秒數**（`64.57`），不是整數毫秒。

### 3.5 Invalid Request Limit（Cloudflare ban）——比 rate limit 更該小心的那個

> "IP addresses that make too many invalid HTTP requests are automatically and temporarily restricted from accessing the Discord API. Currently, this limit is **10,000 per 10 minutes**. **An invalid request is one that results in 401, 403, or 429 statuses.**"

> "*429 errors returned with `X-RateLimit-Scope: shared` are not counted against you.*"

> "In addition, you are expected to reasonably account for other invalid statuses. **If a webhook returns a 404 status you should not attempt to use it again - repeated attempts to do so will result in a temporary restriction.**"

- 來源：<https://docs.discord.com/developers/topics/rate-limits>

**判定**：最後一句是本專案「失敗補送」邏輯的硬約束——**404 是終局失敗，不得重試**。若補送機制盲目重試 404，會被 Cloudflare 暫時封鎖整個出站 IP，連帶讓其他管道也一起死。

### 3.6 未能查證的部分

- **per-webhook 的具體上限（例如流傳甚廣的「30 則/60 秒」）**：**未能查證，需人工確認。** Discord 官方文件從未公布任何 per-route／per-webhook 的數字，而且明文要求不得硬編碼。搜尋到的所有「30/min」「5 requests per 5 seconds per channel」出處皆為第三方部落格與論壇，依本專案來源政策不予採信。
- **per-channel 的 webhook 限制**：**未能查證，需人工確認。** 官方只說 `channel_id` 是 rate limit 的 top-level resource 之一，未給數字。
- **正確做法**：把 `X-RateLimit-Remaining` / `X-RateLimit-Reset-After` 當作唯一事實來源，遇 429 就依 `Retry-After` 退避。以單人每月數百則的量級，實際上幾乎不會觸發。

---

## 4. 訊息格式能力（決定通知文案能長什麼樣）

### 4.1 `content`：純文字上限 2000 字元

Execute Webhook 的 JSON/Form Params：

> "`content` | string | **the message contents (up to 2000 characters)** | one of content, file, embeds, poll"

且至少要給一個內容欄位：

> "Note that when sending a message, you must provide a value for at **least one of** `content`, `embeds`, `components`, `file`, or `poll`."

### 4.2 embeds：最多 10 個

> "`embeds` | **array of up to 10 embed objects** | embedded `rich` content | one of content, file, embeds, poll"

### 4.3 Embed 的欄位上限（官方 Embed Limits 表照抄）

> "To facilitate showing rich content, rich embeds do not follow the traditional limits of message content. However, some limits are still in place to prevent excessively large embeds."
>
> "All of the following limits are measured inclusively. **Leading and trailing whitespace characters are not included** (they are trimmed automatically)."

| Field | Limit |
|---|---|
| `title` | 256 characters |
| `description` | **4096 characters** |
| `fields` | **Up to 25 field objects** |
| `field.name` | 256 characters |
| `field.value` | 1024 characters |
| `footer.text` | 2048 characters |
| `author.name` | 256 characters |

> "Additionally, **the combined sum of characters in all `title`, `description`, `field.name`, `field.value`, `footer.text`, and `author.name` fields across all embeds attached to a message must not exceed 6000 characters. Violating any of these constraints will result in a `Bad Request` response.**"

> "Embeds are deduplicated by URL. If a message contains multiple embeds with the same URL, only the first is shown."

- 來源：<https://docs.discord.com/developers/resources/message>

### 4.4 顏色：支援，紅漲綠跌可直接做

Embed 物件結構：

> "`color?` | integer | **color code of the embed**"

- 來源：同上

**判定**：`color` 是一個 integer（實務上就是 `0xRRGGBB` 的十進位值），**本專案的「紅漲綠跌」可以直接用 embed 顏色條實作**，不需要靠 emoji 硬湊。（台股慣例：漲＝紅、跌＝綠，與美股相反，這點在文案層要記得。）

同一個 embed 還有 `timestamp`：

> "`timestamp?` | **ISO8601 timestamp** | timestamp of embed content"

### 4.5 Webhook embed 的額外限制

> "For the webhook embed objects, you can set **every field except `type`** (it will be `rich` regardless of if you try to set it), **`provider`, `video`, and any `height`, `width`, or `proxy_url` values for images**."

- 來源：<https://docs.discord.com/developers/resources/webhook>

### 4.6 Markdown：官方支援

> "Discord utilizes **a subset of markdown** for rendering message content on its clients, while also adding some custom functionality to enable things like mentioning users and channels."

- 來源：<https://docs.discord.com/developers/reference>

支援中心「Markdown Text 101」列出的完整語法（照抄）：

> Italics `*italics*` or `_italics_`；Bold `**bold**`；Bold Italics `***bold italics***`；Underline `__underline__`；Strikethrough `~~Strikethrough~~`；Headers `#` / `##` / `###`；Subtext `-#`；Masked links `[文字](URL)`；Lists `-` / `*` / `1.`（縮排用 2 個空格）；inline code `` ` ``；code block ` ``` `；Block quotes `>` 與多行 `>>>`；Spoiler `||文字||`

> "Note: Don't forget to add a space between the leading heading character (`#`, `##`, `###`) and your text!"

- 來源：<https://support.discord.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline>

**Timestamp 格式化**（對「觸發時間」欄位很好用）：官方 Message Formatting 提供 `<t:UNIX:style>` 語法，8 種 style（`t`、`T`、`d`、`D`、`f`、`F`、`s`、`S`、`R`），預設 `f`，且「display in the user's timezone and locale」。
- 來源：<https://docs.discord.com/developers/reference>

**未能查證，需人工確認**：官方文件**沒有明文說** markdown 在 **embed 的 `description` / `field.value` 內是否同樣被渲染**（Message Formatting 頁只講 "message content"）。實務上業界普遍認為可以，但**這是二手說法，不予採信**——若要用 embed 內的粗體／連結，請先手動送一則測試訊息驗證。

### 4.7 內容清洗的官方警告

> "**Discord may strip certain characters from message content**, like invalid unicode characters or characters which cause unexpected message formatting. If you are passing user-generated strings into message content, consider **sanitizing the data** to prevent unexpected behavior and **using `allowed_mentions` to prevent unexpected mentions.**"

- 來源：<https://docs.discord.com/developers/resources/webhook>

**判定**：股票名稱／備註若含使用者自填文字，應設 `allowed_mentions: {"parse": []}` 以杜絕誤觸 `@everyone`。

---

## 5. 可靠性與錯誤語意

### 5.1 成功回應：`204` 與 `200` 的差別，以及 `wait` 這個陷阱

> "**Execute Webhook** — `POST /webhooks/{webhook.id}/{webhook.token}` — … **Returns a message or `204 No Content` depending on the `wait` query parameter.**"

`wait` 參數的官方定義（**這是本節最重要的一句**）：

> "`wait` | boolean | **waits for server confirmation of message send before response, and returns the created message body** (**defaults to `false`; when `false` a message that is not saved does not return an error**) | Required: false"

- 來源：<https://docs.discord.com/developers/resources/webhook>

**逐項判定**：

| 情境 | 回應 | 語意 |
|---|---|---|
| 不帶 `wait`（預設 `false`） | `204 No Content` | **只代表 Discord 收下了請求。官方明說「訊息沒被存下來也不會回報錯誤」。這是 fire-and-forget，不能當成投遞證據。** |
| 帶 `?wait=true` | `200` + message 物件（含 `id`） | 代表**「server confirmation of message send」**，訊息已在 Discord 端建立、拿得到 message id。 |

> **對本專案的直接後果**：若 `AlertDelivery` 要落地「已送達」狀態，**必須用 `?wait=true`**，並把回傳的 `message.id` 存起來（同時也是日後 Edit／Delete 該訊息的鑰匙）。用預設的 `204` 當成功，等於在記錄一件自己沒驗證過的事——這正是本專案明確排斥的「看起來合理就繼續跑」。

順帶一提，Slack 相容與 GitHub 相容端點的 `wait` **預設值相反**（`defaults to `true``），但本專案不會用到那兩個端點。

### 5.2 HTTP 2xx 代表什麼——絕對不代表「已投遞到裝置」

Discord 官方 HTTP 狀態碼表：

| Code | 官方原文 |
|---|---|
| 200 (OK) | "The request completed successfully." |
| 201 (CREATED) | "The entity was created successfully." |
| 204 (NO CONTENT) | "The request completed successfully but returned no content." |
| 400 (BAD REQUEST) | "The request was improperly formatted, or the server couldn't understand it." |
| 401 (UNAUTHORIZED) | "The `Authorization` header was missing or invalid." |
| 403 (FORBIDDEN) | "The `Authorization` token you passed did not have permission to the resource." |
| 404 (NOT FOUND) | "The resource at the location specified doesn't exist." |
| 405 (METHOD NOT ALLOWED) | "The HTTP method used is not valid for the location specified." |
| 429 (TOO MANY REQUESTS) | "You are being rate limited, see Rate Limits." |
| 502 (GATEWAY UNAVAILABLE) | "There was not a gateway available to process your request. Wait a bit and retry." |
| 5xx (SERVER ERROR) | "The server had an error processing your request (these are rare)." |

- 來源：<https://docs.discord.com/developers/topics/opcodes-and-status-codes>

**判定**：`200`／`204` 的語意上限是「**Discord 收下 / Discord 已建立訊息物件**」。**沒有任何欄位、標頭或事件表示「使用者裝置已收到推播」或「使用者已讀」。**

### 5.3 有沒有投遞回執機制？——沒有

**未能查證到任何投遞回執機制，且有反面的明文佐證**：官方在 `allowed_mentions` 一節直接承認推播不保證：

> "It is important to note that setting this field **does not guarantee a push notification will be sent**, as additional factors can influence this: … **Users can customize their notification settings through the Discord app, which might cause them to only receive a notification badge and no push notification**"

- 來源：<https://docs.discord.com/developers/resources/message>

**判定**：Discord webhook 提供的最強保證是「訊息已存進頻道」（`wait=true`）。**「使用者是否真的被通知到」在 Discord 的 API 表面上不可觀測。** 任何宣稱能追蹤投遞的設計都不成立。

### 5.4 webhook 被刪除／頻道被刪除時的回應——失敗補送的判定依據

Discord 的 JSON error code（回應主體中的 `code` 欄位）：

| Code | 官方原文 | 對應情境 |
|---|---|---|
| `10015` | "Unknown webhook" | **webhook 被刪除**（或 id 根本不存在） |
| `50027` | "Invalid webhook token provided" | **token 錯誤／URL 被改過** |
| `10016` | "Unknown webhook service" | webhook 服務不存在 |
| `10003` | "Unknown channel" | 頻道不存在 |
| `50073` | "Cannot modify a system webhook" | 系統 webhook |
| `220001` | "Webhooks posted to forum channels must have a thread_name or thread_id" | 貼到論壇頻道未給 thread |

- 來源：<https://docs.discord.com/developers/topics/opcodes-and-status-codes>

搭配 rate-limit 頁的那句硬規定：

> "**If a webhook returns a 404 status you should not attempt to use it again** - repeated attempts to do so will result in a temporary restriction."

**判定（失敗補送的分類規則）**：

| 回應 | 分類 | 應對 |
|---|---|---|
| `200`（`wait=true`）／`204` | 成功（前者為已確認，後者僅為已接收） | 落地 `sent`（`204` 只能落地 `submitted`） |
| `429` | **暫時性** | 依 `Retry-After` 退避後重試 |
| `502` / `5xx` | **暫時性** | 官方原文即建議 "Wait a bit and retry"，指數退避重試 |
| `404`（含 `code: 10015`／`50027`） | **終局失敗** | **禁止重試**，標記為 `dead`，並在站內／備援管道提示「Discord webhook 已失效，請重建並更新 `.env`」 |
| `400` | **終局失敗** | 是我方 payload 有問題（超長、超 6000 字元等），重試無用，落地錯誤詳情 |
| `403` | **終局失敗** | 計入 invalid request 額度，禁止重試 |

**未能查證，需人工確認**：**「頻道被刪除但 webhook 尚在」時 Discord 回什麼**（是 `404`+`10003 Unknown channel`，還是 webhook 一併被刪而回 `10015`）。官方文件未描述此情境的實際回應。保守做法：只要收到 `404`，一律當終局失敗處理，符合官方「should not attempt to use it again」的指示。

### 5.5 官方對可用性的免責聲明

Discord Developer Terms of Service：

> "NEITHER DISCORD NOR ITS AFFILIATES, SUPPLIERS, OR DISTRIBUTORS MAKE ANY SPECIFIC PROMISES ABOUT THE APIs… **WE DON'T MAKE ANY COMMITMENTS OR WARRANTIES ABOUT THE SPECIFIC FUNCTIONS OF THE APIs OR THE RELIABILITY, AVAILABILITY, ACCURACY, QUALITY… YOU ACKNOWLEDGE THAT WE DO NOT WARRANT THAT THE APIs WILL BE UNINTERRUPTED, TIMELY, SECURE, OR ERROR-FREE, AND WE MAY CHANGE, SUSPEND, OR DISCONTINUE THE AVAILABILITY OF THE APIs AT ANY TIME.** WE PROVIDE THE APIs, API DATA, AND DOCUMENTATION "AS IS" AND YOU USE THEM AT YOUR SOLE RISK."

- 來源：<https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service>

**判定**：**沒有 SLA。** 這與 Telegram、LINE 同級，屬於免費管道的常態；不構成排除 Discord 的理由，但構成「不能把 Discord 當唯一通報路徑」的理由。

---

## 6. 服務存廢與政策風險（對照 LINE Notify 之死）

### 6.1 有沒有棄用計畫？——查不到

查證方式：逐條檢視官方 Change Log 中所有含 "webhook" 的條目。

- 來源：<https://docs.discord.com/developers/change-log>

**結果**：**截至 2026-08-05，官方 Change Log 中沒有任何宣告 Incoming Webhook（`POST /webhooks/{id}/{token}`）棄用、落日或移除的條目。** 近期與 webhook 相關的條目都是「新增」性質（如 `APPLICATION_DEAUTHORIZED` webhook event、forum/media channel 的 `thread_name` 支援），或是與 Incoming Webhook 無關的其他端點棄用（例如 pinned messages 舊端點被 deprecate）。

**注意用詞**：這是「**查不到棄用公告**」，不等於「**保證不會棄用**」。LINE Notify 也是在終止前一年才公告的。本文只陳述「今天查不到」這個事實。

### 6.2 有沒有自架／自用場景的條款限制？

**先確認條款適不適用於我們。** Developer ToS 對 "Application" 的定義：

> "**"Application" (or "app") means any application (including any bot, game, activity, website, or other client) that accesses or uses our APIs** or to which we have assigned an Application ID."

- 來源：<https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service>

**判定**：即使我們沒在 Developer Portal 註冊、沒有 Application ID，只要 `quote-worker` 用 HTTP 存取 Discord API（webhook 端點就是 API），**它就是條款定義下的 "Application"，Developer ToS 與 Developer Policy 全部適用。** 「只是打個 webhook，應該不算 app」這個直覺是錯的。

在此前提下，兩條真正相關的限制：

**(a) Developer Policy 第 16 條——金融資訊條款（本專案的實質風險）**

> "Furthermore, you may not, and may not use your Application to, obtain API Data or **transmit data to Discord** (i) of persons under the age of 13 … or (ii) **that includes protected health information, financial information, or other sensitive information under applicable law**, except to the extent specifically allowed by our Terms for a given Discord service or if necessary to process a financial transaction as enabled by a Discord service."

- 來源：<https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy>

**這一條直接打到本專案的核心用途。** 本專案要送的內容是「使用者本人的持股標的、成本、未實現損益」——**這在字面上就是 "financial information"**，而且是 transmit **to** Discord。

需要如實陳述的邊界：

- 條款寫的是 "**under applicable law**"（依適用法律認定的敏感資訊），而非「任何跟錢有關的字串」。個人自願把自己的損益數字貼進自己的私人頻道，與「蒐集他人金融資訊並上傳」在性質上相差很遠。
- 該條的立法意旨顯然是防止開發者把**使用者群體**的敏感資料匯入 Discord，本專案是**單人、資料主體＝資料傳送者本人**。
- **但官方沒有為「自用」開任何例外。** 條款文字裡沒有 "personal use" 或 "self-hosted" 的豁免。
- **未能查證，需人工確認**：Discord 官方是否有針對「使用者本人把自己的財務資料送進自己的頻道」的明確表態。查遍 Developer Policy、Developer ToS、Safety Library 皆無此類說明。

**可降低曝險的做法（陳述選項，不做決策）**：警示文案只寫「代號、名稱、觸發規則、當前價」，**把成本、部位大小、未實現損益留在站內儀表板**，Discord 只當「敲門聲」。這同時也降低了 webhook URL 洩漏時的資訊損害面，且與 MEMORY 中「持股資訊不可進 public repo」的既有戒心一致。

**(b) Developer ToS——閒置 30 天可能被回收**

> "Without limiting any of the foregoing, we may also **limit, suspend, or terminate your Application's access tokens or any other means of access to the APIs that have not been used or accessed within at least the prior 30-day period**, with or without notice to you."

- 來源：<https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service>

**判定**：`quote-worker` 只在台股盤中開機，若遇長假或使用者停用數週，webhook 有被回收的條款依據。**實務上是否真的對 webhook token 執行過此條款，未能查證。** 若在意，可加一則「每週心跳訊息」讓 token 保持活躍——代價是每週一則雜訊。

**(c) 其他 Developer Policy 條文**（與本專案無衝突，列出供對照）：

> "15. Do not use API Data for any purpose outside of what is necessary to provide your stated functionality."
> "17. Do not disclose API Data to data brokers, advertising networks or services, or any other monetization-related service."
> "18. Do not sell, license, or otherwise commercialize API Data or any of Discord's services."
> "13. Do not misrepresent or fraudulently manipulate engagement. … **This also includes automating messages to be sent for the purpose of maintaining activity in a Discord server.**"

**注意第 13 條與上面 (b) 的「心跳訊息」方案有張力**：「為了維持 server 活躍而自動送訊息」正是第 13 條禁止的行為之一。**兩個規避手段互相牴觸**，若採用心跳保活方案需自行評估。

### 6.3 費用

Incoming Webhook 的建立與使用在官方文件與支援文章中**沒有任何收費或額度描述**——不像 LINE 有明確的「每月 200 則」天花板。**未能查證，需人工確認**：Discord 是否在任何官方頁面公布過 webhook 的免費用量上限。查遍開發者文件、rate-limits 頁與支援中心均無此類敘述；rate limit 是唯一的節流機制，而非計費額度。

---

## 7. 推播行為

### 7.1 官方明文：推播不保證

> "It is important to note that setting this field **does not guarantee a push notification will be sent**, as additional factors can influence this:
> - To mention roles and notify their members, the role's `mentionable` field must be set to `true`, or the bot must have the `MENTION_EVERYONE` permission
> - To mention `@everyone` and `@here`, the bot must have the `MENTION_EVERYONE` permission
> - **Setting the `SUPPRESS_NOTIFICATIONS` flag when sending a message will disable push notifications and only cause a notification badge**
> - **Users can customize their notification settings through the Discord app, which might cause them to only receive a notification badge and no push notification**"

- 來源：<https://docs.discord.com/developers/resources/message>

### 7.2 手機 App 的推播是否需要額外設定？

官方支援文章「Notifications Settings 101」：

> "**Mobile Push Notifications**: **When you're signed in on your Android or iOS device, you'll get push notifications for anything you'd normally be notified about on desktop.** Pretty convenient!"

- 來源：<https://support.discord.com/hc/en-us/articles/215253258-Notifications-Settings-101>

Server 層級的三個選項（官方原文）：

> "**All Messages**: Any message posted in this server triggers a notification, based on your app notification settings."
> "**Only @mentions**: Only specific @mentions will trigger a notification. This includes direct @username, @role, @everyone, and @here."
> "**Nothing**: No messages in this server will trigger a device notification."
> "**Mobile Push Notifications**: When enabled, push notifications for this server come through to your mobile device."

一個容易忽略的官方註記：

> "**Note: Regardless of the settings below, you won't receive notifications while the Discord app is open and in focus on your device.**"
>
> （不論下列設定為何，**當 Discord App 在你的裝置上開啟並位於前景時，你不會收到通知。**）

作業系統層則是另一道獨立關卡：

> "Discord's in-app Notification Settings screen controls **whether** Discord sends you a notification at all. Once Discord decides to notify you, **your device's OS-level settings** … control **how** that notification actually appears on your phone, whether as a banner, sound, badge, and so on."

> "**All Discord notifications**: This acts as your master notification control. Disabling it means Discord won't send any push or banner notifications when you receive activity."（Android）

> "Unlike Android, **the iOS app doesn't have a global notifications menu within Discord**. App-wide notification settings are managed through your device's settings: open **Settings > Notifications > Discord**."（iOS）

- 來源：<https://support.discord.com/hc/en-us/articles/218892547--Mobile-Notifications-Settings-101>

**判定**：推播需要三層都放行 —— (1) server 通知等級不是 `Nothing`、未 Mute、且 `Mobile Push Notifications` 開啟；(2) Discord App 內的通知設定；(3) OS 層的 Discord 通知權限。**這三層都在使用者手上，我們的程式無法從 API 端觀測或保證。**

### 7.3 「只在自己的私人 server 收通知，預設會不會有推播？」

**未能查證，需人工確認。** 官方文件**完整描述了三個選項的行為**（`All Messages` / `Only @mentions` / `Nothing`），但**從未明文寫出「新加入或新建立的 server，預設值是哪一個」**。網路上普遍說法是小型 server 預設 `All Messages`、超過一定人數改為 `Only @mentions`，但**這在 Discord 官方文件中查不到，不予採信**。

**實務上的唯一可靠做法**：請使用者在建好私人 server 後，**手動確認**該 server 的 Notification Settings 為 `All Messages`、`Mobile Push Notifications` 開啟、未 Mute，並實際送一則測試訊息驗證手機真的響。**這是一個必須寫進 setup 文件的人工驗收步驟，不能靠假設。**

### 7.4 靜音時段：Discord 也有 `disable_notification` 的對等物

Message Flags 表：

> "| `SUPPRESS_NOTIFICATIONS` | `1 << 12` | **this message will not trigger push and desktop notifications** |"

而 Execute Webhook 明確允許設定它：

> "`flags` | integer | message flags combined as a bitfield (**only `SUPPRESS_EMBEDS`, `SUPPRESS_NOTIFICATIONS` and `IS_COMPONENTS_V2` can be set**) | Required: false"

- 來源：<https://docs.discord.com/developers/resources/message>、<https://docs.discord.com/developers/resources/webhook>

**判定**：靜音送出 = `"flags": 4096`（`1 << 12`）。語意是「訊息照樣送達頻道，但不觸發推播與桌面通知，只留下未讀 badge」——**與 Telegram 的 `disable_notification` 語意幾乎相同**（差別：Telegram 是「有通知但無聲」，Discord 是「完全不發推播、只留 badge」，Discord 更安靜）。

**對「iOS 不用即時通知沒關係」的直接意義**：使用者這句話的落地方式有兩條，代價不同——

| 做法 | 效果 | 代價 |
|---|---|---|
| 使用者自己在手機端 Mute 那個 server | 手機完全不吵，桌面照常 | 我方零程式碼；但**桌面與手機無法分開控制內容**，且 Mute 期間錯過的訊息只能靠回頻道翻 |
| 我方對特定警示帶 `flags: 4096` | 該則訊息在**所有裝置**都不推播，只留 badge | 桌面也一起靜音了。**Discord 沒有「只對某個裝置靜音」的 API。** |

---

## 8. 附帶：Telegram Bot API 的 `disable_notification`

**有這個參數，且語意明確。** `sendMessage` 的官方參數表：

> "`disable_notification` | Boolean | Optional | **Sends the message silently. Users will receive a notification with no sound.**"

同一方法的其他相關參數：

> "`text` | String | Yes | **Text of the message to be sent, 1-4096 characters after entities parsing**"
> "`parse_mode` | String | Optional | Mode for parsing entities in the message text. See formatting options for more details."
> "`protect_content` | Boolean | Optional | Protects the contents of the sent message from forwarding and saving"

回應語意：

> "**sendMessage** — Use this method to send text messages. **On success, the sent Message is returned.**"

- 來源（第一手）：<https://core.telegram.org/bots/api>

**與 Discord 的差異**：

| | Telegram `disable_notification` | Discord `SUPPRESS_NOTIFICATIONS` |
|---|---|---|
| 語意 | 「**有通知，但無聲**」 | 「**完全不觸發推播與桌面通知，只留 badge**」 |
| 成功回應 | **一律回傳完整 Message 物件**（不需額外參數） | 預設回 `204`（無確認），需 `?wait=true` 才回 Message 物件 |
| 文字上限 | 4096 字元 | `content` 2000 字元 / embed `description` 4096 字元 |
| 顏色 | **不支援**（只能靠 emoji） | **支援**（embed `color`） |

順帶查得的 Telegram 速率限制（官方 FAQ 原文）：

> "In a single chat, **avoid sending more than one message per second.** We may allow short bursts that go over this limit, but eventually you'll begin receiving 429 errors."
> "In a group, bots are not be able to send more than **20 messages per minute**."
> "For bulk notifications, bots are not able to broadcast more than about **30 messages per second**, unless they enable paid broadcasts to increase the limit."

- 來源：<https://core.telegram.org/bots/faq>

**這是本份研究裡唯一有「官方公布的具體 per-chat 數字」的管道。** Telegram 公布數字、Discord 不公布並要求讀標頭——兩種哲學，處理程式碼的寫法會不同。

---

## 9. 未能查證清單（需人工確認）

集中列出，方便後續補洞。**以下每一項都不得以推測代替。**

| # | 未能查證的事項 | 為什麼重要 | 建議的確認方式 |
|---|---|---|---|
| 1 | Discord App UI 是否提供「重新產生 webhook URL」而不必刪除重建 | 決定憑證輪替的 runbook | 開一個測試 server 實測 Server Settings → Integrations |
| 2 | per-webhook / per-channel 的實際 rate limit 數字 | 決定是否需要送出端節流 | 官方拒絕公布；只能靠讀 `X-RateLimit-*` 標頭，**不要去實測撞牆**（會計入 invalid request 額度） |
| 3 | Markdown 是否在 embed `description` / `field.value` 內被渲染 | 決定文案能否在 embed 內用粗體／連結 | 手動送一則測試訊息目視確認 |
| 4 | 「頻道被刪除但 webhook 仍在」時的確切回應碼 | 影響失敗分類的精度（實務上一律當 404 終局失敗即可） | 測試 server 上刪一個綁了 webhook 的頻道再打一次 |
| 5 | 新建 server 的預設通知等級是否為 `All Messages` | 決定 setup 文件要不要強制一步人工設定 | **一律當作「不確定」，setup 文件強制要求使用者手動確認並實測** |
| 6 | Discord 是否對 webhook 有任何免費用量上限／計費 | 對照 LINE 的 200 則/月天花板 | 官方無敘述；以 rate limit 為唯一節流機制 |
| 7 | Developer Policy 第 16 條「financial information」是否涵蓋「使用者本人的自用持股損益」 | **本專案最大的政策不確定性** | 官方無表態。可考慮以「文案不含金額與部位」的設計繞開，而非賭解釋 |
| 8 | 閒置 30 天回收條款是否真的對 webhook token 執行過 | 決定要不要做心跳保活（且該方案與 Policy 第 13 條有張力） | 官方無案例可查 |

---

## 10. 對 issue #15 的影響

以下逐項對照 #15 既有的推論與 `alert-notification-channels.md` 的結論，說明因為改用 Discord 而**需要修改**的部分。**只陳述影響與代價，不做決策。**

### 10.1 「Telegram 為主推播管道」——前提已被使用者推翻，但推論本身仍成立

- **既有推論**：`alert-notification-channels.md` 第 0 節結論 3 認定「Telegram Bot 是唯一『免費 + 無月額度 + 即時 + 跨 iOS/Android』的推播管道」，並在推薦組合中把 Telegram 放在行動端主力。
- **需要修改**：把「主推播 = Telegram」改為「主推播 = Discord webhook」。**但該推論的事實基礎沒有錯**——Discord 只是同樣滿足「免費、無月額度、即時、跨平台」，並在本專案多加了三個 Telegram 沒有的優勢：**(a) 不需要註冊 bot（連 BotFather 都不用開）、(b) 有 embed 顏色（紅漲綠跌）、(c) 送出端多了 `wait=true` 這個明確的「已建立」確認**。
- **反向的代價（必須寫進 #15）**：
  1. **文字上限從 4096 掉到 2000**（`content`）。若要長文案必須改用 embed（`description` 4096），但整則訊息受 6000 字元總和上限約束。
  2. **Discord 預設回 `204` 不代表送成功**——Telegram 的 `sendMessage` 是無條件回傳 Message 物件，Discord 要自己記得加 `?wait=true`。這是換管道後**最容易寫錯的一行**。
  3. **收訊模式從「DM」變成「私人 server 的頻道」**。webhook 無法送 DM（webhook 物件綁 `channel_id`），使用者必須自建 server。setup 步驟變多一步。
  4. **多了一層「使用者端通知設定」的不可觀測性**。Telegram bot 對話預設就會推播；Discord 的 server 預設通知等級**未能查證**，必須靠人工驗收。

### 10.2 `ChannelCapabilities` 抽象化——維度需要增補，且不能再假設「格式能力可以共通」

- **既有推論**：以 `ChannelCapabilities` 描述各管道能力，讓觸發引擎與管道解耦。
- **需要修改**：既有維度多半圍繞 Telegram / Web Push / Email 設計。Discord 帶進了幾個**既有維度裝不下**的新事實：

| 新增／修改的維度 | Discord | Telegram | 依據 |
|---|---|---|---|
| `max_plain_text_len` | 2000 | 4096 | 官方 params 表 |
| `max_rich_text_len` | 4096（embed description） | 不適用 | Embed Limits |
| `max_total_chars_per_message` | **6000（跨所有 embed 的合計）** | 不適用 | "combined sum … must not exceed 6000 characters" |
| `max_rich_blocks_per_message` | **10（embeds）** | 不適用 | "array of up to 10 embed objects" |
| `supports_color` | **是**（embed `color` integer） | **否** | Embed 物件 |
| `supports_markdown` | 是（subset；**embed 內未能查證**） | 是（`parse_mode`） | Message Formatting / Bot API |
| `supports_silent_send` | 是（`flags: 1 << 12`） | 是（`disable_notification`） | Message Flags / Bot API |
| `silent_semantics` | **完全不推播、只留 badge** | **有通知、但無聲** | 兩邊官方原文不同，**不可視為同一件事** |
| `confirms_persistence` | **僅在 `wait=true` 時** | 一律 | `wait` 參數定義 |
| `credential_shape` | **URL 即憑證**（單一字串） | bot token + chat_id（兩段） | Webhook Resource |
| `publishes_rate_limit_numbers` | **否（且禁止硬編碼）** | 是（1/s per chat、20/min group） | Rate Limits / Bot FAQ |

- **一個必須寫進抽象層的硬約束**：`supports_silent_send` **不能**被抽象成同一個布林值就當作等價——Telegram 是「無聲通知」、Discord 是「無推播只有 badge」。若靜音時段的產品意圖是「使用者事後看得到但當下不被吵」，兩者都成立；若意圖是「使用者仍應在鎖定畫面看到」，**Discord 做不到**。這個差異必須在 `ChannelCapabilities` 上顯性化，否則會在換管道時默默改變行為。
- **`publishes_rate_limit_numbers` 這個維度是新的**：Telegram 可以在客戶端寫死節流器（1 則/秒/chat），Discord **明文禁止硬編碼**，只能讀標頭 + 依 `Retry-After` 退避。**節流策略不能共用同一份程式碼**，抽象層必須容納「宣告式限制」與「反應式限制」兩種模型。

### 10.3 「投遞狀態落地」——語意需要重新定義，而且必須新增一個中間狀態

- **既有推論**：把每則警示的投遞狀態寫進資料庫，作為稽核與補送依據。
- **需要修改**：Discord 的回應語意讓「成功」不再是二元的。

| 狀態 | 定義（Discord 語境） | 觸發條件 |
|---|---|---|
| `pending` | 尚未送出 | — |
| `submitted` | **Discord 收下了請求，但沒有任何證據訊息被存下來** | 用預設 `wait=false` 收到 `204`。官方原文：「when `false` a message that is not saved does not return an error」 |
| `sent` | **Discord 已建立訊息物件，拿得到 `message.id`** | 用 `?wait=true` 收到 `200` + message body |
| `retrying` | 暫時性失敗 | `429`（依 `Retry-After`）、`502`/`5xx` |
| `dead` | **終局失敗，禁止重試** | `404`（`10015` / `50027`）、`400`、`403` |

- **建議把 `submitted` 這個狀態直接消滅的做法**：一律帶 `?wait=true`，讓成功只有 `sent` 一種。代價是每次送出多等一個 server round-trip（毫秒級，對每月數百則毫無影響），收益是**狀態表不再記錄無法驗證的事**。**這正是 #15 「投遞狀態落地」原本想要的東西——用 Telegram 時它是免費的，用 Discord 時必須主動要。**
- **新增欄位**：`provider_message_id`（Discord 回傳的 `message.id`）。這不只是稽核用——它是日後「編輯已送出的警示」（例如把「觸發中」改成「已解除」）或「刪除誤發警示」的唯一鑰匙（`PATCH` / `DELETE /webhooks/{id}/{token}/messages/{message.id}`）。**Telegram 方案下這個欄位可有可無，Discord 方案下它是能力解鎖點。**
- **新增一條硬規則**：`404` 進 `dead` 後，**補送機制必須永久停止對該 webhook 的重試**，並改由站內通知告知使用者「webhook 已失效」。官方原文：「If a webhook returns a 404 status you should not attempt to use it again - repeated attempts to do so will result in a temporary restriction」。**若沿用既有的「無腦指數退避重試到成功為止」邏輯，會導致整個出站 IP 被 Cloudflare 暫時封鎖，連帶讓其他管道一起失效。這是換成 Discord 後新增的、既有設計沒有考慮的失敗模式。**

### 10.4 「站內通知寫入資料庫當單一事實來源」——不變，而且理由更強了

- Discord 官方明說推播不保證（"does not guarantee a push notification will be sent"），且**沒有任何投遞回執**。「Discord 只是敲門聲、真相在站內」的既有設計**完全不需要修改**，且現在有官方原文背書。
- **唯一的增補**：站內通知現在還必須承擔「Discord webhook 已失效」這類**管道自身的故障告警**，因為 `404` 之後沒有其他路徑能通知使用者。

### 10.5 憑證管理——形狀變了，威脅模型也變了

- **既有推論**：Telegram 需要 `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` 兩個環境變數。
- **需要修改**：Discord 只需要**一個** `DISCORD_WEBHOOK_URL`，但**這一個字串的權限比 Telegram 的 chat_id 危險**：任何持有者可以**不需認證地刪除這個 webhook**（`DELETE /webhooks/{id}/{token}` "does not require authentication"）。
- **對 public repo 的具體要求**（比既有的「走 `.env`」更嚴格）：
  1. `.env` 且 `.gitignore`——既有規則，不變；
  2. **錯誤日誌與例外訊息必須遮蔽 URL**。Python 的 `requests`／`httpx` 在拋 `HTTPStatusError` 時預設會把完整 URL 放進訊息裡，**一旦這種 traceback 被貼進 issue 或 commit，webhook 就洩漏了**。這是 Telegram 方案沒有的風險（Telegram 的 token 在 URL 裡也有同樣問題，但既有研究沒點出來）；
  3. **文件、範例、測試 fixture 一律用 `https://discord.com/api/webhooks/<REDACTED>`**；
  4. 撤銷 runbook：目前唯一有官方依據的做法是**刪掉重建 + 更新 `.env`**（是否能只 rotate token **未能查證**）。

### 10.6 新增的政策風險項——這是 #15 原本完全沒有的一條

- **Developer Policy 第 16 條禁止 "transmit data to Discord … that includes … financial information … under applicable law"**，而本專案的預設文案就是持股損益。
- **這條在 Telegram 方案下不存在對等條款**（Telegram Bot API 的服務條款沒有等價的金融資訊限制）。**換到 Discord 是新增了一個 Telegram 沒有的合規面風險。**
- 選項與代價（不做決策）：
  - **選項 A：文案只寫「代號 + 名稱 + 規則 + 現價」，金額與部位留在站內。** 代價：使用者收到警示後要點進儀表板才知道賺賠多少，多一次操作；收益：同時降低 URL 洩漏的資訊損害面，且與 MEMORY 中「持股資訊不可進 public repo」的既有戒心一致。
  - **選項 B：照送完整損益。** 代價：承擔第 16 條的解釋風險（雖然執法機率極低，且資料主體＝傳送者本人）；收益：通知自足，不必點進儀表板。
  - **選項 C：把 Discord 降為「敲門聲」、真正的損益數字走 Email 或站內。** 代價：多維護一個管道。

### 10.7 不受影響的既有結論

- **LINE 的評估不變**（Notify 已死、Messaging API 每月 200 則天花板）。
- **Web Push 的評估不變**（iOS 需加入主畫面）。
- **Email 作為備援與稽核軌跡的定位不變**。
- **「≤30 分鐘送達」的要求**：Discord webhook 是同步 HTTP POST，延遲是網路 round-trip 級（毫秒到秒），**遠優於要求**。真正的延遲風險不在 Discord，而在使用者端的通知設定（見 7.3，未能查證預設值）。

---

## 附錄：本文引用的全部第一手來源

**Discord 開發者文件**
- Webhook Resource：<https://docs.discord.com/developers/resources/webhook>
- Message Resource（含 Embed Limits、Message Flags、Allowed Mentions）：<https://docs.discord.com/developers/resources/message>
- Rate Limits：<https://docs.discord.com/developers/topics/rate-limits>
- Opcodes and Status Codes（HTTP 與 JSON error codes）：<https://docs.discord.com/developers/topics/opcodes-and-status-codes>
- Reference（Message Formatting、Timestamp Styles）：<https://docs.discord.com/developers/reference>
- Webhooks 平台總覽：<https://docs.discord.com/developers/platform/webhooks>
- Change Log：<https://docs.discord.com/developers/change-log>

**Discord 官方支援與法務**
- Intro to Webhooks（建立步驟）：<https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks>
- Markdown Text 101：<https://support.discord.com/hc/en-us/articles/210298617-Markdown-Text-101-Chat-Formatting-Bold-Italic-Underline>
- Notifications Settings 101：<https://support.discord.com/hc/en-us/articles/215253258-Notifications-Settings-101>
- [Mobile] Notifications Settings 101：<https://support.discord.com/hc/en-us/articles/218892547--Mobile-Notifications-Settings-101>
- Using Webhooks and Embeds（Safety Library）：<https://discord.com/safety/using-webhooks-and-embeds>
- Discord Developer Terms of Service：<https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service>
- Discord Developer Policy：<https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy>

**Telegram 官方文件**
- Bot API（`sendMessage`）：<https://core.telegram.org/bots/api>
- Bot FAQ（速率限制）：<https://core.telegram.org/bots/faq>

**本專案既有研究**
- [`alert-notification-channels.md`](./alert-notification-channels.md)（LINE／Telegram／Web Push／Email 的評估，本文為其 Discord 補遺）
