# Prompt: R4-render

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R4-render |
| skill | run-mf-invoice-report |
| responsibility | R4 月次レポートDBへ非破壊冪等upsert (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (schema なし・notion_report_sink.py の stdout I/O 契約が正本) |
| reproducible | true (同一分類結果に対し同一 upsert) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **DB 構築/配置/冪等 upsert は `scripts/notion_report_sink.py` (C04) が所有**。DB 生成・行 upsert を自作しない (DB 生成は build_notion_db 再利用・行 upsert は C04 が実体)。
- レポート DB は**単一恒久 DB (Design D + 明示 pin・要件2 2026-07-10)**。出力先は **(step0) 明示 pin `notion.report_database_id` (set ならその DB へ直接=構造同定を経ず確実に着地・ビュー/DB URL 可)** を最優先し、未設定時のみ指定トグル (`report_toggle_block`) 内の report DB → 見出しの下 (ページ直下) の既存 DB の順で解決してそこへ複数月を `対象月` 列付きで非破壊 upsert する。**明示 pin なし かつ 既存 DB 未発見時は phantom を作らず fail-closed (exit 2) で停止し、新規作成は `--allow-create` opt-in 時のみ** (構造同定のズレで別 DB=phantom へ書き込みチェックが本来 DB に反映されない症状の根治)。
- **非破壊マージ**: 同月再実行は入力同定 {取引先 × 契約ID × 商品} と stored key (対象月, 取引先名, 商品名) で同一行を 1 行へ収束 (重複行 0)。契約ID違いは要対応優先で collapse し `collapsed_multi_contract` に計上する。以前 run で書いた行も別月行も今回入力に無くても単一 DB から削除しない (`deleted` 常時 0・clear-then-insert でない)。
- **collapse 発行済み実額保全 (C03・要因C5 sink側)**: 固定 8 列は (対象月,取引先名,商品名) で回収するため、代理店/複数エンドクライアントが 1 商品へ複数契約を持つと 1 行へ collapse する。このとき `_prefer_action`/`_preserve_issued_amount` (C03) が **要対応 severity を保持して漏れを隠さない一方、発行済み (reliable_issued=True) 行の実額 (今月金額) を要対応・null 行で上書きさせず保全**する (発行済み実額保全 ∧ 漏れ隠蔽なし=K4 権威訂正の対称適用)。保全した旨と別契約の要対応は `コメント` へ両立注記する。冪等 upsert 骨格そのものは不変。
- **列順 SSOT (固定 8 列)**: [取引先名(title), 対象月(rich_text), 漏れチェック(checkbox), 商品名(rich_text), 先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text), コメント(rich_text)]。金額は税抜。C04 の `COLUMN_ORDER` が正本。Notion table view は title 列を最左固定にするため、取引先名(title)を先頭に置いて定義順と表示順を一致させる。漏れチェックは checkbox で 正常=チェックあり / 要対応=チェックなし。
- **金額列は MF実額 (D3=金額列常時表示・C9=既存 8 列互換)**: `先月の金額`/`今月の金額` には **MF実額** (C05 `mfk_actuals` が返す `actual_amount`=契約起点の期待額でなく MF 掛け払いの実発行額) を入れる。金額差フラグ・期待額差分・残置理由 (旧行 orphan) は**新しい物理列を足さず** `先月と今月の比較`/`コメント` に文字で書く (固定 8 列スキーマを保つ)。これにより金額列は常に表示され (D3)、8 列互換のまま冪等 sink が成立する (C9)。
- **折り返し (wrap) は API 非対応=UI で一度設定**: 全列の折り返し表示 (wrap) はビュー表示設定であってプロパティ設定でないため、Notion 公開 API (2022-06-28) では設定できない (列順は properties 定義順で反映できるが wrap/列幅は不能)。sink はこの制約と UI 手順を `placement.view_format_note` で毎回開示する。Notion UI で当該 DB ビューの『…』→『すべての列を折り返す (Wrap all columns)』を一度トグルすれば以後永続する。
- MF掛け払い API は GET のみ。Notion 書込 (POST/PATCH/PUT/DELETE) は `notion_transport._write_gap` がレート間隔を挟む。
- **出力先未確定は fail-closed (要件2)**: 明示 pin (`notion.report_database_id`) があれば親ページ不要でその DB へ直接 upsert する。明示 pin なし かつ 親ページ ID (`notion.report_parent_page`) 未設定は `--apply` 時に fail-closed (exit 2)。明示 pin なし かつ 既存 DB 未発見時も phantom を作らず fail-closed (exit 2)=新規作成は `--allow-create` opt-in 時のみ。dry-run は書込ゼロで完走し placement に `report_database_id` (pin) を開示する。`report_toggle_block` は歴史的なキー名だが Design D では**出力先の指定見出しブロック ID**で、トグル見出しでもプレーン見出し2でも受ける。C04 は明示 pin を最優先し、無ければこのブロック内/直下の既存 report DB を探す (opt-in 時のみ親ページ直下に新規作成)。

