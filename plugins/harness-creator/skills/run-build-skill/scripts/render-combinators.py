#!/usr/bin/env python3
# /// script
# name: render-combinators
# purpose: Compose an atomic SKILL.md template from _base.md and combinator patch selections.
# inputs:
#   - argv: --kind, optional flags, --templates-dir, --output
#   - argv: --brief <skill-brief.json> --materialize-task-graph-engine <skill-dir>
# outputs:
#   - stdout: composed SKILL.md when --output is omitted
#   - file: composed SKILL.md when --output is provided
#   - files: task-graph template copies + machine-readable SKILL.md profile (materialize mode)
#   - stderr: validation errors
#   - exit: 0=OK / 1=composition error / 2=usage error
# contexts: [A, B, C]
# network: false
# write-scope: output-arg-only / materialize mode の <skill-dir>/{SKILL.md,scripts/*}
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Compose run-build-skill atomic templates from _base.md and combinators.

The repository keeps combinators as unified diff files for reviewability. This
tool makes that route executable for mass production by applying the selected
kind combinator plus optional flag combinators in the documented order.
"""
from __future__ import annotations

import argparse
import json
import shutil
import re
import sys
from pathlib import Path


# dogfooding 除外境界の正本は repo-root scripts/feedback_contract_ssot.py (単一 SSOT)。
# apply_feedback_loop の配備除外を、散在リテラルでなく SSOT 述語へ委譲する。
#
# 解決順: (a) env CLAUDE_PLUGIN_ROOT/scripts → (b) 上方探索 (vendored plugin 内コピーを
# dev/install 双方で発見) → (c) 全滅時は最小 fallback。**絶対に raise しない**
# (build-time に plugin 単独 install されても import-time クラッシュさせない)。
import os


def _load_feedback_contract_ssot():
    """feedback_contract_ssot を fail-soft に解決する (絶対に raise しない)。"""
    import importlib.util

    candidates: list[Path] = []
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidates.append(Path(plugin_root) / "scripts" / "feedback_contract_ssot.py")
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidates.append(ancestor / "scripts" / "feedback_contract_ssot.py")
    for cand in candidates:
        try:
            if cand.is_file():
                spec = importlib.util.spec_from_file_location("feedback_contract_ssot", cand)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                return mod
        except Exception:
            continue
    return _fallback_feedback_contract_ssot()


def _fallback_feedback_contract_ssot():
    """SSOT 全滅時の最小 fallback。render-combinators が使う述語のみ提供。

    自プラグイン名を __file__ パス (plugins/<self>/skills/<skill>/scripts/) から
    導出し、判定用リテラルを直書きせず変数比較する (配備除外判定は「対象が自プラグイン
    自身か」であり self-derive が意味的に正しい)。SSOT 実装と同値で drift せず、散在
    リテラル禁止 (test_dogfooding_boundary) も満たす。vendored コピーが常在するため
    通常ここには到達しない (最終安全弁)。
    """
    import types

    self_plugin = Path(__file__).resolve().parents[3].name
    fc = types.SimpleNamespace()
    fc.SELF_DOGFOODING_PLUGIN = self_plugin
    fc.is_feedback_deploy_exempt = lambda plugin: plugin == self_plugin
    return fc


_FC = _load_feedback_contract_ssot()


KIND_PATCHES = {
    "run": "with-run.patch",
    "ref": "with-ref.patch",
    "wrap": "with-wrap.patch",
    "delegate": "with-delegate.patch",
}

FLAG_PATCHES = {
    "with_evaluator": "with-evaluator.patch",
    "with_hooks": "with-hooks.patch",
    "with_subagent": "with-subagent.patch",
    "with_knowledge": "with-knowledge.patch",
}

# goal-seek 配線を default-ON で注入する loop 実行系 kind。
# assign(評価系=一発採点でループしない) と ref(read-only) は対象外。
GOAL_SEEK_KINDS = ("run", "wrap", "delegate")

TASK_GRAPH_ENGINE_SCRIPTS = (
    "ready-set-from-checklist.py",
    "self-reflect-append.py",
    "extract-capability-dependency-graph.py",
    "record-capability-graph-knowledge.py",
)


FEEDBACK_CONTRACT_KINDS = ("run", "wrap", "delegate")


FEEDBACK_CONTRACT_FM_BLOCK = (
    "# feedback_contract: 量産先 Skill が携帯する per-skill 評価基準。"
    "criteria は brief.goal / Checklist から導出し、content-review の criteria_evaluated と突合する。\n"
    "feedback_contract:\n"
    "  max_iterations: {{feedback_contract_max_iterations | default(3)}}\n"
    "  criteria:\n"
    "    - id: IN1\n"
    "      loop_scope: inner\n"
    "      text: {{feedback_contract_inner_criteria_text}}\n"
    "      verify_by: lint\n"
    "    - id: OUT1\n"
    "      loop_scope: outer\n"
    "      text: {{feedback_contract_outer_criteria_text}}\n"
    "      verify_by: elegant-review"
)


FEEDBACK_CONTRACT_SECTION = (
    "## 評価・改善ループ契約\n"
    "`feedback_contract.criteria` は本 Skill 固有の完了チェックリストから導出した評価基準である。"
    "inner は現在ゴールを満たす小さな検証、outer はユーザー目的と 4 条件を満たす全体検証を担う。"
    "content-review / evaluator / hook は同じ criteria id を参照し、"
    "`criteria_evaluated` が全 id を覆うまで PASS にしない。"
    "未達時は最大 `feedback_contract.max_iterations` 周まで改善→再評価し、"
    "超過時は `INCOMPLETE` として human_review に差し戻す。"
)


# with-knowledge.patch の決定論的注入内容。配布スキルが自己完結するよう、
# harness-creator 内部 (ref-knowledge-loop / templates/ / Loop B / --dir) への参照を一切含めない。
KNOWLEDGE_FM_BLOCK = (
    "# knowledge-loop: 蓄積/検索/§12フィードバックを組み込む。"
    "検索・追加・記録・整合性検証は本 Skill 同梱の scripts/ で完結する (外部ツール不要)。\n"
    "knowledge_loop:\n"
    "  pattern: {{knowledge_loop.pattern}}       # index-search | router-registry\n"
    "  index: knowledge/knowledge-index.json     # router-registry 型は knowledge/router.json\n"
    "  usage_log: knowledge/usage-log.jsonl\n"
    "  consult_at: {{knowledge_loop.consult_at | default([\"runtime\"])}}"
)

KNOWLEDGE_SECTION = (
    "## ナレッジループ\n"
    "本 Skill は `knowledge/` に蓄積した知見を実行時に検索し、活用結果を記録して品質を自己改善する。"
    "検索・追加・記録・整合性検証はすべて本 Skill 同梱の `scripts/` だけで完結し、外部ツールやメタリポジトリへの依存はない。\n\n"
    "### 構造（pattern: {{knowledge_loop.pattern}}）\n"
    "- `knowledge/knowledge-index.json`（index-search 型）/ `knowledge/router.json` + `registry.json`（router-registry 型）。"
    "いずれも `consult_at: [\"runtime\"]` を宣言する。\n"
    "- 各エントリは必須6フィールド `id / title|content / intent|purpose / background / keywords|tags / source` を満たす。"
    "整合性 (ID重複・必須欠落) は `scripts/build_index.py --stats` で検証する。\n\n"
    "### 検索（決定論段 → AI段）\n"
    "1. `scripts/search_knowledge.py --query \"<query>\" --limit 5`"
    "（Stage1 カテゴリ絞り込み + Stage2 重み付きスコアリング・決定論・100%再現）。\n"
    "2. 上位 N 件を文脈に照らして取捨選択する（AI判断）。\n\n"
    "### 知見の追加（日々の更新）\n"
    "- `scripts/add_entry.py --category <id> --id <eid> --title \"...\" --intent \"...\" "
    "--background \"...\" --keywords \"k1,k2,...\" --source \"<出典>\"` で追加する。"
    "必須6フィールドを検証して追記するため JSON の手編集は不要。"
    "誤ったストアへの追加はストアの `consult_at` 不一致として拒否される。\n\n"
    "### §12 フィードバックループ（使うほど良くする）\n"
    "- 検索→活用のたびに `scripts/record_usage.py --record --query ... --matched-ids ... "
    "--used-ids ... --satisfaction helpful|neutral|unhelpful` で `knowledge/usage-log.jsonl` に追記。\n"
    "- 定期的に `scripts/record_usage.py --analyze --emit-queue brushup-queue.jsonl` で"
    "「マッチするが使われない」「unhelpful 多発」等を検出してキュー化し、"
    "`--mark-needs-update` で該当エントリに status を付与、title/keywords/background を改善する。\n\n"
    "### ライフサイクル\n"
    "- 1ファイル 500行 または 25エントリ超でサブトピック分割（`scripts/build_index.py --stats` で監視）。\n"
    "- router-registry 型は `registry.json` の status（pending / processed / needs-update / deprecated）で素材の再同期を追跡。\n\n"
    "> このナレッジループは本 Skill 単体で完結する。配布先のどの環境でも、"
    "追加・更新・検索・記録が同梱 `scripts/` だけで同じ手順で行える。"
)


# with-goal-seek.patch の決定論的注入内容。loop 実行系 (run/wrap/delegate) は _base.md が
# 継承する `## ゴールシーク実行` 散文に加えて、ループを「実行可能な機構」として配線する:
# goal-spec のロード / 周回 progress JSON / 打ち切り規約。
# 重要 (self-contained): ループ本体は本 Skill 内の AI 推論で自己完結し、外部スキルへの依存を持たない。
# run-goal-seek は「重い周回時の任意の最適化手段」であり必須ではない (with-knowledge と同じ自己完結原則)。
GOAL_SEEK_FM_BLOCK = (
    "# goal-seek: 固定手順を持たず Goal+Checklist へ向けて反復する。engine 既定は task-graph (依存順駆動)。"
    "反復ループは fork で分離 context に切り出し親へ最終差分のみ返す(2軸は独立)。\n"
    "goal_seek:\n"
    "  engine: {{goal_seek.engine | default(\"task-graph\")}}      # task-graph(既定/依存順駆動+self-reflect・生成harnessに task-graph-engine 同梱) | inline(opt-down/自己完結・外部スキル不要) | run-goal-seek(同梱時のみ任意で使う重量オーケストレータ)\n"
    "  engine_profile: {{goal_seek.engine_profile | default(\"checklist-graph\")}}  # task-graph(既定)=checklist-graph 固定 (planner full task-spec graph と同等ではない) / inline・run-goal-seek=goal-loop\n"
    "  full_task_spec_graph: false                         # 現 profile の fail-closed capability claim\n"
    "  spec: eval-log/goal-spec.json                       # 任意。あればロードして利用、無ければ AI が文脈から推定\n"
    "  progress: eval-log/{{skill_name}}-progress.json     # schemas/goal-seek-loop.schema.json 準拠\n"
    "  intermediate: eval-log/{{skill_name}}-intermediate.jsonl  # 各周回末に append: original_goal/current_goal_snapshot/delta/merged_directive (ドリフト圧縮アンカー)\n"
    "  max_loops: {{goal_seek.max_loops | default(5)}}\n"
    "  fork: {{goal_seek.fork | default(\"subagent\")}}        # subagent(既定/反復を分離contextで実行し親へ最終差分のみ) | agent-team | inline(軽量単発のみ opt-down)"
)

# _base.md の `### ゴールシークループ` 直後に挿入する実行配線サブセクション。
GOAL_SEEK_LOOP_ANCHOR = (
    "1. 未達 `[ ]` を特定 → 2. 手順を都度生成（固定化禁止）→ 3. 実行 → "
    "4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。"
)

# engine:task-graph 変種の配線サブセクション (route C03)。engine==task-graph 分岐に限り base ループ
# Step1 を「ENG-C01 で ready 集合を算出→最小 id item を拘束的に選択・実行」へ上書き置換し (inline は
# 従来どおり任意選択)、依存順消費と self-reflect 完了 gate を intermediate.jsonl トレースで機械検査
# する。加えて ENG-C06/ENG-C07 (cross-surface dependency graph knowledge) を同梱し各 surface の consult を
# 配線する。別状態ファイル (task-graph.json 相当) は新設せず progress.json / intermediate.jsonl を
# 唯一の truth に保つ (単一truth原則・H3/H4/H6)。
GOAL_SEEK_TASK_GRAPH_SECTION = (
    "### ゴールシーク配線（task-graph 変種）\n"
    "`goal_seek.engine: task-graph` の場合のみ、上記 base ループの Step1「未達 `[ ]` を任意特定」を"
    "次の拘束的 Step へ**上書き置換**する（`engine: inline` は従来どおり任意選択のまま）:\n\n"
    "- 各周回の冒頭で同梱スクリプト `scripts/ready-set-from-checklist.py "
    "eval-log/{{skill_name}}-progress.json` を実行し `{\"ready\":[...]}` を得る。\n"
    "- 返った ready 集合の**最小 id item のみ**を次の実行対象として選ぶ（依存充足順が「助言」でなく"
    "「拘束」になる）。ready が空なら全 done か blocked のみ＝ループ終了判定へ。\n"
    "- 実行中に新たな未網羅タスクを発見したら `scripts/self-reflect-append.py "
    "eval-log/{{skill_name}}-progress.json --id <新id> --text <達成条件> --depends-on <...>` で "
    "checklist 末尾へ追記する（別状態ファイルを新設せず progress.json を唯一の truth に保つ）。追記 "
    "item は done-judge が毎回スキャンする同一配列に入るため反映漏れが構造的に発生しない。\n"
    "- item 完了時は必ず progress.json の該当 item を `status: done` へ**その場で記述**してから次周回へ"
    "進む。この done 記述そのものが次周回 `ready-set-from-checklist.py` 再計算の入力＝**次 item の"
    "発火条件**である（完了記述→ready 再計算→次 item 発火の連鎖で依存グラフを進行させる）。記述漏れは"
    "後続 item が永遠に ready にならない形で顕在化する。\n"
    "- `goal_seek.max_loops` は **checklist item 数＋self-reflect 追記余裕以上**（目安: item 数×1.5）に"
    "設定する。1 周回 1 item 消費と消費完全性の拘束下では done 化できる item 数 ≤ 周回数 ≤ max_loops "
    "のため、bound 不足は completed を構造的に不能にする。不足のまま max_loops へ到達したら "
    "handed_off で差し戻し、上位が max_loops を引き上げて再入する。\n"
    "- progress.json に `engine: task-graph` を**必ず記録**する（runtime 検査が engine 値で "
    "task-graph 変種を判別し、トレース不在を『拘束違反』として絶対検査するため）。\n"
    "- 各周回末に `eval-log/{{skill_name}}-intermediate.jsonl` の周回エントリへ `ready_set`"
    "（算出時点の ready 集合）と `selected_item`（実際に選択・実行した id）を**必須で追記**する"
    "（依存順消費の唯一の証跡・別状態ファイルを新設しない）。engine:task-graph でこのトレースを"
    "書かない harness は下記機械検査が exit1 で落とす（沈黙による回避を封鎖）。\n\n"
    "### ゴールシーク検証（task-graph 変種・機械検査）\n"
    "`engine: task-graph` のループ完了時、intermediate.jsonl の `ready_set`/`selected_item` トレースを"
    "読み、**依存順消費**と self-reflect 完了 gate を機械検査する。検証は自己申告 `ready_set` の内部整合に"
    "留めず**選択列そのものから依存順を実証**する（助言でなく拘束）。**absence-as-violation**: engine が "
    "task-graph なのに intermediate.jsonl 未生成／`ready_set`/`selected_item` トレースが 1 行も無い場合は "
    "exit1（沈黙による依存順消費の回避を封鎖）。加えて (1) `depends_on` closure（全依存先が checklist 内 id で"
    "解決可能・dangling 封鎖）と非循環（cycle は永久 unready=沈黙 stall を招くため封鎖）、(2) `selected_item` "
    "非空の周回は `ready_set` 非空かつ `selected_item` が `ready_set` の最小 id と一致、(3) 選択 item の "
    "`depends_on` が全て**より前の周回で選択済**、(4) 消費完全性（status==done の全 item が最低 1 周回で "
    "`selected_item` として出現）、(5) `completed` 宣言時は pending も blocked も残さない、"
    "(6) `max_loops < checklist item 数` の bound 不足（completed 構造的不能）を早期診断、を検査する。\n\n"
    "```bash\n"
    "python3 - \"$PWD/eval-log/{{skill_name}}-progress.json\" \"$PWD/eval-log/{{skill_name}}-intermediate.jsonl\" <<'PY'\n"
    "import json, sys, os, re\n"
    "prog_path, inter_path = sys.argv[1], sys.argv[2]\n"
    "prog = json.load(open(prog_path, encoding=\"utf-8\")) if os.path.exists(prog_path) else {}\n"
    "engine = prog.get(\"engine\")\n"
    "checklist = prog.get(\"checklist\", [])\n"
    "ids = {it.get(\"id\") for it in checklist}\n"
    "deps_of = {it.get(\"id\"): list(it.get(\"depends_on\") or []) for it in checklist}\n"
    "# depends_on closure: 初期 checklist を含む全 item の depends_on が checklist 内 id で解決可能か (dangling 封鎖)\n"
    "for it in checklist:\n"
    "    for dep in (it.get(\"depends_on\") or []):\n"
    "        assert dep in ids, f\"checklist item {it.get('id')} の depends_on '{dep}' が checklist 内に不在 (dangling・永遠に ready にならない)\"\n"
    "if engine != \"task-graph\":\n"
    "    print(\"engine!=task-graph: task-graph 消費検査は非適用 (inline/run-goal-seek)\"); sys.exit(0)\n"
    "# bound 不足診断: 1周回1item消費では done 化 item 数 ≤ max_loops。checklist が超過すると completed 構造的不能。\n"
    "max_loops = prog.get(\"max_loops\")\n"
    "if isinstance(max_loops, int) and len(checklist) > max_loops and prog.get(\"status\") != \"completed\":\n"
    "    print(f\"WARN: checklist {len(checklist)} item > max_loops {max_loops} — 1周回1item消費では completed 構造的不能 (bound 不足)。max_loops を item 数×1.5 目安へ引き上げ再入すること\", file=sys.stderr)\n"
    "# 非循環検査 (iterative DFS・深い鎖でも recursion 上限非依存): cycle は永久に ready にならず沈黙 stall を招くため fail-closed。\n"
    "WHITE, GREY, BLACK = 0, 1, 2\n"
    "color = {i: WHITE for i in ids}\n"
    "for start in list(ids):\n"
    "    if color[start] != WHITE:\n"
    "        continue\n"
    "    stack = [(start, list(deps_of.get(start, [])))]; color[start] = GREY\n"
    "    while stack:\n"
    "        node, pend_deps = stack[-1]\n"
    "        if pend_deps:\n"
    "            d = pend_deps.pop()\n"
    "            if color.get(d, BLACK) == GREY:\n"
    "                raise AssertionError(f\"checklist の depends_on が循環 (永久に ready にならない): {node} -> {d}\")\n"
    "            if color.get(d, BLACK) == WHITE:\n"
    "                color[d] = GREY; stack.append((d, list(deps_of.get(d, []))))\n"
    "        else:\n"
    "            color[node] = BLACK; stack.pop()\n"
    "# absence-as-violation: task-graph は依存順消費の証跡が必須。不在は拘束違反 (exit1)。\n"
    "assert os.path.exists(inter_path), \"engine:task-graph だが intermediate.jsonl 未生成 (依存順消費の証跡なし=拘束違反)\"\n"
    "lines = [json.loads(l) for l in open(inter_path, encoding=\"utf-8\").read().splitlines() if l.strip()]\n"
    "traced = [e for e in lines if \"ready_set\" in e and \"selected_item\" in e]\n"
    "assert traced, \"engine:task-graph だが ready_set/selected_item トレースが 1 行も無い (沈黙による依存順消費の回避=拘束違反)\"\n"
    "num = re.compile(r\"^C(\\d+)$\")\n"
    "def key(i):\n"
    "    m = num.match(i); return (0, int(m.group(1)), i) if m else (1, 0, i)\n"
    "selected_seq = []\n"
    "for idx, e in enumerate(traced):\n"
    "    ready = e[\"ready_set\"]; sel = e[\"selected_item\"]\n"
    "    if sel:\n"
    "        # 空 ready_set 申告での検査回避を封鎖 (selected があるなら ready は非空でなければならない)\n"
    "        assert ready, f\"周回{idx}: selected_item={sel} だが ready_set が空 (依存順消費違反=検査回避)\"\n"
    "        min_id = sorted(ready, key=key)[0]\n"
    "        assert sel == min_id, f\"周回{idx}: selected_item={sel} != ready 最小 id {min_id} (依存順消費違反)\"\n"
    "        # 選択列で依存順を実証: 選択 item の depends_on は全てより前の周回で選択済 (自己申告 ready に依存しない拘束)\n"
    "        for d in deps_of.get(sel, []):\n"
    "            assert d in selected_seq, f\"周回{idx}: selected_item={sel} の depends_on '{d}' が未選択のまま選択された (依存順消費違反)\"\n"
    "        selected_seq.append(sel)\n"
    "# 消費完全性: status==done の全 item が最低 1 周回で selected_item として現れる (選択証跡なき done を封鎖)\n"
    "sel_set = set(selected_seq)\n"
    "undone = [it[\"id\"] for it in checklist if it.get(\"status\") == \"done\" and it[\"id\"] not in sel_set]\n"
    "assert not undone, f\"依存順消費違反: done だが selected_item 証跡が無い item: {undone} (消費完全性)\"\n"
    "# self-reflect 完了 gate: completed 宣言は pending も blocked も残さない (追記 item が done まで全体 done を gate)\n"
    "unfinished = [it[\"id\"] for it in checklist if it.get(\"status\") in (\"pending\", \"blocked\")]\n"
    "if prog.get(\"status\") == \"completed\":\n"
    "    assert not unfinished, f\"self-reflect 完了 gate 違反: completed だが未完了 (pending/blocked) 残: {unfinished}\"\n"
    "print(f\"task-graph 消費検査 OK: {len(traced)} トレース周回 / 依存順消費 (選択列実証) / 消費完全性 / self-reflect 完了 gate / depends_on closure・非循環\")\n"
    "PY\n"
    "```\n\n"
    "### dependency graph knowledge consult\n"
    "`engine: task-graph` 指定時、生成先 `scripts/` に依存グラフ抽出・記録の 2 スクリプトを同梱し、"
    "各 surface（skill / slash-command / sub-agent / script）の実行前判断で dependency graph knowledge を"
    " consult する（checklist の実行順とは別レイヤの派生判断・単一truth状態と分離）:\n\n"
    "- **同梱**: `templates/task-graph-engine/scripts/extract-capability-dependency-graph.py`（C06）と "
    "`record-capability-graph-knowledge.py`（C07）を生成先 `scripts/` へコピーする。\n"
    "- **抽出**: `scripts/extract-capability-dependency-graph.py <harness_dir>` で surface 横断の "
    "dependency graph JSON（nodes/edges/gaps・未知参照は fail-closed）を得る。\n"
    "- **記録**: `scripts/record-capability-graph-knowledge.py <graph.json> --target-knowledge-dir "
    "knowledge/` で Loop A（生成 harness）へ、`--harness-knowledge-dir` 指定時は Loop B"
    "（harness-creator）へ `source_ref` 付き entry を append/merge する（既存 entry 不変）。\n"
    "- **consult**: 各 surface は着手前に dependency graph knowledge を参照し、依存先が未完成 / "
    "dangling の surface を先に着手しない。\n\n"
    "> engine:task-graph 変種は progress.json checklist を唯一の truth とし、ready 算出・self-reflect "
    "追記・依存グラフ knowledge のいずれも別状態ファイルを新設しない（単一truth原則）。"
)

GOAL_SEEK_WIRING_SECTION = (
    "### ゴールシーク配線（実行可能機構）\n"
    "本 Skill のループは散文だけでなく実行可能機構として配線される。"
    "ユーザーの悩み（要望）をゴールに変換し、達成まで自律ループを回す:\n\n"
    "- **goal-spec**: `eval-log/goal-spec.json` があればロードして利用する"
    "（spec schema が同梱されていれば検証、無ければそのまま利用）。無ければ既存コンテキスト"
    "（直近依頼・制約・対象ファイル）から AI が最適ゴール+完了チェックリストを推定生成する"
    "（ユーザーへの追加質問は原則しない）。\n"
    "- **周回状態**: 各周回で `eval-log/{{skill_name}}-progress.json`"
    "（`run-build-skill/schemas/goal-seek-loop.schema.json` 準拠）に "
    "`iteration` / 各 checklist 項目 `{id,text,status}` / `open_issues` を記録する。\n"
    "- **コンテキスト分離（fork 軸）**: 反復ループは既定で SubAgent（`Agent`）に分離して実行し、"
    "親には最終成果物と `handoff-*.json` 要約のみ返す（中間試行で親 context を汚さない）。"
    "`fork: inline` は軽量単発時の opt-down。なお重い周回で `engine: run-goal-seek`（同梱時のみ）を"
    "使うのは外部依存軸の任意最適化で、fork 分離とは独立（`references/goal-seek-paradigm.md`「コンテキスト分離」）。\n"
    "- **中間成果物アンカー (ドリフト圧縮)**: 各周回末に "
    "`eval-log/{{skill_name}}-intermediate.jsonl` へ "
    "`{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を "
    "1 行追記する。`original_goal` は全周回で**不変**。次周回 Step2 (手順生成) は直前の "
    "`merged_directive_for_next` と `original_goal` を**必須入力**として読み込み、AI が単独で再導出しない。"
    "これにより固定手順なしの自由度を保ちつつ、AI が確率的最尤の抽象解へ集約化していくドリフトを"
    "アンカーで毎周回押し戻す (`references/goal-seek-paradigm.md`「中間成果物」)。\n"
    "- **drift_signal** (enum 6 値、schema 必須): `initial` (iteration=0 のみ・前周回無し) / "
    "`aligned` (差分ゼロ) / `compressing` (縮んでいる・継続) / `stagnant` (2 周連続変化なし・アプローチ転換) / "
    "`widening` (広がっている・差し戻し検討) / `oscillating` (正負反転・打ち切り検討)。"
    "判定主体はループ実行 SubAgent (fork 内自己評価)、判定タイミングは Step4 検証後・Step5 反復判定前。\n"
    "- **打ち切り**: `goal_seek.max_loops`（既定 5）到達でも未達、または "
    "`drift_signal: stagnant`/`widening`/`oscillating` が 2 周連続なら、残項目と差分を `open_issues` に記録し"
    "人間 or 上位 orchestrator へ差し戻す。\n\n"
    "> この配線により、本 Skill は配布先のどの環境でも「ゴールへ向けて自動でループを回す」挙動を同じ機構で再現する。\n\n"
    "### ゴールシーク検証（機械検査）\n"
    "ループ完了時、`eval-log/{{skill_name}}-intermediate.jsonl` の整合を機械検査する。"
    "本検査は `run-goal-seek/SKILL.md` と同型 (中間成果物アンカー機構の SSOT、"
    "`references/goal-seek-paradigm.md` 「中間成果物」)。量産スキルでも同じ機構で再現性 100% を担保する。\n\n"
    "```bash\n"
    "python3 - \"$PWD/eval-log/{{skill_name}}-progress.json\" \"$PWD/eval-log/{{skill_name}}-intermediate.jsonl\" <<'PY'\n"
    "import json, sys, os, hashlib\n"
    "prog_path, inter_path = sys.argv[1], sys.argv[2]\n"
    "prog = json.load(open(prog_path, encoding=\"utf-8\")) if os.path.exists(prog_path) else {}\n"
    "required_keys = {\"iteration\",\"original_goal\",\"current_goal_snapshot\",\"delta_from_original\",\"merged_directive_for_next\",\"drift_signal\"}\n"
    "if not os.path.exists(inter_path):\n"
    "    print(\"intermediate.jsonl 未生成 (ループ未実行)\"); sys.exit(0)\n"
    "lines = [l for l in open(inter_path, encoding=\"utf-8\").read().splitlines() if l.strip()]\n"
    "assert lines, \"intermediate.jsonl が空\"\n"
    "iters = prog.get(\"iteration\", len(lines) - 1)\n"
    "assert len(lines) == iters + 1, f\"intermediate 行数 {len(lines)} != progress.iteration+1 ({iters+1})\"\n"
    "first_anchor = None\n"
    "for i, line in enumerate(lines):\n"
    "    entry = json.loads(line)\n"
    "    missing = required_keys - entry.keys()\n"
    "    assert not missing, f\"intermediate[{i}] 必須キー不足: {missing}\"\n"
    "    if i == 0:\n"
    "        first_anchor = entry[\"original_goal\"]\n"
    "        expected_hash = hashlib.sha256(first_anchor.encode()).hexdigest()\n"
    "        actual_hash = prog.get(\"original_goal_hash\")\n"
    "        assert actual_hash is None or actual_hash == expected_hash, f\"original_goal_hash drift: progress={actual_hash} vs sha256(intermediate[0])={expected_hash}\"\n"
    "    assert entry[\"original_goal\"] == first_anchor, f\"intermediate[{i}] anchor 不変性違反\"\n"
    "print(f\"intermediate 検査 OK: {len(lines)} 行 / anchor 不変 / hash 一致\")\n"
    "PY\n"
    "```\n\n"
    + GOAL_SEEK_TASK_GRAPH_SECTION
)


class ComposeError(RuntimeError):
    """Raised when a selected combinator cannot be applied deterministically."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["run", "ref", "assign", "wrap", "delegate"])
    parser.add_argument("--role-suffix", choices=["generator", "evaluator", "workflow"], default="")
    parser.add_argument("--with-evaluator", action="store_true")
    parser.add_argument("--with-hooks", action="store_true")
    parser.add_argument("--with-subagent", action="store_true")
    parser.add_argument(
        "--with-knowledge",
        action="store_true",
        help="inject self-contained knowledge-loop block (pattern stays as {{knowledge_loop.pattern}} template var)",
    )
    parser.add_argument(
        "--no-goal-seek",
        action="store_true",
        help="opt out of the default-ON goal-seek wiring for loop kinds (run/wrap/delegate)",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "templates",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--brief",
        type=Path,
        help="skill-brief JSON。--materialize-task-graph-engine の engine 判定入力",
    )
    parser.add_argument(
        "--materialize-task-graph-engine",
        type=Path,
        metavar="SKILL_DIR",
        help="brief.goal_seek.engine=task-graph のとき全 engine template を生成 skill scripts/ へ byte-copy",
    )
    parser.add_argument("--trace", action="store_true", help="print applied patch names to stderr")
    # with-feedback-loop combinator (default-ON, opt-out で外す)。
    # SKILL.md 合成とは独立に target plugin へ実体コピー配備を行う副作用付きアクション。
    parser.add_argument(
        "--deploy-feedback-loop",
        type=Path,
        default=None,
        help="量産先 plugin ディレクトリに skills/run-skill-feedback を実体コピーで配備 (default-ON 想定、--no-feedback-loop で opt-out)",
    )
    parser.add_argument(
        "--no-feedback-loop",
        action="store_true",
        help="--deploy-feedback-loop を無効化 (feedback-loop 配備の opt-out)",
    )
    args = parser.parse_args(argv)
    if args.kind is None and args.materialize_task_graph_engine is None:
        parser.error("--kind または --materialize-task-graph-engine が必要")
    if args.materialize_task_graph_engine is not None and args.brief is None:
        parser.error("--materialize-task-graph-engine には --brief が必要")
    return args


