---
name: run-ubm-goal-setting
description: 週報・月報・期報の目標設定をしたいとき、振り返り対話を北原さん式の統一ハイブリッド構造で作成したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[weekly|monthly|bimonthly]"
arguments: [type]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
kind: run
prefix: run
effect: external-mutation
owner: harness-maintainers
since: 2026-07-04
version: 0.1.0
manifest: workflow-manifest.json
goal_seek:
  engine: inline
  fork: subagent
  progress: eval-log/ubm-goal-setting/run-ubm-goal-setting/goal-seek-progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-goal-setting/run-ubm-goal-setting-intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-goal-setting/handoff-run-ubm-goal-setting.json
  max_loops: 5
responsibility_refs:
  - prompts/R1-step1-current-review.md
  - prompts/R2-step2-gap-analysis.md
  - prompts/R3-step3-goal-setting.md
  - prompts/R4-step4-action-plan.md
  - prompts/R5-step5-final-check.md
subagent_refs:
  - info-collector
  - goal-reviewer
  - phase3-coordinator
  - output-formatter
schema_refs:
  - references/data-contract.md
  - references/output-formats.md
knowledge_loop:
  pattern: router-registry
  index: ../../knowledge/router.json
  consult_at: [runtime]
script_refs:
  - scripts/validate-goal-output.py
reference_refs:
  - references/resource-map.yaml
  - references/thinking-guide.md
  - references/thinking-methods-toolkit.md
  - references/thinking-process.md
  - references/version-history.md
source: ObsidianMemo vault (.claude/skills/ubm-goal-setting) の移植
source-tier: internal
last-audited: 2026-07-04
audit-trigger: quarterly
feedback_contract:
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-goal-output.py が出力前に統一ハイブリッド構造21項目・NG表現・やらないこと3項目以上を検証し違反0件であることを確認する。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 週報/月報/期報を実際に生成し validate-goal-output が PASS し、目標設定・振り返り対話が北原さん式21項目を満たすことを受入テストが確認する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: run-skill-live-trial で対話を実走し、AskUserQuestion gate を越えて Phase3 対話→Phase5 検証→Phase6 Daily.md embed 更新まで自走完遂し目標設定ファイルが実生成されることを実行証拠で確認する。
      verify_by: live-trial
---

# run-ubm-goal-setting

UBM（北原さん式ゴールセッティング）の目標設定（週報=1週間 / 月報=1ヶ月 / 期報=2ヶ月）を高速対話で作成し、「行動を促し→実行し→成果を出す」サイクルを支援する。思考法駆動＋「愛情ある厳しさ」で本質を突き、即行動可能な計画を設計する。

## Purpose & Output Contract

- **ゴール**: 週報/月報/期報の目標設定・振り返り対話が北原さん式21項目の統一ハイブリッド構造で出力され、`validate-goal-output.py` の全チェックに PASS した状態。
- **出力契約**: 統一ハイブリッド構造21項目を満たす Markdown 目標設定ファイル1件 + `validate-goal-output` の検証結果（PASS/FAIL）。該当案件名は `tenant` 表記で統一する。
- **境界**: 入力=過去目標 / 合宿情報 / ナレッジ JSON / 対話回答。出力=目標設定ファイル1件 + `02_Configs/Templates/Daily.md` の embed 参照更新（種別該当分）。ナレッジそのものの更新は `run-ubm-knowledge-sync` へ委譲する。
- **統一ハイブリッド構造の定義正本**: `references/output-formats.md` + `references/data-contract.md`（21項目の公式ブロック順）。`validate-goal-output.py` はこの正本に基づき21項目を検査する。

## End-to-End Flow

`assets/execution-prompts.md` でフロー全体を把握し、以下の Phase を順次実行する（依存のないタスクは並列）。

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase0-init | 対象種別（週報/月報/期報）と実行日を確定。引数指定時はスキップ。オプション4は既存目標見直しモード（goal-reviewer） | AskUserQuestion / 本 skill |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ（デュアルパス検索）・journal を並列収集し構造化サマリー生成 | `info-collector`（Task） |
| Phase2b-review | 振り返り対話時に既存目標設定を8項目で見直し・再評価 | `goal-reviewer`（Task） |
| Phase3-dialogue | steps1-5 を参照しながら step1-5 対話（現状振り返り〜最終確認）を進行 | `phase3-coordinator`（Task） |
| Phase4-format | 目標設定テンプレートへ整形し15項目品質チェック | `output-formatter`（Task） |
| Phase5-validate | `validate-goal-output.py` で21項目を検証、最大3回まで改善してファイル保存 | `output-formatter` + script |
| Phase6-daily-update | 保存後、`02_Configs/Templates/Daily.md` の Obsidian embed 参照を最新目標へ更新（種別該当箇所のみ） | 本 skill |

**所要時間目安**: 週報 5〜8分 / 月報 10〜15分 / 期報 15〜20分。

## ゴールシーク実行

固定手順を消化するのでなく、上記ゴールと `feedback_contract` を満たすまで反復する（engine=inline / fork=subagent / max_loops=5）。

### ゴールシーク配線

