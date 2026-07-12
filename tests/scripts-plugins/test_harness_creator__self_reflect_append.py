"""ENG-C02 self-reflect-append.py の genuine 機能テスト。

with-goal-seek engine:task-graph 変種の discovered task 単一truち追記 (H3 実装)。
追記のみ (既存 item 不変)・id 重複/未知 depends_on/追記後サイクルを fail-closed 検査する。

カバー分岐:
- append_item: 正常追記 / id pattern 非準拠で ValueError / id 重複で ValueError /
  未知 depends_on で ValueError / サイクル生成で ValueError / verify_by/depends_on 省略時の形状
- _has_cycle: 非循環 False / 循環 True
- _parse_depends: カンマ分割・空要素除去
- main(CLI): 正常 exit0 で末尾追記+既存不変 / 重複 exit1 / 未知依存 exit1 / 不正 JSON exit2 /
  checklist 非配列 exit2 / 引数不足 exit2

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
    / "templates/task-graph-engine/scripts/self-reflect-append.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("self_reflect_append", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _write(tmp_path, items):
    p = tmp_path / "progress.json"
    p.write_text(json.dumps({"skill": "x", "goal": "g", "iteration": 0,
                             "status": "in_progress", "checklist": items}), encoding="utf-8")
    return p


def _run(path, *args):
    return subprocess.run([sys.executable, str(SCRIPT), str(path), *args],
                          capture_output=True, text=True)


# --- append_item ---
def test_append_item_ok():
    cl = [{"id": "C1", "text": "a", "status": "done"}]
    item = mod.append_item(cl, "C2", "new", ["C1"], "script")
    assert item == {"id": "C2", "text": "new", "status": "pending",
                    "depends_on": ["C1"], "verify_by": "script"}
    assert cl == [{"id": "C1", "text": "a", "status": "done"}]  # 引数 checklist は不変


def test_append_item_minimal_shape():
    item = mod.append_item([{"id": "C1", "status": "done"}], "C2", "t", [], None)
    assert item == {"id": "C2", "text": "t", "status": "pending"}  # depends_on/verify_by 省略


def test_append_item_bad_id_pattern():
    with pytest.raises(ValueError, match="pattern"):
        mod.append_item([], "task-1", "t", [], None)


def test_append_item_dup_id():
    with pytest.raises(ValueError, match="重複"):
        mod.append_item([{"id": "C1", "status": "done"}], "C1", "t", [], None)


def test_append_item_unknown_dep():
    with pytest.raises(ValueError, match="未知"):
        mod.append_item([{"id": "C1", "status": "done"}], "C2", "t", ["C9"], None)


def test_append_item_cycle_detected(monkeypatch):
    # 既存 item が新 item を指す状況を捏造してサイクルを強制検出させる。
    cl = [{"id": "C1", "status": "pending", "depends_on": ["C2"]}]
    # C2 は C1 に依存 → C1→C2→C1 のサイクル
    with pytest.raises(ValueError, match="サイクル"):
        mod.append_item(cl, "C2", "t", ["C1"], None)


# --- _has_cycle ---
def test_has_cycle_false():
    assert mod._has_cycle({"C1": [], "C2": ["C1"]}) is False


def test_has_cycle_true():
    assert mod._has_cycle({"C1": ["C2"], "C2": ["C1"]}) is True


def test_has_cycle_self_loop():
    assert mod._has_cycle({"C1": ["C1"]}) is True


def test_has_cycle_deep_chain_no_recursion_error():
    # 深い直鎖 (2000 段) でも RecursionError にならず False を返す (反復 DFS)
    adj = {f"C{i}": ([f"C{i+1}"] if i < 2000 else []) for i in range(2001)}
    assert mod._has_cycle(adj) is False


def test_has_cycle_diamond_no_false_positive():
    # 菱形 (共有依存先) は循環でない
    assert mod._has_cycle({"C1": ["C2", "C3"], "C2": ["C4"], "C3": ["C4"], "C4": []}) is False


# --- _parse_depends ---
def test_parse_depends():
    assert mod._parse_depends("C1, C2 ,C3") == ["C1", "C2", "C3"]
    assert mod._parse_depends("") == []


# --- main CLI ---
def test_main_ok_appends_and_preserves(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "text": "a", "status": "done"}])
    r = _run(p, "--id", "C2", "--text", "new", "--depends-on", "C1", "--verify-by", "lint")
    assert r.returncode == 0
    d = json.loads(p.read_text())
    assert d["checklist"][-1]["id"] == "C2"
    assert d["checklist"][0] == {"id": "C1", "text": "a", "status": "done"}  # 既存不変


def test_main_dup_exit1(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "status": "done"}])
    r = _run(p, "--id", "C1", "--text", "t")
    assert r.returncode == 1
    assert "重複" in r.stderr


def test_main_unknown_dep_exit1(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "status": "done"}])
    r = _run(p, "--id", "C2", "--text", "t", "--depends-on", "CZZ")
    assert r.returncode == 1


def test_main_bad_json_exit2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{broken", encoding="utf-8")
    r = _run(p, "--id", "C2", "--text", "t")
    assert r.returncode == 2


def test_main_checklist_not_array_exit2(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"checklist": "nope"}), encoding="utf-8")
    r = _run(p, "--id", "C2", "--text", "t")
    assert r.returncode == 2


def test_main_missing_required_arg_exit2(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "status": "done"}])
    r = _run(p, "--id", "C2")  # --text 欠落
    assert r.returncode == 2