def _brief_requests_task_graph(brief: dict) -> bool:
    """brief が task-graph engine を要求するか (明示値優先・無指定 loop kind は既定 ON)。

    validate-build-plan.derive_plan の defaulting と同一規則: goal_seek.engine の明示値が
    あればそれに従い (inline/run-goal-seek は opt-out)、無指定なら loop kind (GOAL_SEEK_KINDS)
    に対して task-graph を既定とする。--no-goal-seek opt-out 経路は build-plan が materializer
    指示自体を出さないため本判定へ到達しない。
    """
    goal_seek = brief.get("goal_seek")
    explicit = (
        str(goal_seek.get("engine", "")).strip() if isinstance(goal_seek, dict) else ""
    )
    if explicit:
        return explicit == "task-graph"
    return str(brief.get("kind", "")).strip() in GOAL_SEEK_KINDS


def _set_goal_seek_scalar(text: str, key: str, value: str) -> str:
    """SKILL.md frontmatter の goal_seek.<key> を決定論的に upsert する。"""
    lines = text.splitlines()
    try:
        fm_end = lines.index("---", 1)
    except ValueError as exc:
        raise ComposeError("generated SKILL.md frontmatter is not closed") from exc
    parent = next(
        (i for i in range(1, fm_end) if re.match(r"^goal_seek:\s*(?:#.*)?$", lines[i])),
        None,
    )
    if parent is None:
        raise ComposeError("generated SKILL.md has no goal_seek frontmatter block")
    end = fm_end
    for i in range(parent + 1, fm_end):
        if lines[i] and not lines[i].startswith((" ", "\t", "#")):
            end = i
            break
    replacement = f"  {key}: {value}"
    for i in range(parent + 1, end):
        if re.match(rf"^\s+{re.escape(key)}\s*:", lines[i]):
            lines[i] = replacement
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    insert_at = parent + 1
    if key != "engine":
        for i in range(parent + 1, end):
            if re.match(r"^\s+engine\s*:", lines[i]):
                insert_at = i + 1
                break
    lines.insert(insert_at, replacement)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def materialize_task_graph_engine(
    brief: dict, skill_dir: Path, templates_dir: Path
) -> list[Path]:
    """task-graph brief の全 engine 資産と capability profile を冪等 materialize。

    同一 brief + template bytes なら何度実行しても生成 bytes は同一。既に一致する
    ファイルは書き直さず、欠落または drift だけを canonical bytes へ戻す。
    """
    if not _brief_requests_task_graph(brief):
        return []
    source_dir = templates_dir / "task-graph-engine" / "scripts"
    dest_dir = skill_dir / "scripts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in TASK_GRAPH_ENGINE_SCRIPTS:
        source = source_dir / name
        if not source.is_file():
            raise ComposeError(f"missing task-graph engine template: {source}")
        dest = dest_dir / name
        expected = source.read_bytes()
        if not dest.is_file() or dest.read_bytes() != expected:
            if dest.exists() and not dest.is_file():
                raise ComposeError(f"task-graph engine destination is not a file: {dest}")
            dest.write_bytes(expected)
        written.append(dest)

    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        content = skill_md.read_text(encoding="utf-8")
        # 値だけでなく説明コメントも 1 定数として upsert し、量産物単体で claim の
        # 意味 (checklist-graph≠planner full graph / gap の所在) が読めるようにする。
        # 検査側 (_frontmatter_nested_value / lint check_engine_profile) は末尾
        # コメントを除去して照合するため byte 冪等・parity とも両立する。
        content = _set_goal_seek_scalar(content, "engine", "task-graph")
        content = _set_goal_seek_scalar(
            content,
            "engine_profile",
            "checklist-graph  # planner の full task-spec graph と非同等 (縮小 profile)",
        )
        content = _set_goal_seek_scalar(
            content,
            "full_task_spec_graph",
            "false  # fail-closed capability claim。gap 一覧は build-plan.capability_gaps 参照",
        )
        if skill_md.read_text(encoding="utf-8") != content:
            skill_md.write_text(content, encoding="utf-8")
        written.append(skill_md)
    return written


