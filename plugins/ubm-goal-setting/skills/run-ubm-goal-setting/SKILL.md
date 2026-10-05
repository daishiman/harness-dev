---
name: run-ubm-goal-setting
description: 週報・月報・期報の目標設定をしたいとき、振り返り対話を北原さん式の統一ハイブリッド構造で作成したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[weekly|monthly|quarterly]"
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
runtime_root_policy: host-skill-path
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: harness-maintainers
since: 2026-07-04
version: 0.2.0
manifest: workflow-manifest.json
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
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
  - ../../scripts/validate-inline-goal-seek-anchor.py
  - scripts/validate-goal-linkage.py
  - scripts/validate-cross-level.py
reference_refs:
  - references/resource-map.yaml
  - references/selection-focus-goal-frame.md
  - references/thinking-guide.md
  - references/thinking-methods-toolkit.md
  - references/thinking-process.md
  - references/version-history.md
source: ObsidianMemo vault (.claude/skills/ubm-goal-setting) の移植
source-tier: internal
last-audited: 2026-07-04
audit-trigger: quarterly
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-goal-output.py が出力前に統一ハイブリッド構造の公式21ブロック・NG表現・やらないこと3項目以上に加え、--type と本文タイトル見出しラベルの一致(不一致は rc=1 で FAIL となる停止条件)を検証し違反0件であることを確認する。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: validate-goal-linkage.py が出力前に一本筋(行動目標のグループ見出し `### → 成果目標名：…` の成果目標名が成果目標セクションの項目名と一致し、各成果目標を支える行動が最低1件ある)を両方向で照合し rc=0 であることを確認する。rc=3(照合対象0件)は PASS として扱わない。
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: 期報と月報が揃っている場合、validate-cross-level.py が期アンカー8種を層をまたいで照合し rc=0 であることを確認する(週報があれば --weekly も渡して三層で照合する)。rc=3(抽出0件)は PASS として扱わない。抽出不可は不一致と別枠で列挙され rc=1 になる。期報か月報のどちらかが無い場合だけこの基準を適用しない。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 週報/月報/期報を実際に生成し validate-goal-output が PASS し、目標設定・振り返り対話が北原さん式の公式21ブロックを満たすことを受入テストが確認する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: run-skill-live-trial で対話を実走し、AskUserQuestion gate を越えて Phase3 対話→Phase5 検証→Phase6 Daily.md embed 更新まで自走完遂し目標設定ファイルが実生成されることを実行証拠で確認する。
      verify_by: live-trial
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。
- `Task` を起動するときは解決済みabsolute `plugin_root` を入力に含め、Task 内で `PLUGIN_ROOT` と旧agent本文互換用 `CLAUDE_PLUGIN_ROOT` の両方へ同じ値を設定する。未指定・非absolute・不一致なら外部Read/Write前にfail-closedで停止する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物またはremote mutation previewをmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方またはpreview receiptを提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはmutationを実行せずhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionおよびexternal mutation safety wrapperはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。actual mutationはcanonical preview→hook-confirm→authorize→execute wrapperだけを通し、release/exhaustiveは別の明示eventを必要とする。

<!-- external-mutation-guard-cli:v1 -->
### Canonical external mutation receipt flow (mandatory)

Never execute the external mutation argv directly. Replace every angle-bracket placeholder
with the reviewed value from this run; the central CLI fails closed on missing/invalid values.

