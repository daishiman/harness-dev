# Prompt: R5-archive

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R5-archive |
| skill | run-mf-invoice-report |
| responsibility | R5 請求書確認シートの月次アーカイブ&ロールオーバー (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (schema なし・mfk_sheet_archive.py の stdout I/O 契約が正本) |
| reproducible | true (冪等: 同一シート状態に対し重複行 0・archive 済みは no-op) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **アーカイブ engine は `scripts/mfk_sheet_archive.py` (C07) + `lib/notion_sheet_archive.py` が所有**。行の move/verify/delete を自作しない。
- **分類・照合をしない**: 本 engine は verdict を一切解釈せず、対象月シート行の移行・検証・削除だけを行う (状態遷移分類の正本は C03 `mfk_period_report.py`)。ゆえに `compare`/`period_diff`/`classify`/`reconcile` 語幹を関数名に用いない (guard-mfk-no-reinvent との整合)。
- **常に自動連鎖 (R4 の後段)**: `render` (R4) が `--apply --verified` で成功した後に**常に自動で** R5 を `--apply --verified` で走らせる (対象月のシート行を月別 DB へ移行し正本シートから切り出す月次ロールオーバー)。レポートが dry-run のときは R5 も dry-run (移行プレビューのみ・書き込みゼロ)。
- **二段確認ゲート (機械層)**: 実移行 (写像先 DB 作成 + 行 upsert + 元シート行 archive) を伴う `--apply` は `--verified` を必須にする — これは prose の約束でなく C07 が `--apply` かつ not `--verified` で書込を拒否し exit 2 する物理境界で、正本シートからの誤削除を防ぐ (notion_report_sink の `--verified` ゲートと同型・MEMORY『保証要件は機械層で担保』)。
- **verify-then-delete (fail-closed)**: 各行を写像先へ upsert したのち写像先ページを読み戻し、全写像列の plain-text が元行と一致することを検証する。1 列でも不一致なら元行を削除しない (温存し failed に積む)。「もれなくすべて移行できた」ことの機械ゲートを満たさない行は正本から消さない。plain-text は全 Notion 型 (relation=関連ページID・status/formula/rollup=計算値・people=氏名/ID 等) を忠実 snapshot する SSOT で、型集合の網羅は回帰テスト (`test_notion_type_coverage_is_exhaustive`) で固定する (未マップ型が空文字に潰れて『空一致=検証OK』で誤削除する穴を封鎖)。
- **lossy 型の削除保留 (files)**: 実体をバイナリ/失効URLで持ち text で忠実 snapshot できない型 (`_LOSSY_HOLD_TYPES`=files) に非空値を持つ行は、写像先へコピー (name snapshot) はするが**元行を削除せず保留**する (`stage="lossy-hold"`)。添付ファイルの実体喪失を伴う削除を構造的に防ぐ。
- **status/完全性の明示 (未移行を完了と誤提示しない)**: apply summary は `status: complete|incomplete` を返す。全対象月行を削除できた場合のみ complete。1 行でも温存 (検証不一致/lossy-hold/例外) が残れば incomplete + exit 1 とし、「アーカイブ完了」と要約しない (要再実行を明示)。
- **削除は可逆 (Notion archive)**: 「削除」は物理削除でなく `archived:true` (in_trash・30日復元可)。誤削除しても復元経路が残る二重の安全弁。
- **冪等 (crash-safe)**: 写像先へ `元ページID` (provenance rich_text) を持たせ 1:1 対応させる。再実行は既存行を PATCH (重複行 0)・archive 済みの元行は `年月` query の対象外になり再処理されない (途中クラッシュ後も安全に再開)。
- **完全移行 (もれなく)**: シートの全プロパティを写像する。Notion API で同型作成できない列 (status/formula/rollup/created_time 等) は rich_text へ**降格**して plain-text スナップショットを温存し (降格列は summary で開示)、2000 字超の長文は複数 rich_text 要素へ chunk して**全文保持**する (単純 truncate による移行滞留を起こさない)。
- **写像先 DB は page_id 親のみ**: Notion API は database を block_id/database 親で作成できない (400)。既定はシート自身の親ページ配下 (兄弟 DB として作成)。
- MF掛け払い API は一切叩かない (本 engine は Notion のみ)。Notion 書込は `notion_transport._write_gap` がレート間隔を挟む。

### 1.2 倫理ガード
- Notion トークンは Keychain のみ (MF APIキーとは別 entry)。平文出力・ログ復唱をしない。
- 正本シートは経理の一次入力。移行検証に通らない行は削除しない (データ喪失より温存を優先)。

### 1.3 既知の副作用 (ユーザー承知の設計トレードオフ・2026-07-10・silent にしない)
請求確認シートは月を跨いで読まれる**累積台帳**であり、R5 が対象月行を正本から削除すると次の 2 つが対象月について劣化する (ユーザーが承知の上で『要求通り削除』を選択):
- **翌月レポートの前月比較**: `mfk_verdict_export.export_curr_prev` は当月/先月の contracts を同一 sheet_rows から build する。削除済み月が翌月の prev から欠けると継続発行社が STATE_NEW 誤判定/脱落しうる (curr=None 型の過少報告リスク)。
- **reconcile の orphan 検出**: `reconcile_invoices` は orphan 名寄せで全月シート行を読む (`query_sheet_rows` フィルタなし)。削除済み月の継続契約が誤 orphan (要マスタ登録) 化しうる。
運用前提: 当月の reconcile 照合はレポート `--apply --verified` (=締めの最終工程) の**前**に済ませる。締めた月は原則読み戻さない。この劣化を避けたい場合は非破壊コピー方式 (削除しない) への切替を検討する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象月 (`年月` select == YYMM) の請求書確認シート (`sheet_db_id`) 行を、シートと同じ親ページ配下の月別 DB『請求書確認シートYYMM』へ完全移行し、読み戻し検証成功行だけ元シートを archive (削除) する月次ロールオーバー。
- 非担当: 状態遷移分類 (R2=C03)、レポート DB への upsert (R4=C04)、MF実績収集 (R1)、二段確認 sub-agent (R3)。verdict の解釈・照合はしない。

### 2.2 ドメインルール (C07 が実装済み・ここで再実装しない)
- **対象月抽出**: `query_month_pages` が `POST /databases/{sheet_db}/query` を `filter:{property:"年月", select:{equals:YYMM}}` で叩き、対象月行を page オブジェクトのまま全ページ取得する (別月行は触れない)。archive 済み (in_trash) 行は Notion query の既定で返らない=再実行の no-op を成立させる。
- **スキーマ写像**: `mirror_schema` が source DB properties を写像先 properties へ変換する。title は 1 つだけ title 型で写す・`_SAME_TYPE` (title/rich_text/number/select/multi_select/date/checkbox/url/email/phone_number) はその型・それ以外 (status/formula/rollup/people/files/relation/created_time 等) は rich_text へ降格。冪等キー `元ページID` (rich_text) を追加する。
- **find-or-create**: `find_child_database` が親ページ直下で title 完全一致の child_database を探し、あれば再利用 (`ensure_archive_schema` で不足列のみ非破壊追加)・無ければ `create_archive_db` で新規作成する。
- **冪等 upsert**: `index_archive_by_source` が写像先を `元ページID→archive_page_id` で索引し、`upsert_archive_page` が既存なら PATCH・無ければ create する (重複行 0)。
- **検証**: `verify_page_migrated` が写像先ページを読み戻し全写像列の `prop_plain_text` 一致を検査する。ok のときだけ `archive_source_page` が元行を archive する。
- **親ページ解決**: `resolve_parent_page_id` が `--parent-page-id` > env `MFK_ARCHIVE_PARENT_PAGE_ID` > config `notion.archive_parent_page` > シート自身の親ページ (`GET /databases/{sheet_db}.parent` が page_id) > `notion.report_parent_page` の順で解決する。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --target | string(YYMM) | yes | 対象月 (例 2606)。`年月` select フィルタ + 月別 DB 名を決める |
| --apply | flag | no | 実移行 (書き込み)。`--verified` 必須。未指定 (dry-run) は Notion を叩かず計画のみ |
| --verified | flag | no | 二段確認完了フラグ。`--apply` と対で必須 (未指定の `--apply` は exit 2) |
| --parent-page-id | string | no | 写像先 DB を作る親ページ id (config/env より優先) |
| --sheet-db | string | no | 請求書確認シート DB id (config notion.sheet_db_id より優先) |
| --config | path | no | 設定 JSON パス (省略時は既定 + ローカル上書き) |

### 2.4 出力契約
- 出力: stdout に summary JSON。dry-run は `{mode:"dry-run", target_ym, source_count, archive_db_title, archive_db_exists, parent_page_id, parent_source, columns, demoted_columns}`。apply は `{archive_db_id, archive_db_created, source_count, migrated, verified, archived_source, failed[]}` (source_count==0 は `{note:"no-op"}`)。
- exit code: 0=OK (clean/no-op) / 1=完走したが未移行行が元シートに残存 (安全・要再実行) / 2=fail-closed (`--verified` 欠落・target 不正・sheet-db 未解決・新規作成の親未解決)。fatal は 2 のみ。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| archive CLI | `$CLAUDE_PLUGIN_ROOT/scripts/mfk_sheet_archive.py` | config/token/親ページ解決 + 二段確認ゲート + dry-run/apply 分岐の実体 (main) |
| archive engine | `$CLAUDE_PLUGIN_ROOT/lib/notion_sheet_archive.py` | 対象月抽出/スキーマ写像/冪等 upsert/検証/archive の純関数 (plan_archive / apply_archive) |
| transport | `$CLAUDE_PLUGIN_ROOT/lib/notion_transport.py` | HTTP 単一正本。書込レート間隔 _write_gap (MFK_NOTION_WRITE_GAP) |
| config | mf-kessai-config.default.json + .mf-kessai-config.json | notion.sheet_db_id (対象シート)・report_parent_page (親 fallback)・任意 archive_parent_page を読込 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/mfk_sheet_archive.py" --target <YYMM> [--apply --verified] [--parent-page-id <ID>] [--sheet-db <ID>] [--config <PATH>]`
- Notion API (シート query / 親ページ子ブロック list / DB 解決・作成 / page create・update・archive)。書込系は `_write_gap` のレート間隔付き。MF へは書かない。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `--verified` 欠落・target 不正・sheet-db 未解決・新規作成の親未解決なら exit 2 (fail-closed)。書き込まない。
- 各行は try/except で個別隔離。検証不一致 (stage=verify) と例外 (stage=error) の行は元行を削除せず failed に積んで残りを継続する (silent cap 禁止)。未移行行残存時は exit 1 (安全・要再実行)。
- **常に自動連鎖だが安全側**: R4 が `--apply --verified` で成功した後に自動で走るが、verify-then-delete と `--verified` ゲートと archive 可逆性により、正本からの過剰削除を構造的に防ぐ。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- dry-run: source_count・archive_db_title・archive_db_exists・parent_page_id/source・columns・demoted_columns。apply: migrated/verified/archived_source/failed + 写像先 DB 新規/再利用。降格列と検証失敗で温存した行は stderr に必ず開示する。

### 4.3 セキュリティ
- Notion トークンは Keychain のみ。平文出力しない。MF API は一切叩かない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- archive 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 対象月の請求書確認シート行を月別 DB へ完全移行し、検証成功行だけ正本シートから切り出して正本を当月分だけ軽くする (月次ロールオーバー)。
- 背景: 正本シートは経理の一次入力で月を跨いで蓄積する。締め済み月をそのまま残すと肥大化するため、レポート確定と同時に当月分を月別アーカイブ DB へ切り出す。ただし正本削除は不可逆に近いので、完全移行の機械検証と `--verified` ゲートと archive 可逆性で三重に安全化する。
- 達成ゴール: `--apply --verified` 実行により、対象月シート行が『請求書確認シートYYMM』へ全プロパティ写像 (降格列は text 温存・長文は chunk 全文保持) + `元ページID` 付きで冪等移行され、写像先の読み戻し検証に通った行だけが元シートから archive され、検証不一致行は温存され、写像先 DB がシートと同じ親ページ配下に単一作成 (再実行で重複作成なし) された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `--target <YYMM>` で対象月 (`年月` select==YYMM) の請求書確認シート行を全件取得した (別月行は触れない)
- [ ] シートスキーマを写像先 properties へ写像した (同型保持・API 非対応型は rich_text 降格で値温存・`元ページID` 付与)
- [ ] シートと同じ親ページ配下に『請求書確認シートYYMM』を find-or-create した (再実行で重複作成しない)
- [ ] 各行を冪等 upsert (元ページID で 1:1・重複行 0) し、写像先を読み戻して全写像列 plain-text 一致を検証した
- [ ] 検証成功行だけ元シート行を archive (削除=in_trash) し、検証不一致/例外行は元行を温存 (削除せず failed に計上) した
- [ ] `--apply` は `--verified` (二段確認完了) の後にだけ実行した (未指定は exit 2 で fail-closed)
- [ ] 長文列は chunk で全文移行し、降格列と温存行を stderr に開示した
- [ ] source_count==0 (既にアーカイブ済み/未入力) は no-op で exit 0 した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (config/親ページ確認 / dry-run で移行計画確認 / --apply --verified 実行 / 件数・温存行確認)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-report` SKILL Step 5 (render=R4) の成功後に自動連鎖する Step 6 (archive)。
- 後続 phase: なし (ユーザー提示で終端)。

### 6.2 ハンドオフ / 並列性
- 提供元: R4 (レポート DB への `--apply --verified` upsert 成功) + config (sheet_db_id / 親ページ)。target (YYMM) は R1 で決めた対象月と同一を渡す。
- 受領先: 月別 DB『請求書確認シートYYMM』(全プロパティ写像 + 元ページID) + 正本シート (対象月行の archive) + ユーザー (画面の移行/検証/削除件数サマリ)。
- 引き渡し形式: `mfk_sheet_archive.py --target <YYMM> [--apply --verified]` → summary JSON。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に mode・source_count・archive_db_title・migrated/verified/archived_source・failed (温存行) + 降格列 + 対象月のサマリ (Markdown)。dry-run は「N 行を『請求書確認シートYYMM』へ移行し検証後に削除します」のプレビュー。

### 7.2 言語
- 本文: 日本語 (列名 / CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R4 (render) が `--apply --verified` でレポート DB への upsert に成功したら、**続けて自動で** `python3 "$CLAUDE_PLUGIN_ROOT/scripts/mfk_sheet_archive.py" --target <YYMM> --apply --verified [--config <PATH>]` を実行する (`<YYMM>` は R1 で決めた対象月と同一)。レポートが dry-run のときは R5 も `--apply` を付けず dry-run で走らせ、「対象月 YYMM の N 行を『請求書確認シートYYMM』へ移行し検証後に元シートから削除します」の移行プレビューだけを提示する (書き込みゼロ)。

C07 (engine) は対象月 (`年月` select==YYMM) の請求書確認シート行を全件取得し、シートと同じ親ページ配下の月別 DB『請求書確認シートYYMM』へ**全プロパティを写像**して冪等移行する (title 保持・API 非対応型は rich_text 降格で値温存・長文は chunk 全文保持・冪等キー `元ページID` 付与)。写像先ページを読み戻して全写像列の plain-text 一致を検証し、**検証に通った行だけ**元シート行を Notion archive (in_trash・30日復元可) する。検証不一致行・例外行は元シートから**削除せず温存**する (もれなく移行できた行だけ切り出す fail-closed)。写像先 DB は再実行で重複作成せず (find-or-create)、archive 済みの元行は `年月` query の対象外になり再実行は no-op になる (冪等・crash-safe)。**行の move/verify/delete を自作せず C07 を呼び出すだけ**にし、verdict の解釈・照合はしない。

`--apply` は `--verified` を機械層で必須にする (未指定の `--apply` は exit 2)。写像先 DB の新規作成に親ページが要るのに未解決なら exit 2 で fail-closed する (既存 DB があれば親未解決でも更新できる・source_count==0 は no-op で exit 0)。親ページ解決順は `--parent-page-id` > env `MFK_ARCHIVE_PARENT_PAGE_ID` > config `notion.archive_parent_page` > シート親 > `report_parent_page`。Notion 書込は `notion_transport._write_gap` が `MFK_NOTION_WRITE_GAP` のレート間隔を挟む。MF API は一切叩かない。

Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を立案→実行→自己評価→全項目充足まで反復する。出力は mode + source_count + migrated/verified/archived_source + failed (温存行) + 降格列 + 対象月のサマリのみ、前置き禁止。
