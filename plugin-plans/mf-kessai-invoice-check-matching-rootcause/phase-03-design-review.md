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

# P03 — design-review (レビュー)

## 目的
P02 の設計 (7 component 分解+依存DAG) を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。照合層修正が既存の正当ロジック (evidence/MF実績第一級/fetch fidelity) を割らないことを実装前に確認する gate フェーズ。

## 背景
6要因根治 (収集status拡張・R1-collect決定論化・NEW/年契約分類・取消継続性・代理店collapse保全・MF顧客ID結合) の修正は、既存の正しい動作 (SUPPRESS_ANNUAL/MATCH_ENDED_FINAL 等の既存verdict・PR#85で確立したMF実績第一級) を巻き込んで壊すリスクを持つ。提案者と承認者を分離することで、単一skillへの退化や不要な component 水増しを実装前に検出する。

## 前提条件
- P02 の component-inventory.json (7 component・依存DAG) が確定している。
- elegant-review 4条件 (矛盾なし/漏れなし/整合性/依存整合) の評価枠組みが参照できる。
- レビュアは提案者と別 context で評価する (構造的に proposer≠approver)。

## ドメイン知識
- design-gate = elegant-review C1-C4 を設計スコープ (7 component 分解+依存DAG) に適用したもの。
- proposer≠approver: 設計した主体と承認する主体を context ごと分離する不変条件 (自己承認は無効)。
- 単一skill退化 = 7 component (C01収集status是正/C02 MF顧客ID解決/C03 sink collapse保全/C04 分類是正(NEW・年契約・取消継続・代理店compare)/C05 R1決定論producer(主因)/C06 検証sub-agent/C07 配線skill) が 1 skill へ畳まれ責務分離が失われた状態 (本plan判定対象)。
- goal-spec constraints (GET専用API維持/突合ロジック再発明禁止/evidence据え置き/MF実績第一級非後退/fetch fidelity保全) が design-gate の追加合否軸。

## 成果物
- design-gate の判定記録 (C1-C4 全PASS/差し戻し理由)。

## スコープ外
- 指摘の修正そのもの (P02 へ差し戻して再設計する・review 内で直さない)。
- テスト設計 (P04)・実装 (P05)。
- 機械 lint の実行 (P09 qa gate の責務・本 gate は設計妥当性のみ)。

## 完了チェックリスト
- [ ] elegant-review C1-C4 が全PASSし、proposer と異なる approver が設計を承認している。
- [ ] 単一skill退化 (7 component→1skill畳み込み) や不要 component の水増しが無い。
- [ ] goal-spec constraints (GET専用API維持/evidence据え置き/MF実績第一級非後退/fetch fidelity保全/突合ロジック再発明禁止/個社会社名ハードコード禁止) が設計上維持される確認が取れている。
- [ ] C5 代理店構造 (1商品に複数エンドクライアント・異額) を8列固定レポートで表現する方式 (契約ID/エンドクライアント列追加 vs 合算 vs 明細分割) が本 gate の**ブロッキング決定**として確定している (goal-spec open_questions[0])。この結論は C03/C04 の受入前提であり、未決のまま build へ流さない。

## 参照情報
- P02 成果物 (component-inventory.json)。
- assign-plugin-plan-evaluator (評価ロジックの正本・proposer≠approver)。
- goal-spec.json constraints。
- 後続 P04 (test-design)。
