# knowledge/ — plugin-dev-planner の蓄積知見ストア (Loop A)

plugin-dev-planner が計画した task-graph を harness-creator が実行 (build) した際の教訓を蓄積し、次回 `run-plugin-dev-plan` 実行時 (planner runtime) に検索して計画判断へ再利用する Loop A ストア。機構は harness-creator の `skills/ref-knowledge-loop` 正本 + `skills/run-build-skill/templates/knowledge-skeleton/scripts/` を共有する (並行実装を作らない = SSOT)。

## 書き手と読み手 (一方向 writer)

| | 誰が | いつ |
|---|---|---|
| 書込 | harness-creator TG-C08 `record-task-graph-knowledge.py` (add_entry.py 委譲) | build 完了ゲート ok 時 |
| 読取 | `run-plugin-dev-plan` (次 cycle 計画時) | planner runtime |

planner 自身はここへ追記しない。build 実行の教訓 (依存詰まり・成果物欠落・blocked 起点・再試行で解消した判断・route friction) だけが source_ref 付きで蒸留される (生ログは複製しない)。

## 構成 (Index-Search型)

```
knowledge/
├── knowledge-index.json            # カテゴリ索引 + consult_at: ["runtime"] 宣言 (KL-007)
├── knowledge-build-patterns.json   # task-graph runtime lessons (TG-C08 が追記)
└── usage-log.jsonl                 # 活用ログ (初回 record_usage.py 実行時に lazy 生成・不在=未使用の正常状態)
```

## runtime での検索 (Loop A 実体)

検索スクリプトは複製せず、テンプレ正本を `--dir` 指定で直接実行する:

```bash
python3 plugins/harness-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py \
  --dir plugins/plugin-dev-planner/knowledge/ --query "<次 cycle のトピック>" --limit 5
```

検索結果は task spec の `knowledge_refs` (C19: id/source_ref/freshness_checked_at/decision 付き有界再利用。`check-cycle-knowledge.py` が検査) の蒸留元として使う。
