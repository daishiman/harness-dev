---
name: component-domain
description: 「プラグイン」を 5 種の component_kind へ写像する対象ドメイン定義と用語集。2 軸直交 (ファイル軸=phase / build 軸=component-inventory) と buildable 実体数 N 導出の正本として読む。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# 対象ドメイン定義: プラグイン = 5 種の buildable component_kind × N 実体 + plugin-level surfaces (§4 / §12)

> パス表記: 本書の絶対パスはすべて harness repo root 相対。

## 中心原則: 2 軸直交 (ファイル軸 = phase / build 軸 = component-inventory)

per-phase 転換の中核 SSOT。plan は**直交する 2 軸**を単一 SSOT + 複数 projection で持つ:

- **ファイル軸 (人間・ライフサイクル)** = 13 フェーズ。各フェーズ = 1 Markdown `phase-NN-<kebab>.md` (上から順に読める宣言型タスク仕様 (8 節)=primary deliverable)。本数は **13 固定** (フェーズ数)。
- **build 軸 (機械・成果物実体)** = N 個の buildable component (skill / sub-agent / slash-command / hook / script)。**`component-inventory.json` が唯一の SSOT** (build routing・1 実体=1 `build_target`・依存 DAG・品質機構=旧 C*.md frontmatter の載せ替え先を保持)。

両軸は build_target/depends_on を二重に持たない (正規化): build 情報は inventory のみが持ち、phase ファイルは `entities_covered: [C01, ...]` の id 参照だけで component に紐づく。

### shadow-tree 同型 (二層に分離)

「plan は対象プラグイン `plugins/<slug>/` の将来ツリーの shadow」という同型を**二層**に分ける:

| 層 | 1:1 対応 | SSOT |
|---|---|---|
| **build 層** | buildable 実体 ⇔ 1 `build_target` ⇔ inventory の `components[]` 1 エントリ | `component-inventory.json` |
| **ファイル層** | 13 フェーズ ⇔ 13 `phase-NN-<kebab>.md` ⇔ index の 1 行 (phase_number 昇順) | `index.md` + phase files |

build 層の N (実体数) は対象プラグインの実体数の射影 (input でなく output)。ファイル層の 13 はフェーズ数で固定であり、N とは独立に決まる。

### 5 種 (分類軸) と N (実体数) は別軸

**混同厳禁**: 「5」と「N」は直交する別軸。

- **5 = component_kind の分類軸** (skill / sub-agent / slash-command / hook / script)。R2 は 5 種すべてを検討軸として `considered_component_kinds` に**全列挙**する (検討証跡)。
- **N = buildable 実体の数** (= inventory `components[]` 件数)。各 capability 実体をいずれかの kind へ写像し、**同一 kind に複数実体があれば各実体を独立 component にする**。N は kind 数 (5) でもフェーズ数 (13) でもなく、対象プラグインの実体数の射影であり、実プラグインでは skill 複数・sub-agent 複数・slash-command 複数… を自然に含み **10 実体超になる**。

## 5 種の buildable component_kind (物理アーティファクト種別・分類軸)

plugin が生成し得る**buildable な capability 種別**。`skill-brief.schema.json#placement_candidates` enum (`Skill`/`Subagent`/`Agent Team`/`Hook`/`MCP`/`CLI`/`API`/`script`) とは**対応するが別軸**: placement_candidates は「能力をどこに置く候補か」(brief の判断材料・casing も大文字)、本 5 種は「実際に生成する capability ファイルの種別」。両者を同一視しない。R2 は 5 種すべてを `considered_component_kinds` で検討済みにし、実際に必要な**各実体**を `components[]` へ写像する (同一 kind 複数実体可)。`components[]` の件数が **N (buildable 実体数)** の導出根拠になる。

