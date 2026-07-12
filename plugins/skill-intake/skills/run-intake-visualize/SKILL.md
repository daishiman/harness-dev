---
name: run-intake-visualize
description: ヒアリング結果に図解を配置したいとき、Mermaid 12 と独自 SVG 8 から各セクションに 1〜3 図を選択して visuals.json と PNG を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.1.0
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成された output/<hint>/visuals.json が schemas/output.schema.json 準拠(additionalProperties:false, items 1-3)かつ scripts/verify-visuals.py exit 0 で、§0〜§11 全 12 セクションに 1〜3 図が配置され、type=svg の全エントリが workspace 相対 png_path の実在 PNG を保有する
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: visuals.json の全 figure_id が Mermaid 12 + SVG 8 のカタログ id 集合に包含され(カタログ外創作ゼロ)、同一 sheet.md+purpose.json で 2 回連続実行した (section→figure_id) が完全一致する(determinism)
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 本スキルが「カタログ既存図の決定論的配置と PNG 配置 (SVG は同梱 PNG、Mermaid は mmdc)」に責務を絞り、カタログ外の図種創作・sheet.md にない事実の図注入(誤情報生成)を行わず、新規図種が必要な場合は創作せず差し戻す設計になっている
      verify_by: elegant-review
---

# run-intake-visualize

## Purpose & Output Contract

Phase 7 (intake aggregator) 担当。`sheet.md` + `purpose.json` + `options.json` を読み、Mermaid 12 種 + SVG 8 種のカタログから §0〜§11 の各セクションへ 1〜3 図を**決定論的に**配置し、SVG は同梱済み PNG (`assets/cvis-*.png`) を配置して Notion 互換化する。各 Phase の機械可読定義は `workflow-manifest.json`、責務別プロンプトは `prompts/R1-main.md` (R1-deterministic-figure-placement)、データ契約は `schemas/output.schema.json` を参照。

**入力**: `sheet.md`, `purpose.json`, `options.json`, アセットカタログ (`plugins/skill-intake/assets/`)
**出力**:
- `output/<hint>/visuals.json` (`schemas/output.schema.json` 準拠、section → [{figure_id, type, png_path}])
- `output/<hint>/visuals/*.png` (PNG 群)

**完了条件**: 全 12 セクションに 1〜3 図配置 + `scripts/verify-visuals.py` PASS + カタログ外 figure_id ゼロ + 同入力 2 回連続実行で visuals.json が完全一致 (determinism)。

## Key Rules

1. **カタログ外創作禁止**: Mermaid 12 + SVG 8 の `figure_id` 集合外は採用しない (R1 不変ルール / Layer 1.1)。違反時 exit 2。
2. **SVG は同梱済み PNG を配置**: Notion は SVG ネイティブ非対応。静的 SVG 8 種は事前レンダリング済み `plugins/skill-intake/assets/cvis-*.png` を `plugins/skill-intake/scripts/render_to_image.py` (bundled-copy、外部依存ゼロ) 経由で配置し、Mermaid は同スクリプトが mmdc で PNG 化する。cvis SVG/PNG は固定資産であり、改版時は `catalog_version` と同期して SVG/PNG を両方更新する (stale parity 防止)。
3. **図数 1〜3 上限**: 1 セクション 4 図以上は過剰可視化として禁止 (`schemas/output.schema.json` maxItems=3)。
4. **倫理ガード**: `sheet.md` にない事実を図に注入しない (誤情報生成防止、Layer 1.2)。
5. **図解マスト 8 ルール強制**: `references/visualization-mandatory-pointer.md` 経由で aggregator 正本ルールを適用。
6. **決定論性**: LLM はカタログ照合のみ、context-fork 不要。同入力で出力一致。

## ゴールシーク実行

### ゴール (Goal)

`sheet.md` + `purpose.json` + `options.json` を入力に、全 12 セクション (§0〜§11) へ Mermaid 12 + SVG 8 カタログ既存図を 1〜3 図ずつ決定論的に配置し、Notion 互換 PNG と `visuals.json` (`schemas/output.schema.json` 準拠) を生成し、`verify-visuals.py` が PASS した状態にする。

### 目的・背景 (Why)

intake aggregator は最終 Notion 公開前に「全セクション 1 図以上」の網羅性を要求する (図解マスト 8 ルール)。図解の創作は誤情報注入リスクが高く、また Notion は SVG ネイティブ非対応であるため PNG 化が必須。固定手順では入力 §の充足度・カタログ照合の失敗・PNG 生成失敗など実行時文脈に脆く、未充足条件を都度埋めるゴールシーク方式が要る。LLM はカタログ照合のみで創作を行わないため context-fork 不要、ただし網羅・整合・決定論の三条件は機械検証する。

