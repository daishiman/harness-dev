---
name: run-ubm-knowledge-sync
description: 北原さん式ナレッジソースを同期する。差分を検知したいとき、6カテゴリへ分類・格納したいときに使う。
disable-model-invocation: true
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
  - scripts/detect-knowledge-updates.py
  - scripts/check-knowledge-split.py
  - scripts/extract-ready-set-from-checklist.py
  - scripts/build-self-reflection-entry.py
  - scripts/extract-capability-dependency-graph.py
  - scripts/build-capability-graph-knowledge-entry.py
  - scripts/validate-knowledge-sync-task-graph.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
  - ../../scripts/validate-knowledge-graph.py
reference_refs:
  - references/knowledge-sources.md
  - references/knowledge-design-principles.md
source: ObsidianMemo vault (.claude/commands/ai/ubm-knowledge-sync) の移植
source-tier: internal
last-audited: 2026-07-04
audit-trigger: quarterly
completeness_exempt:
  - "prompts: 抽出・6カテゴリ分類という唯一の LLM 責務は plugin 直下 SubAgent knowledge-extractor.md (7層プロンプトを本文に内包・43KB) が単独所有し、他 Phase は決定論スクリプト (detect-knowledge-updates.py / check-knowledge-split.py) が担う。skill ローカルの R-id 単位 prompts は SubAgent 本文との二重定義になるため置かない (二重定義禁止 [[project_ssot_dedup_mechanism]])。責務→実行体の対応は本文 End-to-End Flow 表が正本。(prompts/ ディレクトリは配置しない=本 exempt の宣言と実体が一致)"
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

## Purpose & Output Contract

- **ゴール**: ナレッジソースの追加・変更差分が registry.json との照合で検知され、knowledge-extractor による6カテゴリ分類と router.json 更新までナレッジ同期が完了した状態。
- **出力契約**: 検知/抽出/分割/graph 検証の結果レポート（NEW/MODIFIED 件数・格納先・分割要否・graph status）+ `knowledge/*.json` 更新 + `router.json`/`registry.json`/`sync-log.jsonl` 追記 + 差分があるときの `knowledge-relations.json`/`knowledge-graph.json` 再生成。
- **境界**: vault 内ナレッジソースは read-only 入力。書込先は確認済み target scope 内の `PLUGIN_ROOT/knowledge/`、同 skill の `assets/kitahara-principles-db.md`、`PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/` だけ。それ以外と symlink 経由の scope 外は write 前に停止する。目標設定対話は `run-ubm-goal-setting` へ委譲する。
- **6カテゴリ**: principles（原則）/ consultation（相談）/ phase-advice（フェーズ）/ action-guides（行動）/ mindset（転換）/ case-studies（事例）。
- **必須禁則**: `--dry-run` で plugin knowledge や vault を書き換えない。external mutation は canonical receipt flow 外で実行しない。

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `PROJECT_ROOT` は呼出元が渡すリポジトリ絶対パス（Claude Code では `CLAUDE_PROJECT_DIR`）に固定し、realpath containment を確認する。未解決なら mutation や eval-log write を始めない。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物またはremote mutation previewをmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方またはpreview receiptを提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはmutationを実行せずhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionおよびexternal mutation safety wrapperはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。actual mutationはcanonical preview→hook-confirm→authorize→execute wrapperだけを通し、release/exhaustiveは別の明示eventを必要とする。

<!-- external-mutation-guard-cli:v1 -->
### Canonical external mutation receipt flow (mandatory)

Never execute the external mutation argv directly. Replace every angle-bracket placeholder
with the reviewed value from this run; the central CLI fails closed on missing/invalid values.

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

Present that official preview output to the user. Only the exact user reply printed by `preview`
may trigger the registered `hook-confirm` producer. Then use the two returned receipt paths:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/../skill-governance-adapters/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

Do not use an auto-approval flag or invoke the mutation command outside this receipt flow.
<!-- /external-mutation-guard-cli:v1 -->


# run-ubm-knowledge-sync

UBM ナレッジソース（YouTube 議事録・合宿記録・月報 FB・セミナー等）の新規追加・更新差分を検知し、**内容別 JSON ファイル**（6カテゴリ）へ反映する。北原さんの最新の教えを継続的に取り込み、`run-ubm-goal-setting` の品質を底上げする。