### 1.2 倫理ガード
- Notion トークンは Keychain のみ (MF APIキーとは別 entry)。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: R2 (C03) の分類済みレポート行を C04 (`notion_report_sink.py`) に渡し、指定見出しに紐づく単一恒久レポート DB を解決して 8 列行を**非破壊冪等 upsert** する。R3 で差し戻し (reinstate) があれば上流是正→再分類後の行を渡す。
- 非担当: MF実績・verdict 収集 (R1)、状態遷移分類 (R2=C03)、二段確認 (R3 sub-agent)。DB スキーマ定義・列型写像は C04/build_notion_db の責務。

### 2.2 ドメインルール (C04 が実装済み・ここで再実装しない)
- **出力先 DB 解決 (Design D + 明示 pin・要件2)**: `resolve_report_db` が **(step0) 明示 pin `notion.report_database_id` (set ならその DB へ直接=`db_location=pinned`)** を最優先し、未設定時のみ指定見出し (`report_toggle_block`・トグル/プレーン見出し2 両対応) を起点に (1) 見出しがトグルで配下に持つ child_database → (2) プレーン見出しの直下 (ページ兄弟・次セクション見出しの手前まで=見出しの下の DB を重複と区別して同定) → (3) ページ直下で title が『請求漏れ比較レポート』で始まる既存 report DB → **(4) 明示 pin なし かつ 既存未発見時は phantom を作らず fail-closed で停止 (新規作成は `--allow-create` opt-in 時のみ見出しの下=ページ直下)**、の順で解決し `db_location` (pinned/in-block/under-heading/page/page-created) を開示する。**(1)(2) の指定トグル/見出しはレポート専用の器ゆえ配下 DB を表示名非依存で採用する** (ユーザーが『請求漏れ確認レポート』等どんな名前で手作りしても既存として更新=title 前方一致は同点解消/後方互換ヒントに留め、複数併存時のみ prefix 一致→先頭で決定論選択し警告)。(3) の親ページ直下だけは無関係 DB が同居しうるので title 前方一致で限定。既存 DB の title 列名が『取引先名』でなく Notion 既定の『名前』でも `_ensure_db_schema` が実名を検出し行を正しい列へ書く。Notion API は database を block_id 親で作成できないが、UI 作成の DB の更新 (行 upsert・列 PATCH) は親種別に関係なくできる。
- **対象月列で複数月を保持**: 単一 DB に `対象月` (YYYY-MM) 列を持ち、行同定キー (対象月, 取引先名, 商品名) で同月のみ上書き・別月は非破壊共存。対象月列が無い旧 DB は `_ensure_db_schema` が PATCH で後付けする。
- **入力同定と persist**: 入力行の同定は {取引先 × 契約ID × 商品}。ただし固定 8 列に契約ID 列は無く、単一 DB 内の 1 行は (対象月, 取引先名, 商品名) で回収される (contract_id は persist しない=C04 の `_stored_key`)。同一対象月・同一取引先・同一商品は要対応優先で 1 行へ収束し、契約ID違いの collapse は stdout の `collapsed_multi_contract` で観測する。
- **非破壊 upsert**: 既存行あり→PATCH (title は送らない)・無し→POST。入力に無い nullable 事実列は明示クリアして stale を残さないが、行そのものは削除しない (非破壊マージ)。各行は try/except で隔離し個別失敗は skipped に計上して継続する。
- 取引先名 (title) が空の行は skip する (title 必須)。
- **reliable MF実額による cross-run 訂正**: reliable な MF 実発行 (C05 `mfk_actuals` 由来の `actual_amount`) が今 run で確認できた行は、前 run で要対応☐だった同一行 (対象月, 取引先名, 商品名) を今 run で正常☑へ訂正する。実装は C04 側で、R4 は分類済み行を渡すだけ。
- **真 orphan 行の残置注記**: 今回入力に無いが過去 run が書いた行 (真 orphan) は削除せず (deleted 0)、`コメント` に残置理由を注記して残す。これも C04 が実装し R4 は呼ぶだけ。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --rows | path(JSON) | yes | C03 の分類済みレポート行 JSON list |
| --target | string(YYMM) | yes | 対象月 (例 2606)。単一 DB 内の行同定キーになる |
| --apply | flag | no | 実書き込みを行う。未指定 (dry-run) は Notion を叩かず計画のみ返す |
| --config | path | no | 設定 JSON パス (省略時は既定 + ローカル上書き) |

