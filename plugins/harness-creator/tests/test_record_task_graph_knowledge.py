"""record-task-graph-knowledge.py (TG-C08) の機能テスト — 外ループ完了ゲート + knowledge 記録。

conftest 非依存で module-level に importlib ロードする (自己完結テスト)。網羅対象:
- 未処理 inbox → completion_gate:blocked + handback_command + exit1
- blocked handback 強化: pending_discovered_tasks[]{change_level} + needs_approval (structural 判定) +
  --plan-dir 有無で locator (--out-dir) 有無 + structural 時 --approved 承認指示 + next_steps 2 コマンド
- 完了ゲート第2段: --task-state の blocked node 残存 → completion_gate:blocked + blocked_tasks[]
  {id,blocked_reason} + 分岐 next_steps (人手救済 / emit-discovered-task 外ループ合流)
- inbox_absent: inbox ディレクトリ不在 (外ループ未発火) と 実在+全件処理済 の区別を全出力形で明示
- 全解決 status / inbox 不在 → completion_gate:ok + exit0
- scan_pending_discovered の pending 判定 (未設定/pending/読めない form)
- distill_events が生ログを丸写しせず signal だけを limit 件へ蒸留 (noise 除外)
- build_knowledge_entry が add_entry.py 必須6フィールドを生成し source は参照のみ
- write_knowledge が Loop A + Loop B 双方へ追記 (dry-run 経路確認 + 実 add_entry 統合)
- graph / plan を一切書かない (依存方向担保)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_ADD_ENTRY = (SCRIPTS.parent / "skills/run-build-skill/templates/knowledge-skeleton"
              / "scripts/add_entry.py")
sys.path.insert(0, str(SCRIPTS))


def _load(stem: str):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rec = _load("record-task-graph-knowledge")


# ─────────────────────────── fixtures / helpers ───────────────────────────
def _form(node_id="T9", status=None, discovering="T1", change_level="additive") -> dict:
    form = {
        "schema_version": "1.0",
        "discovering_task_id": discovering,
        "reason": "plan 未網羅タスクを発見した",
        "discovered_at_artifact": "eval-log/x/build/route-1.json",
        "proposed_node": {"id": node_id, "title": node_id, "phase_ref": "P02",
                          "entity_ref": None, "state": "pending", "write_scope": node_id},
        "change_level": change_level,
    }
    if status is not None:
        form["status"] = status
    return form


def _write(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def _inbox(tmp_path, forms: dict | None = None) -> Path:
    d = tmp_path / "discovered-tasks"
    d.mkdir()
    for name, form in (forms or {}).items():
        _write(d / name, form)
    return d


def _events(tmp_path, lines: list[dict], name="task-events.jsonl") -> Path:
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")
    return p


def _make_store(base: Path, consult_at: str) -> Path:
    """add_entry.py が受理する consult_at 宣言済み knowledge store dir を作る。"""
    base.mkdir(parents=True, exist_ok=True)
    (base / "knowledge-index.json").write_text(
        json.dumps({"version": "1.0.0", "consult_at": [consult_at], "categories": [],
                    "global_keywords": {}, "synonyms": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return base


# ─────────────────────────── scan_pending_discovered ───────────────────────────
def test_scan_absent_dir_returns_empty(tmp_path):
    assert rec.scan_pending_discovered(tmp_path / "nope") == []


def test_scan_pending_when_status_unset_or_pending(tmp_path):
    inbox = _inbox(tmp_path, {"a.json": _form(status=None), "b.json": _form(node_id="T8", status="pending")})
    pending = rec.scan_pending_discovered(inbox)
    assert len(pending) == 2
    assert {Path(p["path"]).name for p in pending} == {"a.json", "b.json"}


def test_scan_skips_processed_statuses(tmp_path):
    inbox = _inbox(tmp_path, {
        "acc.json": _form(status="accepted"),
        "rej.json": _form(node_id="T8", status="rejected"),
        "sup.json": _form(node_id="T7", status="superseded"),
    })
    assert rec.scan_pending_discovered(inbox) == []


def test_scan_unreadable_form_counts_as_pending(tmp_path):
    inbox = tmp_path / "discovered-tasks"
    inbox.mkdir()
    (inbox / "broken.json").write_text("{not json", encoding="utf-8")
    pending = rec.scan_pending_discovered(inbox)
    assert len(pending) == 1 and pending[0]["status"] is None


# ─────────────────────────── completion gate (main) ───────────────────────────
def test_gate_blocked_emits_handback_and_exit1(tmp_path, capsys):
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "blocked"
    # pending_discovered_tasks は各 form の path + change_level を携帯 (structural 判定用)
    assert out["pending_discovered_tasks"] == [
        {"path": str(inbox / "a.json"), "change_level": "additive", "status": None}
    ]
    assert out["handback_command"].startswith("run-plugin-dev-plan --mode update --discovered-inbox")
    assert str(inbox) in out["handback_command"]


def test_gate_blocked_additive_only_no_approval_and_no_locator(tmp_path, capsys):
    """additive のみ未処理 + --plan-dir 無し → needs_approval=false / handback に locator (--out-dir) 無し。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None, change_level="additive"),
                              "b.json": _form(node_id="T8", status="pending", change_level="additive")})
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["needs_approval"] is False
    # locator (--out-dir) を含まない
    assert "--out-dir" not in out["handback_command"]
    # 承認指示も付かない
    assert "--approved" not in out["handback_command"]
    # next_steps は 2 コマンド [planner drain, capability-build 再実行]
    assert len(out["next_steps"]) == 2
    assert out["next_steps"][0].startswith("run-plugin-dev-plan --mode update --discovered-inbox")
    assert "/capability-build" in out["next_steps"][1]
    # 再入は task-graph route モード (--handoff のみ・--route-id なしで改善グラフ全体を再駆動)
    assert "--handoff" in out["next_steps"][1]
    assert "--route-id" not in out["next_steps"][1]


