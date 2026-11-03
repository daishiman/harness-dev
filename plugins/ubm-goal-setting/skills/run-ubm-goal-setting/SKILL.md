---
name: run-ubm-goal-setting
description: 1年目標から週報までの4層の目標設定を生成したいとき、振り返り対話を北原さん式の統一ハイブリッド構造で作成したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[yearly|weekly|monthly|quarterly]"
arguments: [type]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
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
version: 0.3.0
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
  - ../../scripts/validate-design-rubric.py
  - ../../scripts/extract-knowledge-matches.py
  - ../../scripts/build-knowledge-usage-log.py
  - ../../scripts/guard-staged-publication.py
  - scripts/validate-goal-output.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
  - scripts/validate-goal-linkage.py
  - scripts/validate-cross-level.py
domain: ubm-goal-setting
rubric_refs:
  - ../run-ubm-knowledge-sync/references/rubric.json
reference_refs:
  - ../../references/content-review-rubric.md
  - ../../references/knowledge-retrieval-contract.md
  - ../../references/guarded-publication-contract.md
  - ../../references/action-language-policy.json
  - ../../references/goal-seek-anchor-contract.md
  - ../../references/agent-root-contract.md
  - references/resource-map.yaml
  - references/validation-gates.md
  - references/selection-focus-goal-frame.md
  - references/thinking-guide.md
  - ../../CHANGELOG.md
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
      text: validate-goal-output.py が出力前に統一ハイブリッド構造の公式21ブロック・NG表現・やらないこと3項目以上に加え、--type と本文タイトル見出しラベルの一致を検証し違反0件であることを確認する。--type は weekly|monthly|quarterly|yearly（bimonthly は quarterly の後方互換の別名）で、yearly は 1年層の必須見出し集合を検査する。種別の不一致は rc=1 で不合格（FAIL）とする停止条件である。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: validate-goal-linkage.py が出力前に一本筋(行動目標のグループ見出し `### → 成果目標名：…` の成果目標名が成果目標セクションの項目名と一致し、各成果目標を支える行動が最低1件ある)を両方向で照合し rc=0 であることを確認する。rc=3(照合対象0件)は合格（PASS）として扱わない。
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: 期報と月報が揃っている場合、validate-cross-level.py が期アンカーを層をまたいで照合し rc=0 であることを確認する(週報があれば --weekly。1年層の引数は references/validation-gates.md の「IN3 の1年層の引数」に従う)。rc=3(抽出0件)は合格（PASS）として扱わない。抽出不可は不一致と別枠で列挙され rc=1 になる。--no-yearly のときは [未照合] のアンカー件数を記録する。期報か月報のどちらかが無い場合だけこの基準を適用しない。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 1年目標/週報/月報/期報を実際に生成し validate-goal-output が合格（PASS）し、目標設定・振り返り対話が北原さん式の公式21ブロックを満たすことを受入テストが確認する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: run-skill-live-trial で対話を実走し、AskUserQuestion のゲートを越えて Phase3 対話→Phase5 検証→Phase6 Daily.md の埋め込み更新まで自走完遂し目標設定ファイルが実生成されることを実行証拠で確認する。
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

# run-ubm-goal-setting

対話・既存修正では、`references/output-formats.md` の「共通部品（全層共通の正本）」「目標設計の流れ」「簡潔な記述の共通原則」を先に読む。月報の提出・管理の同期には「月報の項目保持と同期」を適用する。

UBM（北原さん式ゴールセッティング）の目標設定（1年=1年 / 期報=3ヶ月 / 月報=1ヶ月 / 週報=1週間 の4層）を高速対話で作成し、「行動を促し→実行し→成果を出す」サイクルを支援する。思考法駆動＋「愛情ある厳しさ」で本質を突き、即行動可能な計画を設計する。

## 目的と出力契約

**禁則**: 正式保存前後の検証を省略しない。目標と Daily の更新は承認受領書に束縛した保存だけで行う。

