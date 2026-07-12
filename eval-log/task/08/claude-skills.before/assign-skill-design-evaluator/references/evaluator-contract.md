# Evaluator Output Contract

## STDOUT schema (JSON, 1 object)

```json
{
  "rubric_id": "skill-design",
  "rubric_version": "1.0.0",
  "rubric_hash": "sha256:<hex>",
  "composition_hash": "sha256:<hex>",
  "rubric_refs": ["<ordered rubric path>"],
  "target": "<absolute path>",
  "score": 87,
  "threshold": 80,
  "passed": true,
  "machine_checks": [
    {"check": "lint-skill-name", "passed": true}
  ],
  "findings": [
    {
      "id": "FM-003",
      "severity": "medium",
      "area": "frontmatter",
      "message": "trigger count = 4 (expected 2..3)",
      "loc": "frontmatter.description"
    }
  ],
  "required_fixes": [],
  "pending_human": [
    {"id": "BD-004", "reason": "rubric has TODO(human) marker"}
  ]
}
```

## 禁則

- Write/Edit tool 不使用（採点者は被採点物を改変しない、09章）。
- STDERR にはログのみ。JSONは必ずSTDOUT。
- score は 0..100 にクランプ。
- BD-004 が TODO(human) のままなら `pending_human` に積む。スコア控除しない。
- `required_fixes` は high finding または gate failure から派生する修正必須項目。空配列可。
- `machine_checks` は実行済みP0検査の配列。未実行なら空配列にする。

## 利用側 (run-build-skill) の使い方

1. `Skill(assign-skill-design-evaluator) target=<path>` を fork で呼ぶ。
2. STDOUTを JSON parse。
3. `passed=false` なら `findings[].message` を編集ヒントに使う。
4. 最大3周のリトライ。

## rubric_hash

```python
import hashlib, pathlib
h = hashlib.sha256(pathlib.Path("references/rubric.json").read_bytes()).hexdigest()
print(f"sha256:{h}")
```
