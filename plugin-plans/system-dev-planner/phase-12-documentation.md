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
system-dev-planner の利用者向けドキュメント (README/setup.md) と、P08 で正本化した `references/system-task-spec-template.md`・`references/system-phase-spec-template.md` を確定する。

## 背景
team-lead からの明示注意: 「system-dev-planner が将来生成するシステム開発タスク仕様書のテンプレート」は本 plugin の `references/`/`assets/` として設計に記載する対象であり、**本 plan 成果物自体 (13 phase + inventory + index + handoff) と混同しない**。本フェーズはこの分離を文書として確定する。

## 前提条件
- P11 の evidence が確定している。

## ドメイン知識
- ドキュメント資産の所在分離: plan 成果物 (本 `plugin-plans/system-dev-planner/` 配下) vs system-dev-planner が build 後に携帯するテンプレート資産 (`plugins/system-dev-planner/references/system-task-spec-template.md`)。
- dev-graph 側の draft (`templates/system-task-spec.md`) は本テンプレート正本への pointer として README に明記する。

## 成果物
- README.md / setup.md (system-dev-planner の使い方)。
- `references/system-task-spec-template.md` / `references/system-phase-spec-template.md` 確定版 (P08 の正本化を最終反映)。
- symlink導入、repo-local config、root診断、no-overwrite init、atomic promotion recovery、dev-graph登録の運用説明。

## スコープ外
- リリース (P13)。

## 完了チェックリスト
- [ ] テンプレート資産 (`references/system-task-spec-template.md`) の所在が plan 成果物と明確に分離して文書化されている。
- [ ] README/setup.md が dev-graph からの呼出しインターフェース (入出力契約) を記載している。
- [ ] 初学者向け説明で「共有されるのは道具、各repoの文書箱は共有しない」と説明し、技術者向けにprecedence/containment/digest/rollbackを記載する。

## 参照情報
- `references/system-task-spec-template.md`。
- `plugin-plans/dev-graph/templates/system-task-spec.md` (draft・pointer 化対象)。
- 後続 P13 (release)。