def selected_patches(args: argparse.Namespace) -> list[str]:
    if args.kind == "assign":
        role = args.role_suffix or "generator"
        first = f"with-assign-{role}.patch"
    else:
        first = KIND_PATCHES[args.kind]

    patches = [first]
    for flag, patch_name in FLAG_PATCHES.items():
        if getattr(args, flag):
            patches.append(patch_name)
    # goal-seek 配線は loop 実行系で default-ON (--no-goal-seek で opt-out)。
    if args.kind in GOAL_SEEK_KINDS and not args.no_goal_seek:
        patches.append("with-goal-seek.patch")
    # feedback_contract は loop 実行系で default-ON。中身は brief 由来で R1/R4 が具体化し、
    # lint-feedback-contract.py / lint-content-review.py が欠落や未評価を fail-closed にする。
    if args.kind in FEEDBACK_CONTRACT_KINDS:
        patches.append("with-feedback-contract.patch")
    return patches


def apply_unified_diff(content: str, diff_text: str) -> str:
    """Apply one-file unified diff text.

    This implements the minimal deterministic subset used by the combinator
    files: one target file, standard hunk headers, context/add/remove lines.
    """
    original = content.splitlines(keepends=True)
    result: list[str] = []
    cursor = 0
    lines = diff_text.splitlines(keepends=True)
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.startswith("@@ "):
            index += 1
            continue

        match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
        if not match:
            raise ComposeError(f"invalid hunk header: {line.strip()}")

        old_start = int(match.group(1)) - 1
        if old_start < cursor:
            raise ComposeError(f"overlapping hunk at line {old_start + 1}")
        result.extend(original[cursor:old_start])
        cursor = old_start
        index += 1

        while index < len(lines) and not lines[index].startswith("@@ "):
            hunk_line = lines[index]
            if hunk_line.startswith(("--- ", "+++ ")):
                index += 1
                continue
            if not hunk_line:
                index += 1
                continue
            tag = hunk_line[0]
            text = hunk_line[1:]
            if tag == " ":
                if cursor >= len(original) or original[cursor].rstrip("\n") != text.rstrip("\n"):
                    got = "<eof>" if cursor >= len(original) else original[cursor].rstrip("\n")
                    raise ComposeError(f"context mismatch: expected {text.rstrip()} got {got}")
                result.append(original[cursor])
                cursor += 1
            elif tag == "-":
                if cursor >= len(original) or original[cursor].rstrip("\n") != text.rstrip("\n"):
                    got = "<eof>" if cursor >= len(original) else original[cursor].rstrip("\n")
                    raise ComposeError(f"removal mismatch: expected {text.rstrip()} got {got}")
                cursor += 1
            elif tag == "+":
                result.append(text)
            elif hunk_line.startswith("\\ No newline at end of file"):
                pass
            else:
                raise ComposeError(f"unsupported hunk line: {hunk_line.rstrip()}")
            index += 1

    result.extend(original[cursor:])
    return "".join(result)


