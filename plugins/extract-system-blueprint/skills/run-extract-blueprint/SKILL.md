---
name: run-extract-blueprint
description: 参考システムのURL1件から、フロント表層の事実とバックエンド/設計意図の根拠つき推測を明示区別した章別ブループリントを外部公開せずローカルに生成したいとき、生成物の忠実性を独立verdictで品質評価したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "<url> [--crawl-mode single|full_site] [--resume]"
arguments: [url, crawl_mode, resume]
allowed-tools:
  - Read
  - Write
  - WebFetch
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: harness maintainers
since: 2026-07-11
version: 0.2.0
output_language: ja
mcp_tools: []
external_systems: [対象システムの公開URL]
deterministic_checks: [authz-classify.py, fetch-snapshot.py, mermaid-validate.py, doc-emit.py]
responsibility_refs:
  - prompts/R1-fetch.md
  - prompts/R2-analyze.md
  - prompts/R3-document.md
schema_refs:
  - ../../schemas/fact-inference-confidence.schema.json
  - ../../schemas/system-blueprint.schema.json
  - ../../schemas/goal-seek-loop.schema.json
script_refs:
  - scripts/extract-ready-set-from-checklist.py
  - scripts/build-self-reflection-entry.py
  - scripts/extract-capability-dependency-graph.py
  - scripts/build-capability-graph-knowledge-entry.py
manifest: workflow-manifest.json
goal_seek:
  activation_state: semantic_evaluator_started
  engine: task-graph
  engine_profile: checklist-graph
  full_task_spec_graph: false
  fork: agent-team
  spec: eval-log/goal-spec.json
  progress: eval-log/run-extract-blueprint-progress.json
  intermediate: eval-log/run-extract-blueprint-intermediate.jsonl
  max_loops: 5
feedback_contract: # per-skill 評価基準。content-review verdict の criteria_evaluated と突合
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: authz/fetch/mermaid/doc の決定論チェックが exit0 になり、重要 fact 欠落 0、未観測の無断 inference 化 0、request budget 超過 0、対象 origin 並列数 1 を確認する
      verify_by: script
      derived_from: [CL-1, CL-2, CL-3, CL-6, CL-9]
    - id: OUT1
      loop_scope: outer
      text: 生成物でバックエンド機構・設計意図が根拠+確度つき推測として事実と明示区別され、AI へ渡した際に追加のヒアリングなしで自社版スカフォールドの雛形生成に着手できる粒度であることを受入テストが確認する (EVALS reconstruction-rehearsal)
      verify_by: test
      derived_from: [CL-3, CL-4, CL-5]
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
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


# run-extract-blueprint

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

> extract-system-blueprint plugin の抽出本体 (L1 skill)。plugin-root 共有 script (`scripts/authz-classify.py`=C12 / `fetch-snapshot.py`=C09 / `browser-render.py`=C15 / `doc-emit.py`=C11 / `mermaid-validate.py`=C10)・analyzer sub-agent 5 体 (C03/C04/C05/C13/C06)・fail-closed hook (`hooks/pre-fetch-authz-guard.py`=C08) を配線する。パス解決は Runtime root contract の `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` 起点、成果物は明示した project root 配下。

## Purpose & Output Contract

対象URL 1件から、pre-choiceではmain contextが認可済み最小snapshotを根拠にfact/inferenceを分けた開けるblueprint draft (md+json) を生成・決定論guard・提示する。Task analyzer、Mermaid拡充、semantic fidelity評価、有界修正はlight/standard/detailed選択後だけ実行する。外部公開はしない。

**入力**: `url` (対象 URL 1 件), `--crawl-mode single|full_site` (既定 single), `--resume` (前 run の site coverage manifest から継続)
**出力**:
- ローカル章別 blueprint (`system-blueprint.schema.json` 準拠の md + json)・5 種 Mermaid 図・画面別 layout.json / layout-overlay.svg・合成 design-tokens.json・site coverage manifest・request ledger
- 完了レポート (日本語本文、パラメーター名・JSON キー・enum は原文)

**usable handoff条件**: 認可・最小fetch/doc guardがexit0でactual md/jsonのpath/digestを提示済み。accept-as-isならC02/Task/反復0回で完了。**選択後の改善完了条件**: Mermaid5種とfact/inference分離を拡充し、C02が同digestのverdictを発行する。

