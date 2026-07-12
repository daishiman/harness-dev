"""plugins/skill-governance-automation/scripts/compose-rubrics.py の genuine 機能テスト。

設計書29 に基づく rubric 合成スクリプト compose-rubrics.py の純関数と main(argv) の全分岐を
tmp_path fixture で網羅する。network: false / keychain: なし / 実 repo 書換: なし(全 tmp_path)。

スクリプトは importlib.util.spec_from_file_location で実ファイルパスから直接ロードし、純関数
(canonical_json / load_ref / validate_schema / detect_cycles / deep_merge / merge_rules /
compose) を実入力で呼んで assert する。main は subprocess(sys.executable)で exit code/出力を assert。

カバー分岐:
- canonical_json: ソート・区切り・非 ASCII 保持
- load_ref: 直接パス(存在/不在)、ref- プレフィクス(references/ 優先解決 / フォールバック / 不在)
- validate_schema: rules 欠落 / rules 非 list / layer 不正 / rule 非 dict / id 欠落 / id 重複 / 正常
- detect_cycles: 非循環 / 自己循環 / 相互循環
- deep_merge: dict 再帰マージ / 非衝突スカラ / 衝突 error / 衝突 warn-and-merge / 衝突 most-specific-wins
- merge_rules: override / 新規追加 / id 衝突 strict(raise) / policy=error(raise) / warn-and-merge / 静かにマージ
- compose: 不正 strategy / 不正 policy / 単一 / 複数 deep-merge / layered / strict 衝突 / レイヤ順ソート / hash 決定論
- main: 正常 exit0 / load 失敗 exit1 / 不正 JSON exit1 / 引数欠落(argparse exit2)
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-governance-automation" / "scripts" / "compose-rubrics.py"

SPEC = importlib.util.spec_from_file_location("compose_rubrics_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _write(p: Path, data: dict) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ── canonical_json ──────────────────────────────────────────────────────────
def test_canonical_json_sorts_keys_and_compacts():
    s = MOD.canonical_json({"b": 1, "a": 2})
    assert s == '{"a":2,"b":1}'


def test_canonical_json_preserves_non_ascii():
    s = MOD.canonical_json({"layer": "深度"})
    assert "深度" in s
    assert "\\u" not in s


# ── load_ref: 直接パス ───────────────────────────────────────────────────────
def test_load_ref_direct_path(tmp_path):
    p = _write(tmp_path / "r.json", {"layer": "L0", "rules": []})
    ref, resolved, data = MOD.load_ref(str(p))
    assert ref == str(p)
    assert resolved == p.resolve()
    assert data == {"layer": "L0", "rules": []}


def test_load_ref_direct_path_missing(tmp_path):
    with pytest.raises(ValueError, match="rubric not found"):
        MOD.load_ref(str(tmp_path / "nope.json"))


# ── load_ref: ref- プレフィクス(cwd 相対候補を tmp_path で再現) ───────────────
def test_load_ref_prefix_resolves_references_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # references/ 配下を最優先候補として解決すること
    target = tmp_path / "plugins" / "harness-creator" / "skills" / "ref-x-rubric" / "references" / "rubric.json"
    _write(target, {"layer": "L1", "rules": [{"id": "a"}]})
    ref, resolved, data = MOD.load_ref("ref-x-rubric")
    assert ref == "ref-x-rubric"
    assert resolved == target.resolve()
    assert data["layer"] == "L1"


def test_load_ref_prefix_fallback_to_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # references/ が無く root 直下 rubric.json のみ存在 → フォールバック候補で解決
    target = tmp_path / "plugins" / "harness-creator" / "skills" / "ref-y-rubric" / "rubric.json"
    _write(target, {"rules": []})
    ref, resolved, data = MOD.load_ref("ref-y-rubric")
    assert resolved == target.resolve()
    assert data == {"rules": []}


def test_load_ref_prefix_missing_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="rubric not found"):
        MOD.load_ref("ref-absent-rubric")


# ── validate_schema ──────────────────────────────────────────────────────────
def test_validate_schema_ok():
    MOD.validate_schema("r", {"layer": "L0", "rules": [{"id": "a"}, {"id": "b"}]})


def test_validate_schema_layer_none_allowed():
    # layer 未指定は許容
    MOD.validate_schema("r", {"rules": [{"id": "a"}]})


def test_validate_schema_missing_rules():
    with pytest.raises(ValueError, match="rules must be list"):
        MOD.validate_schema("r", {"layer": "L0"})


def test_validate_schema_rules_not_list():
    with pytest.raises(ValueError, match="rules must be list"):
        MOD.validate_schema("r", {"rules": {"id": "a"}})


def test_validate_schema_bad_layer():
    with pytest.raises(ValueError, match="layer must be"):
        MOD.validate_schema("r", {"layer": "L9", "rules": []})


def test_validate_schema_rule_not_object():
    with pytest.raises(ValueError, match=r"rules\[0\] must be object"):
        MOD.validate_schema("r", {"rules": ["not-a-dict"]})


def test_validate_schema_rule_missing_id():
    with pytest.raises(ValueError, match=r"rules\[0\]\.id is required"):
        MOD.validate_schema("r", {"rules": [{"desc": "x"}]})


def test_validate_schema_duplicate_id():
    with pytest.raises(ValueError, match="duplicate rule id: a"):
        MOD.validate_schema("r", {"rules": [{"id": "a"}, {"id": "a"}]})


# ── detect_cycles ────────────────────────────────────────────────────────────
def _loaded(*items):
    return [(ref, Path(ref), data) for ref, data in items]


def test_detect_cycles_acyclic():
    loaded = _loaded(
        ("a", {"extends": ["b"], "rules": []}),
        ("b", {"extends": [], "rules": []}),
    )
    MOD.detect_cycles(loaded)  # no raise


def test_detect_cycles_self_loop():
    loaded = _loaded(("a", {"extends": ["a"], "rules": []}))
    with pytest.raises(ValueError, match="cyclic rubric extends"):
        MOD.detect_cycles(loaded)


def test_detect_cycles_mutual():
    loaded = _loaded(
        ("a", {"extends": ["b"], "rules": []}),
        ("b", {"extends": ["a"], "rules": []}),
    )
    with pytest.raises(ValueError, match="cyclic rubric extends"):
        MOD.detect_cycles(loaded)


def test_detect_cycles_ignores_external_extends():
    # 未ロードの ref への extends は graph から除外され循環扱いされない
    loaded = _loaded(("a", {"extends": ["external"], "rules": []}))
    MOD.detect_cycles(loaded)


# ── deep_merge ───────────────────────────────────────────────────────────────
def test_deep_merge_recurse_and_add_keys():
    w: list[str] = []
    out = MOD.deep_merge(
        {"x": {"a": 1}, "keep": 0}, {"x": {"b": 2}, "new": 9},
        "most-specific-wins", w, "root",
    )
    assert out == {"x": {"a": 1, "b": 2}, "keep": 0, "new": 9}
    assert w == []


def test_deep_merge_equal_scalars_no_warning():
    w: list[str] = []
    assert MOD.deep_merge(5, 5, "error", w, "root") == 5
    assert w == []


def test_deep_merge_conflict_error_raises():
    with pytest.raises(ValueError, match="conflict at root.x"):
        MOD.deep_merge({"x": 1}, {"x": 2}, "error", [], "root")


def test_deep_merge_conflict_warn_and_merge():
    w: list[str] = []
    out = MOD.deep_merge({"x": 1}, {"x": 2}, "warn-and-merge", w, "root")
    assert out == {"x": 2}
    assert any("conflict at root.x" in m for m in w)


def test_deep_merge_conflict_most_specific_silent():
    w: list[str] = []
    out = MOD.deep_merge(1, 2, "most-specific-wins", w, "root")
    assert out == 2
    assert w == []


# ── merge_rules ──────────────────────────────────────────────────────────────
def test_merge_rules_override_replaces():
    base = [{"id": "a", "v": 1}]
    overlay = [{"id": "b", "v": 2}]
    out = MOD.merge_rules(base, overlay, "override", "most-specific-wins", [], "ov")
    assert out == [{"id": "b", "v": 2}]


def test_merge_rules_adds_new_id():
    out = MOD.merge_rules([{"id": "a"}], [{"id": "b"}], "deep-merge", "most-specific-wins", [], "ov")
    ids = {r["id"] for r in out}
    assert ids == {"a", "b"}


def test_merge_rules_strict_conflict_raises():
    with pytest.raises(ValueError, match="rule conflict: a from ov"):
        MOD.merge_rules([{"id": "a", "v": 1}], [{"id": "a", "v": 2}], "strict", "most-specific-wins", [], "ov")


def test_merge_rules_policy_error_raises():
    with pytest.raises(ValueError, match="rule conflict: a from ov"):
        MOD.merge_rules([{"id": "a", "v": 1}], [{"id": "a", "v": 2}], "deep-merge", "error", [], "ov")


def test_merge_rules_warn_and_merge():
    w: list[str] = []
    out = MOD.merge_rules([{"id": "a", "v": 1}], [{"id": "a", "v": 2}], "deep-merge", "warn-and-merge", w, "ov")
    merged = next(r for r in out if r["id"] == "a")
    assert merged["v"] == 2
    assert any("rule conflict: a from ov" in m for m in w)


def test_merge_rules_silent_merge_most_specific():
    w: list[str] = []
    out = MOD.merge_rules(
        [{"id": "a", "v": 1, "keep": "x"}], [{"id": "a", "v": 2}],
        "deep-merge", "most-specific-wins", w, "ov",
    )
    merged = next(r for r in out if r["id"] == "a")
    assert merged["v"] == 2
    assert merged["keep"] == "x"
    assert w == []


# ── compose: バリデーション ─────────────────────────────────────────────────
def test_compose_invalid_strategy(tmp_path):
    p = _write(tmp_path / "r.json", {"rules": []})
    with pytest.raises(ValueError, match="invalid merge_strategy"):
        MOD.compose([str(p)], "bogus", "most-specific-wins")


def test_compose_invalid_policy(tmp_path):
    p = _write(tmp_path / "r.json", {"rules": []})
    with pytest.raises(ValueError, match="invalid conflict_policy"):
        MOD.compose([str(p)], "deep-merge", "bogus")


# ── compose: 正常合成 ────────────────────────────────────────────────────────
def test_compose_single_deep_merge(tmp_path):
    p = _write(tmp_path / "r.json", {"layer": "L0", "title": "base", "rules": [{"id": "a", "v": 1}]})
    out = MOD.compose([str(p)], "deep-merge", "most-specific-wins")
    assert out["title"] == "base"
    assert out["rules"] == [{"id": "a", "v": 1}]
    assert out["_composition_hash"].startswith("sha256:")
    assert out["_composition_refs"] == [str(p)]
    assert "_composition_warnings" not in out


def test_compose_multi_deep_merge_warns_on_rule_conflict(tmp_path):
    p1 = _write(tmp_path / "a.json", {"layer": "L0", "rules": [{"id": "x", "v": 1}]})
    p2 = _write(tmp_path / "b.json", {"layer": "L1", "rules": [{"id": "x", "v": 2}]})
    out = MOD.compose([str(p1), str(p2)], "deep-merge", "warn-and-merge")
    rule = next(r for r in out["rules"] if r["id"] == "x")
    assert rule["v"] == 2
    assert any("rule conflict" in w for w in out["_composition_warnings"])


def test_compose_layered_keeps_all_layers_and_source_meta(tmp_path):
    p1 = _write(tmp_path / "a.json", {"layer": "L0", "rules": [{"id": "x"}]})
    p2 = _write(tmp_path / "b.json", {"layer": "L2", "rules": [{"id": "y"}]})
    out = MOD.compose([str(p1), str(p2)], "layered", "most-specific-wins")
    assert out["rubric_id"] == "layered"
    assert len(out["layers"]) == 2
    sources = {r["id"]: r["source_layer"] for r in out["rules"]}
    assert sources == {"x": "L0", "y": "L2"}


def test_compose_strict_metadata_conflict_raises(tmp_path):
    p1 = _write(tmp_path / "a.json", {"layer": "L0", "title": "one", "rules": []})
    p2 = _write(tmp_path / "b.json", {"layer": "L0", "title": "two", "rules": []})
    with pytest.raises(ValueError, match="metadata conflict"):
        MOD.compose([str(p1), str(p2)], "strict", "most-specific-wins")


def test_compose_layer_order_sort(tmp_path):
    # L2 を先に渡しても layer 昇順 (L0 → L2) に並ぶ
    p2 = _write(tmp_path / "high.json", {"layer": "L2", "rules": [{"id": "hi"}]})
    p0 = _write(tmp_path / "low.json", {"layer": "L0", "rules": [{"id": "lo"}]})
    out = MOD.compose([str(p2), str(p0)], "layered", "most-specific-wins")
    assert [layer["rubric"]["layer"] for layer in out["layers"]] == ["L0", "L2"]


def test_compose_hash_deterministic(tmp_path):
    p = _write(tmp_path / "r.json", {"layer": "L0", "rules": [{"id": "a"}]})
    h1 = MOD.compose([str(p)], "deep-merge", "most-specific-wins")["_composition_hash"]
    h2 = MOD.compose([str(p)], "deep-merge", "most-specific-wins")["_composition_hash"]
    assert h1 == h2
    # 内容変更で hash が変わる(決定論かつ入力依存)
    _write(tmp_path / "r.json", {"layer": "L0", "rules": [{"id": "b"}]})
    h3 = MOD.compose([str(p)], "deep-merge", "most-specific-wins")["_composition_hash"]
    assert h3 != h1


# ── main: subprocess CLI ─────────────────────────────────────────────────────
def _run(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
    )


def test_main_success_exit0(tmp_path):
    p = _write(tmp_path / "r.json", {"layer": "L0", "rules": [{"id": "a"}]})
    res = _run(["--rubric-refs", str(p)])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["_composition_refs"] == [str(p)]
    assert data["rules"] == [{"id": "a"}]


def test_main_success_with_strategy_and_policy(tmp_path):
    p1 = _write(tmp_path / "a.json", {"layer": "L0", "rules": [{"id": "x"}]})
    p2 = _write(tmp_path / "b.json", {"layer": "L1", "rules": [{"id": "y"}]})
    res = _run([
        "--rubric-refs", str(p1), str(p2),
        "--merge-strategy", "layered",
        "--conflict-policy", "warn-and-merge",
    ])
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["rubric_id"] == "layered"


def test_main_load_failure_exit1(tmp_path):
    res = _run(["--rubric-refs", str(tmp_path / "missing.json")])
    assert res.returncode == 1
    assert "compose-rubrics:" in res.stderr
    assert "rubric not found" in res.stderr


def test_main_invalid_json_exit1(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    res = _run(["--rubric-refs", str(bad)])
    assert res.returncode == 1
    assert "compose-rubrics:" in res.stderr


def test_main_validation_error_exit1(tmp_path):
    p = _write(tmp_path / "r.json", {"layer": "L0"})  # rules 欠落
    res = _run(["--rubric-refs", str(p)])
    assert res.returncode == 1
    assert "rules must be list" in res.stderr


def test_main_missing_required_arg_exit2():
    res = _run([])
    assert res.returncode == 2  # argparse: required --rubric-refs 欠落
    assert "rubric-refs" in res.stderr


def test_main_invalid_choice_exit2(tmp_path):
    p = _write(tmp_path / "r.json", {"rules": []})
    res = _run(["--rubric-refs", str(p), "--merge-strategy", "nope"])
    assert res.returncode == 2  # argparse: choices 違反
    assert "invalid choice" in res.stderr


# ── 直接 main() 呼び出し(in-process カバレッジ補完) ─────────────────────────
def test_main_inprocess_success(tmp_path, monkeypatch, capsys):
    p = _write(tmp_path / "r.json", {"layer": "L0", "rules": [{"id": "a"}]})
    monkeypatch.setattr(sys, "argv", ["compose-rubrics.py", "--rubric-refs", str(p)])
    rc = MOD.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert json.loads(out)["rules"] == [{"id": "a"}]


def test_main_inprocess_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["compose-rubrics.py", "--rubric-refs", str(tmp_path / "x.json")])
    rc = MOD.main()
    assert rc == 1
    assert "compose-rubrics:" in capsys.readouterr().err


# ── hash がスクリプトの canonical_json と一致(契約確認) ──────────────────────
def test_compose_hash_matches_canonical(tmp_path):
    p = _write(tmp_path / "r.json", {"layer": "L0", "rules": [{"id": "a"}]})
    out = MOD.compose([str(p)], "deep-merge", "most-specific-wins")
    expected_input = [{"ref": str(p), "path": str(p.resolve()), "rubric": {"layer": "L0", "rules": [{"id": "a"}]}}]
    expected = "sha256:" + hashlib.sha256(MOD.canonical_json(expected_input).encode("utf-8")).hexdigest()
    assert out["_composition_hash"] == expected