def test_gate_blocked_structural_sets_needs_approval_and_approval_instruction(tmp_path, capsys):
    """structural 含む未処理 → needs_approval=true + handback 主コマンドへ --approved 直付与 (F1)。"""
    inbox = _inbox(tmp_path, {
        "a.json": _form(node_id="T9", status=None, change_level="additive"),
        "b.json": _form(node_id="T8", status="pending", change_level="structural"),
    })
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["needs_approval"] is True
    # F1: structural 二段受理 (--approved) が run-plugin-dev-plan 主コマンドへ実引数として直接付く
    # (散文の括弧注や低レベル script 直叩きに埋めず主コマンド1本で承認まで閉じる)
    assert out["handback_command"].startswith("run-plugin-dev-plan --mode update --discovered-inbox")
    assert out["handback_command"].endswith("--approved")
    assert "accept-discovered-task.py" not in out["handback_command"]
    # pending_discovered_tasks に change_level が両方載る
    levels = {t["change_level"] for t in out["pending_discovered_tasks"]}
    assert levels == {"additive", "structural"}
    # next_steps[0] も承認を主コマンドへ携帯 (TG-C08 出力単体で次の一手が分かる)
    assert len(out["next_steps"]) == 2
    assert out["next_steps"][0].endswith("--approved")


def test_gate_blocked_plan_dir_adds_locator(tmp_path, capsys):
    """--plan-dir 有り → handback へ planner locator (--out-dir <PLAN_DIR>) を含む。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    plan_dir = str(tmp_path / "plugin-plans" / "acme")
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--plan-dir", plan_dir])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert f"--out-dir {plan_dir}" in out["handback_command"]
    # next_steps[0] (planner drain 完全形) にも locator が載る
    assert f"--out-dir {plan_dir}" in out["next_steps"][0]


def test_gate_blocked_handoff_arg_makes_rebuild_command_concrete(tmp_path, capsys):
    """--handoff 指定時: next_steps[1] の <handoff> placeholder が実パスへ置換され完全形になる (H-02)。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    handoff = str(tmp_path / "plugin-plans" / "acme" / "handoff-run-plugin-dev-plan.json")
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--handoff", handoff])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["next_steps"][1] == f"/capability-build --handoff {handoff}"
    assert "<handoff>" not in out["next_steps"][1]