- **ゴール**: 1年目標/週報/月報/期報の目標設定・振り返り対話が北原さん式の統一ハイブリッド構造（公式21ブロック）で出力され、`validate-goal-output.py`（形式）と `validate-goal-linkage.py`（一本筋の両方向照合）の両方に合格（PASS）し、期報と月報が揃っている場合は `validate-cross-level.py`（層をまたぐ値の照合・IN3）にも合格した状態。
- **出力契約**: 統一ハイブリッド構造の公式21ブロックを満たす Markdown 目標設定ファイル**1本**（月報だけはその1ファイルの中が提出用セクション＋管理用セクションの2セクションに分かれる） + `validate-goal-output` と `validate-goal-linkage` の検証結果（それぞれの rc の値と引数）。期報と月報が揃っている場合は `validate-cross-level.py` の rc と引数も記録し、揃っていない場合は rc ではなく不適用（`not_applicable`）と記録する。`--no-yearly` を渡した場合は `[未照合]` のアンカー件数も併記する（黙って分母から消さない）。該当案件名は `tenant` 表記で統一する。
- **境界**: 入力=過去目標 / 合宿情報 / ナレッジ JSON / 日次ジャーナル / 挑戦宣言（読み取り専用）/ 対話回答。出力=目標設定ファイル1本 + `02_Configs/Templates/Daily.md` にある Obsidian の埋め込み参照の更新（種別該当分）。`（提出）` 付きの既存ファイルがある場合だけ、削除せず `05_Project/UBM/目標設定/archive/` へ移す（vault 上のファイル移動なので、外部変更のプレビューで渡す `--target-scope` と `--side-effect-summary` に移動元と移動先を含める）。ナレッジそのものの更新は `run-ubm-knowledge-sync` へ委譲する。
- **統一ハイブリッド構造・粒度・採否・参照整合の定義正本**: `references/output-formats.md` + `references/data-contract.md`（公式21ブロックの順序）。**「公式21ブロック」は出力テンプレートの固定の見出し集合（21 は不変）。`output-formatter` の品質チェックリストの件数とは別物で、そちらは件数で呼ばない。**提出用セクションと管理用セクションの違い・売上目標/成果目標/行動目標の三層分離・行動目標の採否基準・一本筋の照合・継続売上と単発の分離も `output-formats.md` 内に置く（別ファイルへ散らさない）。`validate-goal-output.py` はこの正本に基づき公式21ブロックを検査する。

<!-- runtime-root-contract:v1 -->
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
- `prompts/` の下のファイルも、このスキルの決まりに従う。
<!-- /runtime-root-contract:v1 -->

## 選ぶ前の実成果物の作成

「目的と出力契約」の最小の実成果物か、外部変更のプレビューを親コンテキストで作る。effect に応じた最低限の検査（読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物のパス・ハッシュ値・開き方か、プレビューの受領書を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すなら外部変更を行わずに引き継ぎを完了とし、後続の節を実行しない。

## 選んだ深さでの改善の実行

以下の既存の節（全体の流れ・ゴールシーク・評価・修正）と外部変更の安全手順は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。実際の外部変更は正規の `preview`→`hook-confirm`→`authorize`→`execute` の手順だけを通し、リリースと完全監査は別イベントとして明示されたときだけ行う。

<!-- external-mutation-guard-cli-ja:v1 -->
### 外部変更の受領書の手順（必須）

外部変更のコマンドを直接実行しない。山括弧のプレースホルダは、すべてこの実行で確かめた値に置き換える。
値が欠けていたり正しくなかったりすれば、中央の CLI が止める（fail-closed）。

