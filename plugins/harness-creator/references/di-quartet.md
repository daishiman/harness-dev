# di-quartet: ref / lookup / assign / run の責務四重奏

> harness-creator 横断パターン (ANAL-001)。prefix が表現する DI (Dependency Injection) 役割の正本。
>
> **read_when** (G9, plugin-level resource-map):
> - 新規 skill の prefix 選定時
> - assign-* と run-* の責務境界が曖昧と感じた時
> - assign-* が write 副作用を持つ提案を検出した時 (アンチパターン #2)
>
> 正本: `plugins/harness-creator/references/resource-map.yaml#di-quartet`

## 四重奏

| prefix | 役割 | 副作用 | 例 |
|---|---|---|---|
| `ref-*` | 静的 reference の供給 (lookup 対象) | none | `ref-skill-design-rubric`, `ref-pkg-contract` |
| `lookup-*` (将来予約) | 動的 query を ref-* に発行する adapter | read-only | (現状未使用、将来 lookup adapter 用) |
| `assign-*` | 採点 / 検査の実行 (read-only) | none / report 出力のみ | `assign-skill-design-evaluator`, `assign-plugin-package-evaluator` |
| `run-*` | フローのオーケストレーション (write 可) | local-artifact | `run-build-skill`, `run-elegant-review` |

## 依存方向 (DAG)

```
run-* ──depends─▶ assign-* ──depends─▶ ref-*
   │                                     ▲
   └────────────depends────────────────┘
```

run-* は ref-* も assign-* も直接参照できるが、ref-* は他に依存しない (leaf)。

## `assign-*` の意味統一 (MED-1)

`assign-*` の prefix は **「採点 / 検査の実行」** に統一する。`agent 割当 / dispatch` の意味で `assign-*` を使う既存 skill は名称変更を検討する。

| 用途 | 推奨 prefix | NG (使用禁止) |
|---|---|---|
| 採点 / 検査の実行 (read-only, report 出力) | `assign-*` | `evaluate-*` (run-* と紛らわしい) |
| agent への動的タスク割当 / dispatch | `dispatch-*` (将来予約) | `assign-*` (意味二重化) |
| orchestrator がフローを実行 | `run-*` | `assign-*` |

**根拠**: assign が「採点」と「dispatch」の二重意味を持つと SubAgent 起動権限の管理粒度が崩れ、proposer ≠ approver の境界も曖昧化する。本セッション (2026-05-23) では新規 dispatch 用途は `dispatch-*` を予約し、既存 `assign-*` は採点のみに固定。

## アンチパターン

- ref-* が write 副作用を持つ (`effect: none` 違反)
- assign-* が自分で write して `proposer != approver` を破る
- run-* が ref-* を経由せず外部 URL から直接 rubric を fetch する (再現性破壊)

## 関連

- 06 章 (classification-and-naming)
- 23 章 (Capability 抽象)
- 25 章 (meta-skill-runbook)
- orchestrate-gate-pattern.md (Gate A/B/C 配置)