def frontmatter_bounds(text: str) -> tuple[int, int]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ComposeError("_base.md must start with frontmatter")
    for idx in range(1, len(lines)):
        if lines[idx] == "---":
            return 0, idx
    raise ComposeError("_base.md frontmatter is not closed")


def normalize_base(text: str) -> str:
    """Drop the design-note fence that precedes the real template frontmatter."""
    lines = text.splitlines()
    if len(lines) < 3 or lines[0] != "---":
        return text
    for idx in range(1, len(lines)):
        if lines[idx] != "---":
            continue
        if idx + 1 < len(lines) and lines[idx + 1] == "---":
            return "\n".join(lines[idx + 1 :]) + "\n"
        if idx + 1 < len(lines) and lines[idx + 1].startswith("name:"):
            return "---\n" + "\n".join(lines[idx + 1 :]) + "\n"
        return text
    return text


def ensure_frontmatter_line(text: str, line: str, after_key: str = "") -> str:
    lines = text.splitlines()
    start, end = frontmatter_bounds(text)
    key = line.split(":", 1)[0]
    if any(item.startswith(f"{key}:") for item in lines[start + 1 : end]):
        return text
    insert_at = end
    if after_key:
        for idx in range(start + 1, end):
            if lines[idx].startswith(f"{after_key}:"):
                insert_at = idx + 1
                break
    lines.insert(insert_at, line)
    return "\n".join(lines) + "\n"


