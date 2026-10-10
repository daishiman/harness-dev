---
name: run-ubm-journal
description: 日次ジャーナルを作りたいとき、今日やったことを会話で振り返りながら Obsidian の Daily へ構造化したファイルを生成・再生成したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[YYYY-MM-DD]"
arguments: [date]
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
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: harness-maintainers
since: 2026-08-17
version: 0.6.0
responsibility_refs:
  - scripts/build-journal-context.py
  - ../../agents/journal-composer.md
  - scripts/validate-journal-output.py
subagent_refs:
  - journal-composer
schema_refs:
  - references/output-format.md
script_refs:
  - ../../scripts/evaluate-design-rubric.py
  - ../../scripts/search-knowledge.py
  - ../../scripts/record-knowledge-usage.py
  - ../../scripts/publish-staged-files.py
  - scripts/build-journal-context.py
  - scripts/validate-journal-output.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
domain: ubm-goal-setting
rubric_refs:
  - ../run-ubm-knowledge-sync/references/rubric.json
reference_refs:
  - ../../references/content-review-rubric.md
  - ../../references/knowledge-retrieval-contract.md
  - ../../references/guarded-publication-contract.md
  - references/resource-map.yaml
  - references/output-format.md
  - references/interview-map.md
  - references/daily-habits.json
  - references/principle-checklist.md
  - ../../references/goal-seek-anchor-contract.md
  - ../../references/agent-root-contract.md
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  progress: eval-log/ubm-goal-setting/run-ubm-journal/goal-seek-progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-journal/run-ubm-journal-intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-journal/handoff-run-ubm-journal.json
  max_loops: 3
source: ユーザーの既存 Obsidian Daily 運用 (02_Configs/Daily/) の仕組み化
source-tier: internal
last-audited: 2026-08-17
audit-trigger: quarterly
completeness_exempt:
  - "manifest: コンテキストの生成 (build-journal-context.py) → 整形 (サブエージェント journal-composer) → 検証 (validate-journal-output.py) の一本道で、分岐も並列も再入も無い。workflow-manifest.json を置いても Phase の遷移の正本が SKILL.md 本文と二重になるだけで、片方が古びる (二重定義禁止 [[project_ssot_dedup_mechanism]])。実行体の対応は responsibility_refs が持ち、正式保存は親の external_mutation_guard execute が担う。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-journal-output.py が一時下書きと保存後のDailyファイルで REQUIRED_OUTLINE・目標4階層・3ジャーナル×3小節・未置換プレースホルダを検証し違反0件であることを確認する。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: 通し番号は build-journal-context.py の journal_number をそのまま使い、LLM が推測した番号を書かないことを --expected-number 照合で確認する。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 実際の対話でジャーナルを生成し、ユーザーが語った固有名詞・数値・時刻が欠落せず該当セクションへ振り分けられていることを受入テストが確認する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: run-skill-live-trial で対話を実走し、Phase0 の文脈解決から Phase1-3 のヒアリング、Phase4 整形、Phase5 検証の合格までを自走完遂して Daily 配下にジャーナルが実生成されることを実行証拠で確認する。
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
runtime_root_policy: host-skill-path
---

# run-ubm-journal

その日の振り返りを会話で行い、`$UBM_VAULT_ROOT/02_Configs/Daily/{YYYY-MM-DD}.md` へ構造化された
日次ジャーナルを生成する。チェックリストを読み上げるのではなく、「今日は何をやりましたか」から
自然に会話を進め、返ってきた話をジャーナルの各セクションへ振り分ける。

## 目的と出力契約

**禁則**: 未検証の下書きを Daily に正式保存しない。正本の保存前・保存後の検査を通す。

- **ゴール**: 対象日のジャーナル1件が `references/output-format.md` の骨格で生成され、
  `validate-journal-output.py` が合格（PASS）した状態。
