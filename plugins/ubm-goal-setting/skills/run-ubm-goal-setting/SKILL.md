---
name: run-ubm-goal-setting
description: 週報・月報・期報の目標設定を生成したいとき、振り返り対話を北原さん式の統一ハイブリッド構造で作成したいときに使う。
disable-model-invocation: false
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
  - ../../scripts/evaluate-design-rubric.py
  - ../../scripts/search-knowledge.py
  - ../../scripts/record-knowledge-usage.py
  - ../../scripts/publish-staged-files.py
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
      text: validate-goal-output.py が出力前に統一ハイブリッド構造の公式21ブロック・NG表現・やらないこと3項目以上に加え、--type と本文タイトル見出しラベルの一致を検証し違反0件であることを確認する。種別の不一致は rc=1 で不合格（FAIL）とする停止条件である。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: validate-goal-linkage.py が出力前に一本筋(行動目標のグループ見出し `### → 成果目標名：…` の成果目標名が成果目標セクションの項目名と一致し、各成果目標を支える行動が最低1件ある)を両方向で照合し rc=0 であることを確認する。rc=3(照合対象0件)は合格（PASS）として扱わない。
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: 期報と月報が揃っている場合、validate-cross-level.py が期アンカー8種を層をまたいで照合し rc=0 であることを確認する(週報があれば --weekly も渡して三層で照合する)。rc=3(抽出0件)は合格（PASS）として扱わない。抽出不可は不一致と別枠で列挙され rc=1 になる。期報か月報のどちらかが無い場合だけこの基準を適用しない。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 週報/月報/期報を実際に生成し validate-goal-output が合格（PASS）し、目標設定・振り返り対話が北原さん式の公式21ブロックを満たすことを受入テストが確認する。
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

UBM（北原さん式ゴールセッティング）の目標設定（週報=1週間 / 月報=1ヶ月 / 期報=3ヶ月）を高速対話で作成し、「行動を促し→実行し→成果を出す」サイクルを支援する。思考法駆動＋「愛情ある厳しさ」で本質を突き、即行動可能な計画を設計する。

## 目的と出力契約

**禁則**: 正式保存前後の検証を省略しない。目標と Daily の更新は承認受領書に束縛した保存だけで行う。

- **ゴール**: 週報/月報/期報の目標設定・振り返り対話が北原さん式の統一ハイブリッド構造（公式21ブロック）で出力され、`validate-goal-output.py`（形式）と `validate-goal-linkage.py`（一本筋の両方向照合）の両方に合格（PASS）し、期報と月報が揃っている場合は `validate-cross-level.py`（層をまたぐ値の照合・IN3）にも合格した状態。
- **出力契約**: 統一ハイブリッド構造の公式21ブロックを満たす Markdown 目標設定ファイル**1本**（月報だけはその1ファイルの中が提出用セクション＋管理用セクションの2セクションに分かれる） + `validate-goal-output` と `validate-goal-linkage` の検証結果（それぞれの rc の値と引数）。期報と月報が揃っている場合は `validate-cross-level.py` の rc と引数も記録し、揃っていない場合は rc ではなく不適用（`not_applicable`）と記録する。該当案件名は `tenant` 表記で統一する。
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
| Phase0-init | 対象種別（週報/月報/期報）と実行日を確定。引数があれば飛ばす。オプション4は既存目標見直しモード（`goal-reviewer`） | AskUserQuestion / 本スキル |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ（デュアルパス検索）・ジャーナル・挑戦宣言を読み取り専用で並列収集し構造化サマリー生成 | `info-collector`（Task） |
| Phase2b-review | 振り返り対話時に既存目標設定を13項目（基本2＋合宿整合性3＋関係構築3＋三層分離5）で見直し・再評価 | `goal-reviewer`（Task） |
| Phase3-dialogue | 親が Step1-5 を参照し、現状振り返り〜最終確認の対話を進行。必要な場合だけ `phase3-coordinator` から読み取り専用の次問案を受ける | 本 skill（親対話）+ `phase3-coordinator`（任意の助言用 Task） |
| Phase4-format | 目標設定テンプレートへ整形し、`agents/output-formatter.md` Layer 4 の品質チェックリスト（件数は正本側で増減するためここに書かない）を全項目確認する。行動目標は採否基準で1行ずつ判定する | `output-formatter`（Task） |
| Phase4b-submission | **月報のときだけ**、同じファイルの先頭に提出用セクション（公式21ブロックを全件・見出しに「（提出）」を付ける・人数集約・本文に具体日を埋めない・行動目標はグループ見出しを置かず1行1行動・期日は管理用で逆算した値と同値）を置き、その後に管理用セクションを続ける | `output-formatter`（Task） |
| Phase5-validate | `references/validation-gates.md` を正本として、適用する IN1 → IN2 → IN3 を保存前の下書きと保存後の実ファイルに各1回実行する。両段階が合格したときだけ Phase6 へ進む。月報の提出用と管理用も同一ファイルを検査する。保存時に `（提出）` 付きの既存ファイルがある場合だけ、削除せず `archive/` へ移す | `output-formatter`（下書き）+ 本スキル（中央guard保存）+ IN1〜IN3 の検査スクリプト |
| Phase6-daily-update | 保存後、Daily.mdの一時コピーの該当埋め込み行だけを更新し、別manifestと中央guard executeで正式反映 | 本スキル |