**禁則**: 認証必須領域への無断到達・実侵入・認可外スクレイピングをしない。全 origin 並列 1・最小間隔・request budget・Retry-After・停止条件を緩めない (引上げはユーザー承認対象)。

## データ契約と責務分割

- **fact / inference / observation_gap 三値分離** (`${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/schemas/fact-inference-confidence.schema.json`): fact は provenance (source_url/locator/captured_at/method/snapshot_id) 必須・レンズ解釈を含めない。inference は claim + evidence_refs(≥1) + confidence{level,rationale} 必須。observation_gap は not_observed|blocked + reason + budget_state で inference に昇格させない。top-level blueprint shape は `system-blueprint.schema.json` (screens[]/design_tokens/tech_stack/essence 等) を正本とする。
- **責務 (詳細は `prompts/R1-R3`)**:
  - **R1-fetch** (`prompts/R1-fetch.md`): C12 で AuthzEvidence/request budget/crawl_profile を確定し、C09 の URL discovery → C12 の scope 分類 (in_scope/excluded+reason) で system 関連 URL 台帳を作り、C08 の fail-closed 境界内で C09 静的 HTTP snapshot を全 in-scope 画面へ取得し、加えて C15 (`browser-render.py`・MCP 非依存 headless Chrome via Bash) で rendered DOM/screenshot の取得を試みる (ブラウザ不在=exit 3 時のみ gap)。`--resume` は前 run の site coverage manifest を C12 `--coverage-manifest-in` へ再投入する。
  - **R2-analyze (post-choice only)**: light/standard/detailed選択後だけC03→C04/C05/C13→C06をTaskの独立contextへ委譲する。提示前とaccept-as-isでは起動しない。各analyzerは提示済みdraft digestを入力にfact/inferenceを分離して拡充する。
  - **R3-document** (`prompts/R3-document.md`): C11 (`doc-emit.py`) で章別ローカル draft (md/json) と 5 種 Mermaid・画面別 layout.json/overlay を確定し、`doc-emit.py --check-screens` で layout completeness を、`mermaid-validate.py` (C10) で図種網羅を自己検証する。`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/doc-emit.py" --extraction <json> --out-dir <dir> --request-ledger <f> [--check-screens]` で起動する。screenshot / annotated は browser-render (C15) 取得時に extraction の screens[] へ populate され、ブラウザ不在時のみ `observation_gap` として記録する。

## ゴールシーク実行