## End-to-End Flow

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase1-detect | `detect-knowledge-updates.py` が registry.json との MD5 照合で NEW/MODIFIED ソースを漏れなく検知。出力から `05_Project/UBM/目標設定/` を含む行を除外したものが Phase2 入力 | script |
| Phase2-extract | 本 skill が NEW/MODIFIED を最大20ファイルずつのバッチへ分割し、各バッチで `knowledge-extractor` が6カテゴリへ分類して Rule A-F に従い `knowledge/*.json` + `router.json`/`registry.json` を更新 | 本 skill（batch制御）+ `knowledge-extractor`（Task） |
| Phase3-split-check | `check-knowledge-split.py` がナレッジ JSON の500行閾値超過を機械検査し、knowledge-extractor が25エントリ超過時の意味単位分割を完了して corpus を確定する | script / `knowledge-extractor`（必要時の Task） |
| Phase5-graph-sync（Phase3 完了後） | 確定済み corpus に対し `knowledge-relation-extractor` が根拠付き有方向辺の**候補 JSON** を read-only で返し（knowledge へ書込しない=幻覚防止）、呼び出し側が候補を eval-log へ materialize、`validate-knowledge-graph.py --merge-relations` が canonical key (source_id,target_id,relation_type) で `knowledge/knowledge-relations.json` へ冪等 merge（既存辺は保持=first-write-wins）する。全検証 PASS 後に relations→`knowledge-graph.json` を正準書込し、途中書込失敗は同じ候補の再実行で冪等修復する（2ファイル跨ぎの atomicity は主張しない）。dry-run 時は write 禁止 | `knowledge-relation-extractor`（Task）/ `validate-knowledge-graph.py --merge-relations`（script） |
| Phase4-report（Phase5 完了後） | 検知/抽出/分割/graph-sync の結果（NEW/MODIFIED 件数・格納先・分割要否・graph検証）を最終レポートへ統合する | 本 skill |

Phase5 は差分 entry 起点で発火するため、**差分ゼロの周回では不発**になる。既存 corpus へ辺が一度も付いていない（`knowledge-relations.json` 不在＝edges=0 の退化グラフ）場合の初回適用は、RUNBOOK（plugin 直下 `RUNBOOK.md`）の「初回 edge backfill」手順を使う。

## ゴールシーク実行

`goal_seek.engine: task-graph` / `engine_profile: checklist-graph` / `fork: inline` を使い、同じ corpus を更新・読取する責務を安全な依存順 `Phase1 → Phase2 → Phase3 → Phase5 → Phase4` で1件ずつ消費する。これは checklist の縮小 DAG であり、planner の full task-spec graph ではない (`full_task_spec_graph: false`)。

### 完了チェックリスト (Checklist)

- [ ] C1: Phase1-detect を実行し差分一覧または差分0件の証跡を得る (`depends_on: []`, `verify_by: script`)
- [ ] C2: Phase2-extract を完了する。dry-run または差分0件なら条件不成立を記録して no-op 完了にする (`depends_on: [C1]`, `verify_by: reasoning`)
- [ ] C3: Phase3-split-check を完了し、後続が読む corpus を確定する。dry-run なら書込禁止の no-op 完了にする (`depends_on: [C2]`, `verify_by: script`)
- [ ] C4: Phase5-graph-sync を確定済み corpus に対して完了する。dry-run または差分0件なら no-op 根拠を残す (`depends_on: [C3]`, `verify_by: script`)
- [ ] C5: Phase4-report に C1〜C4 の結果、skip理由、未解決事項を統合する (`depends_on: [C4]`, `verify_by: reasoning`)
- [ ] C6: task-graph 消費検証と Anchor 検証が exit 0 で、pending/blocked が残らない (`depends_on: [C5]`, `verify_by: script`)

### ゴールシーク配線

