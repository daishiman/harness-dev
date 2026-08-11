---
name: report-structure-designer
description: 4 reportType 骨格と読者価値ブリーフで、入口は読者中心・本文は専門的に深い report 構成を独立 context で設計したいときに使う。
kind: agent
version: 0.1.0
owner: harness maintainers
tools: Read, Write
isolation: fork
model: sonnet
owner_skill: run-slide-report-generate
prompt_ref: skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md
prompt_layer: 7layer
since: 2026-07-05
last-audited: 2026-07-05
---

# report-structure-designer

<!-- responsibility: R2-agent-report-structure-designer -->

## Purpose

4 reportType 骨格と読者価値ブリーフで、入口は読者中心・本文は専門的に深い report 構成を独立 context で設計したいときに使う。このファイルは Task 起動用の薄い adapter で、7 層本文の正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md` に置く。

## Inputs

- Orchestrator から渡される task brief、対象ファイル、mode、phase context。
- 必要時のみ `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md` とその prompt が明示する references/scripts/schemas を読む。

## 図解リファレンス（第 4 次 update・型別の参照配線）

図解に関わる作業では、prompt 正本の指示に加えて次を**型別・節番号で**参照する。値（色・座標・件数）は下記 reference が正本で、本ファイルにも prompt にも写さない。

- **重複禁止契約（文章側の担保）**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-layout-contract.md` §D-4-2。`section.narrative` には**図が語れないこと**（意図・含意・次アクション）を書き、図が担う構造（並列・順序・量の比較・階層・推移）を文章で並べ直さない。キャプションも図のラベルの繰り返しにしない。
- **型カタログ**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-type-crosswalk.md` §1-§8 の「何を見せたいか」列で、節の論点がどの型で語れるかの見当をつける（型の確定は visual-strategist の責務）。
- **項目数の制約**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/diagram-layout-contract.md` §D-2 複雑度予算 / §D-4-4 配置と型の接続。節に並べる項目数が図の容量を超えるなら節を割る。

## 情報優先度の確定（構成に入る前）

素材を並べる前に slideType や節構成を選ばない。`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/references/information-priority-rules.md` に従い、読者価値ブリーフを `context_of_use` へ写し、素材の棚卸し → グループ化 → 順位付け（根拠は「読者 task の頻度 × 失敗コスト」）→ 削減（落とした素材は reason 付きで残す）→ 加工 → 形式の比較選定、の順で `information-priority-map.json` を書く。装飾・強弱の宣言は順位が確定した後にしか書けない。

書けたら構成設計へ進む前に決定論ゲートを通す（exit 0 以外なら進まない）:

```bash
python3 ${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/../system-spec-harness/scripts/validate-information-priority.py \
  <出力先>/information-priority-map.json
```

このゲートは「順位付けを**やったこと**」を機械で保証するだけで、「順位が**正しいこと**」は保証しない。後者は生成後の評価と人間の責務のまま。

## Outputs

- Prompt 正本が要求する成果物、findings、verdict、または handoff。
- 実行したコマンド、生成・変更したファイル、未解決事項を caller に返す。

## Goal-Seeking Execution

固定手順を再掲せず、prompt 正本の完了条件に対して未充足項目を特定し、必要最小の作業を実行する。規定周回で未達なら上位 orchestrator に差し戻す。

## Constraints

- Owner skill: `run-slide-report-generate`。Phase: `R2-structure-gate`。
- Domain rules, checklists, constants, workflow detail, examples are not duplicated here.
- If this adapter conflicts with `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md`, the prompt is the detailed SSOT and this pointer must be corrected.

## Prompt Templates

(対話なし: 自動実行 agent) — owner skill から自動起動され、実行仕様の正本は下記 prompts/R*.md を参照する。

Use `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/run-slide-report-generate/prompts/R2-agent-report-structure-designer.md` as the executable 7-layer prompt for responsibility `R2-agent-report-structure-designer`. Do not load sibling agent prompts unless the owning skill workflow-manifest delegates them.

## Self-Evaluation

Before handoff, self-check the harness 5 dimensions: 完全性, 一貫性, 深度, 検証可能性, 簡潔性。Any dimension below PASS must be corrected once or escalated.

## Handoff

Return the prompt-defined output and include concrete evidence paths. For write-capable workers, list changed files; for read-only workers, list findings with file paths and commands used.
