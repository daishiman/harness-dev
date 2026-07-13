---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 完了
gate_type: tdd-red
entities_covered: [C01, C02, C03, C16, C17]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component (C16 run-ubm-goal-setting / C17 run-ubm-knowledge-sync) の受入基準を test-first に導出して `feedback_contract` の inner/outer criteria として固定し、あわせて 3 本の既存 shell script を Python へ書き換える script component (C01 validate-goal-output.py / C02 detect-knowledge-updates.py / C03 check-knowledge-split.py) のテスト設計を tdd-red で行う。実装前はいずれも未達 (Red) であることを確認する。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え (lint exit0/4条件PASS) に退化した criteria は purpose を一度も受入検証しないため、goal/checklist 語彙由来であることを設計時に担保する。本 plan は移植プロジェクトのため、旧 .sh の挙動を仕様としてテストケース化する契約移植 (逐語移植ではない) が中心作業になる。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C16/C17 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。
- 旧 shell script (validate-goal-output.sh 474行/detect-knowledge-updates.sh 183行/check-knowledge-split.sh 67行) の検査分岐が参照可能。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点、outer=build 後の受入観点 (各 1 件以上が契約)。
- Red = 実装前に criteria が未達であること (実装後に緑になることで criteria が実効だったと証明される)。
- 契約移植: 旧 shell script の逐語移植でなく検知/検証ロジックの仕様を Python テストケースへ移す (validate-goal-output.sh の「9検査=474行の完全契約」という仮説を、抽出した検査分岐数との parity assert で testable にする)。

## 成果物
- C16 (run-ubm-goal-setting): 「validate-goal-output が出力前に統一ハイブリッド構造21項目・NG表現・やらないこと3項目以上を検証し違反0件」の inner criterion と「週報/月報/期報を生成し validate-goal-output が PASS する」の outer criterion。
- C17 (run-ubm-knowledge-sync): 「detect-knowledge-updates が registry.json との MD5 照合で NEW/MODIFIED を漏れなく検知」の inner criterion と「knowledge-extractor が 6 カテゴリへ分類し router.json/registry.json が同期完了する」の outer criterion。
- C01/C02/C03 の Python 書き換え版に対するテストケース設計 (Red 状態): validate-goal-output.py は統一ハイブリッド構造21項目・NG表現・やらないこと3項目以上の検証、detect-knowledge-updates.py は MD5 照合による NEW/MODIFIED 検知、check-knowledge-split.py は500行閾値超過検知。
- 旧 .sh 検査分岐数と新 .py テストケース数の parity assert 定義 (grep/AST的に条件分岐を機械抽出し件数一致を assert)。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの設計・実行 (P06・kind 別観点はそちらで扱う)。
- 非 skill component の受入: hook(C04)の fail-closed 挙動と slash-command(C18/C19)の起動分岐は tdd-red でなく P06 機能テスト + P07 output_contract 判定で扱う(意図的に P04 対象外)。sub-agent(C05-C13/C15)も同様に P06/P07 で受入。

## 完了チェックリスト
- [ ] 2 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ (汎用ゲート言い換えに退化していない)。
- [ ] 3 本の script が実装前は Red (未達) であることが確認できる。
- [ ] 旧 .sh の検査分岐数と新テストケース数の parity assert が定義されている (各 criteria が対応 skill の goal/checklist 語彙を参照している)。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- 対象 component C01 (validate-goal-output) / C02 (detect-knowledge-updates) / C03 (check-knowledge-split) / C16 / C17。
- 後続 P05 (implementation)。
