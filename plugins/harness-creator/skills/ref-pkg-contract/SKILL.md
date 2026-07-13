---
name: ref-pkg-contract
description: 36章 PKG-001〜017 と package-contract.json schema を参照するとき、PKG ID の意味・適用 package_mode・eval-log 保存先を判断するときに読む。
disable-model-invocation: false
user-invocable: false
allowed-tools: [Read]
kind: ref
prefix: ref
effect: none
owner: team-platform
since: 2026-05-23
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md
source-tier: internal
last-audited: 2026-05-23
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-lookup-pkg.md
schema_refs:
  - schemas/package-contract.schema.json
---

# ref-pkg-contract

## Purpose & Output Contract

36章 Plugin Package Harness Contract の **PKG-001〜017 ID 表** と **`package-contract.json` JSON Schema** を機械可読化した参照専用 skill。`run-plugin-package-check`（B）と `assign-plugin-package-evaluator`（C）が同一定義を共有するためのシングルソース。

**入力**: PKG ID（PKG-001〜015、PKG-013a〜d、PKG-016/017 予約）または `package_mode` 値（`bundle` / `skill-only`）
**出力**: ID 意味・実装スクリプトパス・適用 package_mode・eval-log 保存先パス・ governance 制約

## Key Rules

1. **正本は 36章本体**: 本 skill は参照便宜のための圧縮表現。意味の正本は `doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md` §PKG-001〜017 一覧。ただし**機械処理上**は二層正本で、36章本文と `references/pkg-id-catalog.yaml` に齟齬が出た場合は R1-lookup-pkg (CONST_002) が catalog 値を機械可読正本として採用し `warn: catalog_doc_drift` を併記する（doc-only 更新で CI を止めないため）
2. **改廃は 27章 §4.1 governance 経由**: 本 skill 単独で PKG ID 表を増減しない（自己制約）
3. **eval-log パスは 27章 §3.1 規約**: `eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.{json,log}`。本 skill で再定義しない
4. **schema は外部ファイル**: `schemas/package-contract.schema.json` を一次。本 skill 本文には例示のみ
5. **`package_mode: skill-only` は 3 例外限定**: legacy / dev-only / migration。それ以外で参照されたら governance escalation
6. **予約 ID（PKG-016/017）は未確定として扱う**: 意味確定前の参照は warn を返す

## PKG ID 早見表

| ID | 名称 | 適用 package_mode | 実装スクリプト | Phase |
|---|---|---|---|---|
| PKG-001 | `claude plugin validate --strict` 通過 | bundle | `scripts/run-plugin-validate-strict.sh` | 0 |
| PKG-002 | `plugin.json` frontmatter 完備 | bundle, skill-only | `scripts/validate-plugin-package.py --check pkg-002` | 0 |
| PKG-003 | package 単位の名前空間衝突検査 | bundle | `scripts/validate-plugin-package.py --check pkg-003` | 0 |
| PKG-004 | SKILL.md frontmatter 完備 | bundle, skill-only | `scripts/validate-frontmatter.py` | 0 |
| PKG-005 | Agent definition 整合 | bundle | `scripts/validate-plugin-package.py --check pkg-005` | 0 |
| PKG-006 | Hook registration 整合 | bundle | `scripts/validate-plugin-package.py --check pkg-006` | 0 |
| PKG-007 | script 存在 + 実行可能 | bundle | `scripts/validate-plugin-package.py --check pkg-007` | 0 |
| PKG-008 | settings 断片 lint | bundle | `scripts/validate-plugin-package.py --check pkg-008` | 0 |
| PKG-009 | 外部参照ゼロ | bundle | `scripts/lint-external-refs.py --skills-dir plugins/<plugin>/skills --fail-on-external` | 0 |
| PKG-010 | install smoke | bundle | `scripts/smoke-plugin-install.sh` | 1 |
| PKG-011 | uninstall 完全性 | bundle | `scripts/smoke-plugin-uninstall.sh` | 2 |
| PKG-012 | upgrade 冪等性 | bundle | `scripts/smoke-plugin-upgrade.sh` | 2 |
| PKG-013a | tool permissions scope | bundle | `scripts/validate-plugin-permissions.py --plugin <name> --check 013a` | 2 |
| PKG-013b | filesystem permissions scope | bundle | `scripts/validate-plugin-permissions.py --plugin <name> --check 013b` | 2 |
| PKG-013c | network permissions scope | bundle | `scripts/validate-plugin-permissions.py --plugin <name> --check 013c` | 2 |
| PKG-013d | MCP/external permissions scope | bundle | `scripts/validate-plugin-permissions.py --plugin <name> --check 013d` | 2 |
| PKG-014 | runtime contract 検証 | bundle | `scripts/validate-plugin-package.py --check pkg-014` | 2 |
| PKG-015 | rubric 違反率しきい値 | bundle | `scripts/lint-rubric-violation.py --logs <log-dir>` | 2 |
| PKG-016 | 予約（未確定） | - | - | - |
| PKG-017 | 予約（未確定） | - | - | - |

## eval-log 保存規約（27章 §3.1 引用）

```
eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.{json,log}
```

例: `eval-log/harness-creator/pkg-010/2026-05-23-001.json`

PKG fail は 35章 `pkg_check_failed` failure_mode として observable 集約される。

## package_mode

| `package_mode` | 適用 PKG ID | 用途 |
|---|---|---|
| `bundle` | PKG-001〜015 全て必須 | 新規量産の既定値 |
| `skill-only` | PKG-002/004 のみ任意適用 | legacy / dev-only / migration の 3 例外限定 |

`skill-only` 選択時は `references/package-contract.json` の `package_mode_exception` に `legacy` / `dev-only` / `migration` のいずれかを記録すること（schema enforced）。公式 CLI が読む `.claude-plugin/plugin.json` には harness 専用キーを混在させない。

## Gotchas

1. **PKG ID 新設禁止**: 表に存在しない ID を本 skill で受理しない。governance を通すこと
2. **PKG-013 は単独存在しない**: 必ず 013a/b/c/d の 4 sub-check に展開
3. **`skill-only` での PKG-001/003/005-015 適用は no-op**: skip 扱いではなく適用対象外として `status: not_applicable` を返す
4. **schema 直接編集禁止**: `schemas/package-contract.schema.json` の変更は P0_breaking。33章 proposal 必須
5. **PKG-016/017 を実装着手するときは本 skill 表を先に governance 経由で更新**

## Additional Resources

- `schemas/package-contract.schema.json` — `package-contract.json` の正本 JSON Schema
- `references/pkg-id-catalog.yaml` — PKG ID メタデータ（severity、適用 phase、依存スクリプト）の機械可読版
- `prompts/R1-lookup-pkg.md` — PKG ID 単発参照時の応答テンプレ（R1）
- 設計書: 36章（正本）、27章 §3.1/§4.1、34章 Phase 0/1/2、35章 observables
