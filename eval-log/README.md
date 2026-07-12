# eval-log/ — 評価結果の永続化ディレクトリ

設計書23章「自己進化ループ」の **記録ストック** を保持する正本ディレクトリ。
書き込み責任は `assign-skill-design-evaluator`（および将来追加される他 evaluator）が負い、
唯一の書き込み経路は `creator-kit/scripts/write-eval-log.py`。

## ファイル一覧

| ファイル | フォーマット | 書き込み主体 | 用途 |
|---|---|---|---|
| `skill-build-trace.jsonl` | JSONL (1行=1評価) | `write-eval-log.py` 経由 | 自己進化ループの **入力ストック**。違反率・スコア時系列の元データ |
| `skill-build-trace.json` | 単一JSON | 旧経路 (deprecated) | 最後の1評価のみ保持。後方互換のため残置 |
| `fixtures/` | JSON群 | テスト用 | skill-fixture-runner 等のテストデータ |
| `proposal-rubric-sync-*.json` | JSON | governance Skill | rubric 改正提案の保存 |
| `phase0-reference-inventory.json` | JSON | 1 回限り | Phase 0 外部参照棚卸し結果 |

## skill-build-trace.jsonl スキーマ (v1.0)

1 行 1 オブジェクト。必須キー:

| key | type | 説明 |
|---|---|---|
| `rubric_id` | string | 例: `skill-design` |
| `rubric_version` | string | semver |
| `rubric_hash` | string | `sha256:<hex>` 形式。rubric.json の SHA-256 |
| `target` | string | 評価対象のSKILL.mdパスまたはディレクトリ |
| `score` | number | 0〜100 |
| `passed` | bool | threshold判定結果 |
| `recorded_at` | string | ISO8601。write-eval-log.py が自動付与 |
| `schema_version` | string | `"1.0"`。write-eval-log.py が自動付与 |

任意キー: `findings[]`, `required_fixes[]`, `pending_human[]`, `composition_hash`, `rubric_refs[]`, `machine_checks[]`, `threshold`。

## 書き込み手順

```bash
# evaluator のSTDOUTを直接パイプ
Skill(assign-skill-design-evaluator) target=path/to/SKILL.md | \
  python3 creator-kit/scripts/write-eval-log.py

# またはファイル経由
python3 creator-kit/scripts/write-eval-log.py --input ./build-report.json
```

## 読み取り側 (フィードバックループ)

| 用途 | スクリプト |
|---|---|
| rubric改正時の全Skill再評価 | `creator-kit/scripts/re-evaluate-on-rubric-bump.py` |
| 違反率時系列の集計 | `creator-kit/scripts/aggregate-violation-rate.py` (Phase 1 で追加予定) |
| 安定版凍結判定 | 23章 § 自己進化ループの終了条件 (N=10, M=5%) |

## 環境変数

| 変数 | デフォルト | 用途 |
|---|---|---|
| `EVAL_LOG_DIR` | `<cwd>/eval-log` | eval-log の置き場を上書き |
| `PROJECT_ROOT` | `<cwd>` | プロジェクトルート。EVAL_LOG_DIR 未設定時に `<PROJECT_ROOT>/eval-log` を選ぶ |

## Gotchas

- **直接 echo 追記禁止**: 必ず `write-eval-log.py` 経由（スキーマ検証・タイムスタンプ自動付与のため）
- **改行の含有禁止**: `findings[*].message` 等で改行を含めると JSONL がパースエラーになる。スクリプト側は `json.dumps` で escape する
- **rubric_hash 未設定はexit 1**: 監査可能性のため必須。RG-001 ルールと整合
