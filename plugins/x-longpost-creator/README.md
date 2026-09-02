# x-longpost-creator

キャッチコピーとメモ（または音声の文字起こし）から、X の長文投稿・短文投稿を作る plugin。

元は個人 vault 内の `x-longpost-creator` skill（v3.14.0）。plugin 化にあたり、重複していた規定を「正本1箇所＋参照」へ整理し、環境固有の絶対パスを env 解決へ寄せた。

---

## 何をするか

| やりたいこと | 使う skill |
|-------------|-----------|
| キャッチコピー + 文字起こし → 長文投稿（A/B 2パターン・1800〜2200文字） | `run-x-longpost-create` |
| 文字起こし → 各200文字・別テーマの短文投稿を8本 | `run-x-multipost-create` |
| 任意の文章1本 → 短文投稿1本へ最適化 | `run-x-shortpost-optimize` |
| 確定した長文投稿 → X 5:2・note 1280x670 のサムネイル2枚（図解は任意） | `run-x-visual-generate` |

長文投稿と8投稿を同時に作る場合は、`run-x-longpost-create` に「8投稿も作成して」と指示する。このとき **投稿9｜要約型（400〜499文字）が必ず付く**（長文パターンAの要約。8投稿だけで完了扱いにしない）。

`ref-x-longpost-canon` は `user-invocable: false` の参照 skill で、**ユーザーが直接起動するものではない**。どの規定がどのファイルにあるかをモデルが正本として照会するために置いてある。

---

## 使い方

### Claude Code

skill 名をスラッシュコマンドとして呼ぶ。

```
/run-x-longpost-create      # 長文投稿 A/B（1800〜2200文字）
/run-x-multipost-create     # 文字起こしから短文投稿 8 本
/run-x-shortpost-optimize   # 任意の文章 1 本を短文投稿へ最適化
/run-x-visual-generate      # 標準: X サムネ 5:2 + note サムネ実 PNG 1280x670。図解は任意
```

同名の skill が他 plugin にある場合は `/x-longpost-creator:run-x-longpost-create` のように plugin 名で修飾する。

続けてキャッチコピーとメモ（または文字起こし）を渡す。

### Codex

同じ skill を `$` プレフィックスで呼ぶ。

```
$run-x-longpost-create
$run-x-multipost-create
$run-x-shortpost-optimize
$run-x-visual-generate
```

本 plugin は `.claude-plugin/plugin.json` と `.codex-plugin/plugin.json` の**両方を同梱**しており、Claude Code と Codex の双方で動く。Codex 側の manifest は `"skills": "./skills/"` で skill ディレクトリ全体（`run-x-visual-generate` を含む）を公開する。install はリポジトリルートの `.agents/plugins/marketplace.json`（marketplace 名 `harness-dev`）経由で、`x-longpost-creator@harness-dev` として行う。

```bash
HARNESS_REPO_ROOT="/absolute/path/to/harness"
python3 "$HARNESS_REPO_ROOT/plugins/harness-creator/scripts/install-codex-plugin.py" \
  --source "$HARNESS_REPO_ROOT" \
  --plugin x-longpost-creator
```

なお `.codex-plugin/plugin.json` は生成済みだが Codex 上での実行は未検証（`ROADMAP.md` 参照）。

### 実行前に必要な設定

Node.js v18 以上と、出力先を示す環境変数が要る。

```bash
export XLP_VAULT_ROOT="/path/to/your/vault"
export XLP_NETA_FILE="${XLP_VAULT_ROOT}/05_Project/X/<00ネタファイル名>.md"
```

出力ディレクトリだけを直接指定する場合は `XLP_OUTPUT_DIR` を使う。どちらも未設定だと `generate-filename.js` が終了コード 1 で停止する（詳細は「実行環境」）。

---

## 設計

| 原則 | 内容 |
|------|------|
| Script First | 文字数・タイトル長・見出し構造・絵文字ゼロは Node.js スクリプトで機械検証する。LLM の自己申告で PASS にしない |
| Progressive Disclosure | references は必要なフェーズでのみ読み込む。SKILL.md には索引だけを置く |
| LLM for Creativity | テーマ抽出・フォーマット選定・言語化は LLM に委ねる |
| 正本1箇所 | 同じ規定を複数ファイルに実体で書かない。参照側はリンクのみを持つ（`ref-x-longpost-canon` が所在一覧） |