`Task` のルート入力と停止条件は `../../references/agent-root-contract.md` が正本。全 Task に解決済みの `plugin_root` を渡し、vault の収集/保存には `vault_root`、相談証跡の参照には `project_root` も渡す。vault 未接続時は vault の Task と保存を行わず、同梱ナレッジを参照した対話と下書きの提示までに縮退する。空の環境変数を許可パスとして扱わない。

**所要時間目安**: 週報 5〜8分 / 月報 10〜15分 / 期報 15〜20分。

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
python3 "$PLUGIN_ROOT/scripts/validate-inline-goal-seek-anchor.py" "$progress_path" "$intermediate_path"
```

- **内側ループ（IN1）**: Phase5 で `validate-goal-output.py` を実行する（回す条件・引数・rc の意味は、`references/validation-gates.md` の「決定論ゲート」の表が正本。IN2・IN3 も同じ。`--type` の `bimonthly` は後方互換の別名として受理される）。統一ハイブリッド構造の公式21ブロック・NG表現・やらないこと3項目以上・逆算チェーン（C1〜C6）・シンプルさ上限（S1〜S3）に加え、**`--type` と本文タイトル見出しラベルの一致**を出力前に検証し、種別の取り違えを止める。違反0件になるまで `output-formatter` が最大3回改善する。上位層のファイルを `--peer PATH` で渡すと期アンカーの層間整合を警告（WARN）として併せて報告する（任意・rc には影響しない）。
- **内側ループ（IN2）**: 続けて `validate-goal-linkage.py` を実行する。IN1 の C4（所属不明）・C5（参照先の実在）は不合格だが、**C6（支える行動の無い成果目標）は警告で rc を上げず、括弧で始まる見出し名はすべて免除する**。IN2 は同じ照合規則（成果目標名の切り出し・空白を落とした完全一致・グループ見出しの解釈）を `validate-goal-output.py` から読み込んで使い、支える行動の無い成果目標・`・` で複数の成果目標を指す見出し・`（土台）`／`（関係維持）` 以外の括弧名・月報のグループ見出しのラベルずれを不合格にする。rc=0 になるまで改善する（rc=3 を合格として扱わない理由も表にある）。IN1〜IN3 の rc は**値そのものと引数**を記録する（記録の形は「目的と出力契約」、rc の取り方は`references/validation-gates.md` のとおり）。
- **内側ループ（IN3）**: 正本の回す条件に当たるとき（作成中の下書きと同じ期の peer を合わせて期報と月報が揃うとき）、`validate-cross-level.py` を実行する。**IN1 / IN2 はどちらも1本のファイルしか見ないため、期報の数字を直して月報・週報へ追随させ忘れても rc=0 で通る**（層をまたぐ値を突き合わせる口が存在しない＝分母0件）。この穴を IN3 が埋める。期アンカーを期報と月報（週報があれば三層）で並記して照合し、抽出できなかったアンカーは不一致と別枠で列挙する。照合する期アンカーの一覧の正本は `references/data-contract.md` §3.1.3 の「三層横断照合（validate-cross-level.py）の対象一覧」。
- **外側ループ（OUT1）**: 週報/月報/期報を実際に生成し `validate-goal-output.py` が合格することを受入テストで確認する。未達の指摘は再実行で反映し、最大5周で収束させる。
- **振る舞いの受け入れ確認（OUT2）**: 静的な内容レビュー（`content-review`）とは分離し、`run-skill-live-trial` で AskUserQuestion のゲート → Phase3 対話 → Phase5 検証 → Phase6 Daily.md の埋め込み更新と目標設定ファイル実生成までを実走証拠として確認する。

## 守ること

- **売上 → 成果 → 行動の順に降ろす（週報・月報・期報 共通・最重要）**: 売上目標をまず1つ決め、そこから成果目標を逆算し、成果目標から行動目標を逆算する。行動から書き始めて成果を後付けする順序は禁止。
- **実行した時点で達成になる目標を置かない**: 「勉強会を月4回開催する」「アカデミーに参加する」等は成果ではなく行動。目標欄に置かず、当たり前の土台として扱う。成果目標は「実行した結果、相手側で何が起きたか」で書く。
- **成果と売上を数値で結ぶ**: 各成果目標は **1項目=2行**（1行目 `- 項目：先方判断・結果の状態　期日M/D` ／ 2行目 `  → 売上貢献：<単価> × <件数> = <貢献額>`）。裸の数字は不可で、式にできないものは `→ 売上貢献：<金額>（値引き後の一括見積 等の根拠）` と括弧で根拠を添える（`150000` だけでは後から誰も検算できないため）。計上するのは **その期間に実際に売上として立つ分だけ**（月額5万円の顧問の今週分は `50000 × 1 = 50000`。式の件数に `ヶ月`／`年` 等の期間単位を掛けない）。売上に直接乗らないものは `→ 売上貢献：0（いつ・いくらの見込みか）`。貢献の合計が売上目標に届くまで対話を止めない。記法の正本は `references/output-formats.md`。
- **行動と成果をグループで結ぶ**: 行動目標は `### → XXX：{要約}（{貢献額}円）` の見出しでグループ化し、その配下に `- [ ]` を並べる。`XXX` は成果目標セクションに実在する項目で、見出しの `{貢献額}` はその成果目標の貢献額と一致させる。習慣・土台のみ `### → （土台）`／`### → （関係維持）` 可。貢献額の大きいグループを上に置く並び順は推奨（優先順位が見えるため。機械検査はしない）。
- **シンプルに書く（1項目=1つのこと）**: 成果目標は5件・1項目50字まで、行動目標は8件・1項目60字まで。`・` で複数の成果を1項目に詰め込まない。長くなったら短縮でなく2件に割る。背景・理由は `→ 【考え】`／`→ 【思い】` の注記行へ寄せ、目標本文には入れない。
- **数値は半角のみ**（「万円」不可 → `600000`）。差分は必ず `+`/`-` 付き（例 `-300000`, `+2`）。行動目標には期日と数値を含める。
- **関係構築が軸**: 売上目標を「追う」のでなく「人との関係を育む」を先に置く。売上は関係の結果。
- **ファイルは3本・月報だけ1ファイル2セクション**: 提出用の別ファイルを作らない（**理由: 複数ファイルにまたがると改善・修正のときに反映漏れが起きる**。片方だけ直して他方が古いまま残る形を作らない。見やすさを理由に2本へ戻さない）。月報は1ファイルの中で `# 北原さん提出用（シンプル）` → `# 管理用（詳細）` の順に分け、**提出用セクションの `## 【…】` には閉じ括弧の内側に「（提出）」を付ける**（例 `## 【今月の売上目標（提出）】`）。週報・期報は詳細のみ。既存の `（提出）` 付きファイルは削除せず `05_Project/UBM/目標設定/archive/` へ分離する。
- **出力の内容規則の正本**: `references/output-formats.md`。**本スキルは実行手順であって内容規則の本文は持たない。正本と矛盾した場合は正本が勝つ。** Phase3 に入る前に該当節を `Read` で読む。
  - 三層分離の定義・判定順・数の単位 → 「売上目標・成果目標・行動目標の三層分離」／行動目標の動詞 → 「行動目標の動詞（この語で書く／この語で書かない）」／採否基準 → 「行動目標に何を載せるかの採否基準」／成果→行動の粒度 → 「成果→行動の完全な落とし込み」／一本筋の記法（グループ見出し）と項目名の一致・成果1件に行動1つ以上 → 「分離の実装ルール」／並び順と期日の逆算 → 「行動目標の並び順と期日の逆算」／提出用セクションの粒度 → 「提出用セクションの粒度（シンプルな構成）」／「シンプル＝項目を削ることではない」と両セクション同値 → 「月報は1ファイルの中で提出用セクションと管理用セクションに分ける」／行動差分の書き方 → 「差分セクション」／未達の挽回3点骨格 → 「要因分析セクション」／継続売上と単発の分離・最重要数字 → 「継続売上と単発を混ぜない」
  - 一本筋の照合は IN2 を参照。月報は**管理用セクションだけ**を照合する（提出用グループは `SKIP`）。
