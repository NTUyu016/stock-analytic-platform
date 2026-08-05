# PostgreSQL `jsonb` 的約束能力與數值精度

> 對應票：[#15 決策：警示的觸發模型與通知管道](https://github.com/NTUyu016/stock-analytic-platform/issues/15) 待決事項 2「警示規則的資料模型」
> 調查日期：2026-08-05
> 撰寫語言：繁體中文（zh-tw）
>
> **本文不做決策、不下推薦。** 只陳述事實與代價，定案由使用者在 grilling session 親自做。

---

## 0. 研究方法與版本基準

### 0.1 版本基準

查證當日（2026-08-05）向 [PostgreSQL 官方版本政策頁](https://www.postgresql.org/support/versioning/) 確認：

| 版本 | 現行小版本 | 是否支援 | 首次發行 | EOL |
|---|---|---|---|---|
| **18** | **18.4** | 是 | 2025-09-25 | 2030-11-14 |
| 17 | 17.10 | 是 | 2024-09-26 | 2029-11-08 |
| 16 | 16.14 | 是 | 2023-09-14 | 2028-11-09 |
| 15 | 15.18 | 是 | 2022-10-13 | 2027-11-11 |
| 14 | 14.23 | 是 | 2021-09-30 | **2026-11-12** |

**最新穩定大版本為 PostgreSQL 18，本文一律以 `https://www.postgresql.org/docs/18/` 為準。** PostgreSQL 19 Beta 2 已於 2026-07-16 釋出，但仍是 beta，不列入本文結論。

> ⚠️ 順帶一提：`docs/briefing/16-performance.md` 的 bench 跑在**本機 PostgreSQL 16.2** 上。16.2 已落後現行 16.14 十二個小版本，且與正式環境可能採用的 18.x 差兩個大版本。這與本票無關，但若 #17 定案時要沿用 bench 數字，這件事要先攤開。

### 0.2 方法與限制

- 所有結論以**第一手來源**為準：PostgreSQL 官方文件（含版本路徑）、官方 release notes、擴充套件的官方 repo 原始碼、託管平台官方文件、psycopg / Pydantic 官方文件。
- 二手部落格僅用來「找到官方頁面在哪」，不作為任何結論依據。
- **本機沒有可用的 PostgreSQL 實例**（`psql` 與 `docker` 皆不在 PATH 上），因此本文中所有 SQL 行為**均為由官方文件明文語意推導，非實跑驗證**。凡屬推導者，文中一律標記為「**推導**」。Python 端的行為則有**實跑驗證**（見 §4.3），並標記為「實測」。
- 查不到的一律寫「**未能查證，需人工確認**」，不以記憶或推測填空。

---

## 1. PostgreSQL 有沒有內建的 JSON Schema 驗證？

### 結論先行

**沒有。** PostgreSQL 18 及此前所有版本，核心中**不存在任何 JSON Schema（draft-07 / 2020-12 等）驗證能力**。SQL/JSON 標準本身也沒有納入 JSON Schema。核心提供的是**語法／型別層級**的檢查與**路徑查詢**，兩者都不是 schema 驗證。

檢索 PostgreSQL 18 的 [JSON 函式與運算子文件](https://www.postgresql.org/docs/18/functions-json.html) 與 [18.0 release notes](https://www.postgresql.org/docs/release/18.0/)，**均無 `json_matches_schema` 或任何 JSON Schema 相關字樣**。

### 1.1 `IS JSON` 述詞（PostgreSQL 16 引入）

**引入版本**：PostgreSQL 16。[16.0 release notes](https://www.postgresql.org/docs/release/16.0/) 原文：

> Add SQL/JSON object checks (Nikita Glukhov, Teodor Sigaev, Oleg Bartunov, Alexander Korotkov, Amit Langote, Andrew Dunstan)
>
> The `IS JSON` checks include checks for values, arrays, objects, scalars, and unique keys.

**實際能力**（[PG18 functions-json，Table 9.50 SQL/JSON Testing Functions](https://www.postgresql.org/docs/18/functions-json.html)）原文：

> *`expression`* `IS` [ `NOT` ] `JSON` [ { `VALUE` | `SCALAR` | `ARRAY` | `OBJECT` } ] [ { `WITH` | `WITHOUT` } `UNIQUE` [ `KEYS` ] ]
>
> This predicate tests whether *`expression`* can be parsed as JSON, possibly of a specified type. If `SCALAR` or `ARRAY` or `OBJECT` is specified, the test is whether or not the JSON is of that particular type. If `WITH UNIQUE KEYS` is specified, then any object in the *`expression`* is also tested to see if it has duplicate keys.

**它能驗到什麼程度**：

| 能驗 | 不能驗 |
|---|---|
| 這串文字**能不能被 parse 成 JSON**（語法） | 物件裡**有沒有** `operator` 這個 key |
| 頂層是不是 object / array / scalar | `operator` 的值是不是 `'gt'` / `'lt'` 之一 |
| 物件內**有沒有重複 key**（`WITH UNIQUE KEYS`） | `threshold` 是不是數字 |
| — | 任何 required / enum / type 的結構性規則 |

**對本票的意義**：`condition` 欄位已宣告為 `jsonb`，型別本身就保證了「能 parse 成 JSON」——`jsonb` 欄位裡不可能存在語法無效的值。因此 `CHECK (condition IS JSON OBJECT)` 對 `jsonb` 欄位**只多擋一件事：頂層不是 object**（例如整個值是 `[1,2]` 或 `"abc"` 或 `123`）。它**完全擋不住** `{"oprator": "gt"}` 這種拼錯欄位名的情形。**這正是本票在意的失效模式，`IS JSON` 對它無能為力。**

### 1.2 SQL/JSON 查詢函式（PostgreSQL 17 引入）

`JSON_EXISTS`、`JSON_VALUE`、`JSON_QUERY`、`JSON_TABLE` **均於 PostgreSQL 17 引入**（[PostgreSQL 17 Released!](https://www.postgresql.org/about/news/postgresql-17-released-2936/)）：

> PostgreSQL 17 now supports SQL/JSON constructors (JSON, JSON_SCALAR, JSON_SERIALIZE) and query functions (JSON_EXISTS, JSON_QUERY, JSON_VALUE) […] `JSON_TABLE` is now available in PostgreSQL 17, letting developers convert JSON data into a standard PostgreSQL table.

**`JSON_EXISTS` 的定義**（[PG18 functions-json, Table 9.54](https://www.postgresql.org/docs/18/functions-json.html)）原文：

> Returns true if the SQL/JSON *`path_expression`* applied to the *`context_item`* yields any items, false otherwise.
>
> The `ON ERROR` clause specifies the behavior if an error occurs during *`path_expression`* evaluation. Specifying `ERROR` will cause an error to be thrown with the appropriate message. Other options include returning `boolean` values `FALSE` or `TRUE` or the value `UNKNOWN` which is actually an SQL NULL. **The default when no `ON ERROR` clause is specified is to return the `boolean` value `FALSE`.**

**能否用於 `CHECK` 約束？**

- **`JSON_EXISTS` 可以**：它回傳 `boolean`，且是不含子查詢的純量表達式，符合 CHECK 的形式要求。**未能實跑驗證**（無本機實例），但形式上無阻礙 —— **推導**。
- **`JSON_VALUE` / `JSON_QUERY` 可以出現在 CHECK 表達式裡**（例如 `CHECK (JSON_VALUE(condition, '$.operator') IN ('gt','lt'))`），但它們回傳的是值不是布林，要靠外層比較運算才成為布林——於是就落入 §2.2 的 NULL 陷阱。**推導**。
- **`JSON_TABLE` 不行**：它是 `FROM` 子句的 tuple source，形式上等同於子查詢，而「`CHECK` expressions cannot contain subqueries」（見 §2.1 原文）。

**關鍵**：`JSON_EXISTS` 的預設 `ON ERROR` 是回傳 **FALSE**（不是 NULL），這使它成為少數「預設安全」的寫法之一。但注意這只涵蓋 *path 求值出錯*的情形；path 正常求值但找不到東西時它同樣回傳 false（documented：「yields any items, false otherwise」）——這對「required 欄位存在性」檢查而言反而是想要的行為。

### 1.3 PostgreSQL 18 有沒有新增任何 JSON Schema 能力？

**沒有。** [18.0 release notes](https://www.postgresql.org/docs/release/18.0/) 中所有 JSON 相關條目只有三條，全與 schema 驗證無關：

> Allow `jsonb` `null` values to be cast to scalar types as `NULL` (Tom Lane)
>
> Previously such casts generated an error.

> Add optional parameter to `json{b}_strip_nulls` to allow removal of null array elements (Florents Tselai)

> Improve the performance of processing long `JSON` strings using SIMD (Single Instruction Multiple Data) (David Rowley)

---

## 2. 用 `CHECK` 約束驗 `jsonb`：實務做法與極限

### 2.1 形式上的硬限制

[PG18 CREATE TABLE](https://www.postgresql.org/docs/18/sql-createtable.html) 對 `CHECK ( expression )` 的原文：

> The `CHECK` clause specifies an expression producing a Boolean result which new or updated rows must satisfy for an insert or update operation to succeed. **Expressions evaluating to TRUE or UNKNOWN succeed.** Should any row of an insert or update operation produce a FALSE result, an error exception is raised and the insert or update does not alter the database. […]
>
> **Currently, `CHECK` expressions cannot contain subqueries nor refer to variables other than columns of the current row** (see Section 5.5.1). The system column `tableoid` may be referenced, but not any other system column.

[PG18 ddl-constraints §5.5.1](https://www.postgresql.org/docs/18/ddl-constraints.html) 的對應段落：

> It should be noted that **a check constraint is satisfied if the check expression evaluates to true or the null value.** Since most expressions will evaluate to the null value if any operand is null, they will not prevent null values in the constrained columns. To ensure that a column does not contain null values, the not-null constraint described in the next section can be used.

以及**不得跨列／跨表**：

> PostgreSQL does not support `CHECK` constraints that reference table data other than the new or updated row being checked. While a `CHECK` constraint that violates this rule may appear to work in simple tests, it cannot guarantee that the database will not reach a state in which the constraint condition is false (due to subsequent changes of the other row(s) involved). This would cause a database dump and restore to fail. […] If possible, use `UNIQUE`, `EXCLUDE`, or `FOREIGN KEY` constraints to express cross-row and cross-table restrictions.

### 2.2 ★ 最重要的一節：`CHECK` 對 NULL 放行，而「欄位漏寫」正好產生 NULL

「Expressions evaluating to **TRUE or UNKNOWN** succeed」這一句，讓題目要求查證的三種寫法**有兩種是假的防護**。

先看每個運算子在「key 不存在」時回傳什麼（[PG18 functions-json](https://www.postgresql.org/docs/18/functions-json.html)）：

| 運算子／函式 | 官方描述 | key 不存在時 |
|---|---|---|
| `condition ? 'operator'` | 「Does the text string exist as a top-level key or array element within the JSON value?」 | **`false`**（strict 函式，兩參數皆非 NULL 時必回傳 boolean）—— **推導** |
| `condition -> 'threshold'` | 「Extracts JSON object field with the given key.」 | **SQL NULL** |
| `condition ->> 'operator'` | 「Extracts JSON object field with the given key, as `text`.」 | **SQL NULL** |
| `jsonb_typeof(x)` | 「Returns the type of the top-level JSON value as a text string.」官方範例：`json_typeof(NULL::json) IS NULL → t` | 參數為 NULL 時**回傳 NULL** |

於是：

| 寫法 | 合法？ | `{"oprator": "gt", "threshold": 599.99}`（打錯 key）會怎樣 |
|---|---|---|
| `CHECK (condition ? 'operator')` | ✅ 合法 | `false` → **擋下** ✅ |
| `CHECK (condition->>'operator' IN ('gt','lt'))` | ✅ 合法 | `NULL IN (...)` → `NULL` → **放行** ❌ |
| `CHECK (jsonb_typeof(condition->'threshold') = 'number')` | ✅ 合法 | 若 `threshold` 也漏寫 → `NULL = 'number'` → `NULL` → **放行** ❌ |
| `CHECK (condition @@ '$.threshold > 0')` | ✅ 合法 | 見下方，**放行** ❌ |

**三種寫法都合法，但只有第一種真的擋得住。**

**`@@` 為什麼也不行**——[PG18 functions-json](https://www.postgresql.org/docs/18/functions-json.html) 兩處原文：

> The `jsonpath` operators `@?` and `@@` **suppress the following errors: missing object field or array element, unexpected JSON item type, datetime and numeric errors.** This behavior might be helpful when searching JSON document collections of varying structure.

> **`@@`**：Returns the result of a JSON path predicate check for the specified JSON value. (This is useful only with predicate check expressions, not SQL-standard JSON path expressions, **since it will return `NULL` if the path result is not a single boolean value**.)

> While SQL-standard path expressions return the relevant element(s) of the queried JSON value, predicate check expressions return the **single three-valued `jsonb` result of the predicate: `true`, `false`, or `null`**.

「missing object field 被 suppress」+「三值邏輯」+「CHECK 對 NULL 放行」＝ **`@@` 是本題最糟的選擇：它的設計目標正是「結構不一致時不要吵」，恰好與本專案的原則相反。**

**這件事的份量**：本專案的原則是「**漏寫不會有任何錯誤訊息**」的設計是禁忌。上表顯示，**天真地寫 CHECK 約束，會把同一個禁忌從應用層原封不動地複製到資料庫層**——而且更陰險，因為 DDL 裡明明白白寫著一條 `CHECK`，看起來像是有防護。

**能寫對的形式**（每一條都要顯式處理「不存在」）：

```sql
-- 1) 欄位本身必須 NOT NULL，否則所有 CHECK 都被 NULL 短路
condition jsonb NOT NULL

-- 2) 頂層必須是 object（jsonb 欄位唯一還值得驗的語法層事項）
CHECK (jsonb_typeof(condition) = 'object')

-- 3) required key：用 ?& 一次列完，回傳 false 而非 NULL
CHECK (condition ?& array['rule_type','operator','threshold'])

-- 4) 型別：先確認存在，再驗型別（順序不可反）
CHECK (jsonb_typeof(condition->'threshold') = 'number')
CHECK (jsonb_typeof(condition->'operator')  = 'string')

-- 5) enum：用 COALESCE 把 NULL 摺成 false
CHECK (COALESCE(condition->>'operator' IN ('gt','lt','gte','lte'), false))

-- 6) 封閉 key 集合（拒絕多餘／拼錯的 key）——不需要子查詢
CHECK (condition - 'rule_type' - 'operator' - 'threshold' = '{}'::jsonb)
```

第 6 條用到 `jsonb - text` 運算子，官方定義：

> `jsonb` `-` `text` → `jsonb`：Deletes a key (and its value) from a JSON object, or matching string value(s) from a JSON array.
> `'{"a": "b", "c": "d"}'::jsonb - '{a,c}'::text[]` → `{}`

**這是本題唯一能不靠擴充套件、不靠子查詢就達成「封閉集合」的手法**——把所有已知 key 減掉，剩下的必須是空物件。它同時擋住「多寫」與「拼錯」（拼錯 = 少一個已知 key 且多一個未知 key，第 3 條與第 6 條各擋一半）。**推導，未能實跑驗證。**

**但這組 CHECK 有兩個結構性代價：**

1. **它是「單一形狀」的約束。** 一旦規則有多種型別（價格門檻 / 漲跌幅 / 成交量 / 財報日），required key 集合就因型別而異，第 3、4、6 條全部要改寫成巨大的 `CASE WHEN condition->>'rule_type' = '...' THEN ... END`。這串 CASE 本身**又是一個「漏寫某個分支就默默放行」的地方**——`CASE` 沒有 `ELSE` 時回傳 NULL，NULL → CHECK 放行。要安全就必須顯式 `ELSE false`。**禁忌在此處第三次以新形態出現。**
2. **錯誤訊息品質低。** CHECK 失敗只會說 `new row for relation "alert" violates check constraint "alert_condition_check"`，不會告訴你是哪個 key 錯了。相對地，具名欄位的 `NOT NULL` / enum 違反會直接點名欄位。

### 2.3 `CHECK` 約束內能不能呼叫自訂函式？官方警語

**可以呼叫，PostgreSQL 不禁止，但官方有明確警語。**

[PG18 ddl-constraints §5.5.1](https://www.postgresql.org/docs/18/ddl-constraints.html) 的 Note 原文（**這就是題目要求的原文**）：

> ### Note
>
> **PostgreSQL assumes that `CHECK` constraints' conditions are immutable, that is, they will always give the same result for the same input row.** This assumption is what justifies examining `CHECK` constraints only when rows are inserted or updated, and not at other times. (The warning above about not referencing other table data is really a special case of this restriction.)
>
> **An example of a common way to break this assumption is to reference a user-defined function in a `CHECK` expression, and then change the behavior of that function. PostgreSQL does not disallow that, but it will not notice if there are rows in the table that now violate the `CHECK` constraint. That would cause a subsequent database dump and restore to fail.** The recommended way to handle such a change is to drop the constraint (using `ALTER TABLE`), adjust the function definition, and re-add the constraint, thereby rechecking it against all table rows.

**對本票的翻譯**：如果選擇「把驗證邏輯寫成一個 PL/pgSQL 函式，CHECK 裡呼叫它」，那麼**每次改動那個函式（＝每次新增或修改一種警示規則型別），既有資料列都不會被重新驗證**。資料庫會靜靜地帶著一批違反現行約束的列繼續運作，直到某天 `pg_dump` / `pg_restore` 失敗才爆出來。官方給的處理方式是：`DROP CONSTRAINT` → 改函式 → `ADD CONSTRAINT`（此時才會全表重驗）。

`CREATE DOMAIN` 上的同一警語（[PG18 CREATE DOMAIN](https://www.postgresql.org/docs/18/sql-createdomain.html)）措辭幾乎相同，只是把「rows」換成「stored values」：

> PostgreSQL assumes that CHECK constraints' conditions are immutable, that is, they will always give the same result for the same input value. This assumption is what justifies examining CHECK constraints only when a value is first converted to be of a domain type, and not at other times.
>
> An example of a common way to break this assumption is to reference a user-defined function in a CHECK expression, and then change the behavior of that function. PostgreSQL does not disallow that, but it will not notice if there are stored values of the domain type that now violate the CHECK constraint. […] The recommended way to handle such a change is to drop the constraint (using ALTER DOMAIN), adjust the function definition, and re-add the constraint, thereby rechecking it against stored data.

### 2.4 約束變更時對既有列的驗證行為：`NOT VALID` 與 `VALIDATE CONSTRAINT`

[PG18 ALTER TABLE](https://www.postgresql.org/docs/18/sql-altertable.html) 原文：

> **ADD `table_constraint` [ NOT VALID ]**
>
> This form adds a new constraint to a table using the same constraint syntax as `CREATE TABLE`, plus the option `NOT VALID`, which is currently only allowed for foreign-key, `CHECK`, and not-null constraints.
>
> **Normally, this form will cause a scan of the table to verify that all existing rows in the table satisfy the new constraint.** But if the `NOT VALID` option is used, this potentially-lengthy scan is skipped. The constraint will still be applied against subsequent inserts or updates (that is, they'll fail unless there is a matching row in the referenced table, in the case of foreign keys, or they'll fail unless the new row matches the specified check condition). **But the database will not assume that the constraint holds for all rows in the table, until it is validated by using the `VALIDATE CONSTRAINT` option.**

> **VALIDATE CONSTRAINT**
>
> This form validates a foreign key, check, or not-null constraint that was previously created as `NOT VALID`, by scanning the table to ensure there are no rows for which the constraint is not satisfied. If the constraint was set to `NOT ENFORCED`, an error is thrown. Nothing happens if the constraint is already marked valid.
>
> **This command acquires a `SHARE UPDATE EXCLUSIVE` lock.**

**要點整理：**

| 行為 | 說明 |
|---|---|
| 預設 `ADD CONSTRAINT` | **會全表掃描驗證既有列**；有違反者則整個 DDL 失敗 |
| `NOT VALID` | 跳過掃描，**新寫入仍受約束**，既有列**不保證**符合 |
| `VALIDATE CONSTRAINT` | 事後補掃描；取 `SHARE UPDATE EXCLUSIVE`（**不擋讀寫**，只擋其他 DDL / VACUUM FULL） |
| 支援 `NOT VALID` 的約束型別 | 外鍵、`CHECK`、**not-null**（not-null 的 `NOT VALID` 是 **PG18 新增**，見下） |

PostgreSQL 18 新增（[18.0 release notes](https://www.postgresql.org/docs/release/18.0/)）：

> Allow `ALTER TABLE` to set the `NOT VALID` attribute of `NOT NULL` constraints (Rushabh Lathia, Jian He)

> Store column `NOT NULL` specifications in `pg_constraint` (Álvaro Herrera, Bernd Helmle)
>
> This allows names to be specified for `NOT NULL` constraint. This also adds `NOT NULL` constraints to foreign tables and `NOT NULL` inheritance control to local tables.

**對本票的意義**：`NOT VALID` 是「規則形狀將來會演進」時的關鍵工具——加新約束時可以先不動舊列。但它同時是一個誠實的提醒：**用了 `NOT VALID` 就等於承認資料庫裡有一批不符現行 schema 的列，而查詢時沒有任何東西會告訴你哪些是。** 這與 §2.3 的自訂函式陷阱是同一個形狀的風險。

### 2.5 變體：`CREATE DOMAIN` over `jsonb`

可以把 CHECK 掛在**型別**上而非欄位上：

```sql
CREATE DOMAIN alert_condition AS jsonb
  CHECK (VALUE ?& array['rule_type','operator','threshold']);
```

[PG18 CREATE DOMAIN](https://www.postgresql.org/docs/18/sql-createdomain.html) 原文：

> `CHECK` clauses specify integrity constraints or tests which values of the domain must satisfy. Each constraint must be an expression producing a Boolean result. It should use the key word `VALUE` to refer to the value being tested. **Expressions evaluating to TRUE or UNKNOWN succeed.** If the expression produces a FALSE result, an error is reported and the value is not allowed to be converted to the domain type.

> **Domain constraints, particularly `NOT NULL`, are checked when converting a value to the domain type.**

**優點**：驗證邏輯只寫一次，多個欄位／表可共用；`ALTER DOMAIN ... ADD CONSTRAINT` 會重驗既有值。
**缺點**：（1）同樣的 TRUE-or-UNKNOWN 放行語意，一模一樣的 NULL 陷阱；（2）「檢查發生在轉型時」意味著約束的觸發點比欄位 CHECK 更隱晦；（3）不解決「多種規則型別 → 巨大 CASE」的問題。

### 2.6 變體：生成欄位（Generated Columns）—— 一個 PG18 專屬的陷阱

把 `jsonb` 裡的欄位「拉出來」成為具名欄位，是混合方案（D）的常見手法：

```sql
threshold numeric GENERATED ALWAYS AS ((condition->>'threshold')::numeric) STORED
```

[PG18 CREATE TABLE](https://www.postgresql.org/docs/18/sql-createtable.html) 原文：

> When `VIRTUAL` is specified, the column will be computed when it is read, and it will not occupy any storage. When `STORED` is specified, the column will be computed on write and will be stored on disk. **`VIRTUAL` is the default.**
>
> The generation expression can refer to other columns in the table, but not other generated columns. **Any functions and operators used must be immutable.** References to other tables are not allowed.
>
> **A virtual generated column cannot have a user-defined type, and the generation expression of a virtual generated column must not reference user-defined functions or types, that is, it can only use built-in functions or types.** This applies also indirectly, such as for functions or types that underlie operators or casts. (This restriction does not exist for stored generated columns.)

[18.0 release notes](https://www.postgresql.org/docs/release/18.0/)：

> Allow generated columns to be virtual, and make them the default (Peter Eisentraut, Jian He, Richard Guo, Dean Rasheed)
>
> Virtual generated columns generate their values when the columns are read, not written. The write behavior can still be specified via the `STORED` option.

**⚠️ 三個必須知道的後果：**

1. **PG18 起 `VIRTUAL` 是預設**。寫 `GENERATED ALWAYS AS (...)` 而沒寫 `STORED`，在 PG17 是語法錯誤，在 PG18 會靜靜地給你一個 virtual 欄位。
2. **virtual 生成欄位不能建索引。** PostgreSQL 官方 commit 訊息中存在錯誤字串「indexes on virtual generated columns are not supported」（[pgsql-committers, "Prevent spurious 'indexes on virtual generated columns are not s…'"](https://www.postgresql.org/message-id/E1w4zA1-001DwY-2l%40gemulon.postgresql.org)）；主幹上有進行中的「support create index on virtual generated column」提案（[pgsql-hackers 討論串](https://www.postgresql.org/message-id/CACJufxGao-cypdNhifHAdt8jHfK6-HX=tRBovBkgRuxw063GaA@mail.gmail.com)），意即 **PG18 尚不支援**。要索引就必須顯式寫 `STORED`。
3. **virtual 生成欄位不能引用自訂函式或自訂型別**，只能用內建的。

**這一項本身就是一個「漏寫不會報錯」的陷阱**：漏寫 `STORED` 這個字，資料表建得起來、查詢跑得動，只是索引建不起來、儲存行為與預期不同。

---

## 3. `pg_jsonschema` 擴充套件的現況

### 3.1 套件本身

| 項目 | 事實 | 出處 |
|---|---|---|
| repo | `supabase/pg_jsonschema` | https://github.com/supabase/pg_jsonschema |
| 授權 | **Apache-2.0** | 同上 |
| 最新版本 | **v0.3.4**，發行於 **2026-02-11** | https://api.github.com/repos/supabase/pg_jsonschema/releases/latest |
| 維護狀態 | **活躍**。v0.3.4 內含「PostgreSQL 18 support」、底層 `jsonschema` crate 升至 0.33.0、decimal 驗證的 bug fix，並提供 PG14–18 × AMD64/ARM64 的預編譯產物 | 同上 |
| 匯出函式 | `json_matches_schema`、`jsonb_matches_schema`、`jsonschema_is_valid`、`jsonschema_validation_errors`，另有 compiled schema 變體 `json_matches_compiled_schema` / `jsonb_matches_compiled_schema` | README |
| **函式 volatility** | 四個主函式**皆宣告為 `immutable, strict, parallel_safe`** —— 原始碼 `#[pg_extern(immutable, strict, parallel_safe)]` | https://github.com/supabase/pg_jsonschema/blob/master/src/lib.rs |
| 支援的 JSON Schema draft | README 表示由底層 Rust `jsonschema` crate 決定，未逐項列出 → **未能查證，需人工確認**（需查 `jsonschema` crate 0.33.0 文件） | README |

官方 README 的 CHECK 約束用法：

```sql
create table customer(
    id serial primary key,
    metadata json,
    check (
        json_matches_schema(
            '{
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": { "type": "string", "maxLength": 16 }
                    }
                }
            }',
            metadata
        )
    )
);
```

**兩個必須配套的注意事項：**

1. **`immutable` 是好消息**：它符合 §2.3 官方對 CHECK 的 immutability 要求，且可用於 index 表達式。但**「函式本身 immutable」不等於「約束不會腐化」**——JSON Schema 是寫死在 DDL 裡的字串常數，改 schema 就是改約束定義，此時必須 `DROP CONSTRAINT` / `ADD CONSTRAINT`（會全表重驗），與 §2.3 的處理方式相同。
2. **`strict` 是需要小心的地方**：strict 函式在任一參數為 NULL 時直接回傳 NULL，不執行函式體。因此 `condition` 為 NULL 時 → 函式回傳 NULL → **CHECK 放行**。`condition jsonb NOT NULL` 仍然是必須的。**同一個 NULL 陷阱，換一個外殼。**

另外，JSON Schema 預設**允許未宣告的額外屬性**——要達成 §2.2 第 6 條的「封閉 key 集合」，schema 裡必須顯式寫 `"additionalProperties": false`。**漏寫這一行，拼錯的 key 照樣通過**。這是 JSON Schema 規格本身的預設行為，不是本套件的問題，但它意味著**即使用了 pg_jsonschema，「漏寫就沒有錯誤訊息」的風險依然存在，只是搬到 schema 字串裡**。

### 3.2 託管平台逐一查證（這決定了本選項是否存在）

| 平台 | 支援 `pg_jsonschema`？ | 依據 |
|---|---|---|
| **Neon** | ✅ **支援**。官方 supported extensions 表格明列，版本：PG14–17 為 **0.3.3**，PG18 為 **0.3.4** | [Neon Postgres extensions](https://neon.com/docs/extensions/pg-extensions)；[Extension explorer](https://neon.com/docs/extensions/extension-explorer) 亦列出。官方說明「Unless otherwise noted, supported extensions can be installed using `CREATE EXTENSION` syntax」，且**只能安裝清單上的擴充**，新擴充需向 Neon 支援或 Discord 提出申請 |
| **Supabase** | ✅ **支援**（本套件即 Supabase 自家維護）。Dashboard → Database → Extensions 搜尋啟用，或 `create extension pg_jsonschema with schema extensions;` | [Supabase docs: pg_jsonschema](https://supabase.com/docs/guides/database/extensions/pg_jsonschema)。⚠️ 官方頁面**未載明哪些方案可用** → 方案限制部分**未能查證，需人工確認** |
| **Fly.io Managed Postgres (MPG)** | ❌ **不支援**。官方支援清單為：btree_gin, btree_gist, citext, cube, dict_int, fuzzystrmatch, hstore, intarray, isn, lo, ltree, pg_stat_monitor, pg_trgm, pgcrypto, plpgsql, PostGIS (+raster/sfcgal/topology), seg, tablefunc, tcn, tsm_system_rows, tsm_system_time, unaccent, uuid-ossp, vector —— **無 `pg_jsonschema`** | [Fly.io Supported Postgres Extensions](https://fly.io/docs/mpg/extensions/)。官方僅表示「We plan on supporting additional third party extensions based on user feedback」，**未明說使用者能否自行安裝清單外擴充** → 該點**未能查證** |
| **Railway** | ⚠️ **官方 Postgres 範本不支援，需自建映像**。官方文件明言：「In an effort to maintain simplicity in the default templates, **we do not plan to add extensions to the PostgreSQL templates** covered in this guide.」但 Railway 的 Postgres 是**部署在使用者自己的服務上的 Docker 映像**（`railwayapp-templates/postgres-ssl`），使用者可 fork 該 repo 自行加裝 → **技術上可行，但等於自己維護資料庫映像** | [Railway PostgreSQL guide](https://docs.railway.com/guides/postgresql) |
| **Render Postgres** | ❌ **不在支援清單內**。Render 支援約 50 個擴充（pgvector、PostGIS、TimescaleDB 等），**無 `pg_jsonschema`**；官方文件**未明說**能否安裝清單外擴充 → 該點**未能查證** | [Render PostgreSQL extensions](https://render.com/docs/postgresql-extensions) |
| **自架 Postgres**（Fly Machine / VPS，`persistent-websocket-hosting.md` §「建議」的自用階段方案） | ✅ **可以**，自己 `CREATE EXTENSION` 前先安裝二進位；上游有 PG14–18 × AMD64/ARM64 預編譯 release | pg_jsonschema releases |

**對本票的關鍵推論**：

`docs/research/persistent-websocket-hosting.md` 對資料庫的建議是「**自用階段直接在同一台機器上自架 Postgres（US$0）**，上架階段再視需要換成 **Neon（新加坡）**或 **Fly Managed Postgres（東京）**」。

- **自架** → pg_jsonschema 可用 ✅
- **Neon** → pg_jsonschema 可用 ✅
- **Fly Managed Postgres** → **pg_jsonschema 不可用** ❌

也就是說，**「自架 → Fly MPG」這條遷移路徑會讓 pg_jsonschema 在遷移當下失效**，而「自架 → Neon」不會。#17（部署環境）尚未定案，因此**選 pg_jsonschema 等於對 #17 加上一條約束：不能選 Fly Managed Postgres 與 Render**。這是一個跨票的耦合，本文只指出它存在，不評價。

---

## 4. ★ `jsonb` 中數值的精度語意（本票最關鍵的一項）

### 4.1 PostgreSQL 端：`jsonb` 的數字用 `numeric` 儲存，**不是** IEEE 754 double

**題目的擔憂在 PostgreSQL 這一端不成立。** [PG18 datatype-json §8.14.1](https://www.postgresql.org/docs/18/datatype-json.html) 的 **Table 8.23. JSON Primitive Types and Corresponding PostgreSQL Types**：

| JSON primitive type | PostgreSQL type | Notes |
|---|---|---|
| `string` | `text` | `\u0000` is disallowed, as are Unicode escapes representing characters not available in the database encoding |
| **`number`** | **`numeric`** | **`NaN` and `infinity` values are disallowed** |
| `boolean` | `boolean` | Only lowercase `true` and `false` spellings are accepted |
| `null` | (none) | SQL `NULL` is a different concept |

**官方原文（題目要求的引用）**：

> When converting textual JSON input into `jsonb`, the primitive types described by RFC 7159 are effectively mapped onto native PostgreSQL types, as shown in Table 8.23. Therefore, there are some minor additional constraints on what constitutes valid `jsonb` data that do not apply to the `json` type, nor to JSON in the abstract, corresponding to limits on what can be represented by the underlying data type. **Notably, `jsonb` will reject numbers that are outside the range of the PostgreSQL `numeric` data type**, while `json` will not. Such implementation-defined restrictions are permitted by RFC 7159. **However, in practice such problems are far more likely to occur in other implementations, as it is common to represent JSON's `number` primitive type as IEEE 754 double precision floating point** (which RFC 7159 explicitly anticipates and allows for). **When using JSON as an interchange format with such systems, the danger of losing numeric precision compared to data originally stored by PostgreSQL should be considered.**

**這段話直接回答了本票**：PostgreSQL 自己**不會**把 JSON 數字降成 double；反而是官方文件在**警告「別的實作會」**。也就是說，`599.99` 存進 `jsonb` 之後，在 PostgreSQL 內部就是一個精確的 `numeric` `599.99`，與 `price numeric(20,8)` 的儲存語意**同源**。

輸出格式的補充（同一頁）：

> One semantically-insignificant detail worth noting is that in `jsonb`, numbers will be printed according to the behavior of the underlying `numeric` type. In practice this means that numbers entered with `E` notation will be printed without it, for example:
>
> ```
> SELECT '{"reading": 1.230e-5}'::json, '{"reading": 1.230e-5}'::jsonb;
>          json          |          jsonb
> -----------------------+-------------------------
>  {"reading": 1.230e-5} | {"reading": 0.00001230}
> ```
>
> However, `jsonb` will preserve trailing fractional zeroes, as seen in this example, even though those are semantically insignificant for purposes such as equality checks.

### 4.2 `condition->>'threshold'` 取出再 cast 成 `numeric` 是否無損？

**無損。** 推導鏈：

1. `jsonb` 內部的數字是 `numeric`（§4.1，官方明文）。
2. `->>` 的官方定義是「Extracts JSON object field with the given key, **as `text`**」——它輸出的是那個 `numeric` 的文字表示。
3. 官方明文說「numbers will be printed according to the behavior of the underlying `numeric` type」，且「`jsonb` will preserve trailing fractional zeroes」——**輸出是 numeric 的完整十進位表示，不經過任何二進位浮點中介**。
4. 因此 `(condition->>'threshold')::numeric` 是 `numeric → text → numeric` 的往返，**值不變**。

**標記：推導（依據為 §4.1 兩段官方原文），未能實跑驗證。**

> ⚠️ 一個次要但真實的差異：`numeric` 保留 scale，而 `jsonb` 保留 trailing zeros。`'{"t": 599.990}'::jsonb ->> 't'` 得到 `599.990`，cast 成 `numeric` 是 `599.990`（scale 3）。它與 `599.99`（scale 2）**數值相等**（`=` 為 true），但**文字表示不同**。若日後要對 `condition` 做整份 `jsonb` 的相等比較或建 unique 約束，`{"t":599.99}` 與 `{"t":599.990}` 會被視為**不同的 jsonb 值**（官方明言 trailing zeros「semantically insignificant for purposes such as equality checks」——這句話說的是它們在語意上不重要，但 jsonb 仍會保留它們）。**這一點官方措辭略有歧義，jsonb 相等比較是否忽略 trailing zeros → 未能查證，需人工確認**（需實跑 `SELECT '{"t":1.0}'::jsonb = '{"t":1.00}'::jsonb`）。

### 4.3 ★ Python 端：這裡才是真正會掉精度的地方

**PostgreSQL 沒問題，psycopg 的預設路徑有問題。**

[psycopg 3 官方文件 `docs/basic/adapt.rst`「JSON adaptation」](https://www.psycopg.org/psycopg3/docs/basic/adapt.html)（原文取自 [官方 repo 原始碼](https://raw.githubusercontent.com/psycopg/psycopg/master/docs/basic/adapt.rst)，因 psycopg.org 對本工具回 403）：

> Psycopg can map between Python objects and PostgreSQL `json/jsonb types`, allowing to customise the load and dump function used.
>
> Because several Python objects could be considered JSON (dicts, lists, scalars, even date/time if using a dumps function customised to use them), **Psycopg requires you to wrap the object to dump as JSON into a wrapper: either `psycopg.types.json.Json` or `psycopg.types.json.Jsonb`.**
>
> ```python
> from psycopg.types.json import Jsonb
> thing = {"foo": ["bar", 42]}
> conn.execute("INSERT INTO mytable VALUES (%s)", [Jsonb(thing)])
> ```
>
> **By default Psycopg uses the standard library `json.dumps` and `json.loads` functions to serialize and de-serialize Python objects to JSON.** If you want to customise how serialization happens, for instance changing serialization parameters or using a different JSON library, you can specify your own functions using the `psycopg.types.json.set_json_dumps()` and `psycopg.types.json.set_json_loads()` functions, to apply either globally or to a specific context (connection or cursor).
>
> ```python
> from functools import partial
> from psycopg.types.json import Jsonb, set_json_dumps, set_json_loads
> import ujson
>
> # Use a faster dump function
> set_json_dumps(ujson.dumps)
>
> # Return floating point values as Decimal, just in one connection
> set_json_loads(partial(json.loads, parse_float=Decimal), conn)
>
> conn.execute("SELECT %s", [Jsonb({"value": 123.45})]).fetchone()[0]
> # {'value': Decimal('123.45')}
> ```

同一份文件的 Numbers 一節：Python `int` 依大小對應 `smallint`/`integer`/`bigint`/`numeric`；Python `float` 對應 `float8`；**Python `decimal.Decimal` 對應 `numeric`**。

**實測**（Python 3.13，純標準庫，本機以 `uv run --python 3.13 --no-project` 執行）：

```
dumps(Decimal) -> TypeError: Object of type Decimal is not JSON serializable
default loads type: float 599.99
parse_float=Decimal type: Decimal Decimal('599.99')
0.1+0.2 = 0.30000000000000004
Decimal(float 599.99) = Decimal('599.990000000000009094947017729282379150390625')
```

**兩個方向都會出事：**

| 方向 | 預設行為 | 後果 |
|---|---|---|
| **讀（DB → Python）** | psycopg 用 `json.loads` → JSON 非整數數字變成 Python **`float`** | `599.99` 在 Python 端變成 IEEE 754 double。再 `Decimal(x)` 會得到 `Decimal('599.990000000000009094947017729282379150390625')`。**與 `price numeric(20,8)` 直接比較時就是浮點比較**——「價格 >= 門檻」在邊界上的行為不再是十進位語意 |
| **寫（Python → DB）** | psycopg 用 `json.dumps` → `Decimal` **直接拋 `TypeError`** | 好消息：**這個方向會大聲失敗，不會靜默降精度**。壞消息：為了讓它能寫，最省事的做法是 `float(threshold)` —— 一個一行的、看起來無害的、把精度扔掉的修正 |

**修法存在且是官方支援的**：`set_json_loads(partial(json.loads, parse_float=Decimal), conn)` 官方文件明文列出並附範例輸出（`{'value': Decimal('123.45')}`）。寫入方向則需自訂 `dumps`（官方文件示範了 `UUIDEncoder` 的等價手法）。

**但這正是本專案禁忌的教科書案例**：這兩行設定**漏寫不會有任何錯誤訊息**。程式照跑、警示照送，只是門檻悄悄變成一個近似值。而且它**沒有任何測試會自然抓到**——除非測資恰好選在一個十進位不可精確表示的邊界上。

### 4.4 與本專案既有金額型別的對照

`docs/spec/data-model.md` 的既有欄位：`price numeric(20,8)`、`fee numeric(20,4)`——**沒有任何一欄用浮點**。

| 路徑 | 精度語意 | 與 `numeric` 欄位同源？ |
|---|---|---|
| `threshold numeric(20,8)` 具名欄位 | 十進位精確；psycopg 直接給 `Decimal` | ✅ **完全同源，零設定** |
| `condition->>'threshold'` → `::numeric`（**在 SQL 內比較**） | 十進位精確（§4.2 推導） | ✅ 同源，但每次查詢都要記得寫 cast |
| `condition['threshold']`（**取回 Python 再比較**，psycopg 預設） | **IEEE 754 double** | ❌ **不同源** |
| 同上 + `set_json_loads(..., parse_float=Decimal)` | 十進位精確 | ✅ 同源，**但靠一行全域設定撐著** |

**單向門的判定**：題目問的是「若 `jsonb` 會讓 `599.99` 失去精確性，這是一個現在不決定、之後改要動所有既有規則列的單向門」。

**答案是：不是 `jsonb` 造成的單向門，而是 Python 端預設值造成的單向門，而且它是可逆的。**

- **資料庫裡的值本來就是精確的**（§4.1）。就算專案跑了半年才發現 Python 端一直在用 float，**資料庫裡的 `599.99` 依然是精確的 `599.99`**，改設定即可，**不需要 migrate 任何一列**。
- 真正需要動既有列的，是「決定從 `jsonb` 改成具名欄位」——那是**資料模型**的單向門，與精度無關。
- 但 `jsonb` **確實**讓精度風險從「型別系統保證」降級成「一行連線設定 + 開發者記得寫 cast」。**它把一個編譯期／宣告期的保證，換成一個執行期的慣例。**

---

## 5. 索引能力比較

> 前提：本專案量級極小（單人、個位數規則），**效能不是決定因素**。以下只回答「有沒有硬限制」。

### 5.1 `jsonb` 上的索引

[PG18 datatype-json §8.14.4 jsonb Indexing](https://www.postgresql.org/docs/18/datatype-json.html) 原文摘要：

> GIN indexes can be used to efficiently search for keys or key/value pairs occurring within a large number of `jsonb` documents (datums). Two GIN "operator classes" are provided […]
>
> **The default GIN operator class for `jsonb` supports queries with the key-exists operators `?`, `?|` and `?&`, the containment operator `@>`, and the `jsonpath` match operators `@?` and `@@`.**
>
> The non-default GIN operator class `jsonb_path_ops` does not support the key-exists operators, but it does support `@>`, `@?` and `@@`.

**關鍵限制**（官方原文）：

> However, the index could not be used for queries like the following, **because though the operator `?` is indexable, it is not applied directly to the indexed column** `jdoc`:
>
> ```sql
> SELECT jdoc->'guid', jdoc->'name' FROM api WHERE jdoc -> 'tags' ? 'qui';
> ```
>
> Still, **with appropriate use of expression indexes, the above query can use an index.**

`jsonb` 的 B-tree：

> `jsonb` also supports `btree` and `hash` indexes. **These are usually useful only if it's important to check equality of complete JSON documents.** The `btree` ordering for `jsonb` datums is seldom of great interest […]

### 5.2 對照表

| 查詢形態 | GIN on `jsonb` | 表達式索引 on `jsonb` | B-tree on 具名欄位 |
|---|---|---|---|
| 「有沒有 `operator` 這個 key」`condition ? 'operator'` | ✅（`jsonb_ops`） | ✅ | N/A（key 就是欄位，恆存在） |
| 「`operator` = `'gt'`」等值 | ✅ 用 `@> '{"operator":"gt"}'` | ✅ `((condition->>'operator'))` | ✅ |
| **「`threshold` > 599.99」範圍查詢** | ❌ **GIN 不支援 `jsonb` 上的範圍比較**（GIN 的 jsonb operator class 只涵蓋 `?`/`?|`/`?&`/`@>`/`@?`/`@@`，其中無 `<`/`>`） | ✅ **要建 `((condition->>'threshold')::numeric)` 的 B-tree 表達式索引** | ✅ 天然支援 |
| 排序 `ORDER BY threshold` | ❌ | ✅（同上表達式索引） | ✅ |
| **唯一性約束**（例如「同一標的同一 rule_type 只能有一條」） | ❌ | ✅ **可用 unique 表達式索引** | ✅ `UNIQUE (user_id, instrument_id, rule_type)` |
| 整份文件相等 | ✅ B-tree/hash on jsonb | — | — |

**「表達式索引可當約束」**——[PG18 §11.7 Indexes on Expressions](https://www.postgresql.org/docs/18/indexes-expressional.html) 原文：

> If we were to declare this index `UNIQUE`, it would prevent creation of rows whose `col1` values differ only in case, as well as rows whose `col1` values are actually identical. **Thus, indexes on expressions can be used to enforce constraints that are not definable as simple unique constraints.**

以及維護成本：

> **Index expressions are relatively expensive to maintain**, because the derived expression(s) must be computed for each row insertion and non-HOT update. However, the index expressions are *not* recomputed during an indexed search […]

**表達式的 immutability 要求**（[PG18 CREATE INDEX](https://www.postgresql.org/docs/18/sql-createindex.html)）：

> **All functions and operators used in an index definition must be "immutable"**, that is, their results must depend only on their arguments and never on any outside influence (such as the contents of another table or the current time). This restriction ensures that the behavior of the index is well-defined. To use a user-defined function in an index expression or `WHERE` clause, remember to mark the function immutable when you create it.

> 註：`->`、`->>`、`?`、`jsonb_typeof` 皆為 immutable —— 由官方文件本身示範 `CREATE INDEX idxgintags ON api USING GIN ((jdoc -> 'tags'));` 可反推（索引表達式必須 immutable）。**推導，未逐一查 `pg_proc.provolatile` 驗證。**

### 5.3 硬限制小結

**沒有任何一種查詢是 `jsonb` 做不到的**——只要願意為每個要查的欄位額外建一個表達式索引。差別是：

- 具名欄位：索引能力**內建於型別系統**，`ORDER BY`、`>`、`UNIQUE` 都天然可用。
- `jsonb`：範圍查詢與唯一約束**必須另外顯式建表達式索引**，而**忘了建也不會報錯**（只是慢，本專案量級下慢也感覺不出來）——**又一次同形狀的「漏寫不報錯」，只是這次的後果溫和**。

---

## 6. Pydantic v2 的 discriminated union

### 6.1 官方文件怎麼說

[Pydantic 官方文件「Unions」](https://pydantic.dev/docs/validation/latest/concepts/unions/)（`docs.pydantic.dev/latest/concepts/unions/` 已 301 導向此網址）原文與要點：

> Unions can be validated more efficiently using a discriminator, by specifically choosing which member of the union to validate against.

- **字串 discriminator**：每個 union 成員上設一個共同欄位，值為 `Literal`，再以 `Field(discriminator='field_name')` 指定。驗證引擎依該欄位決定要用哪個成員驗證。
- **Callable discriminator**：`Discriminator(callable)`，適用於沒有統一欄位的情形；callable 收到輸入資料（`dict` 或 model 實例）並回傳 tag 或 `None`。
- **`Tag` 標註**：`Annotated[UnionType, Tag('label')]` 搭配 `Discriminator`，讓錯誤訊息更清楚。

**官方陳述的好處：**

| 好處 | 官方措辭 |
|---|---|
| 效能 | 「This makes validation more efficient」 |
| 錯誤訊息 | discriminated unions「avoid a proliferation of errors when validation fails」——失敗時只產生對應分支的錯誤，不會把所有成員的錯誤都吐出來 |
| Schema | 「Adding discriminator to unions also means the generated JSON schema implements the `discriminator` attribute from the OpenAPI specification」 |

**官方陳述的限制**：discriminated union 不能只有單一成員（`Union[Cat]` 會被 Python 自動化簡成 `Cat`）。

### 6.2 它能保證什麼、**不能**保證什麼

這是本節的重點，也是題目的核心提問。

**能保證的（全部在應用程序記憶體內）：**

1. **穿過 FastAPI request body 的 payload**，若不符合任一分支，回 422，且錯誤訊息會精確指向出錯的分支。
2. `rule_type` 是 `Literal['price_threshold']` 這種宣告，能讓 mypy / pyright **在靜態分析階段**就抓到「這個分支沒有 `threshold` 欄位」。
3. **自動產生的 OpenAPI schema 帶 `discriminator`**——對本專案有實質價值：`docs/spec/tech-stack.md` §3 明言 OpenAPI 自動產生是「補上前後端不同語言這個缺口的關鍵」。前端拿到的 TypeScript 型別會是一個正確的 discriminated union。

**不能保證的：**

1. **它完全擋不住繞過應用層的寫入。** Pydantic 是一個 Python 函式庫，它的驗證只在「有 Python 程式呼叫 `Model.model_validate(...)`」時發生。以下每一條路徑都**繞過它**，且資料庫端**沒有任何東西會抱怨**：
   - **Alembic / SQL migration**：`UPDATE alert SET condition = ...` 直接改 jsonb。
   - **手動 `psql`**：使用者半夜想調一個門檻，直接改。
   - **CLI / 一次性腳本**：即使腳本 import 了 model，寫 `conn.execute("UPDATE ...")` 就繞過了。
   - **任何用 `model_construct()` 的程式碼**：這是 Pydantic 官方提供的「跳過驗證直接建構」的 API。
   - **`model_config = ConfigDict(validate_assignment=False)`（預設值）**：物件建好後 `obj.operator = "typo"` **不會重新驗證**。
2. **它不會在讀取時把壞資料變成錯誤——除非你顯式驗證。** 如果從 DB 讀回的 dict 直接餵進評估函式（而不是 `model_validate`），Pydantic 完全不在場。要它守讀取這一側，**必須每個讀取路徑都記得呼叫驗證**——**漏寫不會有錯誤訊息**。
3. **它保護不了「已經在資料庫裡的壞資料」。** 加一個新的 `Literal` 分支，Pydantic 只影響此後的驗證；DB 裡舊格式的列會在下次被讀取並驗證時才炸——**而炸的時機是警示評估的當下（盤中）**，不是部署時。

### 6.3 一句話總結

**Pydantic discriminated union 是「進門處的守衛」，不是「房子的牆」。** 它守得住 HTTP API 這一道門，守不住 `psql`、migration、腳本這些側門。它與 DB 約束不是替代關係，是**互補**關係——而本專案的原則要問的正是「哪一層是牆」。

---

## 7. 對 issue #15 待決事項 2 的影響

> 本節不推薦任何方案。目的只有一個：把每個候選方案「**DB 層真的擋得住什麼**」與「**只是應用層的君子協定**」分乾淨。

### 7.0 先把「五種失效模式」定義出來

後面每個方案都對這五項逐一回答。

| 代號 | 失效模式 | 為什麼它符合本專案的禁忌 |
|---|---|---|
| **F1** | **欄位名打錯**：`{"oprator": "gt"}` | 規則永不觸發，資料庫收下，程式碼靜默略過 |
| **F2** | **必填欄位漏寫**：`{"operator": "gt"}` 沒有 `threshold` | 同上 |
| **F3** | **值域錯誤**：`{"operator": "greater_than"}`（沒人處理的字串） | 同上 |
| **F4** | **型別錯誤**：`{"threshold": "599.99"}`（字串不是數字） | 比較可能拋例外，也可能字典序比較後靜默給錯答案 |
| **F5** | **數值精度流失**：`599.99` 變成 `599.990000000000009…` | 邊界上的觸發／不觸發變成不確定，且**永遠不會有錯誤訊息** |

**以及一條貫穿全部的前提**：任何方案裡，**只要允許 `condition IS NULL` 或 `operator IS NULL`，所有 CHECK 都會因 TRUE-or-UNKNOWN 語意而被短路放行**（§2.2）。**`NOT NULL` 不是可選項，它是所有其他約束的前提條件。**

---

### 方案 A：單表 + 裸 `jsonb`（＝現況佔位）

```sql
alert(id, user_id, instrument_id, condition jsonb, is_enabled boolean)
```

| 失效模式 | DB 層擋得住？ | 說明 |
|---|---|---|
| F1 欄位名打錯 | ❌ **完全擋不住** | `jsonb` 型別只保證「是合法 JSON」 |
| F2 必填漏寫 | ❌ **完全擋不住** | 同上 |
| F3 值域錯誤 | ❌ **完全擋不住** | 同上 |
| F4 型別錯誤 | ❌ **完全擋不住** | 同上 |
| F5 精度流失 | ⚠️ **DB 端安全，Python 端預設不安全** | jsonb 內部是 `numeric`（§4.1）；但 psycopg 預設 `json.loads` 會給 `float`（§4.3 實測） |

**DB 層唯一真正擋得住的事**：值是合法 JSON、且數字在 `numeric` 範圍內。

**這正是本專案已經拒絕過兩次的形狀。** 這不是評價，是事實比對：`transaction.status` 被拒的理由與 `user_id` 漏過濾被警告的理由，都是「漏寫不會有錯誤訊息」；A 對 F1–F4 四項全部落在這個描述裡。

**代價**：零 migration 成本、規則形狀完全自由。
**單向門性質**：從 A 改成 B/C/D **需要 migrate 每一列既有規則**。以本專案量級（個位數規則）而言，這個 migration 的成本接近零；真正的成本是「發現需要改」之前，靜默失效已經跑了多久。

---

### 方案 B：單表 + 具名欄位

```sql
alert(
  id, user_id, instrument_id,
  rule_type text NOT NULL,
  operator  text NOT NULL,
  threshold numeric(20,8) NOT NULL,
  is_enabled boolean NOT NULL,
  CONSTRAINT alert_rule_type_chk CHECK (rule_type IN ('price_threshold','pct_change','volume')),
  CONSTRAINT alert_operator_chk  CHECK (operator  IN ('gt','gte','lt','lte'))
)
```

| 失效模式 | DB 層擋得住？ | 說明 |
|---|---|---|
| F1 欄位名打錯 | ✅ **完全擋得住** | `INSERT INTO alert (oprator) ...` → `ERROR: column "oprator" of relation "alert" does not exist`。**這是本題唯一「拼錯欄位名會得到明確錯誤訊息」的方案類別** |
| F2 必填漏寫 | ✅ **完全擋得住** | `NOT NULL` → `ERROR: null value in column "threshold" violates not-null constraint` |
| F3 值域錯誤 | ✅ **擋得住** | `CHECK (operator IN (...))`。⚠️ 注意：**唯有搭配 `NOT NULL` 才成立**——`operator` 為 NULL 時 `NULL IN (...)` → NULL → 放行（§2.2） |
| F4 型別錯誤 | ✅ **完全擋得住** | `threshold numeric` → 塞 `'abc'` 會 `ERROR: invalid input syntax for type numeric` |
| F5 精度流失 | ✅ **完全擋得住，零設定** | `numeric` ↔ psycopg ↔ Python `Decimal` 是官方文件明列的對應（§4.3）。**與 `price numeric(20,8)`、`fee numeric(20,4)` 完全同源** |

**代價（誠實列出）：**

1. **多型規則的欄位會互相矛盾。** 「價格門檻」需要 `threshold`；「財報公布日提醒」不需要 `operator` 也不需要 `threshold`；「漲跌幅」的 `threshold` 單位是百分比不是錢。單表要容納，就得讓部分欄位可為 NULL——**而 NULL 一旦允許，該欄位上所有 CHECK 都被短路放行（§2.2）**。要維持保證，就得寫 `CHECK (CASE WHEN rule_type='price_threshold' THEN threshold IS NOT NULL ... ELSE false END)`——**注意這個 `ELSE false` 是必要的，寫成 `ELSE NULL` 或省略 `ELSE` 就等於對未知 rule_type 全部放行**。這是 B 方案裡唯一一個「漏寫不報錯」的殘留點。
2. **加一種規則型別要 `ALTER TABLE`。** 加欄位 + 改 CHECK。改 CHECK 預設會**全表掃描重驗**（§2.4），本專案量級下瞬間完成；若不想掃可用 `NOT VALID` + 之後 `VALIDATE CONSTRAINT`。
3. **`threshold` 的單位語意被扁平化。** 一個 `numeric` 欄位同時承載「599.99 元」與「5.0 %」，DB 層無法區分。這是**新引入的一種 F3 變形**，且 CHECK 擋不住（`5.0` 對兩者都是合法值）。

---

### 方案 C：每種規則型別各一張表

```sql
alert_price_threshold(id, user_id, instrument_id, operator text NOT NULL, threshold numeric(20,8) NOT NULL, ...)
alert_pct_change(id, user_id, instrument_id, direction text NOT NULL, pct numeric(10,4) NOT NULL, window_days int NOT NULL, ...)
alert_earnings_date(id, user_id, instrument_id, days_before int NOT NULL, ...)
```

| 失效模式 | DB 層擋得住？ | 說明 |
|---|---|---|
| F1–F4 | ✅ **完全擋得住，且比 B 更嚴** | 每張表的欄位集合都是**該型別專屬**，不需要任何 NULL、不需要任何 `CASE`。**B 方案殘留的「`ELSE false` 漏寫」風險在 C 完全消失** |
| F5 精度流失 | ✅ **完全擋得住，零設定** | 同 B |

**額外擋得住的（B 做不到的）：**
- **單位語意**：`threshold numeric(20,8)`（元）與 `pct numeric(10,4)`（%）是不同表的不同欄位，型別與名稱都能表達單位。
- **每型別專屬的唯一性約束**：`UNIQUE (user_id, instrument_id, operator)` 只對價格門檻表有意義，在 C 可以自然表達。

**代價（誠實列出）：**

1. **`alert_delivery` / `notification` 之類的下游表無法用單一外鍵指向「一則警示」。** `data-model.md` 已有 `alert_id bigint FK` 的表（見 §`alert` 後續）。C 會迫使這個 FK 變成：
   - (a) 每種型別各一個 nullable FK 欄位 + `CHECK` 保證恰好一個非 NULL（**這個 CHECK 本身又是一個 CASE，回到同樣的問題**）；或
   - (b) 引入一張 `alert(id, user_id, instrument_id, rule_type, is_enabled)` 母表，各型別表以 `alert_id` 為 PK + FK（**classic table-per-type**）。此時 `alert.rule_type` 與「實際存在哪張子表」的一致性，**PostgreSQL 沒有原生機制保證**（沒有 disjoint subclass 約束）。可用 `(id, rule_type)` 複合唯一鍵 + 子表 `CHECK (rule_type = 'price_threshold')` + 複合 FK 這個經典技巧達成——**這個技巧是有效的**，但它把 schema 複雜度推高一階。
2. **每加一種規則型別要 `CREATE TABLE`**，不是 `ALTER TABLE`。
3. **「列出使用者所有警示」變成 N 路 `UNION ALL`**，或需要一張母表。以本專案量級（個位數規則）效能無關，但**每加一種型別，這個 UNION 就要多一支——漏加一支不會有錯誤訊息，只是那類警示在列表頁消失**。⚠️ **這是 C 方案自己引入的一個新的、符合本專案禁忌形狀的失效模式**，位置從資料層搬到查詢層。

---

### 方案 D：混合（具名欄位承載共通部分 + `jsonb` 承載型別專屬部分）

```sql
alert(
  id, user_id, instrument_id,
  rule_type text NOT NULL CHECK (rule_type IN (...)),
  is_enabled boolean NOT NULL,
  params jsonb NOT NULL,
  ...
)
```

**這個方案的安全度**完全取決於「哪些欄位被拉出來」，因此必須分兩種子形態討論。

#### D-1：`threshold` 留在 `jsonb` 裡

| 失效模式 | DB 層擋得住？ |
|---|---|
| F1 欄位名打錯（在 `params` 內） | ❌ 除非顯式寫 §2.2 那組 CHECK（含 `- key` 封閉集合），否則擋不住 |
| F2 必填漏寫（在 `params` 內） | ❌ 同上 |
| F3 值域錯誤（`rule_type`） | ✅ 擋得住 |
| F3 值域錯誤（`params` 內的 `operator`） | ❌ 除非顯式 CHECK + `COALESCE(..., false)` |
| F4 型別錯誤（`params.threshold`） | ❌ 除非顯式 `jsonb_typeof(params->'threshold') = 'number'`，且**必須先驗存在性** |
| **F5 精度流失** | ⚠️ **DB 端安全，Python 端預設不安全**——與 A 相同 |

#### D-2：`threshold numeric` 拉成具名欄位，`jsonb` 只放「真正因型別而異」的參數

```sql
  rule_type  text          NOT NULL,
  operator   text          NOT NULL,
  threshold  numeric(20,8) NOT NULL,
  extra      jsonb         NOT NULL DEFAULT '{}'::jsonb,
```

| 失效模式 | DB 層擋得住？ |
|---|---|
| F1/F2/F3/F4 **對三個具名欄位** | ✅ 完全擋得住（同 B） |
| F1/F2/F3/F4 **對 `extra` 內的東西** | ❌ 除非顯式 CHECK |
| **F5 精度流失** | ✅ **完全擋得住，零設定**（`threshold` 是真 `numeric`） |

**D 的核心事實**：**`jsonb` 裡的東西，DB 層的保證是「零」，除非你為每一個 key 顯式寫一條處理過 NULL 的 CHECK。** 因此 D 的安全度 = 「被拉出來的欄位」的集合。**設計上的關鍵問題不是「要不要用 jsonb」，而是「哪些欄位絕對不能待在 jsonb 裡」。** 依 §4 的分析，`threshold`（＝錢）是最強的候選。

**D 特有的技術選項與陷阱**（§2.6）：可用 `GENERATED ALWAYS AS ((params->>'threshold')::numeric) **STORED**` 把 jsonb 內的值投影成可索引的具名欄位。⚠️ **PG18 起不寫 `STORED` 就會拿到 VIRTUAL，而 VIRTUAL 生成欄位不能建索引**。這個「漏寫一個關鍵字、不報錯、行為不同」的陷阱，形狀與本專案禁忌完全一致。

---

### 方案 E：任一選項 + Pydantic discriminated union（可疊加）

**E 是正交的，它不改變 A/B/C/D 在 DB 層的任何一格。**

| 失效模式 | Pydantic 擋得住？ | 在哪裡擋 |
|---|---|---|
| F1 欄位名打錯 | ⚠️ **只在 HTTP API 這道門擋得住**（且需 `model_config = ConfigDict(extra='forbid')`——**預設是 `'ignore'`，會靜默丟掉多餘欄位**） | 應用層記憶體內 |
| F2 必填漏寫 | ⚠️ 同上 | 應用層 |
| F3 值域錯誤 | ⚠️ 同上（`Literal` / `Enum`） | 應用層 |
| F4 型別錯誤 | ⚠️ 同上 | 應用層 |
| F5 精度流失 | ⚠️ **可以用 `Decimal` 型別標註**，但若上游 psycopg 已經給了 `float`，Pydantic 收到的就是 float——`Decimal(599.99)` 會得到 `Decimal('599.990000000000009…')`（§4.3 實測）。**Pydantic 無法還原已經流失的精度** | 應用層 |

**E 明確擋不住的（§6.2）**：Alembic migration、手動 `psql`、CLI 腳本、`model_construct()`、指派後不重驗（`validate_assignment` 預設 `False`）。

**E 的真實價值**（不宜低估，但要說對）：
- **錯誤訊息品質**：Pydantic 的 422 會精確指出「哪個分支、哪個欄位、什麼問題」；CHECK 約束只會給 `violates check constraint "alert_condition_check"`。
- **靜態型別檢查**：`Literal` discriminator 讓 mypy/pyright 在**寫程式的時候**就抓到分支處理不全——這是 DB 約束做不到的、唯一「在執行前」發生的檢查。
- **OpenAPI → 前端型別**：`tech-stack.md` §3 已把 OpenAPI 自動產生列為選型的關鍵理由，discriminated union 會如實反映到前端的 TypeScript union。

**一句話**：E 讓「寫錯」在開發階段與 API 邊界變得吵鬧；它不改變「已經寫進 DB 的東西是否可信」這件事一分一毫。

---

### 7.1 綜覽表：DB 層真的擋得住的（✅）vs 只是君子協定的（❌／⚠️）

| | **A** 裸 jsonb | **A + §2.2 完整 CHECK** | **B** 具名欄位 | **C** 每型別一表 | **D-1** jsonb 含 threshold | **D-2** threshold 具名 | **+ pg_jsonschema** | **+E** Pydantic |
|---|---|---|---|---|---|---|---|---|
| F1 欄位名打錯 | ❌ | ✅（需 `- key` 封閉集合） | ✅ | ✅ | ❌ | 具名 ✅／jsonb ❌ | ✅（需 `additionalProperties:false`） | ⚠️ 僅 API 門（需 `extra='forbid'`） |
| F2 必填漏寫 | ❌ | ✅（需 `?&`，不可用 `->>`） | ✅ | ✅ | ❌ | 具名 ✅／jsonb ❌ | ✅（需 `required`） | ⚠️ 僅 API 門 |
| F3 值域錯誤 | ❌ | ✅（需 `COALESCE(...,false)`） | ✅（需 `NOT NULL`） | ✅ | ❌ | 具名 ✅／jsonb ❌ | ✅（需 `enum`） | ⚠️ 僅 API 門 |
| F4 型別錯誤 | ❌ | ✅（需先驗存在性） | ✅ 型別系統 | ✅ 型別系統 | ❌ | 具名 ✅／jsonb ❌ | ✅ | ⚠️ 僅 API 門 |
| **F5 精度流失** | ⚠️ 靠一行 `set_json_loads` | ⚠️ 同左 | ✅ **零設定** | ✅ **零設定** | ⚠️ 靠一行設定 | ✅ **零設定** | ⚠️ 靠一行設定 | ❌ 無法還原已流失的精度 |
| 擋得住 `psql` 手改？ | — | ✅ | ✅ | ✅ | 部分 | 部分 | ✅ | ❌ |
| 擋得住 migration 直寫？ | — | ✅ | ✅ | ✅ | 部分 | 部分 | ✅ | ❌ |
| 錯誤訊息會指名欄位？ | — | ❌ 只給約束名 | ✅ | ✅ | ❌ | 具名 ✅ | ⚠️ 可用 `jsonschema_validation_errors` 另外查 | ✅ 最詳細 |
| 加一種規則型別要動什麼 | 什麼都不用 | 改 CHECK（CASE 分支） | `ALTER TABLE` + 改 CHECK | `CREATE TABLE` + 改 UNION | 什麼都不用 | 可能 `ALTER TABLE` | 改 schema 字串 + 重建約束 | 加一個 model class |
| **本方案自己引入的新「漏寫不報錯」點** | — | `CASE` 缺 `ELSE false`；`- key` 清單漏更新 | `CASE` 缺 `ELSE false`；單位語意扁平化 | **UNION 漏加一支** | 同 A | `GENERATED` 漏寫 `STORED` | schema 漏寫 `additionalProperties:false` | 漏寫 `extra='forbid'`；讀取路徑漏呼叫 `model_validate` |
| 對 #17（部署）的約束 | 無 | 無 | 無 | 無 | 無 | 無 | **不能選 Fly MPG / Render** | 無 |

### 7.2 三個必須攤在檯面上的事實

**(1) 「用 jsonb + CHECK」不是「比較不安全」，而是「安全度取決於有沒有把六件事全部寫對」。**
§2.2 那六條 CHECK 若全部寫對（`NOT NULL` + `jsonb_typeof(condition)='object'` + `?&` + `jsonb_typeof(...)` + `COALESCE(...,false)` + `- key` 封閉集合），**F1–F4 全部擋得住，與 B 幾乎等價**。差別在於：
- B 的保證來自**型別系統與 `NOT NULL`**，是宣告式的、不會寫錯的。
- A+CHECK 的保證來自**六條手寫的布林表達式**，其中至少三條有 NULL 陷阱、一條需要維護一份 key 清單。**這些表達式寫錯了，PostgreSQL 不會告訴你——CHECK 約束建立成功，只是不擋東西。**

換句話說：**「用 CHECK 保護 jsonb」這件事本身，就是一個「漏寫不會有任何錯誤訊息」的活動。**

**(2) 精度這一項的結論與題目的假設相反，但方向對本票有利。**
`jsonb` **不會**讓 `599.99` 在資料庫裡失去精確性（§4.1 官方明文：JSON number → `numeric`）。因此**「現在不決定、之後改要動所有既有規則列」這個單向門，在精度這一項上不存在**——DB 裡的值一直是精確的，改設定即可，不需要 migrate。

但**風險換了個位置**：從「資料庫型別」搬到「psycopg 的一行連線設定」（§4.3 實測：預設 `json.loads` 給 `float`，`Decimal(599.99)` → `Decimal('599.990000000000009094947017729282379150390625')`）。**這一行漏寫不會有任何錯誤訊息**——這正是本專案禁忌的定義。相對地，具名 `numeric` 欄位的精度保證**不需要任何設定**，與既有的 `price numeric(20,8)`、`fee numeric(20,4)` 同源。

**(3) `pg_jsonschema` 是唯一能在 DB 層做「真正 schema 驗證」的路，但它綁定部署選項。**
Neon ✅、Supabase ✅、**自架 ✅**；**Fly Managed Postgres ❌、Render ❌**、Railway 需自建映像。而 `persistent-websocket-hosting.md` 對資料庫的既有建議是「自架 → 之後換 Neon 或 **Fly MPG**」。**選 pg_jsonschema 等於在 #17 上砍掉 Fly MPG 這個選項。** 這是一條跨票約束，值得在 grilling 時與 #17 一起看。

---

## 8. 未能查證清單

| # | 事項 | 狀態 |
|---|---|---|
| U1 | `pg_jsonschema` 支援哪些 JSON Schema draft（4/6/7/2019-09/2020-12） | **未能查證，需人工確認**。README 表示由底層 Rust `jsonschema` crate（v0.33.0）決定，未逐項列出 |
| U2 | Supabase 的 `pg_jsonschema` 是否在所有方案（含 Free）可用 | **未能查證，需人工確認**。官方擴充頁未載明方案限制 |
| U3 | Fly Managed Postgres / Render 是否允許使用者自行安裝清單外擴充 | **未能查證，需人工確認**。兩家官方文件皆未明說禁止或允許 |
| U4 | `'{"t":1.0}'::jsonb = '{"t":1.00}'::jsonb` 是否為 true | **未能查證，需人工確認**。官方措辭「preserve trailing fractional zeroes … even though those are semantically insignificant for purposes such as equality checks」語意含糊；本機無 PostgreSQL 實例可實跑 |
| U5 | 本文所有 SQL 行為（`?` 回傳 false 而非 NULL、`- key` 封閉集合、`JSON_EXISTS` 可用於 CHECK 等） | **均為文件推導，未實跑驗證**。本機 `psql` 與 `docker` 皆不可用 |
| U6 | PG18 「virtual generated column 不能建索引」的官方文件明文段落 | **僅由 commit 訊息與 hackers 討論串佐證**；`ddl-generated-columns.html` 與 `sql-createindex.html` 兩頁**均未直接載明此限制** → 正式文件缺漏，需以實跑確認 |
| U7 | `->`、`->>`、`?`、`jsonb_typeof` 的 `pg_proc.provolatile` 實際值 | 由「官方示範用它們建索引」反推為 immutable，**未逐一查目錄驗證** |

---

## 9. 來源清單

**PostgreSQL 官方（一律 v18）**
- 版本政策：https://www.postgresql.org/support/versioning/
- JSON 型別（含數值儲存語意、jsonb 索引）：https://www.postgresql.org/docs/18/datatype-json.html
- JSON 函式與運算子（`IS JSON`、`JSON_EXISTS`/`VALUE`/`QUERY`、`?`、`->>`、`-`、`@?`/`@@`、`jsonb_typeof`）：https://www.postgresql.org/docs/18/functions-json.html
- 約束（CHECK 的 immutability 警語、TRUE-or-UNKNOWN 語意、不得跨列）：https://www.postgresql.org/docs/18/ddl-constraints.html
- CREATE TABLE（CHECK 不得含子查詢、GENERATED ALWAYS AS STORED/VIRTUAL）：https://www.postgresql.org/docs/18/sql-createtable.html
- ALTER TABLE（`NOT VALID` / `VALIDATE CONSTRAINT`）：https://www.postgresql.org/docs/18/sql-altertable.html
- CREATE DOMAIN：https://www.postgresql.org/docs/18/sql-createdomain.html
- CREATE INDEX（表達式必須 immutable）：https://www.postgresql.org/docs/18/sql-createindex.html
- 表達式索引：https://www.postgresql.org/docs/18/indexes-expressional.html
- 生成欄位：https://www.postgresql.org/docs/18/ddl-generated-columns.html
- Release notes 16.0（`IS JSON`）：https://www.postgresql.org/docs/release/16.0/
- Release notes 18.0：https://www.postgresql.org/docs/release/18.0/
- PostgreSQL 17 Released!（SQL/JSON 查詢函式與 `JSON_TABLE`）：https://www.postgresql.org/about/news/postgresql-17-released-2936/
- pgsql-committers「indexes on virtual generated columns are not supported」：https://www.postgresql.org/message-id/E1w4zA1-001DwY-2l%40gemulon.postgresql.org
- pgsql-hackers「support create index on virtual generated column」：https://www.postgresql.org/message-id/CACJufxGao-cypdNhifHAdt8jHfK6-HX=tRBovBkgRuxw063GaA@mail.gmail.com

**pg_jsonschema**
- Repo / README：https://github.com/supabase/pg_jsonschema
- 原始碼（函式 volatility）：https://github.com/supabase/pg_jsonschema/blob/master/src/lib.rs
- 最新 release（v0.3.4, 2026-02-11）：https://api.github.com/repos/supabase/pg_jsonschema/releases/latest

**託管平台**
- Neon 支援擴充清單：https://neon.com/docs/extensions/pg-extensions
- Neon extension explorer：https://neon.com/docs/extensions/extension-explorer
- Supabase pg_jsonschema：https://supabase.com/docs/guides/database/extensions/pg_jsonschema
- Fly.io MPG 支援擴充：https://fly.io/docs/mpg/extensions/
- Railway PostgreSQL guide：https://docs.railway.com/guides/postgresql
- Render PostgreSQL extensions：https://render.com/docs/postgresql-extensions

**Python 端**
- psycopg 3 型別轉換（JSON adaptation、Numbers）：https://www.psycopg.org/psycopg3/docs/basic/adapt.html
  （該站對本次抓取工具回 403，原文取自官方 repo 原始檔：https://raw.githubusercontent.com/psycopg/psycopg/master/docs/basic/adapt.rst）
- Pydantic Unions（discriminated unions）：https://pydantic.dev/docs/validation/latest/concepts/unions/
  （`https://docs.pydantic.dev/latest/concepts/unions/` 已 301 導向此網址）

**本專案內部文件**
- `docs/spec/data-model.md`（`alert.condition jsonb` 佔位、`price numeric(20,8)`、`fee numeric(20,4)`）
- `docs/spec/tech-stack.md`（PostgreSQL、FastAPI + Pydantic、OpenAPI 自動產生）
- `docs/research/persistent-websocket-hosting.md`（託管資料庫選項與建議路徑）
- `docs/briefing/15-alerts.md`（本票既有簡報）