`preview` の前に、ガードを持つプラグインのルートを1回だけ解決する。インストールされたプラグインからは、
隣のプラグインに `<プラグインのルート>/..` では届かないので、このパスを推測しない:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-plugin-root.py" skill-governance-adapters
```

表示された絶対パスを、`preview`・`authorize`・`execute` の `<GUARD_PLUGIN_ROOT>` に使う
（確認を待つあいだはほかの Bash が止められるので、解決し直さない）。
解決のスクリプトが 0 以外で終わったら、外部変更をせずに止まり、`skill-governance-adapters` プラグインを入れるようユーザーに伝える。

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

この正規の `preview` の出力をユーザーに見せる。登録済みの `hook-confirm` を動かせるのは、`preview` が表示したとおりのユーザーの返答だけ。
そのあと、返ってきた2つの受領書のパスを使う:

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

自動承認のフラグを使わない。この受領書の手順の外で外部変更のコマンドを実行しない。
<!-- /external-mutation-guard-cli-ja:v1 -->


### 正式保存の実行境界

`../../references/guarded-publication-contract.md` をReadして適用する。書き手のWriteは一時下書きだけとし、正式保存・archive移動・Daily更新・ナレッジ/台帳/グラフの更新は親がユーザー承認とcommand-bound受領書を揃えた中央guard `execute`だけで実行する。保存可否booleanだけで直接Write/Editしない。

`../../references/knowledge-retrieval-contract.md` をReadし、同契約の入力表に従って決定論の重み付き検索→候補の意味選択→親による実利用IDと取得済みユーザー反応の記録を実行する。検索結果を `knowledge_candidates` として担当役へ渡し、返された実使用を実際の出力と照合する。

## 全体の流れ

`assets/execution-prompts.md` でフロー全体を把握し、以下の段階（Phase）を順次実行する（依存のないタスクは並列）。`assets/execution-prompts.md` と `references/data-contract.md` は整形・検証・保存をまとめて「Phase 4」と呼ぶ。本表の Phase4-format〜Phase5-validate（Phase4b-submission を含む）がそれに当たる。

| 段階 | 責務 | 実行体 |
|---|---|---|
| Phase0-init | 対象種別（1年/期報/月報/週報）と実行日を確定。引数があれば飛ばす。オプション4は1年目標（`yearly`）、オプション5は既存目標見直しモード（`goal-reviewer`） | AskUserQuestion / 本スキル |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ（デュアルパス検索）・ジャーナル・挑戦宣言を読み取り専用で並列収集し構造化サマリー生成。**種別を問わず現行の1年目標と最新の挑戦宣言を収集し、1年層の到達点（月間売上到達点・継続コンサル人数）を対話へ持ち上げる** | `info-collector`（Task） |
| Phase2b-review | 振り返り対話時に既存目標設定を13項目（基本2＋合宿整合性3＋関係構築3＋三層分離5）で見直し・再評価 | `goal-reviewer`（Task） |
| Phase3-dialogue | 親が Step1-5 を参照し、現状振り返り〜最終確認の対話を進行。必要な場合だけ `phase3-coordinator` から読み取り専用の次問案を受ける | 本 skill（親対話）+ `phase3-coordinator`（任意の助言用 Task） |
| Phase4-format | 目標設定テンプレートへ整形し、`agents/output-formatter.md` Layer 4 の品質チェックリスト（件数は正本側で増減するためここに書かない）を全項目確認する。行動目標は採否基準で1行ずつ判定する | `output-formatter`（Task） |
| Phase4b-submission | **月報のときだけ**、同じファイルの先頭に提出用セクション（公式21ブロックを全件・見出しに「（提出）」を付ける。中身は管理用の射影で、行動行は `output-formats.md` の「共通部品A 行動行」の提出用の書式）を置き、その後に管理用セクションを続ける | `output-formatter`（Task） |
| Phase5-validate | `references/validation-gates.md` を正本として、適用する IN1 → IN2 → IN3 を保存前の下書きと保存後の実ファイルに各1回実行する。両段階が合格したときだけ Phase6 へ進む。月報の提出用と管理用も同一ファイルを検査する。保存時に `（提出）` 付きの既存ファイルがある場合だけ、削除せず `archive/` へ移す。`--type` は4層の値（`yearly`/`quarterly`/`monthly`/`weekly`）から対象種別のものを渡す | `output-formatter`（下書き）+ 本スキル（中央guard保存）+ IN1〜IN3 の検査スクリプト |
| Phase6-daily-update | 保存後、Daily.mdの一時コピーの該当埋め込み行だけを更新し、別manifestと中央guard executeで正式反映 | 本スキル |

`Task` のルート入力と停止条件は `../../references/agent-root-contract.md` が正本。全 Task に解決済みの `plugin_root` を渡し、vault の収集/保存には `vault_root`、相談証跡の参照には `project_root` も渡す。vault 未接続時は vault の Task と保存を行わず、同梱ナレッジを参照した対話と下書きの提示までに縮退する。空の環境変数を許可パスとして扱わない。

**所要時間目安**: 値は `output-formats.md` の「共通部品F 層別差分表」（1年は挑戦宣言が確定していることを前提とした推定値。1年層の対話を実測したら F の値と `agents/phase3-coordinator.md` のターン数を同時に直す）。

### Phase5 の検証コマンド（種別別）

`--file` は保存前の下書きと保存後の実ファイルに各1回当てる。rc は**値そのものと引数**を記録する。

```bash
# IN1: 対象種別の --type を渡す（4層 + 後方互換の bimonthly）
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-goal-output.py" --file "<対象ファイル>" --type yearly
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-goal-output.py" --file "<対象ファイル>" --type quarterly
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-goal-output.py" --file "<対象ファイル>" --type monthly
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-goal-output.py" --file "<対象ファイル>" --type weekly

