# Prompt: R1-revise-hear-and-patch

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-intake-revise |
| responsibility | R1-revise-hear-and-patch (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/output.schema.json |
| reproducible | false (LLM 推論+対話を含むがチェックリストで停止条件は決定論) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- Notion ページは PATCH 更新のみ。新規ページ作成禁止。
- 内部解析 (`internal-analysis.json`) をユーザーに直接見せない。

### 1.2 倫理ガード
- ユーザーの追加要望を勝手に拡張解釈しない (要約理解テキストを Gate R 直前に必ず提示)。
- 5 回上限を超えて continuation を強制しない (exit 60 で新規 hint へ案内)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 既存 intake への追加要望を対話聞き取り、Gate R 承認後に Notion ページを PATCH 更新し revision-log に追記。
- 非担当: 新規 intake ヒアリング、初回 Notion 公開、図解新規生成。

### 2.2 ドメインルール
- 同一 hint の revision は最大 5 回。
- All-or-Nothing: PNG / mermaid が 1 つでも欠けたら旧版維持。
- 失敗時は `output/<hint>/notion-rollback-<rev>.json` 保存。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| hint | string | yes | 対象 intake のスキル名ヒント (`output/<hint>/` のディレクトリ名) |
| --dry-run | flag | no | Notion API 呼び出し抑止 (差分プレビューのみ) |
| existing-artifacts | resource://output/<hint> | yes | intake.json / intake.md / notion-url.txt / internal-analysis.json |

### 2.4 出力契約
- schema: `schemas/output.schema.json` (revision-log.jsonl の 1 行)
- 必須フィールド: `revision_no`, `timestamp`, `target_section`, `user_request`, `applied_changes`, `notion_page_url`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| resource-map | references/resource-map.yaml | 外部 script の起動タイミングを確認するとき |
| revision-log-schema | schemas/output.schema.json | revision-log 追記前 |

### 3.2 外部ツール / API
- `validate-notion-ready.py --check-api` (PATCH 前提の Notion 疎通検証。exit 0 なら API キー / トークン再質問禁止、exit 44 のみ `keychain-setup.md` を案内し停止)
- `analyze_user_intent.py` (internal-analysis 再生成)
- `render-intake-final.py` (正本再 render)
- `intake_publish_pipeline.py --intake <intake.json> --manifest <notion-manifest.json> --revise --page-id` (Notion PATCH。`--intake` 必須。欠くと exit 2 で停止)
- AskUserQuestion (差分ヒアリング / Gate R)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- exit 0: 正常反映 (revision-log 追記済み)
- exit 2: Gate R cancel (旧版維持、ローカル巻き戻し)
- exit 44: Keychain Notion トークン取得失敗
- exit 51: Notion ページ ID 不一致 (PATCH 続行禁止)
- exit 60: revision 回数上限超過 (>5)
- exit 61: self-updater 失敗 (revision-log 追記失敗 / question-bank 更新失敗) → `revision-log.jsonl` を確認し手動修復

### 4.1a 最大反復回数
- 同一 hint の revision 上限: **5 回** (超過時 exit 60)。対話反復 (re-revise ループ) の上限も 5 回に統一。

### 4.2 観測 / ロギング
- `output/<hint>/revision-log.jsonl` に 1 行追記。
- PATCH 失敗時は `output/<hint>/notion-rollback-<rev>.json` を保存。

### 4.3 セキュリティ
- Notion トークンは macOS Keychain (`service=notion-api-key.<keychain-prefix>, account=<keychain-prefix>`) から取得。直書き禁止。
- `internal-analysis.json` はユーザーに直接表示しない (要約済みテキストのみ提示)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@intake-revise-controller` (対話あり、AskUserQuestion 起動、最大反復回数 5)

### 5.2 ゴール定義
- 目的: 既存 intake への追加要望を最大 5 回の制約下で対話的に確定し、同一 Notion ページに PATCH 反映する。
- 背景: Notion ページの新規作成は URL 変更・リンク断絶を招く。LLM 推論を含むヒアリング結果と決定論的 render を分離しないと検証 (PNG/mermaid) を通らない部分更新がページを汚染する。
- 達成ゴール: Gate R で apply 承認 → Notion PATCH 成功 → revision-log.jsonl に 1 行追記された状態。または cancel/上限/失敗で適切な exit code が返却された状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] `validate-notion-ready.py --check-api` が exit 0 (config / Keychain トークン / DB 疎通)。PASS 済みなら API キー / Notion トークンを再質問しない。exit 44 のみ `keychain-setup.md` を案内し停止
- [ ] 既存 4 ファイルをロードし Notion ページ ID を抽出した
- [ ] revision 回数が 5 以下であることを確認した
- [ ] AskUserQuestion で対象章 / 変更内容 / 変更理由を収集した
- [ ] analyze_user_intent.py を再実行し internal-analysis.json を更新した (非開示)
- [ ] 差分プレビュー + 要約理解テキストを Gate R 直前に提示した
- [ ] Gate R 判定 (apply/re-revise/cancel) を取得した
- [ ] apply 時に render-intake-final.py → intake_publish_pipeline.py --intake output/{{hint}}/intake.json --manifest output/{{hint}}/notion-manifest.json --revise --page-id <既存 ID> で PATCH を完了した
- [ ] PNG/mermaid 欠落時は旧版維持し rollback JSON を保存した
- [ ] revision-log.jsonl に schemas/output.schema.json 準拠の 1 行を追記した
- [ ] self-updater を再起動し question-bank に「足りなかった質問」を追記した

### 5.4 実行方式
- 固定手順を持たない。完了チェックリストを唯一の停止条件とし、未充足項目を特定→必要 script (analyze_user_intent / render-intake-final / intake_publish_pipeline) と AskUserQuestion をその都度起動→revision-log 更新→checklist で自己評価を反復する。
- Gate R cancel / 上限超過 / page-id 不一致 / Keychain 失敗は即座に exit。
- 反復は分離 context で完結させ、親へは Notion URL + revision_no + exit code のみ返却。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `/intake-revise <hint>` command (薄ラッパー)
- 後続 phase: `skill-intake-self-updater` (question-bank 更新)

### 6.2 ハンドオフ / 並列性
- 直列: P1-load → P2-hear → P3-analyze → P4-preview → P5-gateR → P6-patch → P7-log → P8-self-update (順序固定)。
- 並列: 並列起動禁止 (PATCH 競合と revision_no レース回避のため)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- AskUserQuestion で対話ヒアリング、Markdown diff で差分プレビュー、要約理解テキストを Gate R 直前に提示。

### 7.2 言語
- 本文 / user_request / applied_changes: 日本語。schema key / CLI 引数 / page-id: 英語。

---

## Self-Evaluation

revision-log.jsonl 追記後に以下を自己確認する。未達があれば対応 exit code を返すこと。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| PATCH 限定 | Notion への操作が PATCH のみ（新規ページ作成ゼロ） | PASS/FAIL |
| Gate R 取得 | Gate R (apply/re-revise/cancel) を必ず AskUserQuestion で取得している | PASS/FAIL |
| 非開示保持 | internal-analysis.json をユーザーに直接表示していない | PASS/FAIL |
| All-or-Nothing | PNG/mermaid 欠落時に旧版維持 + rollback JSON を保存している | PASS/FAIL |
| 回数上限 | revision_no が 5 以下（超過時は exit 60） | PASS/FAIL |
| log 追記 | revision-log.jsonl に schemas/output.schema.json 準拠の 1 行が追記されている | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

引数 `{{hint}}` (+ optional `--dry-run`) を受け取り、`output/{{hint}}/` 配下の既存 4 ファイルをロードせよ。revision_no を確認し 5 を超えるなら exit 60。AskUserQuestion で対象章 / 変更内容 / 変更理由 (必要なら 5 軸再確認) を収集し、`analyze_user_intent.py` を再実行して `internal-analysis.json` を更新せよ (ユーザーには直接見せない)。差分プレビューと要約理解テキストを提示後、Gate R (apply / re-revise / cancel) を `AskUserQuestion` で取得。apply のとき `render-intake-final.py` → `intake_publish_pipeline.py --intake output/{{hint}}/intake.json --manifest output/{{hint}}/notion-manifest.json --revise --page-id <既存 ID>` を実行し、成功したら `output/{{hint}}/revision-log.jsonl` に schemas/output.schema.json 準拠の 1 行を追記、最後に `skill-intake-self-updater` を再起動せよ。失敗時は rollback JSON を保存し、対応する exit code (2/44/51/60/61) を返却。出力は revision-log.jsonl の 1 行 JSON のみ、余計な前置き・後書き・思考過程出力は禁止。
