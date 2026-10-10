---
name: run-ubm-knowledge-sync
description: 北原さん式ナレッジソースを同期する。差分を検知したいとき、6カテゴリへ分類・格納したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--all] [--since YYYY-MM-DD] [--dry-run]"
arguments: [all, since, dry-run]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
kind: run
prefix: run
effect: external-mutation
runtime_root_policy: host-skill-path
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: harness-maintainers
since: 2026-07-04
version: 0.1.0
manifest: workflow-manifest.json
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: task-graph
  engine_profile: checklist-graph
  full_task_spec_graph: false
  fork: inline
  progress: eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-knowledge-sync/run-ubm-knowledge-sync-intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-knowledge-sync/handoff-run-ubm-knowledge-sync.json
  max_loops: 9
responsibility_refs:
  - scripts/detect-knowledge-updates.py
  - ../../agents/knowledge-extractor.md
  - scripts/check-knowledge-split.py
subagent_refs:
  - knowledge-extractor
  - knowledge-relation-extractor
schema_refs:
  - ../../knowledge/schema.json
knowledge_loop:
  pattern: router-registry
  index: ../../knowledge/router.json
  consult_at: [runtime]
script_refs:
  - ../../scripts/evaluate-design-rubric.py
  - ../../scripts/search-knowledge.py
  - ../../scripts/record-knowledge-usage.py
  - ../../scripts/publish-staged-files.py
  - scripts/detect-knowledge-updates.py
  - scripts/check-knowledge-split.py
  - scripts/extract-ready-set-from-checklist.py
  - scripts/build-self-reflection-entry.py
  - scripts/extract-capability-dependency-graph.py
  - scripts/build-capability-graph-knowledge-entry.py
  - scripts/validate-knowledge-sync-task-graph.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
  - ../../scripts/validate-knowledge-graph.py
domain: ubm-goal-setting
rubric_refs:
  - ../run-ubm-knowledge-sync/references/rubric.json
reference_refs:
  - ../../references/content-review-rubric.md
  - ../../references/knowledge-retrieval-contract.md
  - ../../references/guarded-publication-contract.md
  - ../../references/goal-seek-anchor-contract.md
  - ../../references/agent-root-contract.md
  - references/knowledge-sources.md
  - references/knowledge-design-principles.md
source: ObsidianMemo vault (.claude/commands/ai/ubm-knowledge-sync) の移植
source-tier: internal
last-audited: 2026-07-04
audit-trigger: quarterly
completeness_exempt:
  - "prompts: このスキルでサブエージェントの LLM に任せる仕事は、抽出と6カテゴリへの分類（Phase2・Phase3）と、関係の辺の候補の生成（Phase5）の2つである。前者はプラグイン直下の knowledge-extractor.md（7層プロンプトを本文に含む）、後者は knowledge-relation-extractor.md（同じく7層プロンプトを本文に含む・読み取り専用）が受け持つ。検知・分割の検査・グラフの検証は決定論スクリプト（detect-knowledge-updates.py / check-knowledge-split.py / validate-knowledge-graph.py）が受け持ち、バッチの制御と最終レポートは親コンテキストが本文の手順どおりに行う。スキル内に R-id ごとの prompts を置くと、サブエージェントの本文と二重に定義することになるので置かない（二重定義の禁止 [[project_ssot_dedup_mechanism]]）。仕事と実行体の対応は、本文の「全体の流れ」の表を正本とする。（prompts/ ディレクトリは置かない。この免除の宣言と実際の配置は一致している）"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: detect-knowledge-updates.py が registry.json との MD5 照合で NEW/MODIFIED ソースを漏れなく検知することをスクリプトで確認する。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 既知の更新済みソースを投入し knowledge-extractor が6カテゴリへ正しく分類し router.json/registry.json が同期完了することを受入テストが確認する。
      verify_by: test
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

# run-ubm-knowledge-sync

