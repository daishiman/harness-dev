# Prompt: R4-sink

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R4-sink |
| skill | run-mf-invoice-reconcile |
| responsibility | R4 契約マスタ/月次チェック 非破壊upsert (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/monthly-check-db.schema.json |
| reproducible | true (同一判定結果に対し同一 upsert) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- DB2 への投入は **当月 (対象年月==target) のみ**。既存行の取得 (`query_month`) は `対象年月==target_ym` でフィルタし、過去月 (対象年月≠target) は読まない・触らない。翌月以降も先月の確認済み記録が構造的に消えない (非破壊の要)。
- `人間対応済み`==true の行は **frozen で skip**。判定/AI確認済み/金額/警告/relation を一切 PATCH しない。人が確認した記録を機械が絶対に上書きしない。
- upsert キーは方向別: 順方向 title=`{契約ID}_{ym}` (キー=契約ID)、逆方向orphan title=`ORPHAN_{MF顧客ID}_{ym}` (キー=MF顧客ID)。同月再実行は title 索引で既存行を更新する (冪等)。
- DB1 契約マスタは契約ID キーで冪等 upsert (`sheet_to_master.upsert_master`)。既存は PATCH・未登録のみ POST。sync-master 段で実施済みなら省略可。
- MF掛け払い API は GET のみ。Notion 書込 (POST/PATCH/PUT/DELETE) は `notion_transport._write_gap` がレート間隔を挟む。
- DB id (db1/db2) 未設定は fail-closed (exit 2)。書き込まない。

### 1.2 倫理ガード
- Notion トークンは Keychain のみ (MF APIキーとは別 entry)。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: (a) DB1 契約マスタへ契約ID キーで冪等 upsert する (`sheet_to_master.upsert_master`。sync-master 段で実施済みなら省略可)。(b) reconcile 結果 (順方向 rows + 逆方向 orphans) の各 row に `contract_page_id` (DB1 relation) を解決し、DB2 月次発行チェックへ `notion_reconcile_sink.upsert_monthly` で**非破壊 upsert** する。(c) 判定 SoR=DB2 (forward rows) から請求確認シート各行へ『判定』(5値select) + 『AI確認』(checkbox) + 『確認ポイント』(rich_text=何を確認すべきか=action_hint SSOT + 行固有警告) を `notion_sheet_writeback.writeback` で**片方向ミラー書き戻し**する。機械が常時上書きするのはこの3列のみで、加えて空欄の『契約開始日』だけ期間由来の派生値で補完する。人間列『チェック済み』『確認内容』『取引先』『商品』は不可侵、ORPHAN はシート行なしで投影しない、契約終了月は補完しない。
- 非担当: MF実績取得 (R1)、照合判定 (R2)、二段確認 (R3)。DB1/DB2 の新規構築 (`build_reconcile_dbs.py` の責務)。

### 2.2 ドメインルール
- **当月限定**: 当月 (対象年月==target) の行だけを query・upsert する。過去月は query フィルタで構造的に触れない (翌月以降も先月の確認済み記録が消えない)。
- **確認済み凍結**: `人間対応済み`==true の行は frozen で skip。`人間対応済み`==false の当月既存行は事実列 (判定/AI確認済み/方向/金額類/件数類/MF ID/発行日/警告/契約relation) を PATCH 更新 (title と `人間対応済み` には触れない)。当月既存行なしは POST 新規作成 (`人間対応済み`=false で初期化)。
- **方向別キー**: 順方向={契約ID}_{ym} / orphan=ORPHAN_{MF顧客ID}_{ym}。orphan は契約relation 空のため (契約ID 空, 対象年月) で衝突する。方向で分岐し逆方向は MF顧客ID をキーにする。
- **改行保持**: `確認内容`/`警告` 等の rich_text は改行 (`\n`) を split せずそのまま投入する (`notion_reconcile_sink._rt`、上限 2000 字で安全に切る)。DB1 側の rich_text も `upsert_master` が改行を保持して投入する。
- **page_id 重複除去**: `query_month` (DB2) / `_existing_contract_ids` (DB1) は pagination の重複返却を page_id で dedup し、同一ページの二重 archive (HTTP400 archived) / 二重登録を防ぐ。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --target | string(YYMM) | yes | 対象月 (例 2606)。当月の対象年月ラベルにもなる |
| --apply | flag | no | 実書き込みを行う。未指定 (dry-run) は DB2 への書き込みを行わず投入対象件数のみ表示 |
| --verified | flag | sink apply時 yes | dry-run と R3 二段確認が完了済みであることを明示する。sink を含む `--apply` では未指定なら exit 2 |
| sink_rows | list | (内部) | `build_sink_rows(result, page_id_by_cid)` が reconcile 結果から整形した行 (順方向 + orphan)。`contract_page_id` は DB1 を query して契約ID→page_id で解決 (--apply 時) |

### 2.4 出力契約
- schema: `../schemas/monthly-check-db.schema.json` (DB2) / `../schemas/contract-master-db.schema.json` (DB1)。`判定` ラベル (DB2=judge_label distinct / シート=sheet_label 5値) と `AI確認(済み)` は `../schemas/verdict-mapping.json` SSOT で導出する (engine emit ⊆ mappings)。
- 出力: DB1 契約マスタへ契約ID キーで冪等 upsert (created/updated/failed) + DB2 月次チェックへ方向別キーで非破壊 upsert (created/updated/frozen/failed) + 請求確認シートへ『判定』5値+『AI確認』+『確認ポイント』書き戻し (判定列状態/更新行数/failed) + 画面に投入件数 (dry-run は contract_page_id 解決件数を含む投入対象件数) サマリ。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| orchestrator | `$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py` | --apply 実行時 (sink step は build_sink_rows + upsert_monthly を配線) |
| DB2 sink lib | `$CLAUDE_PLUGIN_ROOT/lib/notion_reconcile_sink.py` | DB2 非破壊 upsert の実体 (query_month / upsert_monthly) |
| DB1 sink lib | `$CLAUDE_PLUGIN_ROOT/lib/sheet_to_master.py` | DB1 冪等 upsert + 契約ID→page_id 解決 (upsert_master / _existing_contract_ids) |
| transport | `$CLAUDE_PLUGIN_ROOT/lib/notion_transport.py` | HTTP 単一正本。書込レート間隔 _write_gap (MFK_NOTION_WRITE_GAP) |
| schema | ../schemas/monthly-check-db.schema.json / ../schemas/contract-master-db.schema.json / ../schemas/verdict-mapping.json | プロパティ名・判定ラベル SSOT |
| config | .mf-kessai-config.json | notion.{reconcile_db1_id,reconcile_db2_id} 読込 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py" --target <YYMM> --apply --verified` (全 steps。`--steps sink` 単独は reconcile 依存で不可)。
- Notion API (DB query / page create / page update)。書込系は `_write_gap` のレート間隔付き。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- DB id (db1/db2) 未設定なら停止し fail-closed (exit 2)。どの id が欠落かを明示し書き込まない。
- 各行は try/except で個別隔離。1 行の HTTP400/timeout を failed に計上して残りを継続する (silent cap 禁止)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- DB1: created/updated/failed 件数 (失敗は契約ID と error を stderr へ可視化)。
- DB2: created/updated/frozen/failed 件数 + dry-run 時は contract_page_id 解決件数を含む投入対象件数。

### 4.3 セキュリティ
- Notion トークンは Keychain のみ。平文出力しない。MF API は GET のみ (本 sink から POST/PATCH/DELETE を MF へ発行しない)。

### 4.4 管理列不可侵 / 履歴非破壊 (CONST)
- `AI確認済み` checkbox は **AI管理列**。`verdict-mapping.json` の `ai_check=true` だけ true とし、発行漏れ・要確認・orphan は false。
- `人間対応済み` checkbox は **人間専用 managed 列**。AI は読むだけで書かない (frozen 判定の入力に使う)。機械は新規作成時のみ `人間対応済み`=false で初期化し、以後この列に触れない。
- DB2 への upsert は当月 (対象年月==target) のみ。過去月は `query_month` のフィルタ対象外なので PATCH/POST/archive を一切受けない (履歴不変の主担保)。
- `期待金額` は判定時にスナップショット凍結し再計算しない (マスタ後編集で過去月が変わらない)。
- Notion 書込 (POST/PATCH/PUT/DELETE) は `notion_transport._write_gap` が `MFK_NOTION_WRITE_GAP` (既定 0.34 秒) のレート間隔を成功直後に挟む (一括投入のレート制限回避)。GET には間隔を入れない。page_id 重複除去で二重 archive を防ぐ。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- sink 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 契約マスタ DB1 と月次チェック DB2 を当月分のみ非破壊 upsert し、過去月の確認済み履歴と `人間対応済み` を保全する。
- 背景: 全消し再投入や過去月への波及・管理列上書きは運用を壊す (反面教師=archive_all で DB2 を全消ししていた旧 load_db2.py)。当月限定 query + 確認済み凍結 + 方向別キー + 書込レート間隔を機構で固定する。
- 達成ゴール: command 実行により各 row に contract_page_id (DB1 relation) が解決され、DB2 へ方向別キーで当月行が非破壊 upsert され (過去月不可侵・AI確認済み更新・人間対応済み凍結・改行保持)、DB1 契約マスタが契約ID キーで冪等 upsert され、Notion 書込にレート間隔が挟まれた状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] DB1 契約マスタを契約ID キーで冪等 upsert した (既存=PATCH / 未登録=POST。sync-master 済みなら省略可)
- [ ] 各 row に contract_page_id (DB1 relation) を解決した (DB1 を query して契約ID→page_id)
- [ ] DB2 へ方向別キー (順方向={契約ID}_{ym} / orphan=ORPHAN_{MF顧客ID}_{ym}) で当月行を非破壊 upsert した
- [ ] 過去月 (対象年月≠target) の行に触れていない (当月限定 query)
- [ ] `人間対応済み`=true の行を凍結 (skip) した
- [ ] `AI確認済み` が verdict-mapping.json の `ai_check` から派生している
- [ ] `確認内容`/`警告` の改行 (`\n`) を保持して投入した
- [ ] DB2 upsert に failed が無い場合、請求確認シート各行へ『判定』(5値=sheet_label) + 『AI確認』 + 『確認ポイント』(action_hint+警告) を片方向ミラー書き戻しした (forward rows のみ・ORPHAN 投影せず。保留/未締結は REVIEW_PENDING として要確認投影。frozen 行は DB2 を上書きしないが、シートの現在判定/確認ポイント投影は継続)
- [ ] シート書き戻しで人間列『チェック済み』『確認内容』『取引先』『商品』と『契約終了月』に触れていない (機械は『判定』『AI確認』『確認ポイント』3列を常時 PATCH し、空欄の『契約開始日』だけ派生補完)
- [ ] Notion 書込にレート間隔 (MFK_NOTION_WRITE_GAP) を挟んだ / page_id 重複除去で二重 archive を防いだ
- [ ] DB id (db1/db2) 未設定なら exit 2 で fail-closed した
- [ ] DB1/DB2 の created/updated/frozen/failed 件数 + シート書き戻し件数を画面に表示した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (config/DB id 確認 / dry-run で投入対象確認 / --apply 実行 / 件数確認)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-reconcile` SKILL Step 5 (sink)。R3 で誤検出を排除した reconcile 結果が入力。
- 後続 phase: なし (ユーザー提示で終端)。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (順方向 rows + 逆方向 orphans) + R3 (誤検出排除済み)。DB1 (契約ID→page_id 解決) / `verdict-mapping.json` (judge_label 導出)。
- 受領先: DB1 契約マスタ (契約ID キー冪等 upsert) + DB2 月次チェック (方向別キー非破壊 upsert) + ユーザー (画面の件数サマリ)。
- 引き渡し形式: `build_sink_rows(result, page_id_by_cid)` → `notion_reconcile_sink.upsert_monthly(sink_rows, db2, target, token)`。DB1 は `sheet_to_master.upsert_master(contracts, db1, token)`。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に DB1 (created/updated/failed) + DB2 (created/updated/frozen/failed) 件数 + 対象年月のサマリ (Markdown)。dry-run は投入対象件数 + contract_page_id 解決件数。

### 7.2 言語
- 本文: 日本語 (列名 / CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`python3 "$CLAUDE_PLUGIN_ROOT/scripts/reconcile_invoices.py" --target <YYMM> --apply --verified` を実行する (全 steps。`--steps sink` 単独は reconcile 依存で不可)。`--verified` は dry-run と R3 二段確認が完了したことを示す物理ゲートで、未指定なら sink を含む apply は exit 2 で停止する。

DB1 契約マスタは `sheet_to_master.upsert_master` で契約IDキーの冪等 upsert を行う。DB2 月次発行チェックは `notion_reconcile_sink.upsert_monthly` で当月行だけを方向別キー (順方向=`{契約ID}_{ym}` / orphan=`ORPHAN_{MF顧客ID}_{ym}`) により非破壊 upsert する。過去月は query 対象外、`人間対応済み`=true は frozen skip、更新時は nullable な事実列を明示クリアして前回の MF 証跡や警告を stale に残さない。

判定ラベルと `AI確認済み` は `../schemas/verdict-mapping.json` SSOT から導出し、別表記・別条件を作らない。DB2 upsert に failed が無い場合、判定 SoR=DB2 から請求確認シート各行へ `notion_sheet_writeback.writeback` で『判定』(5値=sheet_label) + 『AI確認』 + 『確認ポイント』を片方向ミラー書き戻しする。`確認ポイント` は `AIの確認OK` のみ空、対象外/要確認/発行漏れは `action_hint + warning` を書く。取消では status/取消日時/取消前金額、0円取消では status/商品名由来の取消状態が警告・確認ポイントに残る。**`対象外` (契約終了/前払い/単発/off-cycle) でも当月境界に取消があれば engine の `cancellation_note` が `warning` へ取消注記を併記し、`compose_note` が `{hint}（{warning}）` で対象外行の確認ポイントへ取消理由を出す** (verdict/sheet_label は据え置き=WARN-not-FAIL・書き戻し層は不改修)。人間列『チェック済み』『確認内容』『取引先』『商品』と『契約終了月』は不可侵、空欄の『契約開始日』だけ派生補完できる。ORPHAN は投影しない。保留/未締結契約は `REVIEW_PENDING` として『判定=要確認』に投影し、理由を『確認ポイント』へ書く。frozen 行は DB2 を上書きしないが、シートの現在判定/確認ポイント投影は継続する。

DB1/DB2 が未構築なら `scripts/build_reconcile_dbs.py` (冪等 find-or-create) で用意する。MF API は GET のみ。Notion 書込は `notion_transport._write_gap` が `MFK_NOTION_WRITE_GAP` のレート間隔を挟む。DB id 未設定なら exit 2 で fail-closed する。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を立案→実行→自己評価→全項目充足まで反復する。出力は DB1/DB2 の created/updated/frozen/failed 件数と対象年月のサマリのみ、前置き禁止。
