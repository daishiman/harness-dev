---
name: run-task-graph-demo
description: engine:task-graph 変種 (依存順駆動 + self-reflect) の配線実例。Use when 依存グラフ順に checklist を自律消費する生成ハーネスを参照するとき。
kind: run                              # ref | run | wrap | assign | delegate （atomic は旧仕様）
effect: local-artifact
role_suffix: workflow
hierarchy_level: L1        # L0 | L1 | L2
owner: team-skills
since: 2026-07-11
rubric_refs: []
# goal-seek: 固定手順を持たず Goal+Checklist へ向けて反復する。engine 既定は task-graph (依存順駆動)。反復ループは fork で分離 context に切り出し親へ最終差分のみ返す(2軸は独立)。
goal_seek:
  engine: task-graph
  engine_profile: checklist-graph  # planner の full task-spec graph と非同等 (縮小 profile)
  full_task_spec_graph: false  # fail-closed capability claim。gap 一覧は build-plan.capability_gaps 参照
  spec: eval-log/goal-spec.json                       # 任意。あればロードして利用、無ければ AI が文脈から推定
  progress: eval-log/run-task-graph-demo-progress.json     # schemas/goal-seek-loop.schema.json 準拠
  intermediate: eval-log/run-task-graph-demo-intermediate.jsonl  # 各周回末に append: original_goal/current_goal_snapshot/delta/merged_directive (ドリフト圧縮アンカー)
  max_loops: 5
  fork: subagent        # subagent(既定/反復を分離contextで実行し親へ最終差分のみ) | agent-team | inline(軽量単発のみ opt-down)
# doc/21 source-traceability
source: run-build-skill/references/goal-seek-paradigm.md
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
# permissions: 副作用ありスキルは settings.json の permissions.deny に明示禁止を書くこと（設計書04章）
# PreToolUse hook: 文脈依存の危険検査を hook で追加（二段防御）。
---

# run-task-graph-demo

## 目的と出力契約
依存順 (`depends_on`) に checklist を消費し、発見タスクを self-reflect で追記しながら ゴール達成まで反復する engine:task-graph 変種の実例。成果物は `eval-log/run-task-graph-demo-progress.json` の全 item done + `status: completed`。

## 境界
本 Skill は engine:task-graph 変種の配線例であり、別状態ファイル (task-graph.json 相当) を新設しない。progress.json checklist と intermediate.jsonl のみを唯一の truth とする。

checklist-graph profile が planner (plugin-dev-planner) の task-graph 機構と**同型な範囲**: 依存順拘束消費 (ready 集合の機械算出)・self-reflect による発見タスクの自己追記・トレース不在を違反とする機械検査・capability graph の knowledge 記録。**非同等な範囲** (= `full_task_spec_graph: false` の根拠) は build-plan `capability_gaps` の 4 項と 1:1 対応する: task-spec 実体グラフ (task-spec-artifact-graph)・write_scope 付き並列 dispatch (parallel-ready-set-dispatch-with-write-scope)・実行 envelope と状態投影 (execution-envelope-state-projection)・discovered-task の仕様改善外ループ (discovered-task-spec-improvement-outer-loop)。この 4 項の harness 側消費が全部実装されたときのみ profile 昇格を検討する (それまで claim は false 固定)。

## 主要ルール
1. ready 集合の最小 id item のみを拘束選択する (任意選択でなく依存順が拘束)。
2. item 完了時は progress.json に `status: done` をその場で記述してから次周回へ進む。
3. 各周回末に intermediate.jsonl へ `ready_set`/`selected_item` を必須追記する。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。
> ループを多周回す／重い試行錯誤を伴う場合は、親セッションを汚さないよう SubAgent（`Agent`）または Agent Team に fork して実行し、親へは最終成果物と要約のみ返す（同 references「コンテキスト分離」）。

### ゴール (Goal)
`eval-log/run-task-graph-demo-progress.json` の全 checklist item が依存順に done 化され `status: completed` になっている。

### 目的・背景 (Why)
固定手順ではなく依存充足順に自律消費する task-graph 変種を、生成ハーネス単体で再現可能な形で示すための最小実例。