Resolve the guard plugin root once, before `preview`. An installed plugin cannot reach a sibling
plugin as `<plugin root>/..`, so never guess that path:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-plugin-root.py" skill-governance-adapters
```

Use the printed absolute path as `<GUARD_PLUGIN_ROOT>` in `preview`, `authorize` and `execute`
(other Bash is blocked while the confirmation is pending, so do not resolve it again).
If the resolver exits non-zero, stop without any external mutation and tell the user to install
the `skill-governance-adapters` plugin.

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

Present that official preview output to the user. Only the exact user reply printed by `preview`
may trigger the registered `hook-confirm` producer. Then use the two returned receipt paths:

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

Do not use an auto-approval flag or invoke the mutation command outside this receipt flow.
<!-- /external-mutation-guard-cli:v1 -->


# run-ubm-goal-setting

UBM（北原さん式ゴールセッティング）の目標設定（週報=1週間 / 月報=1ヶ月 / 期報=3ヶ月）を高速対話で作成し、「行動を促し→実行し→成果を出す」サイクルを支援する。思考法駆動＋「愛情ある厳しさ」で本質を突き、即行動可能な計画を設計する。

## Purpose & Output Contract

- **ゴール**: 週報/月報/期報の目標設定・振り返り対話が北原さん式の統一ハイブリッド構造（公式21ブロック）で出力され、`validate-goal-output.py`（形式）と `validate-goal-linkage.py`（一本筋の両方向照合）の両方に PASS し、期報と月報が揃っている場合は `validate-cross-level.py`（層をまたぐ値の照合・IN3）にも PASS した状態。
- **出力契約**: 統一ハイブリッド構造の公式21ブロックを満たす Markdown 目標設定ファイル**1本**（月報だけはその1ファイルの中が提出用セクション＋管理用セクションの2セクションに分かれる） + `validate-goal-output` と `validate-goal-linkage` の検証結果（それぞれの rc の値と引数）。期報と月報が揃っている場合は `validate-cross-level.py` の rc と引数も記録し、揃っていない場合は rc ではなく不適用（`not_applicable`）と記録する。該当案件名は `tenant` 表記で統一する。
- **境界**: 入力=過去目標 / 合宿情報 / ナレッジ JSON / 対話回答。出力=目標設定ファイル1本 + `02_Configs/Templates/Daily.md` の embed 参照更新（種別該当分）。`（提出）` 付きの既存ファイルがある場合だけ、削除せず `05_Project/UBM/目標設定/archive/` へ移す（vault 上のファイル移動なので、external mutation preview の `--target-scope` と `--side-effect-summary` に移動元と移動先を含める）。ナレッジそのものの更新は `run-ubm-knowledge-sync` へ委譲する。
- **統一ハイブリッド構造・粒度・採否・参照整合の定義正本**: `references/output-formats.md` + `references/data-contract.md`（公式21ブロックの順序）。**「公式21ブロック」は出力テンプレートの固定の見出し集合（21 は不変）。`output-formatter` の品質チェックリストの件数とは別物で、そちらは件数で呼ばない。**提出用セクションと管理用セクションの違い・売上目標/成果目標/行動目標の三層分離・行動目標の採否基準・一本筋の照合・継続売上と単発の分離も `output-formats.md` 内に置く（別ファイルへ散らさない）。`validate-goal-output.py` はこの正本に基づき公式21ブロックを検査する。

## End-to-End Flow

`assets/execution-prompts.md` でフロー全体を把握し、以下の Phase を順次実行する（依存のないタスクは並列）。`assets/execution-prompts.md` と `references/data-contract.md` は整形・検証・保存をまとめて「Phase 4」と呼ぶ。本表の Phase4-format〜Phase5-validate（Phase4b-submission を含む）がそれに当たる。

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase0-init | 対象種別（週報/月報/期報）と実行日を確定。引数指定時はスキップ。オプション4は既存目標見直しモード（goal-reviewer） | AskUserQuestion / 本 skill |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ（デュアルパス検索）・journal を並列収集し構造化サマリー生成 | `info-collector`（Task） |
| Phase2b-review | 振り返り対話時に既存目標設定を13項目（基本2＋合宿整合性3＋関係構築3＋三層分離5）で見直し・再評価 | `goal-reviewer`（Task） |
| Phase3-dialogue | 親が steps1-5 を参照し、現状振り返り〜最終確認の対話を進行。必要な場合だけ coordinator から読取専用の次問案を受ける | 本 skill（親対話）+ `phase3-coordinator`（任意の助言Task） |
| Phase4-format | 目標設定テンプレートへ整形し、`agents/output-formatter.md` Layer 4 の品質チェックリスト（件数は正本側で増減するためここに書かない）を全項目確認する。行動目標は採否基準で1行ずつ判定する | `output-formatter`（Task） |
| Phase4b-submission | **月報のときだけ**、同じファイルの先頭に提出用セクション（公式21ブロックを全件・見出しに「（提出）」を付ける・人数集約・本文に具体日を埋めない・行動目標はグループ見出しを置かず1行1行動・期日は管理用で逆算した値と同値）を置き、その後に管理用セクションを続ける | `output-formatter`（Task） |
| Phase5-validate | `validate-goal-output.py`（公式21ブロック・逆算チェーン C1〜C6）→ `validate-goal-linkage.py`（一本筋の両方向照合）→ 期報と月報が揃っていれば `validate-cross-level.py`（層をまたぐ値の照合・IN3。週報があれば `--weekly`）の順で検証、最大3回まで改善してファイル保存。月報も1ファイルなので各スクリプトは1回ずつ。各 rc の値そのものと引数を記録する（IN3 を適用しないときは `not_applicable`）。保存時に `（提出）` 付きの既存ファイルがある場合だけ、削除せず `archive/` へ移す | `output-formatter` + scripts |
| Phase6-daily-update | 保存後、`02_Configs/Templates/Daily.md` の Obsidian embed 参照を最新目標へ更新（種別該当箇所のみ） | 本 skill |

**所要時間目安**: 週報 5〜8分 / 月報 10〜15分 / 期報 15〜20分。

## ゴールシーク実行

固定手順を消化するのでなく、上記ゴールと `feedback_contract` を満たすまで親の対話contextで反復する（engine=inline / fork=inline / max_loops=5）。

### ゴールシーク配線

- `goal_seek.progress`: `eval-log/ubm-goal-setting/run-ubm-goal-setting/goal-seek-progress.json` に checklist 状態、iteration、`open_issues`、`status` を記録する。
- `goal_seek.intermediate`: 各周回末の Anchor Step で `run-ubm-goal-setting-intermediate.jsonl` に `original_goal` / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` を append-only で残す。
- `goal_seek.handoff`: 完了時に validated goal file path、Daily.md 更新有無、検証結果を `handoff-run-ubm-goal-setting.json` へ書く。
- ループ本体とユーザー対話は親contextが所有する。`Task` は表の専門責務へ限定し、各結果を親へ戻して同じ goal/checklist に統合する。
- `max_loops` 到達時は PASS 扱いせず、残チェック項目を `open_issues` に残して human review へ差し戻す。

