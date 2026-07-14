# examples

`/system-dev-plan plan` の必須入力 (feature context) の実物ゴールデンです。初見でも「何を書けば通るか」をこの1ファイルで把握できます。

## feature-context.example.json

- 対応 schema: `../schemas/feature-context.schema.json` (唯一の入力側 schema。他6 schema は全て出力側)。
- 内容: `feature-auth` を題材にした、schema に valid な最小かつ現実的な feature context。9 フィールド (`graph_node_id`, `artifact_kind`, `purpose`, `goal`, `scope_in`, `scope_out`, `acceptance`, `architecture_refs`, `updated_at`) を全て含みます。

### 使い方

caller repository 側にこの形の JSON を置き、`--feature-context` で repository 相対 path として渡します。`graph_node_id` は `--feature-id` と一致させます (不一致は C09 が停止)。

```bash
# 例: caller repo の features/feature-auth.json に配置した場合
/system-dev-plan plan \
  --feature-id feature-auth \
  --feature-context features/feature-auth.json
```

`architecture_refs` は caller repository 内で解決できる参照 (system-spec-harness の confirmed 成果物 path 等) を指し、絶対 path・`..`・root 外 symlink・別 repository の context は拒否されます。
