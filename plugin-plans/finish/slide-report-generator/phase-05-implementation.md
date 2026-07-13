---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 23 buildable component を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす(Green)状態にする。あわせて vendor surface(Node engine 一式)を byte 携行で plugin へ配置する。build routing は `component-inventory.json` の依存 top-sort 順に実行する(phase 順 ≠ build 順)。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る(worker 群 + 共有 script → orchestrator skill → hook/command)。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果(到達状態)を宣言する。Node engine は Python 化せず vendor として byte コピーし、skill/agent は Bash(node *) で起動する。

## 前提条件
- P04 で C01/C02/C03 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている(worker sub-agent C04-C19 + 共有 script C23 → skill C01/C02/C03 → hook C20 → command C21/C22 の依存順)。
- 後段 builder(run-skill-create / run-build-skill / plugin-scaffold)が利用可能。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順(依存先が常に先。phase 番号順ではない)。
- vendor 携行の実装規律: Node/CJS 製エンジンは byte 維持で plugin の vendor へ配置し、node_modules は install 時に再取得する。stdlib script へ書き換えない。
- 共有 script hoist: validate-output-mode.py(C23)は builder=plugin-scaffold で plugins/slide-report-generator/scripts/ 直下へ実体化する(単一 skill 配下に退化させない)。
- Green 判定の主体は P04 で固定した criteria(実装が判定基準を都合よく再定義しない)。

## 成果物
- 全 23 component の実体(skills/agents/commands/hooks/scripts)が build_target に生成された状態。
- vendor surface(Node engine + 118 templates + package.json)が byte 携行で配置された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest(後段 scaffold owner)。

## スコープ外
- カバレッジ拡充・テスト網羅(P06)。
- purpose 受入判定(P07)・SSOT 重複整理(P08)。
- builder 自体の改修(harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [ ] 依存 top-sort 順に全 23 component が build され、skill loop の criteria が Green(受入テスト PASS)になる。
- [ ] build 実体パスが inventory の build_target と一致する。
- [ ] vendor Node engine が byte 携行で配置され Python 化されていない(skill/agent が Bash(node *) で起動する)。
- [ ] 共有 script C23 が plugin-root へ実体化されている(単一 skill 配下に退化していない)。
- [ ] 実行環境 preflight (node --version / npm ci 成功 / playwright browser 取得 / codex exec 疎通※画像生成使用時) が exit0 (C23 validate-output-mode.py --preflight)。

## 参照情報
- `handoff-run-plugin-dev-plan.json`(build routing)/ `component-inventory.json`(依存 DAG)。
- 対象 component C01-C23、vendor surface。
- 後続 P06(test-run)。
