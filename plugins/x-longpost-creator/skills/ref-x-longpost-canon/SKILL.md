---
name: ref-x-longpost-canon
description: X 長文投稿のルールがどのファイルにあるか迷ったとき、同じ規定が複数箇所に見えてどれが正か判断する必要があるときに読む。
disable-model-invocation: false
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
effect: none
owner: team-content
since: 2026-08-31
version: 1.0.0
source: ObsidianMemo/.claude/skills/x-longpost-creator (v3.14.0)
source-tier: internal
last-audited: 2026-08-31
audit-trigger: quarterly
responsibility_refs:
  - ../../plugin-composition.yaml
  - ../run-x-longpost-create/references/resource-map.md
schema_refs:
  - ../../references/package-contract.json
  - ../run-x-visual-generate/references/visual-spec.json
completeness_exempt:
  - "manifest: ref/effect:none の読み取り専用正本索引であり、実行 Phase や gate を持たない。"
---

# ref-x-longpost-canon

## Purpose & Output Contract

本ファイルは、規定の所在と意味を説明する読み取り専用の索引である。値の合否をここの散文で決めない。**機械可読 spec/script が判定**し、本ファイルはその判定先と人間向けの意味を一方向に案内する。visual の kind・寸法・比率・横断 text rule は `skills/run-x-visual-generate/references/visual-spec.json`、その他の数値判定は表に記載した検証 script が authority である。

元スキル（v3.14.0）では同じ規定が複数ファイルに実体で重複していた。plugin 化にあたり「正本1箇所＋他は参照のみ」へ整理した結果を記録する。

規定の値が食い違って見えたときは、本索引が指す machine-readable authority を実行する。散文は意味説明であり、機械判定を上書きしない。

---

## 正本一覧

本表のパスはすべて plugin ルート `${CLAUDE_PLUGIN_ROOT}` からの相対である（読み手のファイル位置に依存しない）。

