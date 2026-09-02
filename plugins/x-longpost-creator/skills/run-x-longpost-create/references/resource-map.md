# リソースマップ

> **読み込み条件**: スキル実行時に参照するリソースを確認する時
> **責務**: 全リソースのインデックスを提供

---

## ディレクトリ構造

```
x-longpost-creator/                        # plugin ルート
├── prompts/                                # Read 用タスク仕様書
├── references/                            # 共有知識ベース
├── scripts/                               # 決定論的処理と共有 rule component
├── assets/                                # テンプレート
├── skills/run-x-visual-generate/          # 図解・サムネイル（Phase 4）
│   └── references/                        # visual-spec + 画風・アイコン語彙・サムネ説明（4本）
└── skills/run-x-longpost-create/
    ├── SKILL.md                           # スキル定義（エントリポイント）
    └── references/                        # 本スキル専用の知識ベース
```

使用記録の出力先は `XLP_LOG_FILE` → `${XLP_OUTPUT_DIR}/x-longpost-usage-log.md` の順で解決する。plugin ディレクトリの中には書かない。

visual references は4本で、kind・生成/納品寸法・比率・横断 text rule の機械可読正本は [visual-spec.json](../../run-x-visual-generate/references/visual-spec.json) である。残る3本は画風・アイコン粒度・サムネイル版面の意味を説明する。

---

## prompts/（タスク仕様書・plugin ルート直下）

| ファイル | 責務 | Phase | ワークフロー |
|----------|------|-------|-------------|
| [structure-transcript.md](../../../prompts/x-longpost-structure-transcript.md) | 文字起こし → 構造化メモ | 0 | 文字起こし系（共通前処理） |
| [create-multi-posts.md](../../../prompts/x-longpost-create-multi-posts.md) | 短文投稿作成（投稿1〜8は各200文字 / §5.3.5 の投稿9｜要約型は400〜499文字。いずれも空白・改行を除く） | 1 / 3.4 | 文字起こし→8投稿 / 長文+8投稿 |
| [parse-input.md](../../../prompts/x-longpost-parse-input.md) | 構成要素抽出 | 1 | 長文投稿 |
| [resolve-contradictions.md](../../../prompts/x-longpost-resolve-contradictions.md) | 矛盾解決 | 1 | 長文投稿 |
| [create-title.md](../../../prompts/x-longpost-create-title.md) | タイトル3案生成・推奨1案を確定（以後この文字列が唯一のタイトル） | **1.5** | 長文投稿 |
| [apply-style-genome.md](../../../prompts/x-longpost-apply-style-genome.md) | スタイル適用（本文生成） | 2 | 長文投稿 |
| [optimize-length.md](../../../prompts/x-longpost-optimize-length.md) | 文章最適化・2パターン生成・見出し2作成（タイトルは作らない） | 2 | 長文投稿 |
| [split-thread.md](../../../prompts/x-longpost-split-thread.md) | スレッド分割 | 3 | 長文投稿 |
| [output-file.md](../../../prompts/x-longpost-output-file.md) | ファイル出力 | 3 | 長文投稿 |
| [generate-idea-compass.md](../../../prompts/x-longpost-generate-idea-compass.md) | アイデアコンパス生成 | 3.5 | 長文投稿（出力後処理） |
| [short-post-optimizer.md](../../../prompts/x-longpost-short-post-optimizer.md) | 短文投稿最適化（入力文章→1投稿。独立実行／長文フロー内の2モード） | 1-4 / 3 | 短文投稿最適化 / 長文投稿（オプション） |
| [analyze-visual-structure.md](../../../prompts/x-longpost-analyze-visual-structure.md) | パターンA本文 → `visual-structure.json`（三分割・構造型 T1〜T4・サムネ文言） | **4.1** | 図解・サムネイル |
| [design-diagram-prompt.md](../../../prompts/x-longpost-design-diagram-prompt.md) | 構造データ → 図解の生成プロンプト（STYLE/LAYOUT/CONTENT/TYPOGRAPHY/NEGATIVE の5ブロック） | **4.2** | 図解・サムネイル |
| [design-thumbnail-prompt.md](../../../prompts/x-longpost-design-thumbnail-prompt.md) | 構造データ → 標準成果物 X 5:2・note 1280x670 のプロンプト（両サムネイルで STYLE/TYPOGRAPHY/NEGATIVE を共有） | **4.2** | サムネイル（図解は任意） |

