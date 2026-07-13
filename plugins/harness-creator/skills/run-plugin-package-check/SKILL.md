---
name: run-plugin-package-check
description: plugin package を出荷前に検査したいとき、PKG-001〜015 gate を一括実行したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "<plugin-name> [--phase 0|1|2|all] [--pkg PKG-NNN,...] [--dry-run]"
arguments: [plugin, phase, pkg, dry-run]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(python3 *)
  - Bash(bash *)
  - Bash(claude plugin validate *)
  - Skill
model: sonnet
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-23
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md
source-tier: internal
last-audited: 2026-05-23
audit-trigger: quarterly
pair: assign-plugin-package-evaluator
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-orchestrate.md
  - prompts/R2-gate-decide.md
rubric_refs:
  - ref-pkg-contract
schema_refs:
  - schemas/run-report.schema.json
  - ../ref-pkg-contract/schemas/package-contract.schema.json
script_refs:
  - scripts/run-plugin-validate-strict.sh
  - scripts/smoke-plugin-install.sh
  - scripts/smoke-plugin-uninstall.sh
  - scripts/smoke-plugin-upgrade.sh
  - scripts/sandbox-plugin-lifecycle.py
  - scripts/validate-plugin-permissions.py
  - scripts/run-pkg-015.py
  - scripts/aggregate-pkg-findings.py
subagent_refs:
  - assign-plugin-package-evaluator
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: phase に対応する PKG gate を全件評価し pass か not_applicable で確定させ fail が1件でもあれば exit 1 で停止する
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: pkg-summary を 27章 §3.1 規約パスへ append-only 保存し run-report スキーマを通過させ verdict.fail>0 のとき pkg_check_failed を1 run 1行だけ emit する
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: 契約適合検査を elegance lint や rubric 採点と責務直交に保ち PKG 定義は ref-pkg-contract に委ね PKG-002〜008/014 は evaluator へ fork 委譲する設計を崩さない
      verify_by: elegant-review
---

# run-plugin-package-check

## Purpose & Output Contract

36章 Plugin Package Harness Contract の PKG-001〜015 gate を **plugin 単位で一括実行する orchestrator**。25章 §runbook の Step 5（PKG completeness check）として `run-build-skill` 直後・`run-elegant-review` 直前に挟まる。

**入力**:
```yaml
plugin: "harness-creator"                       # 必須
phase: 0                                       # {0, 1, 2, all}。既定 0。⚠️出荷前検査は必ず --phase all を明示。省略時(=0)は PKG-001〜009 のみ走り 010〜015 が黙って未検査=subset PASS が緑に見える false green。0/1/2 は反復途中の部分検査用
pkg: null                                      # 個別 PKG ID 指定（例: "PKG-010,PKG-013a"）。null なら phase 全件
dry_run: false                                 # true なら scripts を呼ばず計画のみ表示
output_dir: "eval-log/<plugin>/"               # 既定値、27章 §3.1 規約
```

**出力**:
- `eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.json`（各 PKG ID の個別ログ、27章 §3.1）
- `eval-log/<plugin>/pkg-summary/<YYYY-MM-DD>-<run>.json`（`schemas/run-report.schema.json` 準拠）
- stdout に verdict サマリ markdown
- 35章 `pkg_check_failed` failure_mode への observable 配線（fail 時のみ）

**完了条件**:
- Phase 0 = PKG-001〜009 全 pass / not_applicable
- Phase 1 = + PKG-010 pass
- Phase 2 = + PKG-011〜015 pass
- 1 件でも `fail` なら exit 1、`run-skill-create` パイプライン側で停止

## Key Rules

1. **PKG ID 定義は ref-pkg-contract 経由**: 本 skill で再定義しない
2. **PKG-002〜008 / PKG-014 は assign-plugin-package-evaluator に委譲**: Skill tool 経由で `context: fork`
3. **PKG-001/009/010〜013/015 は本 skill が直接実装**: 各 scripts を sub-process で実行
4. **`package_mode: skill-only` plugin に対する適用範囲**: PKG-002/004 のみ実行、それ以外は `not_applicable`
5. **eval-log パス独自定義禁止**: 27章 §3.1 規約厳守
6. **35章 observable 配線**: `verdict.fail > 0` のとき `pkg_check_failed` を `.claude/logs/` に 1 行 append（schema は 35章 §observables）
7. **`dry_run=true` でも計画 JSON は出力**: 副作用なし、stdout に実行予定 PKG ID 列挙
8. **PKG-013 は単独実行不可**: 必ず 013a/b/c/d 4 件に展開

## ゴールシーク実行

