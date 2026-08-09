# 決策簡報（上桌前準備）

> ## ⚠️ 這裡的東西**不是決策**，不可據以實作
>
> 本目錄是 [issue #1](https://github.com/NTUyu016/stock-analytic-platform/issues/1) 地圖上幾張**尚未定案**的決策票的**準備材料**：事實查證、選項盤點、代價估算。
>
> 它們刻意**不含結論**。文中若出現「選項 A 的代價比 B 低」，那是比較，不是選擇。
>
> **已定案的規格一律在 [`docs/spec/`](../spec/)。** 那裡才有決定，也才記錄了「被淘汰的選項輸在哪」。

## 這些檔案存在的理由

決策票的瓶頸是**人的注意力**，不是算力——決策必須由使用者在 `/grilling` session 中親自做，不能平行化。但每張票上桌前的**閱讀與查證**可以，而那才是耗時的部分。

這些簡報就是把那部分先做完，讓 grilling 時每一題都有實據可談。

## 內容

**全部決策票皆已定案（2026-08-09）。** 以下每一份都只保留為證據來源，決策一律見 [`docs/spec/`](../spec/)。

| 檔案 | 對應票 | 狀態 |
|---|---|---|
| [`14-analysis-dimensions.md`](./14-analysis-dimensions.md) | [#14 個股分析頁的台股指標集合](https://github.com/NTUyu016/stock-analytic-platform/issues/14) | ✅ 已定案（2026-08-08）→ [`analysis-dimensions.md`](../spec/analysis-dimensions.md) |
| [`15-alerts.md`](./15-alerts.md) | [#15 警示的觸發模型與通知管道](https://github.com/NTUyu016/stock-analytic-platform/issues/15) | ✅ 已定案 → [`alerts.md`](../spec/alerts.md)。⚠️ 本文**部分過時**（管道改 Discord、待決 3/6/8 已答），見檔首更新欄 |
| [`16-performance.md`](./16-performance.md) | [#16 歷史快照與績效計算策略](https://github.com/NTUyu016/stock-analytic-platform/issues/16) | ✅ 已定案（2026-08-07）→ [`performance.md`](../spec/performance.md) |
| [`17-deployment.md`](./17-deployment.md) | [#17 部署、環境與成本上限](https://github.com/NTUyu016/stock-analytic-platform/issues/17) | ✅ 已定案（2026-08-09）→ [`deployment.md`](../spec/deployment.md)。⚠️ 檔首有 **2026-08-09 事實更正欄**（六處被推翻）；且**定案方向與本文九個待決事項的預設前提不同**——v1 不上雲，本文的雲端盤點降級為遷移路徑材料 |
| [`20-corporate-actions.md`](./20-corporate-actions.md) | [#20 公司行動的型別與偵測](https://github.com/NTUyu016/stock-analytic-platform/issues/20) | ✅ 已定案（2026-08-09）→ [`corporate-actions.md`](../spec/corporate-actions.md) |
| [`bench/`](./bench/) | #16 的效能實測腳本與原始輸出 | 證據 |

產出日期 **2026-08-04**（#17／#20 為 2026-08-08）。第三方的額度、價格與服務存廢會變——引用前請確認時效。

## `bench/` 是什麼

`16-performance.md` 有一項發現推翻了既有規格的推論（[`dashboard-ui.md`](../spec/dashboard-ui.md) §7 斷言拖曳選取互動「放大了 #16 的成本差距」，實測顯示方向相反）。

推翻既有規格需要證據，所以**測量腳本與原始輸出一併留下**，任何人都能重跑驗證。腳本用 `pgserver` 起臨時 PostgreSQL，不需要既有資料庫、不含任何憑證。

```bash
uv run --with psycopg --with pgserver docs/briefing/bench/bench_16.py
```

> 這些腳本是**丟棄式的**，不是專案程式碼——它們不會進入 `src/`，也不受 [`tech-stack.md`](../spec/tech-stack.md) §7 的測試策略約束。

## 這些檔案的下場

每張票定案後，其結論寫進 `docs/spec/`，**對應的簡報就失去作用**。

**[#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18) 已決定：保留不刪。**

理由是它們記著兩件規格不會記的事——**被淘汰的選項輸在哪**，以及**哪些事實在當時查不到**。而本專案已經發生過兩次「後來的查證推翻了當初的理由，但結論仍然成立」（#20 的減資有 feed、#17 的 Render 750 小時），**刪掉簡報會讓那類複查失去比對基準**。
