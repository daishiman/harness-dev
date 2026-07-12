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
effect: local-artifact  # wrap-* は base: run-build-skill の effect を継承
base: run-build-skill
owner: team-platform
since: 2026-05-18
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L1
# wrap-* prefix の最小実例。base Skill (run-build-skill) の commit 前後を安全側で被せる。
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

## Steps

### Step 1: 機密ファイル検出 (決定論スキャン)

```bash
python3 creator-kit/skills/wrap-git-commit-safe/scripts/pre-commit-secret-scan.py \
  --repo-root "$(git rev-parse --show-toplevel)" \
  --commit-args "$@"
```
exit 2 で BLOCK。LLM の文字列マッチに依存しない決定論的検査。

### Step 2: hook bypass 検出

ユーザー指示や script に `--no-verify` / `--no-gpg-sign` が含まれていないか確認。検出時は BLOCK。

### Step 3: base の commit 実行

base (`run-build-skill`) の commit 手順を呼ぶ。

## Gotchas

- **wrap は base の代替ではない**: base を上書きせず、前後フックとして振る舞う。
- **L1 階層**: 共通 git 規約 (L0) に依存。プロジェクト固有規約 (L2) はさらに wrap する。

## Additional Resources

- base: `run-build-skill`
- 設計書: `06-classification-and-naming.md` (wrap-* prefix), `01a-build-flow.md` Step3