- **精神論 NG**: 「頑張る」「意識する」「気をつける」は行動目標として不可 → 具体化（誰に・何を・いつまで・何件）を要求。
- **やらないこと3項目以上** + 判断基準1文で迷いを排除する。出力先は種別依存（月報・期報＝独立セクション必須／週報＝該当日の到達ラインの子タスクへ組み込み）。
- **合宿（アカデミー）整合**: 直近の合宿アドバイスと目標の方向性のズレを検出したら即軌道修正。
- **プロジェクト別タスク**: 週報=任意 / 月報=必須 / 期報=禁止。`- [ ] [期日] [提出先・宛先] 対象物・行動` のチェックリスト形式・2階層まで・先方担当者付き。
- **選択と集中の1点収束**: 目標が「人・お金・時間・場所・やること」の5要素で1点に収束しているかを検査し、中途半端が混ざっていたら差し戻す。判断基準は `references/selection-focus-goal-frame.md`（見出し構造は変更しない・対話側の検査基準のみ）。
- **ポジティブ事故を起こさない**: 支出を伴う行動目標は「そもそもかけない → 回収してから実行 → かけてから回収」の順で検討させ、最後の手段を採る場合は回収条件と期限を明記させる。
- **思考法駆動**: 質問の形で自然に思考法を適用し、名前は出さない。北原さんの原則引用は1対話あたり1〜2回まで。

