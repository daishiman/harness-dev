# granularity-rubric

粒度スコアは 0〜100 の整数 (内部は 0.0〜1.0 を 100 倍)。section ごとに算出し、加重平均を `overall_score` とする。

## 計算式 (section 単位)

```
section_score = 0.30 * char_score
              + 0.40 * field_score
              + 0.30 * viz_score
```

### char_score (30%)

canonical の `char_bounds = {min, max}` と context.json 上の section 本文文字数 `L` を比較する。

| 条件 | char_score |
|---|---|
| `min <= L <= max` | 1.0 |
| `L < min` | `max(0.0, L / min)` |
| `L > max` | `max(0.0, 1.0 - (L - max) / max)` |

### field_score (40%)

canonical の `required_fields[].key` のうち、context.json 該当 section に存在するキー数を `present`, 全件を `total` として `present / total`。`absence_behavior=warn-fallback` のフィールドは欠落しても half-credit (0.5) を与える。

### viz_score (30%)

canonical の `viz_slots[]` のうち `mandatory=true` を母集団とする。context.json 側 (figures[].kind / viz_slots) に `asset_id` 互換のスロットが存在すれば充足。母集団 0 件の section は `viz_score = 1.0` 固定。

## overall_score

```
overall_score = mean(section_score for section in canonical.sections)
```

`section_canonical_map.json` 上の `absence_behavior=warn-fallback` セクション (例: `10_self_updater`) は weight 0.5 で平均する。

## section_text_length() の規約

- `executive_summary`, `assumption.deep_problem`, `purpose.true_purpose` のように **本文相当の string / array of strings** を結合し、空白除去後の文字数を採用する。
- JSON のキー名や記号は計測対象外。
- 計測ロジックは `scripts/validate-notion-fidelity.py` 内 `section_text_length()` を正本とする。
