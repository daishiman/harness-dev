# observable emit examples (35 章 §observables 配線)

> SKILL.md 「35 章 observable 配線」節の外出し (300 行 cap 遵守, G4 拡張)。
> `scripts/emit-observable.py` が `.claude/logs/meta-harness.jsonl` に append する event の reference 例。

## trigger 定義

`workflow-manifest.json#observable.trigger` と論理同一: **4 条件のいずれかが FAIL、または `safety_valve_fired=true`**。emit 呼出は `phases[phase3-execute].steps.step6` (always 実行) に一本化済 (G3, append-only jsonl 重複防止)。

## 例 1: 4 条件 FAIL 時

```json
{
  "event": "elegant_review_4condition_failed",
  "schema_version": "1.0",
  "ts": "2026-05-23T12:00:00Z",
  "plugin": "harness-creator",
  "skill": "run-skill-rename",
  "scope_mode": "skill",
  "failed_conditions": ["矛盾なし", "依存関係整合"],
  "fail_counts": {"contradiction": 2, "omission": 0, "inconsistency": 0, "dependency_break": 1},
  "iteration_count": 2,
  "status": "incomplete",
  "safety_valve_fired": false
}
```

## 例 2: safety_valve_fired=true (4 条件 PASS でも max_iter 到達は失敗扱い)

`failed_conditions=[]` でも emit 強制。`examples/safety-valve-fired-verdict.json` を `emit-observable.py --dry-run` に与えると本イベントが生成される。

```json
{
  "event": "elegant_review_4condition_failed",
  "schema_version": "1.0",
  "ts": "2026-05-23T12:00:00Z",
  "plugin": "harness-creator",
  "skill": "run-skill-rename",
  "scope_mode": "skill",
  "failed_conditions": [],
  "fail_counts": {"contradiction": 0, "omission": 0, "inconsistency": 0, "dependency_break": 0},
  "iteration_count": 3,
  "status": "incomplete",
  "safety_valve_fired": true
}
```

35 章 `pkg_check_failed` と並走し、collect → classify → improve の閉ループを成立させる。
