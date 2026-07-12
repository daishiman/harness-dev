# オーケストレーションタイプガイド

> **読み込み条件**: オーケストレーション機能使用時
> **相対パス**: `assets/type-orchestration.md`

---

## 概要

オーケストレーションは、複数スキルを連携させてワークフローを構築する機能。
スキルクリエイターで生成されたスキルにオーケストレーション機能を追加する際のガイド。

---

## スキルタイプとしてのオーケストレーション

| 属性 | 値 |
|------|-----|
| タイプ名 | `orchestration` |
| カテゴリ | ワークフロー管理 |
| 主要依存 | なし（内蔵機能） |
| ランタイム | Node.js |

---

## 追加可能な機能

### 1. スキルチェーン

```yaml
# スキル定義に追加
orchestration:
  type: chain
  steps:
    - skill: step1-skill
    - skill: step2-skill
    - skill: step3-skill
```

### 2. 並列実行

```yaml
orchestration:
  type: parallel
  tasks:
    - skill: task-a
    - skill: task-b
    - skill: task-c
  aggregate: merge
```

### 3. 条件分岐

```yaml
orchestration:
  type: conditional
  conditions:
    - when: "{{input.type}} == 'A'"
      skill: handler-a
    - when: "{{input.type}} == 'B'"
      skill: handler-b
  default: handler-default
```

### 4. スケジュール

```yaml
orchestration:
  type: scheduled
  schedule:
    cron: "0 9 * * *"
    timezone: "Asia/Tokyo"
  skill: scheduled-task
```

### 5. イベントトリガー

```yaml
orchestration:
  type: triggered
  trigger:
    type: webhook
    path: "/api/trigger"
  skill: triggered-task
```

---

## スキル作成時の選択フロー

```
スキル作成開始
    │
    ├─ 単一処理? → 通常スキル
    │
    └─ 複数スキル連携? → オーケストレーション
        │
        ├─ 順次実行? → chain
        ├─ 同時実行? → parallel
        ├─ 条件分岐? → conditional
        ├─ 定期実行? → scheduled
        └─ イベント駆動? → triggered
```

---

## 関連リソース

| リソース | 用途 |
|----------|------|
| [references/orchestration-guide.md](../references/orchestration-guide.md) | 詳細ガイド |
| [schemas/orchestration.json](../schemas/orchestration.json) | スキーマ |
| [agents/design-orchestration.md](../agents/design-orchestration.md) | 設計エージェント |
