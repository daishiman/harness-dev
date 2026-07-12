# harness-prompt-conformance — build evidence / implementation-guide

本 plan (SubAgent/prompts の7層準拠を機械層で強制) を実プラグイン (harness-creator + prompt-creator) へ
build した記録。全 9 component を実体化し、決定論ゲート・pytest・repo 横断 lint を緑化した。

## 実装区分の判断

plan の `constraints` は「成果物はタスク仕様書 (13 phase plan) のみ・実 build はスコープ外」と記す
(plugin-dev-planner の既定境界)。本サイクルの指示は「plugin-plans/harness-prompt-conformance/ を構築せよ
(抜け漏れなく全て)」であり、目的達成には**実コード変更が必要**と判断し、plan を実プラグインへ build した
(ラベル docs-only を上書き / capability-build 実装プロンプト CONST_006)。

## build した component (9)

| id | kind | build_target | 実体 |
|---|---|---|---|
| C01 | skill 更新 | `plugins/prompt-creator/skills/run-prompt-creator-7layer/` | `references/subagent-hybrid-format.md` 新設 + resource-map 登録 |
| C02 | script 新設 | `plugins/harness-creator/scripts/lint-agent-prompt-content.py` | `--mode agent|prompt` / `--check-vendor-parity` / `--self-test`。vendor `vendor/prompt-creator/verify-completeness.py` を byte 一致複製。tests 33件 |
| C03 | sub-agent 是正 | `plugins/harness-creator/agents/elegant-improvement-executor.md` | 7層ハイブリッド化 |
| C04 | sub-agent 是正 | `plugins/harness-creator/agents/elegant-logical-structural-analyst.md` | 7層ハイブリッド化 |
| C05 | sub-agent 是正 | `plugins/harness-creator/agents/elegant-meta-divergent-analyst.md` | 7層ハイブリッド化 |
| C06 | sub-agent 是正 | `plugins/harness-creator/agents/elegant-reset-observer.md` | 7層ハイブリッド化 |
| C07 | sub-agent 是正 | `plugins/harness-creator/agents/elegant-system-strategic-analyst.md` | 7層ハイブリッド化 |
| C08 | sub-agent 是正 | `plugins/harness-creator/agents/run-build-skill-subagent.md` | 7層ハイブリッド化 |
| C09 | skill 更新 | `plugins/harness-creator/skills/run-build-skill/` | schema `prompt_provenance` + validator `_validate_prompt_provenance` + SKILL.md/trace-schema doc + CI 配線 |

plugin-level surfaces: vendor (`vendor/prompt-creator/verify-completeness.py`)・references_config_assets
(`subagent-hybrid-format.md`)・harness_eval (CI: `harness-creator-kit-ci.yml`)。

## 付随変更 (side-effect / 機械層強化)

- `scripts/lint-vendored-ssot.py` — VENDORED_PAIRS に C02 vendor ペアを追加 (byte 一致を repo 横断で強制、3 件に)。
- `.github/workflows/harness-creator-kit-ci.yml` — C02 の 3 step (parity / --mode agent / --mode prompt) を配線。
- `plugins/harness-creator/scripts/validate-plan-coverage.py` — surface 照合を cross-plugin (`targets[]` repo-relative) 対応に強化。本 plan の C7 (C01→prompt-creator, C02-C09→harness-creator の cross-plugin routing) を正式サポート。

## 受入確認 (goal-spec C1-C8 トレーサビリティ / P07)

