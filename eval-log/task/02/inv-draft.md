# Task 02 INV Draft

Date: 2026-05-20

Source: `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md`

## Adopted Invariants

| INV | Summary | Machine check |
|---|---|---|
| INV-1 | user 管理値保存 | user 管理値の正規化 JSON SHA256 を実行前後で比較 |
| INV-2 | 決定的生成 | 固定 fixture と golden JSON の比較 |
| INV-3 | 冪等性 | 実行、再実行、`--check` の3段階テスト |
| INV-4 | plugin 順序 | 入力ディレクトリ順を入れ替えた fixture で出力同一性を確認 |
| INV-5 | 衝突 ERROR | 衝突 fixture で exit 2 と conflict report を確認 |
| INV-6 | 未知キー保存 | 未知キー fixture の AST 等価または SHA256 比較 |
| INV-7 | JSON 正規化 | 生成領域を formatter fixture と比較 |
| INV-8 | 原子的書き込み | 書き込み失敗注入後の target SHA256 不変を確認 |
| INV-9 | グローバル名前空間一意性 | 同名 fixture で exit 2 と target SHA256 不変を確認 |
| INV-10 | settings 構造検証 | JSON parse 後、必須 key、型、hook command entry を検査 |
| INV-11 | permissions マージ安全性 | permissions conflict fixture と dedupe fixture を確認 |
| INV-12 | plan 完全性 | plan JSON に `namespace`, `settings`, `conflicts`, `invariants_checked` を確認 |

## Review Notes

- 管理メタデータは `hooks` 配下ではなく top-level `_build_claude_settings` に限定する。
- hook 衝突キーは `event`, `matcher`, `command` の normalized triple とする。
- permissions は完全一致のみ dedupe し、decision が異なる同一 rule は自動解決しない。
- task 04/07 へ、fixture と exit code の実装契約を引き継ぐ。
