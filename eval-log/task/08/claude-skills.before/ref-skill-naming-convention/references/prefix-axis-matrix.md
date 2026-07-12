# 5 prefix × 4軸 対応マトリクス

4軸:
- **A1 発動主体**: user / model / sibling-skill / hook
- **A2 context**: inline / fork
- **A3 write権限**: yes / no
- **A4 評価対象**: self / external / none

| prefix | A1 発動主体 | A2 context | A3 write | A4 評価対象 |
|---|---|---|---|---|
| `run-` | user, model | inline | yes | none |
| `ref-` | sibling-skill (Read) | inline | no | none |
| `assign-*-generator` | sibling-skill | fork | yes | external | role=生成。典型例: `assign-skill-design-generator` |
| `assign-*-evaluator` | sibling-skill | fork | no  | external | role=採点・検証。典型例: `assign-skill-design-evaluator` |
| `wrap-` | user, model | inline | depends | none |
| `delegate-` | user, model | fork | yes | none |

注: `assign-` は generator / evaluator を**別行**として扱う（MECE 分離）。同一行に括ると write 権限・role が混在し責務境界が曖昧になるため禁止。

## wrap と delegate の境界条件

両者は「他リソースを呼ぶ」点で混同されがちだが、以下で厳密に区別する。

### wrap-（被せる派生）
- **定義**: 既存スキルに preset / 設定 / プロファイルを被せた派生スキル
- **context**: `inline`（呼び出し元と同コンテキストで動作）
- **依存形態**: `depends on base skill`（base が存在しない場合は成立しない）
- **必須フィールド**: `base_skill`（被せる対象の Skill 名）
- **典型例**: `wrap-run-skill-create-strict`（厳格版プロファイル）

### delegate-（別 agent への委譲）
- **定義**: 別 agent / 別 context へ task を受け渡す委譲スキル
- **context**: `fork` **必須**（独立 agent / 独立 context で実行）
- **依存形態**: 独立 agent への task 受け渡し（base スキル不要、agent ID 必須）
- **必須フィールド**: `delegate_agent`（委譲先 agent ID）
- **典型例**: `delegate-codex-review`（外部 agent へレビュー委譲）

判定: **同 context で設定を被せるなら wrap、別 context へ task を渡すなら delegate**。

## 重要組み合わせ

- `disable-model-invocation: true` は `ref-` のみ既定 ON
- `user-invocable: false` は `assign-` / `delegate-` 既定 ON
- `context: fork` は `assign-` / `delegate-` 必須
- evaluator は `A3 write=no`（採点者は被採点物を改変しない、Goodhart防止）

## アンチパターン

- `run-` + `disable-model-invocation: true` → 矛盾、意味なし
- `assign-` + `context: inline` → 採点者と生成本体が同context、Goodhart罠
- `ref-` + Write tool → ref は読み専用が原則、編集が必要なら別Skillへ