UBM のナレッジソース（YouTube の議事録・合宿の記録・月報へのフィードバック・セミナーなど）について、新しく追加されたものと更新された差分を見つけ、**内容別の JSON ファイル**（6カテゴリ）に反映する。北原さんの最新の教えを続けて取り込み、`run-ubm-goal-setting` の品質を底上げする。

## 目的と出力契約

**禁則**: ユーザーの記録を北原さんのナレッジへ混ぜない。未検証の変更を正式ナレッジへ反映しない。

- **ゴール**: ナレッジソースの追加と変更の差分が `registry.json` との照合で見つかり、`knowledge-extractor` による6カテゴリへの分類と `router.json` の更新まで、ナレッジの同期が終わった状態。
- **出力契約**: 検知・抽出・分割・グラフ検証の結果の報告（NEW/MODIFIED の件数・格納先・分割の要否・グラフの状態）。あわせて `knowledge/*.json` を更新し、`router.json`/`registry.json`/`sync-log.jsonl` に追記し、差分があるときは `knowledge-relations.json`/`knowledge-graph.json` を作り直す。
- **境界**: vault 内のナレッジソースは読み取り専用の入力とする。書き込み先は、確認済みの対象範囲（ガードの `--target-scope`）にある `PLUGIN_ROOT/knowledge/`、同じスキルの `assets/kitahara-principles-db.md`、`PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/` だけ。それ以外の場所と、シンボリックリンクを通って範囲の外へ出る場所は、書き込む前に止める。目標設定の対話は `run-ubm-goal-setting` に委譲する。
- **6カテゴリ**: `principles`（原則）/ `consultation`（相談）/ `phase-advice`（フェーズ）/ `action-guides`（行動）/ `mindset`（転換）/ `case-studies`（事例）。
- **必須禁則**: `--dry-run` のときは、プラグインのナレッジも vault も書き換えない。外部変更は、正規の受領書の手順の外では実行しない。

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
| Phase1-detect | `detect-knowledge-updates.py` が `registry.json` と MD5 で照合し、NEW/MODIFIED のソースを漏れなく見つける。利用者自身の記録（`05_Project/UBM/目標設定/`・`05_Project/UBM/挑戦宣言/`）は、スクリプトが検知の段階で除く（除外の正本は同スクリプトの `EXCLUDED_SUBDIRS`）。出力をそのまま Phase2 の入力にする | スクリプト |
| Phase2-extract | このスキルが NEW/MODIFIED を最大20ファイルずつのバッチに分ける。各バッチで `knowledge-extractor` が親の一時knowledge_dirで6カテゴリへ分類しRule A-Fを適用する。親が検証済み差分を中央guard executeで正式保存する | このスキル（バッチの制御）+ `knowledge-extractor`（Task） |
| Phase3-split-check | `check-knowledge-split.py` が、ナレッジ JSON が500行の上限を超えていないかを機械的に検査する。`knowledge-extractor` は、25エントリを超えたときの意味のまとまりでの分割を終え、コーパスを確定する | スクリプト / `knowledge-extractor`（必要なときの Task） |
| Phase5-graph-sync（Phase3 の完了後） | 確定したコーパスについて、`knowledge-relation-extractor` が根拠付きの向きのある辺の**候補 JSON** を読み取り専用で返す（`knowledge/` へは書き込まない。幻覚を防ぐため）。呼び出し側は候補を `eval-log/` にファイルとして書き出す。`validate-knowledge-graph.py --merge-relations` が、正規のキー（`source_id`・`target_id`・`relation_type`）で `knowledge/knowledge-relations.json` へ冪等に統合する（既存の辺は残し、先に書いたものを優先する）。すべての検証に合格（PASS）したあとで、`knowledge-relations.json`→`knowledge-graph.json` の順に正規の書き込みをする。途中で書き込みに失敗したら、同じ候補で再実行して冪等に直す（2つのファイルにまたがる不可分性は主張しない）。試し実行（`--dry-run`）のときは書き込みを禁止する | `knowledge-relation-extractor`（Task）/ `validate-knowledge-graph.py --merge-relations`（スクリプト） |
| Phase4-report（Phase5 の完了後） | 検知・抽出・分割・グラフ同期の結果（NEW/MODIFIED の件数・格納先・分割の要否・グラフの検証）を最終報告にまとめる | このスキル |