- **出力契約**: `02_Configs/Daily/{YYYY-MM-DD}.md` 1ファイル + 合格か不合格（FAIL）かを示す検証結果。
- **境界**: 入力=前回ジャーナル / 最新の週報・月報・期報 / 対話回答。出力=日次ジャーナル1件のみ。
  週報・月報・期報そのものの更新は `run-ubm-goal-setting` へ委譲する（このスキルは読むだけ）。
- **フォーマットは器であって目的ではない**: テンプレートの穴埋めではなく、その日やったことを
  構造的にまとめることが目的。分類見出しはその日の実態に合わせて命名してよい。

<!-- runtime-root-contract:v1 -->
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
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

| 段階 | 責務 | 実行体 |
|---|---|---|
| Phase0-resolve | 対象日を確定し `build-journal-context.py` で番号・目標4階層・週報引き継ぎ・`warnings` を取得 | 本スキル（Bash） |
| Phase1-open | 「今日は何をやりましたか」で対話を開き、事実を出しきる | 本スキル |
| Phase2-deepen | 気づき・うまくいかなかったこと・時間の使い方・お金の動きを掘る | 本スキル |
| Phase3-fill | 埋まっていない枠（感謝・禁止事項・タスク）と**未確認の固定習慣**を、週報の呼び水を使って補う | 本スキル |
| Phase4-compose | 収集内容を骨格へ整形し Markdown を組み立てる | `journal-composer`（Task） |
| Phase5-validate | エージェントが一時下書きを検証し、親が中央guard executeで正式保存して再検証 | `journal-composer`（下書き）+ 本スキル（正式保存）+ 検査スクリプト |

**所要時間目安**: 5〜10分。

## Phase0: 文脈解決（必ず最初に実行する）

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-journal/scripts/build-journal-context.py" \
  --vault-root "$UBM_VAULT_ROOT" --date "{YYYY-MM-DD}"
```

- 対象日は引数 `$ARGUMENTS` があればそれ、無ければ **今日**（ファイル日付＝見出し日付＝振り返る日）。
- `journal_number` をそのまま使う。**番号を自分で数えない・推測しない。**
- `warnings` は対話の切り口として使う（例: 1年目標の期間満了、期報の期間ズレ、当日タスク未検出）。
- `existing_file.write_mode` を**必ず先に見る**。ジャーナルは Write で全置換されるため、
  ここを飛ばすと利用者の既存ファイルが消える。
  - `new`: そのまま新規作成して進む。
  - `regenerate`: 同じ日のジャーナルを作り直す。番号を維持し、更新であることを伝えてから進む。
  - `blocked`: **Write せず停止する。** 対象ファイルに別日の内容が入っている。
    どうするか（別名で作る／既存を退避する／中止する）を必ずユーザーへ確認してから動く。

## Phase1-3: 対話

`references/interview-map.md` の問い→セクション対応表に沿って進める。

- **開き方**: 「今日は何をやりましたか？」。列挙が出たら、時間をかけた順・人が関わった順に掘る。
- **翌日以降の視点**: 「昨日やったことで気づいたことはありますか？」で効果性の材料を取る。
- **週報の呼び水**: `weekly_report.day_tasks` を「今日はこれが入っていましたが、どうなりましたか？」
  の形で提示する。丸ごと転記はしない。
- **固定習慣（毎日必須）**: Phase0の `daily_habits` を `references/interview-map.md` の「習慣の引き出し」に従って確認する。問いと書く先は `daily-habits.json` の値を使い、項目を本文へ写して再定義しない。
- **週次習慣目標**: 週報の習慣目標4群は独立セクションにせず、会話から達成状況を推し量って
  行動・時間・お金の各ジャーナルへ事実として織り込む（`references/interview-map.md` 参照）。
- **目標セクションだけは自動**: 1年/3ヶ月/1ヶ月/1週間目標と残日数は Phase0 の結果をそのまま使い、
  ユーザーに確認を求めない。ただし `warnings` に期間ズレ・満了があるときだけ確認する。

## Phase4-5: 整形と検証

- Taskのルート入力と停止条件は `../../references/agent-root-contract.md` が正本。`journal-composer` へ Phase0 のコンテキストJSON、対話内容、親が `host-skill-path` から解決した絶対パスの `PLUGIN_ROOT`、保存可否を渡す。整形・一時下書きの検証・最大3回の修復は同エージェントだけが担う。正式保存と保存後検査は親が担う。親は対話・保存可否・入力スナップショットを持つ。`PLUGIN_ROOT` が未指定か絶対パスでなければ書き込み前に停止する。
- 下書きの絶対パスはエージェントが `Bash` の `tempfile.mkdtemp(prefix="ubm-journal-")` で実行専用ディレクトリを一度作り、その中の `{YYYY-MM-DD}.md` として解決する。この観測値を `Write` と検証の `--file` に同じ値で渡す。シェル変数を含む文字列を `Write` に渡さない。保存の手順と返す受領書は `../../agents/journal-composer.md` の「出力と検証」が正本。
- 下書きが0なら親が正式保存の契約でmanifestを作り、ユーザー確認と受領書を取得して中央executeから保存する。保存後には次を実行する。親は同じファイルを再編集せず、下書きと保存後の受領書の終了コード 0、保存先・期待番号・期待日付の一致で完了を判定する:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-journal/scripts/validate-journal-output.py" \
  --file "$UBM_VAULT_ROOT/02_Configs/Daily/{YYYY-MM-DD}.md" \
  --expected-number {journal_number} --expected-date {YYYY-MM-DD}
```