### 完了チェックリスト (Checklist)

- [ ] `visuals.json` が `schemas/output.schema.json` に validate (additionalProperties:false 含む)
- [ ] 全 12 セクション (§0〜§11) に 1〜3 図が配置 (4 図以上ゼロ、ゼロ図ゼロ)
- [ ] `visuals.json` の全 `figure_id` が Mermaid 12 + SVG 8 カタログ id 集合に包含 (カタログ外創作ゼロ)
- [ ] `type=svg` の全エントリが対応 PNG (`output/<hint>/visuals/*.png`) を保有し、`png_path` は workspace 相対
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/run-intake-visualize/scripts/verify-visuals.py output/<hint>/visuals.json output/<hint>/visuals/` が exit 0 (網羅性・整合性 PASS。第 1 引数=visuals.json、第 2 引数=PNG 出力 dir、両方必須)
- [ ] 同 `sheet.md` + `purpose.json` で 2 回連続実行し `(section → figure_id)` が完全一致 (determinism)
- [ ] `sheet.md` にない事実が図へ注入されていない (倫理ガード、Layer 1.2)
- [ ] `references/section-figure-mapping.md` の §×図種対応表に基づく配置で、逸脱は理由付き

### ゴールシークループ

1. **現状評価**: `visuals.json` 既存内容と `verify-visuals.py` 出力を読み、Checklist の未達項目を列挙。
2. **手順生成**: 未達項目ごとに解消手順を立案 (例: §5 図ゼロ → mapping 表参照 → カタログから該当 figure_id を選択 / SVG エントリに PNG なし → `render_to_image.py` 起動)。
3. **実行**: prompts/R1-main.md R1 に従い決定論的にカタログ照合→`visuals.json` 更新→`render_to_image.py` で PNG 化。
4. **検証**: `verify-visuals.py` 起動 + schema validate + 2 回連続実行 diff で determinism 確認。
5. **反復**: 全 Checklist 充足まで戻る。カタログに該当図が無い場合は Key Rule 1 に従い exit 2 で停止しエスカレーション (LLM が勝手にカタログ拡張しない)。

各 Phase (`P1-section-scan` / `P2-select` / `P3-render` / `P4-emit`) の `dependsOn` / `entryHook` / `exitHook` / `fatal_exit_codes` は `workflow-manifest.json` 参照。

## Gotchas

1. **PNG 1 枚欠落で全体停止**: 後続 Phase 10 (Notion 公開) が All-or-Nothing で fail する。本スキル内で全 PNG 生成を保証してから完了とする。
2. **カタログ拡張は別 phase**: 新規図種が必要な場合は本スキルで創作せず TODO 起票し aggregator/設計側へ差し戻し (Key Rule 1)。
3. **並列書込み衝突**: セクション単位で並列化可能だが PNG 書込みパスの衝突回避必須 (Layer 6.2)。`output/<hint>/visuals/<section>-<figure_id>.png` のように一意化。
4. **絶対パス漏出**: `png_path` は workspace 起点の相対パスで記録 (Layer 4.3)。
5. **render_to_image.py のパス**: 正本は `plugins/skill-intake/scripts/render_to_image.py` (aggregator 共有)。本スキル `scripts/` 配下ではない。
6. **mapping 表の正本**: `references/section-figure-mapping.md` は薄い pointer。詳細スコアは `plugins/skill-intake/references/mermaid-visualization-guide.md`。

## Additional Resources

`references/resource-map.yaml` を最初に読む (機械可読 read_when 一覧)。主要参照:

- `workflow-manifest.json` — P1-section-scan / P2-select / P3-render / P4-emit の機械可読定義
- `prompts/R1-main.md` — R1-deterministic-figure-placement (7 層プロンプト、Layer 1-7)
- `schemas/output.schema.json` — `visuals.json` の正本スキーマ (additionalProperties:false, items 1-3)
- `references/section-figure-mapping.md` — §0〜§11 と Mermaid/SVG 図種の対応表 (aggregator guide.md への pointer)
- `references/visualization-mandatory-pointer.md` — 図解マスト 8 ルールへの参照ガイド
- `scripts/verify-visuals.py` — visuals.json + PNG 群の網羅性/整合性検証
- 上流: `plugins/skill-intake/scripts/render_to_image.py` (Mermaid→PNG + SVG 同梱 PNG 配置の共有スクリプト)
- 上流: `plugins/skill-intake/assets/` (Mermaid 12 + SVG 8 カタログ正本)
- 呼出元: `run-skill-intake` Phase 7 (P7-visualize) / 後続: Phase 8 (P8-summary, `skill-intake-summarizer`)
