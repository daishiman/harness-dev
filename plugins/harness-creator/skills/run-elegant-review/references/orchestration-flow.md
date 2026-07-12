# Orchestration Flow: Phase1 → Phase2 → Phase3

```
[target_type, target_path]
        │
        ▼
┌─────────────────────────────────┐
│ Phase 1: 思考リセット俯瞰        │
│ Agent 1 elegant-reset-observer  │
│ → raw_observations.json         │
└─────────────────────────────────┘
        │
        ├──────────┬──────────┐  (並列起動)
        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Agent 2  │ │ Agent 3  │ │ Agent 4  │
│ 論理+構造│ │ メタ+発想│ │ Sys+戦略 │
│ 10思考法 │ │ 9思考法  │ │ 11思考法 │
└──────────┘ └──────────┘ └──────────┘
        │          │          │
        └──────────┴──────────┘
                   ▼
        scripts/validate-paradigm-coverage.py {{review_workspace}}/findings.json (used + skipped_with_reason == 30)
                   │
                   ▼
        scripts/build-paradigm-scorecard.py
                   │
                   ▼
┌─────────────────────────────────┐
│ Phase 3: 改善実行                │
│ Agent 5 elegant-improvement-... │
│  - findings重大度順              │
│  - C1〜C4 FAIL 項目にパッチ      │
│  - 4条件 PASS or loop<=3 で復帰  │
└─────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │ ALL PASS?           │
        ├── yes → 完了        │
        └── no  → Phase2 再実行│
                              (max 3 loops, 超過時 escalate)
```

## Self-Application Audit（MD-004）

Phase 3 完了時、`references/amplified-patterns.json` の各パターンをレビュー実施側 plugin（本 skill を含む実行主体）自身へ照合し、同型の穴があれば finding として残す。レビューで他者に課した修正パターンは、自己にも同基準で適用チェックする（自己適用の非対称を許さない）。検出した自己側の穴は通常の findings と同じ schema・severity 変換で記録し、スコープ外なら `residual_risks[]` へ引き継ぐ。

## 改善の受入条件 (機械検査のチェックリスト化)

機械検査 (lint / script) をチェックリスト項目として追記する改善を Phase 3 で適用する際は、当該スクリプトの dry-run 実行 (exit code 確認) を受入条件に含める。チェックリスト追記だけの表層改善では検査実体の故障が見逃される (前例: check-rubric-sync 2026-05-24 — チェックリストに載せた script 自体が壊れたまま残存した)。

## ループ制御
- max_loops = 3
- 各ループで Agent5 のパッチを適用後、Phase2 を再実行
- 3ループでも 4条件未達なら `escalate-to-human` イベント発火

## ファイル受け渡し
- Phase1出力: `{{review_workspace}}/raw_observations.json` + `{{review_workspace}}/shared_state.md`
- Phase2出力: `{{review_workspace}}/phase2-agent{2,3,4}.json`
- 集約: `{{review_workspace}}/findings.json`
- 最終: 対象ディレクトリ直下に `findings.json` + `review-<type>.md`

## 作業領域

`{{review_workspace}}` は OS 依存の一時領域に作る。固定の `/tmp` を前提にしない。

| `{{os_kind}}` | 既定候補 |
|---|---|
| `mac` / `linux` | `${TMPDIR:-/tmp}/elegant-review` |
| `windows` | `%TEMP%\\elegant-review` |
| `unknown` | ユーザー確認後に決定 |