- 下書きの終了コード 1 は違反コードに従って最大3回修復する。収束しなければ下書きに残件を保持して停止し、Dailyは変更しない。終了コード 2 は読込不能・引数不正なので内容を修正せず、対象パスと標準エラーを親へ返す。保存後が0以外なら完了にせず、保存先と検査結果を返す。保存後の自動再編集はしない。

## ゴールシーク実行

`goal_seek.engine: inline` / `fork: inline` とし、ユーザーとの対話と保存可否は親コンテキストが持つ。`journal-composer` は Phase4-5 の一時下書きだけの書き手と検証役を `Task` で担い、親は受領書で完了を判定する。最大3周で未達なら残件を `open_issues` と引き継ぎファイル（`goal_seek.handoff`）に記録し、完了扱いにしない。

親の 1 周回の実体は **Phase1-3 の対話へ戻って不足を埋め、`journal-composer` を Phase4-5 へ再委譲すること**である。周回の発火条件は「保存されたジャーナルが `original_goal` に対して不足している」と親コンテキストが判断した場合に限る (例: 事実・数値・固有名詞の取りこぼし、当日の意思決定が言語化されていない)。周回ごとに `intermediate.jsonl` へ 1 行追記し、`iteration` を進める。

`journal-composer` の中の最大3回は一時下書きの機械違反の修復であり、親のゴールシークの周回とは別である。3回で収束しなければ親がPhase4を自動再起動せず、周回を消費しないまま停止し、違反コードをユーザーへ報告する。

### ゴールシーク配線

`original_goal` と対象日を進捗ファイル（`goal_seek.progress`）に固定し、各反復を `run-ubm-journal-intermediate.jsonl` へ追記する。各行は `iteration/original_goal/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal` を持ち、ジャーナルのパスと検査スクリプトの受領書は結果の観測値として併記する。次回は直前の `merged_directive_for_next` を必須入力とする。

### ゴールシーク検証

