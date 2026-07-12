# fidelity-check-rules

`overall_score` を閾値で `verdict` に変換し、exit code を確定する。

## 閾値

| verdict | 条件 | exit code | 呼び出し元の挙動 |
|---|---|---|---|
| `pass` | `overall_score >= fidelity_threshold_pass` (既定 0.85) | 0 | Notion 公開を続行 |
| `warn` | `fidelity_threshold_warn <= overall_score < fidelity_threshold_pass` (既定 0.70) | 1 | 公開は可だが CI に警告ログを残す |
| `fail` | `overall_score < fidelity_threshold_warn` | 2 | 公開を停止し handoff へ差し戻し |

閾値は `--pass-threshold` / `--warn-threshold` CLI 引数で上書き可能 (量産時の差し替え)。

## エスカレーション規約

- `verdict=fail` のとき: `fidelity-report.{json,md}` を out_dir (context.json と同階層) に書き出し (exit 2)、`skill-intake-handoff` に差し戻す。
- `verdict=warn` が同一 hint で連続 3 回発生: canonical-page-snapshot.json の更新検討 (template-change trigger 発火)。

## 必須セクション欠落の即時 fail

`section_canonical_map.json` 上で `absence_behavior=block` のセクションが context.json から完全欠落している場合、overall_score に関係なく `verdict=fail` を強制する (12 section のうち 10 件が block)。