| 構成要素 | 定義 | 実体例 |
|---|---|---|
| **skill** | `SKILL.md` 入口の能力単位 (kind ∈ run/ref/wrap/assign/delegate) | `run-skill-create` |
| **sub-agent** | `agents/*.md`、独立 context | `assign-skill-design-evaluator` |
| **slash-command** | `commands/*.md` | `/install-bundle` |
| **hook** | `plugin.json`/`settings.json` 配線スクリプト | `preflight-git-commit.py` |
| **script** | `scripts/*.py`、決定論処理 | `validate-build-trace.py` |

→ §8 P02 (設計・phase-lifecycle.md) で構想に対しこの 5 種を検討し、必要な**各実体**を component として kind/prefix/hierarchy/pattern 確定する。実体数が N であり、N は固定 (13 等) でも「5 種を 1 本ずつ」でもなく、対象プラグインの実体数に依存して変動する。

### component 粒度 (script の畳み込み・P02)

「1 実体 = 1 component」と no-split threshold (第二消費者/機械検証/280 行超の無い分割を避ける) は `build_target` を軸に両立する:

- **独立 builder を持つ kind** (skill / sub-agent / slash-command / hook) は、各実体を**必ず独立 component** にする (skill が 3 本なら skill component 3 本)。これらは各々が固有の `build_target` (実ファイル/ディレクトリ) を持つ。
- **builder を持たない script** (`run-build-skill` に script kind は無く親 skill の付随物) は、**複数 skill 共有・独立検証あり・280 行超**のいずれか (no-split threshold) を満たす時のみ独立 component に昇格する。単一 skill 専用 script は親 skill の build へ**畳み込み** component にしない (11 個の専用 script を 11 component に割る水増しを防ぐ)。
- **水増し (padding) の定義は「実体数が多い」ことではなく、`build_target` を持たない/重複する/到達不能な component の存在**。各 component が唯一の実 `build_target` に写像する限り、実体数が多いこと自体は正しい帰結であり善 (`detect-unassigned.py` が build_target 非空を fail-closed 強制する)。

## plugin-level surfaces (個別 component_kind に押し込まないが必須確認する面)

| surface | 実体例 | 記録先 |
|---|---|---|
| **plugin manifest** | `.claude-plugin/plugin.json` | `index.md` の `plugin_meta.manifest` |
| **plugin composition** | `plugin-composition.yaml` | `index.md` の `plugin_meta.pkg_contract` / `component-inventory.json` |
| **harness/eval** | `EVALS.json`, `eval-log/coverage/**` | `index.md` の `plugin_meta.ci` / `harness_coverage` |
| **references/config/assets** | `references/**`, `config/**`, `assets/**` | component の references または `plugin_meta.ssot_dedup` |
| **schemas** | `schemas/**` (JSON Schema 契約) | component の schemas または `plugin_meta.ssot_dedup` |
| **vendor** | `vendor/**` = cross-plugin SSOT の byte 同一複製 (携帯性のための vendoring) | `plugin_meta.ssot_dedup` |
| **MCP/app connector** | `.mcp.json`, `.app.json` | `plugin_meta.manifest` と `component-inventory.json` |
| **notion_config** | 設置先 repo-root `.notion-config.json` (DB ID 供給・gitignore)。plan は DB キーのみ宣言し解決は `notion_config.py` の名前参照 | `plugin_level_surfaces.notion_config` + `plugin_meta.feedback_deploy.notion_sink` (契約は `io-contract.md` §9) |

これらは component エントリの `component_kind` ではない。欠落すると plugin として不完全になるため、R2/R3 で要否を判定し、不要なら `plugin_level_surfaces.<surface>.omitted_reason` に理由を残す。省略理由のキーは `omitted_reason` 一本のみ (評価器が読むのもこのキーのみ)。

### placement_scope (配置境界・install 携帯性 / F8)

component は `component_kind` (分類軸 5 種) と直交する属性 `placement_scope ∈ {"skill", "plugin-root"}` を持つ (既定 `skill`)。**これは新 component_kind ではなく既存 script の配置属性**であり、builder 写像 (`specfm.builder_for`) が消費する:

