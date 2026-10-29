# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`prompt-creator` plugin の変更履歴を記録する。設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased] - 2026-07-02 宣言型転換 (elegant-review run 20260702T065933)

### Added
- **Layer 5 契約 (l5-contract v2.0.0)** を `seven-layer-format.md` に単一正本化 (5.2 ゴール定義 / 5.3 完了チェックリスト=停止条件 / 5.4 実行方式=6ステップ+Anchor)。旧「5.2 推論手順 / 5.3 自己検証 checklist」は廃止宣言。従属者一覧+版数併記義務を明記。
- `prompt-brief.schema.json` に `goals[]` / `checklist[]` (required) / `purpose` / `background` / `user_confirmed` を追加 (宣言型の中核材料が elicit→build で脱落していた欠陥の解消)。`hearing-result.schema.json` に `goals` / `checklist` required 化と `evaluation_priorities` enum SSOT (日本語5値・最大2) を定義。
- `verify-completeness.py`: 固定手順検出の強化 (「推論手順/思考プロセス/手順/Steps」見出し配下の連番列挙を FAIL、実行方式ループは allowlist)、`--layers` サブセット検査、failfast 化。
- `run-prompt-creator-7layer` に worker 内蔵設計ゲート (`phase-design-gate`: C1-C4 fork 評価を完了条件へ内蔵、呼出経路非依存) と Phase 4-C 中間アンカー配線 (goal-seek-loop schema 正本参照)。
- `tests/test_prompt_creator_7layer_l5_contract.py` (19件): 検出強化 / --layers / parity (lint-agent-prompt-section 双方向互換) / **self-scan 自己適用 dogfooding ゲート (plugin 所有 6 prompts 全件 PASS を機械強制)**。
- README 冒頭に 1 分判別表、`run-prompt-elicit` に standalone モード (skill 非紐付け汎用プロンプト経路) を公認。

### Changed
- **`prompt-rubric.json` v2.0.0**: C3-004 (旧「5.2 推論手順が 3-7 ステップで具体的」) / C4-001 (旧「5-8 項目」) を宣言型基準 (成果状態+検証可能チェックリスト+機械アンカー) へ再定義。数量レンジ廃止、l5-contract 従属を機械可読宣言。`c1-c4-criteria.md` の曖昧語検査をチェックリスト項目内に限定しゴールシーク正準文言を allowlist 化 (命令型引き戻しループの根を解体)。
- auto_approve_conditions を `{condition, evidence}` 形へ (判定主体 1:1 紐付け)。恒真の静的条件 (solo_operator_mode / stable_frozen) は preconditions へ分離。
- 全 6 prompts (R1-main / R1-elicit / R2-gate-review / R3-governance-decide / R1-interview / R1-evaluate)・SKILL.md 4本・agents 3体の Steps/推論手順を宣言型 (ゴール+完了チェックリスト+実行方式) へ転換 (dogfooding: 機械 baseline 6/6 FAIL → 6/6 PASS)。
- ヒアリング経路を `run-prompt-elicit` へ委譲一本化 (7layer Phase 1 の interview-user 直呼び廃止)。brief 供給時は Phase 1-3 の全ユーザー対話 skip を invariant 化。
- `seven-layer-format.md` のゴールシークループを goal-seek-paradigm.md 正本 (6ステップ+Anchor Step) へ追従、反復上限に convergence-policy loop_bounds の出所を付記。scripts 埋込の旧5ステップも追従。
- `plugin-composition.yaml` invariant を実依存 (skill-governance-lint 直呼び含む) と一致化。ROADMAP の dogfooding を長期→本 run 実施済みへ更新。

### Fixed
- `prompt-brief.schema.json` を if/then/else で条件分岐化し standalone モードと両立 (skill 紐付け時= target_skill+responsibility_id 必須 / standalone 時= output_path 必須・R-id 禁止。旧: 無条件 required で standalone brief が検証不能)。
- workflow-manifest / resource-map / SKILL.md の dangling 参照 (`prompts/elicit.md` 等 → 実在 R-prefix ファイル名) を全数修正。
- `R1-interview.md` の裸 TODO 残存 (validate-prompt FAIL) と、open_questions 処遇の矛盾 (TODO(human) 保持 vs auto-resolve) を「AI 最尤補完+仮定記録、TODO(human) 生成禁止」へ統一。
- `parse_known_args` による未知引数黙殺を 5 scripts で failfast 化。

## [2.1.14] - 2026-10-30

- `run-skill-feedback`: 必須項目を「要望タイトル・要望種別・やってほしいこと」の 3 つに絞った。背景・優先度・重要度・関連 URL は任意で、利用者が示した値だけを保持する (優先度と重要度は未指定なら中)。対象スキル名は同定の確定値から自動で設定し、対象プラグインを確定できないときは「不明」で投入せず、ヒアリングへ戻る。