Phase5 は差分のエントリをきっかけに動くので、**差分がゼロの周回では動かない**。既存のコーパスに辺が一度も付いていない場合（`knowledge-relations.json` が無く、`edges=0` の退化したグラフ）の初回の適用には、RUNBOOK（プラグイン直下の `RUNBOOK.md`）の「辺の過去分の初回埋め戻し」の手順を使う。

各 Task のルートと停止条件は `../../references/agent-root-contract.md` が正本。`knowledge-extractor` には Phase1 の検知行をそのまま target_files とし、NEW は mode=new、MODIFIED は mode=update に分け、解決済み plugin_root と source_root（Phase1 の --sources）を渡す。--all のときだけ mode=full を使う。relation-extractor には plugin_root と knowledge_dir=plugin_root/knowledge を渡す。--dry-run ではこれらの書き手/統合を起動しない。

## ゴールシーク実行

`goal_seek.engine: task-graph` / `engine_profile: checklist-graph` / `fork: inline` を使う。同じコーパスを更新したり読んだりする仕事を、安全な依存順 `Phase1 → Phase2 → Phase3 → Phase5 → Phase4` で1件ずつ消費する。これはチェックリストを縮めた有向非巡回グラフであり、計画づくりのスキルが作る完全なタスク仕様のグラフではない（`full_task_spec_graph: false`）。

### 完了チェックリスト

- [ ] C1: Phase1-detect を実行し、差分の一覧か、差分が0件だという証跡を得る (`depends_on: []`, `verify_by: script`)
- [ ] C2: Phase2-extract を終える。試し実行か差分0件なら、条件を満たさないことを記録し、何もせずに完了とする (`depends_on: [C1]`, `verify_by: reasoning`)
- [ ] C3: Phase3-split-check を終え、後の段階が読むコーパスを確定する。試し実行なら書き込みを禁止し、何もせずに完了とする (`depends_on: [C2]`, `verify_by: script`)
- [ ] C4: 確定したコーパスに対して Phase5-graph-sync を終える。試し実行か差分0件なら、何もしなかった根拠を残す (`depends_on: [C3]`, `verify_by: script`)
- [ ] C5: Phase4-report に、C1〜C4 の結果、飛ばした理由、未解決の事項をまとめる (`depends_on: [C4]`, `verify_by: reasoning`)
- [ ] C6: `task-graph` の消費の検証と Anchor の検証がどちらも終了コード 0 で、pending/blocked が残っていない (`depends_on: [C5]`, `verify_by: script`)

### ゴールシーク配線

