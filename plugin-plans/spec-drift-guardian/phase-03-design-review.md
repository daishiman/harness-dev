---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビュー / design-gate)

## 目的
P02 のcomponent分解・依存DAG・surface ownerと、通常read-only/C02承認済みapply限定の書き込み境界がgoal-spec C1-C6を満たすか審査する。

## 背景
分解が単一skillへ退化していないか、共有scriptのhoistが妥当か、C02 apply以外の書き込みやC02の承認バイパスがないか、独立verdictがclose gateへ届くかは自己承認では見落としやすい。独立design-gateで審査する。

## 前提条件
- P02 の `component-inventory.json` と `envelope-draft/plugin.json` が存在する。
- `check-surface-inventory.py` / `detect-unassigned.py` による構造検証を実行できる環境がある。

## ドメイン知識
- design-gate は 4 elegant condition (C1-C4) を含む `elegant_review` の外形審査であり、component 個別の内容審査 (content_review) とは別軸。
- 審査観点: (1) 5種kindが必要十分か、(2) C02以外の書き込み経路がなくC02もC04 PASS+明示承認+allowlist+hash guardを要求するか、(3) 検知責務と重複しないか、(4) C03/C04 verdictがC10/C07に到達するか。

## 成果物
- design-gate 審査結果 (合格/差し戻し理由)。
- 差し戻し時の component-inventory.json 修正差分 (該当時のみ)。

## スコープ外
- 受入 criteria の詳細導出 (P04 の責務)。
- 実体の生成・実装 (P05 の責務)。

## 完了チェックリスト
- [ ] considered_component_kinds が 5 種全て列挙され、少なくとも skill/sub-agent/slash-command/hook/script の各 1 実体以上が存在する (単一 skill 退化なし)。
- [ ] harness-creatorへの書き込みはC02 apply modeだけで、C04 PASS・明示承認・allowlist・pre-image hash一致を満たさない全経路がfail-closedである。
- [ ] C11がtruncated historyを完全diffとして扱わず、commit pair/digest/completenessを必須にしている。
- [ ] `check-surface-inventory.py` および `detect-unassigned.py` が exit0。

## 参照情報
- `references/harness-creator-spec-reflection.md` (design-gate の焼き込み基準)。
- `component-inventory.json` / `envelope-draft/plugin.json` (P02 成果物)。
- 後続 P04 (承認された設計から受入 criteria を導出する)。