固定手順は書かず、ゴール+チェックリストへ向け都度手順を生成・反復する。正本: `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

対象 plugin の指定 phase に属する全 PKG gate が `pass` / `not_applicable` で確定し、`schemas/run-report.schema.json` 準拠の pkg-summary JSON と verdict markdown が `eval-log/<plugin>/` 配下に保存された状態になっている。

### 目的・背景 (Why)

25章 §runbook Step 5（契約適合）として出荷前に PKG-001〜015 を機械検査し、規範採点や elegance lint と直交した「契約準拠」を保証するため。fail を残したまま下流パイプラインへ流すと不整合 package が出荷される。

### 完了チェックリスト (Checklist)

- [ ] phase に対応する PKG gate を全件評価した（Phase0=001〜009 / Phase1=+010 / Phase2=+011〜015）
- [ ] PKG-002〜008・014 は `assign-plugin-package-evaluator` へ `context: fork` で委譲済み
- [ ] PKG-013 を 013a〜d の 4 件へ展開して集約した
- [ ] 各 PKG ログを `eval-log/<plugin>/pkg-<id>/<date>-<run>.json`（27章 §3.1）へ append-only 保存した
- [ ] pkg-summary JSON が `schemas/run-report.schema.json` を通過する
- [ ] `verdict.fail > 0` のとき `pkg_check_failed` を `.claude/logs/` に 1 行だけ emit した
- [ ] fail が 1 件でもあれば exit 1、全 pass/not_applicable なら exit 0

### ゴールシークループ

正本 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step→反復、既定 5 周）に従う。未達チェック項目を埋める最短手順をその場で生成する。下記「局面カタログ」は順序固定ではなく、その周回で未達な gate に応じて都度選ぶ。

## 局面カタログ（順序は都度判断）

```
[Step 0] 入力検証 + package_mode 読込
   │
   ▼
[Step 1] PKG-001 公式 CLI strict validate
   │     scripts/run-plugin-validate-strict.sh
   ▼
[Step 2] PKG-002〜008 委譲
   │     Skill(assign-plugin-package-evaluator, target_plugin=<name>, context=fork)
   ▼
[Step 3] PKG-009 外部参照ゼロ
   │     ../../../skill-governance-lint/scripts/lint-external-refs.py --skills-dir plugins/<name>/skills --fail-on-external
   ▼ (phase >= 1)
[Step 4] PKG-010 install smoke
   │     scripts/smoke-plugin-install.sh
   ▼ (phase >= 2)
[Step 5] PKG-011〜012 smoke
   │     smoke-plugin-uninstall.sh / smoke-plugin-upgrade.sh
   ▼
[Step 6] PKG-013a〜d permission scope
   │     scripts/validate-plugin-permissions.py --check 013<a-d>
   ▼
[Step 7] PKG-014 runtime contract
   │     assign-plugin-package-evaluator (delegated, --check pkg-014)
   ▼
[Step 8] PKG-015 rubric 違反率
│     scripts/run-pkg-015.py --plugin <name> --log-dir eval-log/<name> --out eval-log/<name>/pkg-015/rubric-violation.json
│     (履歴 bootstrap 中は明示 not_applicable、開each 時は fail、それ以外は pass へ正規化)
   ▼
[Step 9] findings 集約 + observable 配線
   │     scripts/aggregate-pkg-findings.py
   ▼
[Step 10] run-report.json 生成 + verdict markdown 出力
```

Phase 別の実行 Step は `workflow-manifest.json phases[].id` 参照。

## 役割直交（Step 5 / 5.5 / 6）

25章 runbook での位置づけ:

| Step | 役割 | 担当 skill |
|---|---|---|
| 5 | **契約適合**: PKG-001〜015 機械検査 | **本 skill** |
| 5.5 | **設計 elegance**: 30 思考法 × 4 条件 lint | `run-elegant-review` v2 |
| 6 | **規範採点**: rubric 適合度 | `assign-skill-design-evaluator` |

3 つは責務直交。本 skill は規範ではなく契約準拠を見る。

## Gotchas

1. **PKG-001 の公式 CLI が未配備の環境**: `claude plugin validate` コマンド未インストール時は `status: skip` + `skip_reason="claude CLI not found"` を残し exit 1 にしない（環境依存差を吸収）
2. **PKG-010 install smoke の sandboxing**: local marketplace install は実環境に副作用。`--dry-run` または専用 sandbox dir を必須化（実装スクリプト側で隔離）
3. **PKG-013 sub-check の合算**: 1 件でも fail なら PKG-013 全体を fail として集約。サマリ表記は `PKG-013(a:pass, b:fail, c:pass, d:pass)`
4. **35章 observable 配線の二重発火禁止**: 1 run につき 1 line。複数 PKG fail でも `pkg_check_failed` event は集約して 1 件
5. **`eval-log/<plugin>/` の append-only**: 過去ログを上書き禁止（27章 §10 アンチパターン #6 準用）

## Additional Resources

- `prompts/R1-orchestrate.md` — Step 0〜10 の制御プロンプト（R1）
- `prompts/R2-gate-decide.md` — phase 別完了判定（R2）
- `schemas/run-report.schema.json` — run 全体集約 JSON
- `scripts/run-plugin-validate-strict.sh` — PKG-001 公式 CLI ラッパー
- `scripts/smoke-plugin-install.sh` — PKG-010 install smoke
- `scripts/smoke-plugin-uninstall.sh` — PKG-011
- `scripts/smoke-plugin-upgrade.sh` — PKG-012
- `scripts/sandbox-plugin-lifecycle.py` — PKG-010〜012 を一時 Claude home で実行する決定論 lifecycle harness
- `scripts/validate-plugin-permissions.py` — PKG-013a〜d
- `scripts/run-pkg-015.py` — rubric lint の bootstrap/breach を PKG status へ正規化
- `scripts/aggregate-pkg-findings.py` — Step 9 集約
- 子 skill: `assign-plugin-package-evaluator` (PKG-002〜008, PKG-014)
- 参照 skill: `ref-pkg-contract`
- 設計書: 36章（正本）、27章 §3.1/§4.1、34章 Phase 0/1/2、35章 observables、34a §4
