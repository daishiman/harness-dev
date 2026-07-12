---
name: assign-notion-fidelity-evaluator
description: Notion ページを描画する直前に粒度を検証したいとき、info-collector-agent ページと同等の section 充足度を section_canonical_map 基準で機械検証したいときに使う。
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
kind: assign
user-invocable: false
context: fork
effect: conversation-output
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: template-change
hierarchy_level: L1
rubric_refs: [ref-output-routing]
role_suffix: evaluator
owner: team-platform
since: 2026-05-22
version: 0.1.0
responsibility_refs:
  - prompts/R1.md
  - prompts/R2.md
  - prompts/R3.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-notion-fidelity.py が granularity_score を char_bounds 30%(section_text_length 計測値・json.dumps 長でない)+ required_fields 充足 40% + viz_slots(mandatory=true のみ)30% で算出し、overall_score を fidelity-check-rules.md の閾値 pass≥0.85/warn≥0.70/fail<0.70 で verdict 判定して exit 0/1/2 を返す決定論が test/script で機械検証できる
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 生成される output/<hint>/fidelity-report.json が schemas/output.schema.json に適合し sections[].present/granularity_score/missing_slots/excess_slots と overall_score/verdict を必ず保持し、verdict=fail(exit 2)でも fidelity-report.json/.md を空でなく書き出す(fail-fast ≠ silent-fail)
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 本スキルが構造粒度の fidelity 検証に責務を単一化し、canonical を section_canonical_map.json からの派生スナップショット(手書き禁止)のみで参照、intake 内容妥当性・スキーマ存在検査・Notion API 経由公開へ越境せず JSON 構造比較のみ(認証情報不保持)を貫く設計になっている
      verify_by: elegant-review
---

# assign-notion-fidelity-evaluator

## Purpose & Output Contract

intake-final-context.json を Notion へ描画する**前後**に、`info-collector-agent` (Notion page_id=35195d6503b781788e31f59b4e05e705) と同等の構造粒度・再現性が保たれているかを機械検証する fidelity ガード。Notion API を叩かず、**`references/canonical-page-snapshot.json` との JSON 構造比較のみ**で公開前 (pre-publish) / 公開後 (post-publish 差分) の双方を判定する。

- **入力**: `intake-final-context.json` + `references/canonical-page-snapshot.json` (派生元として `references/section_canonical_map.json` を参照)
- **出力**: `output/<hint>/fidelity-report.json` … `sections[].present/granularity_score/missing_slots/excess_slots` と `overall_score`, `verdict ∈ {pass, warn, fail}`
- **副次出力**: `output/<hint>/fidelity-report.md` (R3 delta-report, 人間可読)
- **完了条件**: `verdict=pass` のときのみ呼び出し元 (`render_notion_page.py`) が公開を許可する。`fail` は exit 2、`warn` は exit 1、`pass` は exit 0。fail でも JSON/MD は必ず書き出す (fail-fast ≠ silent-fail)。

## Key Rules

1. **責務単一: 構造粒度のみ**: 公開前/後の fidelity (再現性・差分) 検証に専念。intake 内容妥当性は `run-skill-intake` に、スキーマ存在検査は `intake.schema.json` に、Notion API 経由公開は `run-notion-intake-publish` / `render_notion_page.py` に委譲する。
2. **Canonical SoT は section_canonical_map.json**: 12 section の `required_fields / char_bounds / viz_slots` は aggregator 配下を一次正本とし、本スキルは **派生スナップショット** (`references/canonical-page-snapshot.json`) を保持する (DRY)。手で snapshot を書かない。
3. **Notion API 直接呼び出し禁止**: 検査は JSON 構造比較のみ。API 認証情報は本スキルでは扱わない。
4. **Fail-fast**: `verdict=fail` で exit 2、呼び出し元は即停止すること。
5. **Script First**: 全判定は `scripts/*.py` (Python 3, jsonschema/jinja2 許容) で決定論実行。
6. **300 行制約**: SKILL.md は 300 行以下。詳細ルールは `references/` に分割し、`when_to_read` で誘導 (Progressive Disclosure)。
7. **命名規約**: 全 script ファイル名はハイフン区切り (28 章 §4.3, no underscore)。
8. **評価ルブリック**: granularity score (0-100) は char_bounds 一致 30% + required_fields 充足 40% + viz_slots 一致 30%。詳細は `references/granularity-rubric.md`、verdict 閾値 (pass≥0.85 / warn≥0.70 / fail<0.70) は `references/fidelity-check-rules.md`。
9. **viz_slots は mandatory=true のみ評価**: `mandatory=false` は missing でも減点しない (warn 列にのみ記録)。