- `goal_seek.progress`: 初回に上の C1〜C6 を `{id,text,status:"pending",depends_on,verify_by}` として `eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json` へ記録し、top-level に `engine:"task-graph"`、iteration、`open_issues`、`status`、`max_loops:9` を置く。 `goal_seek.intermediate`: 各周回末の Anchor Step で `run-ubm-knowledge-sync-intermediate.jsonl` に `original_goal` / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` と、その周回の `ready_set` / `selected_item` を append-only で残す。 `goal_seek.handoff`: 完了時に検知件数、更新先、split-check/graph検証結果、dry-run 有無、未解決課題を `handoff-run-ubm-knowledge-sync.json` へ書く。
- ループ・ready-set・外部mutation guard・ユーザー確認・progress write は親 context が所有する。Phase2 の抽出と Phase5 の関係候補生成だけを対応する `knowledge-extractor` / `knowledge-relation-extractor` へ `Task` 委譲し、各自は個別 surface 成果だけを返す。各 Task input には親が host-skill-path から解決した absolute `PLUGIN_ROOT` を明示し、SubAgent は未指定または非 absolute なら write 前に fail-closed で停止する。preview 後の exact reply は親が受け、confirmation receipt を得てから同じ周回を authorize→execute へ再開する。
- 各周回は `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-knowledge-sync/scripts/extract-ready-set-from-checklist.py" "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json"` で raw ready を算出する。`C6` は最終 completion gate のため、`C6` 以外の item が1件でも未消費なら raw ready から `C6` を除いた集合を effective `ready_set` とし、その最小IDだけを選択する。実行または条件付きno-opの証跡を残して該当itemを `done` にしてから再計算する。実行中に追加必須作業を発見した場合だけ同じ skill 配下の `build-self-reflection-entry.py` で `C7` 以降のidと実際の先行item（`C6` 以外）への `depends_on` を持つitemを同じ checklist 末尾へ追記する（別 task graph state は作らない）。effective ready が空で将来周回から有効な追記itemがある場合は、その周回を未選択traceとして残し `C6` を先行させない。
- `--dry-run` 指定時も C1→C2(no-op)→C3(no-op)→C4(no-op)→C5 の順に選択してtraceを残し、Phase2 extraction・Phase3 split repair・Phase5 graph writeを禁止する。condition不成立を「未選択」のまま残さない。
- C6 は `selected_item` trace を先に追記し、C6をdone・全体をcompleted候補へ更新してから下記検証を最終実行する。exit非0ならcompletedを確定せず `status: handed_off` と `open_issues` へ違反を残す。
- `max_loops` 到達時は PASS 扱いせず、残チェック項目を `open_issues` に残して human review へ差し戻す。

### dependency graph knowledge consult

各 surface の着手前に `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-knowledge-sync/scripts/extract-capability-dependency-graph.py" "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"` の出力を `$PROJECT_ROOT/eval-log/` の派生JSONへ保存する。通常実行では dangling/cycle が無いときだけ同じ skill 配下の `build-capability-graph-knowledge-entry.py` へ graph path と `--target-knowledge-dir "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/knowledge"` を渡し、`source_ref` 付き要約をappend/mergeする。`--dry-run` では extract 結果を eval-log 内でのみ consult し、record と plugin `knowledge/` write を no-op trace にする。通常時は `knowledge/knowledge-capability-graph.json` を consult し、未完成依存を先に実行しない。この knowledge は実行順stateではなく派生判断であり、progress checklistだけを唯一のtruthとする。

### ゴールシーク検証

Anchor Step と依存順消費を同時に機械検証する。absence-as-violation とし、task-graph なのに `ready_set` / `selected_item` trace が無い場合は失敗させる。申告 `ready_set` は信用せず、checklist・過去の `selected_item`・`available_from_iteration` から各周回の ready 全集合を再計算し、未消費の `C6` 以外itemがある間は completion gate `C6` を effective ready から除く。以下を順に実行し、両方 exit 0 を必須とする。前者の正本は `required_keys` / `original_goal_hash` / `hashlib.sha256` を検査し、後者は追記itemが `C6` より前に全てdoneとなる `self-reflect 完了 gate` を含む依存順消費を検査する。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/run-ubm-knowledge-sync-intermediate.jsonl"
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-knowledge-sync/scripts/validate-knowledge-sync-task-graph.py" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json" \
  "$PROJECT_ROOT/eval-log/ubm-goal-setting/run-ubm-knowledge-sync/run-ubm-knowledge-sync-intermediate.jsonl"
