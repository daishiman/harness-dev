---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
C1/C2/C3 に加え C6/C7/C10/C11 (機械層新規 script 2 本)・C8/C12 (assign-plugin-plan-evaluator のプロンプト/schema 拡張) の解消内容を、既存ドキュメント (SKILL.md の script_refs 説明・io-contract.md の拡張ゲート一覧・harness-creator-spec-reflection.md の該当行) へ反映する範囲を確定する。

## 背景
新規 script (`check-harness-coverage-selfcheck.py`・`check-generative-fidelity.py`・`check-downstream-harness.py`) の追加は SKILL.md の script_refs リストと io-contract.md の拡張ゲート表への追記を要する。既存 script の拡張 (C1/C2) はシグネチャの後方互換拡張のみのためドキュメント上の契約変更は最小限で足りる。C8/C12 は assign-plugin-plan-evaluator 側の prompts/schemas の追記であり、こちら側のドキュメント (存在すれば SKILL.md の該当節) にも反映する。

## 前提条件
- P11 の証跡が揃っている。

## ドメイン知識
- **更新対象 1**: `run-plugin-dev-plan/SKILL.md` の `script_refs` へ `scripts/check-harness-coverage-selfcheck.py`・`scripts/check-generative-fidelity.py`・`scripts/check-downstream-harness.py` の 3 本を追加する。
- **更新対象 2**: `references/io-contract.md` の拡張ゲート一覧表 (§11) へ新規 3 script の invocation を追記する。
- **更新対象 3**: `references/harness-creator-spec-reflection.md` は行の追加・変更を伴わない (既存 46 行の適用範囲内の改修のため、マトリクス自体は不変)。この点を明示し test_matrix_doc_integrity.py が退行しないことを確認する。
- **更新対象 4**: `assign-plugin-plan-evaluator/SKILL.md` (存在する場合) の R1-evaluate 説明へ C8/C12 判定軸の追加を反映する。
- **更新不要**: C1/C2 は既存 script の内部拡張のみで公開インターフェース (CLI 引数・SKILL.md 記載の起動コマンド) を変えないため、ドキュメント更新は不要。

## 成果物
- SKILL.md (run-plugin-dev-plan / assign-plugin-plan-evaluator) / io-contract.md への追記範囲の確定 (build 後の実施対象)。

## スコープ外
- 実ドキュメントファイルの編集 (L4 build へ委譲)。

## 完了チェックリスト
- [ ] run-plugin-dev-plan の SKILL.md script_refs への追記対象 (3 script) が確定している。
- [ ] io-contract.md 拡張ゲート表への追記対象 (3 script) が確定している。
- [ ] harness-creator-spec-reflection.md が不変であること (46 行マトリクス non-change) が明示されている。
- [ ] assign-plugin-plan-evaluator 側ドキュメントへの C8/C12 判定軸反映対象が確定している。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 上記 4 更新対象それぞれについて、追記先ファイル・追記箇所・追記内容の要約が具体的に記述されている。
- 満たさない例: 「ドキュメントを適切に更新する」とのみ記述し、追記先ファイルや箇所が特定されていない。

### 事前解決済み判断
- 分岐点: harness-creator-spec-reflection.md の 46 行マトリクスに C6-C12 分の新規行を追加すべきか → 判断: 追加しない。46 行マトリクスは既存 6 種別×mechanical/llm_eval 軸の完全性証明であり、C6-C12 は既存軸の内部拡張 (同一 skill 内の script/prompt 追加) に留まるため新規軸を構成しない。

## 参照情報
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/SKILL.md`。
- `plugins/plugin-dev-planner/skills/assign-plugin-plan-evaluator/`。
- `references/io-contract.md`。
- 後続 P13 (release)。
