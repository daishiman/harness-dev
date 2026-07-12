# elegant-review: plugin-dev-planner (completeness / SRP / dogfooding)

- run-id: `20260630-completeness-srp`
- scope: plugin (`plugins/plugin-dev-planner/`)
- 観点 (ユーザー指定): skill-creator 規律が全サーフェス (skill/agent/hook/command/script/test) に網羅的に反映されているか / 評価 skill と計画 skill の責務分離は最適か / プラグイン構築の仕組み (dogfooding) は整っているか
- 30 思考法: 全使用 (A2 論理構造10 / A3 メタ発想9 / A4 システム戦略11)、独立 SubAgent 3 体で並列分析
- 最終 verdict: **矛盾なし PASS / 漏れなし PASS / 整合性あり PASS / 依存関係整合 PASS** → **APPROVE** (proposer≠approver, 1 REJECT→修正→APPROVE)

## 収束した根本原因 (3 analyst が独立に同一構造へ収束)

本 plugin は「**生成する plan**」へ skill-creator 規律を frontmatter で焼く層 (layer a) は堅牢で、責務分離 (producer=run-plugin-dev-plan / approver=assign-plugin-plan-evaluator の fork 分離 = proposer≠approver) も健全。だが:

- **Gap 1 — 自己適用 (dogfooding) が CI/governance に未配線**: 188 tests がローカルで通るのに `creator-kit-ci.yml` の `plugins/*/tests` 1 階層 glob が nested-test plugin を取りこぼし **CI で一度も走っていなかった** (A4-3 critical)。`governance-check.yml` 未列挙 (A4-10)、composition quality_gates に runner 不在 (A4-1)、content-review verdict 不在で PR 赤化 (A4-4)。
- **Gap 2 — plugin envelope / MCP の builder 不在**: 唯一 builder を持たない envelope (plugin.json+marketplace) が全 plan に同一 open_issue として波及 (A3-3/A3-8/A3-9 が double-loop/if/素人 の 3 レンズから収束)。

「skill-creator が情報を全て網羅していない」というユーザー直感の実体はこの 2 点。**SRP (評価/計画の責務分離) は既に最適** (これ以上の分割は過剰) と確認。

## 適用した改善

### Tier A (plugin 内・安全)
- **FIX-A1**: `plan-rubric.json` C2-004 の alias drift を canonical `omitted_reason` (互換 alias 併記) へ統一
- **FIX-A2**: `elicitor.md` の重複連番 `4.` を 1-7 へ採番
- **FIX-A3**: `EVALS.json` の宙吊り `threshold:80` に消費者注記 + 全 surface の `surfaces_enforced_by` 宣言
- **FIX-A4**: assign skill の C1-C4 (inner 機械ゲート) と elegant-review の C1-C4 (outer 30 思考法) の二層性を disambiguation 注記
- **FIX-A5**: `plan-rubric.json` に rubric-governance 意図的除外の監査注記
- **FIX-A6**: hook 責務境界 (sample-plan drift 検出器・製品ゲートではない) を docstring/SKILL.md で明文化
- **FIX-A7**: R3 が `<PLAN_DIR>/envelope-draft/plugin.json` (貼れる manifest ドラフト) を emit + envelope/MCP 生成器不在を `/run-skill-feedback` 経由の 1 回限り構造化 capability-gap として起票する方針へ昇格

### Tier B (共有 CI・dogfooding ループを閉じる)
- **FIX-B1**: `creator-kit-ci.yml` の per-plugin pytest を `plugins/*/skills/*/tests` も収集するよう拡張 → nested-test plugin が CI 実走
- **FIX-B1/B2**: `governance-check.yml` に siblings 同型の plugin-dev-planner conformance block (validate-frontmatter/name/description/completeness) 追加
- **回帰固定**: `tests/test_ci_integration.py` (CI 配線 + enforced_by + handoff gate green from skill-dir cwd を機械固定)

## proposer≠approver が捕捉した CI-red (round 1 REJECT)

FIX-B1 で nested tests を CI へ配線したことで、**既存の cwd 依存バグが露呈**:
- `check-build-handoff.py` が handoff の相対 `plan_dir` を `Path.cwd()` で再構成 → CI が `cd skill_dir && pytest` で走るとパスが二重化し `test_build_handoff_gate` が fail。
- proposer の「188/191 passed」は **repo-root cwd** で取得され CI-cwd の失敗を遮蔽していた。
- **修正**: spec 解決を cwd 非依存化 (handoff は必ず `<PLAN_DIR>` 直下にあるため `handoff_path.parent` 基準)。回帰テスト 2 本追加。
- **教訓**: CI が `cd plugin_dir && pytest` で走らせるテストは、その正確な cwd から検証しないと意味がない (repo-root の pass は CI の pass を保証しない)。

## 残課題 (ユーザー選択で deferred)

- **Tier C (PR 前提条件)**: 両 skill へ `run-elegant-review` + `assign-skill-design-evaluator` を genuine 実行し `eval-log/plugin-dev-planner/<skill>/content-review/{elegance,rubric}-verdict.json` を生成 (`lint-content-review.py --all` が fail-closed・SHA 手書換は偽装ゆえ禁止)。
- **DEF-1..4 (理由付き deferred)**: matrix 上流被覆 lint / OUT2 round-trip schema-validate / minimal-omission golden / prompt-creator frontmatter backfill (本 plugin 外)。
- **commit 時**: `.claude/` の plugin 相対 symlink 6 件を同梱 (build-claude-symlinks.py --check 緑)。

## 検証 (独立 approver が自走で実測)
- skill dir cwd: 202 passed / repo root cwd: 202 passed / CI ループ全 4 plugin green (blast radius なし)
- 決定論 6 ゲート exit0 / conformance 4 lint exit0 / validate-plugin-completeness / lint-plugin-lint-coverage / build-claude-symlinks --check exit0