### ゴールシーク検証

Anchor Step の検証は `required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}` を満たす全 JSONL 行を対象にする。初回に `hashlib.sha256(original_goal)` を `original_goal_hash` として progress へ固定し、以後の周回で `original_goal` が変化していないことを照合する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "${CLAUDE_PROJECT_DIR:?caller project root is required}/eval-log/ubm-goal-setting/run-ubm-goal-setting/goal-seek-progress.json" \
  "${CLAUDE_PROJECT_DIR}/eval-log/ubm-goal-setting/run-ubm-goal-setting/run-ubm-goal-setting-intermediate.jsonl"
```

progress/intermediate の不在、必須キー欠落、空または途中変更された `original_goal`、SHA-256 不一致は exit 非0で完了を阻止する。
- **inner ループ (IN1)**: Phase5 で `validate-goal-output.py --file <保存先> --type <weekly|monthly|quarterly>` を実行（`bimonthly` は後方互換の別名として受理される）。統一ハイブリッド構造の公式21ブロック・NG表現・やらないこと3項目以上・逆算チェーン（C1〜C6）・シンプルさ上限（S1〜S3）に加え、**`--type` と本文タイトル見出しラベルの一致**（不一致は rc=1 で FAIL。種別の取り違えを止める停止条件）を出力前に検証し、違反0件になるまで output-formatter が最大3回改善する。上位層のファイルを `--peer PATH` で渡すと期アンカーの層間整合を WARN で併せて報告する（任意・rc には影響しない）。
- **inner ループ (IN2)**: 続けて `validate-goal-linkage.py --file <保存先>` を実行する。IN1 の C4（所属不明）・C5（参照先の実在）は FAIL だが、**C6（支える行動の無い成果目標）は WARN で rc を上げず、括弧で始まる見出し名はすべて免除する**。IN2 は同じ照合規則（成果目標名の切り出し・空白を落とした完全一致・グループ見出しの解釈）を validator から読み込んで使い、支える行動の無い成果目標・`・` で複数の成果目標を指す見出し・`（土台）`／`（関係維持）` 以外の括弧名・月報のグループ見出しのラベルずれを rc=1 で止める。rc=0（未解決0件・分母あり）になるまで改善する。**rc=3 は「照合対象が1件も無い」= 判定していないので PASS として扱わない**。両スクリプトの rc は**値そのものと引数**を記録する（パイプを挟むと検査器の rc が読めなくなるので、出力をファイルへ落として `$?` を直後に取る）。
- **inner ループ (IN3)**: 期報と月報が揃っている場合（週報があれば `--weekly` も渡す）、`validate-cross-level.py --quarterly <期報> --monthly <月報> [--weekly <週報>]` を実行する。**IN1 / IN2 はどちらも1本のファイルしか見ないため、期報の数字を直して月報・週報へ追随させ忘れても rc=0 で通る**（層をまたぐ値を突き合わせる口が存在しない＝分母0件）。この穴を IN3 が埋める。期アンカー8種（今期の売上目標／当月の売上目標／無料相談の延べ回数／1回目の実人数／月額継続コンサルの累積件数／現在事業パートナー数／現在のグリッドパートナー数／次回の壁打ち予定日）を期報と月報（週報があれば三層）で並記して照合し、**抽出不可は不一致と別枠で列挙して rc=1** にする。**rc=3 は抽出0件＝何も判定していないので PASS として扱わない**。週報がまだ無ければ `--weekly` を省略する。対象一覧の正本は `references/data-contract.md` §3.1.3。
- **outer ループ (OUT1)**: 週報/月報/期報を実際に生成し validate-goal-output が PASS することを受入テストで確認する。未達 findings は再実行で反映し、最大5周で収束させる。
- **behavioral acceptance (OUT2)**: 静的 content-review とは分離し、`run-skill-live-trial` で AskUserQuestion gate → Phase3 対話 → Phase5 検証 → Phase6 Daily.md embed 更新と目標設定ファイル実生成までを実走証拠として確認する。

## Key Rules

- **売上 → 成果 → 行動の順に降ろす（週報・月報・期報 共通・最重要）**: 売上目標をまず1つ決め、そこから成果目標を逆算し、成果目標から行動目標を逆算する。行動から書き始めて成果を後付けする順序は禁止。
- **実行した時点で達成になる目標を置かない**: 「勉強会を月4回開催する」「アカデミーに参加する」等は成果ではなく行動。目標欄に置かず、当たり前の土台として扱う。成果目標は「実行した結果、相手側で何が起きたか」で書く。
- **成果と売上を数値で結ぶ**: 各成果目標は **1項目=2行**（1行目 `- 項目：先方判断・結果の状態　期日M/D` ／ 2行目 `  → 売上貢献：<単価> × <件数> = <貢献額>`）。裸の数字は不可で、式にできないものは `→ 売上貢献：<金額>（値引き後の一括見積 等の根拠）` と括弧で根拠を添える（`150000` だけでは後から誰も検算できないため）。計上するのは **その期間に実際に売上として立つ分だけ**（月額5万円の顧問の今週分は `50000 × 1 = 50000`。式の件数に `ヶ月`／`年` 等の期間単位を掛けない）。売上に直接乗らないものは `→ 売上貢献：0（いつ・いくらの見込みか）`。貢献の合計が売上目標に届くまで対話を止めない。記法の正本は `references/output-formats.md`。
- **行動と成果をグループで結ぶ**: 行動目標は `### → XXX：{要約}（{貢献額}円）` の見出しでグループ化し、その配下に `- [ ]` を並べる。XXX は成果目標セクションに実在する項目で、見出しの `{貢献額}` はその成果目標の貢献額と一致させる。習慣・土台のみ `### → （土台）`／`### → （関係維持）` 可。貢献額の大きいグループを上に置く並び順は推奨（優先順位が見えるため。機械検査はしない）。
- **シンプルに書く（1項目=1つのこと）**: 成果目標は5件・1項目50字まで、行動目標は8件・1項目60字まで。`・` で複数の成果を1項目に詰め込まない。長くなったら短縮でなく2件に割る。背景・理由は `→ 【考え】`／`→ 【思い】` の注記行へ寄せ、目標本文には入れない。
- **数値は半角のみ**（「万円」不可 → `600000`）。差分は必ず `+`/`-` 付き（例 `-300000`, `+2`）。行動目標には期日と数値を含める。
- **関係構築が軸**: 売上目標を「追う」のでなく「人との関係を育む」を先に置く。売上は関係の結果。
- **ファイルは3本・月報だけ1ファイル2セクション**: 提出用の別ファイルを作らない（**理由: 複数ファイルにまたがると改善・修正のときに反映漏れが起きる**。片方だけ直して他方が古いまま残る形を作らない。見やすさを理由に2本へ戻さない）。月報は1ファイルの中で `# 北原さん提出用（シンプル）` → `# 管理用（詳細）` の順に分け、**提出用セクションの `## 【…】` には閉じ括弧の内側に「（提出）」を付ける**（例 `## 【今月の売上目標（提出）】`）。週報・期報は詳細のみ。既存の `（提出）` 付きファイルは削除せず `05_Project/UBM/目標設定/archive/` へ分離する。
- **出力の内容規則の正本**: `references/output-formats.md`。**本 skill は実行手順であって内容規則の本文は持たない。正本と矛盾した場合は正本が勝つ。** Phase3 に入る前に該当節を Read する。
  - 三層分離の定義・判定順・数の単位 → 「売上目標・成果目標・行動目標の三層分離」／行動目標の動詞 → 「行動目標の動詞（この語で書く／この語で書かない）」／採否基準 → 「行動目標に何を載せるかの採否基準」／成果→行動の粒度 → 「成果→行動の完全な落とし込み」／一本筋の記法（グループ見出し）と項目名の一致・成果1件に行動1つ以上 → 「分離の実装ルール」／並び順と期日の逆算 → 「行動目標の並び順と期日の逆算」／提出用セクションの粒度 → 「提出用セクションの粒度（シンプルな構成）」／「シンプル＝項目を削ることではない」と両セクション同値 → 「月報は1ファイルの中で提出用セクションと管理用セクションに分ける」／行動差分の書き方 → 「差分セクション」／未達の挽回3点骨格 → 「要因分析セクション」／継続売上と単発の分離・最重要数字 → 「継続売上と単発を混ぜない」
  - 一本筋の切れのうち、支える行動の無い成果目標は **`validate-goal-output.py` では C6 の WARN に留まり rc=0 で通る**。生成後に必ず `validate-goal-linkage.py` を回し、rc の値を記録する。月報は**管理用セクションだけ**を照合する（提出用グループは `SKIP`）。
