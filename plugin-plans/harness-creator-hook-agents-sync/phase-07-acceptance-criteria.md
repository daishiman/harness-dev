---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的

goal checklist C1-C10 を evidence と1:1照合し、plan/build/local/runtime の状態を分離して判定する。

## 背景

旧計画は route build 完了だけで Makefile/CI/apply/trust を含む目的達成と誤認できた。受入は outcome 別に判定する。

## 前提条件

- P06 local evidence 完了。
- artifact digest が current files と一致する。

## ドメイン知識

- state: spec_ready / local_implementation_pass / runtime_activation_pending / runtime_verified。
- C6 trust runtime は user-gated。未実行は pending であり FAIL 隠蔽ではない。
- C9 freshness FAIL は他 criterion PASS を無効化する。

## 成果物

- C1-C10 acceptance table (criterion/evidence/status/owner/next gate)。
- local vs runtime boundary verdict。

## スコープ外

- missing evidence の口頭補完。
- partial PASS での早期終了。

## 完了チェックリスト

- [ ] C1-C10 全行に current digest の evidence がある。
- [ ] local/runtime pending が分離される。
- [ ] unsupported kind が明示 status を持つ。
- [ ] 4条件を全て再判定する。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: Codex trust 未実行なら local PASS + runtime pending と明記される。
- 満たさない例: route 5件 done を理由に runtime verified とする。

### 事前解決済み判断

- runtime pending を completion へ自動昇格しない。

## 参照情報

- `goal-spec.json`
- P06 evidence