### 2.4 出力契約
- 出力: stdout に upsert 結果 JSON `{created, updated, skipped, deleted(=0), collapsed_multi_contract, report_db_id, db_location, db_created, placement}`。`db_location` = in-block/under-heading/page/page-created (出力先の解決結果)。dry-run は `dry_run:true` + `planned_rows`。
- exit code: 0=OK / 1=部分失敗 (行 skip) / 2=fail-closed (target 不正・親ページ未設定・rows 不正)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| sink engine | `$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py` | Design D の出力先 DB 解決 + 非破壊冪等 upsert の実体 (run / resolve_report_db / upsert_report_rows) |
| DB builder | `$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py` | DB 生成・列型写像 (build_property) の再利用元 |
| transport | `$CLAUDE_PLUGIN_ROOT/lib/notion_transport.py` | HTTP 単一正本。書込レート間隔 _write_gap (MFK_NOTION_WRITE_GAP) |
| config | tenant overlay + .mf-kessai-config.json | notion.report_toggle_block (Design D: 出力先トグル=最優先の更新対象 DB の在り処) + report_parent_page (トグル内に DB が無いときの探索/新規作成先ページ) を読込 (配布既定は ID 空で fail-closed) |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py" --rows <ROWS> --target <YYMM> [--apply] [--config <PATH>]`
- Notion API (指定見出し/親ページ子ブロック list / DB 解決・作成 / page create/update)。書込系は `_write_gap` のレート間隔付き。MF へは書かない。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- target 不正・親ページ ID 未設定・rows 不正なら C04 が exit 2 (fail-closed)。書き込まない。
- 各行は try/except で個別隔離。1 行の HTTP400/timeout を skipped に計上して残りを継続する (silent cap 禁止)。
- **skill 層のゲート**: report DB 反映を含む `--apply` は dry-run と R3 二段確認が完了済みであることを示す `--verified` を skill が要求する (誤投入防止)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- created/updated/skipped/deleted(=0) 件数 + collapsed_multi_contract + report_db_id + db_location + db_created + placement。dry-run は planned_rows。