- **精神論 NG**: 「頑張る」「意識する」「気をつける」は行動目標として不可 → 具体化（誰に・何を・いつまで・何件）を要求。
- **やらないこと3項目以上** + 判断基準1文で迷いを排除する。出力先は種別依存（月報・期報＝独立セクション必須／週報＝該当日の到達ラインの子タスクへ組み込み）。
- **合宿（アカデミー）整合**: 直近の合宿アドバイスと目標の方向性のズレを検出したら即軌道修正。
- **プロジェクト別タスク**: 週報=任意 / 月報=必須 / 期報=禁止。`- [ ] [期日] [提出先・宛先] 対象物・行動` のチェックリスト形式・2階層まで・先方担当者付き。
- **選択と集中の1点収束**: 目標が「人・お金・時間・場所・やること」の5要素で1点に収束しているかを検査し、中途半端が混ざっていたら差し戻す。判断基準は `references/selection-focus-goal-frame.md`（見出し構造は変更しない・対話側の検査基準のみ）。
- **ポジティブ事故を起こさない**: 支出を伴う行動目標は「そもそもかけない → 回収してから実行 → かけてから回収」の順で検討させ、最後の手段を採る場合は回収条件と期限を明記させる。
- **思考法駆動**: 質問の形で自然に思考法を適用し、名前は出さない。北原さんの原則引用は1対話あたり1〜2回まで。

