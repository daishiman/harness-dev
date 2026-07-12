"""validate_intake_schema.py を genuine に網羅する (network/keychain/secret なし)。

このスクリプトは intake.json を Draft 2020-12 スキーマ + x-cross-field-rules で検証する
pre-publish hook である。SCHEMA_PATH はモジュール load 時に CLAUDE_PLUGIN_ROOT (なければ
parents[1]) 起点で算出される定数なので、テストでは:

  - 純関数 (_resolve_dotted / _check_cross_field_rules / _read_target_path) を実ファイル
    から importlib でロードして直接検証する。
  - main の全 exit code 経路は monkeypatch.setattr(MOD, "SCHEMA_PATH", <tmp schema>) で
    本番スキーマの 12 セクション複雑性に依存せず *最小カスタムスキーマ* を tmp_path に置いて
    駆動する。これにより validator 配線・cross-field 強制・truncation・各エラー経路を
    決定的に検証できる。
  - 1 本だけ本番 intake.schema.json を実ロードして「実スキーマでも check_schema が通り
    cross-field rule が SSOT に存在する」統合不変を assert する (実通信は皆無)。
  - stdin モードは sys.stdin を StringIO で差し替える (実 IO/ネットワークなし)。

スクリプトの兄弟 import (_jsonschema_compat) を解決するため script ディレクトリを sys.path に
前置してから exec_module する。tests/scripts(2,3) と衝突しない _r4 名で in-process ロードする。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "skill-intake" / "scripts" / "validate_intake_schema.py"
REAL_SCHEMA = ROOT / "plugins" / "skill-intake" / "references" / "intake.schema.json"

# 兄弟 import (_jsonschema_compat) を解決できるよう script dir を sys.path に前置。
_SCRIPT_DIR = str(SCRIPT.parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

_SPEC = importlib.util.spec_from_file_location("validate_intake_schema_r4", SCRIPT)
VIS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VIS)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _write(p: Path, obj) -> Path:
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def _minimal_schema(extra: dict | None = None) -> dict:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["a"],
        "properties": {"a": {"type": "string"}},
    }
    if extra:
        schema.update(extra)
    return schema


def _run_main(monkeypatch, schema: dict, instance, *, capsys, use_stdin=None):
    """SCHEMA_PATH を tmp schema に差し替え、main を実行して (rc, err) を返す。"""
    tmp = Path(monkeypatch._tmp)
    sp = _write(tmp / "schema.json", schema)
    monkeypatch.setattr(VIS, "SCHEMA_PATH", sp)
    if use_stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(use_stdin))
        argv = ["prog"]
    else:
        inst = _write(tmp / "instance.json", instance)
        argv = ["prog", str(inst)]
    rc = VIS.main(argv)
    captured = capsys.readouterr()
    return rc, captured.err


@pytest.fixture
def mp_with_tmp(monkeypatch, tmp_path):
    monkeypatch._tmp = tmp_path
    return monkeypatch


# --------------------------------------------------------------------------
# 純関数: _resolve_dotted
# --------------------------------------------------------------------------

def test_resolve_dotted_nested_hit():
    assert VIS._resolve_dotted({"x": {"y": {"z": 7}}}, "x.y.z") == 7


def test_resolve_dotted_single_key():
    assert VIS._resolve_dotted({"k": "v"}, "k") == "v"


def test_resolve_dotted_missing_key_returns_none():
    assert VIS._resolve_dotted({"x": {}}, "x.y") is None


def test_resolve_dotted_traverses_non_dict_returns_none():
    # 途中の cur が dict でない -> None
    assert VIS._resolve_dotted({"x": 1}, "x.y") is None


def test_resolve_dotted_top_non_dict_returns_none():
    assert VIS._resolve_dotted([1, 2], "x") is None


# --------------------------------------------------------------------------
# 純関数: _check_cross_field_rules
# --------------------------------------------------------------------------

def _xrule(left="a", right="b", op="equals", rid="r1"):
    return {"x-cross-field-rules": [{"id": rid, "left": left, "operator": op, "right": right}]}


def test_cross_field_no_rules_returns_empty():
    assert VIS._check_cross_field_rules({}, {"a": 1}) == []


def test_cross_field_equal_values_no_error():
    assert VIS._check_cross_field_rules(_xrule(), {"a": "x", "b": "x"}) == []


def test_cross_field_unequal_values_reports_error():
    errs = VIS._check_cross_field_rules(_xrule(rid="myrule"), {"a": "x", "b": "y"})
    assert len(errs) == 1
    assert "[myrule]" in errs[0]
    assert "a='x'" in errs[0] and "b='y'" in errs[0]


def test_cross_field_both_none_is_not_error():
    # 両方欠落は cross-field エラーでなく schema required で別途検出される。
    assert VIS._check_cross_field_rules(_xrule(), {}) == []


def test_cross_field_one_none_reports_error():
    errs = VIS._check_cross_field_rules(_xrule(), {"a": "x"})
    assert len(errs) == 1
    assert "b=None" in errs[0]


def test_cross_field_non_equals_operator_ignored():
    # operator が equals 以外なら何もしない。
    assert VIS._check_cross_field_rules(_xrule(op="lt"), {"a": 1, "b": 2}) == []


def test_cross_field_multiple_rules_aggregate():
    schema = {
        "x-cross-field-rules": [
            {"id": "r1", "left": "a", "operator": "equals", "right": "b"},
            {"id": "r2", "left": "c", "operator": "equals", "right": "d"},
        ]
    }
    errs = VIS._check_cross_field_rules(schema, {"a": 1, "b": 2, "c": 3, "d": 3})
    assert len(errs) == 1 and "[r1]" in errs[0]


# --------------------------------------------------------------------------
# 純関数: _read_target_path
# --------------------------------------------------------------------------

def test_read_target_path_from_argv():
    p = VIS._read_target_path(["prog", "some/relative/path.json"])
    assert p.is_absolute() and p.name == "path.json"


def test_read_target_path_stdin_intake_json(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"intake_json": "/a/b.json"})))
    assert VIS._read_target_path(["prog"]) == Path("/a/b.json").resolve()


def test_read_target_path_stdin_tool_input_file_path(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"file_path": "/c/d.json"}})))
    assert VIS._read_target_path(["prog"]) == Path("/c/d.json").resolve()


def test_read_target_path_stdin_path_key(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"path": "/e/f.json"})))
    assert VIS._read_target_path(["prog"]) == Path("/e/f.json").resolve()


def test_read_target_path_stdin_no_candidate_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"unrelated": 1})))
    with pytest.raises(SystemExit) as exc:
        VIS._read_target_path(["prog"])
    assert exc.value.code == 2
    assert "target path not provided" in capsys.readouterr().err


# --------------------------------------------------------------------------
# main: exit code 経路
# --------------------------------------------------------------------------

def test_main_schema_missing_returns_3(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(VIS, "SCHEMA_PATH", tmp_path / "does-not-exist.json")
    rc = VIS.main(["prog", str(tmp_path / "irrelevant.json")])
    assert rc == 3
    assert "schema not found" in capsys.readouterr().err


def test_main_invalid_stdin_payload_returns_2(monkeypatch, tmp_path, capsys):
    sp = _write(tmp_path / "schema.json", _minimal_schema())
    monkeypatch.setattr(VIS, "SCHEMA_PATH", sp)
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    rc = VIS.main(["prog"])
    assert rc == 2
    assert "invalid stdin payload" in capsys.readouterr().err


def test_main_target_not_found_returns_2(monkeypatch, tmp_path, capsys):
    sp = _write(tmp_path / "schema.json", _minimal_schema())
    monkeypatch.setattr(VIS, "SCHEMA_PATH", sp)
    rc = VIS.main(["prog", str(tmp_path / "ghost.json")])
    assert rc == 2
    assert "intake.json not found" in capsys.readouterr().err


def test_main_valid_instance_returns_0(mp_with_tmp, capsys):
    rc, err = _run_main(mp_with_tmp, _minimal_schema(), {"a": "ok"}, capsys=capsys)
    assert rc == 0
    assert "PASS" in err and "cross-field rules" in err


def test_main_schema_violation_returns_1(mp_with_tmp, capsys):
    rc, err = _run_main(mp_with_tmp, _minimal_schema(), {"a": 123}, capsys=capsys)
    assert rc == 1
    assert "schema violations" in err
    assert "[a]" in err  # location rendered


def test_main_missing_required_property_returns_1(mp_with_tmp, capsys):
    rc, err = _run_main(mp_with_tmp, _minimal_schema(), {}, capsys=capsys)
    assert rc == 1
    assert "schema violations" in err
    assert "required property" in err


def test_main_root_level_type_error_renders_root_location(mp_with_tmp, capsys):
    # instance がオブジェクトでない -> absolute_path が空 -> "<root>" location 経路を踏む。
    rc, err = _run_main(mp_with_tmp, _minimal_schema(), "i-am-a-string", capsys=capsys)
    assert rc == 1
    assert "schema violations" in err
    assert "<root>" in err


def test_main_cross_field_only_violation_returns_1(mp_with_tmp, capsys):
    schema = _minimal_schema(
        {
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "x-cross-field-rules": [
                {"id": "consistency", "left": "a", "operator": "equals", "right": "b"}
            ],
        }
    )
    rc, err = _run_main(mp_with_tmp, schema, {"a": "x", "b": "y"}, capsys=capsys)
    assert rc == 1
    assert "cross-field violations" in err
    assert "[consistency]" in err


def test_main_schema_and_cross_field_both_violate_prefers_schema_report(mp_with_tmp, capsys):
    # schema error が存在する場合は cross-field 単独ブランチに入らず schema violations を報告。
    schema = _minimal_schema(
        {
            "required": ["a", "b"],
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "x-cross-field-rules": [
                {"id": "x", "left": "a", "operator": "equals", "right": "b"}
            ],
        }
    )
    rc, err = _run_main(mp_with_tmp, schema, {"a": "x"}, capsys=capsys)
    assert rc == 1
    assert "schema violations" in err
    assert "cross-field violations" not in err


def test_main_truncates_after_20_errors(mp_with_tmp, capsys):
    # 25 個の type 不整合を起こし "... and N more" truncation 経路を踏む。
    props = {f"f{i}": {"type": "string"} for i in range(25)}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": props,
    }
    instance = {f"f{i}": i for i in range(25)}  # 全て int -> string 不整合
    rc, err = _run_main(mp_with_tmp, schema, instance, capsys=capsys)
    assert rc == 1
    assert "and 5 more" in err


def test_main_stdin_mode_valid_returns_0(mp_with_tmp, capsys, tmp_path):
    inst = _write(tmp_path / "inst.json", {"a": "yes"})
    payload = json.dumps({"intake_json": str(inst)})
    rc, err = _run_main(mp_with_tmp, _minimal_schema(), None, capsys=capsys, use_stdin=payload)
    assert rc == 0
    assert "PASS" in err


# --------------------------------------------------------------------------
# 統合: 本番スキーマでの不変 (実通信なし)
# --------------------------------------------------------------------------

def test_production_schema_loads_and_is_valid_draft():
    schema = json.loads(REAL_SCHEMA.read_text(encoding="utf-8"))
    import _jsonschema_compat as jsonschema  # noqa: WPS433

    validator_cls = jsonschema.validators.validator_for(schema)
    # check_schema が例外なく通ることがメタ不変。
    validator_cls.check_schema(schema)


def test_production_schema_declares_handoff_cross_field_rule():
    schema = json.loads(REAL_SCHEMA.read_text(encoding="utf-8"))
    rules = schema.get("x-cross-field-rules", [])
    ids = {r["id"] for r in rules}
    assert "handoff_mode_consistency" in ids
    # cross-field checker が本番ルールでも欠落同士は通すことを genuine に確認。
    assert VIS._check_cross_field_rules(schema, {}) == []


def test_production_schema_main_rejects_empty_instance(monkeypatch, tmp_path, capsys):
    # 本番スキーマ + 空 instance -> required 欠落で exit 1 (実通信/実書込なし)。
    monkeypatch.setattr(VIS, "SCHEMA_PATH", REAL_SCHEMA)
    inst = _write(tmp_path / "empty.json", {})
    rc = VIS.main(["prog", str(inst)])
    assert rc == 1
    assert "schema violations" in capsys.readouterr().err
