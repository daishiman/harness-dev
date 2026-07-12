"""validate-prompt.py の genuine 機能テスト (scripts4 / 独立計測用)。

対象: plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/validate-prompt.py

挙動の要約:
  --phase に応じて 2 系統の検証を行う。
    * hearing / sheet / trace … JSON の必須フィールド (schema.required) を検証。
      hearing のみ phase1 ネスト解決のフォールバックあり。
    * prompt … 生成プロンプト本文の 7 層マーカー / 未展開 {{...}} placeholder /
      TODO (TODO(human) 除く) 残存を検証。
  終了コード: 0=OK, 1=検証失敗, 2=引数欠落 or schema 不在。
  phase 未指定時は拡張子で判定 (.json→trace, それ以外→prompt)。

検証方針:
  - 純関数 (parse_args / load_json / default_schema_for / check_required /
    detect_phase / validate_json_by_schema / validate_prompt_text) を importlib で
    実ファイルからロードし、正常系・各異常系・エッジ (空文字/None/非dict/拡張子大小/
    sheet トップレベル required/hearing phase1 ネスト) を実入力で assert。
  - main は argv を monkeypatch して in-process 実行し、SystemExit code を捕捉して
    全分岐 (input 無し=2 / prompt OK=0 / prompt FAIL=1 / trace 明示 schema OK /
    schema 不在=2 / default schema 解決 / hearing default) を網羅。
  - CLI 経路 (__main__ guard) は subprocess(sys.executable) で exit code を実測。

network: false / keychain: なし / 実 repo 書換: なし (tmp_path + monkeypatch のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "prompt-creator"
    / "skills"
    / "run-prompt-creator-7layer"
    / "scripts"
    / "validate-prompt.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_prompt_uut_r4", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _wj(p: Path, data) -> Path:
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _seven_layer_prompt(*, output_section=True, trailing=""):
    """7 層マーカーを全て備えた合格プロンプト本文を組み立てる。"""
    parts = ["# 生成プロンプト", ""]
    for n in range(1, 8):
        parts.append(f"## Layer {n}: 見出し{n}")
        parts.append(f"Layer {n} の本文 (placeholder は展開済み)。")
        parts.append("")
    if output_section:
        parts.append("## 出力指示")
        # 出力指示セクション以降の {{...}} は実行時入力として許可される
        parts.append("ユーザー入力: {{user_query}}")
    if trailing:
        parts.append(trailing)
    return "\n".join(parts)


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True
    )


def _main_exit(monkeypatch, argv):
    monkeypatch.setattr(MOD.sys, "argv", argv)
    try:
        MOD.main()
        return 0
    except SystemExit as e:
        return e.code if e.code is not None else 0


# ── parse_args ───────────────────────────────────────────────────────────────
def test_parse_args_full(monkeypatch):
    monkeypatch.setattr(
        MOD.sys,
        "argv",
        ["validate-prompt.py", "--input", "i.json", "--phase", "sheet", "--schema", "s.json"],
    )
    a = MOD.parse_args()
    assert (a.input, a.phase, a.schema) == ("i.json", "sheet", "s.json")


def test_parse_args_defaults_none(monkeypatch):
    monkeypatch.setattr(MOD.sys, "argv", ["validate-prompt.py"])
    a = MOD.parse_args()
    assert a.input is None and a.phase is None and a.schema is None


def test_parse_args_rejects_unrecognized_failfast(monkeypatch):
    # A4-10: parse_known_args の黙殺を廃止。未知の --debug は argparse が exit 2 で failfast。
    monkeypatch.setattr(
        MOD.sys, "argv", ["validate-prompt.py", "--input", "p.md", "--debug", "1"]
    )
    with pytest.raises(SystemExit) as exc:
        MOD.parse_args()
    assert exc.value.code == 2


# ── load_json ────────────────────────────────────────────────────────────────
def test_load_json_unicode_roundtrip(tmp_path):
    p = _wj(tmp_path / "u.json", {"日本語": "値", "list": [1, 2, 3]})
    assert MOD.load_json(str(p)) == {"日本語": "値", "list": [1, 2, 3]}


def test_load_json_raises_on_invalid(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        MOD.load_json(str(p))


# ── default_schema_for ───────────────────────────────────────────────────────
def test_default_schema_for_each_phase_resolves_existing_file():
    for phase, marker in (
        ("hearing", "run-prompt-elicit"),
        ("sheet", "run-prompt-creator-7layer"),
        ("trace", "build-trace.schema.json"),
    ):
        path = MOD.default_schema_for(phase)
        assert path is not None, phase
        assert marker in path, (phase, path)
        assert Path(path).exists(), f"schema for {phase} must exist: {path}"


def test_default_schema_for_unknown_phase_is_none():
    assert MOD.default_schema_for("prompt") is None
    assert MOD.default_schema_for("totally-unknown") is None


# ── check_required ───────────────────────────────────────────────────────────
def test_check_required_no_missing():
    assert MOD.check_required({"a": 1, "b": "x", "c": [0]}, ["a", "b", "c"], "p") == []


def test_check_required_counts_none_empty_and_absent():
    obj = {"present": 1, "empty": "", "null": None}
    missing = MOD.check_required(obj, ["present", "empty", "null", "absent"], "ph")
    assert "ph.present" not in missing
    assert set(missing) == {"ph.empty", "ph.null", "ph.absent"}


def test_check_required_zero_and_false_are_not_missing():
    # 0 / False は None でも "" でもないので欠落扱いされない
    obj = {"zero": 0, "flag": False}
    assert MOD.check_required(obj, ["zero", "flag"], "ph") == []


def test_check_required_non_dict_marks_all():
    assert MOD.check_required("a string", ["x", "y"], "pfx") == ["pfx.x", "pfx.y"]
    assert MOD.check_required(None, ["z"], "pfx") == ["pfx.z"]


# ── detect_phase ─────────────────────────────────────────────────────────────
def test_detect_phase_explicit_overrides_extension():
    assert MOD.detect_phase("anything.json", "sheet") == "sheet"


def test_detect_phase_json_extension_uppercase():
    assert MOD.detect_phase("/p/TRACE.JSON", None) == "trace"


def test_detect_phase_non_json_is_prompt():
    assert MOD.detect_phase("/p/out.md", None) == "prompt"
    assert MOD.detect_phase("/p/no_extension", None) == "prompt"
    assert MOD.detect_phase("/p/file.txt", None) == "prompt"


# ── validate_json_by_schema: trace ───────────────────────────────────────────
def test_validate_trace_all_required_present(tmp_path, capsys):
    schema = _wj(tmp_path / "s.json", {"required": ["x", "y", "z"]})
    data = _wj(tmp_path / "d.json", {"x": 1, "y": "v", "z": [1]})
    MOD.validate_json_by_schema(str(data), "trace", str(schema))
    out = capsys.readouterr().out
    assert "OK phase=trace" in out and "required=3" in out


def test_validate_trace_missing_exits_1(tmp_path, capsys):
    schema = _wj(tmp_path / "s.json", {"required": ["x", "y", "z"]})
    data = _wj(tmp_path / "d.json", {"x": 1})
    with pytest.raises(SystemExit) as e:
        MOD.validate_json_by_schema(str(data), "trace", str(schema))
    assert e.value.code == 1
    err = capsys.readouterr().err
    assert "FAIL missing fields" in err
    assert "trace.y" in err and "trace.z" in err


def test_validate_trace_schema_without_required_key(tmp_path, capsys):
    # schema に required が無い → required=[] で常に OK
    schema = _wj(tmp_path / "s.json", {"title": "no-required"})
    data = _wj(tmp_path / "d.json", {"anything": 1})
    MOD.validate_json_by_schema(str(data), "trace", str(schema))
    assert "required=0" in capsys.readouterr().out


# ── validate_json_by_schema: hearing (phase1 nesting) ────────────────────────
def test_validate_hearing_phase1_nested_required(tmp_path, capsys):
    schema = _wj(
        tmp_path / "s.json",
        {"required": ["phase1"], "properties": {"phase1": {"required": ["session_id", "answers"]}}},
    )
    data = _wj(tmp_path / "d.json", {"phase1": {"session_id": "s1", "answers": ["a"]}})
    MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    out = capsys.readouterr().out
    assert "OK phase=hearing" in out and "required=2" in out


def test_validate_hearing_phase1_nested_missing_exits_1(tmp_path, capsys):
    schema = _wj(
        tmp_path / "s.json",
        {"properties": {"phase1": {"required": ["session_id", "answers"]}}},
    )
    data = _wj(tmp_path / "d.json", {"phase1": {"session_id": "s1"}})
    with pytest.raises(SystemExit) as e:
        MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    assert e.value.code == 1
    assert "hearing.answers" in capsys.readouterr().err


def test_validate_hearing_toplevel_when_no_phase1(tmp_path, capsys):
    # phase1 が無い → data 自体を target、sch.required を使用
    schema = _wj(tmp_path / "s.json", {"required": ["session_id", "timestamp", "answers"]})
    data = _wj(tmp_path / "d.json", {"session_id": "s", "timestamp": "t", "answers": []})
    MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    assert "OK phase=hearing" in capsys.readouterr().out


def test_validate_hearing_falls_back_to_default_required(tmp_path, capsys):
    # properties.phase1 も sch.required も無い → ["session_id","timestamp","answers"]
    schema = _wj(tmp_path / "s.json", {"title": "bare"})
    data = _wj(tmp_path / "d.json", {"session_id": "s", "timestamp": "t", "answers": [1]})
    MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    out = capsys.readouterr().out
    assert "OK phase=hearing" in out and "required=3" in out


# ── validate_json_by_schema: sheet (no phase1 special-casing) ────────────────
def test_validate_sheet_uses_toplevel_required(tmp_path, capsys):
    schema = _wj(tmp_path / "s.json", {"required": ["prompt_name", "purpose"]})
    data = _wj(tmp_path / "d.json", {"prompt_name": "p", "purpose": "目的"})
    MOD.validate_json_by_schema(str(data), "sheet", str(schema))
    out = capsys.readouterr().out
    assert "OK phase=sheet" in out and "required=2" in out


def test_validate_sheet_missing_exits_1(tmp_path, capsys):
    schema = _wj(tmp_path / "s.json", {"required": ["prompt_name", "purpose"]})
    data = _wj(tmp_path / "d.json", {"prompt_name": "p"})
    with pytest.raises(SystemExit) as e:
        MOD.validate_json_by_schema(str(data), "sheet", str(schema))
    assert e.value.code == 1
    assert "sheet.purpose" in capsys.readouterr().err


# ── validate_prompt_text ─────────────────────────────────────────────────────
def test_validate_prompt_text_full_seven_layers_ok(tmp_path, capsys):
    p = tmp_path / "p.md"
    p.write_text(_seven_layer_prompt(), encoding="utf-8")
    MOD.validate_prompt_text(str(p))
    assert "OK phase=prompt layers=7" in capsys.readouterr().out


def test_validate_prompt_text_marker_fullwidth_colon_ok(tmp_path, capsys):
    # Layer マーカーは全角コロン「：」も許容される (正規表現 [:：])
    lines = ["# p", ""]
    for n in range(1, 8):
        lines.append(f"## Layer {n}：本文")
        lines.append("展開済み本文")
    p = tmp_path / "p.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    MOD.validate_prompt_text(str(p))
    assert "OK phase=prompt" in capsys.readouterr().out


def test_validate_prompt_text_missing_multiple_layers(tmp_path, capsys):
    p = tmp_path / "p.md"
    txt = _seven_layer_prompt().replace("## Layer 3: 見出し3", "## 別見出し3")
    txt = txt.replace("## Layer 6: 見出し6", "## 別見出し6")
    p.write_text(txt, encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        MOD.validate_prompt_text(str(p))
    assert e.value.code == 1
    err = capsys.readouterr().err
    assert "Layer 3: marker missing" in err
    assert "Layer 6: marker missing" in err


def test_validate_prompt_text_unexpanded_placeholder_in_body(tmp_path, capsys):
    p = tmp_path / "p.md"
    txt = _seven_layer_prompt().replace(
        "Layer 2 の本文 (placeholder は展開済み)。", "未展開: {{still_a_var}}"
    )
    p.write_text(txt, encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        MOD.validate_prompt_text(str(p))
    assert e.value.code == 1
    assert "unexpanded placeholder remains" in capsys.readouterr().err


def test_validate_prompt_text_placeholder_after_output_section_is_allowed(tmp_path, capsys):
    # 出力指示セクション以降の {{user_query}} は許可 (本文には残っていない)
    p = tmp_path / "p.md"
    p.write_text(_seven_layer_prompt(output_section=True), encoding="utf-8")
    MOD.validate_prompt_text(str(p))
    assert "OK phase=prompt" in capsys.readouterr().out


def test_validate_prompt_text_todo_detected(tmp_path, capsys):
    p = tmp_path / "p.md"
    p.write_text(_seven_layer_prompt(trailing="todo: 後で対応"), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        MOD.validate_prompt_text(str(p))
    assert e.value.code == 1
    assert "TODO remains without TODO(human)" in capsys.readouterr().err


def test_validate_prompt_text_todo_human_allowed(tmp_path, capsys):
    p = tmp_path / "p.md"
    p.write_text(_seven_layer_prompt(trailing="TODO(human): 人間判断"), encoding="utf-8")
    MOD.validate_prompt_text(str(p))
    assert "OK phase=prompt" in capsys.readouterr().out


def test_validate_prompt_text_reports_all_problems_together(tmp_path, capsys):
    # Layer 欠落 + 未展開 placeholder + TODO を同時に出す
    p = tmp_path / "p.md"
    txt = "# only-some-layers\n## Layer 1: a\n本文 {{x}}\nTODO: fix\n"
    p.write_text(txt, encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        MOD.validate_prompt_text(str(p))
    assert e.value.code == 1
    err = capsys.readouterr().err
    assert "Layer 7: marker missing" in err
    assert "unexpanded placeholder remains" in err
    assert "TODO remains without TODO(human)" in err


# ── main: in-process via argv monkeypatch ────────────────────────────────────
def test_main_no_input_usage_exit_2(monkeypatch, capsys):
    assert _main_exit(monkeypatch, ["validate-prompt.py"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_main_prompt_ok(monkeypatch, tmp_path, capsys):
    p = tmp_path / "p.md"
    p.write_text(_seven_layer_prompt(), encoding="utf-8")
    assert _main_exit(monkeypatch, ["validate-prompt.py", "--input", str(p)]) == 0
    assert "OK phase=prompt" in capsys.readouterr().out


def test_main_prompt_fail(monkeypatch, tmp_path, capsys):
    p = tmp_path / "p.md"
    p.write_text("empty body, no layers", encoding="utf-8")
    assert _main_exit(monkeypatch, ["validate-prompt.py", "--input", str(p)]) == 1
    assert "FAIL prompt validation" in capsys.readouterr().err


def test_main_trace_explicit_schema_ok(monkeypatch, tmp_path, capsys):
    schema = _wj(tmp_path / "s.json", {"required": ["a"]})
    data = _wj(tmp_path / "d.json", {"a": 1})
    code = _main_exit(
        monkeypatch,
        ["validate-prompt.py", "--input", str(data), "--phase", "trace", "--schema", str(schema)],
    )
    assert code == 0
    assert "OK phase=trace" in capsys.readouterr().out


def test_main_schema_not_found_exit_2(monkeypatch, tmp_path, capsys):
    data = _wj(tmp_path / "d.json", {"a": 1})
    code = _main_exit(
        monkeypatch,
        ["validate-prompt.py", "--input", str(data), "--phase", "trace", "--schema", str(tmp_path / "nope.json")],
    )
    assert code == 2
    assert "schema not found" in capsys.readouterr().err


def test_main_default_schema_resolved_for_trace(monkeypatch, tmp_path, capsys):
    # --schema 省略 + .json → trace, default build-trace schema を解決し全 required 充足
    data = _wj(
        tmp_path / "trace.json",
        {
            "prompt_name": "p",
            "responsibility_id": "R1",
            "timestamp": "2026-01-01T00:00:00Z",
            "layer_coverage": {},
            "review_passes": [],
        },
    )
    code = _main_exit(monkeypatch, ["validate-prompt.py", "--input", str(data)])
    assert code == 0
    assert "OK phase=trace" in capsys.readouterr().out


def test_main_default_schema_resolved_for_hearing(monkeypatch, tmp_path, capsys):
    data = _wj(
        tmp_path / "h.json",
        {
            "session_id": "s",
            "timestamp": "t",
            "answers": [],
            # 3b schema 拡張 (required 追加: goals/checklist/evaluation_priorities) に追従
            "goals": ["検証済み成果物が出力された状態になっている"],
            "checklist": ["schema 検証を通過している"],
            "evaluation_priorities": ["正確性・精度"],
        },
    )
    code = _main_exit(monkeypatch, ["validate-prompt.py", "--input", str(data), "--phase", "hearing"])
    assert code == 0
    assert "OK phase=hearing" in capsys.readouterr().out


# ── CLI subprocess (exit code 実測 / __main__ guard) ─────────────────────────
def test_cli_no_input_exit_2():
    res = _run_cli()
    assert res.returncode == 2
    assert "usage:" in res.stderr


def test_cli_prompt_ok(tmp_path):
    p = tmp_path / "p.md"
    p.write_text(_seven_layer_prompt(), encoding="utf-8")
    res = _run_cli("--input", str(p))
    assert res.returncode == 0, res.stderr
    assert "OK phase=prompt" in res.stdout


def test_cli_prompt_fail(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("no layers", encoding="utf-8")
    res = _run_cli("--input", str(p))
    assert res.returncode == 1
    assert "FAIL prompt validation" in res.stderr


def test_cli_trace_missing_exit_1(tmp_path):
    schema = _wj(tmp_path / "s.json", {"required": ["a", "b"]})
    data = _wj(tmp_path / "d.json", {"a": 1})
    res = _run_cli("--input", str(data), "--phase", "trace", "--schema", str(schema))
    assert res.returncode == 1
    assert "FAIL missing fields" in res.stderr