### 完了チェックリスト (Checklist)
- [ ] C1: `eval-log/run-task-graph-demo-progress.json` を `goal-seek-loop.schema.json` 準拠で読み込み `engine: task-graph` を記録している
- [ ] C2: `ready-set-from-checklist.py` の返す ready 集合の最小 id item のみを選択している (依存順消費・C1 完了が前提)
- [ ] C3: 選択 item 実行後に progress.json の該当 item を `status: done` へ記述している (C2 完了が前提)
- [ ] C4: 全 checklist item が done で `status: completed` を宣言し pending/blocked を残さない (C3 完了が前提)

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成（固定化禁止）→ 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。

### ゴールシーク配線（実行可能機構）
本 Skill のループは散文だけでなく実行可能機構として配線される。ユーザーの悩み（要望）をゴールに変換し、達成まで自律ループを回す:

- **goal-spec**: `eval-log/goal-spec.json` があればロードして利用する（spec schema が同梱されていれば検証、無ければそのまま利用）。無ければ既存コンテキスト（直近依頼・制約・対象ファイル）から AI が最適ゴール+完了チェックリストを推定生成する（ユーザーへの追加質問は原則しない）。
- **周回状態**: 各周回で `eval-log/run-task-graph-demo-progress.json`（`run-build-skill/schemas/goal-seek-loop.schema.json` 準拠）に `iteration` / 各 checklist 項目 `{id,text,status}` / `open_issues` を記録する。
- **コンテキスト分離（fork 軸）**: 反復ループは既定で SubAgent（`Agent`）に分離して実行し、親には最終成果物と `handoff-*.json` 要約のみ返す（中間試行で親 context を汚さない）。`fork: inline` は軽量単発時の opt-down。なお重い周回で `engine: run-goal-seek`（同梱時のみ）を使うのは外部依存軸の任意最適化で、fork 分離とは独立（`references/goal-seek-paradigm.md`「コンテキスト分離」）。
- **中間成果物アンカー (ドリフト圧縮)**: 各周回末に `eval-log/run-task-graph-demo-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を 1 行追記する。`original_goal` は全周回で**不変**。次周回 Step2 (手順生成) は直前の `merged_directive_for_next` と `original_goal` を**必須入力**として読み込み、AI が単独で再導出しない。これにより固定手順なしの自由度を保ちつつ、AI が確率的最尤の抽象解へ集約化していくドリフトをアンカーで毎周回押し戻す (`references/goal-seek-paradigm.md`「中間成果物」)。
- **drift_signal** (enum 6 値、schema 必須): `initial` (iteration=0 のみ・前周回無し) / `aligned` (差分ゼロ) / `compressing` (縮んでいる・継続) / `stagnant` (2 周連続変化なし・アプローチ転換) / `widening` (広がっている・差し戻し検討) / `oscillating` (正負反転・打ち切り検討)。判定主体はループ実行 SubAgent (fork 内自己評価)、判定タイミングは Step4 検証後・Step5 反復判定前。
- **打ち切り**: `goal_seek.max_loops`（既定 5）到達でも未達、または `drift_signal: stagnant`/`widening`/`oscillating` が 2 周連続なら、残項目と差分を `open_issues` に記録し人間 or 上位 orchestrator へ差し戻す。

> この配線により、本 Skill は配布先のどの環境でも「ゴールへ向けて自動でループを回す」挙動を同じ機構で再現する。

### ゴールシーク検証（機械検査）
ループ完了時、`eval-log/run-task-graph-demo-intermediate.jsonl` の整合を機械検査する。本検査は `run-goal-seek/SKILL.md` と同型 (中間成果物アンカー機構の SSOT、`references/goal-seek-paradigm.md` 「中間成果物」)。量産スキルでも同じ機構で再現性 100% を担保する。

```bash
# NOTE: この汎用アンカー検査は render-combinators.py が with-goal-seek へ注入する機械検査と同型。
# 正本は run-goal-seek/SKILL.md の同節にあり、ここでは例示のため要点のみを再構成する (詳細ロジックは正本を参照)。
python3 - "$PWD/eval-log/run-task-graph-demo-progress.json" "$PWD/eval-log/run-task-graph-demo-intermediate.jsonl" <<'PY'
import json, sys, os, hashlib
prog_path, inter_path = sys.argv[1], sys.argv[2]
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
required_keys = {"iteration", "original_goal", "merged_directive_for_next", "drift_signal"}  # 各 intermediate 行の必須キー
if not os.path.exists(inter_path):
    print("intermediate.jsonl 未生成 (ループ未実行)"); sys.exit(0)
