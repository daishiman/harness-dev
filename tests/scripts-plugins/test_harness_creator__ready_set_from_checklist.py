"""ENG-C01 ready-set-from-checklist.py の genuine 機能テスト。

with-goal-seek engine:task-graph 変種の ready 集合ステートレス算出 (H1 実装)。
純関数を importlib でロードして実入力で assert し、main は subprocess で exit/出力を確認する。

カバー分岐:
- id_sort_key: C<n> 数値昇順 (C1<C2<C10) / 非準拠 id は末尾辞書順
- compute_ready: depends_on 全充足 pending のみ / 未充足除外 / dangling は not-ready /
  done/blocked は非 ready / 昇順ソート / 不整合 (id 欠落/status 配列不正) で ValueError
- load_checklist: 正常 / checklist 非配列で ValueError
- main(CLI): 正常 exit0 / usage exit2 / 不正 JSON exit2 / データ不整合 exit1 / --help exit0

network: false, 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins/harness-creator/skills/run-build-skill"
    / "templates/task-graph-engine/scripts/ready-set-from-checklist.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("ready_set_from_checklist", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _prog(items):
    return {"skill": "x", "goal": "g", "iteration": 0, "status": "in_progress", "checklist": items}


def _write(tmp_path, items):
    p = tmp_path / "progress.json"
    p.write_text(json.dumps(_prog(items)), encoding="utf-8")
    return p


def _run(path):
    return subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)


# --- id_sort_key ---
def test_id_sort_key_numeric_order():
    ids = ["C10", "C2", "C1", "C3"]
    assert sorted(ids, key=mod.id_sort_key) == ["C1", "C2", "C3", "C10"]


def test_id_sort_key_noncompliant_tail():
    ids = ["Cx", "C2", "alpha"]
    ordered = sorted(ids, key=mod.id_sort_key)
    assert ordered[0] == "C2"  # 準拠 id が先頭
    assert set(ordered[1:]) == {"Cx", "alpha"}


# --- compute_ready ---
def test_compute_ready_deps_satisfied():
    cl = [
        {"id": "C1", "text": "a", "status": "done"},
        {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
        {"id": "C10", "text": "c", "status": "pending", "depends_on": ["C1"]},
    ]
    assert mod.compute_ready(cl) == ["C2", "C10"]


def test_compute_ready_unsatisfied_excluded():
    cl = [
        {"id": "C1", "text": "a", "status": "pending"},
        {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
    ]
    assert mod.compute_ready(cl) == ["C1"]  # C2 は C1 未 done ゆえ除外


def test_compute_ready_no_deps_all_pending():
    cl = [{"id": "C1", "status": "pending"}, {"id": "C2", "status": "pending"}]
    assert mod.compute_ready(cl) == ["C1", "C2"]


def test_compute_ready_dangling_dep_not_ready():
    cl = [{"id": "C2", "status": "pending", "depends_on": ["CZZ"]}]
    assert mod.compute_ready(cl) == []  # 存在しない依存先は充足不能


def test_compute_ready_done_and_blocked_excluded():
    cl = [
        {"id": "C1", "status": "done"},
        {"id": "C2", "status": "blocked"},
        {"id": "C3", "status": "pending"},
    ]
    assert mod.compute_ready(cl) == ["C3"]


def test_compute_ready_missing_id_raises():
    with pytest.raises(ValueError):
        mod.compute_ready([{"status": "pending"}])


def test_compute_ready_depends_on_not_list_raises():
    with pytest.raises(ValueError):
        mod.compute_ready([{"id": "C1", "status": "pending", "depends_on": "C0"}])


def test_compute_ready_item_not_object_raises():
    with pytest.raises(ValueError):
        mod.compute_ready(["notdict"])


# --- load_checklist ---
def test_load_checklist_ok(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "status": "done"}])
    assert mod.load_checklist(p) == [{"id": "C1", "status": "done"}]


def test_load_checklist_non_array_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"checklist": {"not": "array"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        mod.load_checklist(p)


# --- main CLI ---
def test_main_ok(tmp_path):
    p = _write(tmp_path, [
        {"id": "C1", "status": "done"},
        {"id": "C2", "status": "pending", "depends_on": ["C1"]},
    ])
    r = _run(p)
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"ready": ["C2"]}


def test_main_usage_exit2():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2


def test_main_help_exit0():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0


def test_main_bad_json_exit2(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    r = _run(p)
    assert r.returncode == 2


def test_main_data_inconsistency_exit1(tmp_path):
    p = tmp_path / "prog.json"
    p.write_text(json.dumps(_prog([{"status": "pending"}])), encoding="utf-8")  # id 欠落
    r = _run(p)
    assert r.returncode == 1