> 本 skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。正本: `../../../harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

対象 URL 1 件について、フロント表層の事実とバックエンド/設計意図の根拠つき推測を明示区別した章別ドキュメント群 (md + json + 事実推測区別図を含む 5 種 Mermaid + 主要画面の layout.json / 注釈 overlay / verbatim content fact / essence 章) が**ローカルへ生成されて完結**し、C02 (独立 context) がローカル品質評価の verdict (PASS/FAIL) を発行できる状態。

### 目的・背景 (Why)

URL をブラウザ目視 + F12 確認する手作業 3 ステップ (週 2.5 回 × 平均 90 分) を排し、URL 解析結果から自社実装の雛形・設計ドキュメントを即生成して自社構築の着手を速くするため。事実と推測を構造分離することで、AI へ渡した際に追加ヒアリングなしで自社版スカフォールドへ着手できる粒度を担保する。

### 完了チェックリスト (Checklist)

- [ ] C12 が AuthzEvidence/request budget/crawl_profile を発行し (`allow`)、C08 の fail-closed 境界内で C09 静的 HTTP snapshot を全 in-scope 画面へ取得し、C15 browser-render で rendered DOM/screenshot の取得を試みた (MCP 非依存・対象 origin 並列 1・budget 超過 0・ブラウザ不在=exit 3 時のみ gap) <!-- CL-1 -->
- [ ] フロント表層の fact (UI 要素/観測通信/verbatim content/tech_signals/機能/CWV/security/compliance/site_inventory・および browser-render 取得時は JS 後 DOM/screenshot/computed style) が provenance 付きで採取され、browser-render がブラウザ不在 (exit 3=browser-unavailable) の場合のみ JS 後 DOM/screenshot/computed style が `observation_gap`+reason=browser-unavailable として記録され、未取得 field が無言欠落でなく `not_observed`+reason である <!-- CL-2 -->
- [ ] バックエンド機構・設計意図・named 同定・UIUX 根拠・content-intent が evidence_refs+confidence 付き inference として fact と明示区別され、essence 章 (本質的問題(JTBD)/読者/価値提案/キーメッセージ/トーン/positioning) が統合された <!-- CL-3 -->
- [ ] 各 analyzer の実プロンプトに著名エンジニア名付き原則レンズ見出し・cross-lens conflicts・neutral synthesis があり、レンズ由来主張も evidence_refs+confidence 必須で fact へ混入していない <!-- CL-4 -->
- [ ] 5 種 Mermaid 図 (全体構成/事実↔推測レイヤ/画面遷移/データフロー sequence/データモデル) が生成され `mermaid-validate.py` が exit0 <!-- CL-5 -->
- [ ] `doc-emit.py --check-screens` が exit0 (layout 参照整合・観測色の palette 孤児 0・site coverage manifest の pending 無言欠落なし・未取得 screenshot は observation_gap として記録) で、draft_hash が固定された <!-- CL-6 -->
- [ ] 対象 origin への load-policy (並列 1・最小間隔・request budget・Retry-After・停止条件) を全周で満たし、full_site でも瞬間負荷レバーを緩めていない <!-- CL-9 -->

### ゴールシークループ

正本 goal-seek-paradigm.md の 6 ステップ (現状評価/手順生成/実行/検証/Anchor Step/反復) に従う。本 skill 固有の差分:

- **現状評価**の単位は上記チェックリスト。未達項目を `## 局面カタログ (順序は都度判断)` から選んで埋める (順序固定禁止)。
- **検証**は決定論チェック (authz/fetch/mermaid/doc の exit0) を優先し、LLM 判断より機械層を先に通す。
- **差し戻し**: 決定論チェック fail または C02 FAIL なら R1-R3 の該当局面へ戻す (最大 5 周)。超過・drift 停滞は `open_issues` へ残し上位 orchestrator へ差し戻す。
- **重い周回は選択後だけ分離 context**: light/standard/detailed選択後のみanalyzerをTaskでforkする。accept-as-isでは0回。親へは最終成果物pathと要約だけを返す。

### ゴールシーク配線

- goal_seek.spec は plugin 単一の `eval-log/goal-spec.json` を本 skill と `run-blueprint-apply` (C14) が共有する (progress は skill 別ファイル。ゴール正本は 1 つ、周回状態は skill 別という設計意図)。
- 周回状態と中間成果物は **repo-root (非 repo 環境では plugin-root) 直下**の `eval-log/run-extract-blueprint-intermediate.jsonl` へ追記する (cwd 相対禁止)。各周回末に不変アンカー `original_goal` (上記ゴール文の原文) と `delta_from_original`、次周回の必須入力 `merged_directive_for_next` を記録し、次周回 Step2 の必須入力とする (集約化ドリフト圧縮)。周回サマリは `schemas/goal-seek-loop.schema.json` 準拠の `eval-log/run-extract-blueprint-progress.json` に残す。
- `workflow-manifest.json` の R1-fetch → R2-analyze → R3-document を progress checklist へ射影し、`dependsOn` を `depends_on` として保つ。pre-choice 実行済みの R1 は証跡 digest を確認して done trace を作り、post-choice の graph は R2 から再開する。
- progress checklist の決定論的ID写像は `C1=R1-fetch evidence再検証 (depends_on=[])`、`C2=R2-analyze (depends_on=[C1])`、`C3=R3-document (depends_on=[C2])` とする。C1はpre-choice成果物を再取得せず、post-choice最初のtask-graph周回で提示済みdigestとguard receiptを選択・照合してdoneにするため、選択証跡なきdoneを作らない。C1/C2/C3はそれぞれ `CL-1/CL-2/CL-9`、`CL-3/CL-4`、`CL-5/CL-6` をgateし、`max_loops=5` は3 item+最大2件のself-reflect余裕を持つ。
- 各周回冒頭で `scripts/extract-ready-set-from-checklist.py eval-log/run-extract-blueprint-progress.json` を実行し、ready 集合の最小 id だけを選ぶ。R2 では `frontend-surface-analyzer` による fact (C03) を先行させ、完了後に backend / UIUX / content (C04/C05/C13) の 3 分析を Agent Team で独立 fan-out する。各自は C03 fact を読み、個別 artifact のみを write scope とする。`architecture-essence-synthesizer` (C06) の fan-in 完了後に R2 を done にする。
- 未網羅タスクを発見した場合だけ `scripts/build-self-reflection-entry.py` で新しい sink item を checklist へ追記する。未知 `depends_on` と cycle は exit 1 で拒否し、追記 item が done になるまで self-reflect 完了 gate を閉じる。
- 各周回に `ready_set` と `selected_item` を intermediate.jsonl へ追記する。`selected_item` は `ready_set` 最小 id と一致し、全依存が過去に done であることを検証する。トレース不在を依存順消費の成功に畳まない。
- 着手前に `scripts/extract-capability-dependency-graph.py` で Skill / SubAgent / script の参照を確認し、dangling があれば停止する。再利用価値のある依存判断だけを `scripts/build-capability-graph-knowledge-entry.py` で dependency graph knowledge へ記録する。