---

## references/（知識ベース）

| ファイル | 責務 | 読込条件 |
|----------|------|----------|
| [style-genome.md](../../../references/style-genome.md) | 8レベル文体特徴 | 文章生成時（必須） |
| [writing-guidelines.md](writing-guidelines.md) | 文章整形ガイド | 文章整形時（必須） |
| [horizontal-vertical-guide.md](../../../references/horizontal-vertical-guide.md) | ホリゾンタル入口×バーティカル中身の設計原則（正本: 欲求翻訳・TAMチェック・ネタ性質判定・2層設計） | タイトル・冒頭・フック・本文構成の作成時（必須） |
| [title-guidelines.md](../../../references/title-guidelines.md) | **タイトルの文言設計の正本**（構文パターンA〜H・共感/結末ワード・心理トリガー・禁止表現・字数配分） | タイトル生成時（Phase 1.5・必須） |
| [heading-structure-rules.md](heading-structure-rules.md) | **見出し構造とA/B表現契約の正本**（R1/R2・4箇所一致・F4本文同値・F5の1文1行・check ID・終了コード） | タイトル生成時・長文A/B生成時・ファイル出力時（必須） |
| [short-post-formats.md](../../../references/short-post-formats.md) | 短文投稿8パターン（冒頭フックバリエーション付き） | 短文投稿生成時（必須） |
| [expression-variations.md](../../../references/expression-variations.md) | 表現バリエーション（接続詞・文末・締め・問いかけ） | 短文投稿生成時（必須） |
| [anti-ai-writing-guide.md](../../../references/anti-ai-writing-guide.md) | AI臭除去ガイド（6分類+崩し3技法） | 短文投稿生成時・AI臭チェック時（必須） |
| [heading-title-guide.md](heading-title-guide.md) | **見出し2の書き方の実質正本**（絵文字全面禁止・具体化原則・NG役割名リスト。validate-headings.js H10 の判定元） | セクション見出し作成時（必須） |
| [optimize-length-details.md](optimize-length-details.md) | AI編集4原則・AI臭6分類・改行詳細ルール（prompts/x-longpost-optimize-length.md から分離保管） | 文章最適化時（必須） |
| [workflow-diagrams.md](workflow-diagrams.md) | ワークフロー図のフル版・フロー間対応表 | フロー全体像の確認時 |
| [script-llm-patterns.md](script-llm-patterns.md) | スクリプト/LLM分担 | 処理設計時 |
| [output-config.json](output-config.json) | 入出力パス解決（vaultRoot・netaFile・テンプレート）の正本 | パス解決時（必須） |
| [resource-map.md](resource-map.md) | リソース一覧 | 参照確認時 |

---

## assets/（テンプレート・plugin ルート直下）

| ファイル | 責務 | 読込条件 |
|----------|------|----------|
| [output-template.md](../../../assets/output-template.md) | 出力ファイルテンプレート（実運用標準形・TEMPLATE-START/ENDマーカー間を展開） | ファイル出力時 |

---

## scripts/（決定論的処理）

