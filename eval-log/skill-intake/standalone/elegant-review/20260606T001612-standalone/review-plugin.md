# elegant-review: skill-intake 単独配布自己完結性

- run-id: 20260606T001612-standalone
- target: plugins/skill-intake/ (scope_mode=plugin)
- 主題: 不特定多数が `plugins/skill-intake/` のみ単独 install して使う想定で、他スクリプト/repo固有資産に依存せず自己完結動作する改善になっているか
- 思考法カバレッジ: 30/30 (論理構造10 + メタ発想9 + システム戦略11、skip 0)
- スコープ決定: **A 案 (runtime 自己完結のみ)**。maintainer 資産は doc 配布スコープ宣言で明示しスコープ外

## verdict

| 条件 | before | after |
|---|---|---|
| C1 矛盾なし | FAIL | **PASS** |
| C2 漏れなし | FAIL | **PASS** |
| C3 整合性あり | FAIL | **PASS** |
| C4 依存関係整合 | FAIL | **PASS** |

> after は runtime 自己完結スコープでの判定。maintainer 専用資産 (F6-F9) は「単独 install には不要・未同梱」と doc で明示し、欠落ではなく意図的な配布境界として整理。

## 核心 (3 アナリスト独立収束)

単独 install を阻む真因は **「notion_config.py のコード実体は vendoring したが、それが依存する設定探索アンカー (repo-root) を vendoring し忘れた」**。コード同梱 ≠ 自己完結。破綻経路は 2 本:
1. **config 自動解決** — `notion_config.find_repo_root` が repo-root marker 必須 → 単独 install で空振り
2. **schema 検証 hook** — `validate_intake_schema.py` の `parents[3]` が repo レイアウト前提 → 単独 install で schema 不在 → publish 誤ブロック (SA-01、コアフロー破綻)

## 適用した改善 (Phase 3)

| ID | 内容 | auto_fixable | 実証 |
|---|---|---|---|
| F1 | setup-doc L114 の symlink 記述削除、docstring を vendoring 表現に統一 | true | byte 一致 lint PASS |
| F2 | notion_config に plugin-root フォールバック探索 (`$CLAUDE_PLUGIN_ROOT`→parents[1]) 追加。canonical(skill-creator)+vendored(skill-intake) 両方へ反映し byte 一致維持 | false | 隔離環境で config 解決、get_db_id=TEST-DBID-123 ✓ |
| F3 | validate_intake_schema の `parents[3]`→plugin-root 起点。hook pre-publish-schema-validate と root 解決規約を統一 | true | 隔離環境で env 有無両方 schema exists:True ✓ |
| F5 | setup-doc を単独 install 既定経路に再構成、build/sync-notion-schema を maintainer-only 明示、配布スコープ節追加 (SA-08) | true | doc レビュー |
| — | README の DB ID 解決順に plugin-root 追加、単独インストール節に config 用意前提を明示 | true | doc レビュー |

## 撤回 (二段確認で誤検知と判明)

- **F4 (resource-map.yaml `../../scripts/` が1段不足)**: resource-map の path は SKILL.md (skill-root) 起点。同ファイル L21 の整合パス `../run-skill-intake-aggregator/` がそれを証明。`../../scripts/` は正しく `plugins/skill-intake/scripts/` を指す。Phase1/A2 が references/ 起点と誤読していた。**修正せず**。

## スコープ外 (maintainer 資産、doc で配布境界を明示)

- F6: drift lint/sync が repo-root (canonical=skill-creator)。単独 install では比較相手不在で本質的に monorepo 専用
- F7: lint_subagent_seven_layer.py 等の `parents[3]` (maintainer/CI 用、runtime 非依存)
- F8: vendored-ssot lint の CI 未配線
- F9: verify_standalone.sh が hook 経路/flat-layout 未カバー

→ いずれも「repo 保守者専用・単独 install 不要」と README/setup-doc に宣言。runtime 自己完結要件には影響しない。別途 maintainer 改善 PR の候補。

## 検証ログ

- syntax: `py_compile` OK (notion_config ×2, validate_intake_schema)
- byte 一致: `lint-intake-vendored-ssot.py` PASS (vendored 1 件 byte 一致)
- F2 runtime: 隔離 tmpdir (marker/.git 不在) で `find_config_path(start=neutral)` → plugin-root の `.notion-config.json` 解決
- F3 runtime: 隔離 tmpdir で `SCHEMA_PATH.exists()` env 有無とも True (parents[3] 非依存化を実証)

## proposer ≠ approver

改善 proposer = orchestrator。客観承認は隔離環境での実動作テスト (F2/F3) + byte 一致 lint で代替。最終承認はユーザー。
