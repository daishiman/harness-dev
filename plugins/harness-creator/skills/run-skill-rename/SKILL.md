---
name: run-skill-rename
description: Skill名を変更するとき、改名後の参照整合を確認するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[old-skill-name] [new-skill-name]"
arguments: [old_name, new_name]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
  - Bash(git *)
kind: run
prefix: run
owner: team-platform
since: 2026-05-18
version: 0.1.0
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
effect: local-artifact
responsibility_refs:
  - prompts/R1-rename.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)。content-review verdict の criteria_evaluated と突合
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 改名後の新名 SKILL.md が lint-skill-name と lint-skill-tree と validate-frontmatter を全て exit0 で通過する
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: ディレクトリ改名が git mv で履歴保持され frontmatter.name が新名へ更新され aliases に旧名が登録された不可分セットが全て満たされる
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: OUT_BASE 配下 SKILL.md 全体の pair と Skill() 旧名参照を漏れなく走査し全ヒットが新名へ更新され参照切れが残らない
      verify_by: elegant-review
---

# run-skill-rename

## Purpose & Output Contract

スキルを安全に改名するワークフロー（A5/C2: 未実装スキルの新規作成）。

**入力**: old_name (現在のスキル名), new_name (新しいスキル名)
**出力**:
- 改名済みディレクトリ `$OUT_BASE/<new-name>/`
- SKILL.md frontmatter の `name:` 更新
- `aliases:` に旧名を追加
- `CHANGELOG.md` に改名エントリ追加
- 参照元スキルの `pair:` / `Skill()` 記述を新名に更新

**完了条件**: lint-skill-name.py, lint-skill-tree.py が exit 0。

## Key Rules

1. **ディレクトリ名 == frontmatter.name**: 第8条。改名後は両方を同時更新。
2. **alias必須**: 旧名を `aliases:` に登録して参照切れを防ぐ（第6条）。
3. **CHANGELOG必須**: 改名エントリを `references/CHANGELOG.md` に追加（第6条）。
4. **参照元更新**: `pair:` / `Skill()` の旧名参照を新名に更新する。
5. **gitの履歴保持**: `git mv` を使い、ファイル移動の履歴を残す。

## ゴールシーク実行

### ゴール (Goal)

旧名スキルが `$OUT_BASE/<new-name>/` へ git 履歴を保ったまま改名され、frontmatter.name・aliases・CHANGELOG・全参照元 (`pair:`/`Skill()`) が新名で整合し、lint-skill-name.py / lint-skill-tree.py が exit 0 の状態になっている。

### 目的・背景 (Why)

ディレクトリ名・frontmatter.name・参照は同時に一致させないと参照切れを生む (第8条)。部分更新で不整合が起きやすいため、固定手順ではなく「全箇所が新名で整合した状態」へ向けて未達箇所を都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `resolve-skill-dirs.py` で `$OUT_BASE` (eval-log/skill-dirs.json) が解決済み
- [ ] 旧名 `$OUT_BASE/$OLD_NAME/SKILL.md` の存在を確認済み、新名 `$OUT_BASE/$NEW_NAME` は未存在 (重複なし)
- [ ] 新名が `lint-skill-name.py --name "$NEW_NAME"` の命名規約を通過
- [ ] ディレクトリが `git mv` で改名され git 履歴が保持されている (rm+mkdir 禁止)
- [ ] 新 SKILL.md frontmatter の `name:` が `$NEW_NAME` に更新され、`aliases:` に `$OLD_NAME` が登録されている (第6条、参照切れ防止)
- [ ] `references/CHANGELOG.md` に改名エントリ (date / 旧→新 / Reason / aliases) が追記されている (第6条)
- [ ] `pair:` / `Skill()` の旧名参照を `$OUT_BASE/` 配下 SKILL.md 全体から grep し、ヒット各所が新名へ更新されている
- [ ] `lint-skill-name.py`・`lint-skill-tree.py`・`validate-frontmatter.py` (新 SKILL.md) が全て exit 0

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。本スキル固有の差分:

- **対象パス**: `$OUT_BASE` は `resolve-skill-dirs.py` 出力。入出力は `$OUT_BASE/$OLD_NAME` → `$OUT_BASE/$NEW_NAME`。
- **不可分セット**: ディレクトリ改名・frontmatter.name・aliases は必ずひとまとめで満たす (どれか欠けると参照不整合)。
- **検証コマンド**: `lint-skill-name.py "$OUT_BASE/$NEW_NAME/SKILL.md"` / `lint-skill-tree.py "$OUT_BASE/$NEW_NAME"` / `validate-frontmatter.py`。いずれか非 0 なら frontmatter/参照更新へ差し戻す。
- 参照元検索: `grep -r "$OLD_NAME" "$OUT_BASE/" --include="SKILL.md" -l`。

## Gotchas

- **git mv 省略禁止**: `rm` + `mkdir` で移動すると git 履歴が途切れる。
- **alias 追加忘れ**: alias なしで旧名参照があると呼び出し先が消える。
- **CHANGELOG 省略禁止**: 第6条違反。CI で検出される。
- **部分更新**: ディレクトリ名だけ or frontmatter だけの更新は不整合を生む。改名・frontmatter.name・aliases は必ずセットで満たす。

## Additional Resources

- `06-classification-and-naming.md` — 命名規約 第6条（改名手続き）
- `13-checklists.md` — 命名規約条文チェックリスト
- `plugins/skill-governance-lint/scripts/lint-skill-name.py` — 命名検証
- `plugins/harness-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py` — OUT_BASE 解決スクリプト