rows = [json.loads(x) for x in open(inter_path, encoding="utf-8").read().splitlines() if x.strip()]
assert rows, "intermediate.jsonl が空"
anchor = rows[0]["original_goal"]  # 不変アンカー (周回で変わらない)
for idx, row in enumerate(rows):
    assert not (required_keys - row.keys()), f"intermediate[{idx}] 必須キー不足"
    assert row["original_goal"] == anchor, f"intermediate[{idx}] anchor 不変性違反"
expected_hash = hashlib.sha256(anchor.encode()).hexdigest()
assert prog.get("original_goal_hash") in (None, expected_hash), "original_goal_hash drift"
print(f"intermediate 検査 OK: {len(rows)} 行 / anchor 不変 / hash 一致")
PY
```

### ゴールシーク配線（task-graph 変種）
`goal_seek.engine: task-graph` の場合のみ、上記 base ループの Step1「未達 `[ ]` を任意特定」を次の拘束的 Step へ**上書き置換**する（`engine: inline` は従来どおり任意選択のまま）:

- 各周回の冒頭で同梱スクリプト `scripts/ready-set-from-checklist.py eval-log/run-task-graph-demo-progress.json` を実行し `{"ready":[...]}` を得る。
- 返った ready 集合の**最小 id item のみ**を次の実行対象として選ぶ（依存充足順が「助言」でなく「拘束」になる）。ready が空なら全 done か blocked のみ＝ループ終了判定へ。
- 実行中に新たな未網羅タスクを発見したら `scripts/self-reflect-append.py eval-log/run-task-graph-demo-progress.json --id <新id> --text <達成条件> --depends-on <...>` で checklist 末尾へ追記する（別状態ファイルを新設せず progress.json を唯一の truth に保つ）。追記 item は done-judge が毎回スキャンする同一配列に入るため反映漏れが構造的に発生しない。
- item 完了時は必ず progress.json の該当 item を `status: done` へ**その場で記述**してから次周回へ進む。この done 記述そのものが次周回 `ready-set-from-checklist.py` 再計算の入力＝**次 item の発火条件**である（完了記述→ready 再計算→次 item 発火の連鎖で依存グラフを進行させる）。記述漏れは後続 item が永遠に ready にならない形で顕在化する。
- `goal_seek.max_loops` は **checklist item 数＋self-reflect 追記余裕以上**（目安: item 数×1.5）に設定する。1 周回 1 item 消費と消費完全性の拘束下では done 化できる item 数 ≤ 周回数 ≤ max_loops のため、bound 不足は completed を構造的に不能にする。不足のまま max_loops へ到達したら handed_off で差し戻し、上位が max_loops を引き上げて再入する。
- progress.json に `engine: task-graph` を**必ず記録**する（runtime 検査が engine 値で task-graph 変種を判別し、トレース不在を『拘束違反』として絶対検査するため）。
- 各周回末に `eval-log/run-task-graph-demo-intermediate.jsonl` の周回エントリへ `ready_set`（算出時点の ready 集合）と `selected_item`（実際に選択・実行した id）を**必須で追記**する（依存順消費の唯一の証跡・別状態ファイルを新設しない）。engine:task-graph でこのトレースを書かない harness は下記機械検査が exit1 で落とす（沈黙による回避を封鎖）。

### ゴールシーク検証（task-graph 変種・機械検査）
`engine: task-graph` のループ完了時、intermediate.jsonl の `ready_set`/`selected_item` トレースを読み、**依存順消費**と self-reflect 完了 gate を機械検査する。検証は自己申告 `ready_set` の内部整合に留めず**選択列そのものから依存順を実証**する（助言でなく拘束）。**absence-as-violation**: engine が task-graph なのに intermediate.jsonl 未生成／`ready_set`/`selected_item` トレースが 1 行も無い場合は exit1（沈黙による依存順消費の回避を封鎖）。加えて (1) `depends_on` closure（全依存先が checklist 内 id で解決可能・dangling 封鎖）と非循環（cycle は永久 unready=沈黙 stall を招くため封鎖）、(2) `selected_item` 非空の周回は `ready_set` 非空かつ `selected_item` が `ready_set` の最小 id と一致、(3) 選択 item の `depends_on` が全て**より前の周回で選択済**、(4) 消費完全性（status==done の全 item が最低 1 周回で `selected_item` として出現）、(5) `completed` 宣言時は pending も blocked も残さない、(6) `max_loops < checklist item 数` の bound 不足（completed 構造的不能）を早期診断、を検査する。

```bash
python3 - "$PWD/eval-log/run-task-graph-demo-progress.json" "$PWD/eval-log/run-task-graph-demo-intermediate.jsonl" <<'PY'
import json, sys, os, re
prog_path, inter_path = sys.argv[1], sys.argv[2]
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
engine = prog.get("engine")
checklist = prog.get("checklist", [])
ids = {it.get("id") for it in checklist}
deps_of = {it.get("id"): list(it.get("depends_on") or []) for it in checklist}
# depends_on closure: 初期 checklist を含む全 item の depends_on が checklist 内 id で解決可能か (dangling 封鎖)
for it in checklist:
    for dep in (it.get("depends_on") or []):
        assert dep in ids, f"checklist item {it.get('id')} の depends_on '{dep}' が checklist 内に不在 (dangling・永遠に ready にならない)"