## つまずきやすい点

- **出力ファイル命名**: 週報 `UBM - 1-週報 - {期間}.md` / 月報 `UBM - 2-月報（１ヶ月） - {期間}.md` / 期報 `UBM - 3-月報（３ヶ月） - {期間}.md`（`{期間}` は `YYYY-MM-DD〜YYYY-MM-DD`）の3本のみ。`（提出）` 付きのファイル名は新規作成しない。旧名 `UBM - 3-月報（２ヶ月） - …` と `UBM - 3-期報 - …` は読み取り・過去参照では受理し続ける（新規作成では使わない）。
- **「（提出）」は `validate-goal-output.py` を通すための規約**: 重複見出し検査は `## 【…】` 行の**完全一致**で数えるため、`## 【今月の売上目標（提出）】` は `## 【今月の売上目標】` と衝突しない。必須見出し検査も完全一致なので管理用セクション側で満たす。したがって**管理用セクションの見出しには文字を足さない**（素の `## 【今月の売上目標】` のまま。「（管理）」等を足すと必須見出しが満たされず不合格）。`## 【今月の行動目標（提出）】` はグループ見出しを持たない1行1行動なので、所属の検査（C4/C5）と件数の上限（S3）から外れる。行動目標系の検査（NG表現は不合格 / 数値・期日・固有名詞は警告）は見出しの部分一致で両セクションを1プールにするため、提出用セクションにも精神論を書かない（固有名詞の警告は管理用セクション側で満たされる）。
- **三層のズレの直し方**: 層をまたぐ値の照合は IN3 を参照。IN1 の `--peer` は3アンカーしか見ないので、IN3 の代わりにならない。ズレが見つかったら**期報を先に直し、そこから月報・週報へ降ろす。下から上へは直さない。**
- **経緯の記述を現在値と読み違える**: 「以前は500,000だった」のような履歴は【仮置き事項】【衝突】【確定済み・解消済みの記録】【来月以降に対応すること】の中に置く。アンカーの節の本文に混ぜると、人も検査スクリプトも現在値として読む（`validate-cross-level.py` はこれらの節を抽出範囲から外している）。
- **ファイル名に全角カッコ付き期間表記を本文へ書かない**: 本文で他ファイルを参照するときは `（１ヶ月）`・`（３ヶ月）` を含むファイル名を引用せず期間表記で書く（`validate-goal-output.py` の全角数字チェックで rc=1 になる）。
- **期報の期間**: UBM の目標期間は月の最終月曜日起点。期報は対象3ヶ月分の月報期間の連結で、開始日=1ヶ月目の月報開始日 / 終了日=3ヶ月目の月報終了日（例: 7月・8月・9月分 → `2026-06-29〜2026-09-27`）。期報は月報3件をロールアップして作る。
- **保存先**: `$UBM_VAULT_ROOT/05_Project/UBM/目標設定/` のみ（`UBM_VAULT_ROOT` 未設定時は保存を停止）。
- **Daily.md 更新（Phase6）**: `$UBM_VAULT_ROOT/02_Configs/Templates/Daily.md` の該当する埋め込み行だけを正規表現で検出・置換し、他部分は一切変更しない。サマリー見出し（`【1週間の目標】`/`【1ヶ月の目標】`/`【3ヶ月の目標】`）は継続語彙で凍結（今週/今月/今期へ改名しない）。
- **期報の正本**: `references/output-formats.md` の静的規則を A1 優先で正本化し、動的学習はスタイル参照に限定（見出し集合を上書きしない）。
- **書き込み保護**: `ubm-write-path-guard` フックは、`UBM_VAULT_ROOT` 配下の許可範囲外への Write|Edit|MultiEdit を止める。判定できない呼び出し（フックへの入力 JSON が読めない・書き込み先のパスが無い）も通さずに止める（不明なら止める）。フックの許可範囲の正本はプラグイン直下 `hooks/ubm-write-path-guard.py` の `ALLOWED_PREFIXES` / `ALLOWED_EXACT` で、`05_Project/` 全体・`02_Configs/Daily/` なども含み、本スキルの書き込み範囲より広い。本スキルが書くのは `05_Project/UBM/目標設定/`（`archive/` を含む）と Daily.md の埋め込み行だけで、その境界はフックではなく本スキルの規則が守る。vault 外のプラグイン同梱データは保護対象外。