| ファイル | 責務 | 入力 | 出力形式 |
|----------|------|------|----------|
| [calculate-next-date.js](../../../scripts/calculate-next-date.js) | 次の投稿日計算 | 00ネタファイルパス | JSON |
| [generate-filename.js](../../../scripts/generate-filename.js) | ファイル名生成（タイトル50文字超はfail-closed） | 日付、タイトル | JSON |
| [validate-title.js](../../../scripts/validate-title.js) | タイトル絶対ルール検証（50文字・非空・単一行・絵文字・禁止表現・ファイル名安全） | タイトル | JSON |
| [validate-headings.js](../../../scripts/validate-headings.js) | 見出し構造の絶対ルール検証（H1〜H10）と、タイトル4箇所一致 F1〜F3・A/B本文同値 F4・B本文1文1行 F5 | 本文（`--text` は `# タイトル` 行を含むパターンA全文＋`--title` 必須）またはファイルパス | JSON |
| [count-chars.js](../../../scripts/count-chars.js) | 文字数カウント・検証（空白・改行を除いた文字数で判定） | `--text` または `--file`。`--min` `--max` は必須で既定値なし（未指定は終了コード2） | JSON |
| [update-neta-file.js](../../../scripts/update-neta-file.js) | 00ネタファイル更新 | ファイルパス | JSON |
| [expand-template.js](../../../scripts/expand-template.js) | テンプレート展開 | テンプレート、変数 | テキスト |
| [check-no-emoji.js](../../../scripts/check-no-emoji.js) | 絵文字ゼロ検証 | ファイルパスまたはテキスト | JSON |
| [log_usage.js](../../../scripts/log_usage.js) | 使用記録 | 結果、Phase | ログ追記 |
| [log_usage.mjs](../../../scripts/log_usage.mjs) | 使用記録（ESM 版・`log_usage.js` と等価） | 結果、Phase | ログ追記 |
| [build-visual-prompts.js](../../../scripts/build-visual-prompts.js) | 図解構造データの制約検証（ゾーン数・字数・禁止語・絵文字）と meta 生成 | `visual-structure.json` | JSON + `{kind}.meta.json` |
| [generate-images-codex.js](../../../scripts/generate-images-codex.js) | `XLP_CODEX_BIN` の実行可能性を事前検査し、executable + argv で行う画像生成と PNG 回収（**課金あり**。`--dry-run` は課金せず同じ preflight） | プロンプトと meta | JSON + PNG |
| [lint-thumbnail-prompt.js](../../../scripts/lint-thumbnail-prompt.js) | サムネイル2種の `.prompt.txt` を**課金前**に検証（TL-01〜TL-12。`--structure` による本文由来文言の一致と、2種間の STYLE/TYPOGRAPHY/NEGATIVE 完全一致を含む） | 画像ディレクトリ + `visual-structure.json` | JSON |
| [assets/reference-images/](../../../assets/reference-images/README.md) | 画風の見本画像と manifest。`generate-images-codex.js` が kind ごとに `codex exec -i` で添付する。実体が無くても生成は動くが、宣言との差は毎回 WARN として記録される | 見本 PNG と manifest.json | codex への添付 |
| [validate-visual-assets.js](../../../scripts/validate-visual-assets.js) | 生成 PNG の署名・比率・寸法・背景の不透明性・種別ごとの背景色を検証。既定は標準2サムネイルを strict 検証し、note は実 PNG 1280x670 以外を FAIL にする。図解は `--only diagram` 時だけ対象 | 画像ディレクトリ | JSON |
| [record-thumbnail-review.js](../../../scripts/record-thumbnail-review.js) | Claude Code `Read` / Codex `view_image` で開いた同じ絶対パスに対する5項目の PASS、ホスト、表示ツール、画像 SHA256 を review receipt へ記録 | サムネイル PNG、`--host` | `{kind}.review.json` |
| [embed-visual-paths.js](../../../scripts/embed-visual-paths.js) | 検証済み画像を投稿固有名で Obsidian 添付先へ配置し、対応欄へ冪等に差し込む。サムネイルは5項目 PASS receipt と現在の画像 SHA256 の一致を必須にする | 投稿ファイル、作業画像、review receipt、添付先 | JSON + PNG + md 更新 |

---

## ワークフロー別リソース

### 長文投稿ワークフロー