if engine != "task-graph":
    print("engine!=task-graph: task-graph 消費検査は非適用 (inline/run-goal-seek)"); sys.exit(0)
# bound 不足診断: 1周回1item消費では done 化 item 数 ≤ max_loops。checklist が超過すると completed 構造的不能。
max_loops = prog.get("max_loops")
if isinstance(max_loops, int) and len(checklist) > max_loops and prog.get("status") != "completed":
    print(f"WARN: checklist {len(checklist)} item > max_loops {max_loops} — 1周回1item消費では completed 構造的不能 (bound 不足)。max_loops を item 数×1.5 目安へ引き上げ再入すること", file=sys.stderr)
# 非循環検査 (iterative DFS・深い鎖でも recursion 上限非依存): cycle は永久に ready にならず沈黙 stall を招くため fail-closed。
WHITE, GREY, BLACK = 0, 1, 2
color = {i: WHITE for i in ids}
for start in list(ids):
    if color[start] != WHITE:
        continue
    stack = [(start, list(deps_of.get(start, [])))]; color[start] = GREY
    while stack:
        node, pend_deps = stack[-1]
        if pend_deps:
            d = pend_deps.pop()
            if color.get(d, BLACK) == GREY:
                raise AssertionError(f"checklist の depends_on が循環 (永久に ready にならない): {node} -> {d}")
            if color.get(d, BLACK) == WHITE:
                color[d] = GREY; stack.append((d, list(deps_of.get(d, []))))
        else:
            color[node] = BLACK; stack.pop()