| 規定 | 正本 | 参照のみ（実体を持たない） |
|------|------|---------------------------|
| **禁止表現リスト（タイトル）** | `references/title-guidelines.md` §3.3.1 | `prompts/x-longpost-create-title.md` §9 |
| **禁止表現リスト（本文）** | `references/title-guidelines.md` §3.3.2 | `prompts/x-longpost-apply-style-genome.md` §4.5、`prompts/x-longpost-optimize-length.md` §4.3.1、各 SKILL.md |
| **タイトル構文パターンA〜H・字数配分・心理トリガー** | `references/title-guidelines.md` | `prompts/x-longpost-create-title.md` |
| **見出し構造の絶対ルール R1/R2・4箇所一致・A/B本文同値・Bの1文1行・check ID H1〜H10 / F1〜F5** | `skills/run-x-longpost-create/references/heading-structure-rules.md` | `prompts/x-longpost-optimize-length.md`、`prompts/x-longpost-output-file.md`、`skills/run-x-longpost-create/SKILL.md` |
| **スタイルゲノム 8レベル（L1〜L8）の詳細** | `references/style-genome.md` | `skills/run-x-longpost-create/SKILL.md`（索引表のみ）、`prompts/x-longpost-apply-style-genome.md`、`prompts/x-longpost-short-post-optimizer.md` §5 Phase 4、`prompts/x-longpost-create-multi-posts.md` §5.3 |
| **AI臭6分類 + 崩し3技法** | `references/anti-ai-writing-guide.md` | `prompts/x-longpost-apply-style-genome.md`、`prompts/x-longpost-optimize-length.md`、`prompts/x-longpost-short-post-optimizer.md`、`prompts/x-longpost-create-multi-posts.md` §5.4、`skills/run-x-longpost-create/references/optimize-length-details.md` §2 |
| **AI文章編集4原則（中村昌弘）** | `skills/run-x-longpost-create/references/optimize-length-details.md` §1 | `prompts/x-longpost-apply-style-genome.md`（①②主担当）、`prompts/x-longpost-optimize-length.md`（③④主担当） |
| **文脈改行のルール・かぎ括弧複数の改行ルール** | `skills/run-x-longpost-create/references/optimize-length-details.md` §3・§4 | `prompts/x-longpost-optimize-length.md` |
| **短文投稿8フォーマット・冒頭フックバリエーション・改行ルール詳細** | `references/short-post-formats.md` | `prompts/x-longpost-short-post-optimizer.md` §6.2、`prompts/x-longpost-create-multi-posts.md` §5.2 |
| **表現バリエーション（接続詞・文末・締め・問いかけ・強調副詞）** | `references/expression-variations.md` | 各 agent の生成フェーズ |
| **ホリゾンタル入口×バーティカル中身・欲求翻訳6カテゴリ・TAMチェック・ネタ性質判定** | `references/horizontal-vertical-guide.md` | `prompts/x-longpost-create-title.md`、`prompts/x-longpost-short-post-optimizer.md` SP-C08 |
| **見出しタイトルの作り方（避けるべき汎用タイトル・目指すべき具体タイトル）** | `skills/run-x-longpost-create/references/heading-title-guide.md` | `skills/run-x-longpost-create/SKILL.md`「見出し作成のガイドライン」 |
| **ワークフロー図のフル版・フロー間対応表** | `skills/run-x-longpost-create/references/workflow-diagrams.md` | `skills/run-x-longpost-create/SKILL.md`（要約図） |
| **リソース一覧（prompts / references / assets / scripts）** | `skills/run-x-longpost-create/references/resource-map.md` | `skills/run-x-longpost-create/SKILL.md`（要約表） |
| **Script と LLM の処理分担マトリクス** | `skills/run-x-longpost-create/references/script-llm-patterns.md` | 各 SKILL.md |
| **入出力パスの env-only 解決順** | `skills/run-x-longpost-create/references/output-config.json` | `../../scripts/generate-filename.js`、各 SKILL.md「出力設定」 |
| **visual kind・生成/納品寸法・比率・palette・背景規則・横断 text rule** | `skills/run-x-visual-generate/references/visual-spec.json` | `build-visual-prompts.js`、`validate-visual-assets.js`、`lint-thumbnail-prompt.js`、`thumbnail-specs.md` |
| **サムネイルの画風・配色・情報商材的意匠の禁止** | `skills/run-x-visual-generate/references/thumbnail-style-canon.md` | `x-longpost-design-thumbnail-prompt.md`、`thumbnail-specs.md`、`lint-thumbnail-prompt.js` |
| **画風の見本画像（線の太さ・塗りの密度・簡略度）** | `assets/reference-images/manifest.json` | 文章の canon が決めるのは色・個数・余白まで。絵でしか渡せない量はここが正本で、`codex exec -i` として生成へ渡る |
| **投稿9｜要約型（400〜499文字）の必須条件** | `prompts/x-longpost-create-multi-posts.md` §5.3.5 / MP-C07 | `skills/run-x-longpost-create/SKILL.md`「絶対遵守ルール」、`skills/run-x-multipost-create/SKILL.md` |
| **短文投稿最適化の4フェーズ・2つの呼び出しモード** | `prompts/x-longpost-short-post-optimizer.md` | `skills/run-x-shortpost-optimize/SKILL.md`、`skills/run-x-longpost-create/SKILL.md` Phase 3 |
| **絵文字全面禁止** | `scripts/lib/text-rules.js`（共有意味実装） | `check-no-emoji.js` / `validate-title.js` / `validate-headings.js` / `build-visual-prompts.js` が各 CLI 入力境界で検査 |

references の実体は2箇所に分かれる。複数の skill が読む**共有 references**（`style-genome.md` / `short-post-formats.md` / `expression-variations.md` / `anti-ai-writing-guide.md` / `horizontal-vertical-guide.md` / `title-guidelines.md`）は plugin ルートの `references/` にあり、`run-x-longpost-create` だけが読む固有 references は `skills/run-x-longpost-create/references/` にある。scripts / assets の実体は plugin ルート直下の `scripts/` と `assets/` にある（`lint-skill-tree` 第 10 条が `skills/*/scripts/` を `.py` / `.sh` に限るため、Node スクリプトは skill 配下に置けない）。他スキルは同一 plugin 内の相対参照で読む。

---

## 絵文字の定義（判定境界）

「絵文字」とは Unicode プロパティ `\p{Extended_Pictographic}` に該当する文字を指す。この意味実装の正本は `../../scripts/lib/text-rules.js` である。`check-no-emoji.js` はファイル/テキスト全体の検査 CLI、`validate-title.js` と `validate-headings.js` は各タイトル・見出し境界、`build-visual-prompts.js` は構造データの全 string leaf 境界で、同じ共有実装を呼ぶ。

| 判定 | 例 |
|------|-----|
| 絵文字（禁止） | 顔文字類、および U+2705 / U+274C / U+26A0 などの記号系絵文字 |
| 絵文字ではない（使用可） | `✓` `✗` `☆` `→` `▼` `①` `※` |

U+2705 と `✓`（U+2713）は見た目が近いが、Extended_Pictographic に該当するのは前者だけである。成果物全体で迷ったら `check-no-emoji.js` に通す。

