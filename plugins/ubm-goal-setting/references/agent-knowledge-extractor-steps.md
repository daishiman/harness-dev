# knowledge-extractor の実行手順（Step 0〜5）

`agents/knowledge-extractor.md` の「思考プロセス」の正本。knowledge-extractor は処理を始める前にこのファイルを Read し、`mode` 別の順序で実行する。各フェーズの要約と完了条件は `agents/knowledge-extractor.md` の Layer 6「実行フロー」の表と同じ。Rule A〜F の本文は `${PLUGIN_ROOT}/references/agent-knowledge-extractor-rules.md`、エントリの書き方と出力テンプレートは `${PLUGIN_ROOT}/references/agent-knowledge-extractor-entry-format.md` にある。ここで `knowledge/` と書くのは、親が渡した一時 `knowledge_dir` のコピーを指す。

## Step 0: `mode` の決定（必須・最初に実行）

`detect-knowledge-updates.py` 出力の先頭フィールドから `mode` を決定する:

```
入力形式: {STATUS}|{source_type}|{file_hash}|{file_path}
STATUS = NEW      → mode: "new"（新規ファイル：registry.json に未登録）
STATUS = MODIFIED → mode: "update"（更新ファイル：ハッシュ変化あり）
```

利用者自身の記録（`05_Project/UBM/目標設定/`・`05_Project/UBM/挑戦宣言/`）は、`detect-knowledge-updates.py` が検知の段階で除くので、この入力には現れない。除外の正本は同スクリプトの `EXCLUDED_SUBDIRS` で、このエージェントの側で行を除く手順は持たない。

**`mode` 別の完全実行フロー（必ずこの順序で実行）:**

```
mode: "new"
  → Step 1（読み込み）→ Step 2（抽出）→ Step 3（格納）→ Step 4（更新）→ Step 5（DB同期）

mode: "update"
  → Rule F Step U-1（registry.json 確認）
  → Rule F Step U-2（既存エントリ全削除・3ケース分岐）
  → Rule F Step U-3（Step 1→2→3 を実行）
  → Rule F Step U-4（registry.json 更新）
  → Step 5（DB同期）
  ※ Step 3 単独を実行してはいけない。必ず Rule F Step U-1〜U-4 を完結させること

mode: "full"
  → Rule F Step F-1〜F-3（全リセット）
  → 全ファイルを mode: "new" として順次処理
```

**ハッシュ変化なし（検知の出力に含まれないファイル）は処理しない。**

## Step 1: ファイル読み込みと分類

1. 対象ファイルの種別を判定:
   - `YouTube/` → YouTube議事録
   - `合宿/` → 合宿記録
   - `月報フィードバック/` → 月報FB
   - `動画教材/` → 公式教材
   - UBMルート直下 → セミナー・イベント記録

2. ファイルサイズに応じた読み込み戦略: `agents/knowledge-extractor.md` の Layer 4「ファイルサイズ別読み込み戦略」に従う（5万文字以下は全文、5万文字以上は先頭200行で構造把握 → 見出し一覧取得 → 関連セクションのみ精読）。

YouTube議事録は2-9万文字と大型。以下の戦略で効率的に処理する:

```
全文 (2-9万文字)
  ↓ Bash: grep -n '^#' で見出し一覧取得（そのソース1ファイルだけ）
見出し一覧 (20-50行)
  ↓ キーワードマッチで関連セクション特定
関連セクション (3-10個)
  ↓ Read(offset, limit) で精読
抽出されたエントリ (カテゴリ別にJSON変換)
  ↓ Rule A で決めた knowledge/{category}-{subtopic}.json に追記
```

## Step 2: 知識抽出とJSON変換

