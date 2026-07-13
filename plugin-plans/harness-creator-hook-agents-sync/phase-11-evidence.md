---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 完了
gate_type: evidence
entities_covered: [C05]
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的

local machine evidence と user-gated Codex install/enable/trust runtime evidence を分離して収集する。

## 背景

Codex plugin hook は manifest/marketplace が正しくても trust 前には実行されない。build成功、local static PASS、runtime activation PASSを混同しない。

## 前提条件

- P10 final GO。
- runtime mutation はユーザーの明示承認後のみ。

## ドメイン知識

- local evidence: lint/schema/build-trace/content-review/coverage + manifests/marketplace/parity/failure logs。
- runtime evidence: install、enable、trust review、new session、SessionStart status、uninstall/prune。
- trust 定義変更時は re-trust pending へ戻る。

## 成果物

- local evidence manifest と raw logs。
- user-gated runtime evidence ledger (`present|pending_user_gate|n/a`)。
- redacted diff sample、source manifest/marketplace hash snapshot、created-path inventory、fixture 内の rollback→restore 実行結果。

## スコープ外

- 承認なしの plugin install/enable/trust。
- screenshot を機械ログの代替にすること。

## 完了チェックリスト

- [ ] local evidence 全件 present。
- [ ] trust前 non-run と trust後 run の両証跡がある、または pending_user_gate と明記される。
- [ ] SessionStart warning が child failure detail/remediation を保持する。
- [ ] global/beads/secret/PII diff 0。
- [ ] install/uninstall/prune 後の orphan 0。
- [ ] local evidence は artifact path+SHA-256+graph hash+UTC timestamp を持つ schema-valid ledger で、runtime user gate と local-required gate を混同しない。
- [ ] rollback は reverse `--check` だけでなく、fixture 内で managed path を実際に戻して source snapshot と一致させ、その後再 apply/restore で current desired state へ復帰できる。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 未承認 runtime は pending とし、local static PASS だけを明確に報告する。
- 満たさない例: manifestが存在するだけで hook発火済みとする。

### 事前解決済み判断

- runtime user gate が残る場合、workflow state は runtime_verified にしない。

## 参照情報

- OpenAI Codex plugin hook trust contract
- P10 final verdict