def add_section_after(text: str, anchor: str, section: str) -> str:
    if section.splitlines()[0] in text:
        return text
    if anchor not in text:
        raise ComposeError(f"anchor not found for semantic combinator: {anchor}")
    return text.replace(anchor, anchor + "\n\n" + section, 1)


def apply_semantic_patch(text: str, patch_name: str) -> str:
    """Compatibility adapter for reviewed patches whose base moved to Japanese headings."""
    if patch_name == "with-run.patch":
        # run-kind の固有差分は frontmatter のみ。手順は _base.md の `## ゴールシーク実行` を継承し、
        # 固定手順 (### Step 1/2/3) は注入しない (goal-seek 原則「固定手順は書かない」と矛盾するため)。
        text = ensure_frontmatter_line(text, "effect: {{effect | default(\"local-artifact\")}}", "kind")
        text = ensure_frontmatter_line(text, "role_suffix: {{role_suffix | default(\"workflow\")}}", "effect")
        return text
    if patch_name == "with-ref.patch":
        text = ensure_frontmatter_line(text, "disable-model-invocation: true", "description")
        text = ensure_frontmatter_line(text, "user-invocable: false", "disable-model-invocation")
        text = ensure_frontmatter_line(text, "effect: read-only", "kind")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## 参照内容\n\n本Skillは {{ref_topic}} の正本情報を提供する Read-only スキル。\n\n"
            "- 主参照元: {{primary_source}}\n"
            "- 補助参照: {{secondary_sources | default(\"(なし)\")}}\n"
            "- 更新頻度: {{update_frequency | default(\"公式仕様改訂時\")}}\n"
            "- 鮮度ポリシー: `last-audited` を四半期ごとに更新（設計書15章）",
        )
    if patch_name == "with-assign-generator.patch":
        text = ensure_frontmatter_line(text, "role_suffix: generator", "effect")
        text = ensure_frontmatter_line(text, "pair: {{pair_skill}}", "role_suffix")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## 生成契約\n\n"
            "- **入力**: {{generator_input}}\n"
            "- **出力**: {{generator_output}}\n"
            "- **後段 evaluator**: `Skill({{pair_skill}})` が fork で評価\n"
            "- **再生成ループ**: evaluator findings を受け、最大 {{retry_max | default(3)}} 周まで自動再試行\n"
            "- **禁則**: 評価判断を generator 側で行わない（Goodhart 対策、09章）",
        )
    if patch_name == "with-assign-evaluator.patch":
        text = ensure_frontmatter_line(text, "user-invocable: false", "description")
        text = ensure_frontmatter_line(text, "context: fork", "user-invocable")
        text = ensure_frontmatter_line(text, "role_suffix: evaluator", "effect")
        text = ensure_frontmatter_line(text, "pair: {{pair_skill}}", "role_suffix")
        text = ensure_frontmatter_line(text, "agent: {{agent | default(\"general-purpose\")}}", "pair")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Evaluator Contract\n\n評価結果は STDOUT に JSON 1 オブジェクトで返す:\n\n"
            "```json\n"
            "{\"rubric_id\":\"{{rubric_id}}\",\"rubric_version\":\"{{rubric_version}}\",\"score\":0,\"threshold\":{{threshold | default(80)}},\"passed\":false,\"findings\":[]}\n"
            "```\n\n"
            "**禁則**: 被採点物の Write/Edit を持たない。rubric も改変しない。",
        )
    if patch_name == "with-wrap.patch":
        text = ensure_frontmatter_line(text, "role_suffix: cli-wrapper", "effect")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Wrapped CLI\n\n"
            "- **対象CLI**: `{{wrapped_cli}}`\n"
            "- **想定バージョン**: {{cli_version | default(\"未固定\")}}\n"
            "- **安全側デフォルト**: {{safe_defaults}}\n"
            "- **禁止サブコマンド**: {{forbidden_subcommands | default(\"(なし)\")}}\n"
            "- **dry-run 既定**: {{dry_run_default | default(\"true\")}}\n"
            "- **失敗時挙動**: {{failure_behavior | default(\"非ゼロ exit を上位に伝搬し、副作用は rollback しない\")}}",
        )
    if patch_name == "with-delegate.patch":
        text = ensure_frontmatter_line(text, "role_suffix: external-delegator", "effect")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Delegation Target\n\n"
            "- **委譲先**: {{delegate_target}}\n"
            "- **委譲理由**: {{delegation_reason}}\n"
            "- **入力契約**: {{delegation_input}}\n"
            "- **出力契約**: {{delegation_output}}\n"
            "- **失敗時 fallback**: {{delegation_fallback | default(\"ユーザーに手動実行を要請\")}}\n"
            "- **タイムアウト**: {{delegation_timeout | default(\"300秒\")}}",
        )
    if patch_name == "with-evaluator.patch":
        text = ensure_frontmatter_line(text, "pair: {{pair_skill}}", "rubric_refs")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Evaluator 連携\n本Skillは完了後 `Skill({{pair_skill}}) target=<artifact>` を fork で呼び、JSON評価結果を受け取る。`{{pair_skill}}` 側が `context: fork` を持つ。",
        )
    if patch_name == "with-hooks.patch":
        text = ensure_frontmatter_line(text, "with_hooks: true", "rubric_refs")
        text = ensure_frontmatter_line(text, "needs_lifecycle_enforcement: true", "with_hooks")
        return add_section_after(
            text,
            "## セキュリティと権限\n本Skillは副作用を伴う可能性がある。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。",
            "## Hook Wiring（10章 / 17章）\n"
            "- `PreToolUse`: 破壊的引数の検査。block は exit 2 または `hookSpecificOutput.permissionDecision: \"deny\"` で行う。\n"
            "- `PostToolUse`: 監査ログ + 後処理。failure 系は `PostToolUseFailure` を別途配線。\n"
            "- `SubagentStop`: Subagent ありの場合、完了 hook で evaluator JSON 検証を強制。",
        )
    if patch_name == "with-subagent.patch":
        text = ensure_frontmatter_line(text, "context: fork", "rubric_refs")
        text = ensure_frontmatter_line(text, "agent: {{subagent_type}}", "context")
        text = ensure_frontmatter_line(text, "needs_independent_context: true", "agent")
        text = ensure_frontmatter_line(text, "with_subagent_hint: true", "needs_independent_context")
        return add_section_after(
            text,
            "## 追加リソース\n- `references/`\n{{additional_resources}}",
            "## Subagent / Agent Team 連携（17章）\n"
            "- spawn prompt は lead history を継承しないため、必要な context を明示する。\n"
            "- file ownership を分け、同一 file を複数 teammate に触らせない。\n"
            "- cleanup は必ず lead 経由で行う。",
        )
    if patch_name == "with-knowledge.patch":
        text = ensure_frontmatter_line(text, KNOWLEDGE_FM_BLOCK, "rubric_refs")
        return add_section_after(text, "## 主要ルール\n{{key_constraints}}", KNOWLEDGE_SECTION)
    if patch_name == "with-goal-seek.patch":
        text = ensure_frontmatter_line(text, GOAL_SEEK_FM_BLOCK, "rubric_refs")
        return add_section_after(text, GOAL_SEEK_LOOP_ANCHOR, GOAL_SEEK_WIRING_SECTION)
    if patch_name == "with-feedback-contract.patch":
        text = ensure_frontmatter_line(text, FEEDBACK_CONTRACT_FM_BLOCK, "rubric_refs")
        return add_section_after(text, "## 主要ルール\n{{key_constraints}}", FEEDBACK_CONTRACT_SECTION)
    raise ComposeError(f"unknown combinator: {patch_name}")


