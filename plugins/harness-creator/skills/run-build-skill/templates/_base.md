---
# Atomic Composer 骨格（_base.md）
#
# 全 kind 共通の最小骨格。kind 固有の差分は combinators/*.patch を順次適用して合成する。
# 9 種テンプレを「atom (この _base.md) + combinator (差分パッチ)」の和に再編し、
# kind × フラグの組合せ爆発（積）を atom 数 + combinator 数の和に削減する。
#
# combinator 適用順（推奨）:
#   1. kind-specific combinator: with-ref.patch / with-run.patch / with-wrap.patch /
#                                with-assign-evaluator.patch / with-assign-generator.patch /
#                                with-delegate.patch
#   2. optional flag combinators: with-evaluator.patch / with-hooks.patch / with-subagent.patch
#   3. project combinator: with-cross-platform.patch / with-rubric.patch
#
# 各 combinator は unified diff 形式（`patch -p1` 適用可能）。同じセクションを複数 combinator が
# 触る場合の競合は run-build-skill Step 8 で順序保証する（kind-specific が先、flag が後）。
---
name: {{skill_name}}
description: {{description}}
kind: {{kind}}                              # ref | run | wrap | assign | delegate （atomic は旧仕様）
hierarchy_level: {{hierarchy_level}}        # L0 | L1 | L2
owner: {{owner}}
since: {{date}}
rubric_refs: {{rubric_refs | default([])}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal")}}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly")}}
# permissions: 副作用ありスキルは settings.json の permissions.deny に明示禁止を書くこと（設計書04章）
# PreToolUse hook: 文脈依存の危険検査を hook で追加（二段防御）。
---

# {{skill_name}}

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 主要ルール
{{key_constraints}}

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。
> ループを多周回す／重い試行錯誤を伴う場合は、親セッションを汚さないよう SubAgent（`Agent`）または Agent Team に fork して実行し、親へは最終成果物と要約のみ返す（同 references「コンテキスト分離」）。

### ゴール (Goal)
{{goal}}

### 目的・背景 (Why)
{{purpose_background}}

### 完了チェックリスト (Checklist)
{{generated_checklist}}

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成（固定化禁止）→ 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。

## 検証
{{generated_checks}}

## 注意点
{{generated_gotchas}}

## 変数化契約
{{variable_contract}}

## 追加リソース
- `references/`
{{additional_resources}}

## セキュリティと権限
本Skillは副作用を伴う可能性がある。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。
