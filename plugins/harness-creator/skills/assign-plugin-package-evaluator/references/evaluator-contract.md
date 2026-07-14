# Evaluator Contract: assign-plugin-package-evaluator

## 責務境界

| 検査 | 担当 | 補足 |
|---|---|---|
| PKG-001 公式 CLI strict validate | **B (run-plugin-package-check)** | `claude plugin validate --strict` ラッパー |
| PKG-002〜008 静的検査 | **本 skill** | findings JSON で返す |
| PKG-009 外部参照ゼロ | **B** | 既存 `scripts/lint-external-refs.py` 直呼出 |
| PKG-010 install smoke | **B** | `scripts/smoke-plugin-install.sh` |
| PKG-011〜013 / PKG-015 出荷前 gate | **B** | uninstall/upgrade/permission/rubric |
| PKG-014 runtime contract | **本 skill** | kind/combinator 宣言と実配線の静的整合を findings JSON で返す |

## context: fork 理由

本 skill は規範採点（assign-skill-design-evaluator と同型）であり、親 context の sycophancy（自分が書いた package を甘く採点する罠）を排除するため context fork 必須。fork 後の入力は `target_plugin` 名のみで、親 context の判断履歴は持ち込まない。

## findings 出力規約

- 1 件の finding に必ず `pkg_id` フィールド（属する PKG ID）
- `severity` は PKG ID 別の既定値（`pkg-id-catalog.yaml` の `severity`）を尊重しつつ、特定 finding の重要度で上書き可能
- `auto_fixable=true` の finding は B 側で自動 commit 候補（`chmod +x` 等）
- `location` は repo root からの相対 path + 任意 `:line_number`

## eval-log 保存

`scripts/validate-plugin-package.py` 単独実行時は stdout のみ。B から呼ばれた際の保存先は B が `--output` 指定で渡す（27章 §3.1 規約）。

## 公式制約整合

- 34章公式制約 a/b/e（plugin スコープ・permissions・外部参照）は **B が PKG-009/013 で検査**。本 skill は内部構造の整合性のみ
- 34a 章 INV-1〜12 は PKG-008 で部分検査（schema 違反のみ）。設定マージ時の動的検証は別 skill

## 改廃

PKG-002〜008 / PKG-014 の **意味変更** は 27章 §4.1 governance 経由。本 skill 内のスクリプト実装変更は P1（governance 不要）。検査関数追加（例: PKG-004 に新規必須キー追加）は schema 変更を伴うため P0_breaking。
