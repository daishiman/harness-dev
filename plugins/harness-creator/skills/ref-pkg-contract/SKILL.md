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
version: 0.2.0
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

script の path は `plugins/harness-creator/skills/` からの相対。`<plugin>` は検査する plugin の名前で、`--plugin <plugin>` は省けない（省くと exit 2）。install 先で plugin の dir を直に渡すときは、validate-plugin-package.py と validate-plugin-permissions.py に `--plugin-dir <dir>` を使う。

| ID | 名称 | 適用 package_mode | 実装スクリプト | Phase |
|---|---|---|---|---|
| PKG-001 | `claude plugin validate --strict` 通過 | bundle | `run-plugin-package-check/scripts/run-plugin-validate-strict.sh --plugin <plugin>` | 0 |
| PKG-002 | `plugin.json` frontmatter 完備 | bundle, skill-only | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-002` | 0 |
| PKG-003 | package 単位の名前空間衝突検査 | bundle | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-003` | 0 |
| PKG-004 | SKILL.md frontmatter 完備 | bundle, skill-only | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-004`（repo の clone では `scripts/validate-frontmatter.py --skills-dir plugins/<plugin>/skills` も使える） | 0 |
| PKG-005 | Agent definition 整合 | bundle | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-005` | 0 |
| PKG-006 | Hook registration 整合 | bundle | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-006` | 0 |
| PKG-007 | script 存在 + 実行可能 | bundle | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-007` | 0 |
| PKG-008 | settings 断片 lint | bundle | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-008` | 0 |
| PKG-009 | 外部参照ゼロ | bundle | `run-plugin-package-check/scripts/lint-pkg-009.py --skills-dir plugins/<plugin>/skills --fail-on-external` | 0 |
| PKG-010 | install smoke | bundle | `run-plugin-package-check/scripts/smoke-plugin-install.sh --plugin <plugin>` | 1 |
| PKG-011 | uninstall 完全性 | bundle | `run-plugin-package-check/scripts/smoke-plugin-uninstall.sh --plugin <plugin>` | 2 |
| PKG-012 | upgrade 冪等性 | bundle | `run-plugin-package-check/scripts/smoke-plugin-upgrade.sh --plugin <plugin>` | 2 |
| PKG-013a | tool permissions scope | bundle | `run-plugin-package-check/scripts/validate-plugin-permissions.py --plugin <plugin> --check 013a` | 2 |
| PKG-013b | filesystem permissions scope | bundle | `run-plugin-package-check/scripts/validate-plugin-permissions.py --plugin <plugin> --check 013b` | 2 |
| PKG-013c | network permissions scope | bundle | `run-plugin-package-check/scripts/validate-plugin-permissions.py --plugin <plugin> --check 013c` | 2 |
| PKG-013d | MCP/external permissions scope | bundle | `run-plugin-package-check/scripts/validate-plugin-permissions.py --plugin <plugin> --check 013d` | 2 |
| PKG-014 | runtime contract 検証 | bundle | `assign-plugin-package-evaluator/scripts/validate-plugin-package.py --plugin <plugin> --check pkg-014` | 2 |
| PKG-015 | rubric 違反率しきい値 | bundle | `run-plugin-package-check/scripts/run-pkg-015.py --plugin <plugin> --log-dir <log-dir> --out <pkg-log>` | 2 |
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

`package_mode` と `package_mode_exception` は `references/package-contract.json` に書く。`skill-only` 選択時は `package_mode_exception` に `legacy` / `dev-only` / `migration` のいずれかを記録すること（schema enforced）。公式 CLI が読む `.claude-plugin/plugin.json` には harness 専用キーを混在させない（PKG-002 は plugin.json に `name`/`version`/`description`、package-contract.json に `package_mode`/`entry_points` を求める）。

`distribution.distributable` は Claude marketplace の従来契約。Codex 配布は独立の
`codex_distribution` で宣言し、`marketplace=.agents/plugins/marketplace.json`、
`source=./plugins/<plugin-name>` を使う。製品間で公開可否が異なる場合に、
Claude 側を true へ強制的に引き上げない。Codex projection は
`run-codex-plugin-package` / `sync-plugin-platforms.py` が生成・検査する。
根拠は `schemas/package-contract.schema.json` の `codex_distribution`（36 章の埋め込み schema は骨格だけで、この key を載せていない）。

## plugin root の外への参照（PKG-009）

SKILL.md が plugin root の外を名指ししてよいのは、`package-contract.json` で宣言したものと、lint の既定の許可 prefix だけ。

既定の許可 prefix（`.claude/`・`eval-log/`・`references/`・`scripts/`。lint-external-refs.py の `DEFAULT_ALLOWED_PREFIXES`）で始まる参照は、宣言なしで通り、実在も確かめない。plugin の中の `scripts/` と repo root の `scripts/` を見分けないので、実在しない path もこの経路で通る。PKG-009 の pass は「宣言の無い外部参照が無い」ことだけを示し、名指しした path が解決できることは示さない。

| 宣言 | 使う場面 | lint の確かめ方 |
|---|---|---|
| `depends_on` | install 先でも要る plugin | `plugins/<名前>/` の参照を依存として通す |
| `runtime_dependencies`（owned-vendored） | 他 plugin が正本の skill を写して持つ | 写しが正本と byte で同じときだけ、参照の扱いを正本に任せる |
| `repo_refs` | repo の clone の中にだけある設計書や、循環になるので `depends_on` に入れられない兄弟 plugin | 参照ごとに repo の中で実在を確かめる。`prefix` か `exact` で書き、`exact` には実在を確かめる先の `target` を書ける |

`repo_refs` は install した plugin の中には無い資産なので、install 先では実在を確かめられず fail になる。使われていない宣言も fail にする（許可の範囲が黙って広がらないため）。

## Gotchas

1. **PKG ID 新設禁止**: 表に存在しない ID を本 skill で受理しない。governance を通すこと
2. **PKG-013 は単独存在しない**: 必ず 013a/b/c/d の 4 sub-check に展開
3. **`skill-only` での PKG-001/003/005-015 適用は no-op**: skip 扱いではなく適用対象外として `status: not_applicable` を返す
4. **schema 直接編集禁止**: `schemas/package-contract.schema.json` の破壊的変更（required の追加・enum の削除・`pkg_checks` の pattern の変更）は P0_breaking で、33章 proposal 必須（36章 §更新ルール 3）。それ以外の変更も 27章 §4.1 を通し、governance-log に記録する
5. **PKG-016/017 を実装着手するときは本 skill 表を先に governance 経由で更新**

## Additional Resources

- `schemas/package-contract.schema.json` — `package-contract.json` の正本 JSON Schema
- `references/pkg-id-catalog.yaml` — PKG ID メタデータ（severity、適用 phase、依存スクリプト）の機械可読版
- `prompts/R1-lookup-pkg.md` — PKG ID 単発参照時の応答テンプレ（R1）
- 設計書: 36章（正本）、27章 §3.1/§4.1、34章 Phase 0/1/2、35章 observables
