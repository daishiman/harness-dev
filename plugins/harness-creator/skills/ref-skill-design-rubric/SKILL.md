---
name: ref-skill-design-rubric
description: SKILL.mdを評価するとき、新規Skillを設計するときに読む。
disable-model-invocation: true
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-05-17
version: 0.1.0
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-search-summarize.md
---

# ref-skill-design-rubric

## Purpose & Output Contract

Skill 設計の評価基準の **正本（upstream rubric）**。
`assign-skill-design-evaluator` は本Skillの `references/rubric.json` を継承して採点する。

**出力**: なし（reference）。読み手は人間 or evaluator Skill のみ。

## Key Rules

1. **本Skillが唯一の正本**: 他Skillの `references/rubric.json` は本ファイルを upstream とし deep-merge する（29章）。
2. **threshold 80 / max 100**: severity weights は high -20, medium -10, low -3 固定。
3. **rubric_version は semver**: minor=緩和、major=厳格化、patch=文言だけ（`run-skill-rubric-governance` 参照、27章）。
4. **改正は governance runbook 経由**: 直接編集禁止。
5. **判断箇所は AI 起案 + 根拠記録 (TODO(human) で凍結しない)**: 方針決定を要する rule も固定 `TODO(human)` で空欄放置せず、AI が文脈から check 式を起案し rationale に根拠を残す。人間関与は governance runbook の承認段 (proposer≠approver) で担保する。BD-004 はこの方針に従い 1.2.0 で実ルール化済 (description↔body 整合の LLM judge)。

## 評価軸サマリ

kind 別ディスパッチ (rubric.json `supported_kinds` = skill/agent/hook/command/plugin-composition/prompt/workflow)。共通核 (kind=skill) の FM/BD/NM/PD/RG に加え、1.2.0 で kind 別 area、1.3.0 で KL を追加した全 41 rule。

- **FM (Frontmatter, kind=skill)**: name kebab+prefix / description="Use when" / trigger 2-3 / 動作詳細混入なし / 動詞ベース
- **BD (Body, kind=skill)**: Output contract / Gotchas 節 / <=300行 / BD-004=description↔body 整合 (LLM judge)
- **NM (Naming, kind=skill)**: ディレクトリ名一致 / 第1〜5条 / 第8〜13条
- **PD (Progressive Disclosure, kind=skill)**: 本文 <=100 or references/ 存在
- **RG (Governance, kind=skill)**: rubric_hash 埋込
- **AG (Agent, kind=agent)**: tools 明示 allowlist / Isolation・Context Boundary 節 / phase 一意 id / Handoff・Output Contract 節
- **HK (Hook, kind=hook)**: event enum / matcher 具体 (wildcard 不可) / timeout bound / 副作用明記
- **CM (Command, kind=command)**: argument-hint / allowed-tools 最小 allowlist / entrypoint skill 実在
- **PC (Plugin Composition, kind=plugin-composition)**: capabilities[] 列挙 / 依存 DAG (循環なし) / rubric 参照解決 / hook 配線
- **PR (Prompt Structure, kind=prompt)**: 7 層構造 / Self-Evaluation 節 / Output Format・Output Contract 節
- **WF (Workflow Structure, kind=workflow)**: phase 順序番号 / gate 条件 / max_iterations 安全弁
- **KL (Knowledge Loop)**: knowledge/ 6 必須フィールド / 決定論 script + LLM 段分離 / §12 feedback 配線 / 分割閾値 (500行/25エントリ)

各ルールの check 式と rationale は `references/rubric.json` を参照 (kind 別 rule は 1.2.0、KL-* は 1.3.0 追加。`_kind_dispatch_doc` 参照)。

## Steps

参照用Skill。手順なし。改正手順は `run-skill-rubric-governance` を呼ぶこと。

## Gotchas

- **本Skillを直接編集しない**: `run-skill-rubric-governance` の Runbook 経由でのみ更新（27章）。
- **rule の check 式変更は governance を通す**: rubric 変更は minor/major 扱い。直接編集は禁止 (KeyRule4)。新規 rule も TODO(human) で凍結せず AI が起案し rationale を残す (KeyRule5)。

## Additional Resources

- `references/rubric.json` — 機械可読rubric（正本）
- `references/rubric-rationale.md` — 各ルールのwhy
- 関連: `assign-skill-design-evaluator/references/rubric.json`（override層）
- 関連: `run-skill-rubric-governance/` — 改正Runbook
