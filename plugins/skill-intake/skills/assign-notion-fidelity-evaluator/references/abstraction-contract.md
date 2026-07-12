# abstraction-contract

本スキルを別ドメイン (例: 他社向け intake テンプレ) に量産流用するための **差し替え変数規約**。

## テンプレ変数

| 変数 | 型 | 既定値 | 規約 |
|---|---|---|---|
| `canonical_page_id` | string (Notion page id) | `35195d6503b781788e31f59b4e05e705` | snapshot 抽出元の Notion page id。`extract-canonical-snapshot.py` の `--canonical-page-id` で上書き可能。 |
| `canonical_snapshot_path` | path | `references/canonical-page-snapshot.json` | snapshot の保存先。skill ディレクトリ相対で記述する。 |
| `fidelity_threshold_pass` | float (0-1) | `0.85` | pass 判定の下限。`validate-notion-fidelity.py --pass-threshold` で上書き可能。 |
| `fidelity_threshold_warn` | float (0-1) | `0.70` | warn 判定の下限。fail との境界。`--warn-threshold` で上書き可能。 |

## 差し替え時の整合性ルール

1. `0.0 <= fidelity_threshold_warn < fidelity_threshold_pass <= 1.0` を満たすこと。違反時は CLI で exit 64 (usage error)。
2. `canonical_snapshot_path` を skill ディレクトリ外に出す場合は、`SKILL.md` の `Additional Resources` 表と `resource-map.yaml` を同時更新する (Progressive Disclosure の整合)。
3. `canonical_page_id` を差し替えた場合、必ず `extract-canonical-snapshot.py` を走らせて snapshot を再生成すること (手書き禁止)。

## 量産チェックリスト

- [ ] `SKILL.md` Abstraction Variables 表が更新されている
- [ ] `references/fidelity-check-rules.md` の閾値表が新値と一致している
- [ ] `prompts/R2.md` の評価基準 layer に新閾値が反映されている
- [ ] snapshot が再生成されている (`canonical-page-snapshot.json` の `generated_at` が新しい)