### ゴールシーク検証（task-graph consumption）

`engine: task-graph` の完了判定前に、progress checklistとintermediate traceから依存順消費を機械検査する。`ESB_RUNTIME_ROOT` は上記配線で解決したrepo-root（非repo環境ではplugin-root）のabsolute pathに固定し、cwdから推測しない。intermediate不在、unknown依存、cycle、ready最小ID以外の選択、依存未選択、選択証跡なきdone、未完了itemを残したcompletedはfail-closedにする。

```bash
ESB_RUNTIME_ROOT="$(git -C "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}" rev-parse --show-toplevel 2>/dev/null || printf '%s' "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}")"
python3 - "$ESB_RUNTIME_ROOT/eval-log/run-extract-blueprint-progress.json" "$ESB_RUNTIME_ROOT/eval-log/run-extract-blueprint-intermediate.jsonl" <<'PY'
import json, os, re, sys

progress_path, intermediate_path = sys.argv[1:]
progress = json.load(open(progress_path, encoding="utf-8"))
if progress.get("engine") != "task-graph":
    raise SystemExit("progress.engine must be task-graph")
checklist = progress.get("checklist", [])
ids = {item.get("id") for item in checklist}
deps_of = {item.get("id"): list(item.get("depends_on") or []) for item in checklist}
for item_id, dependencies in deps_of.items():
    for dependency in dependencies:
        assert dependency in ids, f"{item_id}: unknown depends_on={dependency}"

WHITE, GREY, BLACK = 0, 1, 2
colors = {item_id: WHITE for item_id in ids}
for start in ids:
    if colors[start] != WHITE:
        continue
    colors[start] = GREY
    stack = [(start, iter(deps_of[start]))]
    while stack:
        item_id, pending = stack[-1]
        dependency = next(pending, None)
        if dependency is None:
            colors[item_id] = BLACK
            stack.pop()
        elif colors[dependency] == GREY:
            raise AssertionError(f"depends_on cycle: {item_id}->{dependency}")
        elif colors[dependency] == WHITE:
            colors[dependency] = GREY
            stack.append((dependency, iter(deps_of[dependency])))

assert os.path.exists(intermediate_path), "task-graph intermediate trace is missing"
rows = [json.loads(line) for line in open(intermediate_path, encoding="utf-8") if line.strip()]
traced = [row for row in rows if "ready_set" in row and "selected_item" in row]
assert traced, "ready_set/selected_item trace is missing"
numeric = re.compile(r"^C(\d+)$")
def sort_key(item_id):
    match = numeric.match(item_id)
    return (0, int(match.group(1)), item_id) if match else (1, 0, item_id)

selected = []
items = {item["id"]: item for item in checklist}
for index, row in enumerate(traced):
    ready, selected_item = row["ready_set"], row["selected_item"]
    if not selected_item:
        continue
    assert ready, f"iteration {index}: selected_item with empty ready_set"
    assert selected_item == sorted(ready, key=sort_key)[0], f"iteration {index}: not minimum ready id"
    assert selected_item in items, f"iteration {index}: unknown selected_item={selected_item}"
    assert all(dependency in selected for dependency in deps_of[selected_item]), (
        f"iteration {index}: dependency not previously selected for {selected_item}"
    )
    available = items[selected_item].get("available_from_iteration", 0)
    assert row.get("iteration", index) >= available, (
        f"iteration {index}: {selected_item} selected before available_from_iteration={available}"
    )
    selected.append(selected_item)

selected_set = set(selected)
untraced_done = [item["id"] for item in checklist if item.get("status") == "done" and item["id"] not in selected_set]
assert not untraced_done, f"done item without selected trace: {untraced_done}"
unfinished = [item["id"] for item in checklist if item.get("status") in ("pending", "blocked")]
if progress.get("status") == "completed":
    assert not unfinished, f"completed with unfinished items: {unfinished}"
max_loops = progress.get("max_loops")
if isinstance(max_loops, int) and len(checklist) > max_loops:
    raise AssertionError(f"checklist size {len(checklist)} exceeds max_loops {max_loops}")
print(f"task-graph consumption OK: {len(traced)} traced iterations")
PY
```