def apply_patch_file(content: str, patch_path: Path) -> str:
    diff_text = patch_path.read_text(encoding="utf-8")
    try:
        return apply_unified_diff(content, diff_text)
    except ComposeError:
        return apply_semantic_patch(content, patch_path.name)


def _feedback_loop_source() -> Path:
    """Return the canonical run-skill-feedback directory from this plugin install."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    candidates: list[Path] = []
    if plugin_root:
        candidates.append(Path(plugin_root) / "skills" / "run-skill-feedback")
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "skills" / "run-skill-feedback")
    for candidate in candidates:
        if candidate.is_dir() and not candidate.is_symlink():
            return candidate
    raise OSError("run-skill-feedback source not found")


def apply_feedback_loop(target_plugin_dir: Path) -> Path:
    """量産先 plugin ディレクトリに skills/run-skill-feedback を実体コピーで配備する。

    marketplace install では plugin 境界を越える symlink が dangling し得るため、配布先には
    自己完結する実体ディレクトリを置く。冪等: 既に実体があれば no-op。既存 symlink は
    dangling 回帰を避けるため置換する。
    """
    target_plugin_dir = target_plugin_dir.resolve()
    # 生成器自身は配備除外 (自分への自己コピーは不要)。境界判定は SSOT 述語へ委譲。
    if _FC.is_feedback_deploy_exempt(target_plugin_dir.name):
        return target_plugin_dir / "skills" / "run-skill-feedback"
    skills_dir = target_plugin_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    dest = skills_dir / "run-skill-feedback"
    if dest.exists() and not dest.is_symlink():
        return dest
    if dest.is_symlink():
        dest.unlink()
    shutil.copytree(_feedback_loop_source(), dest, symlinks=False)
    return dest


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.materialize_task_graph_engine is not None:
        try:
            brief = json.loads(args.brief.read_text(encoding="utf-8"))
            materialized = materialize_task_graph_engine(
                brief, args.materialize_task_graph_engine, args.templates_dir
            )
            if args.trace:
                if materialized:
                    print(
                        "materialized task-graph engine: "
                        + ", ".join(str(p) for p in materialized),
                        file=sys.stderr,
                    )
                else:
                    print("task-graph engine: not requested by brief", file=sys.stderr)
        except (OSError, json.JSONDecodeError, ComposeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if args.kind is None:
            return 0
    # 副作用アクション: feedback-loop 配備のみのモード (SKILL.md 合成は skip 可能)。
    if args.deploy_feedback_loop and not args.no_feedback_loop:
        try:
            link = apply_feedback_loop(args.deploy_feedback_loop)
            if args.trace:
                print(f"deployed feedback-loop: {link}", file=sys.stderr)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    base_path = args.templates_dir / "_base.md"
    combinator_dir = args.templates_dir / "combinators"
    try:
        content = normalize_base(base_path.read_text(encoding="utf-8"))
        patch_names = selected_patches(args)
        for patch_name in patch_names:
            patch_path = combinator_dir / patch_name
            if not patch_path.exists():
                raise ComposeError(f"missing combinator: {patch_path}")
            content = apply_patch_file(content, patch_path)
        if args.trace:
            print("applied: " + ", ".join(patch_names), file=sys.stderr)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
        else:
            sys.stdout.write(content)
        return 0
    except (OSError, ComposeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