# absence-as-violation: task-graph は依存順消費の証跡が必須。不在は拘束違反 (exit1)。
assert os.path.exists(inter_path), "engine:task-graph だが intermediate.jsonl 未生成 (依存順消費の証跡なし=拘束違反)"
lines = [json.loads(l) for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
traced = [e for e in lines if "ready_set" in e and "selected_item" in e]
assert traced, "engine:task-graph だが ready_set/selected_item トレースが 1 行も無い (沈黙による依存順消費の回避=拘束違反)"
num = re.compile(r"^C(\d+)$")
def key(i):
    m = num.match(i); return (0, int(m.group(1)), i) if m else (1, 0, i)
selected_seq = []
for idx, e in enumerate(traced):
    ready = e["ready_set"]; sel = e["selected_item"]
    if sel:
        # 空 ready_set 申告での検査回避を封鎖 (selected があるなら ready は非空でなければならない)
        assert ready, f"周回{idx}: selected_item={sel} だが ready_set が空 (依存順消費違反=検査回避)"
        min_id = sorted(ready, key=key)[0]
        assert sel == min_id, f"周回{idx}: selected_item={sel} != ready 最小 id {min_id} (依存順消費違反)"
        # 選択列で依存順を実証: 選択 item の depends_on は全てより前の周回で選択済 (自己申告 ready に依存しない拘束)
        for d in deps_of.get(sel, []):
            assert d in selected_seq, f"周回{idx}: selected_item={sel} の depends_on '{d}' が未選択のまま選択された (依存順消費違反)"
        selected_seq.append(sel)
# 消費完全性: status==done の全 item が最低 1 周回で selected_item として現れる (選択証跡なき done を封鎖)
sel_set = set(selected_seq)
undone = [it["id"] for it in checklist if it.get("status") == "done" and it["id"] not in sel_set]
assert not undone, f"依存順消費違反: done だが selected_item 証跡が無い item: {undone} (消費完全性)"
# self-reflect 完了 gate: completed 宣言は pending も blocked も残さない (追記 item が done まで全体 done を gate)
unfinished = [it["id"] for it in checklist if it.get("status") in ("pending", "blocked")]
if prog.get("status") == "completed":
    assert not unfinished, f"self-reflect 完了 gate 違反: completed だが未完了 (pending/blocked) 残: {unfinished}"
print(f"task-graph 消費検査 OK: {len(traced)} トレース周回 / 依存順消費 (選択列実証) / 消費完全性 / self-reflect 完了 gate / depends_on closure・非循環")
PY
```

### dependency graph knowledge consult
`engine: task-graph` 指定時、生成先 `scripts/` に依存グラフ抽出・記録の 2 スクリプトを同梱し、各 surface（skill / slash-command / sub-agent / script）の実行前判断で dependency graph knowledge を consult する（checklist の実行順とは別レイヤの派生判断・単一truth状態と分離）:

- **同梱**: `templates/task-graph-engine/scripts/extract-capability-dependency-graph.py`（C06）と `record-capability-graph-knowledge.py`（C07）を生成先 `scripts/` へコピーする。
- **抽出**: `scripts/extract-capability-dependency-graph.py <harness_dir>` で surface 横断の dependency graph JSON（nodes/edges/gaps・未知参照は fail-closed）を得る。
- **記録**: `scripts/record-capability-graph-knowledge.py <graph.json> --target-knowledge-dir knowledge/` で Loop A（生成 harness）へ、`--harness-knowledge-dir` 指定時は Loop B（harness-creator）へ `source_ref` 付き entry を append/merge する（既存 entry 不変）。
- **consult**: 各 surface は着手前に dependency graph knowledge を参照し、依存先が未完成 / dangling の surface を先に着手しない。

> engine:task-graph 変種は progress.json checklist を唯一の truth とし、ready 算出・self-reflect 追記・依存グラフ knowledge のいずれも別状態ファイルを新設しない（単一truth原則）。

## 検証
同梱の task-graph 消費検査 bash (下記ゴールシーク検証節) が intermediate.jsonl の `ready_set`/`selected_item` トレースから依存順消費・消費完全性・self-reflect 完了 gate を 機械検査し exit0 を返す。

## 注意点
- `max_loops` は checklist item 数 × 1.5 目安以上に設定する (bound 不足は completed 構造的不能)。
- intermediate.jsonl を書かない harness は消費検査が exit1 で落とす (absence-as-violation)。

## 変数化契約
`skill_name` = run-task-graph-demo。progress/intermediate パスは `eval-log/run-task-graph-demo-*` に固定。

## 追加リソース
- `references/`
- `references/goal-seek-paradigm.md`「engine 変種 (task-graph)」
- `templates/task-graph-engine/scripts/` (ENG-C01/C02/C06/C07 の 4 script 原本)

## セキュリティと権限
本Skillは副作用を伴う可能性がある。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。