```
Phase 1: 入力解析
├── prompts/x-longpost-parse-input.md
├── prompts/x-longpost-resolve-contradictions.md
└── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/calculate-next-date.js

Phase 1.5: タイトル確定（以後この文字列が唯一のタイトル）
├── prompts/x-longpost-create-title.md
├── references/title-guidelines.md（構文パターンA〜H・推奨はE）
├── references/heading-structure-rules.md（50字ルールの根拠・リライト6手順）
├── references/horizontal-vertical-guide.md（ネタ性質判定・欲求翻訳・TAMチェック・2層設計）
└── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-title.js（3案すべてに実行）

Phase 2: 文章生成（タイトルは作らない。Phase 1.5 の確定タイトルをそのまま見出し1に置く）
├── prompts/x-longpost-apply-style-genome.md
├── prompts/x-longpost-optimize-length.md
├── references/style-genome.md
├── references/writing-guidelines.md
├── references/horizontal-vertical-guide.md（冒頭フック・見出し・本文構成の入口設計）
├── references/heading-structure-rules.md（見出し1の50文字・見出し2必須の絶対ルール）
├── references/heading-title-guide.md（見出し2の書き方・NG役割名）
├── references/optimize-length-details.md（AI編集4原則・AI臭6分類・改行詳細ルール）
└── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js（--text は `# タイトル` 行を含むパターンA全文＋--title 必須。PASSするまでパターンAを確定しない）

Phase 3: 出力整形
├── prompts/x-longpost-split-thread.md
├── prompts/x-longpost-output-file.md
├── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-filename.js
├── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/expand-template.js（Writeで直接組み立てず必ず展開経由。missingVars が空であること）
├── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-headings.js（--file で H1〜H10 / F1〜F5 を一時パス上で検証 → PASS後に X/ へ配置 → 配置後に再検証）
├── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-chars.js
├── ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/update-neta-file.js
└── ../../../assets/output-template.md
```

### 文字起こし → 8投稿ワークフロー

```
Phase 0: 文字起こし構造化
└── prompts/x-longpost-structure-transcript.md（フィラー除去・書き言葉変換・構造化メモ生成）

Phase 1: 8投稿作成
├── prompts/x-longpost-create-multi-posts.md（8つの独立テーマ→各200文字）
├── references/short-post-formats.md（8パターン）
├── references/horizontal-vertical-guide.md（フック行の欲求翻訳）
├── references/style-genome.md（8レベル文体特徴）
├── references/expression-variations.md（バリエーション）
└── references/anti-ai-writing-guide.md（AI臭チェック）
```

### 短文投稿最適化ワークフロー（1投稿）

```
Phase 1: 入力文章分析
└── prompts/x-longpost-short-post-optimizer.md#入力文章アナリスト

Phase 2: フォーマット選定
├── prompts/x-longpost-short-post-optimizer.md#フォーマットセレクター
├── references/short-post-formats.md（8パターン+冒頭フックバリエーション）
└── references/horizontal-vertical-guide.md（フック行の欲求翻訳・ホリゾンタル入口）

Phase 3: 投稿文生成
├── prompts/x-longpost-short-post-optimizer.md#投稿文ジェネレーター
└── references/expression-variations.md（接続詞・文末・締め）

Phase 4: 最適化・出力
├── prompts/x-longpost-short-post-optimizer.md#スタイルオプティマイザー
├── references/style-genome.md（8レベル文体特徴）
└── references/anti-ai-writing-guide.md（AI臭6パターン確認）
```

### 短文投稿生成（長文フロー内・オプション）

```
Phase 3: 短文投稿生成
├── prompts/x-longpost-short-post-optimizer.md（長文フロー内で並行生成）
├── references/short-post-formats.md
├── references/horizontal-vertical-guide.md（フック行の欲求翻訳・ホリゾンタル入口）
└── references/expression-variations.md
```

---

## Progressive Disclosure

リソースは必要な時に必要なものだけを読み込む:

1. **常に読み込み**: SKILL.md
2. **Phase実行時**: 該当Phaseのprompts/
3. **必要時**: references/（prompts 内で参照指示）
4. **決定論的処理時**: scripts/を実行

---

## 関連リソース

| 目的 | 参照先 |
|------|--------|
| スキル概要 | [SKILL.md](../SKILL.md) |
| スクリプト/LLM分担 | [script-llm-patterns.md](script-llm-patterns.md) |
| 変更履歴 | [CHANGELOG.md](../../../CHANGELOG.md) |