- **C1** (prompt-creator にハイブリッド契約 SSOT): `subagent-hybrid-format.md` 新設。frontmatter=plugin YAML/本文=7層を明記し `seven-layer-format.md` との差分を表で明文化。→ C02 `--check-vendor-parity`/`--mode agent` で参照。
- **C2** (内容 lint が生成フローに配線): C02 `lint-agent-prompt-content.py` が本文7層を fail-closed 検証。C09 が SKILL.md Step0.4/Step3.5 で生成フローに配線し CI でも repo 全走査。配置 lint (`lint-prompt-placement.py`) と直交。
- **C3** (既存6 SubAgent 是正): 6 agent を frontmatter=plugin YAML 維持・本文7層 l5-contract v2.0.0 化。固定手順の numbered self-correction を Layer5.4 ゴールシークループへ置換。→ C02 `--mode agent` scanned=6 exit0。
- **C4** (既存 skill prompts 準拠の機械検証): C02 `--mode prompt` scanned=33 exit0。
  - 母数注記: plan 時計測の「36本」は symlink 込み glob、C02 の scanned=33 は symlink 除外走査。
    差分3本 = contract-generator symlink bundling 分 (run-contract-finalize / run-contract-generate /
    run-template-sync 各1本)。実数矛盾ではなく計測条件差 (measured_at 2026-07-05)。
- **C5** (prompt-creator 経由必須 + バイパス不能): C09 の `prompt_provenance` (schema + `_validate_prompt_provenance`)。`resolved_policy=required` 時必須化し、`prompt_creator_invocation=false`/契約参照欠落/`content_lint≠PASS`/ブロック欠落を exit1。受入例 `test_e2e_bypass_trace_exits_1` + 単体7件。
- **C6** (plan 決定論ゲート全 exit0): plan 同梱 G1-G10 = 10/10 PASS。
- **C7** (build_target の所有 plugin 別 routing): C01=prompt-creator、C02-C09=harness-creator。`validate-plan-coverage --all` が cross-plugin 対応で実体化済みとして網羅。
- **C8** (除外 plan_dir を build_target に含めない): `plugin-plans/{plugin-dev-planner,skill-intake,harness-creator}/` は build_target/side_effect に不在 (grep 0 件)。

## ゲート結果 (P11 evidence)

| ゲート | 結果 |
|---|---|
| C02 `--mode agent` (agents 6本) | exit0 |
| C02 `--mode prompt` (prompts 33本) | exit0 |
| C02 `--check-vendor-parity` | exit0 (byte 一致) |
| C02 pytest (`test_lint_agent_prompt_content.py`) | 33 passed |
| C09 validate-build-trace (バイパス不能性) | `test_validate_build_trace.py` 34 passed (E2E bypass exit1 + optional downgrade exit1 含む) |
| lint-agent-prompt-section (6 agents) | 全 OK |
| validate-frontmatter (6 agents) | 全 OK |
| lint-ssot-duplication --strict (harness-creator) | OK (相互 DUP-PASSAGE なし) |
| lint-vendored-ssot (3 pairs) | OK (byte 一致) |
| lint-script-frontmatter (harness-creator/scripts) | OK (checked=7) |
| lint-script-naming (全体) | VIOLATION=0 (`lint` は ALLOWED_VERB) |
| lint-runtime-portability | OK |
| lint-prompt-placement | OK (prompts 空殻反転なし) |
| lint-matrix-sync | OK |
| plan 決定論ゲート G1-G10 | 10/10 PASS |
| validate-plan-coverage --all | OK (実体化済み網羅) |
| 影響範囲 pytest (touched test files) | 367 passed |
| repo 全体 pytest (`tests/`) | 6305 passed / 4 skipped / 0 failed |

### 事後計測 (elegant-review run-20260705-113702 / Phase 3 write-back 後の実測)

build 時のゲート表に不在だった LLM 層関連ゲートの追補と、plan 状態 write-back
(build_status=realized / routes=built / phase status=完了 / goal-spec done=true) 後の再計測。