def test_gate_blocked_without_handoff_keeps_template_placeholder(tmp_path, capsys):
    """--handoff 未指定時: 後方互換で <handoff> テンプレート表示のまま。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["next_steps"][1] == "/capability-build --handoff <handoff>"


def test_gate_blocked_unreadable_form_change_level_none_not_approval(tmp_path, capsys):
    """読めない form は change_level None (structural デッドロック無し) → needs_approval に加算しない。"""
    inbox = tmp_path / "discovered-tasks"
    inbox.mkdir()
    (inbox / "broken.json").write_text("{not json", encoding="utf-8")
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["needs_approval"] is False
    assert out["pending_discovered_tasks"][0]["change_level"] is None


def test_gate_ok_when_all_resolved_exit0(tmp_path, capsys):
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "ok"


def test_gate_ok_when_inbox_absent_exit0(tmp_path, capsys):
    rc = rec.main(["--discovered-inbox", str(tmp_path / "nope"),
                   "--task-events", str(tmp_path / "none.jsonl"), "--dry-run"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["completion_gate"] == "ok"


def test_missing_inbox_and_slug_usage_exit2(capsys):
    rc = rec.main(["--dry-run"])
    assert rc == 2


# ─────────────────────────── 完了ゲート第2段 (blocked node 残存) ───────────────────────────
def _task_state(tmp_path, nodes, name="task-state.json") -> Path:
    return _write(tmp_path / name, {"schema_version": "1.0", "nodes": nodes})


def test_gate_blocked_when_blocked_nodes_remain(tmp_path, capsys):
    """pending discovered-task ゼロでも blocked node が残れば completion_gate:blocked + exit1。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    state = _task_state(tmp_path, [
        {"id": "T2", "state": "blocked", "blocked_reason": "propagated", "origin_task_id": "T1"},
        {"id": "T1", "state": "blocked", "blocked_reason": "origin-failure"},
        {"id": "T3", "state": "done"},
    ])
    events_p = tmp_path / "task-events.jsonl"
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(events_p),
                   "--task-state", str(state)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "blocked"
    assert out["inbox_absent"] is False
    # blocked_tasks は id 昇順で blocked_reason を携帯 (origin-failure / propagated 双方)
    assert out["blocked_tasks"] == [
        {"id": "T1", "blocked_reason": "origin-failure"},
        {"id": "T2", "blocked_reason": "propagated"},
    ]
    # 分岐指示: 人手救済 (受入基準修正→再検証) または emit-discovered-task 外ループ合流
    assert any("人手救済" in s and "受入基準" in s for s in out["next_steps"])
    assert any("emit-discovered-task" in s and str(inbox) in s for s in out["next_steps"])
    # gate 判定確定 event も第2段で append される
    blocked_events = [e for e in _read_events(events_p) if e.get("type") == "build_blocked"]
    assert len(blocked_events) == 1 and blocked_events[0]["blocked_task_count"] == 2


def test_gate_blocked_nodes_handoff_arg_makes_rescue_command_concrete(tmp_path, capsys):
    """--handoff 指定時: 人手救済側の再実行コマンドも実パスの完全形になる。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    state = _task_state(tmp_path, [{"id": "T1", "state": "blocked", "blocked_reason": "origin-failure"}])
    handoff = str(tmp_path / "plugin-plans" / "acme" / "handoff-run-plugin-dev-plan.json")
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--task-state", str(state), "--handoff", handoff])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    rescue = next(s for s in out["next_steps"] if "人手救済" in s)
    assert f"/capability-build --handoff {handoff}" in rescue
    assert "<handoff>" not in rescue


def test_gate_not_blocked_when_no_blocked_nodes(tmp_path, capsys):
    """blocked node の無い task-state は gate を塞がない (done/pending/running は対象外)。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    state = _task_state(tmp_path, [{"id": "T1", "state": "done"},
                                   {"id": "T2", "state": "pending"},
                                   {"id": "T3", "state": "running"}])
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--task-state", str(state), "--dry-run"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["completion_gate"] == "ok"


