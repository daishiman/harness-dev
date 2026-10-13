---
name: assign-plugin-package-evaluator
description: 36章 PKG-002〜008 / PKG-014 sub-check を実行したいとき、plugin package の静的検査結果を findings JSON で得たいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Glob, Grep, Bash(python3 *)]
pair: run-plugin-package-check
kind: assign
prefix: assign
effect: conversation-output
role_suffix: evaluator
owner: team-platform
since: 2026-05-23
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md
source-tier: internal
last-audited: 2026-05-23
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-run-pkg-check.md
schema_refs:
  - schemas/findings.schema.json
  - ../ref-pkg-contract/schemas/package-contract.schema.json
script_refs:
  - scripts/validate-plugin-package.py
  - scripts/render-pkg-findings.py
reference_refs:
  - references/evaluator-contract.md
  - ref-pkg-contract
completeness_exempt:
  - "rubric: 判定は ref-pkg-contract の pkg-id-catalog.yaml (reference_refs) にある PKG ID ごとの pass/fail で、点数を合成する rubric.json を持たない。rubric_refs は compose-rubrics と lint-rubric-refs-exist が rubric.json として読むため、catalog を指さない (harness-aor)。"
---

# assign-plugin-package-evaluator

## Purpose & Output Contract

36章 Plugin Package Harness Contract の **PKG-002〜008 / PKG-014 sub-check** を実装する worker skill。`run-plugin-package-check`（B）から呼ばれ、`plugins/<plugin>/` を入力に findings JSON を返す。PKG-001（公式 CLI ラッパー）/ PKG-009（外部参照）/ PKG-010〜013 / PKG-015 は B が直接実装し、本 skill は静的に検証可能な 8 件に責務を絞る。

**入力**:
```yaml
target_plugin: "harness-creator"             # 必須。plugins/<name>/ の name
pkg_ids: ["PKG-002", "PKG-003", "PKG-004", "PKG-005", "PKG-006", "PKG-007", "PKG-008", "PKG-014"]
options:
  output_path: "eval-log/<plugin>/pkg-batch/<date>-<run>.json"  # 任意。複数 PKG ID の一括実行の保存先（呼出元 workflow-manifest.json の pkg-002-008 の output）。1 件だけなら pkg-<id>/
  render: markdown                          # 任意。指定時のみ render-pkg-findings.py で markdown サマリも出力
```

**出力**: `schemas/findings.schema.json` 準拠の findings 配列 + verdict サマリ
**完了条件**: 全 PKG ID で `status ∈ {pass, fail, skip, not_applicable}` が確定し、eval-log に保存されること

## Key Rules

1. **PKG ID 定義は ref-pkg-contract 経由**: 本 skill 内で PKG ID 表を再定義しない（DRY、33章準拠）
2. **findings の thought_method フィールドは不要**: 本 skill は規範的静的検査であり、思考法多視点レビュー（run-elegant-review）とは責務直交
3. **package_mode による適用判定**: `skill-only` plugin に対しては PKG-003/005/006/007/008/014 を `not_applicable` として返す（PKG-002/004 のみ実行）
4. **途中で止めない**: fail が出ても指定された全 PKG ID を走らせて findings を網羅収集する（script に途中停止の option は無い）
5. **eval-log パスは 27章 §3.1**: 本 skill で再定義しない
6. **入力エラーは exit 2**: plugin ディレクトリが無い・`--check` が不正・読み書きできないとき、script は findings を出さずに止まる。出力が `schemas/findings.schema.json` に合うかは script ではなく評価者が最後に確かめる
7. **context: fork 必須**: 親 context の sycophancy 排除（assign-skill-design-evaluator と同じポリシー）

## ゴールシーク実行

evaluator は一度の採点で完結する read-only 工程。ループは回さず、**採点の網羅性をチェックリストで担保**する。正本: `../run-build-skill/references/goal-seek-paradigm.md`（§評価系の扱い）。

### ゴール (Goal)

指定された全 PKG ID（既定 PKG-002〜008 / PKG-014）を採点し、各 finding にエビデンスと severity を付与、全件の `status ∈ {pass, fail, skip, not_applicable}` が確定して `schemas/findings.schema.json` 準拠の findings JSON + verdict サマリが eval-log に返された状態になっている。

### 目的・背景 (Why)

