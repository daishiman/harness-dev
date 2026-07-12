# Phase 04 — テスト設計レポート (TDD Red)

実装前に受入テストを設計・作成し、Red を確認した (対象コードが無い/未拡張の段階で失敗することを確認)。

## テスト配置規約

- 配置: repo-root `tests/scripts-plugins/`。
- 命名: `test_skill_intake__<script>.py` (CI は `python3 -m pytest tests/ -q` で一括走査)。
- `conftest.py` が cwd 復元 + 同名 bare-import モジュールの隔離を担う。

## 新規/拡張テストファイル

| ファイル | 対象 | 件数 |
|----------|------|------|
| `test_skill_intake__validate_procedure_completeness.py` (新規) | C02 完全性 + contamination | 43 |
| `test_skill_intake__interview_procedure.py` (新規) | C01 抽象判定 axis=procedure / build-sheet-json procedure 抽出 | 25 |
| `test_skill_intake__quality_gate.py` (拡張) | C04 dual-gate / migration_warn / require_procedure | +約15 |

3 ファイル合計 **127 tests**。

## 主要テスト観点

- **完全性 (C1)**: detailed モードの steps 各要素非空 / overview_fallback の difficulty_flag=true + overview 非空 / 各フィールド欠落で exit1。
- **決定論分岐 (C2/OUT1)**: 2 連続抽象→overview、具体回答→detailed。同一入力→同一経路。
- **contamination (C7)**: 強シグナル単独→detected / 弱シグナル+当為共起→detected / 弱シグナル名詞的用法→detected=false + warn。
- **dual-gate (C3)**: purpose 欠落→gate fail / procedure 欠落→gate fail / migration_warn (procedure 非認識 intake) で既存緑維持。
- **exit code 契約**: C02 exit 0=complete&clean / 1=incomplete or contaminated / 2=usage。

## Red 確認

対象 script (C02) 未作成 / 拡張前の段階で新規テストが ImportError・AssertionError で失敗することを確認し、Phase 05 実装後に Green へ遷移させる TDD サイクルを成立させた。