```

- **inner ループ (IN1)**: Phase1 で `detect-knowledge-updates.py --registry knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM [--all|--since]` を実行し、NEW/MODIFIED を registry との MD5 照合で漏れなく検知する。
- **outer ループ (OUT1)**: 既知の更新済みソースを投入し、knowledge-extractor が6カテゴリへ正しく分類し router.json/registry.json が同期完了することを受入テストで確認する。

## Key Rules

- **検知対象**: `$UBM_VAULT_ROOT/05_Project/UBM/` 配下の全 `.md`（YouTube/合宿/月報フィードバック/動画教材/ルート直下）。`05_Project/UBM/目標設定/`（ユーザー自身の目標記録＝北原ナレッジ非該当）は **consumer 側で除外**する。
- **抽出モード**: 引数なし=未処理のみ / `--all`=全件強制 NEW（mode:full 全再構築・knowledge-extractor Rule F）/ `--since YYYY-MM-DD`=指定日以降 / `--dry-run`=検知のみで書込なし。
- **必須フィールド**: 各エントリに `content`/`background`/`intent`/`root_cause`/`expected_outcome` 等（`schema.json` 準拠）。引用は北原さんの原文を正確に抜き出す（要約でなく引用）。分類はソース種別でなく**内容の種類**で行う。
- **命名規則（厳守）**: `{category}-{subtopic}.json`。subtopic は内容を英語で表現（relationship/organization/0to1 等）。**連番 `-1`/`-2`/`-a`/`-b` は絶対禁止**（ファイル名だけで対象読者が分かること）。
- **分割基準の二層化**: 25エントリ超過は意味単位の分割検討トリガー、500行超過は `check-knowledge-split.py` の機械的な肥大ガード。両者が衝突する場合は 25エントリ基準でサブテーマを設計し、500行ガードを必ず解消する。
- **registry の file_hash**: Bash の md5 由来 32文字ハッシュを記録。日付文字列・偽値の使用は禁止。`extracted_entry_ids` は null 禁止（次回 MODIFIED 検知時の削除に使用）。
- **MODIFIED 処理**: registry の `extracted_entry_ids` を辿って既存エントリを削除 → 全件再抽出 → registry を上書き（Case A/B は knowledge-extractor の Step U-1〜U-4 を正本とする）。
- **legacy null の移行**: シード registry の `extracted_entry_ids: null` 7件（`_note: legacy`）は、初回 MODIFIED 検知時に該当ソース由来のエントリを全削除 → 再抽出で `extracted_entry_ids` を backfill し、以後は null 禁止を適用する。
- **途中失敗の再開**: 最大20ファイルは並列 transaction ではなく1 sourceずつ処理する。source ごとに `knowledge/*.json` → router 再集計 → idempotency key 付き sync-log → registry の順で確定し、registry の `(file_path,file_hash,status=processed)` を唯一の commit point とする。registry 確定前の失敗は同じ source を再実行し、content/source 重複検査と sync-log key で冗等に収束させる。commit 後の source は detect が再選択しない。未 commit source を残したまま次へ進まない。

## Gotchas

- **schema は plugin-root 共有 surface**: 本 skill の knowledge-extractor は `knowledge/schema.json` 準拠でエントリを書き、`run-ubm-goal-setting` の info-collector は `router.json` 経由でその `knowledge/*.json` を読む。consumer が schema ファイル自体を直接読む契約ではなく、共有データを schema 準拠に保つことで skill 間を整合させる。
- **初期シードの非対称**: `registry.json` は実台帳（処理済み67ファイル・移植元の dead path 6件は build 時に除去）を初期値として vendor 済み（初回 sync 全件 NEW 誤検知を回避）。`sync-log.jsonl` は空（0エントリ）で開始し append-only で追記する。
- **L2 vault 未接続時**: sources が空でも検知0件レポートを正常終了として返す（個人利用で vault 未接続でも FAIL 扱いしない）。L1 curated knowledge は vendor 同梱のため疎通不要。
- **書き込み保護**: vault ソースは常に read-only。plugin 同梱 `knowledge/*.json` / 同 skill asset / 専用 eval-log 以外は書かず、各 Task は解決済み absolute root と realpath containment を write 前に確認する。

## Additional Resources

- **agents**: `knowledge-extractor`（6カテゴリ分類・Rule A-F・router/registry 更新）/ `knowledge-relation-extractor`（read-only 候補辺生成）。どちらも plugin 直下 `agents/`。
- **scripts**: skill 直下の差分検知・分割・ready/self-reflect/capability graph・task-graph trace 検査と、plugin 直下 `validate-knowledge-graph.py` / `validate-inline-goal-seek-anchor.py`。frontmatter `script_refs` が実パスの正本。
- **references**: `references/knowledge-sources.md`（取得方法・優先順位）/ `references/knowledge-design-principles.md`（記録対象・必須フィールド・命名規則）。
- **assets**: `assets/kitahara-principles-db.md`（北原さん原則 DB・新原則発見時に追記する L3 mutable asset）。
- **knowledge**: plugin 直下 `knowledge/`（`schema.json`/`router.json`/`registry.json`/`sync-log.jsonl` + 6カテゴリ `*.json`）。