## Gotchas

- **出力ファイル命名**: 週報 `UBM - 1-週報 - {期間}.md` / 月報 `UBM - 2-月報（１ヶ月） - {期間}.md` / 期報 `UBM - 3-月報（３ヶ月） - {期間}.md`（`{期間}` は `YYYY-MM-DD〜YYYY-MM-DD`）の3本のみ。`（提出）` 付きのファイル名は新規作成しない。旧名 `UBM - 3-月報（２ヶ月） - …` と `UBM - 3-期報 - …` は読み取り・過去参照では受理し続ける（新規作成では使わない）。
- **「（提出）」は validator を通すための規約**: 重複見出し検査は `## 【…】` 行の**完全一致**で数えるため、`## 【今月の売上目標（提出）】` は `## 【今月の売上目標】` と衝突しない。必須見出し検査も完全一致なので管理用セクション側で満たす。したがって**管理用セクションの見出しには文字を足さない**（素の `## 【今月の売上目標】` のまま。「（管理）」等を足すと必須見出しが満たされず FAIL）。`## 【今月の行動目標（提出）】` はグループ見出しを持たない1行1行動なので、所属の検査（C4/C5）と件数の上限（S3）から外れる。行動目標系の検査（NG表現 FAIL / 数値・期日・固有名詞 WARN）は見出しの部分一致で両セクションを1プールにするため、提出用セクションにも精神論を書かない（固有名詞 WARN は管理用セクション側で満たされる）。
- **validator だけでは止まらない一本筋の切れ**: `validate-goal-output.py` は支える行動の無い成果目標を C6 の WARN に留め、括弧で始まる見出し名（`### → （準備）` など）をすべて免除する。どちらも rc=0 で通るので、`validate-goal-linkage.py` を**必ず併走**させる（rc=3 は分母0で判定していない状態なので PASS にしない）。
- **単一ファイル検査の穴（三層のズレ）**: `validate-goal-output.py` と `validate-goal-linkage.py` は**どちらも1本のファイルしか見ない**。期報の数字を直して月報・週報へ降ろし忘れても両方 rc=0 で通る。`--peer` の層間一致は WARN のみ・3アンカーで rc を上げない。期報と月報が揃ったら `validate-cross-level.py` を回す（週報があれば `--weekly` も渡す。rc=1 で落ちる）。**期報を先に直し、そこから月報・週報へ降ろす。下から上へは直さない。**
- **経緯の記述を現在値と読み違える**: 「以前は500,000だった」のような履歴は【仮置き事項】【衝突】【確定済み・解消済みの記録】【来月以降に対応すること】の中に置く。アンカーの節の本文に混ぜると、人も検査器も現在値として読む（`validate-cross-level.py` はこれらの節を抽出範囲から外している）。
- **ファイル名に全角カッコ付き期間表記を本文へ書かない**: 本文で他ファイルを参照するときは `（１ヶ月）`・`（３ヶ月）` を含むファイル名を引用せず期間表記で書く（validator の全角数字チェックで rc=1 になる）。
- **期報の期間**: UBM の目標期間は月の最終月曜日起点。期報は対象3ヶ月分の月報期間の連結で、開始日=1ヶ月目の月報開始日 / 終了日=3ヶ月目の月報終了日（例: 7月・8月・9月分 → `2026-06-29〜2026-09-27`）。期報は月報3件をロールアップして作る。
- **保存先**: `$UBM_VAULT_ROOT/05_Project/UBM/目標設定/` のみ（`UBM_VAULT_ROOT` 未設定時は self-relative 解決）。
- **Daily.md 更新（Phase6）**: `$UBM_VAULT_ROOT/02_Configs/Templates/Daily.md` の該当 embed 行のみ正規表現で検出・置換し、他部分は一切変更しない。サマリー見出し（`【1週間の目標】`/`【1ヶ月の目標】`/`【3ヶ月の目標】`）は継続語彙で凍結（今週/今月/今期へ改名しない）。
- **期報の正本**: `references/output-formats.md` の静的規則を A1 優先で正本化し、動的学習はスタイル参照に限定（見出し集合を上書きしない）。
- **書き込み保護**: `ubm-write-path-guard` hook が `UBM_VAULT_ROOT` 配下の許可範囲外への Write|Edit|MultiEdit を fail-closed で阻む。hook の許可範囲の正本は plugin 直下 `hooks/ubm-write-path-guard.py` の `ALLOWED_PREFIXES` / `ALLOWED_EXACT` で、`05_Project/` 全体・`02_Configs/Daily/` なども含み、本 skill の書き込み範囲より広い。本 skill が書くのは `05_Project/UBM/目標設定/`（`archive/` を含む）と Daily.md の embed 行だけで、その境界は hook ではなく本 skill の規則が守る。vault 外の plugin 同梱 data は保護対象外。