def test_pending_discovered_gate_takes_precedence_over_blocked_nodes(tmp_path, capsys):
    """第1段 (未処理 discovered-task) が第2段より優先し handback を出す。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    state = _task_state(tmp_path, [{"id": "T1", "state": "blocked", "blocked_reason": "origin-failure"}])
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--task-state", str(state)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert "pending_discovered_tasks" in out and "blocked_tasks" not in out


# ─────────────────────────── inbox_absent (未発火と処理済の区別) ───────────────────────────
def test_inbox_absent_true_when_dir_missing(tmp_path, capsys):
    """inbox ディレクトリ不在 = 外ループ未発火を inbox_absent:true で明示する。"""
    rc = rec.main(["--discovered-inbox", str(tmp_path / "nope"),
                   "--task-events", str(tmp_path / "none.jsonl"), "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "ok" and out["inbox_absent"] is True


def test_inbox_absent_false_when_all_processed(tmp_path, capsys):
    """inbox 実在 + 全件処理済は inbox_absent:false (未発火と区別)。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    rc = rec.main(["--discovered-inbox", str(inbox),
                   "--task-events", str(tmp_path / "none.jsonl"), "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "ok" and out["inbox_absent"] is False


def test_blocked_payload_carries_inbox_absent(tmp_path, capsys):
    """第1段 blocked 出力にも inbox_absent が載る (全出力形で携帯)。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--dry-run"])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["inbox_absent"] is False


# ─────────────────────────── distill_events ───────────────────────────
def test_distill_extracts_signals_and_drops_noise(tmp_path):
    events = _events(tmp_path, [
        {"ts": "2026-07-06T00:00:00Z", "type": "state_transition", "task_id": "T1", "to_state": "running"},
        {"ts": "2026-07-06T00:01:00Z", "type": "lease_renewed", "task_id": "T1"},
        {"ts": "2026-07-06T00:02:00Z", "type": "graph_hash_pinned", "graph_hash": "sha256:x"},
        {"ts": "2026-07-06T00:03:00Z", "type": "lease_reaped", "task_id": "T1"},
        {"ts": "2026-07-06T00:04:00Z", "type": "state_transition", "task_id": "T2",
         "to_state": "blocked", "blocked_reason": "propagated", "origin_task_id": "T1"},
    ])
    lessons = rec.distill_events(events, {}, limit=10)
    signals = {l["signal"] for l in lessons}
    assert signals == {"retry-resolved", "blocked-propagation"}
    # noise (running / renew / pin) は一切含まれない
    assert all(l["signal"] not in ("state_transition", "lease_renewed", "graph_hash_pinned")
               for l in lessons)


def test_distill_does_not_copy_raw_log_verbatim(tmp_path):
    raw = {"ts": "2026-07-06T00:03:00Z", "type": "lease_reaped", "task_id": "T1",
           "reason": "lease_expired", "from_state": "running", "to_state": "pending"}
    events = _events(tmp_path, [raw])
    lessons = rec.distill_events(events, {}, limit=3)
    assert len(lessons) == 1
    msg = lessons[0]["message"]
    # 生ログ JSON 全文の複製ではなく synthesized な要約
    assert msg != json.dumps(raw, ensure_ascii=False)
    assert "from_state" not in msg and "{" not in msg


def test_distill_respects_limit(tmp_path):
    events = _events(tmp_path, [
        {"ts": f"t{i}", "type": "state_transition", "task_id": f"T{i}", "to_state": "blocked"}
        for i in range(10)
    ])
    lessons = rec.distill_events(events, {}, limit=3)
    assert len(lessons) == 3


def test_distill_reads_stall_summary_diagnosis(tmp_path):
    summary = {"stall": {"stalled": True, "has_spec_gap": True, "diagnosis": [
        {"task_id": "T2", "message": "T2 は depends_on T4 が task-graph 上に不在", "kind": "spec-gap"},
        {"task_id": "T3", "message": "T3 の producer が route 失敗で blocked", "kind": "build-failure"},
    ]}}
    lessons = rec.distill_events(None, summary, limit=10)
    signals = {l["signal"] for l in lessons}
    assert "dependency-stall" in signals and "blocked-origin" in signals


def test_distill_reads_handoff_notes(tmp_path):
    summary = {"handoff_notes": [
        {"task_id": "T1", "route_id": "C01", "file": "route-C01.json",
         "friction_points": ["依存の受け渡しで詰まった"], "downstream_watchouts": []},
    ]}
    lessons = rec.distill_events(None, summary, limit=10)
    assert any(l["signal"] == "friction" for l in lessons)


# ─────────────────────────── route report 実体レーン (deviations/handover) ───────────────────────────
def _route_report(tmp_path, name, **fields) -> Path:
    report = {"schema_version": "1.0.0", "plugin_slug": "acme", "route_id": "C01",
              "component_kind": "script", "name": name, "builder": "b",
              "build_target": "plugins/acme/scripts/x.py", "status": "success",
              "summary": "s", "deviations": [], "evidence": [], "inputs_consumed": [],
              "handover": None}
    report.update(fields)
    return _write(tmp_path / name, report)


def test_collect_report_lessons_reads_deviations_and_handover(tmp_path):
    """route-build-report の deviations[] (string 配列) と handover を lesson 候補へ蒸留する。"""
    rp = _route_report(tmp_path, "route-C01.json",
                       deviations=["evaluator ゲートは独立 context 起動不能のため自己適用した"],
                       handover="C01 は build 済み。後続は verdict receipt を検証すること")
    state = {"nodes": [{"id": "T1", "state": "done", "route_report": str(rp)}]}
    lessons = rec._collect_report_lessons(state)
    signals = [l["signal"] for l in lessons]
    # deviation が handover より先 (limit 打ち切りで計画逸脱を優先)
    assert signals == ["deviation", "handover"]
    assert "自己適用" in lessons[0]["message"]
    assert lessons[0]["source_ref"] == {"file": str(rp), "task_id": "T1", "route_id": "C01"}


def test_collect_report_lessons_reads_string_array_handoff_notes(tmp_path):
    """checklist-verification 等の handoff_notes (string 配列形式) も lesson 候補として消費する。"""
    rp = _write(tmp_path / "plan-P01-x-01.json", {
        "report_kind": "checklist-verification", "task_id": "P01-x-01", "verdict": "PASS",
        "handoff_notes": ["purpose非空・C1-9完備・語彙導出一貫"],
    })
    state = {"nodes": [{"id": "P01-x-01", "state": "done", "route_report": str(rp)}]}
    lessons = rec._collect_report_lessons(state)
    assert len(lessons) == 1 and lessons[0]["signal"] == "handover"
    assert "C1-9完備" in lessons[0]["message"]


def test_collect_report_lessons_clips_long_prose(tmp_path):
    """report 由来の長文 prose は蒸留上限で打ち切り生ログを丸写ししない。"""
    rp = _route_report(tmp_path, "route-C02.json", deviations=["あ" * 500])
    state = {"nodes": [{"id": "T1", "state": "done", "route_report": str(rp)}]}
    lessons = rec._collect_report_lessons(state)
    assert len(lessons[0]["message"]) <= rec._REPORT_MESSAGE_CLIP + 1
    assert lessons[0]["message"].endswith("…")


def test_collect_report_lessons_fail_soft_on_missing_or_broken_report(tmp_path):
    """report 不在・非 JSON は skip (gate 判定へ影響させない fail-soft)。"""
    broken = tmp_path / "route-broken.json"
    broken.write_text("{not json", encoding="utf-8")
    state = {"nodes": [
        {"id": "T1", "state": "done", "route_report": str(tmp_path / "nope.json")},
        {"id": "T2", "state": "done", "route_report": str(broken)},
        {"id": "T3", "state": "done"},
    ]}
    assert rec._collect_report_lessons(state) == []


def test_roundtrip_records_deviation_lessons_from_route_reports(tmp_path, capsys):
    """往復 fixture: task-state → route report deviations → Loop A/B へ entry 記録 (entries_recorded>=1)。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_a = _make_store(tmp_path / "targetkb", "runtime")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    rp = _route_report(tmp_path, "route-C14.json", route_id="C14",
                       deviations=["evaluator 独立起動不能のため rubric 観点を自己適用した"])
    state = _task_state(tmp_path, [{"id": "P05-C14-01", "state": "done", "route_report": str(rp)}])
    rc = rec.main([
        "--target-plugin-slug", "acme-plugin",
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(tmp_path / "none.jsonl"),
        "--task-state", str(state),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["knowledge_record_status"] == "ok"
    assert out["entries_recorded"] >= 1
    assert out["empty_reason"] is None
    a_cat = json.loads((loop_a / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert any(i["id"].startswith("runtime-deviation_") for i in a_cat["items"])


def test_zero_lessons_reports_ok_no_lessons_with_empty_reason(tmp_path, capsys):
    """蒸留 0 件は vacuous "ok" でなく ok_no_lessons + entries_recorded/empty_reason を明示する。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    # noise のみの events (蒸留レーンに合致しない)
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_renewed", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "ok"
    assert out["entries_recorded"] == 0
    assert out["knowledge_record_status"] == "ok_no_lessons"
    assert out["empty_reason"] == "no distillable events matched distiller lanes"


# ─────────────────────────── build_knowledge_entry ───────────────────────────
def test_build_entry_has_six_required_fields():
    lesson = {"signal": "retry-resolved", "message": "lease 回収で再試行",
              "source_ref": {"file": "task-events.jsonl", "task_id": "T1", "event_id": "L4"}}
    entry = rec.build_knowledge_entry(lesson, lesson["source_ref"], "acme-plugin")
    for key in ("id", "title", "intent", "background", "keywords", "source"):
        assert entry.get(key), f"必須フィールド欠落: {key}"
    # source は参照だけ (file/task_id/route_id/event_id のみ)
    assert set(entry["source"].keys()) <= {"file", "task_id", "route_id", "event_id"}
    assert entry["source"]["task_id"] == "T1"
    assert "acme-plugin" in entry["keywords"]


def test_build_entry_id_is_deterministic():
    lesson = {"signal": "blocked-origin", "message": "route 失敗", "source_ref": {"task_id": "T2"}}
    a = rec.build_knowledge_entry(lesson, lesson["source_ref"], "p")
    b = rec.build_knowledge_entry(lesson, lesson["source_ref"], "p")
    assert a["id"] == b["id"]


def test_build_entry_passes_add_entry_validation():
    """add_entry.validate_entry が build_knowledge_entry の 6 フィールドを通す。"""
    add = _load_add_entry()
    lesson = {"signal": "artifact-missing", "message": "producer 成果物欠落",
              "source_ref": {"file": "task-events.jsonl", "task_id": "T3"}}
    entry = rec._entry_for_store(rec.build_knowledge_entry(lesson, lesson["source_ref"], "p"))
    errors, _ = add.validate_entry(entry)
    assert errors == [], errors


def _load_add_entry():
    spec = importlib.util.spec_from_file_location("add_entry", _ADD_ENTRY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ─────────────────────────── write_knowledge / Loop A+B ───────────────────────────
def test_dry_run_confirms_both_loop_routes_without_writing(tmp_path, capsys):
    loop_a = tmp_path / "targetkb"
    loop_b = tmp_path / "harnesskb"
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--dry-run",
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["loop_a_store"] == str(loop_a)
    assert out["loop_b_store"] == str(loop_b)
    assert len(out["entry_candidates"]) == 1
    # dry-run は書込まない
    assert not loop_a.exists() and not loop_b.exists()


def test_write_knowledge_appends_to_both_loops(tmp_path):
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_a = _make_store(tmp_path / "targetkb", "runtime")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [
        {"ts": "t1", "type": "lease_reaped", "task_id": "T1"},
    ])
    rc = rec.main([
        "--target-plugin-slug", "acme-plugin",
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    a_cat = json.loads((loop_a / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    b_cat = json.loads((loop_b / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert len(a_cat["items"]) == 1 and len(b_cat["items"]) == 1
    # 双方に同一 entry id が焼かれる
    assert a_cat["items"][0]["id"] == b_cat["items"][0]["id"]
    assert a_cat["items"][0]["id"].startswith("runtime-")


def test_write_knowledge_single_store_direct(tmp_path):
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    store = _make_store(tmp_path / "store", "build-time")
    entry = rec.build_knowledge_entry(
        {"signal": "blocked-origin", "message": "route 失敗"}, {"task_id": "T2"}, "p")
    rec.write_knowledge(entry, store, _ADD_ENTRY)
    cat = json.loads((store / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert cat["items"][0]["id"] == entry["id"]


def test_write_knowledge_missing_add_entry_raises(tmp_path):
    entry = rec.build_knowledge_entry({"signal": "friction", "message": "x"}, {}, "p")
    with pytest.raises(FileNotFoundError):
        rec.write_knowledge(entry, tmp_path, tmp_path / "no_such_add_entry.py")


def test_write_knowledge_duplicate_id_is_idempotent(tmp_path, capsys):
    """gate 再実行 (resume) で同一決定論 id の再 add は冪等成功として扱う (record_failed にしない)。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_a = _make_store(tmp_path / "targetkb", "runtime")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [
        {"ts": "t1", "type": "lease_reaped", "task_id": "T1"},
    ])
    args = [
        "--target-plugin-slug", "acme-plugin",
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ]
    assert rec.main(list(args)) == 0
    capsys.readouterr()
    assert rec.main(list(args)) == 0  # 2 回目 = 全 entry が重複
    out = json.loads(capsys.readouterr().out)
    assert out["knowledge_record_status"] == "ok"
    cat = json.loads((loop_a / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert len(cat["items"]) == 1  # 二重追記されない


def test_write_knowledge_same_store_dedup(tmp_path, capsys):
    """自己 build (Loop A == Loop B の同一 store) では二重 add せず 1 回だけ書く (重複 id 拒否を回避)。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    store = _make_store(tmp_path / "selfkb", "runtime")
    events = _events(tmp_path, [
        {"ts": "t1", "type": "lease_reaped", "task_id": "T1"},
    ])
    rc = rec.main([
        "--target-plugin-slug", "harness-creator",
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(store),
        "--harness-knowledge-dir", str(store),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["knowledge_record_status"] == "ok"
    assert out["entries_recorded"] == 1
    cat = json.loads((store / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert len(cat["items"]) == 1


def test_entries_loop_a_unwired_warns_and_records_loop_b_only(tmp_path, capsys):
    """F2: Loop A 未配線 + entry あり → 完了を block せず (exit0) WARN + Loop B のみ記録。

    完了ゲート (制御) と knowledge 記録 (ベストエフォート) の疎結合: Loop A store が
    orchestrator から渡されなくても build 完了を巻き込んで落とさない。
    """
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    captured = capsys.readouterr()
    assert rc == 0  # 疎結合: 未配線でも完了を block しない
    out = json.loads(captured.out)
    assert out["completion_gate"] == "ok"
    assert out["knowledge_record_status"] == "loop_a_skipped"
    assert "Loop A" in captured.err
    # Loop B には記録される (片系統は担保)
    b_cat = json.loads((loop_b / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert len(b_cat["items"]) == 1


def test_loop_a_store_absent_precheck_classifies_skipped(tmp_path, capsys):
    """store ディレクトリ不在は事前検知で loop_a_skipped へ分類 (record_failed にしない)。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(tmp_path / "no_such_store"),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["knowledge_record_status"] == "loop_a_skipped"
    assert out["store_results"]["loop_a"]["status"] == "skipped"
    assert "不在" in out["store_results"]["loop_a"]["reason"]
    # Loop B は per-store 隔離で記録される
    assert out["store_results"]["loop_b"] == {"status": "ok", "recorded": 1}
    assert out["entries_recorded"] == 1


def test_loop_a_store_without_consult_at_classifies_skipped(tmp_path, capsys):
    """consult_at 未宣言 store は事前検知で loop_a_skipped へ分類 (KL-007 事前検査)。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_a = tmp_path / "targetkb"
    loop_a.mkdir()
    (loop_a / "knowledge-index.json").write_text(
        json.dumps({"version": "1.0.0", "categories": []}), encoding="utf-8")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["knowledge_record_status"] == "loop_a_skipped"
    assert "consult_at" in out["store_results"]["loop_a"]["reason"]
    assert out["store_results"]["loop_b"]["recorded"] == 1


def test_loop_a_write_failure_does_not_abort_loop_b(tmp_path, capsys):
    """Loop A の実書込失敗 (store 単位 try 隔離) でも Loop B へは全 entry 記録される。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_a = _make_store(tmp_path / "targetkb", "runtime")
    # 事前検知は通る (index+consult_at あり) が add_entry が category file 破損で失敗する
    (loop_a / "knowledge-build-patterns.json").write_text("{broken json", encoding="utf-8")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0  # 記録失敗を完了へ伝播させない
    out = json.loads(capsys.readouterr().out)
    assert out["knowledge_record_status"] == "record_failed"
    assert out["store_results"]["loop_a"]["status"] == "failed"
    assert out["store_results"]["loop_a"]["recorded"] == 0
    # per-store 隔離: Loop B は巻き込まれず記録される
    assert out["store_results"]["loop_b"] == {"status": "ok", "recorded": 1}
    assert out["entries_recorded"] == 1
    b_cat = json.loads((loop_b / "knowledge-build-patterns.json").read_text(encoding="utf-8"))
    assert len(b_cat["items"]) == 1


def test_check_store_ready_reasons(tmp_path):
    """check_store_ready の事前検知 3 分類 (dir 不在 / index 不在 / consult_at 未宣言)。"""
    assert "不在" in rec.check_store_ready(tmp_path / "nope")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert "knowledge-index.json" in rec.check_store_ready(empty)
    undeclared = tmp_path / "undeclared"
    undeclared.mkdir()
    (undeclared / "knowledge-index.json").write_text("{}", encoding="utf-8")
    assert "consult_at" in rec.check_store_ready(undeclared)
    ready = _make_store(tmp_path / "ready", "runtime")
    assert rec.check_store_ready(ready) is None


def test_knowledge_write_failure_does_not_block_completion(tmp_path, capsys):
    """F2: add_entry 不在で knowledge 記録が失敗しても完了ゲートは ok を維持 (exit0)。"""
    loop_a = _make_store(tmp_path / "targetkb", "runtime")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(tmp_path / "no_such_add_entry.py"),
    ])
    captured = capsys.readouterr()
    assert rc == 0  # knowledge 記録失敗を完了へ伝播させない
    out = json.loads(captured.out)
    assert out["completion_gate"] == "ok"
    assert out["knowledge_record_status"] == "record_failed"


# ─────────────────────────── gate 判定 event 化 (S-11) ───────────────────────────
def _read_events(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_gate_blocked_appends_build_blocked_event(tmp_path):
    """blocked 判定確定後に task-events.jsonl へ build_blocked を append (TG-C02 append_event 経由)。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status=None, change_level="structural")})
    events_p = tmp_path / "task-events.jsonl"
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(events_p)])
    assert rc == 1
    events = _read_events(events_p)
    blocked = [e for e in events if e.get("type") == "build_blocked"]
    assert len(blocked) == 1
    assert blocked[0]["pending_count"] == 1 and blocked[0]["needs_approval"] is True
    assert blocked[0]["ts"]  # append_event が ts を付与 (単一 writer 規約の形式)


def test_gate_ok_appends_build_completed_event(tmp_path):
    """ok 判定確定後に build_completed を append (knowledge 記録結果を携帯)。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events_p = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--discovered-inbox", str(tmp_path / "nope"),
        "--task-events", str(events_p),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    completed = [e for e in _read_events(events_p) if e.get("type") == "build_completed"]
    assert len(completed) == 1
    assert completed[0]["entries_recorded"] == 1
    assert completed[0]["knowledge_record_status"] == "loop_a_skipped"


def test_dry_run_does_not_append_gate_events(tmp_path):
    """--dry-run は gate event を書かない (blocked/ok 双方)。"""
    # blocked + dry-run
    inbox = _inbox(tmp_path, {"a.json": _form(status=None)})
    events_p = tmp_path / "task-events.jsonl"
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(events_p), "--dry-run"])
    assert rc == 1
    assert not events_p.exists()
    # ok + dry-run (既存 events は読取のみで不変)
    events_p2 = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}], name="e2.jsonl")
    before = events_p2.read_bytes()
    rc = rec.main(["--discovered-inbox", str(tmp_path / "nope"), "--task-events", str(events_p2),
                   "--dry-run"])
    assert rc == 0
    assert events_p2.read_bytes() == before


# ─────────────────────────── 依存方向担保 (graph 非書込) ───────────────────────────
def test_never_writes_task_graph_or_plan(tmp_path, capsys):
    """gate ok の記録経路が task-graph.json / phase-*.md / component-inventory.json を書かない。"""
    if not _ADD_ENTRY.exists():
        pytest.skip("add_entry.py テンプレートが見つからない")
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    graph_p = build_dir / "task-graph.json"
    graph_before = {"schema_version": "1.0", "nodes": [{"id": "T1"}], "edges": []}
    _write(graph_p, graph_before)
    graph_bytes = graph_p.read_bytes()

    loop_a = _make_store(tmp_path / "targetkb", "runtime")
    loop_b = _make_store(tmp_path / "harnesskb", "build-time")
    events = _events(tmp_path, [{"ts": "t1", "type": "lease_reaped", "task_id": "T1"}])
    rc = rec.main([
        "--target-plugin-slug", "p",
        "--discovered-inbox", str(build_dir / "discovered-tasks"),
        "--task-events", str(events),
        "--target-knowledge-dir", str(loop_a),
        "--harness-knowledge-dir", str(loop_b),
        "--add-entry-path", str(_ADD_ENTRY),
    ])
    assert rc == 0
    # task-graph.json はバイト単位で不変
    assert graph_p.read_bytes() == graph_bytes
    # plan 成果物は一切生成されない
    assert not list(build_dir.glob("phase-*.md"))
    assert not (build_dir / "component-inventory.json").exists()


# ─────────────────────────── 完了ゲート第3段 (.claude symlink drift) ───────────────────────────
def _fake_repo(tmp_path, generator_exit: int):
    """唯一の生成器 scripts/build-claude-symlinks.py を持つ repo root と配下 task-state を模す。"""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "build-claude-symlinks.py").write_text(
        "import sys\n"
        "print('created=0 updated=0 noop=1 conflict=0 missing=2')\n"
        f"sys.exit({generator_exit})\n",
        encoding="utf-8")
    build_dir = root / "eval-log" / "p" / "build"
    build_dir.mkdir(parents=True)
    state = _write(build_dir / "task-state.json",
                   {"schema_version": "1.0", "nodes": [{"id": "T1", "state": "done"}]})
    return root, state