- `goal_seek.progress`（進捗ファイル）: 最初に、上の C1〜C6 を `{id,text,status:"pending",depends_on,verify_by}` の形で `eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json` に記録する。最上位には `engine:"task-graph"`、`iteration`、`open_issues`、`status`、`max_loops:9` を置く。 `goal_seek.intermediate`（中間ファイル）: 各周回の終わりの Anchor Step で、`run-ubm-knowledge-sync-intermediate.jsonl` に `original_goal` / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` と、その周回の `ready_set` / `selected_item` を、追記だけで残す。 `goal_seek.handoff`（引き継ぎファイル）: 完了したときに、検知した件数、更新先、分割の検査とグラフ検証の結果、試し実行かどうか、未解決の課題を `handoff-run-ubm-knowledge-sync.json` に書く。
- ループ、実行できる項目の集合（`ready_set`）の計算、外部変更のガード、ユーザーへの確認、進捗ファイルへの書き込みは、親コンテキストが受け持つ。Phase2 の抽出と Phase5 の関係候補の生成だけを、それぞれ `knowledge-extractor` / `knowledge-relation-extractor` に `Task` で委譲する。各サブエージェントは、自分が受け持つ構成要素（スキル・コマンド・エージェント・フック・スクリプトの単位）の成果だけを返す。各 Task input には親が host-skill-path から解決した absolute `PLUGIN_ROOT` を明示する。Phase2には親がコピーした一時knowledge_dirも必須で渡し、Taskは正式knowledge/へ書かない。サブエージェントは、これが指定されていないか絶対パスでないなら、書き込む前に止まる。preview 後の exact reply は親が受ける。確認の受領書を得たら、同じ周回の `authorize`→`execute` を再開する。
- 各周回では `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-knowledge-sync/scripts/extract-ready-set-from-checklist.py" "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json"` で、絞り込む前の実行できる項目の集合を求める。実際に使う `ready_set` は、そこから次の2種類を除いた集合とする。(a) `C6` 以外の項目がまだ1件でも消費されていないときの、最後の完了ゲートである `C6`。(b) `available_from_iteration` が今の周回番号より後の追記項目（まだ有効になっていないもの）。除いたあとで、いちばん小さい ID だけを選ぶ。この2条件は、`validate-knowledge-sync-task-graph.py` が実行できる項目の集合を計算し直すときの条件と同じである。片方だけを使うと検査スクリプトと食い違い、その周回は不合格（FAIL）になる。実行したか、条件付きで何もしなかった根拠を残し、その項目を `done` にしてから計算し直す。実行中に必須の追加作業を見つけたときだけ、同じスキルの `build-self-reflection-entry.py` で、同じチェックリストの末尾に項目を追記する。この項目は `C7` 以降の id と、実際に先に終わっているべき項目（`C6` 以外）への `depends_on` を持つ（別のタスクグラフの状態は作らない）。実際に使う `ready_set` が空で、後の周回から有効になる追記項目があるときは、その周回を「未選択」の実行記録として残し、`C6` を先に進めない。
- `--dry-run` のときも、C1→C2（何もしない）→C3（何もしない）→C4（何もしない）→C5 の順に選んで実行記録を残す。Phase2 の抽出、Phase3 の分割の修復、Phase5 のグラフへの書き込みは禁止する。条件を満たさない項目を「未選択」のまま残さない。
- C6 では、先に `selected_item` の実行記録を追記する。C6 を `done` にし、全体を `completed` の候補に更新してから、最後に下の検証を実行する。終了コードが 0 でなければ `completed` を確定しない。`status: handed_off` にして、違反を `open_issues` に残す。
- `max_loops` に達したときは合格とみなさない。残ったチェック項目を `open_issues` に残し、人のレビューに差し戻す。

### 依存グラフのナレッジ参照（dependency graph knowledge）

各構成要素に取りかかる前に、`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-knowledge-sync/scripts/extract-capability-dependency-graph.py" "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"` の出力を `$PROJECT_ROOT/eval-log/` の派生 JSON に保存する。通常の実行では、宙に浮いた参照も循環も無いときだけ、同じスキルの `build-capability-graph-knowledge-entry.py` にグラフのパスと `--target-knowledge-dir "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/knowledge"` を渡し、`source_ref` 付きの要約を追記または統合する。`--dry-run` では extract 結果を eval-log 内でのみ consult し、record と plugin `knowledge/` write を no-op trace にする（抽出結果は `eval-log/` の中だけで参照し、記録とプラグインの `knowledge/` への書き込みは行わずに実行記録だけを残す）。通常は `knowledge/knowledge-capability-graph.json` を参照し、依存先が終わっていないものを先に実行しない。このナレッジは実行順の状態ではなく、依存グラフから導いた派生の判断である。唯一の正となる状態は、進捗ファイルのチェックリストだけとする。

