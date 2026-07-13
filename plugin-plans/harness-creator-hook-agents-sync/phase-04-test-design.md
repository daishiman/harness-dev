---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 完了
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的

C1-C10 を positive/negative/concurrency/trust/freshness の test matrix へ変換する。

## 背景

単純な未反映 fixture だけでは、unknown event 脱落、trust bypass、同時SessionStart、stale evidence、unsupported silent skip を検出できない。

## 前提条件

- P03 design GO。
- 実在 package/test command を `package.json` と runner config から確認する。

## ドメイン知識

- 必須 negative: target unknown preserve、managed unknown block、untrusted hook non-run、unsupported kind report、global/tool-owned write拒否、digest mismatch、別 marketplace の同名 plugin、個人絶対 path 混入、同一 runtime hook 重複、active CI の legacy desired-set command。
- 必須 concurrency: 二重実行、同時2 session、lock timeout、partial write recovery。
- 必須 lifecycle: install/enable/trust、upgrade/re-trust、uninstall/prune。

## 成果物

- AC→test ID→fixture→command→evidence path matrix。
- C01/C02/C03/C05/C04 と repo integration task の focused test plan。

## スコープ外

- 実 test 実行。
- public marketplace/browser UI test。

## 完了チェックリスト

- [ ] C1-C10 の各 criterion に最低1 positive と1 negative がある。
- [ ] concurrency/trust/freshness の各 matrix がある。
- [ ] unsupported kind 0件成功ではなく明示 status を検証する。
- [ ] 実在 command だけを記載する。
- [ ] 別 clone/worktree fixture で全 hook command の展開先が repo 内に実在し、生成物に個人絶対 path が0件となる。
- [ ] `plugin@marketplace` exact identity、foreign marketplace 非選択、source-aware hook dedupe を回帰テストする。
- [ ] 全 `.github/workflows/*.yml` に legacy unfiltered native projection check が0件であることを検査する。
- [ ] runtime ledger は graph/artifact digest と gate別 state を必須とし、user-gated でない P13 node の defer を拒否する。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 同時2 session でも重複 hook/破損 file が0で、別 clone でも command が実在 path へ解決され、warning status が保存される期待値がある。
- 満たさない例: `pytest` とだけ書き fixture/期待差分がない。

### 事前解決済み判断

- coverage 80% だけでなく critical branch を個別 test ID で固定する。

## 参照情報

- `goal-spec.json` checklist C1-C10
- `component-inventory.json`