| placement_scope | 意味 | build_target | builder |
|---|---|---|---|
| `skill` (既定) | 当該 skill 配下に畳み込む専用 script | `plugins/<slug>/skills/<skill>/scripts/<name>.py` | `parent-skill-build` |
| `plugin-root` | 複数 skill が共有する script を `plugins/<slug>/scripts/` へ hoist | `plugins/<slug>/scripts/<name>.py` | `plugin-scaffold` |

- **plugin-root は script のみ**許可する (skill/sub-agent/slash-command/hook は各自の deploy 面を持つため対象外)。
- **≥2 skill consumer の script は plugin-root 必須**。deploy 境界の内 (skill 配下) / 外 (plugin-root) が dangling 可否を決める (発見方法でなく境界が本質)。共有 script を単一親 skill 配下に固定すると symlink 共有や単独 install で第二 consumer 側から辿れず dangling するため。この強制は `check-runtime-portability.py` が行う。
- cross-plugin SSOT (別 plugin と共有する SSOT) は **vendoring (byte 一致複製)** か **self-derive fail-soft loader** で携帯性を担保する (先行事例 skill-intake / harness-creator の lint-runtime-portability)。plugin 内共有で足りる場合は plugin-root への hoist で十分 (vendoring 不要)。
- component_kind は 5 種のまま (placement_scope は属性であって第 6 の kind ではない)。builder 写像を壊さない。

## 用語集 (§12)

| 用語 | 定義 |
|---|---|
| plugin | skill/sub-agent/slash-command/hook/script と plugin-level surfaces の集合・配布単位 |
| plugin manifest | `.claude-plugin/plugin.json`。plugin root の物理契約であり、folder name と `name` が一致する |
| marketplace | `.claude-plugin/marketplace.json` (repo/team marketplace)。plugin の表示順・install/auth policy・category を定義する |
| skill | `SKILL.md` 入口の能力単位。kind ∈ {run,ref,wrap,assign,delegate} |
| sub-agent | `agents/*.md`・独立 context |
| slash-command | `commands/*.md` |
| hook | `plugin.json`/`settings.json` 配線スクリプト |
| script | `scripts/*.py`・決定論処理 |
| phase ファイル | 本スキル(L2)が出力する 1 フェーズ=1 Markdown (`phase-NN-<kebab>.md`)・上から順に読める宣言型タスク仕様 (8 節・L3 ファイル軸) |
| component | `component-inventory.json` の `components[]` 1 エントリ (L3 build 軸)・`run-skill-create`/`run-build-skill` 投入可能粒度・1 実体=1 `build_target` |
| フェーズ | プラグイン開発ライフサイクルの 1 段階 (§8 P01-P13)。従来 Phase 1-13 を写像した 13 フェーズ |
| name(slug) | 機械識別子 (例 `run-plugin-dev-plan`)・lint で形式検証 |
| displayName | 人間向け表示名・slug と区別 |
| 依頼書 | `run-skill-create` への入力 (skill-brief 相当) |
| TDD (本文脈) | Red=未達 criteria/チェックリスト項目、Green=goal-seek ループで充足し lint/test/verdict exit0/PASS (vitest でなく pytest harness-coverage) |
| N | buildable 実体の数 = inventory `components[]` 件数。kind 数 (5) でもフェーズ数 (13) でもなく、同一 kind 複数実体を含む実体数の射影 (input でなく output) |

## 4 層分離 (root cause「作成する」混線の解消)

| 層 | 内容 |
|---|---|
| L0 | プラグイン構想 (本スキルへの入力) |
| L1 | 道具 `run-skill-create` (既存) |
| L2 | 本スキル `run-plugin-dev-plan` (計画を生成する) |
| L3 | 13 phase files + index + `component-inventory.json` (L2 を実行して作る)。ファイル軸=phase、build 軸=inventory の 2 軸。index は manifest/marketplace/cachebuster/validation 契約を `plugin_meta` に持つ |
| L4 | 実プラグイン (L3 の各 inventory component を L1 に投入して作る) |

本スキルは L3 までを担い、L4 (実 build) は各 inventory component を `run-skill-create`/`run-build-skill` へ委譲する。実コードは生成しない。