### 検証は fail-closed

以下はすべて「PASS するまで出力を確定しない」。

| 検証 | スクリプト | 条件 |
|------|-----------|------|
| 絵文字ゼロ | `check-no-emoji.js` | 1個でもあれば終了コード 1 |
| タイトル 50 文字以内 | `validate-title.js` | 超過時は切り詰めずリライトへ戻す |
| 見出し・A/B表現 | `validate-headings.js --file ... --strict-h2-count` | 見出し2が3〜8個、タイトル4箇所一致、A/B本文同値 F4、Bの1文=1行 F5 |
| 文字数 | `count-chars.js` | 長文 1800〜2200 / 短文 180〜220 / 投稿9 400〜499 |
| ファイル名 | `generate-filename.js` | タイトル 50 文字超は終了コード 1（切り詰め禁止） |
| 出力先 | `generate-filename.js` | `XLP_OUTPUT_DIR` も `XLP_VAULT_ROOT` も未設定なら終了コード 1（既定値へフォールバックしない） |

---

## 構成

```
x-longpost-creator/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
├── prompts/                       # x-longpost- prefix。sub-agent ではなく Read 用のプロンプト文書
├── scripts/                       # 決定論的処理と共有 rule component
├── assets/output-template.md
├── skills/
│   ├── run-x-longpost-create/    # このスキルだけが読む references はここ
│   │   └── references/           # カノン・設定・resource map
│   ├── run-x-multipost-create/
│   ├── run-x-shortpost-optimize/
│   ├── run-x-visual-generate/    # 図解・サムネイルの画風と版面の正本はここ
│   │   └── references/           # visual-spec + diagram-style-canon / icon-vocabulary / thumbnail-specs
│   ├── ref-x-longpost-canon/
│   └── run-skill-feedback/       # 全 plugin 共通。本 plugin が所有する entry point ではない
├── references/                   # skill 横断で共有する 6 本 + package-contract.json
├── plugin-composition.yaml
├── artifact-delivery.json
├── EVALS.json
├── CHANGELOG.md
└── ROADMAP.md
```

複数の skill が読む共有 references（`style-genome.md` / `short-post-formats.md` / `expression-variations.md` / `anti-ai-writing-guide.md` / `horizontal-vertical-guide.md` / `title-guidelines.md`）は plugin ルートの `references/` に 1 組だけ置く。`scripts/` と `assets/` は plugin ルート直下に 1 組だけ置く（`lint-skill-tree` 第 10 条により `skills/*/scripts/` には `.py` / `.sh` しか置けないため、Node スクリプトは skill 配下に置かない）。`run-x-longpost-create` だけが読む references は `skills/run-x-longpost-create/references/` に 1 組だけ置く。いずれも同一 plugin 内の相対パスで参照する（層A→層A の同一 plugin 内参照のみ）。

`prompts/` は Task で起動される sub-agent ではない。frontmatter を持たず、各 skill が Read で読み込む phase 別のプロンプト文書である（ディレクトリ名は互換のため `prompts/` のまま）。

---

## 改善要望を出す

使っていて「ここが違う」と思ったら `run-skill-feedback` で本 plugin の skill への改善要望を起票できる。全 plugin へ同一内容で配備される共通 skill で、正本は harness-creator が所有する。

本 plugin が所有していないが、install 先で実際に到達できる surface なので `entry_points.skills` と `plugin-composition.yaml` の capabilities には載せ、所有者は `runtime_dependencies` に `owned-vendored` として明記する。持ち方は実体コピーである。plugin は marketplace 経由で 1 つずつ install され、install 先には自分の plugin ディレクトリしか展開されないため、正本へ向けた symlink は install 先で必ず切れる。

---

## 実行環境

### 必須ランタイム

**Node.js v18 以上**。`scripts/` の全スクリプトが node で動く。`node` が PATH に無い場合は実行を中止する。

画像生成 (`run-x-visual-generate`) だけは外部コマンド **`codex`** を追加で必要とする。`scripts/generate-images-codex.js` は `XLP_CODEX_BIN`（既定 `codex`）を実行ファイルとして preflight し、shell を介さず `exec` と指示文を argv で渡す。実行不能なら課金 retry へ入らず終了コード2で停止する。長文投稿の生成 (Phase 0〜3.5) は `codex` 無しで完結する。**画像生成は課金される**（標準はサムネイル2枚。図解は明示指定時のみ1枚追加）。