def test_gate_blocked_on_claude_symlink_drift(tmp_path, capsys):
    """inbox/blocked node 全解決でも .claude symlink drift なら blocked + fix_command 単体提示。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    root, state = _fake_repo(tmp_path, generator_exit=1)
    events_p = tmp_path / "task-events.jsonl"
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(events_p),
                   "--task-state", str(state)])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "blocked"
    gate = out["claude_symlink_gate"]
    assert gate["status"] == "drift"
    assert gate["repo_root"] == str(root)
    assert gate["fix_command"] == "bash scripts/sync-skills-to-claude.sh --apply"
    assert any("sync-skills-to-claude.sh --apply" in s for s in out["next_steps"])
    # gate 判定確定 event も第3段で append される
    blocked_events = [e for e in _read_events(events_p) if e.get("type") == "build_blocked"]
    assert len(blocked_events) == 1 and blocked_events[0]["claude_symlink_gate"] == "drift"


def test_gate_ok_when_symlink_check_green(tmp_path, capsys):
    """--check exit0 なら claude_symlink_gate:ok を携帯して completion_gate:ok。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    root, state = _fake_repo(tmp_path, generator_exit=0)
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--task-state", str(state), "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "ok"
    assert out["claude_symlink_gate"] == {"status": "ok", "repo_root": str(root)}


def test_gate_symlink_skipped_when_generator_absent(tmp_path, capsys):
    """生成器を持つ祖先なし (隔離環境/配布先) は fail-soft skip で完了を block しない。"""
    inbox = _inbox(tmp_path, {"a.json": _form(status="accepted")})
    state = _task_state(tmp_path, [{"id": "T1", "state": "done"}])
    rc = rec.main(["--discovered-inbox", str(inbox), "--task-events", str(tmp_path / "none.jsonl"),
                   "--task-state", str(state), "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["completion_gate"] == "ok"
    assert out["claude_symlink_gate"]["status"] == "skipped"