`${PLUGIN_ROOT}/references/agent-knowledge-extractor-entry-format.md` を Read し、その「抽出の最重要原則」「ナレッジ化の核心原則」「抽出時に必ず問いかける6つの問い」に沿って各ファイルから知識を抽出する。エントリは同じファイルの「出力テンプレート（標準・全カテゴリ共通）」の形で作り、「各フィールドの抽出ルール」と「カテゴリ別の追加フィールド」（`consultation`・`mindset`）を満たす。`background`・`intent`・`root_cause`・`expected_outcome` が揃っていない抽出は不完全とみなす。

## Step 3: JSONファイルへの格納

**`mode: "update"` の場合の前提確認**:
Rule F の Step U-1〜U-2（対象ファイルの既存エントリ全削除）が完了していることを確認。
削除完了後は重複チェック（手順2）は不要。削除が済んでいない場合は必ず先に実行すること。

**格納先ファイルの決定 → Rule A に従う**（毎回必ず実行）:

```
Rule A を実行:
  1. router.json の routing_rules[category] を Read
  2. entry.tags と各ルールの tags の共通要素数でスコアを計算
  3. 最大スコアのファイルを格納先に決定（タイ→エントリ数多い方、全0→default:true）
```

1. 格納先ファイルが存在しない場合は `schema.json` に準拠した構造で新規作成
2. 重複チェック: 同じ `content` のエントリが既存の場合は `source` を追記するのみ
3. エントリの `id` を **Rule C（ID採番アルゴリズム）** に従って採番
4. `entries` 配列に新エントリを追加し `entry_count` を更新して Write で保存
5. `router.json` を **Rule D（更新順序）** に従って更新

**成長による新サブトピックファイル作成**（エントリ数が25を超えた場合）:

   対象ファイルのエントリが25件を超え、さらに新しいサブテーマが明確になった場合:

   ```
   Step 3-A: 対象ファイルのエントリをテーマ別にグループ化
     → 各エントリのtags・content・backgroundを読み、共通テーマを特定する
     → グループ例: relationship/organization/marketing/hiring/mindset/product...

   Step 3-B: 新サブトピック名を決定（命名規則に従う）
     ◎ ファイル名だけで「どんな悩みを持つユーザー向けか」が分かること
     ◎ 形式: 既存ファイルの分割は {category}-{existing_topic}-{new_subtopic}.json（router.json の growth_rules.new_file_naming）
     ◎ 例: consultation-organization.json → consultation-organization-hiring.json
     絶対NG: -1/-2 などの連番、-a/-b などのアルファベット連番

   Step 3-C: 新サブトピックファイルを knowledge/ に Write で作成

   Step 3-D: router.json の routing_rules と files リストを更新
     → 新ファイルに対応する routing_rules エントリを追加（tags と default を設定）
     → categories[category].files に新ファイルを追加
   ```

   **サブトピック命名サンプル**:
   | カテゴリ | サブトピック例 |
   |---------|--------------|
   | `principles` | `relationship`, `business-growth`, `mindset`, `action`, `trust` |
   | `consultation` | `organization`, `sales`, `marketing`, `client-acquisition`, `product` |
   | `phase-advice` | `0to1`, `1to10`, `10to100`, `startup`, `scaling` |
   | `action-guides` | `daily-routine`, `networking`, `follow-up`, `content` |
   | `mindset` | `fear`, `perfectionism`, `comparison`, `self-worth` |
   | `case-studies` | `tax-accountant`, `freelance`, `growth-success`, `failure` |

## Step 4: ルーターとレジストリの更新

1. `knowledge/router.json` を更新（以下の全フィールドを必ず更新する）:

   **エントリ追加のたびに更新するフィールド**:
   - `last_sync`: 現在日付（`YYYY-MM-DD`）
   - `total_entries`: 全サブトピックファイルのエントリ数の合計を再集計
   - `categories[category].entry_count`: そのカテゴリの全ファイルのエントリ数合計
   - `categories[category].subcategory_counts[格納先ファイル名]`: +1 インクリメント

   **新サブトピックファイルを作成した場合のみ追加更新**:
   - `categories[category].files`: 新ファイル名を配列に追加
   - `categories[category].subcategory_counts[新ファイル名]`: 初期値として現在のエントリ数を設定
   - `routing_rules[category][新ファイル名]`: 新ルールを追加（`topic`・`tags`・`default` を設定）
     - `default`: そのカテゴリの他のファイルに `default: true` が既にある場合は `false`
     - `tags` にはエントリの `tags` から代表的なキーワードを選定する