## 関連資料

- **エージェント**: `info-collector` / `goal-reviewer` / `phase3-coordinator` / `output-formatter`（プラグイン直下の `agents/`。`phase3-coordinator` は必要なときに `prompts/R1-R5` を `Read` で読んで次の質問案だけを返し、ユーザーとの対話と状態の更新は親が行う）。
- **プロンプト**: `prompts/R{1..5}-<slug>.md` — Phase3 の対話 Step1-5 を責務ごとに分けた 7 層プロンプトの正本（`prompt-placement-convention` に従う。`verify-completeness.py` で 7 層と `l5-contract` を検証する）。
- **スクリプト**: `scripts/validate-goal-output.py`（出力の検証・決定論的なゲート）/ `scripts/validate-goal-linkage.py`（一本筋の両方向の照合。照合規則は `validate-goal-output.py` と共用。rc=0/1/2/3。受け入れテストはプラグイン直下の `../../tests/test_validate_goal_linkage.py`）/ `scripts/validate-cross-level.py`（期報・月報・週報の期アンカー8種の横断照合。rc=0/1/2/3。受け入れテストはプラグイン直下の `../../tests/test_validate_cross_level.py`）/ `../../scripts/validate-inline-goal-seek-anchor.py`（プラグイン直下。インラインのゴールシークの進捗ファイル・中間ファイルのアンカーを検証し、不備なら止める）。
- **参照資料**: `references/selection-focus-goal-frame.md`（北原さん 2026-08-12 コメント由来の選択と集中フレーム・期間別検査・運用カレンダー）/ `references/thinking-guide.md`（思考法）/ `references/output-formats.md`（テンプレートの公式21ブロック・提出用/管理用セクションの粒度・三層分離・行動目標の採否基準・一本筋・継続売上と単発の分離の単一正本）/ `references/data-contract.md`（各 Phase の間の入出力）/ `references/thinking-methods-toolkit.md` / `references/thinking-process.md` / `references/version-history.md` / `references/resource-map.yaml`（資源一覧の機械可読正本）。
- **付属資料**: `assets/execution-prompts.md`（フロー参照）/ `assets/interview-quick-templates.md` / `assets/action-goals-best-practices.md` / `assets/golden-sample-weekly.md`（手本として示す例）。
- **ナレッジ**: プラグイン直下の `knowledge/`（`router.json` → `*.json` の順に `info-collector` がデュアルパス検索する。L1 の精選済みナレッジをプラグインに同梱しているので、新規インストールの直後から使える）。