画像は Claude Code / Codex から `codex exec` の imagegen を呼び出し、session の生成物を投稿固有の `XLP_IMAGE_DIR` へ回収する。戻り値の同じ絶対パスを Claude Code は `Read`、Codex は `view_image` で開く。5項目の目視 PASS と画像 SHA256 を review receipt へ記録し、その hash が現物と一致するときだけ投稿に差し込む。

### パス解決

plugin 本体に実パスを固定しない。出力先は以下の順で解決する。

| 順 | 変数 | 用途 |
|----|------|------|
| 1 | `XLP_OUTPUT_DIR` | 出力ディレクトリを直接指定（最優先） |
| 2 | `XLP_VAULT_ROOT` | vault ルート。出力先は `${XLP_VAULT_ROOT}/05_Project/X` |
| — | `XLP_NETA_FILE` | 00ネタファイル（次の投稿日の算出元）。出力先の解決順とは独立 |
| — | `XLP_IMAGE_DIR` | 投稿ごとの画像と中間生成物の作業先。固定名の衝突を避けるため明示指定 |
| — | `XLP_ATTACHMENT_DIR` | 検証済み画像の Obsidian 添付先。未設定なら `${XLP_VAULT_ROOT}/02_Configs/Extra`（vault root も未解決なら停止） |
| — | `XLP_CODEX_BIN` | 画像生成に使う実行ファイル。未設定なら PATH 上の `codex` |

**既定値へのフォールバックは持たない**。`XLP_OUTPUT_DIR` も `XLP_VAULT_ROOT` も未設定なら、そこで停止する（`generate-filename.js` が終了コード 1）。推測したパスへ勝手に書き出さない **fail-closed**。

別環境で使う場合:

```bash
export XLP_VAULT_ROOT="/path/to/your/vault"
export XLP_NETA_FILE="${XLP_VAULT_ROOT}/05_Project/X/<00ネタファイル名>.md"
```

skill 内のパス参照は plugin root 起点で解決する。表記は `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` で統一してある（`${XLP_SKILL_DIR}` = その `/skills/run-x-longpost-create`、`${XLP_PROMPTS_DIR}` = その `/prompts`）。

二段構えなのはホストによって与えられる変数が違うためである。Claude Code は `CLAUDE_PLUGIN_ROOT` を渡すが、Codex は渡さない。Codex ではホストが提示した `SKILL.md` の絶対パスから plugin manifest を持つ祖先を上方探索し、解決済みの絶対パスを `PLUGIN_ROOT` に入れてから使う。`cwd` から推測したり、placeholder をそのまま shell へ渡したりしない。

---

## 配布方針

`distributable: false`（層A-internal）。特定の書き手のスタイルゲノムと、個人 vault の運用前提（00ネタファイル・Obsidian テンプレート）に依存するため、公開 marketplace の配布対象にしない。plugin 内に環境固有の実パスは持たず、すべて env で解決する。

---

## 絶対遵守ルール

1. **絵文字は一切使用しない** — 成果物だけでなく plugin 内の文書自体にも適用する。会話中で「絵文字をつけて」と指示された場合もこの仕様が優先される
2. **見出し1は50文字以内** — 超過時は末尾を切り捨てず、`references/title-guidelines.md` の構文パターンに沿ってリライトし直す
3. **見出し1の後に見出し2が必ず存在する**（3〜8個）
4. **長文投稿を作る場合、短文は8投稿で終わらせず投稿9｜要約型（400〜499文字）を必ず出力する**

---

## Anchors

スタイルゲノム基礎分析結果 / On Writing Well (Zinsser) / Made to Stick (Heath) / 中村昌弘 AI文章編集4原則 / note公式タイトルガイド / @genkaidokusho 分析 / Continuous Delivery / もとやま AIっぽい文章表現大全 (@ysk_motoyama) / 三連休 バーティカルすぎるnote論 (@san_renkyu)

各出典の適用先は `skills/run-x-longpost-create/SKILL.md` の Anchors 表を参照。