アンカーの固定・必須キー・検査範囲・終了コードは `../../references/goal-seek-anchor-contract.md` が正本。進捗と中間ファイルの絶対パスを呼出元のプロジェクトルートから解決して、以下を実行する。ジャーナルの本文・番号・日付は Phase5 の検査スクリプト、保存先と受領書の対応は親が検査する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "{resolved_progress_path}" "{resolved_intermediate_path}"
```

## 守ること

- **番号は決定論**: `journal_number` はスクリプト値のみ。同日再生成時は番号を維持する。
- **日付3点一致**: ファイル名の日付・見出しの日付・振り返る対象日は常に同じ。
- **数値は半角**: 「25万円」ではなく `250,000`。件数・日数・時刻も具体値で書く。
- **精神論を書かない**: 「頑張る」「意識する」は打ち手として不可 → 誰に・何を・いつまで・何件 へ。
- **要約しすぎない**: ユーザーが出した固有名詞・数値・時刻・相手の発言はそのまま残す。
  1項目1事実に分解し、冗長な言い回しだけを削る。
- **3小節を混ぜない**: 「現状を確認する」に評価や改善案を書かない。事実／解釈／打ち手を分離する。
- **継承値は書き換えない**: 人生の究極目的・フェーズ別課題チェックシート・原理原則チェックシートは
  前回から引き継ぎ、ユーザーが変更を申し出た項目だけ更新する。
- **原理原則チェックシート**: `references/principle-checklist.md` の「出力規則」に従う。対話へ追加する質問ではなく、Phase4で継承する器として扱う。

## つまずきやすい点

- **保存先の書き込み許可**: `ubm-write-path-guard` フックは vault 配下の `02_Configs/` のうち、`02_Configs/Daily/` と
  `02_Configs/Templates/Daily.md`（完全一致）への書き込みを許し、それ以外の `02_Configs/` 配下は止める。
  一方、本スキルが書くのは `02_Configs/Daily/{YYYY-MM-DD}.md` だけで、`Templates/Daily.md` は書かない
  （それを更新するのは `run-ubm-goal-setting` の Phase6）。この線引きはフックではなく本スキルの規則が守る。
- **`UBM_VAULT_ROOT` 未設定**: Phase0 が終了コード 2 で終わる。vault のパスをユーザーに確認してから再実行する。
  Phase0 の終了コード 2 は「引数不正・vault 解決不能・`Daily` ディレクトリ不在・daily-habits.json 破損」の総称なので、
  標準エラー出力の 1 行目を必ず読んでから対処すること。
- **週報が当日を含まない**: 週をまたいだ直後は直近週報を参照する（`covers_target: false` の警告）。
  1週間目標の残日数は `0日（期間終了・次週分の週報は未作成）` と書く。
- **1年目標の対応レポートは存在しない**: 前回ジャーナルからの継承のみ。満了していたら対話で確認する。
- **フェーズ別課題チェックシートは本文の外**: `## 【お金のジャーナル】` の後、レベル1見出しとして置く。
- **チェックシート2種を取り違えない**: `# フェーズ別 課題チェックシート`（0→1 / 1→10 / 10→100）と
  `# 原理原則 チェックシート`（11 設問）は別ブロックで、どちらも `- [ ]` の塊なので見た目では区別できない。
  順序・継承・区切りの規則は `references/principle-checklist.md` の「出力規則」を参照する。

## 関連資料

- **スクリプト**: `scripts/build-journal-context.py`（番号・目標・週報引き継ぎの決定論解決）/
  `scripts/validate-journal-output.py`（下書きと保存後の検証）。
- **参照資料**: `references/resource-map.yaml`（どの Phase でどれを開くかの索引。迷ったら最初に見る）/
  `references/output-format.md`（骨格の正本）/ `references/interview-map.md`（問い→セクション対応）/
  `references/daily-habits.json`（毎日固定の習慣6項目の正本。項目を増減するときはここだけを編集し、
  `keywords` と `search_scopes`（H01 が検査するセクション）を必ず併記する。`search_scopes` を
  書き忘れた習慣は検査不能として H02 違反になる）/
  `references/principle-checklist.md`（「テンプレート（未チェック状態）」と「出力規則」の正本。
  設問の変更手順は `references/output-format.md` 冒頭の契約を参照する）。
- **付属資料**: `assets/golden-sample.md`（検査スクリプトに合格する見本 / 例示（few-shot））。
- **エージェント**: `journal-composer`（プラグイン直下の `agents/`）。