| ゲート | 実測結果 (2026-07-05) |
|---|---|
| lint-content-review --all (governance-check 相当) | exit0 — 47 skill(s) verified。run-build-skill の elegance/rubric 両 verdict は本 review run で genuine 再生成済み (reviewed_at 2026-07-05T11:37:02+09:00、別ワーカー担当) |
| C02 --check-vendor-parity | exit0 (byte 一致) |
| C02 --mode agent | exit0 scanned=6 |
| C02 --mode prompt | exit0 scanned=33 |
| C02 scanned=0 floor guard (fail-open 封鎖・本 review で新設) | pytest 4件追加 → `test_lint_agent_prompt_content.py` 33 passed |
| validate-plan-coverage --all (build_status=realized で gate 発火) | exit0 — 実体化済み 2 plan 網羅 |
| check-build-handoff (GAP-SCRIPT-BUILDER 手順(3) の事後消化) | exit0 — 9 routes + envelope 契約充足 (routes status=built 化後) |
| check-route-component-parity | exit0 — 9 routes 1:1 parity |
| plan 決定論ゲート再実行 (verify-index-topsort / check-spec-frontmatter / check-requirements-coverage / check-plugin-goal-spec / detect-unassigned / check-spec-gates / check-surface-inventory / check-runtime-portability) | 全 exit0 (write-back 後の状態で再緑化) |
| plugins/harness-creator pytest 全体 | 74 passed |
| tests/test_validate_build_trace.py (C09-1 optional downgrade 封鎖後) | 34 passed |
| tests/scripts-plugins/test_harness_creator__validate_build_trace_r3.py | 113 passed |
| tests/scripts-plugins/test_harness_creator__validate_paradigm_coverage*.py | 71 passed (condition_matrix C1-C4 証跡 gate 追加後) |

goal-spec.json checklist done=true 化の証跡対応は本ファイル「受入確認」節の C1-C8 各行が正本
(goal-spec の checklist item は schema `additionalProperties:false` のため証跡フィールドを持てない)。

### 独立 evaluator findings (evaluator-verdict-run-build-skill.json, score 84/PASS) の処置

`eval-log/harness-creator/_plugin/elegant-review/run-20260705-113702/evaluator-verdict-run-build-skill.json`
の 3 findings を本 review Phase 3 で処置 (2026-07-05):

- **C09-1 (medium)** run/assign×optional downgrade による prompt_provenance 回避穴 — 本改善で即時是正。
  `validate-build-trace.py` が `run` / `assign` の `resolved_policy=optional|skip` を exit1 とし、
  `test_pgm_run_assign_optional_downgrade_fails` / `test_pgm_optional_contradicts_run_assign` で回帰固定。
- **C09-2 (low)** content_lint.status enum の到達不能値 — schema description へ「存在時は PASS のみ受理」
  注記済みを実測確認 (並行 content-review ワーカーが是正済み。重複編集なし)。
- **C09-3 (low)** reproducibility-trace-schema.md ルール5 regex drift — validator `LAYER_YAML_PATH_PATTERNS`
  正本と byte 一致済みを実測確認 (同上。ルール5 に SSOT ポインタ行あり)。

## 設計上の判断根拠 (learning notes)

1. **vendoring を subprocess 実行で再利用**: C02 は canonical `verify-completeness.py` を byte 一致 vendoring し
   subprocess で丸ごと実行。ロジック二重実装 (drift 源) を避け、`--check-vendor-parity` + `lint-vendored-ssot`
   の二層で byte 一致を強制。frontmatter を無視し `# Layer N:` で分割する verify-completeness の性質により、
   agent (frontmatter 付) と prompt (純7層) の双方をそのまま渡せる。
2. **symlink 除外**: `plugins/harness-creator/skills/` に他プラグイン (contract-generator) を bundling する
   symlink が存在。C02 は所有プラグインの自前コンテンツのみ対象とし symlink skill を除外 (glob 透過を `iterdir`+
   `is_symlink` で遮断)。
3. **固定手順の除去**: agent 是正は再見出しに留まらず、l5-contract v2.0.0 が禁じる「numbered 自己修正手順」を
   Layer5.4 のゴールシークループ (完了チェックリスト駆動) へ置換する実質準拠改善。
4. **cross-plugin plan の validator 正式サポート**: C7 の意図的 cross-plugin routing を `validate-plan-coverage`
   が誤検出していた ("1 inventory=1 plugin" ハードフェイル)。surface を `targets[]` (repo-relative) で直接照合
   する形に強化し、plan をコミットしても CI 緑を保てるようにした。

