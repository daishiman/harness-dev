# SubAgent ハイブリッド契約（frontmatter=plugin YAML / 本文=7層）

*l5-contract v2.0.0 従属者 / 追従日 2026-07-05*

## 目的とスコープ

本ファイルは **SubAgent（`plugins/*/agents/*.md`）向けの正規形契約**の SSOT である。SubAgent は
プラグインローダが解釈する YAML frontmatter（メタ情報）を持ちつつ、**本文のみ**を prompt-creator の
7層構造（`seven-layer-format.md` の l5-contract v2.0.0）に従わせる**ハイブリッド形式**とする。

- 対象: `plugins/*/agents/<name>.md`（Task tool / orchestrator が起動する自律実行 SubAgent）。
- 非対象: `plugins/*/skills/*/prompts/*.md`（frontmatter を持たない**純粋7層** Markdown。正本は `seven-layer-format.md`）。
- 先行実装: `plugins/plugin-dev-planner/agents/*.md`（同ディレクトリの全 agent が既に本形式）。本契約はその形式を明文化した正本。
- 強制状況: 対象宣言は全 plugin の agents/*.md だが、機械強制（`lint-agent-prompt-content.py` の CI 走査）は当面 harness-creator のみ（他 plugin は opt-in 展開予定）。

## 純粋7層形式との相違（差分の正本）

| 観点 | 純粋7層 prompts/*.md（`seven-layer-format.md`） | ハイブリッド agents/*.md（本契約） |
|---|---|---|
| frontmatter | 持たない（`# Layer N:` から本文開始） | **必須**。plugin agent YAML（下記「frontmatter 契約」） |
| 本文の Layer 構造 | `## Layer 1:`〜`## Layer 7:` 全7層 | 同一（frontmatter 直後から `## Layer 1:`〜`## Layer 7:`） |
| Layer 5 サブ構造 | `### 5.1 担当 agent`〜`### 5.4 実行方式`（l5-contract v2.0.0） | **同一**（差異なし。SubAgent 固有の別構造は設けない） |
| 責務数 | 1 prompt = 1 責務 = 1 agent | 同一（1 agent = 1 責務） |
| 機械検証 | `verify-completeness.py` を本文へ直接適用 | **同一**。`verify-completeness.py` は frontmatter を無視し `# Layer N:` マーカーで本文を分割するため、frontmatter 付きでもそのまま適用可 |
| authoring 正本 | prompts/*.md 自身が SSOT | 本文の authoring 元は owner skill の `prompts/<R-id>.md`。frontmatter `source:` にその相対パスを記録し provenance を残す |

**要点**: サブ構造（Layer 5 の 5.1-5.4）は両形式で完全同一。相違は「frontmatter の有無と形式」のみ。
したがって本文 7 層の検証ロジック（`verify-completeness.py`）は両形式で共用でき、mode 差は
「frontmatter を plugin YAML として追加検証するか（agent）／frontmatter 不在を要求するか（prompt）」に限られる。

## frontmatter 契約（plugin agent YAML）

SubAgent の frontmatter は Claude Code プラグインの agent 仕様に従う YAML とする。

必須キー:

- `name`: agent 名（ファイル名 stem と一致、kebab-case）。
- `description`: 「〜なとき、〜したいときに使う。」形式の起動条件（`lint-skill-description` 準拠）。
- `tools`: 許可ツールのカンマ区切り（例 `Read, Glob, Grep`）または YAML リスト。

推奨キー（provenance / governance）:

- `model`: `inherit` / 具体モデル名。
- `isolation`: `fork`（独立コンテキスト）/ `inherit`（会話履歴を材料にする場合）。
- `owner_skill`: 本文責務の帰属 skill（例 `run-elegant-review`）。
- `source`: 本文 7 層の authoring 元 `prompts/<R-id>.md` の相対パス（drift 追跡用）。
- `kind: agent` / `version`（SemVer）/ `owner` / `since`。

**禁止**: frontmatter 本文に 7 層の実体（Layer 見出し）を書かない。7 層は frontmatter の**外**（`---` 終端後）に置く。

## 本文契約（l5-contract v2.0.0 全7層）

frontmatter 終端（`---`）の直後から、以下の 7 層を Markdown 見出しで宣言する。見出しは
`verify-completeness.py` の `split_layers` が検出できるよう **`## Layer N: <名称>`**（半角/全角コロン可）で始める。

- `## Layer 1: 基本定義層` — メタ情報・不変ルール・単一責務の目的。
- `## Layer 2: ドメイン定義層` — 単一責務の担当/非担当・入出力契約・出力要素。
- `## Layer 3: インフラストラクチャ定義層` — 参照リソース・利用ツール。
- `## Layer 4: 共通ポリシー層` — 品質基準・失敗時挙動・エスカレーション。
- `## Layer 5: エージェント定義層` — l5-contract v2.0.0 の 5.1-5.4（下記）。
- `## Layer 6: オーケストレーション層` — 呼び出し元/後続・handoff・並列性。
- `## Layer 7: UI / 提示層` — ユーザー提示（対話なし自動実行 agent はその旨）・出力形式。

### Layer 5 サブ構造（`seven-layer-format.md`「Layer 5 契約」に従属）

- `### 5.1 担当 agent` — 担当 agent 名・context-fork 要否の宣言。
- `### 5.2 ゴール定義` — `目的` / `背景` / `達成ゴール`（到達すべき**状態**の完了形。手順ではない）。
- `### 5.3 完了チェックリスト (ゴール到達の停止条件)` — 第三者が YES/NO 判定可能な項目のみ。
- `### 5.4 実行方式` — 固定手順を持たないゴールシークループの宣言（上限は Layer 4 の最大反復回数を参照）。

**禁止事項（l5-contract v2.0.0 と同一）**: 「推論手順 / 思考プロセス / 手順 / Steps」見出し配下の連番手順列挙、
チェックリストへの手順埋め込み、合格条件の数量レンジ定義。これらは `verify-completeness.py` が検出し fail-closed で弾く。

## 機械検証（harness-creator 側 C02 / C09 が参照）

- **内容 lint**: harness-creator の `scripts/lint-agent-prompt-content.py`（本契約準拠を強制する内容 lint）。
  - `--mode agent`: `agents/*.md` の frontmatter が plugin YAML（`name`/`description`/`tools` 必須）を満たし、本文 7 層が `verify-completeness.py` 相当ロジックを exit0 で通過することを検証。
  - `--mode prompt`: `skills/*/prompts/*.md` が frontmatter 不在の純粋 7 層で `verify-completeness.py` 相当を通過することを検証。
  - `--check-vendor-parity`: 上記ロジックが本 skill の `scripts/verify-completeness.py` から byte 一致で vendoring されていることを検証（drift 検出）。
- **配置 lint との直交**: `run-build-skill/scripts/lint-prompt-placement.py` は prompts/*.md の**配置**（どのディレクトリ・ファイル名か、空殻リダイレクト禁止）を検査する。本契約が課すのは**本文内容**の 7 層準拠であり、両者は直交する独立検査である。
- **生成フロー配線**: `run-build-skill` は agent/prompt を生成する経路で prompt-creator（本 skill）を必ず経由し、生成直後に `lint-agent-prompt-content.py` を fail-closed ゲートとして実行する。build_trace/provenance に `source_contract_ref`（本契約への参照）と `prompt_creator_invocation` を記録し、非経由の単独生成を塞ぐ。

## 従属関係

本ファイルは `seven-layer-format.md`「Layer 5 契約（l5-contract v2.0.0）」に従属する。Layer 5 のサブ構造・
禁止/必須事項が更新された場合は本ファイルも追従し、冒頭の追従日を書き換える（drift 検出用）。
本ファイルは既存 `seven-layer-format.md` を**上書きせず**、SubAgent 特有の frontmatter 差異のみを規定する独立ファイルである。