# IN2: 一本筋（種別引数は持たない）
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-goal-linkage.py" --file "<対象ファイル>"

# IN3: 層をまたぐ照合（1年層の引数は references/validation-gates.md の「IN3 の1年層の引数」）
python3 "$PLUGIN_ROOT/skills/run-ubm-goal-setting/scripts/validate-cross-level.py" \
  {--yearly "<1年目標>" | --no-yearly "<理由>"} --quarterly "<期報>" --monthly "<月報>" [--weekly "<週報>"] [--month N]
```

1年層の扱いは `output-formats.md` の「共通部品C 設計順序と4層」、IN3 の1年層の引数は `references/validation-gates.md` の「IN3 の1年層の引数」に従う。

## 対象種別（4層）

| 層 | `--type` / 引数 | 期間語 | タイトル見出し | ファイル名 |
|---|---|---|---|---|
| 1年 | `yearly` | 今年 / 前年 | `## 【1年の目標】{期間}` | `UBM - 4-年報（１年） - {期間}.md` |
| 3ヶ月 | `quarterly` | 今期 / 前期 | `## 【3ヶ月の目標】{期間}` | `UBM - 3-月報（３ヶ月） - {期間}.md` |
| 1ヶ月 | `monthly` | 今月 / 前月 | `## 【1ヶ月の目標】{期間}` | `UBM - 2-月報（１ヶ月） - {期間}.md` |
| 1週間 | `weekly` | 今週 / 前週 | `## 【1週間の目標】{期間}` | `UBM - 1-週報 - {期間}.md` |

- `bimonthly` は `quarterly` の後方互換の別名（旧・2ヶ月期報の呼び名）。新規では使わない。
- ファイル名プレフィックスの許容は `UBM - [1-4]-`。
- **1年層の期間は暦の1年で切る**（下位3層の最終月曜起点とは別の切り方）。
- **1年層の正本は挑戦宣言**（`$UBM_VAULT_ROOT/05_Project/UBM/挑戦宣言/UBM - 挑戦宣言 - YYYY-MM-DD.md`）。1年層に置いた到達点を下位層へ割っていく順序は `output-formats.md` の「共通部品C 設計順序と4層」に従う。
- **対象の年報の期限までつなげる**: 現行の1年目標と挑戦宣言を参照し、各層の対応を `references/output-formats.md`「四層（1年目標・期報・月報・週報）の連携」、軌道修正の記録を `output-formats.md` の「共通部品E 軌道修正記録」で確認する。

## ゴールシーク実行

固定手順を消化するのでなく、上記ゴールと `feedback_contract` を満たすまで親の対話コンテキストで反復する（`engine: inline`／`fork: inline`／`max_loops: 5`）。

### ゴールシーク配線

- `goal_seek.progress`（進捗ファイル）: `eval-log/ubm-goal-setting/run-ubm-goal-setting/goal-seek-progress.json` にチェックリストの状態、周回数、`open_issues`、`status` を記録する。
- `goal_seek.intermediate`（中間ファイル）: 各周回末のアンカー手順（Anchor Step）で `run-ubm-goal-setting-intermediate.jsonl` に `original_goal` / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` を追記のみで残す。
- `goal_seek.handoff`（引き継ぎファイル）: 完了時に、検証済みの目標設定ファイルのパス、Daily.md の更新有無、検証結果を `handoff-run-ubm-goal-setting.json` へ書く。
- ループ本体とユーザー対話は親コンテキストが持つ。`Task` は表の専門責務へ限定し、各結果を親へ戻して同じゴールとチェックリストに統合する。
- `max_loops` 到達時は合格扱いせず、残チェック項目を `open_issues` に残して人のレビューへ差し戻す。

### ゴールシーク検証

共通アンカーは `../../references/goal-seek-anchor-contract.md` を Read し、初回固定と各周回の追記を行う。完了前に親が frontmatter の progress/intermediate を `project_root` から絶対パスへ解決して次を実行し、終了コード 0 を必須とする。

```bash
python3 "$PLUGIN_ROOT/scripts/validate-inline-goal-seek-anchor.py" \
  "{resolved_progress_path}" "{resolved_intermediate_path}"