2. `knowledge/sync-log.jsonl` に実行ログを**追記**（上書き禁止・永続ログ）:

   `idempotency_key = sha256(mode + "|" + source_file + "|" + file_hash)` を各行に必須記録する。追記前に既存行を読み、同じキーがあれば追記しない。これにより `registry.json` の確定より前の再実行でログが重複しない。

   **通常ログ（正常完了）:**
   ```json
   {"timestamp":"YYYY-MM-DDTHH:MM:SS","idempotency_key":"sha256:<hex>","file_hash":"<md5>","mode":"new|update|full","source_file":"ファイルパス","added":["PR-013","CP-007"],"deleted":[],"warnings":[],"categories_updated":["principles","consultation"]}
   ```

   **警告ログ（異常あり・処理は続行）:**
   ```json
   {"timestamp":"YYYY-MM-DDTHH:MM:SS","idempotency_key":"sha256:<hex>","file_hash":"<md5>","mode":"update","source_file":"ファイルパス","added":["PR-015"],"deleted":["PR-010"],"warnings":["ID PR-011: not found in any knowledge file (already deleted?)","Case C: 残存エントリ2件を修復削除した"],"categories_updated":["principles"]}
   ```

   - ファイルが存在しない場合は新規作成（1行目から追記）
   - 1回の実行でファイルが複数ある場合は、ソースごとに一意なキーで1行ずつ追記
   - `warnings` が空 `[]` の場合は正常完了。`warnings` があっても処理は続行する

   **`warnings` フィールドの記録ルール:**
   | 状況 | `warnings` に記録する内容 |
   |------|----------------------|
   | Case A で ID が見つからなかった | `"ID {id}: not found in any knowledge file"` |
   | Case A で削除件数 ≠ `extracted_entry_ids.length` | `"削除件数不一致: expected {N}, actual {M}"` |
   | Case C で残存エントリが発見された | `"Case C: {N}件の残存エントリを修復削除した"` |
   | `total_entries` の再集計で不整合を修正した | `"total_entries 不整合を修正: {old} → {new}"` |

   このログにより「いつ・どのファイルを・どのモードで処理し・何を追加/削除したか・何が警告されたか」が追跡可能になる。

3. `knowledge/registry.json` を**ソースの最終確定点として最後に**更新:
   - 処理済みファイルのエントリを追加/更新
   - `file_hash`: MD5ハッシュ。`target_files` の行（`detect-knowledge-updates.py` の出力）の `file_hash` をそのまま書く（計算し直さない）
   - `status`: `"processed"`
   - `processed_date`: 現在日時（`YYYY-MM-DDTHH:MM:SS` 形式）
   - `entries_extracted`: 抽出件数
   - `extracted_entry_ids`: 今回追加したエントリIDの配列（例: `["PR-013", "CP-007", "AG-005"]`）
   - `deleted_entry_ids`: 今回削除したエントリIDの配列（`mode: "new"` の場合は `[]`）
   - `target_categories`: エントリを格納したカテゴリ一覧

   **なぜこのログが必要か**: LLMの実行内容はセッションをまたいで記憶されない。`registry.json`は「最新状態」のみ保持するが、`sync-log.jsonl`は「実行の全履歴」を保持する。更新ミス・重複・矛盾を後から検証するためにこのログは不可欠。

## Step 5: 原則DBとの同期

新しい原則・名言が見つかった場合:
1. 原則DBの該当カテゴリへの追加は提案として親へ返す（この役は正式DBへ書かない）
2. 既存カテゴリに該当しない場合は新カテゴリを提案