### 4.3 セキュリティ
- Notion トークンは Keychain のみ。平文出力しない。MF API は GET のみ (本 sink から MF へ POST/PATCH/DELETE を発行しない)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- render 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 分類済みレポート行を単一恒久レポート DB へ非破壊冪等 upsert し、対象月列で月次履歴を保全する。
- 背景: 全消し再投入や別 DB 乱立は履歴と運用導線を壊す。指定見出しに紐づく既存 DB 優先の解決 + 非破壊マージ (deleted 0) + 対象月を含む stored key 収束 (重複行 0) を機構で固定する。
- 達成ゴール: command 実行により、明示 pin (`notion.report_database_id`) があればその DB へ直接、無ければ既存レポート DB を解決してそれを更新し (明示 pin なし かつ 既存未発見時は phantom を作らず fail-closed=新規作成は `--allow-create` opt-in 時のみ)、8 列行が入力同定 {取引先×契約ID×商品} と stored key (対象月,取引先名,商品名) で 1 行へ収束して非破壊 upsert され、別月/以前行が保全され、Notion 書込にレート間隔が挟まれた状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] R2 の分類済みレポート行 JSON を `--rows` に渡し `--target <YYMM>` を指定して C04 を実行した
- [ ] 出力先 DB を解決した (明示 pin `report_database_id` があればその DB へ直接=step0 / 無ければ指定見出しに紐づく既存 report DB を更新対象にする / 明示 pin なし かつ 既存未発見時は phantom を作らず fail-closed=新規作成は `--allow-create` opt-in 時のみ・二重 DB を作らない)
- [ ] 8 列行を入力同定 {取引先×契約ID×商品} と stored key (対象月,取引先名,商品名) で 1 行へ収束させ非破壊冪等 upsert した (重複行 0・deleted 0・契約ID違いは `collapsed_multi_contract` に計上)
- [ ] 月跨ぎでは同一 DB 内に対象月列で別月行が共存し、以前月/以前 run の行が保全された
- [ ] 取引先名 (title) 空の行を skip した / 個別失敗を skipped に計上して継続した
- [ ] 明示 pin なし かつ 親ページ ID 未設定なら `--apply` 時に exit 2 で fail-closed した (明示 pin ありなら親ページ不要)。明示 pin なし かつ 既存 DB 未発見時も phantom を作らず exit 2 で停止した (`--allow-create` 未指定時)
- [ ] `--apply` は dry-run と R3 二段確認完了 (--verified 相当) の後にだけ実行した
- [ ] created/updated/skipped/deleted + report_db_id + db_location + placement を画面に表示した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (config/親ページ ID 確認 / dry-run で計画確認 / --apply 実行 / 件数確認)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-report` SKILL Step 4 (render)。R3 で二段確認した分類済みレポート行が入力。
- 後続 phase: R5 archive (`prompts/R5-archive.md`・C07)。`--apply --verified` でレポート DB への upsert に成功したら、続けて自動で `mfk_sheet_archive.py --target <YYMM> --apply --verified` を走らせ対象月シート行を月別 DB へ切り出す (レポート dry-run では R5 も dry-run)。render が dry-run/失敗のときは archive へ連鎖しない。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (C03 分類済みレポート行) + R3 (二段確認・差し戻し反映済み)。config (report_parent_page / report_toggle_block 論理キー)。
- 受領先: 単一恒久レポート DB (対象月列付き 8 列行を非破壊冪等 upsert) + ユーザー (画面の件数・placement サマリ)。
- 引き渡し形式: `notion_report_sink.py --rows <ROWS> --target <YYMM> [--apply]` → upsert 結果 JSON。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に created/updated/skipped/deleted(=0) 件数 + collapsed_multi_contract + report_db_id + db_location + db_created + placement + 対象月のサマリ (Markdown)。dry-run は planned_rows。

### 7.2 言語
- 本文: 日本語 (列名 / CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R2 の分類済みレポート行 JSON をファイルに用意し、`python3 "$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py" --rows <ROWS> --target <YYMM> [--apply] [--config <PATH>]` を実行する。既定は dry-run (Notion を叩かず計画のみ)。単一恒久レポート DB 反映を含む `--apply` は、dry-run と R3 二段確認が完了済みであることを skill が `--verified` で確認した後にだけ使う (誤投入防止)。

C04 (Design D) は出力先 DB を `resolve_report_db` で解決する: (1) 指定見出し (`report_toggle_block`) がトグルならその中の report DB → (2) プレーン見出しならその直下 (ページ兄弟・次セクション手前) の report DB → (3) 親ページ (`report_parent_page`) 直下の既存 report DB → (4) 見出しの下 (ページ直下) へ新規作成。そこへ 8 列行 (取引先名=title/対象月/漏れチェック=checkbox/商品名/先月の金額/今月の金額/先月と今月の比較/コメント・金額税抜・列順固定) を行同定キー (対象月, 取引先名, 商品名) で **非破壊冪等 upsert** する。`先月の金額`/`今月の金額` は MF実額 (C05 `mfk_actuals` 由来の実発行額・期待額でない)、金額差フラグ/期待額差分/残置理由は物理列を足さず `先月と今月の比較`/`コメント` に書く (固定 8 列を保つ=D3/C9)。reliable MF実額が確認できた行の cross-run 訂正 (前 run 要対応☐→今 run 正常☑) と真 orphan 行の残置注記 (削除せず `コメント` に理由) は C04 が実装するので R4 は行を渡すだけにする。同月再実行は同一行を 1 行へ収束 (重複行 0)、別月は非破壊共存、契約ID違いは要対応優先で collapse し `collapsed_multi_contract` に計上する。以前 run の行も別月の行も今回入力に無くても削除しない (deleted 常時 0)。対象月列が無い旧 DB は `_ensure_db_schema` が PATCH で後付けする。**DB 解決・行 upsert を自作せず C04 を呼び出すだけ**にする。

親ページ ID が未設定なら `--apply` 時に exit 2 で fail-closed する (dry-run は完走)。Notion 書込は `notion_transport._write_gap` が `MFK_NOTION_WRITE_GAP` のレート間隔を挟む。Notion API は database の親に block_id を許容しないため、新規作成だけはページ直下になる。既存 DB が指定見出しの中/直下にあれば、その DB を更新する。

Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を立案→実行→自己評価→全項目充足まで反復する。出力は created/updated/skipped/deleted 件数 + collapsed_multi_contract + report_db_id + db_location + placement + 対象月のサマリのみ、前置き禁止。
