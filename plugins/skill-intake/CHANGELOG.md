# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`skill-intake` plugin の変更履歴を記録する。skill-creator 設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [0.1.2] - 2026-07-02

統治レイヤ (composition/ROADMAP/EVALS) の追加と、elegant-review (30 思考法 × 4 条件) の指摘一括反映を含む品質リリース。

### Added

- **plugin-composition.yaml**: skill-creator の CapabilityManifest 仕様 (kindPluginComposition) に準拠した composition manifest を新設。公開 capabilities(10 skills + 4 agents + 4 commands + 8 hook 配線)・11 phase の依存 DAG・contract invariant・governance を宣言し、`.claude-plugin/plugin.json` の entry_points / hooks と1対1対応させた。
- **ROADMAP.md**: 短期 / 中期 / 長期のロードマップを新設し、governance.roadmap の参照先を確立した。
- **EVALS.json**: 公開 capability の evaluation baseline を記録する eval_sink を新設した。
- **mode P (plugin-dev-planner 連携)**: `run-intake-next-action` の引き渡しモードに P (plugin 規模構想 → `run-plugin-dev-plan` R1 へ intake.json を構想材料として引き渡し) を新設。`next-action.json` に `handoff_target` を追加し、intake → タスク仕様書 → skill-creator の三段パイプラインを契約化した。
- **mmdc preflight**: `validate-notion-ready.py` に mermaid-cli (mmdc) 存在検査を追加。README §1 前提条件表に Node.js + mmdc を必須行として明記した。
- **初回 publish 翻訳経路**: `intake_publish_pipeline.py` が初回実行時に intake.json の `notion_target.mode=='create-explicit'` かつ `allow_create==true` を `--allow-create` へ翻訳し、初回公開の実行主体不在を解消した。

### Changed

- **render 系 fail-fast 統一**: `render_to_image.py` / `render_to_svg.py` の mmdc 不在時 placeholder fail-open を廃止し、execution-contract 準拠の exit 3 (DEPENDENCY_ERROR) に統一。placeholder は `--allow-placeholder` (CI/テスト専用) へ隔離した。
- **All-or-Nothing 検査の常時実行化**: `intake_publish_pipeline.py` の verify_notion_assets を `--manifest` 任意指定から既定パス自動解決の常時実行へ変更 (skip は `--skip-assets` 明示のみ)。
- **fixed config の安全化**: `notion-config.fixed.json` の `parent_page` を空文字化 (従来は DB ID と同一値で DB 新規作成が必ず失敗)。`create_notion_database.py` に親ページ空/DB ID 同一値の fail-closed ガードを追加。死にキー `schema_dir` と空 `db_id` エントリを除去した。
- **handoff 契約の v2 一本化**: `handoff-contract.md` のインライン v1 schema (schema_version 1.0.0) を削除し `intake.schema.json` (2.0.0, sections 12 章) を唯一の正本に。skill-creator 向け対応表を v2 パスへ更新、mode-catalog の渡し先語彙を run-skill-create の実在語彙へ是正した。
- **secret-scrub hook の対象限定**: `pre-publish-secret-scrub.sh` に publish コマンド検出 gate を追加し、無関係な Bash 呼び出しの誤遮断を解消 (fail-closed 性質は不変)。
- **README 導線是正**: 出力先 DB 設定を必須ステップ 7-1 へ昇格 (既定固定 DB は保守者専用で外部 Integration からは 403)、存在しないスクリプト参照 (`smoke_plugin_vendor.py`) と `.claude/settings.json.example` 参照を修正、config 解決順の記述をファイル単位先勝ちの実装実態へ正確化した。

### Removed

- **移行残置物の配布除外**: `migration-plan-v2.md` / `RENAME_PLAN.md` / `m3_deprecation_reverse_index.py` / `convert_v1_to_v2_context.py` を `package.exclude` へ追加 (repo には残置、配布パッケージからのみ除外)。

### Fixed

- SKILL.md 散文の phase 番号 drift 3 件 (visualize P7 / next-action P11 / publish P10) を workflow-manifest 正へ統一。
- `handoff.schema.json` の PostCompact hook 復元宣言を実態 (append-only 記録) へ修正。
- `EVALS.json` の assign-notion-fidelity-evaluator kind (run → assign) を frontmatter 正本と一致させた。
- intake-final schema の二重定義 (enum 競合) を正本一本化で解消。

### Notes

- 統治レイヤ (composition manifest + changelog/roadmap/evals) の追加により skill-creator 仕様へのフル準拠を達成する (命名規約・CapabilityManifest frontmatter・PKG-002〜008 パッケージ検査は既存で PASS 済み)。

## [0.1.1] - 2026-06-07

### Changed

- `.claude-plugin/plugin.json` の skills / agents / commands / hooks 独自宣言を予約フィールドから `entry_points` へ退避し、`package_mode: bundle` と `version: 0.1.1` を明示した。
- marketplace install のポータビリティ不変条件 (cwd 非依存 import + 純ソース配布) を `validate-plugin-vendor.py` で検証する CI step を追加した。

## [0.1.0] - 2026-05-22

### Added

- 初期リリース。非技術者向けヒアリング orchestration と Markdown 正本 + JSON 副本 + Notion ページの3成果物生成、macOS Keychain 経由の Notion publish を提供。