## Additional Resources

- **agents**: `info-collector` / `goal-reviewer` / `phase3-coordinator` / `output-formatter`（plugin 直下 `agents/`。coordinator は必要時に `prompts/R1-R5` を Read して次問案だけを返し、ユーザー対話と状態更新は親が行う）。
- **prompts**: `prompts/R{1..5}-<slug>.md` — Phase3 対話 Step1-5 の責務単位 7 層プロンプト正本（prompt-placement-convention 準拠、verify-completeness.py で 7 層+l5-contract 検証）。
- **scripts**: `scripts/validate-goal-output.py`（出力バリデーション・決定論ゲート）/ `scripts/validate-goal-linkage.py`（一本筋の両方向照合・照合規則は validator と共用・rc=0/1/2/3。受け入れテストは plugin 直下の `../../tests/test_validate_goal_linkage.py`）/ `scripts/validate-cross-level.py`（期報・月報・週報の期アンカー8種の横断照合・rc=0/1/2/3。受け入れテストは plugin 直下の `../../tests/test_validate_cross_level.py`）/ `../../scripts/validate-inline-goal-seek-anchor.py`（plugin 直下。inline goal-seek の progress/intermediate anchor 検証・fail-closed）。
- **references**: `references/selection-focus-goal-frame.md`（北原さん 2026-08-12 コメント由来の選択と集中フレーム・期間別検査・運用カレンダー）/ `references/thinking-guide.md`（思考法）/ `references/output-formats.md`（テンプレートの公式21ブロック・提出用/管理用セクションの粒度・三層分離・行動目標の採否基準・一本筋・継続売上と単発の分離の単一正本）/ `references/data-contract.md`（Phase 間 I/O）/ `references/thinking-methods-toolkit.md` / `references/thinking-process.md` / `references/version-history.md` / `references/resource-map.yaml`（資源一覧の機械可読正本）。
- **assets**: `assets/execution-prompts.md`（フロー参照）/ `assets/interview-quick-templates.md` / `assets/action-goals-best-practices.md` / `assets/golden-sample-weekly.md`（Few-shot）。
- **knowledge**: plugin 直下 `knowledge/`（`router.json` → `*.json` を info-collector がデュアルパス検索。L1 curated vendor 同梱でfresh-install 直後から機能）。