契約適合（PKG check）の中核 8 件を静的検査する worker。採点漏れがあると親 orchestrator の verdict が偽陽性 PASS になるため、規範採点や思考法レビューと直交した「全 rubric 項目の網羅採点」が要る。`context: fork` で親 context の sycophancy を排除する。

### 完了チェックリスト (Checklist)

- [ ] 入力 `pkg_ids` の全項目を採点した（未採点 ID が 0 件）
- [ ] `package_mode=skill-only` の場合 PKG-003/005/006/007/008/014 を `not_applicable` 判定にした
- [ ] 各 finding に `location` と `evidence`（観測根拠）と `severity` が付与されている
- [ ] 全 PKG ID で `status` が確定し、verdict カウント（total/pass/fail/skip/not_applicable）が算出済み
- [ ] 出力が `schemas/findings.schema.json` に準拠する（schema は出力の契約で、script は schema 検証をしない）
- [ ] exit 0 と exit 1（fail あり）では findings JSON を stdout（または `--output`）へ出力した。exit 2（入力エラー）は findings を出さず stderr に理由を出す

### 採点フロー

`Step N:` の固定連番は使わない。チェックリストの未充足項目に応じ、`scripts/validate-plugin-package.py --check pkg-<id> --plugin <name>`（一括なら `--check all`）を必要な PKG ID 分だけ実行して findings を集約する。次に下の「評価者が読んで判定する条件」を読み、違反があればその PKG ID の `findings` に足して `status` を `fail` にする。最後に verdict を数え直し、評価者が `schemas/findings.schema.json` で検証して締める。

## PKG-002〜008 / PKG-014 sub-check 詳細

catalog（`ref-pkg-contract` の `pkg-id-catalog.yaml`）が各 PKG ID に約束する条件のうち、script が機械判定するのは「script が機械判定する条件」の表の分だけ。「評価者が読んで判定する条件」の表は script では判定しないので、評価者が読んで判定する。後者を読まずに script の pass だけで PKG ID を pass にしない。

### script が機械判定する条件

| PKG ID | 検査関数（`validate-plugin-package.py`） | fail 条件 |
|---|---|---|
| PKG-002 | `check_pkg_002` | 公式 `plugin.json` の `name`/`version`/`description`、または `references/package-contract.json` の `package_mode`/`entry_points` のいずれか欠落。`package_mode` が `bundle`/`skill-only` 以外（このときは check を飛ばさず `bundle` として全 check を流す）。`skill_dependencies` のキーが `entry_points.skills` に無い・値が plugin slug の配列でない・重複がある・`depends_on` に無い plugin を指す |
| PKG-003 | `check_pkg_003` | 同じ plugins root の別 plugin と skill 名・agent 名が重なる。symlink で配った skill・agent は数えない。`run-skill-feedback` の配布コピーは中身が一致すれば衝突にしない（一致の判定では `__pycache__`・`.pyc`/`.pyo`・`.DS_Store` を除く） |
| PKG-004 | `check_pkg_004` | 自前 skill（symlink でない）の frontmatter が読めない、または `name`/`description`/`kind` が欠落か空値。`responsibility_refs`/`schema_refs`/`manifest` の欠落か空値は P1（`manifest` は理由付きの `completeness_exempt` で代えられる） |
| PKG-005 | `check_pkg_005` | `agents/*.md` の frontmatter `name` が無いか、ファイル名（拡張子を除く）と違う。自前 skill の `subagent_refs`（block 形式でも flow 形式 `[a, b]` でもよい。`agents/x.md` と書けば `x`）が指す `agents/<name>.md` が無い |
| PKG-006 | `check_pkg_006` | `hooks/` 直下の `*.py`/`*.sh` がどこにも登録されていない（名前は拡張子まで含めて完全一致で比べる。`guard` の登録は `guard.py` を満たさない）。逆に、`hooks/hooks.json`（`plugin.json` に `hooks` キーが無くても Claude Code が読む既定の場所）、`plugin.json` の `hooks`（object ならその中身、文字列か文字列の配列なら指す hooks file の中身）、package contract と `plugin.json` の `entry_points.hooks`、`settings/*.json` の hook command のうち `${CLAUDE_PLUGIN_ROOT}/hooks/…` か `./hooks/…` を指すものに実体が無い、または plugin の外を指す。`plugin.json` の `hooks` が指す file が plugin の中に無い。hooks file が JSON の object として読めない |
| PKG-007 | `check_pkg_007` | plugin root 直下の `scripts/` にある `*.py`/`*.sh` に shebang が無い、または shebang があるのに `+x` が無い |
| PKG-008 | `check_pkg_008` | `settings/*.json` が JSON として読めない、最上位が object でない、`$schema` が無い（P1） |
| PKG-014 | `check_pkg_014` | `kind` / combinator 宣言と goal-seek / feedback runtime 設定・本文配線が不一致 |