```

- **内側ループ（IN1）**: Phase5 で `validate-goal-output.py` を実行する（回す条件・引数・rc の意味は、`references/validation-gates.md` の「決定論ゲート」の表が正本。IN2・IN3 も同じ。`--type` は4層の `weekly`/`monthly`/`quarterly`/`yearly` を受け、`bimonthly` は `quarterly` の後方互換の別名として受理される）。`--type yearly` は1年層の必須見出し（期報と同じ骨格で期間語を「今年/前年」に置き換えたもの。`【今年の最重要数字】` は期報と違い必須）を検査し、1年層では**プロジェクト別タスクを出力しない**ことも含めて見る。統一ハイブリッド構造の公式21ブロック・NG表現・やらないこと3項目以上・逆算チェーン（C1〜C6）・シンプルさ上限（S1〜S3）に加え、**`--type` と本文タイトル見出しラベルの一致**を出力前に検証し、種別の取り違えを止める。違反0件になるまで `output-formatter` が決定論ゲートの修復上限（`references/validation-gates.md`）まで改善する。上位層のファイルを `--peer PATH` で渡すと期アンカーの層間整合を警告（WARN）として併せて報告する（任意・rc には影響しない）。
- **内側ループ（IN2）**: 続けて `validate-goal-linkage.py` を実行する。IN1 の C4（所属不明）・C5（参照先の実在）は不合格だが、**C6（支える行動の無い成果目標）は警告で rc を上げず、括弧で始まる見出し名はすべて免除する**。IN2 は同じ照合規則（成果目標名の切り出し・空白を落とした完全一致・グループ見出しの解釈）を `validate-goal-output.py` から読み込んで使い、支える行動の無い成果目標・`・` で複数の成果目標を指す見出し・`（土台）`／`（関係維持）` 以外の括弧名・月報のグループ見出しのラベルずれを不合格にする。rc=0 になるまで改善する（rc=3 を合格として扱わない理由も表にある）。IN1〜IN3 の rc は**値そのものと引数**を記録する（記録の形は「目的と出力契約」、rc の取り方は`references/validation-gates.md` のとおり）。
- **内側ループ（IN3）**: 正本の回す条件に当たるとき（作成中の下書きと同じ期の peer を合わせて期報と月報が揃うとき）、`validate-cross-level.py` を実行する。**IN1 / IN2 はどちらも1本のファイルしか見ないため、期報の数字を直して月報・週報へ追随させ忘れても rc=0 で通る**（層をまたぐ値を突き合わせる口が存在しない＝分母0件）。この穴を IN3 が埋める。期アンカーを渡した層（1年・期報・月報・週報）で並記して照合し、抽出できなかったアンカーは不一致と別枠で列挙する。照合する期アンカーの一覧の正本は `references/data-contract.md` §3.1.3 の「四層横断照合（validate-cross-level.py）の対象一覧」。1年層の引数は `references/validation-gates.md` の「IN3 の1年層の引数」に従う。
- **外側ループ（OUT1）**: 1年目標/週報/月報/期報を実際に生成し `validate-goal-output.py` が合格することを受入テストで確認する。未達の指摘は再実行で反映し、OUT1 の周回上限（5周）までに収束させる。
- **振る舞いの受け入れ確認（OUT2）**: 静的な内容レビュー（`content-review`）とは分離し、`run-skill-live-trial` で AskUserQuestion のゲート → Phase3 対話 → Phase5 検証 → Phase6 Daily.md の埋め込み更新と目標設定ファイル実生成までを実走証拠として確認する。

## 守ること

- **4層の設計と調整**: `references/output-formats.md`「四層（1年目標・期報・月報・週報）の連携」を正本に、直属上位の成果・期限への対応と、実績を踏まえた月・週の調整を確認する。
- **出力の内容規則の正本**: `references/output-formats.md`。**本スキルは実行手順であって内容規則の本文は持たない。** Phase3 に入る前に該当節を `Read` で読む。
  - 行動目標1行の書式・合格基準・期日・並び順 → `output-formats.md` の「共通部品A 行動行」
  - 成果目標の2行記法と売上貢献の根拠 → `output-formats.md` の「共通部品B 成果目標と売上貢献の根拠」
  - 売上 → 成果 → 行動の逆算と4層（1年・期報・月報・週報で共通） → `output-formats.md` の「共通部品C 設計順序と4層」
  - 前期間の転記・実績・差分・挽回 → `output-formats.md` の「共通部品D 前回ブロック」
  - 月・週の軌道修正と記録 → `output-formats.md` の「共通部品E 軌道修正記録」
  - 層ごとに違う値（ファイル構成・`projects` の要否・日付索引・やらないことの出力先）と、名前で区別する上限3つの正本の場所 → `output-formats.md` の「共通部品F 層別差分表」
  - 目標の各層に何を置くかの基準（全層の大前提） → `output-formats.md` の「共通部品G 原理原則の基準」
  - 三層分離の定義・判定順・数の単位 → 「売上目標・成果目標・行動目標の三層分離」／行動目標の動詞 → 「行動目標の動詞（この語で書く／この語で書かない）」／採否基準 → 「行動目標に何を載せるかの採否基準」／成果→行動の粒度 → 「成果→行動の完全な落とし込み」／一本筋の記法（グループ見出し）と項目名の一致・成果1件に行動1つ以上 → 「分離の実装ルール」／並び順と期日の逆算 → 「行動目標の並び順と期日の逆算」／提出用セクションの粒度 → 「提出用セクションの粒度（シンプルな構成）」／「シンプル＝項目を削ることではない」と両セクション同値 → 「月報は1ファイルの中で提出用セクションと管理用セクションに分ける」／行動差分の書き方 → 「差分セクション」／未達の挽回3点骨格 → 「要因分析セクション」／継続売上と単発の分離 → 「継続売上と単発を混ぜない」／最重要数字（売上と人数の対） → 「共通部品G 原理原則の基準」と各層の【…の最重要数字】の注記
  - 一本筋の照合は IN2 を参照。月報は**管理用セクションだけ**を照合する（提出用グループは `SKIP`）。
- **記述量**: `references/output-formats.md` の「簡潔な記述の共通原則」「シンプルさの上限」に従う。
- **数値の表記**: `output-formats.md` の「数値ルール」に従う。
- **関係構築が軸**: 売上目標を置いたうえで、成果と行動が `output-formats.md` の「共通部品G 原理原則の基準」に沿っているかを確かめる（成果は誰からのどの YES か・前回 YES をくれた人と連続しているか、行動は原理原則のどの動きか）。
- **ファイルは4層で各1本・月報だけ1ファイル2セクション**: 構成は `output-formats.md` の「共通部品F 層別差分表」、理由と旧 `（提出）` ファイルの扱いは `output-formats.md` の「ファイル命名規則」に従う。
- **精神論 NG**: NG 語の正本は `../../references/action-language-policy.json` の `goal_exact_phrases`。該当したら `output-formats.md` の「共通部品A 行動行」の形へ具体化を求める。
- **やらないこと3項目以上** + 判断基準1文で迷いを排除する。出力先は `output-formats.md` の「共通部品F 層別差分表」に従う。
- **合宿（アカデミー）整合**: 直近の合宿アドバイスと目標の方向性のズレを検出したら即軌道修正。
- **詳細タスクの要否**: `projects` の要否は `output-formats.md` の「共通部品F 層別差分表」に従い、簡潔な月報では自動追加しない。
- **選択と集中の1点収束**: 目標が「人・お金・時間・場所・やること」の5要素で1点に収束しているかを検査し、中途半端が混ざっていたら差し戻す。判断基準は `references/selection-focus-goal-frame.md`（見出し構造は変更しない・対話側の検査基準のみ）。
- **ポジティブ事故を起こさない**: 支出を伴う行動目標は「そもそもかけない → 回収してから実行 → かけてから回収」の順で検討させ、最後の手段を採る場合は回収条件と期限を明記させる。
- **思考法駆動**: 質問の形で自然に思考法を適用し、名前は出さない。北原さんの原則引用は、ターンテンプレートに固定した引用のほかに、1対話あたり1〜2回まで。

## つまずきやすい点

- **出力ファイル命名**: 週報 `UBM - 1-週報 - {期間}.md` / 月報 `UBM - 2-月報（１ヶ月） - {期間}.md` / 期報 `UBM - 3-月報（３ヶ月） - {期間}.md` / 1年 `UBM - 4-年報（１年） - {期間}.md`（`{期間}` は `YYYY-MM-DD〜YYYY-MM-DD`）の4本のみ。プレフィックスの許容は `UBM - [1-4]-`。`（提出）` 付きのファイル名は新規作成しない。旧名 `UBM - 3-月報（２ヶ月） - …` と `UBM - 3-期報 - …` は読み取り・過去参照では受理し続ける（新規作成では使わない）。
- **「（提出）」は `validate-goal-output.py` を通すための規約**: 重複見出し検査は `## 【…】` 行の**完全一致**で数えるため、`## 【今月の売上目標（提出）】` は `## 【今月の売上目標】` と衝突しない。必須見出し検査も完全一致なので管理用セクション側で満たす。したがって**管理用セクションの見出しには文字を足さない**（素の `## 【今月の売上目標】` のまま。「（管理）」等を足すと必須見出しが満たされず不合格）。`## 【今月の行動目標（提出）】` はグループ見出しを持たない1行1行動なので、所属の検査（C4/C5）と件数の上限（S3）から外れる。行動目標系の検査（NG表現・期日の欠落。期日の規則は `output-formats.md` の「共通部品A 行動行」）は見出しの部分一致で両セクションを1プールにするため、提出用セクションにも精神論を書かず、期日を落とさない。
- **層のズレの扱い**: 照合は IN3、訂正と軌道修正の区別は正本の四層連携に従う。IN1 の `--peer` は金額2アンカー（今期の売上目標・累計売上実績）の参考照合で、IN3 の代わりにはならない。
- **経緯の記述を現在値と読み違える**: 「以前は500,000だった」のような履歴は【仮置き事項】【衝突】【確定済み・解消済みの記録】【来月以降に対応すること】の中に置く。アンカーの節の本文に混ぜると、人も検査スクリプトも現在値として読む（`validate-cross-level.py` はこれらの節を抽出範囲から外している）。
- **ファイル名に全角カッコ付き期間表記を本文へ書かない**: 本文で他ファイルを参照するときは `（１ヶ月）`・`（３ヶ月）`・`（１年）` を含むファイル名を引用せず期間表記で書く。引用しても rc=1 にはならない（`validate-goal-output.py` の全角数字チェックは `１ヶ月`・`２ヶ月`・`３ヶ月`・`１年` を含む行を丸ごと外す）。**外れるのはその行全体なので、同じ行に書いたほかの全角数字も検査されないまま通る**。それを避けるために引用しない。
- **期報の期間**: UBM の目標期間は月の最終月曜日起点。期報は対象3ヶ月分の月報期間の連結で、開始日=1ヶ月目の月報開始日 / 終了日=3ヶ月目の月報終了日（例: 7月・8月・9月分 → `2026-06-29〜2026-09-27`）。期報は月報3件をロールアップして作る。
- **1年の期間だけ切り方が違う**: 1年層は**暦の1年**で切る（下位3層の最終月曜起点とは別）。期報・月報・週報の期間の区切りと1年層の区切りが一致しないのは既知のもので、揃えようとして下位層の起点を動かさない。1年層は月報・期報のロールアップで作るのではなく、**挑戦宣言を正本に到達点から組み立てる**（下位層は1年層から割る側）。
- **保存先**: `$UBM_VAULT_ROOT/05_Project/UBM/目標設定/` のみ（`UBM_VAULT_ROOT` 未設定時は保存を停止）。
- **Daily.md 更新（Phase6）**: `$UBM_VAULT_ROOT/02_Configs/Templates/Daily.md` の該当する埋め込み行だけを正規表現で検出・置換し、他部分は一切変更しない。サマリー見出し（`【1週間の目標】`/`【1ヶ月の目標】`/`【3ヶ月の目標】`）は継続語彙で凍結（今週/今月/今期へ改名しない）。**1年層の埋め込み行は Daily.md に無い場合がある**ので、`yearly` のときは該当行が存在するときだけ更新し、無ければ見出しを新設せず「更新対象なし」として記録する（Daily.md の見出しを本スキルの都合で増やさない）。
- **期報の正本**: `references/output-formats.md` の静的規則を A1 優先で正本化し、動的学習はスタイル参照に限定（見出し集合を上書きしない）。
- **書き込み保護**: `ubm-write-path-guard` フックは、`UBM_VAULT_ROOT` 配下の許可範囲外への Write|Edit|MultiEdit を止める。判定できない呼び出し（フックへの入力 JSON が読めない・書き込み先のパスが無い）も通さずに止める（不明なら止める）。フックの許可範囲の正本はプラグイン直下 `hooks/ubm-write-path-guard.py` の `ALLOWED_PREFIXES` / `ALLOWED_EXACT` で、`05_Project/` 全体・`02_Configs/Daily/` なども含み、本スキルの書き込み範囲より広い。本スキルが書くのは `05_Project/UBM/目標設定/`（`archive/` を含む）と Daily.md の埋め込み行だけで、その境界はフックではなく本スキルの規則が守る。vault 外のプラグイン同梱データは保護対象外。

