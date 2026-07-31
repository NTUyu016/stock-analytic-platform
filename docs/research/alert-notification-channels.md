# 研究：價格／損益警示觸發時的通知管道選型

- **對應 issue**：[#7 研究：即時警示的通知管道選項](https://github.com/NTUyu016/stock-analytic-platform/issues/7)（隸屬 wayfinder 地圖 #1）
- **查證日期**：2026-08-01
- **來源政策**：僅採信第一手來源（LINE Developers／LINE Biz-Solutions 官方、W3C／IETF 規格、MDN、WebKit／Apple 官方、Telegram 官方文件、各郵件服務官方定價頁）。查不到官方數據者一律標註「未能查證」。

---

## 0. 結論摘要（TL;DR）

1. **LINE Notify 確定已死**：2025-03-31 終止，2025-04-01 起所有 API 全面失效，官方指定改用 Messaging API 的 push message。
2. **LINE 仍可個人申請、且不需公司登記**，但台灣免費（輕用量）方案**每月只有 200 則推播**，且**輕用量不能加購訊息**，超量只能等下個月或升級中用量（NT$800/月，3,000 則）。對「每分鐘可能觸發」的股價警示而言，這是硬天花板。
3. **Telegram Bot 是唯一「免費 + 無月額度 + 即時 + 跨 iOS/Android」的推播管道**，申請只要跟 BotFather 講一句 `/newbot`，零審核、零費用。
4. **Web Push 在 iOS 上仍必須「加入主畫面」才能收到通知**（MDN BCD 註記與 WebKit 官方文章一致，直到 Safari 26.6 / 2026-07-27 都沒有解除此限制）。桌面與 Android 則完全堪用且零成本。
5. **Email 適合當備援與稽核軌跡，不適合當即時警示**：Resend 免費 3,000 封/月但**每日上限 100 封**；SendGrid 免費方案已於 2025-05-27 退場改成 60 天試用；SES 走用量計價（à la carte $0.10/1,000 封）。
6. **推薦組合**：**主：Web Push（桌面／Android）＋ Telegram Bot（行動）**；**備援：Email 補送與每日彙總**；**站內通知一律寫入資料庫當單一事實來源**；**LINE 列為選配**，僅用於低頻高價值警示或每日彙總（受 200 則/月限制）。

---

## 1. LINE：Notify 終止與 Messaging API 現況（重點查證項目）

### 1.1 LINE Notify 已終止 —— 確認屬實

LINE Developers 官方新聞頁明文記載：

> 「2025年3月31日をもって、LINE Notifyのサービスを終了しました」（LINE Notify 服務已於 2025-03-31 終止）

- 來源（第一手）：<https://developers.line.biz/ja/news/2025/04/01/line-notify/>
- 同一則公告同時出現在 LINE Developers 的「サポート終了（End of Life）」標籤頁：<https://developers.line.biz/ja/news/tags/end-of-life/1/>
- 官方指定的替代方案：**LINE 公式アカウント（LINE 官方帳號）＋ Messaging API**。

**結論**：任何仍以 LINE Notify token 為前提的設計都必須放棄，沒有延長、沒有寬限期。

### 1.2 Messaging API 對個人開發者的申請門檻

依 LINE Developers 官方「Getting started with the Messaging API」：

1. 用**個人 LINE 帳號或 email** 註冊一組 **Business ID**（不需公司統編、不需營業登記）。
2. 建立一個 **LINE 官方帳號**（台灣稱「一般官方帳號」，免費開設）。
3. 在 **LINE Official Account Manager** 中為該帳號啟用 **Messaging API**，即取得 channel 與 access token。
4. 若 LINE Developers Console 是第一次登入，另需填寫 developer 名稱與 email。

- 來源：<https://developers.line.biz/en/docs/messaging-api/getting-started/>
- 免費開設官方帳號入口：<https://tw.linebiz.com/account/>

**認證帳號（藍盾）才需要公司文件，且非使用 Messaging API 的必要條件。** 台灣官方說明認證帳號需繳交「服務說明、台灣主管機關核准的設立文件、申請人在職證明」等，並限特定業種：

- 來源：<https://tw.linebiz.com/column/line-lac-id-0418/>、<https://tw.linebiz.com/e-learning/LINE-LAC-verifed-id/>

**個人開發者可行性判定：可行。** 不需公司、不需信用卡（停留在輕用量方案時），只需一組 LINE 帳號。

**但有兩個實務前提**：

- 使用者**必須先把你的官方帳號加為好友**，你才推得到訊息；
- 你必須取得對方的 `userId`，而 `userId` 只能從 webhook 事件取得（使用者互動後才會產生）。
  - 來源：<https://developers.line.biz/en/docs/messaging-api/sending-messages/>

### 1.3 免費訊息額度與超量計費（台灣，2026 現況）

LINE 官方文件明說**額度依地區方案而異**，並把台灣導向 LINE Biz-Solutions 台灣站：

- 來源（總則）：<https://developers.line.biz/en/docs/messaging-api/pricing/>

台灣官方 FAQ「訊息費用的計價方式？」列出的現行三方案：

| 方案 | 月費（未稅） | 免費訊息則數／月 | 可否加購 |
|---|---|---|---|
| 輕用量 | NT$0 | 200 則 | **不可加購** |
| 中用量 | NT$800 | 3,000 則 | **不可加購**（需升級高用量） |
| 高用量 | NT$1,200 | 6,000 則 | 可，**每則 NT$0.2 起**，階梯式累進遞減 |

- 來源（第一手）：<https://tw.linebiz.com/faq/oa-price/message-price-list/>
- 費用相關 FAQ 總覽：<https://tw.linebiz.com/faq/oa-price/>
- 產品頁與費用計算機：<https://tw.linebiz.com/service/account-solutions/line-official-account/>

**計費規則（官方文件明載）**：

- **計入額度的是**：push message、multicast、broadcast、narrowcast。
- **不計入額度的是**：**reply message（回覆訊息）完全免費、不佔額度**。
- **計算單位是「送達人數」**，不是 request 數或訊息物件數；送給封鎖你的使用者或不存在的 userId **不計費**。
- 台灣的算法同樣是「發送次數 × 目標好友數 = 總訊息則數」。
- 來源：<https://developers.line.biz/en/docs/messaging-api/pricing/>、<https://tw.linebiz.com/faq/oa-price/message-price-list/>

> 對照組（日本）：Light 免費 200 則、Standard ¥5,000/5,000 則、Premium ¥15,000/30,000 則＋超量 ¥3/則。可見**「免費 200 則」是跨區一致的起點**。
> 來源：<https://developers.line.biz/en/docs/messaging-api/pricing/>、<https://www.lycbiz.com/jp/service/line-official-account/plan/>

### 1.4 LINE 的 API 速率限制

- 一般 endpoint：**2,000 requests/秒**；「Issue short-lived channel access token」：370 requests/秒。超過回 `429 Too Many Requests`。速率限制以 **channel** 為單位、以 **endpoint（URL + HTTP method）** 區分。
- 來源：<https://developers.line.biz/en/reference/messaging-api/nojs/>（Common specifications → Rate limits）
- 額外注意：2025-04-23 起「Send multicast message」endpoint 的速率限制有調整。來源：<https://developers.line.biz/en/news/2025/03/31/messaging-api-rate-limit/>

**速率限制不是瓶頸，月額度才是。**

### 1.5 LINE 對本專案的實質意義

以「單一使用者、每月 300 則價格警示」估算：

- 300 則 > 輕用量 200 則 → **免費方案不夠用**，且輕用量不能加購。
- 要撐住就得跳到中用量 **NT$800/月（未稅）換 3,000 則**——對自用專案而言，這是整份研究裡**最貴的單一管道**。

可行的省錢設計：

- 把 LINE 用在**每日一封彙總**（1 天 1 則 ≈ 30 則/月，遠低於 200），即時逐筆警示交給 Telegram／Web Push。
- 善用**免費的 reply message**：使用者主動傳「查詢」給官方帳號時用 reply 回覆（不計額度），只有「主動推播」才吃額度。

---

## 2. Web Push（Service Worker + VAPID）

### 2.1 規格與後端元件

- **Push API**：W3C Working Draft，最新版日期 **2025-12-01**。<https://www.w3.org/TR/push-api/>
- **傳輸協定**：RFC 8030（Generic Event Delivery Using HTTP Push），定義 `TTL`、`Urgency` 標頭。<https://www.rfc-editor.org/rfc/rfc8030>
- **訊息加密**：RFC 8291（P-256 ECDH + auth secret）。
- **應用伺服器識別（VAPID）**：RFC 8292。<https://www.rfc-editor.org/rfc/rfc8292>
- MDN 總覽：<https://developer.mozilla.org/en-US/docs/Web/API/Push_API>

需要自建／持有的元件：

| 元件 | 說明 | 成本 |
|---|---|---|
| HTTPS 站台 + Web App Manifest | iOS 加入主畫面的必要條件 | 已有 |
| Service Worker | 接收 `push` 事件並呼叫 `showNotification()` | 0 |
| VAPID 金鑰對（P-256） | 自行產生，公鑰給前端 `applicationServerKey`，私鑰留後端簽 JWT | 0 |
| 訂閱資料儲存 | 存 endpoint + p256dh + auth 三元組 | DB 既有 |
| 推送函式庫 | 例如 `web-push`（Node）／`pywebpush` | 0 |
| Push Service | 由瀏覽器廠商提供（Chrome→FCM、Firefox→Mozilla autopush、Safari→APNs），**不需自建、不需付費** | 0 |

> ⚠️ 安全提醒：VAPID 私鑰屬於憑證，**絕不可進版控**，一律走環境變數／secret store。

### 2.2 瀏覽器支援度（2026 現況）

MDN 標記 Push API 為 **Baseline「Widely available」，自 2023 年 3 月起跨瀏覽器可用**（<https://developer.mozilla.org/en-US/docs/Web/API/Push_API>）。

MDN browser-compat-data 對 `PushManager.subscribe()` 的第一手註記：

| 瀏覽器 | version_added | 官方註記 |
|---|---|---|
| Chrome / Edge（桌面） | 42 | 需在 options 帶 `applicationServerKey` |
| Chrome Android | 42 | 同上 |
| Firefox（桌面／Android） | 支援 | — |
| **Safari（macOS）** | **16** | `"Notifications are supported on macOS Ventura and later."` |
| **Safari on iOS / iPadOS** | **16.4** | **`"Notifications are supported in web apps saved to the home screen."`** |

- 來源（第一手 BCD 原始資料）：<https://github.com/mdn/browser-compat-data/blob/main/api/PushManager.json>

### 2.3 iOS Safari 限制（重點查證項目）

**結論：截至 2026-08-01，iOS／iPadOS 上的 Web Push 仍然只在「加入主畫面（Home Screen web app）」的情境下可用；一般 Safari 分頁無法取得推播權限。**

證據鏈：

1. WebKit 官方文章〈Web Push for Web Apps on iOS and iPadOS〉（iOS/iPadOS 16.4 引入，2023-02）：
   > 「A web app that has been added to the Home Screen can request permission to receive push notifications **as long as that request is in response to direct user interaction** — such as tapping on a 'subscribe' button provided by the web app.」
   - 同文明確指出：**「You do not need to be a member of the Apple Developer Program to use it.」**（不需要 Apple 開發者帳號、不需付 US$99）
   - 通知行為與原生 App 一致：出現在鎖定畫面、通知中心、配對的 Apple Watch，並整合 Focus。
   - 來源：<https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/>
2. WebKit〈Meet Declarative Web Push〉（Safari 18.4 / iOS 18.4 / iPadOS 18.4，macOS 15.5）：新增**不需 Service Worker** 的宣告式推播，payload 需含頂層 `"web_push": 8030` 與 `notification` 字典（title / body / navigate URL / app_badge）。在 iOS/iPadOS 上**同樣限於加入主畫面的 web app**。
   - 來源：<https://webkit.org/blog/16535/meet-declarative-web-push/>、<https://webkit.org/blog/16574/webkit-features-in-safari-18-4/>
3. MDN BCD 的 `safari_ios` 註記（見上表）至今仍是 `"Notifications are supported in web apps saved to the home screen."`
4. 追查後續 Safari 版本：**Safari 26.6（2026-07-27 釋出）** 的 WebKit 官方 release notes 內容集中在 WebAssembly、CSS、networking、service workers、extensions、WebRTC 的修正，**未提及解除主畫面限制**。
   - 來源：<https://webkit.org/blog/18178/webkit-features-for-safari-26-6/>、<https://webkit.org/blog/17333/webkit-features-in-safari-26-0/>

**產品影響**：iPhone 使用者若沒有主動「分享 → 加入主畫面」，就**收不到任何 Web Push**。這在台灣是致命的（iOS 市佔高、且多數人不知道 PWA 安裝流程）。因此 iOS 必須有非 Web Push 的替代管道（Telegram／LINE／Email）。

### 2.4 延遲與可靠性的機制性因素

沒有任何官方 SLA 保證 Web Push 的端到端延遲（見 §7 未能查證）。但規格與平台文件明確指出會影響延遲的機制：

- **RFC 8030 `Urgency` 標頭**（預設 `normal`）：`very-low`=僅在充電且 Wi-Fi、`low`=充電或 Wi-Fi 其一、`normal`=兩者皆無亦可、`high`=低電量也送（適用「incoming phone call or **time-sensitive alert**」）。價格警示屬於 `high` 的教科書案例。
- **RFC 8030 `TTL` 標頭**（必填）：`TTL: 0` 表示「裝置在線就立即送達，之後 push service 可立即丟棄」——適合「過期就沒意義」的即時報價警示；若希望使用者開機後補收，需給正數 TTL。
- 來源：<https://www.rfc-editor.org/rfc/rfc8030>
- **Android Doze／App Standby**：Android 官方文件明載 Doze「**Suspends network access**」，系統只在週期性的 maintenance window 放行；而 **FCM high-priority 訊息可喚醒 App 並取得暫時網路存取**，normal-priority 則被推遲到 maintenance window 或裝置喚醒時才送。文件建議「只在時效敏感、使用者可見的通知上使用 high priority」。
  - 來源：<https://developer.android.com/training/monitoring-device-state/doze-standby>

---

## 3. Telegram Bot

### 3.1 申請難度

- 對 [@BotFather](https://t.me/botfather) 送 `/newbot`，給一個顯示名稱與一個以 `bot` 結尾的 username（5–32 字元），立刻拿到 API token。**無審核、無公司資格、無信用卡。**
- 來源：<https://core.telegram.org/bots/features>
- 前置條件：需自備後端呼叫 Bot API（webhook 或 long polling）。
- 來源：<https://core.telegram.org/bots/faq>

**實務限制**：`chat_id` 只能從使用者與 bot 互動所產生的 update 取得（`getUpdates` 或 webhook），所以使用者必須先對 bot 按一次 `/start`。這與 LINE「必須先加好友」是同一類前置摩擦，但 Telegram 沒有月額度。

- 來源：<https://core.telegram.org/bots/api#getupdates>

### 3.2 額度與速率限制

官方 FAQ「My bot is hitting limits, how do I avoid this?」原文：

- 單一聊天室：「avoid sending more than **one message per second**」
- 群組：「bots are not be able to send more than **20 messages per minute**」
- 大量廣播：「not able to broadcast more than about **30 messages per second**」
- 來源：<https://core.telegram.org/bots/faq>

**沒有「每月幾則」的額度概念，也沒有月費。** 付費廣播（Paid Broadcasts，以 Telegram Stars 計費、可衝到 1,000 則/秒）門檻是 100,000 Stars 餘額 + 100,000 月活躍使用者——與個人專案無關。

### 3.3 可靠性

- Bot API 由 Telegram 自行營運，本專案這種量級（每分鐘個位數訊息）遠低於任何限制。
- iOS/Android 都是原生 App 推播，**不受 Web Push 的主畫面限制**。
- 風險：Telegram 在台灣普及率遠低於 LINE，需要使用者額外安裝 App。

---

## 4. Email

| 服務 | 免費額度（2026 現況） | 付費起價 | 備註 |
|---|---|---|---|
| **Resend** | **3,000 封/月，且每日上限 100 封**；1,000 marketing contacts | Pro **US$20/月**含 50,000 封，超量 $0.90/1,000 | **必須驗證自有網域**才能正式寄送：「You must add and verify at least one domain to send and receive emails with Resend.」 |
| **Twilio SendGrid** | **永久免費方案已於 2025-05-27 起退場**，改為 **60 天試用（100 封/日）** | Essentials **US$19.95/月**起（50,000 封）；Pro US$89.95/月起 | 對自用小專案性價比最差 |
| **Amazon SES** | 無永久免費層；新帳號改為 **AWS Free Tier credits 最高 US$200、6 個月內有效** | **à la carte US$0.10／1,000 封**；或 Essentials $0.16/1K、Pro $0.22/1K（0–10M 級距） | 另收附件流量 **US$0.12/GB**。需自行處理網域驗證與 sandbox 解除 |

來源：

- Resend 定價：<https://resend.com/pricing>
- Resend 網域驗證要求：<https://resend.com/docs/dashboard/domains/introduction>
- SendGrid 免費方案退場公告：<https://www.twilio.com/en-us/changelog/sendgrid-free-plan>
- SendGrid 定價：<https://www.twilio.com/en-us/products/email-api/pricing>
- SendGrid 試用方案說明：<https://support.sendgrid.com/hc/en-us/articles/35270136965403-Twilio-SendGrid-Trial-Account-Plan>
- Amazon SES 定價：<https://aws.amazon.com/ses/pricing/>

**即時性評估**：SMTP 投遞本身通常是秒級，但**使用者「看到」的時間取決於收件端 App 的抓信策略**（iOS Mail 預設可能是 fetch 而非 push、Gmail App 有自己的推播節奏），且警示信容易被歸類到促銷／垃圾匣。**Email 不適合當唯一的即時警示管道**，適合當：補送、每日彙總、稽核軌跡。

**送達率**：三家皆要求 SPF/DKIM（透過網域驗證），本質上取決於寄件網域信譽——這一項無官方量化數據可引（見 §7）。

---

## 5. 站內通知（In-App）

無外部依賴、無成本、無額度。

- 實作：警示事件寫入 `notifications` 資料表，前端以 SSE／WebSocket／輪詢取用。
- 優點：**唯一 100% 可控、可重放、可稽核**的管道；不受任何第三方額度、審核、政策變動影響。
- 缺點：**使用者沒開網頁就等於沒收到**，完全不具備「叫醒使用者」的能力。
- 定位：**不是備援，是基礎層**。所有外部管道都應該是「站內通知的投影」，而非各自獨立的真相來源。

---

## 6. 管道比較總表

| 項目 | Web Push | Telegram Bot | LINE Messaging API | Email（Resend） | 站內通知 |
|---|---|---|---|---|---|
| **申請門檻** | 無需申請；自產 VAPID 金鑰。**不需 Apple Developer Program** | 對 BotFather `/newbot`，無審核 | 註冊 Business ID → 開一般官方帳號 → 啟用 Messaging API；個人可辦，不需公司 | 註冊 + **驗證自有網域**（DNS 設定） | 無 |
| **使用者前置動作** | 允許通知權限；**iOS 須加入主畫面** | 對 bot 按 `/start` | **加官方帳號好友** | 提供 email | 登入即可 |
| **免費額度** | 無上限（廠商 push service 免費） | 無月額度；~30 則/秒、單聊 1 則/秒 | **200 則/月**（台灣輕用量），reply 訊息免費不計 | 3,000 封/月 **且 100 封/日** | 無上限 |
| **超量計費** | — | — | 輕用量**不可加購**；中用量 NT$800/3,000 則；高用量 NT$1,200/6,000 則 + NT$0.2/則起 | Pro US$20/月 50,000 封 | — |
| **自用量級月成本** | **NT$0** | **NT$0** | NT$0（≤200 則）／**NT$800+**（超量） | NT$0（≤3,000 封） | NT$0 |
| **實際延遲** | 秒級；受 `Urgency`/`TTL` 與 Android Doze 影響（無官方 SLA） | 秒級（原生推播，無官方 SLA） | 秒級（無官方 SLA） | 數秒送出，但收件端可能延遲數分鐘 | 即時（連線中）／不送達（未開頁） |
| **平台限制** | **iOS/iPadOS 僅限主畫面 web app（16.4+）**；macOS Safari 16+；Chrome/Firefox/Edge 全面支援 | 需安裝 Telegram App | 需 LINE App（台灣普及率最高） | 無 | 需開著網頁 |
| **可靠性風險** | 使用者清瀏覽器資料／移除主畫面圖示即失效 | 台灣普及率低 | 月額度天花板；官方政策變動史（Notify 已被砍） | 進垃圾匣、收件端延遲 | 無外部風險 |
| **憑證管理** | VAPID 私鑰（**勿進版控**） | Bot token（**勿進版控**） | Channel access token（**勿進版控**） | API key（**勿進版控**） | 無 |

---

## 7. 未能查證的項目（誠實標註）

1. **各管道的官方端到端延遲數據／SLA**：Web Push（Chrome FCM、Mozilla autopush、Apple APNs）、Telegram Bot API、LINE Messaging API 均**未發布**投遞延遲保證或統計。本文只引用了**會影響延遲的官方機制**（RFC 8030 `Urgency`/`TTL`、Android Doze 對 FCM 優先級的處理），任何「約 X 秒」的數字都應由本專案自行實測 P50/P95 後填回本表。
2. **Email 送達率的量化數據**：Resend／SendGrid／SES 官方均未公布可引用的 inbox placement 比率。
3. **Resend 測試網域 `onboarding@resend.dev` 的限制細節**：官方文件僅載明「必須驗證至少一個網域」，未在該頁說明沙盒網域是否只能寄給自己。
4. **台灣 LINE 三方案月費的稅別呈現**：官方 FAQ 頁列出 0／800／1,200 元，本文標註「未稅」係依 LINE Biz-Solutions 慣例；若要精確報價請以帳務專區為準（<https://tw.linebiz.com/manual/line-official-account/20240903finace/>）。
5. **高用量方案加購訊息的完整階梯級距表**：官方僅公開「每則 0.2 元起、階梯式累進」，未公開完整級距。

---

## 8. 推薦組合

### 8.1 建議架構

```
警示規則觸發
      │
      ▼
┌─────────────────────┐
│ 站內通知（DB 寫入） │ ← 基礎層／單一事實來源，永遠執行
└──────────┬──────────┘
           │ fan-out（依使用者偏好與裝置）
           ├─▶ Web Push  ── 桌面 Chrome/Edge/Firefox、macOS Safari、Android
           ├─▶ Telegram  ── iOS 與所有行動裝置的主力（免費、無額度）
           ├─▶ LINE      ── 選配：每日彙總 or 高價值警示（≤200 則/月）
           └─▶ Email     ── 備援：上述皆失敗時補送 + 每日彙總 + 稽核
```

### 8.2 具體選型

| 角色 | 管道 | 理由 |
|---|---|---|
| **基礎層** | 站內通知 | 零成本、零外部風險、可重放；所有外部管道皆為其投影 |
| **主要（桌面／Android）** | Web Push | 零成本、零額度、標準化（RFC 8030/8291/8292）、不綁單一廠商；本專案主要使用情境是盯盤的桌面瀏覽器 |
| **主要（行動／iOS）** | Telegram Bot | 唯一同時滿足「免費 + 無月額度 + 原生推播 + 不受 iOS 主畫面限制」；申請 5 分鐘完成 |
| **備援** | Email（Resend 免費層） | 3,000 封/月足夠；用於推播失敗補送與每日彙總；同時是可稽核的紀錄 |
| **選配（台灣友善）** | LINE Messaging API | 台灣使用者最習慣，但 200 則/月的免費天花板使其不適合逐筆即時警示；建議只推「每日彙總」與「重大警示」，並用免費的 reply message 承接使用者主動查詢 |

### 8.3 實作注意事項

1. **Web Push 一律帶 `Urgency: high` 與適當 `TTL`**：即時報價警示用 `TTL: 0`～數分鐘（過期即無意義），持倉損益日報用較長 TTL 讓使用者開機補收。
2. **iOS 必須做安裝引導**：偵測到 `standalone === false` 的 iOS Safari 時，明確提示「分享 → 加入主畫面」才能收通知；否則直接引導改用 Telegram。並提供 Web App Manifest。
3. **可考慮 Declarative Web Push**：Safari 18.4+ 支援不需 Service Worker 的宣告式推播（payload 需含 `"web_push": 8030`），可作為 Safari 上的簡化路徑，但**仍不解除主畫面限制**。
4. **LINE 節流**：對 LINE 通道實作獨立的月額度計數器（上限 200，留 buffer 到 180），逼近上限時自動降級為「每日一則彙總」，並在站內通知標示降級狀態。
5. **所有 token/金鑰走環境變數**：VAPID 私鑰、Telegram bot token、LINE channel access token、Resend API key **一律不得進入版控**（本 repo 為 public）。
6. **投遞結果要落地**：每次外部推播的成功/失敗需寫回站內通知紀錄，才能做「失敗補送 Email」與後續的延遲實測。

---

## 9. 來源清單（全部第一手）

**LINE**

- LINE Notify 終止公告：<https://developers.line.biz/ja/news/2025/04/01/line-notify/>
- LINE Developers 支援終止標籤頁：<https://developers.line.biz/ja/news/tags/end-of-life/1/>
- Messaging API 總覽：<https://developers.line.biz/en/docs/messaging-api/overview/>
- Messaging API 定價規則：<https://developers.line.biz/en/docs/messaging-api/pricing/>
- Messaging API 入門（申請流程）：<https://developers.line.biz/en/docs/messaging-api/getting-started/>
- 發送訊息（push / reply / 計數方式）：<https://developers.line.biz/en/docs/messaging-api/sending-messages/>
- Messaging API reference（速率限制）：<https://developers.line.biz/en/reference/messaging-api/nojs/>
- multicast 速率限制變更公告（2025-04-23）：<https://developers.line.biz/en/news/2025/03/31/messaging-api-rate-limit/>
- 台灣訊息費計價方式 FAQ：<https://tw.linebiz.com/faq/oa-price/message-price-list/>
- 台灣費用相關 FAQ：<https://tw.linebiz.com/faq/oa-price/>
- 台灣 LINE 官方帳號產品頁：<https://tw.linebiz.com/service/account-solutions/line-official-account/>
- 台灣免費開設帳號：<https://tw.linebiz.com/account/>
- 台灣認證帳號申請流程：<https://tw.linebiz.com/column/line-lac-id-0418/>
- 日本方案對照：<https://www.lycbiz.com/jp/service/line-official-account/plan/>

**Web Push**

- W3C Push API（WD 2025-12-01）：<https://www.w3.org/TR/push-api/>
- RFC 8030（HTTP Web Push、Urgency/TTL）：<https://www.rfc-editor.org/rfc/rfc8030>
- RFC 8292（VAPID）：<https://www.rfc-editor.org/rfc/rfc8292>
- MDN Push API：<https://developer.mozilla.org/en-US/docs/Web/API/Push_API>
- MDN PushManager.subscribe()：<https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe>
- MDN browser-compat-data（PushManager 原始 JSON）：<https://github.com/mdn/browser-compat-data/blob/main/api/PushManager.json>
- WebKit：Web Push for Web Apps on iOS and iPadOS：<https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/>
- WebKit：Meet Declarative Web Push：<https://webkit.org/blog/16535/meet-declarative-web-push/>
- WebKit Features in Safari 18.4：<https://webkit.org/blog/16574/webkit-features-in-safari-18-4/>
- WebKit Features in Safari 26.0：<https://webkit.org/blog/17333/webkit-features-in-safari-26-0/>
- WebKit Features for Safari 26.6（2026-07-27）：<https://webkit.org/blog/18178/webkit-features-for-safari-26-6/>
- Android Doze / App Standby（FCM 優先級與網路限制）：<https://developer.android.com/training/monitoring-device-state/doze-standby>

**Telegram**

- Bot 功能與 BotFather：<https://core.telegram.org/bots/features>
- Bot FAQ（速率限制）：<https://core.telegram.org/bots/faq>
- Bot API reference：<https://core.telegram.org/bots/api>

**Email**

- Resend 定價：<https://resend.com/pricing>
- Resend 網域驗證：<https://resend.com/docs/dashboard/domains/introduction>
- SendGrid 免費方案退場公告：<https://www.twilio.com/en-us/changelog/sendgrid-free-plan>
- SendGrid Email API 定價：<https://www.twilio.com/en-us/products/email-api/pricing>
- SendGrid 試用方案：<https://support.sendgrid.com/hc/en-us/articles/35270136965403-Twilio-SendGrid-Trial-Account-Plan>
- Amazon SES 定價：<https://aws.amazon.com/ses/pricing/>