### ゴールシーク検証

Anchor Step と依存順消費を、まとめて機械的に検証する。記録が無いことも違反とみなす。`task-graph` なのに `ready_set` / `selected_item` の実行記録が無ければ失敗にする。記録された `ready_set` は信用しない。チェックリスト・過去の `selected_item`・`available_from_iteration` から、各周回の実行できる項目の全集合を計算し直す。`C6` 以外にまだ消費されていない項目がある間は、完了ゲート `C6` を実際に使う `ready_set` から除く。以下を順に実行し、両方とも終了コード 0 であることを必須とする。共通アンカーの初回固定・必須キー・検査範囲・終了コードは `../../references/goal-seek-anchor-contract.md` が正本。後者は依存順消費を検査する。この検査には、追記した項目がすべて `C6` より前に `done` になることを求める `self-reflect 完了 gate` も含まれる。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/run-ubm-knowledge-sync-intermediate.jsonl"
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-knowledge-sync/scripts/validate-knowledge-sync-task-graph.py" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/run-ubm-knowledge-sync-intermediate.jsonl"
```

- **内側ループ（IN1）**: Phase1 で `detect-knowledge-updates.py --registry knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM [--all|--since]` を実行し、NEW/MODIFIED を登録簿（`registry.json`）との MD5 照合で漏れなく見つける。
- **外側ループ（OUT1）**: 更新済みだとわかっているソースを入れ、`knowledge-extractor` が6カテゴリへ正しく分類し、`router.json`/`registry.json` の同期が終わることを受け入れテストで確かめる。

## 守ること

- **検知の対象**: `$UBM_VAULT_ROOT/05_Project/UBM/` の下にある `.md`（YouTube/合宿/月報フィードバック/動画教材/`UBM/` 直下）。利用者自身の記録で北原ナレッジに当たらない `05_Project/UBM/目標設定/`（`run-ubm-goal-setting` の保存先）と `05_Project/UBM/挑戦宣言/`（`run-ubm-challenge` の保存先）は、**`detect-knowledge-updates.py` が検知の段階で除く**。除外の正本は同スクリプトの `EXCLUDED_SUBDIRS` で、読む側で出力の行を除く手順は持たない（スクリプトを直接呼んでも同じ結果になる）。利用者の記録を置くディレクトリを増やすときは、この定数に足す。
- **抽出モード**: 引数なし=未処理のものだけ / `--all`=全件を強制的に `NEW` とする（`mode:full` ですべて作り直す。`knowledge-extractor` の Rule F）/ `--since YYYY-MM-DD`=指定日より後に更新された同一ハッシュも再処理する追加条件（未登録・ハッシュ変更は日付に関係なく対象） / `--dry-run`=検知だけで、書き込まない。
- **必須フィールド**: 各エントリに `content`/`background`/`intent`/`root_cause`/`expected_outcome` などを持たせる（`schema.json` に従う）。引用は北原さんの原文を正確に抜き出す（要約ではなく引用）。分類はソースの種類ではなく、**内容の種類**で行う。
- **命名規則（厳守）**: `{category}-{subtopic}.json`。`{subtopic}` は内容を英語で表す（relationship/organization/0to1 など）。**連番 `-1`/`-2`/`-a`/`-b` は絶対禁止**（ファイル名だけで、誰向けの内容かが分かるようにする）。
- **分割基準は二層**: 25エントリを超えたら、意味のまとまりでの分割を検討するきっかけにする。500行を超えたかどうかは、`check-knowledge-split.py` が肥大を防ぐガードとして機械的に調べる。両者がぶつかるときは、25エントリの基準でサブテーマを設計し、500行のガードを必ず解消する。
- **登録簿の `file_hash`**: Bash の md5 で求めた32文字のハッシュを記録する。日付の文字列や偽の値を使うのは禁止。`extracted_entry_ids` を `null` にするのは禁止（次に `MODIFIED` を検知したときの削除に使う）。
- **`MODIFIED` の処理**: 登録簿の `extracted_entry_ids` をたどって既存のエントリを削除 → 全件を再抽出 → 登録簿を上書き（Case A/B は `knowledge-extractor` の Step U-1〜U-4 を正本とする）。
- **旧形式の `null` の移行**: 初期データの登録簿にある `extracted_entry_ids: null` の7件（`_note: legacy`）は、初めて `MODIFIED` を検知したときに、そのソース由来のエントリをすべて削除 → 再抽出して `extracted_entry_ids` を埋め直す（過去分の埋め戻し）。それ以降は `null` の禁止を適用する。
- **途中で失敗したときの再開**: 最大20ファイルは、並列のトランザクションにせず、1ソースずつ処理する。ソースごとに `knowledge/*.json` → ルーターの再集計 → 冪等キー付きの `sync-log.jsonl` → 登録簿の順に確定し、registry の `(file_path,file_hash,status=processed)` を唯一の commit point（確定点）とする。登録簿の確定前に失敗したら同じソースを再実行し、`content`/`source` の重複検査と `sync-log.jsonl` のキーで冪等に収束させる。確定したソースは、検知の段階（`detect-knowledge-updates.py`）が選び直さない。確定していないソースを残したまま次へ進まない。

## つまずきやすい点

- **スキーマはプラグイン直下で共有するもの**: このスキルの `knowledge-extractor` は `knowledge/schema.json` に従ってエントリを書く。`run-ubm-goal-setting` の `info-collector` は、`router.json` を通してその `knowledge/*.json` を読む。読む側がスキーマのファイルそのものを直接読む約束ではない。共有するデータをスキーマに合わせておくことで、スキルどうしの整合を保つ。
- **初期データの非対称**: `registry.json` は、実際の台帳（処理済みの67ファイル。移植元に実在しないパス6件はビルドのときに除いた）を初期値として同梱してある（初回の同期で全件を `NEW` と誤って検知しないため）。`sync-log.jsonl` は空（0エントリ）から始め、追記だけで書き足す。
- **L2 の vault につながっていないとき**: ソースが空でも、検知0件の報告を正常終了として返す（個人で使っていて vault がつながっていなくても、不合格にしない）。L1 の厳選したナレッジは同梱しているので、接続の確認は要らない。
- **書き込みの保護**: vault のソースは常に読み取り専用とする。プラグイン同梱の `knowledge/*.json`、同じスキルのアセット、専用の `eval-log/` 以外には書かない。各 Task は、解決済みの絶対パスのルートと、書き込み先の実パス（`realpath`）がその範囲に収まることを、書き込む前に確かめる。

## 関連資料

- **エージェント**: `knowledge-extractor`（6カテゴリへの分類・Rule A-F・ルーターと登録簿の更新）/ `knowledge-relation-extractor`（読み取り専用で候補の辺を作る）。どちらもプラグイン直下の `agents/` にある。
- **スクリプト**: スキル直下には、差分の検知・分割・実行できる項目の計算・自己反映・依存グラフ・`task-graph` の実行記録の検査のスクリプトがある。プラグイン直下には `validate-knowledge-graph.py` / `validate-inline-goal-seek-anchor.py` がある。実際のパスの正本は、フロントマターの `script_refs` とする。
- **参照資料**: `references/knowledge-sources.md`（取得方法・優先順位）/ `references/knowledge-design-principles.md`（記録対象・必須フィールド・命名規則）。
- **付属資料**: `assets/kitahara-principles-db.md`（北原さんの原則の DB。新しい原則を見つけたときに追記する、書き換えてよい L3 のアセット）。
- **ナレッジ**: プラグイン直下の `knowledge/`（`schema.json`/`router.json`/`registry.json`/`sync-log.jsonl` と、6カテゴリの `*.json`）。
