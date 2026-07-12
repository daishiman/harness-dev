"""run-prompt-creator-7layer/scripts/validate-prompt.py の genuine 機能テスト。

hearing/sheet/trace JSON のスキーマ必須項目検証、または生成プロンプトの
7層マーカー・未展開placeholder・TODO残存検証を行うスクリプト。
純関数を実ファイルパスから importlib でロードして実入力で assert し、
main は subprocess(sys.executable) で argv 依存の分岐(phase 自動判定/schema 解決/
exit code 0=OK 1=検証失敗 2=引数・schema 不在)を確認する。

カバー分岐:
- parse_args: --input/--phase/--schema パース、未知引数の failfast (A4-10: parse_args, exit 2)
- load_json: 正常 JSON ロード
- default_schema_for: hearing/sheet/trace の各 schema パス, その他 None
- check_required: 全充足(空 missing) / None・空文字を missing 計上 / 非 dict 入力
- detect_phase: explicit 優先 / .json→trace / その他→prompt
- validate_json_by_schema: trace 正常(全 required 充足) / 不足で exit1 /
  hearing phase1 ネスト解決 / hearing トップレベル解決
- validate_prompt_text: 7層全マーカーあり OK / マーカー欠落 / 未展開 {{...}} /
  出力指示セクション後の {{...}} は許可 / TODO 残存 / TODO(human) は許可
- main: --input 無し usage exit2 / prompt 経路 / json 経路 / schema 不在 exit2 /
  明示 --schema 指定 / hearing phase 明示

network: false, keychain: なし, 実 repo 書換: なし (tmp_path / stdout/stderr のみ)。
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

SPEC = importlib.util.spec_from_file_location("validate_prompt_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── helpers ──────────────────────────────────────────────────────────────────
def _write_json(p: Path, data) -> Path:
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _valid_prompt_text() -> str:
    lines = ["# 生成プロンプト本文", ""]
    for n in range(1, 8):
        lines.append(f"## Layer {n}: セクション{n}")
        lines.append(f"Layer {n} の本文。プレースホルダーは展開済み。")
        lines.append("")
    lines.append("## 出力指示")
    # 出力指示セクション以降の {{...}} は実行時入力として許可される
    lines.append("入力: {{runtime_input}}")
    return "\n".join(lines)


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
    )


# ── parse_args ───────────────────────────────────────────────────────────────
def test_parse_args_all_flags(monkeypatch):
    monkeypatch.setattr(
        MOD.sys,
        "argv",
        ["validate-prompt.py", "--input", "x.json", "--phase", "trace", "--schema", "s.json"],
    )
    args = MOD.parse_args()
    assert args.input == "x.json"
    assert args.phase == "trace"
    assert args.schema == "s.json"


def test_parse_args_rejects_unknown_failfast(monkeypatch):
    # A4-10: parse_known_args の黙殺を廃止。未知引数 --extra は argparse が exit 2 で failfast。
    monkeypatch.setattr(
        MOD.sys, "argv", ["validate-prompt.py", "--input", "x.txt", "--extra", "v"]
    )
    with pytest.raises(SystemExit) as exc:
        MOD.parse_args()
    assert exc.value.code == 2


# ── load_json ────────────────────────────────────────────────────────────────
def test_load_json_roundtrip(tmp_path):
    p = _write_json(tmp_path / "d.json", {"k": "値", "n": 3})
    assert MOD.load_json(str(p)) == {"k": "値", "n": 3}


# ── default_schema_for ───────────────────────────────────────────────────────
def test_default_schema_for_hearing():
    path = MOD.default_schema_for("hearing")
    assert path is not None
    assert path.endswith(
        Path("run-prompt-elicit/schemas/hearing-result.schema.json").as_posix().replace("/", "/")
    ) or "run-prompt-elicit" in path
    assert Path(path).exists(), f"resolved hearing schema should exist: {path}"


def test_default_schema_for_sheet():
    path = MOD.default_schema_for("sheet")
    assert "run-prompt-creator-7layer" in path
    assert Path(path).exists()


def test_default_schema_for_trace():
    path = MOD.default_schema_for("trace")
    assert "build-trace.schema.json" in path
    assert Path(path).exists()


def test_default_schema_for_unknown_returns_none():
    assert MOD.default_schema_for("prompt") is None
    assert MOD.default_schema_for("nope") is None


# ── check_required ───────────────────────────────────────────────────────────
def test_check_required_all_present():
    obj = {"a": 1, "b": "x"}
    assert MOD.check_required(obj, ["a", "b"], "p") == []


def test_check_required_missing_and_empty():
    obj = {"a": 1, "b": "", "c": None}
    missing = MOD.check_required(obj, ["a", "b", "c", "d"], "phase")
    # b は空文字, c は None, d は欠落 → 全て missing
    assert "phase.b" in missing
    assert "phase.c" in missing
    assert "phase.d" in missing
    assert "phase.a" not in missing


def test_check_required_non_dict_input():
    # obj が dict でない → 全 required が None 扱いで missing
    missing = MOD.check_required(["not", "a", "dict"], ["x", "y"], "pfx")
    assert missing == ["pfx.x", "pfx.y"]


# ── detect_phase ─────────────────────────────────────────────────────────────
def test_detect_phase_explicit_wins():
    assert MOD.detect_phase("file.json", "hearing") == "hearing"


def test_detect_phase_json_to_trace():
    assert MOD.detect_phase("/some/path/trace.JSON", None) == "trace"


def test_detect_phase_other_to_prompt():
    assert MOD.detect_phase("/x/prompt.md", None) == "prompt"
    assert MOD.detect_phase("/x/noext", None) == "prompt"


# ── validate_json_by_schema (trace) ──────────────────────────────────────────
def test_validate_json_by_schema_trace_ok(tmp_path, capsys):
    schema = _write_json(tmp_path / "s.json", {"required": ["a", "b"]})
    data = _write_json(tmp_path / "d.json", {"a": 1, "b": 2})
    MOD.validate_json_by_schema(str(data), "trace", str(schema))
    out = capsys.readouterr().out
    assert "OK phase=trace" in out
    assert "required=2" in out


def test_validate_json_by_schema_trace_missing_exits_1(tmp_path, capsys):
    schema = _write_json(tmp_path / "s.json", {"required": ["a", "b", "c"]})
    data = _write_json(tmp_path / "d.json", {"a": 1})
    with pytest.raises(SystemExit) as exc:
        MOD.validate_json_by_schema(str(data), "trace", str(schema))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "FAIL missing fields" in err
    assert "trace.b" in err
    assert "trace.c" in err


# ── validate_json_by_schema (hearing) ────────────────────────────────────────
def test_validate_json_by_schema_hearing_phase1_nested(tmp_path, capsys):
    # schema に properties.phase1.required がある → phase1 を target に required を引く
    schema = _write_json(
        tmp_path / "s.json",
        {
            "required": ["phase1"],
            "properties": {"phase1": {"required": ["session_id", "answers"]}},
        },
    )
    data = _write_json(
        tmp_path / "d.json",
        {"phase1": {"session_id": "s1", "answers": ["a"]}},
    )
    MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    out = capsys.readouterr().out
    assert "OK phase=hearing" in out
    assert "required=2" in out


def test_validate_json_by_schema_hearing_toplevel(tmp_path, capsys):
    # phase1 が無い → target は data 自体、required は sch.required を使用
    schema = _write_json(
        tmp_path / "s.json", {"required": ["session_id", "timestamp", "answers"]}
    )
    data = _write_json(
        tmp_path / "d.json",
        {"session_id": "s", "timestamp": "2026-01-01T00:00:00Z", "answers": []},
    )
    # answers は [] (空 list) → "" でも None でもないので missing にならない
    MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    assert "OK phase=hearing" in capsys.readouterr().out


def test_validate_json_by_schema_hearing_missing_exits_1(tmp_path, capsys):
    schema = _write_json(
        tmp_path / "s.json", {"required": ["session_id", "timestamp", "answers"]}
    )
    data = _write_json(tmp_path / "d.json", {"session_id": "s"})
    with pytest.raises(SystemExit) as exc:
        MOD.validate_json_by_schema(str(data), "hearing", str(schema))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "hearing.timestamp" in err
    assert "hearing.answers" in err


# ── validate_prompt_text ─────────────────────────────────────────────────────
def test_validate_prompt_text_ok(tmp_path, capsys):
    p = tmp_path / "prompt.md"
    p.write_text(_valid_prompt_text(), encoding="utf-8")
    MOD.validate_prompt_text(str(p))
    out = capsys.readouterr().out
    assert "OK phase=prompt layers=7" in out


def test_validate_prompt_text_missing_layer_exits_1(tmp_path, capsys):
    p = tmp_path / "prompt.md"
    # Layer 7 を欠落させる
    text = _valid_prompt_text().replace("## Layer 7: セクション7", "## Section7")
    p.write_text(text, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        MOD.validate_prompt_text(str(p))
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "FAIL prompt validation" in err
    assert "Layer 7: marker missing" in err


def test_validate_prompt_text_unexpanded_placeholder_exits_1(tmp_path, capsys):
    p = tmp_path / "prompt.md"
    # Layer 本文 (出力指示より前) に {{...}} を残す
    text = _valid_prompt_text().replace(
        "Layer 1 の本文。プレースホルダーは展開済み。", "未展開: {{var_name}}"
    )
    p.write_text(text, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        MOD.validate_prompt_text(str(p))
    assert exc.value.code == 1
    assert "unexpanded placeholder remains" in capsys.readouterr().err


def test_validate_prompt_text_placeholder_after_output_section_allowed(tmp_path, capsys):
    # 出力指示セクション以降の {{...}} は許可される (本文には無い前提)
    p = tmp_path / "prompt.md"
    p.write_text(_valid_prompt_text(), encoding="utf-8")
    MOD.validate_prompt_text(str(p))
    # 本文に {{runtime_input}} は出力指示以降にしか無いので OK 判定
    assert "OK phase=prompt" in capsys.readouterr().out


def test_validate_prompt_text_todo_exits_1(tmp_path, capsys):
    p = tmp_path / "prompt.md"
    text = _valid_prompt_text() + "\nTODO: 後で書く\n"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        MOD.validate_prompt_text(str(p))
    assert exc.value.code == 1
    assert "TODO remains without TODO(human)" in capsys.readouterr().err


def test_validate_prompt_text_todo_human_allowed(tmp_path, capsys):
    p = tmp_path / "prompt.md"
    text = _valid_prompt_text() + "\nTODO(human): 人間が判断する\n"
    p.write_text(text, encoding="utf-8")
    # TODO(human) は negative lookahead で許可される
    MOD.validate_prompt_text(str(p))
    assert "OK phase=prompt" in capsys.readouterr().out


# ── main: in-process (argv monkeypatch + SystemExit) ─────────────────────────
def _call_main(monkeypatch, argv):
    monkeypatch.setattr(MOD.sys, "argv", argv)
    try:
        MOD.main()
        return 0
    except SystemExit as exc:
        return exc.code if exc.code is not None else 0


def test_main_no_input_usage_exit_2(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["validate-prompt.py"])
    assert code == 2
    assert "usage:" in capsys.readouterr().err


def test_main_prompt_path_ok(monkeypatch, tmp_path, capsys):
    p = tmp_path / "prompt.md"
    p.write_text(_valid_prompt_text(), encoding="utf-8")
    code = _call_main(monkeypatch, ["validate-prompt.py", "--input", str(p)])
    assert code == 0
    assert "OK phase=prompt" in capsys.readouterr().out


def test_main_prompt_path_fail(monkeypatch, tmp_path, capsys):
    p = tmp_path / "prompt.md"
    p.write_text("no layers here", encoding="utf-8")
    code = _call_main(monkeypatch, ["validate-prompt.py", "--input", str(p)])
    assert code == 1
    assert "FAIL prompt validation" in capsys.readouterr().err


def test_main_json_trace_explicit_schema_ok(monkeypatch, tmp_path, capsys):
    schema = _write_json(tmp_path / "s.json", {"required": ["a"]})
    data = _write_json(tmp_path / "d.json", {"a": 1})
    code = _call_main(
        monkeypatch,
        ["validate-prompt.py", "--input", str(data), "--phase", "trace", "--schema", str(schema)],
    )
    assert code == 0
    assert "OK phase=trace" in capsys.readouterr().out


def test_main_schema_not_found_exit_2(monkeypatch, tmp_path, capsys):
    data = _write_json(tmp_path / "d.json", {"a": 1})
    missing_schema = str(tmp_path / "nope.json")
    code = _call_main(
        monkeypatch,
        ["validate-prompt.py", "--input", str(data), "--phase", "trace", "--schema", missing_schema],
    )
    assert code == 2
    assert "schema not found" in capsys.readouterr().err


def test_main_json_default_schema_resolved(monkeypatch, tmp_path, capsys):
    # --schema 省略 → default_schema_for(trace) = build-trace.schema.json を解決
    data = _write_json(
        tmp_path / "trace.json",
        {
            "prompt_name": "p",
            "responsibility_id": "R1",
            "timestamp": "2026-01-01T00:00:00Z",
            "layer_coverage": {},
            "review_passes": [],
        },
    )
    code = _call_main(monkeypatch, ["validate-prompt.py", "--input", str(data)])
    # detect_phase(.json)→trace, default schema 解決, 全 required 充足で OK
    assert code == 0
    assert "OK phase=trace" in capsys.readouterr().out


def test_main_hearing_default_schema(monkeypatch, tmp_path, capsys):
    data = _write_json(
        tmp_path / "h.json",
        {
            "session_id": "s",
            "timestamp": "2026-01-01T00:00:00Z",
            "answers": [],
            # 3b schema 拡張 (required 追加: goals/checklist/evaluation_priorities) に追従
            "goals": ["検証済み成果物が出力された状態になっている"],
            "checklist": ["schema 検証を通過している"],
            "evaluation_priorities": ["正確性・精度"],
        },
    )
    code = _call_main(
        monkeypatch, ["validate-prompt.py", "--input", str(data), "--phase", "hearing"]
    )
    # run-prompt-elicit schema (required: session_id/timestamp/answers) で OK
    assert code == 0
    assert "OK phase=hearing" in capsys.readouterr().out


# ── main: subprocess (CLI exit code 実測, sitecustomize 連携) ─────────────────
def test_cli_no_input_exit_2():
    res = _run()
    assert res.returncode == 2
    assert "usage:" in res.stderr


def test_cli_prompt_ok(tmp_path):
    p = tmp_path / "prompt.md"
    p.write_text(_valid_prompt_text(), encoding="utf-8")
    res = _run("--input", str(p))
    assert res.returncode == 0, res.stderr
    assert "OK phase=prompt" in res.stdout


def test_cli_prompt_fail(tmp_path):
    p = tmp_path / "prompt.md"
    p.write_text("nothing", encoding="utf-8")
    res = _run("--input", str(p))
    assert res.returncode == 1
    assert "FAIL prompt validation" in res.stderr


def test_cli_trace_ok(tmp_path):
    schema = _write_json(tmp_path / "s.json", {"required": ["a"]})
    data = _write_json(tmp_path / "d.json", {"a": 1})
    res = _run("--input", str(data), "--phase", "trace", "--schema", str(schema))
    assert res.returncode == 0, res.stderr
    assert "OK phase=trace" in res.stdout


def test_cli_trace_missing_exit_1(tmp_path):
    schema = _write_json(tmp_path / "s.json", {"required": ["a", "b"]})
    data = _write_json(tmp_path / "d.json", {"a": 1})
    res = _run("--input", str(data), "--phase", "trace", "--schema", str(schema))
    assert res.returncode == 1
    assert "FAIL missing fields" in res.stderr


def test_cli_schema_not_found_exit_2(tmp_path):
    data = _write_json(tmp_path / "d.json", {"a": 1})
    res = _run("--input", str(data), "--phase", "trace", "--schema", str(tmp_path / "x.json"))
    assert res.returncode == 2
    assert "schema not found" in res.stderr