## [2.1.13] - 2026-10-12

- 版番号だけを上げた。中身は 2.1.12 と同じ。利用者の手元の local marketplace には、2.1.12 の版番号のまま中身の違うもの（PR #85 の途中の作業ツリー）が入っていた。同じ版番号で中身が2通りあると、どちらが入っているかを版で見分けられないので、区別のために上げた。

## [2.1.12] - 2026-10-10

2.1.11（節なし）からの変更をまとめる。固定手順の検出を英語の見出しにも広げ、検査が読めない入力で止まったときに lint の段を通さないようにした。ほかは他 plugin が所有する正本の追従である。

### Changed
- **`verify-completeness.py`（`run-prompt-creator-7layer`。harness-creator の `vendor/prompt-creator/` はこの写し）**: Layer 5 の要素（Goal definition / Completion checklist / Achievement goal）を大文字と小文字を区別せず（casefold）照合する。固定手順とみなす見出し（`BANNED_HEADING_TOKENS`）に英語の Procedure / Reasoning steps / Thinking process を足し、英語の見出しは大文字と小文字を区別しない（Steps も同じ）。連番の列挙に「Step N」を足した。旧形式の検出（思考プロセスとステップ N の共起）に英語の Thinking process と Step N の組を足し、言語をまたいだ組は数えない（`LEGACY_FIXED_PROCEDURE_PAIRS`）。メッセージに英語のラベルを併記した。
- **`run-prompt-create/workflow-manifest.json`**: lint の段（handoff は `after_prompt_lint`）の `fatal_exit_codes` を `[1]` から `[1, 2]` にした。検査が入力不正（終了コード 2）で止まったときに、段を通さない。
- **`scripts/extract-plugin-root.py` を正本の 0.2.0 へ追随（投影の追従）**: 他プロジェクト専用（`scope` が `project` / `local`）の install 先を、sibling と cache fallback の候補からも除く。そうした登録しか無い `<plugin>@<marketplace>` は cache の下を version を問わず除き、同じ marketplace に有効な登録があれば、除くのはその installPath だけにする。同じ X.Y.Z なら正式版を prerelease より先に選ぶ。
- **`skills/run-skill-feedback/scripts/validate-inline-goal-seek-anchor.py` を正本へ追随（投影の追従）**: iteration の連番と、progress の iteration との一致を検査する。非 UTF-8・深すぎる入れ子・OSError は終了コード 2 で止まる。
- **guard runtime 固定値**: `artifact-delivery.json` の `runner_sha256` を、いまの guard runtime に合わせた。

### Fixed
- **`verify-completeness.py`**: 読めない `--input`（存在しない・ディレクトリ・非 UTF-8）を終了コード 2 で止める。

## [Unreleased] - 2026-05-24

### Added
- `plugin-composition.yaml` を新設し、capabilities / dependencies DAG / governance / eval_sinks / observability を skill-creator 仕様 (kindPluginComposition) で宣言。
- 4 SKILL.md (`run-prompt-create` / `run-prompt-elicit` / `run-prompt-creator-7layer` / `assign-prompt-design-evaluator`) に commonCore (`version: 2.1.0`) と `contract { intent, interface, invariant }` を付与。
- `assign-prompt-design-evaluator` に `rubric_refs` (L0 共通 `ref-skill-design-rubric` + L2 固有 `prompt-rubric.json`) を追加し `lint-skill-completeness` の rubric カテゴリを充足。
- `.github/workflows/governance-check.yml` に prompt-creator スコープの lint 5 ステップ (frontmatter / skill-name / skill-description / skill-completeness / dependency-direction[全プラグイン]) を配線。

### Changed
- `plugins/prompt-creator/scripts/*.js` 8 本を `plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/*.py` へ移植 (byte 等価, PEP 723 frontmatter 付与)。
- `agents/prompt-creator-{interview-user,generate-prompt,review-prompt}.md` の `context:` 指定を `isolation:` (skill-creator 仕様の正典キー) に統一。
- `run-prompt-create/scripts/evaluate-create-gates.py` に PEP 723 frontmatter (`# /// script ... # ///`) を追加し `lint-script-frontmatter` を充足。

### Removed
- 旧 `plugins/prompt-creator/scripts/` ディレクトリ (JS 8 本) を削除。

### Pending
- 移行 6 スクリプト (`merge-layers` / `verify-completeness` / `scaffold-prompt` / `generate-sheet` / `convert-format` / `log-usage`) は `lint-script-naming` の許可動詞外。`PENDING_RENAME_PATHS` に登録済み。後続 Change Governance PR で SKILL.md / agent / manifest 参照と同時にリネーム予定。
