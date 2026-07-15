---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (エビデンス)

## 目的
P03 (design-gate)・P09 (qa)・P10 (final-gate) の各ゲート通過証跡と、`references/io-contract.md §11` (決定論検査スクリプトの単一正本表) が列挙する自己検証スクリプト群の exit code を、後続の evaluator/監査が再現確認できる形でエビデンスとして固定する。

## 背景
決定論ゲートは再実行可能でなければならない。本planは通常read-onlyに加え、承認済みapply時だけ書き込みを許すため、未承認caseの差分0件と承認caseの対象限定差分・pre/post hash・validator結果を分けて証跡化する。

## 前提条件
- P10 の final-gate が合格している。
- 各ゲートスクリプトの実行ログ (exit code + 標準出力) を保存できる。

## ドメイン知識
- エビデンスの最小単位はゲートスクリプト単位の exit code + 実行コマンド (再現可能性を担保する)。
- スクリプトの総数・一覧は本 phase では直書きせず `references/io-contract.md §11` の表 (`specfm.GATE_SCRIPTS` が実行可能正本) を都度引用する (drift 耐性)。
- no-change/未承認/監査FAIL caseは差分0件、apply caseはproposal allowlist以外の差分0件とpost-image hash/validator一致を確認する。C03/C04 verdict digestも保存する。

## 成果物
- `references/io-contract.md §11` が列挙する自己検証スクリプト全件の exit code 一覧。
- Issue #17完全diffのcommit pair/digest/completeness証跡、4軸+semantics判定、独立verdict、apply/no-change別の差分・hash・validator証跡。

## スコープ外
- ドキュメント整備そのもの (P12 の責務)。
- リリース判断 (P13 の責務)。

## 完了チェックリスト
- [ ] `references/io-contract.md §11` に列挙される自己検証スクリプトそれぞれの exit code が記録されている。
- [ ] 未承認系は差分0件、承認apply系はallowlist対象だけに差分がありpost hash/validatorが一致することを確認している。
- [ ] エビデンスが再実行可能なコマンド形式 (絶対パスではなく `$SKILL_DIR`/相対参照) で記録されている。

## 参照情報
- `references/io-contract.md §11` (決定論検査スクリプトの単一正本表、総数・一覧はここを正とする)。
- 後続 P12 (このエビデンスをドキュメントへ反映する)。