### ゴールシーク検証（goal anchor）

各周回末に中間成果物 JSONL の整合を機械検証する。`required_keys` (= `original_goal`, `merged_directive_for_next`, `delta_from_original`) が全て存在し、`original_goal_hash` が初回の `hashlib.sha256(original_goal)` と一致することを確認する (ゴール改竄検出)。不一致なら周回を停止し差し戻す。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-goal-seek-anchor.py" \
  --intermediate eval-log/run-extract-blueprint-intermediate.jsonl
```

検証ロジックの正本は共有 validator `../../scripts/validate-goal-seek-anchor.py` とし、各 skill は対象 JSONL のパスだけを渡す (対象 JSONL 不在は fail-closed で exit 1=配線バグ扱い。必ず追記後に起動する)。

## 局面カタログ (順序は都度判断)

下記は固定順序ではなく、ゴールシークループが未達チェックリスト項目に応じて選ぶ局面群。各局面の詳細手順・入出力契約は `prompts/R1-R3` を正本とする。

### 局面: 認可 preflight と取得 (R1-fetch)

run 開始時の bootstrap は `Bash(python3 *)` で許可された**単一 Python 呼び**が正本: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/authz-classify.py" --url <url> --evidence-out <dir>/authz.json --budget-out <dir>/budget.json [--crawl-mode full_site --discovered-urls ... --coverage-manifest-in ...]`。`authz-classify.py` 自身が出力親dirを作成して C12 authz とbudgetを同一処理で発行し、allow/deny/unknown と budget/crawl_profile を確定する (unknown は deny)。C08 hook は tool call 開始時にdir不在ならこのbootstrapだけを素通しし、完了時にはdir+evidenceが揃うため、以後の全tool callがenforceされる (evidence不在窓なし)。`ESB_RUN=1` は hook が別プロセスでspawnされるため Bashセッション内exportでは継承されず、セッション起動時envとしてのみ有効な補助上書き。allow のとき `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/fetch-snapshot.py" --url <url> --out-dir <dir> --authz-evidence <dir>/authz.json --request-budget <dir>/budget.json [--discover-urls --discovered-urls-out ...]` で snapshot + discovery。evidence/budget は C08 が参照する `ESB_AUTHZ_DIR` (既定 `.esb-authz`) へ配置する。全 fetch は C08 hook の fail-closed 境界内で走る。

### 局面: 分析への fan-out (R2-analyze)

Task で `frontend-surface-analyzer` を先行起動し fact records を得てから、`backend-inference-analyzer` / `uiux-rationale-analyzer` / `content-intent-analyzer` を C03 出力起点の直交レーンとして起動し、最後に `architecture-essence-synthesizer` へ fan-in する。各 analyzer は fact/inference を分離 JSON として成果物ディレクトリへ直接書き出す (応答長起因の無言欠落を排除)。

### 局面: 文書化と自己検証 (R3-document)

`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/doc-emit.py" --extraction <json> --out-dir <dir> --request-ledger <f> [--check-screens]` で章別 draft + Mermaid + layout を生成し、`doc-emit.py --check-screens` と `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/mermaid-validate.py" --docs-dir <dir>` で自己検証。draft_hash を固定する。