**共有意味実装を替えてはならない。** `\p{Extended_Pictographic}` の範囲は処理系とバージョンで変わる。そのため散文の例示から安全性を推測せず、現在の `text-rules.js` を呼ぶ `check-no-emoji.js` の実行結果を正本とする。CLI ごとに別の正規表現を再実装せず、全体走査は `check-no-emoji.js`、個別値はそれぞれの検証 CLI を使う。

---

## 数値契約の機械判定先

下表は人間が要件の意味を素早く読むための索引である。合否は「検証コマンド」列の script と visual-spec.json が判定する。

| 対象 | 正本の値 | 検証コマンド |
|------|----------|-------------|
| 長文投稿 A/B の文字数 | **1800〜2200文字**（中心値2000） | `count-chars.js --min 1800 --max 2200` |
| 投稿9｜要約型の文字数 | **400〜499文字** | `count-chars.js --min 400 --max 499` |
| 短文投稿（8投稿）の文字数 | **180〜220文字**（約200文字） | `count-chars.js --min 180 --max 220` |
| 見出し1（タイトル）の長さ | **50文字以内**（コードポイント数・空白含む） | `validate-title.js --title "..."` |
| タイトルの字数配分 | 入口26〜32字 + 予告8〜18字 | — |
| 見出し2の個数 | **3〜8個**（check ID H5） | `validate-headings.js --file <path> --strict-h2-count`（既定では H5 は警告止まりのため、本 plugin は常に `--strict-h2-count` を付ける） |
| 見出し1と見出し2の間のリード文 | 8行・300文字以内 | `validate-headings.js` |
| 1行の目安幅（文脈改行） | 30〜40字程度（文字数ぴったりでは切らない） | — |
| 絵文字 | **0個**（例外なし） | `check-no-emoji.js --file <path>` |
| 長文 A/B の本文同値 | Markdown 見出し・先頭タイトル・空白・改行を表示差として除いた本文が同一 | `validate-headings.js --file <path>`（F4） |
| 長文 B の改行 | 非空本文行が1行につきちょうど1文 | `validate-headings.js --file <path>`（F5） |

---

## 移植時に解消した重複・矛盾

元スキル v3.14.0 からの移植で、値が食い違っていた箇所とその決着。

| # | 矛盾していた箇所 | 元の状態 | 決着 |
|---|-----------------|----------|------|
| 1 | 長文の文字数レンジ | SKILL.md「2000文字以上」/ 実行手順「1800〜2500」/ `optimize-length.md` §4.7「1800〜2200」 | **1800〜2200** に統一（`optimize-length.md` の値を採用） |
| 2 | 禁止表現リスト | SKILL.md・`create-title.md`・`apply-style-genome.md`・`optimize-length.md` の4箇所に実体が重複 | `references/title-guidelines.md` §3.3 を唯一の正本とし、他は参照のみ |
| 3 | 制約 ID `CONST_007` | 4つの agent が同じ ID を別の意味で使用 | agent 別プレフィックス（`TR-` / `MP-` / `SP-` / `IC-`）で一意化 |
| 4 | 短文投稿エージェント | `create-short-post.md` と `short-post-optimizer.md` が同一責務で並存 | `x-longpost-short-post-optimizer.md` 1本へ統合（§4.5 で2つの呼び出しモードを規定） |
| 5 | 見出し2の個数 | 記述箇所により揺れ | **3〜8個**（`validate-headings.js` の check ID H5 の実装値を正本） |
| 6 | `emoji-selection-guide.md` | v3.3.0 の絵文字全面禁止後も旧名のまま、中身は見出しタイトル作成ガイド | `heading-title-guide.md` へ改名（名実一致） |
| 7 | 出力先の絶対パス | SKILL.md・scripts・旧 prompt 群に vault の実パスが直書き | `skills/run-x-longpost-create/references/output-config.json` へ env-only 解決契約を集約。未解決時は fail-closed |
| 8 | 重複・冗長ファイル | `output-template-legacy.md` / `references/changelog.md` / `LOGS.md` / `log_usage.js` と `log_usage.mjs` の2重実装 | legacy / changelog / LOGS は移植せず（CHANGELOG.md を v1.0.0 から新規開始）。`log_usage.mjs` は ESM 環境向けとして同梱 |

---

## Key Rules

- 規定を追記するときは machine-readable authority にだけ判定値を置き、本ファイルには所在と意味だけを追記する。
- 参照側から正本を指すときは相対リンクを張り、値そのものを再掲しない（再掲すると drift の起点になる）。
- 数値を変更するときは対応する spec/script を先に更新し、その後で本索引の意味説明と parity test を追従させる。
- 散文と判定が食い違った場合は spec/script の判定を実行結果とし、散文側を drift として修正する。