各検査は `scripts/validate-plugin-package.py --check pkg-<id> --plugin <name>` 単独実行可能。B からは sub-process でまとめて呼ばれる。

### 評価者が読んで判定する条件

| PKG ID | 判定すること | script で判定しない理由 |
|---|---|---|
| PKG-003 | hook 名・permission 名が同じ marketplace の別 plugin と衝突しない | 何を同じ名前とみなすか（event と matcher の組・permission の pattern の包含）を機械的に決められない |
| PKG-007 | SKILL.md の `script_refs` が指す script が plugin の中に実在し、shebang と `+x` がある。`skills/*/scripts/` の script も同じ | `script_refs` には repo root 起点の vendored 参照や注釈付きの値が混じり、機械判定すると正しい参照まで fail にする |
| PKG-008 | 34a 章 INV-1〜12 を満たし、Layer3（user・project 設定）とのマージで衝突しない | 不変条件の多くは他の設定層との組み合わせで決まり、settings 断片だけでは判定できない |

この表の条件で違反を見つけたら、その PKG ID の `findings` に `location`・`evidence`・`severity` を付けて足し、`status` を `fail` にする。

## findings 出力フォーマット

```json
{
  "run_id": "pkg-validate-harness-creator-20260523-001",
  "target_plugin": "harness-creator",
  "package_mode": "bundle",
  "pkg_checks": {
    "PKG-002": {
      "status": "pass",
      "findings": [],
      "last_run_at": "2026-05-23T12:00:00Z"
    },
    "PKG-006": {
      "status": "fail",
      "findings": [
        {
          "id": "F-PKG006-001",
          "pkg_id": "PKG-006",
          "severity": "P0",
          "location": "/abs/path/to/repo/plugins/harness-creator/hooks/pre-commit.sh",
          "evidence": "hook ファイル実体は存在するが plugin hook 契約に未登録",
          "suggested_fix": "plugins/harness-creator/settings/hooks.json の hooks 配列に追加"
        }
      ],
      "last_run_at": "2026-05-23T12:00:01Z"
    }
  },
  "verdict": {
    "total": 8,
    "pass": 7,
    "fail": 1,
    "skip": 0,
    "not_applicable": 0
  }
}
```

## Gotchas

1. **`scripts/validate-plugin-completeness.py` との関係**: 既存スクリプトは plugin 完全性の総合検査。本 skill の `validate-plugin-package.py` は **PKG ID 別 sub-command** で findings 形式を返す点が異なる。既存をラップせず別実装にする（責務分離）
2. **PKG-001/009 は本 skill 対象外**: B 側で直接実装。本 skill に投げられたら stderr に `unsupported --check value` を出して exit 2 で止まる（`prompts/R1-run-pkg-check.md` の `unsupported_pkg_id` エラー。findings JSON は出さない）
3. **PKG-010〜013 / PKG-015 は対象外**: smoke/permission/rubric 検査は別 skill（B が直接 or 専用 assign）
4. **`skill-only` plugin への PKG-003 適用は禁止**: 名前空間検査は bundle のみ。skill-only に投げられたら `not_applicable` を返す
5. **fail（exit 1）でも findings は必ず JSON 出力**: findings JSON は stdout（`--output` を渡したときはそのファイル）に出す。stderr に出るのは exit 2 の理由だけで、進捗ログは出さない。入力エラー（exit 2）だけは findings を出さず、stderr の理由で止まる

## Additional Resources

- `scripts/validate-plugin-package.py` — PKG-002〜008 / PKG-014 sub-command 実装
- `scripts/render-pkg-findings.py` — findings JSON → 人間可読 markdown レポート
- `schemas/findings.schema.json` — findings JSON 出力 schema
- `prompts/R1-run-pkg-check.md` — R1 単発検査時の応答テンプレ
- `ref-pkg-contract` — PKG ID 表・package-contract schema の正本参照
- 設計書: 36章（正本）、34a §4（PKG-003 共有名前空間）、03章（PKG-004 frontmatter 必須キー）