## Key Rules

1. **fact ≠ inference ≠ gap**: 観測は provenance 付き fact、推測は evidence_refs+confidence 付き inference、未観測は observation_gap。gap を無言欠落や inference へ昇格させない。
2. **proposer ≠ approver**: 自己 draft は C02 (独立 context) の**ローカル品質ゲート** verdict (PASS/FAIL) を経て品質適格を判定する。C01 は自己評価だけで適格判定しない (proposer と approver を分離する)。
3. **低負荷不変**: 対象 origin 並列 1・最小間隔・request/byte budget・Retry-After・stop 条件は single/full_site 両モードで不変。full_site は per-run 有界 + multi-run resume で全 URL へ到達する。
4. **認可外へ egress しない**: C12 が allow した AuthzEvidence 範囲外・認証必須領域へフェッチしない (C08 が fail-closed 遮断)。
5. **共有決定論ゲートの SSOT**: `mermaid-validate.py` (C10) / `doc-emit.py --check-screens` (C11) は C01 の自己検証と C02 の独立評価で同一ロジックを共有する。
6. **参考/学習目的注記**: 各正本へ参考/学習目的限定注記を焼く (C11 が担保)。

## ハンドオフ

- **次工程 (評価)**: `assign-blueprint-fidelity-evaluator` (C02) が draft_hash に束縛したローカル品質評価の verdict (PASS/FAIL) を発行する。C01 は draft と draft_hash を成果物ディレクトリへ出す。
- **下流適用**: C02 PASS (ローカル品質評価) 済 blueprint は `run-blueprint-apply` (C14) が自社適用 recommendations の入力に使う。

## Gotchas

- **`export ESB_RUN=1` は hook に届かない**: PreToolUse hook はハーネスが別プロセスで spawn するため Bash セッション内 export を継承しない。C08 run-scoping のアクティブ化は `.esb-authz` / `.esb-verdict` ディレクトリ検出が正 (R1 冒頭の `authz-classify.py` 単一 Python 呼びが親dirごと作成する)。`ESB_RUN=1` はセッション起動時 env としてのみ有効。
- **`.esb-authz` を手作業で先行作成しない**: 空dirだけがあるとhookがアクティブ化し、evidence producerであるC12をevidence不在として遮断しうる。bootstrapは親dirを原子的に用意する `authz-classify.py` の単一Python呼びで行う。
- **MCP を使わない (browser 観測は progressive enhancement)**: 本 skill は外部 MCP 接続を持たず、WebFetch + C09 静的 HTTP snapshot を baseline 観測とする。JS 実行後 DOM・画面遷移・screenshot・computed style は C15 `browser-render.py` (MCP 非依存のローカル headless Chrome via Bash) で取得を試み、ブラウザ不在 (exit 3=browser-unavailable) 時のみこれらを `observation_gap` (blocked) として記録する (無言欠落禁止・inference へ昇格させない)。
- **per-run 予算は out-dir 単位**: 別 out-dir で再実行すると request budget は新規に始まる。ただし瞬間負荷レバー (並列 1・最小間隔・Retry-After・停止条件) は out-dir 非依存で常に不変。
- **verdict receipt は cwd 相対既定**: `${ESB_VERDICT_DIR:-.esb-verdict}` は cwd 起点なので、C02 の品質評価 verdict 発行と C01 の品質判定参照は同一 cwd で回す (cwd が変わると receipt 不在=fail-closed で品質判定が読めない)。

## Additional Resources

- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/` — `authz-classify.py` (C12) / `fetch-snapshot.py` (C09) / `doc-emit.py` (C11) / `mermaid-validate.py` (C10)
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/agents/` — `frontend-surface-analyzer` (C03) / `backend-inference-analyzer` (C04) / `uiux-rationale-analyzer` (C05) / `content-intent-analyzer` (C13) / `architecture-essence-synthesizer` (C06)
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/pre-fetch-authz-guard.py` (C08) — fetch-authz 単一述語の fail-closed hook (matcher=`Bash|WebFetch`)
- `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/schemas/` — `fact-inference-confidence.schema.json` / `system-blueprint.schema.json` (横断データ契約)
- `prompts/R1-fetch.md`〜`R3-document.md` — 責務プロンプト (7 層)
