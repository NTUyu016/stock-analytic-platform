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

| 檔案 | 對應票 | 狀態 |
|---|---|---|
| [`14-analysis-dimensions.md`](./14-analysis-dimensions.md) | [#14 個股分析頁的台股指標集合](https://github.com/NTUyu016/stock-analytic-platform/issues/14) | 待 grilling |
| [`15-alerts.md`](./15-alerts.md) | [#15 警示的觸發模型與通知管道](https://github.com/NTUyu016/stock-analytic-platform/issues/15) | 待 grilling |
| [`16-performance.md`](./16-performance.md) | [#16 歷史快照與績效計算策略](https://github.com/NTUyu016/stock-analytic-platform/issues/16) | 待 grilling |
| [`bench/`](./bench/) | #16 的效能實測腳本與原始輸出 | 證據 |

產出日期 **2026-08-04**。第三方的額度、價格與服務存廢會變——引用前請確認時效。

## `bench/` 是什麼

`16-performance.md` 有一項發現推翻了既有規格的推論（[`dashboard-ui.md`](../spec/dashboard-ui.md) §7 斷言拖曳選取互動「放大了 #16 的成本差距」，實測顯示方向相反）。

推翻既有規格需要證據，所以**測量腳本與原始輸出一併留下**，任何人都能重跑驗證。腳本用 `pgserver` 起臨時 PostgreSQL，不需要既有資料庫、不含任何憑證。

```bash
uv run --with psycopg --with pgserver docs/briefing/bench/bench_16.py
```

> 這些腳本是**丟棄式的**，不是專案程式碼——它們不會進入 `src/`，也不受 [`tech-stack.md`](../spec/tech-stack.md) §7 的測試策略約束。

## 這些檔案的下場

每張票定案後，其結論寫進 `docs/spec/`，**對應的簡報就失去作用**。

是否在定案後刪除、或保留為決策過程的紀錄，由 [#18](https://github.com/NTUyu016/stock-analytic-platform/issues/18)（v1 規格文件的形狀與交付）一併決定。在那之前它們留在這裡。
