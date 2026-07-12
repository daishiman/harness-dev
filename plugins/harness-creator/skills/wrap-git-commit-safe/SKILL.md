---
name: wrap-git-commit-safe
description: git commit を安全側で実行したいとき、機密ファイルやhook無視を防ぎたいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - Read
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git add *)
  - Bash(git commit *)
kind: wrap
prefix: wrap
effect: local-artifact  # wrap-* は base: run-build-skill の effect を継承
base: run-build-skill
owner: team-platform
since: 2026-05-18
version: 0.1.0
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L1
# wrap-* prefix の最小実例。base Skill (run-build-skill) の commit 前後を安全側で被せる。
schema_refs:
  - schemas/wrap-io.schema.json
script_refs:
  - scripts/pre-commit-secret-scan.py
  - scripts/preflight-git-commit.py
reference_refs:
  - references/resource-map.yaml
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: pre-commit-secret-scan.py が機密ファイル(.env credentials.json *.pem)を add 対象から検出した場合に exit 2 で BLOCK し LLM の文字列マッチに依存しない決定論検査として閉じている
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: commit_args や script に --no-verify --no-gpg-sign が含まれる場合と main master への force-push が試行された場合をいずれも決定論的に検出して BLOCK する
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: base(run-build-skill)の commit 手順を上書きせず前後フックとして被せる wrap 責務が allowed-tools と本文で一貫し L1 階層として L0 共通規約に依存する設計が崩れていない
      verify_by: elegant-review
---

# wrap-git-commit-safe

## Purpose & Output Contract

base Skill (`run-build-skill`) の commit ステップを wrap し、機密ファイル混入・hook bypass・force-push を防止する。

**入力**: なし (base から呼ばれる)
**出力**: 安全側で実行された `git commit` の結果、または BLOCK 理由

**完了条件**: commit 成功または BLOCK 理由が提示されている。

## Key Rules

1. **base 継承**: `run-build-skill` の commit 手順を base とし、前後に安全チェックを追加。
2. **--no-verify 禁止**: hook bypass フラグを検出したら即停止。
3. **機密ファイル検出**: `.env`, `credentials.json`, `*.pem` を git add 対象に含めない。
4. **force-push 禁止**: main/master への `git push --force` は常に BLOCK。

## ゴールシーク実行

base Skill (`run-build-skill`) の commit ステップを wrap する実行系。固定手順ではなく、下記ゴール・チェックリストへ向けて反復する（正本 `run-build-skill/references/goal-seek-paradigm.md`）。

### ゴール (Goal)

機密ファイル混入・hook bypass・force-push のいずれもないことが決定論的に確認されたうえで `git commit` が成功している、または BLOCK 理由が提示されている。

### 目的・背景 (Why)

base の commit を上書きせず前後に安全フックを被せ、LLM の文字列マッチに頼らない決定論検査で危険な commit/push を未然に止めるため。

### 完了チェックリスト (Checklist)

- [ ] `pre-commit-secret-scan.py` が exit 0（`.env` / `credentials.json` / `*.pem` 等が add 対象に含まれない）
- [ ] commit_args / script に `--no-verify` / `--no-gpg-sign` が含まれない
- [ ] main/master への `git push --force` が発生していない
- [ ] base (`run-build-skill`) の commit が成功、または上記いずれか不合格時に BLOCK 理由を提示している

### ゴールシークループ

正本の 6 ステップ（現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し）に従う。固有差分は下記局面で未達チェックを埋める。決定論検査は script に寄せ、検査不合格は即 BLOCK（再試行で握り潰さない）。

### 局面カタログ（順序は都度判断）

- **機密ファイル検出 (決定論スキャン)**:

  ```bash
  python3 plugins/harness-creator/skills/wrap-git-commit-safe/scripts/pre-commit-secret-scan.py \
    --repo-root "$(git rev-parse --show-toplevel)" \
    --commit-args "$@"
  ```
  exit 2 で BLOCK。LLM の文字列マッチに依存しない決定論的検査。
- **hook bypass 検出**: ユーザー指示や script に `--no-verify` / `--no-gpg-sign` が含まれていないか確認。検出時は BLOCK。
- **base の commit 実行**: base (`run-build-skill`) の commit 手順を呼ぶ。

## Gotchas

- **wrap は base の代替ではない**: base を上書きせず、前後フックとして振る舞う。
- **L1 階層**: 共通 git 規約 (L0) に依存。プロジェクト固有規約 (L2) はさらに wrap する。

## Additional Resources

- base: `run-build-skill`
- `templates/commit-template.md` — commit message を整形するときに Read
- 設計書: `06-classification-and-naming.md` (wrap-* prefix), `01a-build-flow.md` Step3