## side_effect_targets 宣言と実変更の差分注記

C09 checklist の CI 配線要件は「harness-creator-kit-ci.yml / governance-check.yml の**いずれか**」であり、
実 build は kit-ci 側配線 (C02 3 step) で充足する。`governance-check.yml` は未変更のため
`component-inventory.json` / handoff の side_effect_targets から削除済み。

## スコープ外 / 先送り — 優先度付き backlog (elegant-review run-20260705-113702 起票)

当初「なし」と宣言していたが、本 elegant-review (30思考法・KJ法集約) が証跡系の残作業を特定した。
push 前必須だった stale verdict 再生成は同 review 内で消化済み (事後計測表参照)。以下は恒久機構の backlog
(いずれも実装未着手。番号=優先度順)。run-build-skill SKILL.md / run-prompt-creator-7layer SKILL.md への
成文化を伴う項目は sha 固定中 (並行 content-review 再評価) につき本 review では起票のみ:

1. **build 終端 write-back プロトコル成文化** — run-build-skill SKILL.md へ終端3ステップ
   ((1) 対象 SKILL.md sha 変化時の content-review verdict 再生成 (2) build trace + evaluator verdict の
   eval-log 記録 (3) plan 状態 write-back: inventory build_status / handoff routes[].status / index /
   goal-spec done / phase frontmatter) を必須化。KJ法が特定した5 issue (stale verdict・trace 不在・
   再評価トリガ未配線・plan 状態 drift・証跡欠落再発) の共通根。
2. **validate-plan-coverage への quality_gates 充足照合 (gate reachability 検査) 追加** — 宣言ゲートに
   対応する verifier + verdict 置場が実在するかを検査し、宣言のみの到達不能ゲートを fail させる。
3. **stale-sha 検出→content-review 再実行の機構連結** — lint-content-review の検出 (dampener) に対する
   回復経路 (再評価トリガ自動起票) の配線。
4. **agent kind 向け content_review verdict 置場 + lint 拡張** — C03-C08 の
   content_review ゲート宣言は現状検証手段が無い (lint-content-review.py は skills/*/SKILL.md 専用)。
   同根として trace 側も PROMPT_REQUIRED_KINDS={run,assign} に agent 系が不在 (brief schema の kind enum に
   "agent" 自体が無く、単純追加は dead code = 到達不能ゲートの新設になるため見送り。agent build の trace 語彙
   (brief/schema/policy_resolution) 設計とセットで解決する)。
   [解消済 2026-07-05] run/assign×resolved_policy=optional の downgrade 穴は本改善で validator / schema docs /
   tests を更新し、`run` / `assign` では `optional|skip` を禁止済み。残る本項の対象は agent kind 向け
   content_review/evaluator verdict の置場・lint 到達性に限定する。
5. **契約 doc subagent-hybrid-format.md の vendoring** — verifier (verify-completeness.py) のみ vendor 済で
   契約 doc は cross-plugin 相対参照のままの非対称。単独 install 時 dangling の解消。
6. **contract-generator 3 prompts への C02 横展開** — symlink 除外の代償「所有元が lint する」前提が
   contract-generator 側で未実装 (lint カバレッジ空白地帯の透明化)。
7. **agents/*.md 編集時 PreToolUse hook (シフトレフト)** — 手動直接編集経路の検出位置が CI のみで遅延。
   hook-guard-skillgen と同型の単発ファイル lint hook アダプタ。
8. **skill-build-trace 本 build 分の未記録** — 本 build はメタプロンプト経由 (capability-build ラベル
   上書き) で run-build-skill フロー外のため、skill-build-trace.json (prompt_provenance 付き) が存在
   しない。事後捏造はせず「次回 build から C09 機構 (validate-build-trace + prompt_provenance) が強制」
   と透明化する。代替実証: C02 --mode agent/prompt が現時点 exit0 (事後計測表)、バイパス不能性機構
   自体は `test_e2e_bypass_trace_exits_1` 含む 33 テストで演習済み。

commit / PR / push はユーザー指示待ち。