## ゴールシーク実行

### ゴール (Goal)

`intake-final-context.json` が canonical-page-snapshot.json と同等粒度を保ち、`output/<hint>/fidelity-report.json` (`verdict ∈ {pass, warn, fail}`, `overall_score`, section 別 missing/excess) と `fidelity-report.md` (delta-report) が生成され、公開直前 (pre-publish) フックおよび公開後 (post-publish) 差分検証で `verdict=pass` のみ呼び出し元へ通過させた状態になっている。

### 目的・背景 (Why)

Notion 公開パイプラインは API 経由で行われるため、intake-final-context.json と canonical ページの section 粒度がずれると、後段の人間レビューで「再現性が無い」「情報が欠落した」と判明し戻り工数が発生する。Notion API 認証を伴わずに JSON 構造比較のみで決定論的に判定することで、公開前のフェイルファスト停止と、公開後の差分検知 (canonical 更新時の追従漏れ検出) を低コストで両立させる。固定手順では canonical 更新タイミング・char_bounds の計測対象差異・viz_slots の mandatory 区分など実行時文脈で揺れるため、未達観点を都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `section_canonical_map.json` (v2 以降) が変更された場合、`scripts/extract-canonical-snapshot.py` を再走させ `references/canonical-page-snapshot.json` が最新派生に更新されている (手書き禁止)
- [ ] `scripts/validate-notion-fidelity.py <intake-final-context.json>` が exit 0/1/2 のいずれかで完了し、`output/<hint>/fidelity-report.json` が生成されている (fail でも JSON/MD 出力必須)
- [ ] `fidelity-report.json` が `sections[].present / granularity_score / missing_slots / excess_slots` と `overall_score`, `verdict` を保持し、`schemas/output.schema.json` 準拠である
- [ ] char_bounds は `scripts/validate-notion-fidelity.py` 内 `section_text_length()` で計測した本文相当文字数を使用 (json.dumps 長ではない)
- [ ] required_fields[] が context.json に全て存在し型整合 (granularity score の 40% を充足)
- [ ] viz_slots は `mandatory=true` のみで減点判定、`mandatory=false` 欠落は warn 列に記録のみ
- [ ] verdict 判定が `references/fidelity-check-rules.md` の閾値 (pass≥0.85 / warn≥0.70 / fail<0.70) と一致し、pass のみ呼び出し元 (`render_notion_page.py`) が公開許可
- [ ] `verdict=fail` で exit 2、`warn` で exit 1、`pass` で exit 0 が返り、fail/warn でも `fidelity-report.md` (R3 delta-report) が人間可読で書き出されている
- [ ] 公開後の差分検証 (post-publish) として `scripts/extract-granularity-score.py` で overall_score (0-100) を取得し CI メトリクスに記録 (optional だが canonical 更新追従漏れ検知の根拠となる)
- [ ] Notion API 認証情報を本スキル内で扱っていない (構造比較のみ)
- [ ] R1 (canonical-snapshot-extraction) / R2 (fidelity-check) / R3 (delta-report) の 7 層 prompt (`prompts/R1.md` / `R2.md` / `R3.md`) と整合した出力になっている

### ゴールシークループ

`references/fidelity-check-rules.md` と `references/granularity-rubric.md` の評価観点に従い、未達観点をゲートとみなして都度埋める。本スキル固有の差分:

- **未達評価の単位は section**: 12 section 各々で `granularity_score` を算出し、`overall_score` 未達なら不足 section の R3 delta-report を根拠に context.json 側を埋めて再走する。
- **差し戻し**: `verdict=fail` (exit 2) で呼び出し元を即停止。`warn` (exit 1) は呼び出し元判断に委ねるが、`fidelity-report.md` の改善示唆を必ず提示する。
- **canonical 更新追従**: `section_canonical_map.json` が更新されたら必ず `extract-canonical-snapshot.py` を再走 (template-change audit-trigger)。snapshot 手書き禁止。
- **API 呼び出し禁止**: 検証は JSON 構造比較のみ。Notion API 認証情報を要する処理は `run-notion-intake-publish` 側に委譲。
- **fail-fast ≠ silent-fail**: exit 2 でも JSON/MD は必ず書き出し、呼び出し元が原因を読めるようにする。

### 実行コマンド (要点)

```bash
# canonical snapshot 再生成 (template-change trigger 時のみ)
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/assign-notion-fidelity-evaluator/scripts/extract-canonical-snapshot.py \
  --source plugins/skill-intake/references/section_canonical_map.json \
  --out    plugins/skill-intake/skills/assign-notion-fidelity-evaluator/references/canonical-page-snapshot.json

# fidelity check (公開直前フック)
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/assign-notion-fidelity-evaluator/scripts/validate-notion-fidelity.py <intake-final-context.json>
# exit 0 = pass / 1 = warn / 2 = fail

# 粒度スコア単体取得 (CI メトリクス用)
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/assign-notion-fidelity-evaluator/scripts/extract-granularity-score.py <intake-final-context.json>
```

## Gotchas

1. **canonical の更新タイミング**: `section_canonical_map.json` (v2) が変わったら本スキルの `extract-canonical-snapshot.py` を再走させる。手で snapshot を書かない。
2. **char_bounds の計測対象**: Notion ブロック化前の context.json 上での該当 section の本文相当文字列 (json.dumps の長さではない — `scripts/validate-notion-fidelity.py` 内の `section_text_length()` を使用)。
3. **viz_slots は mandatory=true のみ評価**: `mandatory=false` は missing でも減点しない (warn 列にのみ記録)。
4. **fail でも report.md は出力する**: 呼び出し元が原因を読めるよう、exit=2 でも JSON/MD は必ず書き出す (fail-fast ≠ silent-fail)。
5. **Notion API 直叩き禁止**: 認証を要する処理は `run-notion-intake-publish` 側へ。本スキルは構造比較のみ。
6. **責務逸脱禁止**: intake 内容妥当性 (5 軸 / true_purpose 等) は aggregator、スキーマ準拠は `intake.schema.json` に委譲。本スキルは粒度差分のみ。

## Additional Resources (Progressive Disclosure)

| 用途 | パス | when_to_read |
|---|---|---|
| 責務別 prompt (R1: canonical-snapshot-extraction) | `prompts/R1.md` | aggregator の `section_canonical_map.json` から派生スナップショットを生成する手順を確認するとき |
| 責務別 prompt (R2: fidelity-check) | `prompts/R2.md` | context と canonical の section 粒度比較・verdict 判定ロジックを確認するとき |
| 責務別 prompt (R3: delta-report) | `prompts/R3.md` | missing/excess/granularity_warnings を Markdown と exit code に変換するとき |
| 正本構造マップ | `references/canonical-page-snapshot.json` | 各 section の required_fields / char_bounds / viz_slots を参照するとき |
| スコア算出ルール | `references/granularity-rubric.md` | 0-100 score の重み付け (char_bounds 30% / required 40% / viz 30%) を確認するとき |
| verdict 閾値 | `references/fidelity-check-rules.md` | pass/warn/fail の境界とエスカレーション規約を確認するとき |
| 量産規約 | `references/abstraction-contract.md` | `canonical_page_id` / `canonical_snapshot_path` / `fidelity_threshold_pass` / `fidelity_threshold_warn` 等のテンプレ変数を差し替えるとき |
| Progressive Disclosure 地図 | `references/resource-map.yaml` | references 全体の読み順を確認するとき |
| 機械可読フロー定義 | `workflow-manifest.json` | Step/Gate/Phase の entryHook/exitHook/dependsOn を確認するとき |
| 出力スキーマ | `schemas/output.schema.json` | `fidelity-report.json` の必須キーを確認するとき |

### 関連スキル

- `run-skill-intake` — canonical SoT (`references/section_canonical_map.json`) の所有者
- `run-notion-intake-publish` — 本スキルを公開直前フックとして呼ぶ sibling (API 経由公開を担当)