- `goal_seek.progress`: `eval-log/ubm-goal-setting/run-ubm-goal-setting/goal-seek-progress.json` に checklist 状態、iteration、`open_issues`、`status` を記録する。
- `goal_seek.intermediate`: 各周回末の Anchor Step で `run-ubm-goal-setting-intermediate.jsonl` に `original_goal` / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` を append-only で残す。
- `goal_seek.handoff`: 完了時に validated goal file path、Daily.md 更新有無、検証結果を `handoff-run-ubm-goal-setting.json` へ書く。
- ループ本体は SubAgent context で実行し、親へ返すのは最終成果物パス、handoff 要約、未解決 `open_issues` のみにする。
- `max_loops` 到達時は PASS 扱いせず、残チェック項目を `open_issues` に残して human review へ差し戻す。

### ゴールシーク検証

Anchor Step の検証は `required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}` を満たす全 JSONL 行を対象にする。初回に `hashlib.sha256(original_goal)` を `original_goal_hash` として progress へ固定し、以後の周回で `original_goal` が変化していないことを照合する。

- **inner ループ (IN1)**: Phase5 で `validate-goal-output.py --file <保存先> --type <weekly|monthly|bimonthly>` を実行。統一ハイブリッド構造21項目・NG表現・やらないこと3項目以上を出力前に検証し、違反0件になるまで output-formatter が最大3回改善する。
- **outer ループ (OUT1)**: 週報/月報/期報を実際に生成し validate-goal-output が PASS することを受入テストで確認する。未達 findings は再実行で反映し、最大5周で収束させる。
- **behavioral acceptance (OUT2)**: 静的 content-review とは分離し、`run-skill-live-trial` で AskUserQuestion gate → Phase3 対話 → Phase5 検証 → Phase6 Daily.md embed 更新と目標設定ファイル実生成までを実走証拠として確認する。

## Key Rules

- **数値は半角のみ**（「万円」不可 → `600000`）。差分は必ず `+`/`-` 付き（例 `-300000`, `+2`）。行動目標には期日と数値を含める。
- **関係構築が軸**: 売上目標を「追う」のでなく「人との関係を育む」を先に置く。売上は関係の結果。
- **精神論 NG**: 「頑張る」「意識する」「気をつける」は行動目標として不可 → 具体化（誰に・何を・いつまで・何件）を要求。
- **やらないこと3項目以上** + 判断基準1文で迷いを排除する。
- **合宿（アカデミー）整合**: 直近の合宿アドバイスと目標の方向性のズレを検出したら即軌道修正。
- **プロジェクト別タスク**: 週報=任意 / 月報=必須 / 期報=禁止。`- [ ] [期日] [提出先・宛先] 対象物・行動` のチェックリスト形式・2階層まで・先方担当者付き。
- **思考法駆動**: 質問の形で自然に思考法を適用し、名前は出さない。北原さんの原則引用は1対話あたり1〜2回まで。

## Gotchas

- **出力ファイル命名**: 週報 `UBM - 1-週報 - {期間}.md` / 月報 `UBM - 2-月報（１ヶ月） - {期間}.md` / 期報 `UBM - 3-月報（２ヶ月） - {期間}.md`（`{期間}` は `YYYY-MM-DD〜YYYY-MM-DD`）。
- **保存先**: `$UBM_VAULT_ROOT/05_Project/UBM/目標設定/` のみ（`UBM_VAULT_ROOT` 未設定時は self-relative 解決）。
- **Daily.md 更新（Phase6）**: `$UBM_VAULT_ROOT/02_Configs/Templates/Daily.md` の該当 embed 行のみ正規表現で検出・置換し、他部分は一切変更しない。サマリー見出し（`【1週間の目標】`/`【1ヶ月の目標】`/`【2ヶ月の目標】`）は継続語彙で凍結（今週/今月/今期へ改名しない）。
- **期報の正本**: `references/output-formats.md` の静的規則を A1 優先で正本化し、動的学習はスタイル参照に限定（見出し集合を上書きしない）。
- **書き込み保護**: `ubm-write-path-guard` hook が `UBM_VAULT_ROOT` 配下の禁止パスへの Write|Edit|MultiEdit を fail-closed で阻む。許可は目標設定/ 保存と Daily.md embed 更新のみ。vault 外の plugin 同梱 data は保護対象外。

## Additional Resources

- **agents**: `info-collector` / `goal-reviewer` / `phase3-coordinator` / `output-formatter`（plugin 直下 `agents/`。coordinator は `prompts/R1-R5` を Read でインライン参照）。
- **prompts**: `prompts/R{1..5}-<slug>.md` — Phase3 対話 Step1-5 の責務単位 7 層プロンプト正本（prompt-placement-convention 準拠、verify-completeness.py で 7 層+l5-contract 検証）。
- **scripts**: `scripts/validate-goal-output.py`（出力バリデーション・決定論ゲート）。
- **references**: `references/thinking-guide.md`（思考法）/ `references/output-formats.md`（テンプレート21項目正本）/ `references/data-contract.md`（Phase 間 I/O）/ `references/thinking-methods-toolkit.md` / `references/thinking-process.md` / `references/version-history.md`。
- **assets**: `assets/execution-prompts.md`（フロー参照）/ `assets/interview-quick-templates.md` / `assets/action-goals-best-practices.md` / `assets/golden-sample-weekly.md`（Few-shot）。
- **knowledge**: plugin 直下 `knowledge/`（`router.json` → `*.json` を info-collector がデュアルパス検索。L1 curated vendor 同梱でfresh-install 直後から機能）。