## 関連資料

- **エージェント**: `info-collector` / `goal-reviewer` / `phase3-coordinator` / `output-formatter`（プラグイン直下の `agents/`。`phase3-coordinator` は必要なときに `prompts/R1-R5` を `Read` で読んで次の質問案だけを返し、ユーザーとの対話と状態の更新は親が行う）。
- **プロンプト**: `prompts/R{1..5}-<slug>.md` — Phase3 の対話 Step1-5 を責務ごとに分けた 7 層プロンプトの正本（`prompt-placement-convention` に従う。`verify-completeness.py` で 7 層と `l5-contract` を検証する）。
- **スクリプト**: `scripts/validate-goal-output.py`（出力の検証・決定論的なゲート）/ `scripts/validate-goal-linkage.py`（一本筋の両方向の照合。照合規則は `validate-goal-output.py` と共用。rc=0/1/2/3。受け入れテストはプラグイン直下の `../../tests/test_validate_goal_linkage.py`）/ `scripts/validate-cross-level.py`（1年目標・期報・月報・週報の4層をまたぐアンカーの横断照合。`LEVELS = ("yearly", "quarterly", "monthly", "weekly")`。1年層のアンカーは `requires_level="yearly"` で `--yearly` を渡したときだけ照合する。rc=0/1/2/3。受け入れテストはプラグイン直下の `../../tests/test_validate_cross_level.py`）/ `../../scripts/validate-inline-goal-seek-anchor.py`（プラグイン直下。インラインのゴールシークの進捗ファイル・中間ファイルのアンカーを検証し、不備なら止める）。
- **参照資料**: `references/selection-focus-goal-frame.md`（北原さん 2026-08-12 コメント由来の選択と集中フレーム・期間別検査・運用カレンダー）/ `references/thinking-guide.md`（思考法）/ `references/output-formats.md`（テンプレートの公式21ブロック・提出用/管理用セクションの粒度・三層分離・行動目標の採否基準・一本筋・継続売上と単発の分離の単一正本）/ `references/data-contract.md`（各 Phase の間の入出力）/ `../../CHANGELOG.md`（版履歴。`references/version-history.md` は凍結した旧スキル版の履歴）/ `references/resource-map.yaml`（資源一覧の機械可読正本）。
- **付属資料**: `assets/execution-prompts.md`（フロー参照）/ `assets/interview-quick-templates.md` / `assets/action-goals-best-practices.md` / `assets/golden-sample-weekly.md`（手本として示す例）。
- **ナレッジ**: プラグイン直下の `knowledge/`（`router.json` → `*.json` の順に `info-collector` がデュアルパス検索する。L1 の精選済みナレッジをプラグインに同梱しているので、新規インストールの直後から使える）。
