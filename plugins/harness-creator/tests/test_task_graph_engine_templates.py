"""engine:task-graph 変種の runtime テンプレ 4 script + ループ E2E + 宣言実例の実証。

層②: wtg-goalseek build で機構は完備だが未実証だった (a) テンプレ 4 script の専用
pytest、(b) runtime ループの E2E 実走、(c) engine:task-graph 宣言 SKILL.md 実例を恒久化する。

対象テンプレ (run-build-skill/templates/task-graph-engine/scripts/・生成 harness へ byte-copy 同梱):
  - ready-set-from-checklist.py   (ENG-C01): depends_on 充足順の ready 集合をステートレス算出
  - self-reflect-append.py        (ENG-C02): 発見タスクを checklist 末尾へ単一truth追記
  - extract-capability-dependency-graph.py (ENG-C06): cross-surface 依存グラフ抽出
  - record-capability-graph-knowledge.py   (ENG-C07): Loop A/B knowledge へ source_ref 付き記録

script 本体は原則無改修 (仕様は各 script の header docstring を正とする)。
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "plugins/harness-creator/skills/run-build-skill"
TEMPLATE_SCRIPTS = SKILL_ROOT / "templates/task-graph-engine/scripts"
EXAMPLE = SKILL_ROOT / "examples/task-graph-engine-skill.md"


def _load(stem: str) -> ModuleType:
    """ハイフン名テンプレ script を importlib で file-path ロードする (name 衝突回避で unique 名)。"""
    path = TEMPLATE_SCRIPTS / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(f"tg_tmpl_{stem.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


READY = _load("ready-set-from-checklist")
REFLECT = _load("self-reflect-append")
EXTRACT = _load("extract-capability-dependency-graph")
RECORD = _load("record-capability-graph-knowledge")


def _run(script: str, *args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TEMPLATE_SCRIPTS / f"{script}.py"), *args],
        capture_output=True, text=True, **kw,
    )


# --------------------------------------------------------------------------- #
# ENG-C01: ready-set-from-checklist.py                                         #
# --------------------------------------------------------------------------- #
class TestReadySetFromChecklist:
    def test_ready_is_pending_with_all_deps_done(self) -> None:
        checklist = [
            {"id": "C1", "text": "a", "status": "done"},
            {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
            {"id": "C3", "text": "c", "status": "pending", "depends_on": ["C2"]},
        ]
        # C1 done ゆえ C2 だけ ready (C3 は C2 未 done で不可)。
        assert READY.compute_ready(checklist) == ["C2"]

    def test_no_deps_pending_is_ready(self) -> None:
        checklist = [{"id": "C1", "text": "a", "status": "pending"}]
        assert READY.compute_ready(checklist) == ["C1"]

    def test_id_sort_is_numeric_not_lexical(self) -> None:
        # C10 が C2 より前に来る辞書順ではなく、数値昇順 (C2 < C10) であること。
        checklist = [
            {"id": "C10", "text": "j", "status": "pending"},
            {"id": "C2", "text": "b", "status": "pending"},
            {"id": "C1", "text": "a", "status": "pending"},
        ]
        assert READY.compute_ready(checklist) == ["C1", "C2", "C10"]
        assert READY.id_sort_key("C10") > READY.id_sort_key("C2")

    def test_non_conforming_id_sorts_after_conforming(self) -> None:
        # 非準拠 id (bucket=1) は準拠 id (bucket=0) の後ろへ辞書順で回る。
        assert READY.id_sort_key("Cx")[0] == 1
        assert READY.id_sort_key("C3")[0] == 0

    def test_dangling_dependency_is_not_ready_not_error(self) -> None:
        # depends_on 先が checklist に不在 → 永遠に done にならないため not-ready (fail は C02 委譲)。
        checklist = [{"id": "C1", "text": "a", "status": "pending", "depends_on": ["C9"]}]
        assert READY.compute_ready(checklist) == []

    def test_blocked_and_done_are_excluded(self) -> None:
        checklist = [
            {"id": "C1", "text": "a", "status": "done"},
            {"id": "C2", "text": "b", "status": "blocked"},
        ]
        assert READY.compute_ready(checklist) == []

    def test_empty_ready_exit0(self, tmp_path: Path) -> None:
        p = tmp_path / "prog.json"
        p.write_text(json.dumps({"checklist": [{"id": "C1", "text": "a", "status": "done"}]}), encoding="utf-8")
        r = _run("ready-set-from-checklist", str(p))
        assert r.returncode == 0
        assert json.loads(r.stdout) == {"ready": []}

    def test_data_integrity_exit1(self, tmp_path: Path) -> None:
        # id 欠落 = データ不整合 (exit1)。
        p = tmp_path / "prog.json"
        p.write_text(json.dumps({"checklist": [{"text": "a", "status": "pending"}]}), encoding="utf-8")
        r = _run("ready-set-from-checklist", str(p))
        assert r.returncode == 1
        assert "不整合" in r.stderr

    def test_missing_file_exit2(self, tmp_path: Path) -> None:
        r = _run("ready-set-from-checklist", str(tmp_path / "nope.json"))
        assert r.returncode == 2

    def test_usage_exit2(self) -> None:
        r = _run("ready-set-from-checklist")  # 引数なし
        assert r.returncode == 2


# --------------------------------------------------------------------------- #
# ENG-C02: self-reflect-append.py                                             #
# --------------------------------------------------------------------------- #
class TestSelfReflectAppend:
    @staticmethod
    def _prog(tmp_path: Path, checklist: list[dict]) -> Path:
        p = tmp_path / "prog.json"
        p.write_text(json.dumps({
            "skill": "s", "goal": "g", "iteration": 0,
            "checklist": checklist, "status": "in_progress",
        }, ensure_ascii=False), encoding="utf-8")
        return p

    def test_append_adds_pending_item_to_tail(self, tmp_path: Path) -> None:
        p = self._prog(tmp_path, [{"id": "C1", "text": "a", "status": "done"}])
        r = _run("self-reflect-append", str(p), "--id", "C2", "--text", "new",
                 "--depends-on", "C1", "--verify-by", "script")
        assert r.returncode == 0
        data = json.loads(p.read_text())
        assert data["checklist"][-1] == {
            "id": "C2", "text": "new", "status": "pending",
            "depends_on": ["C1"], "verify_by": "script",
        }
        # 既存 item は一切書き換えない (単一truth追記)。
        assert data["checklist"][0] == {"id": "C1", "text": "a", "status": "done"}

    def test_append_without_deps_omits_field(self, tmp_path: Path) -> None:
        p = self._prog(tmp_path, [{"id": "C1", "text": "a", "status": "pending"}])
        r = _run("self-reflect-append", str(p), "--id", "C2", "--text", "n")
        assert r.returncode == 0
        item = json.loads(p.read_text())["checklist"][-1]
        assert "depends_on" not in item and "verify_by" not in item

    def test_id_pattern_violation_exit1(self, tmp_path: Path) -> None:
        p = self._prog(tmp_path, [{"id": "C1", "text": "a", "status": "pending"}])
        r = _run("self-reflect-append", str(p), "--id", "task2", "--text", "n")
        assert r.returncode == 1 and "pattern" in r.stderr

    def test_duplicate_id_exit1(self, tmp_path: Path) -> None:
        p = self._prog(tmp_path, [{"id": "C1", "text": "a", "status": "pending"}])
        r = _run("self-reflect-append", str(p), "--id", "C1", "--text", "n")
        assert r.returncode == 1 and "重複" in r.stderr

    def test_unknown_dependency_exit1(self, tmp_path: Path) -> None:
        p = self._prog(tmp_path, [{"id": "C1", "text": "a", "status": "pending"}])
        r = _run("self-reflect-append", str(p), "--id", "C2", "--text", "n", "--depends-on", "C9")
        assert r.returncode == 1 and "未知" in r.stderr

    def test_appended_item_is_sink_no_cycle(self, tmp_path: Path) -> None:
        # 追記 item は新規シンク: 既存を指すのみで循環を作れない (正常 append)。
        p = self._prog(tmp_path, [
            {"id": "C1", "text": "a", "status": "pending"},
            {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
        ])
        r = _run("self-reflect-append", str(p), "--id", "C3", "--text", "n", "--depends-on", "C1,C2")
        assert r.returncode == 0

    def test_has_cycle_detects_preexisting_cycle(self) -> None:
        # 反復 DFS が既存の循環 (C1->C2->C1) を検出する (深鎖でも recursion 上限非依存)。
        assert REFLECT._has_cycle({"C1": ["C2"], "C2": ["C1"]}) is True
        assert REFLECT._has_cycle({"C1": [], "C2": ["C1"]}) is False

    def test_append_into_cyclic_checklist_exit1(self, tmp_path: Path) -> None:
        # 既存 checklist が循環を含む場合、追記後グラフのサイクル検査が fail-closed。
        p = self._prog(tmp_path, [
            {"id": "C1", "text": "a", "status": "pending", "depends_on": ["C2"]},
            {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
        ])
        r = _run("self-reflect-append", str(p), "--id", "C3", "--text", "n", "--depends-on", "C1")
        assert r.returncode == 1 and "サイクル" in r.stderr


# --------------------------------------------------------------------------- #
# ENG-C06: extract-capability-dependency-graph.py                             #
# --------------------------------------------------------------------------- #
class TestExtractDependencyGraph:
    @staticmethod
    def _harness(root: Path, *, skill_body: str = "", agent: bool = True) -> Path:
        (root / "skills/run-a").mkdir(parents=True)
        (root / "skills/run-a/SKILL.md").write_text(
            "---\nname: run-a\nkind: run\n---\n\n# run-a\n" + skill_body, encoding="utf-8"
        )
        (root / "scripts").mkdir(parents=True)
        (root / "scripts/helper.py").write_text("# helper\n", encoding="utf-8")
        if agent:
            (root / "agents").mkdir(parents=True)
            (root / "agents/worker.md").write_text(
                "---\nname: worker\n---\n\n# worker\n", encoding="utf-8"
            )
        return root

    def test_nodes_are_discovered_with_kind_prefixed_ids(self, tmp_path: Path) -> None:
        root = self._harness(tmp_path)
        nodes = EXTRACT.discover_nodes(root)
        ids = {n["id"] for n in nodes}
        assert {"skill:run-a", "agent:worker", "script:helper.py"} <= ids
        # id 昇順で正準化されている。
        assert [n["id"] for n in nodes] == sorted(n["id"] for n in nodes)

    def test_edges_from_invocations_and_gaps_are_fail_closed(self, tmp_path: Path) -> None:
        # skill が worker (発見済) と unknown-agent (未発見) を呼ぶ → edge 1 + gap 1。
        root = self._harness(tmp_path, skill_body="Agent(worker) と Agent(unknown-agent) を使う\n")
        graph, findings = EXTRACT.build_graph(root)
        assert {"from": "skill:run-a", "to": "agent:worker", "type": "agent-invoke",
                "source_ref": "skills/run-a/SKILL.md"} in graph["edges"]
        assert any(g["ref"] == "agent:unknown-agent" for g in graph["gaps"])
        assert any("未知参照" in f for f in findings)  # gaps 非空 = fail-closed

    def test_builtin_agent_is_neither_edge_nor_gap(self, tmp_path: Path) -> None:
        root = self._harness(tmp_path, skill_body="Agent(general-purpose) に委譲\n", agent=False)
        graph, _ = EXTRACT.build_graph(root)
        assert all(e["to"] != "agent:general-purpose" for e in graph["edges"])
        assert all("general-purpose" not in g["ref"] for g in graph["gaps"])

    def test_empty_graph_is_fail_closed(self, tmp_path: Path) -> None:
        (tmp_path / "empty").mkdir()
        graph, findings = EXTRACT.build_graph(tmp_path / "empty")
        assert graph["nodes"] == []
        assert any("空 graph" in f for f in findings)

    def test_cycle_is_fail_closed(self, tmp_path: Path) -> None:
        # 2 script が相互参照 → find_cycle が検出。
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts/a.py").write_text("scripts/b.py を呼ぶ\n", encoding="utf-8")
        (tmp_path / "scripts/b.py").write_text("scripts/a.py を呼ぶ\n", encoding="utf-8")
        graph, findings = EXTRACT.build_graph(tmp_path)
        assert any("循環" in f for f in findings)

    def test_main_exit1_on_gaps(self, tmp_path: Path) -> None:
        root = self._harness(tmp_path, skill_body="Skill(missing-skill) を呼ぶ\n", agent=False)
        r = _run("extract-capability-dependency-graph", str(root))
        assert r.returncode == 1
        # JSON は失敗時も stdout へ (C07 が graph+gaps を読めるように)。
        assert json.loads(r.stdout)["gaps"]

    def test_main_exit0_on_clean_graph(self, tmp_path: Path) -> None:
        root = self._harness(tmp_path, skill_body="Agent(worker) に委譲\n")
        r = _run("extract-capability-dependency-graph", str(root))
        assert r.returncode == 0, r.stderr

    def test_main_exit2_on_missing_dir(self, tmp_path: Path) -> None:
        r = _run("extract-capability-dependency-graph", str(tmp_path / "nope"))
        assert r.returncode == 2


# --------------------------------------------------------------------------- #
# ENG-C07: record-capability-graph-knowledge.py                              #
# --------------------------------------------------------------------------- #
class TestRecordCapabilityGraphKnowledge:
    @staticmethod
    def _graph() -> dict:
        return {
            "nodes": [{"id": "skill:run-a", "kind": "skill", "path": "skills/run-a/SKILL.md"}],
            "edges": [{"from": "skill:run-a", "to": "script:helper.py", "type": "script-call",
                       "source_ref": "skills/run-a/SKILL.md"}],
            "gaps": [{"from": "skill:run-a", "ref": "agent:missing", "type": "agent-invoke",
                      "source_ref": "skills/run-a/SKILL.md"}],
        }

    def test_entries_have_source_ref_and_cover_summary_gap_task(self) -> None:
        discovered = [{"id": "C9", "text": "発見タスク"}]
        entries = RECORD.build_entries(self._graph(), "graph.json", discovered)
        ids = {e["id"] for e in entries}
        assert "cdg-summary" in ids
        assert any(i.startswith("cdg-gap-") for i in ids)
        assert any(i.startswith("cdg-task-") for i in ids)
        # 全 entry が source_ref を持つ (Loop A/B の出所追跡 = KL-007 契約の前提)。
        assert all(e.get("source_ref") for e in entries)
        # id 昇順で決定論。
        assert [e["id"] for e in entries] == sorted(e["id"] for e in entries)

    def test_merge_declares_consult_at_runtime_and_index_registered(self, tmp_path: Path) -> None:
        # KL-007: 記録先 store / index が consult_at を宣言し index-search consult で発見可能になる。
        entries = RECORD.build_entries(self._graph(), "graph.json", [])
        status = RECORD.merge_into_store(tmp_path, entries, dry_run=False)
        store = json.loads((tmp_path / "knowledge-capability-graph.json").read_text())
        assert store["consult_at"] == ["runtime"]
        assert status["added"] and status["category_registered"] is True
        index = json.loads((tmp_path / "knowledge-index.json").read_text())
        assert index["consult_at"] == ["runtime"]
        assert any(c["file"] == "knowledge-capability-graph.json" for c in index["categories"])

    def test_merge_is_idempotent_skips_existing_ids(self, tmp_path: Path) -> None:
        entries = RECORD.build_entries(self._graph(), "graph.json", [])
        RECORD.merge_into_store(tmp_path, entries, dry_run=False)
        second = RECORD.merge_into_store(tmp_path, entries, dry_run=False)
        assert second["added"] == [] and set(second["skipped"]) == {e["id"] for e in entries}
        # 二重記録されない。
        store = json.loads((tmp_path / "knowledge-capability-graph.json").read_text())
        assert len(store["items"]) == len(entries)

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        entries = RECORD.build_entries(self._graph(), "graph.json", [])
        RECORD.merge_into_store(tmp_path, entries, dry_run=True)
        assert not (tmp_path / "knowledge-capability-graph.json").exists()
        assert not (tmp_path / "knowledge-index.json").exists()

    def test_main_records_loop_a_and_loop_b(self, tmp_path: Path) -> None:
        graph_path = tmp_path / "graph.json"
        graph_path.write_text(json.dumps(self._graph()), encoding="utf-8")
        loop_a = tmp_path / "knowledge_a"
        loop_b = tmp_path / "knowledge_b"
        r = _run("record-capability-graph-knowledge", str(graph_path),
                 "--target-knowledge-dir", str(loop_a),
                 "--harness-knowledge-dir", str(loop_b))
        assert r.returncode == 0, r.stderr
        out = json.loads(r.stdout)
        assert out["loop_a_status"]["added"] and out["loop_b_status"]["added"]
        # 両 Loop に source_ref 付き entry が実在。
        for d in (loop_a, loop_b):
            store = json.loads((d / "knowledge-capability-graph.json").read_text())
            assert all(it["source_ref"] for it in store["items"])

    def test_main_missing_graph_exit2(self, tmp_path: Path) -> None:
        r = _run("record-capability-graph-knowledge", str(tmp_path / "nope.json"),
                 "--target-knowledge-dir", str(tmp_path / "k"))
        assert r.returncode == 2


# --------------------------------------------------------------------------- #
# runtime E2E: ready 算出 → 最小 id 拘束選択 → done → self-reflect 追記 →         #
#              ready 再計算 → 全消費。intermediate トレース + example 同梱 verifier #
# --------------------------------------------------------------------------- #
def _keyfn(item_id: str) -> tuple[int, int, str]:
    m = re.match(r"^C(\d+)$", item_id)
    return (0, int(m.group(1)), item_id) if m else (1, 0, item_id)


def _ready(progress_path: Path) -> list[str]:
    r = _run("ready-set-from-checklist", str(progress_path))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["ready"]


def _drive_loop(prog_path: Path) -> list[dict]:
    """progress.json を disk-truth に依存順消費し、intermediate エントリ列を返す。

    毎周: disk から再読込 → ready 算出 → 最小 id 選択 → intermediate 記録 → done 記述 →
    (C1 完了時に自己反映で C4 を追記) を繰り返し、ready 空で終了する。
    """
    entries: list[dict] = []
    original_goal = json.loads(prog_path.read_text())["goal"]
    appended = False
    it = 0
    while True:
        prog = json.loads(prog_path.read_text())
        ready = _ready(prog_path)
        if not ready:
            break
        sel = sorted(ready, key=_keyfn)[0]
        entries.append({
            "iteration": it, "original_goal": original_goal,
            "current_goal_snapshot": f"{sel} を done 化", "delta_from_original": "",
            "merged_directive_for_next": "original_goal の具体性を保つ",
            "drift_signal": "initial" if it == 0 else "aligned",
            "ready_set": ready, "selected_item": sel,
        })
        for item in prog["checklist"]:
            if item["id"] == sel:
                item["status"] = "done"
        prog["iteration"] = it
        prog_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
        if sel == "C1" and not appended:
            # 実行中に発見した未網羅タスクを self-reflect で checklist 末尾へ追記 (別状態ファイルを作らない)。
            rr = _run("self-reflect-append", str(prog_path), "--id", "C4",
                      "--text", "発見タスク: 追加検証", "--depends-on", "C3")
            assert rr.returncode == 0, rr.stderr
            appended = True
        it += 1
    return entries


def test_e2e_dependency_ordered_consumption_with_self_reflect(tmp_path: Path) -> None:
    import hashlib
    eval_log = tmp_path / "eval-log"
    eval_log.mkdir()
    prog_path = eval_log / "prog.json"
    inter_path = eval_log / "inter.jsonl"
    goal = "全 checklist item を依存順に done 化し completed"
    prog_path.write_text(json.dumps({
        "skill": "run-task-graph-demo", "goal": goal, "engine": "task-graph",
        "iteration": 0, "max_loops": 8,
        "checklist": [
            {"id": "C1", "text": "基盤", "status": "pending"},
            {"id": "C2", "text": "中段", "status": "pending", "depends_on": ["C1"]},
            {"id": "C3", "text": "上段", "status": "pending", "depends_on": ["C2"]},
        ],
        "status": "in_progress",
        "original_goal_hash": hashlib.sha256(goal.encode()).hexdigest(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    entries = _drive_loop(prog_path)

    # 依存順に消費された (C4 は self-reflect 追記後 C3 完了を待って最後)。
    assert [e["selected_item"] for e in entries] == ["C1", "C2", "C3", "C4"]

    # 完了宣言 + intermediate トレース書き出し。
    prog = json.loads(prog_path.read_text())
    prog["status"] = "completed"
    prog["iteration"] = len(entries) - 1
    prog_path.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8")
    inter_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8"
    )

    # 追記 item C4 が checklist 末尾に統合され done 化 (発見が完了判定に反映される)。
    assert prog["checklist"][-1]["id"] == "C4"
    assert all(it["status"] == "done" for it in prog["checklist"])

    # intermediate.jsonl の各行が ready_set/selected_item トレースを持つ。
    lines = [json.loads(l) for l in inter_path.read_text().splitlines() if l.strip()]
    assert all("ready_set" in l and "selected_item" in l for l in lines)

    # example 同梱の task-graph 消費検査 verifier で E2E トレースを機械検証 (exit0)。
    r = _run_verifier(prog_path, inter_path)
    assert r.returncode == 0, r.stderr
    assert "task-graph 消費検査 OK" in r.stdout

    # 負例 (absence-as-violation): intermediate 不在で verifier が拘束違反として exit != 0。
    neg = _run_verifier(prog_path, eval_log / "absent.jsonl")
    assert neg.returncode != 0
    assert "intermediate.jsonl 未生成" in neg.stderr


def _extract_task_graph_verifier() -> str:
    """example SKILL.md から task-graph 消費検査の heredoc PY 本体を抽出する。"""
    text = EXAMPLE.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
    tg = [b for b in blocks if "task-graph 消費検査 OK" in b]
    assert tg, "example に task-graph 消費検査 bash が無い"
    body = re.search(r"<<'PY'\n(.*?)\nPY", tg[0], re.DOTALL)
    assert body, "heredoc PY 本体を抽出できない"
    return body.group(1)


def _run_verifier(prog_path: Path, inter_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-", str(prog_path), str(inter_path)],
        input=_extract_task_graph_verifier(), capture_output=True, text=True,
    )


def test_e2e_verifier_rejects_out_of_order_selection(tmp_path: Path) -> None:
    """依存順を破った選択列 (C2 を C1 より先に selected) を verifier が exit1 で捕捉する。"""
    import hashlib
    eval_log = tmp_path / "eval-log"
    eval_log.mkdir()
    prog_path = eval_log / "prog.json"
    inter_path = eval_log / "inter.jsonl"
    goal = "順序違反の負例"
    prog_path.write_text(json.dumps({
        "skill": "s", "goal": goal, "engine": "task-graph", "iteration": 1, "max_loops": 8,
        "checklist": [
            {"id": "C1", "text": "基盤", "status": "done"},
            {"id": "C2", "text": "中段", "status": "done", "depends_on": ["C1"]},
        ],
        "status": "completed",
        "original_goal_hash": hashlib.sha256(goal.encode()).hexdigest(),
    }, ensure_ascii=False), encoding="utf-8")
    # C2 の depends_on C1 が未選択のまま C2 を選択した捏造トレース。
    inter_path.write_text(
        json.dumps({"iteration": 0, "original_goal": goal, "current_goal_snapshot": "",
                    "delta_from_original": "", "merged_directive_for_next": "",
                    "drift_signal": "initial", "ready_set": ["C2"], "selected_item": "C2"}) + "\n",
        encoding="utf-8",
    )
    r = _run_verifier(prog_path, inter_path)
    assert r.returncode != 0
    assert "依存順消費違反" in r.stderr


# --------------------------------------------------------------------------- #
# engine:task-graph 宣言実例が lint-goal-seek で緑になる                        #
# --------------------------------------------------------------------------- #
def _load_lint() -> ModuleType:
    path = SKILL_ROOT / "scripts/lint-goal-seek.py"
    spec = importlib.util.spec_from_file_location("tg_lint_goal_seek", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_exists_and_declares_task_graph_engine() -> None:
    assert EXAMPLE.is_file(), f"engine:task-graph 宣言実例が無い: {EXAMPLE}"
    lint = _load_lint()
    text = EXAMPLE.read_text(encoding="utf-8")
    # concrete な engine: task-graph 宣言 (散文言及でなく frontmatter 実値)。
    assert lint._CONCRETE_TASK_GRAPH_ENGINE_RE.search(text)


def test_example_passes_goal_seek_lint_with_no_findings() -> None:
    # lint が examples/ を走査対象にしないため、lint 関数へ直接通して緑 (findings 空) を assert。
    lint = _load_lint()
    findings, _warnings = lint.lint_file(EXAMPLE)
    assert findings == [], f"example が goal-seek lint 違反: {findings}"


def test_example_wiring_carries_all_task_graph_tokens() -> None:
    # engine:task-graph concrete 宣言スキルに要求される consumption verifier /
    # dependency graph knowledge consult トークンが `### ゴールシーク配線` scope 内に全て在る。
    lint = _load_lint()
    body = lint.body_after_frontmatter(EXAMPLE.read_text(encoding="utf-8"))
    wiring = lint.WIRING_SECTION_RE.search(body)
    assert wiring, "### ゴールシーク配線 セクションが無い"
    wiring_text = wiring.group(0)
    for tok in lint._TASK_GRAPH_WIRING_TOKENS + lint._TASK_GRAPH_KNOWLEDGE_TOKENS:
        assert tok in wiring_text, f"配線トークン欠落: {tok}"


def test_example_passes_capability_graph_lint_when_bundled(tmp_path: Path) -> None:
    """example を harness へ配置し 4 script を同梱すると capability-graph lint が緑になる。

    lint-capability-graph-knowledge.py は宣言 skill ごとの scripts/ 同梱 byte-parity を hard gate
    するため、example 単体でなく harness 形状で緑を確認する。
    """
    cap_lint_path = SKILL_ROOT / "scripts/lint-capability-graph-knowledge.py"
    spec = importlib.util.spec_from_file_location("tg_cap_lint", cap_lint_path)
    cap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cap)

    skill_dir = tmp_path / "skills/run-task-graph-demo"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    for name in cap.BUNDLED_SCRIPTS:
        (skill_dir / "scripts" / name).write_bytes((TEMPLATE_SCRIPTS / name).read_bytes())

    findings, _warnings, applicable = cap.lint(tmp_path)
    assert applicable is True
    assert findings == [], f"capability-graph lint 違反: {findings}"
