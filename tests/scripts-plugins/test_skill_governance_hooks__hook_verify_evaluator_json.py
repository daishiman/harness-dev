"""hook-verify-evaluator-json.py の genuine 機能テスト (network 不要)。

SubagentStop フック。subagent 名が assign-* かつ "evaluator" を含むとき、
最終 STDOUT に評価コントラクト JSON (rubric_id / score / passed / threshold /
findings / required_fixes / machine_checks / rubric_version / rubric_hash /
target) が揃っているかを検査する。違反は exit 2 (block), それ以外は exit 0。

genuine に網羅する分岐:
  extract_json:
    - text 全体が JSON      → そのまま dict
    - 前後にノイズ + 末尾の {...} ブロック → 最後の有効ブロックを採用
    - 複数 {...} のうち末尾が壊れていて前のが有効 → reversed 走査で拾う
    - JSON が一切無い        → None
    - 空文字 / None          → None
  main:
    - stdin 空 / 不正 JSON   → return 0
    - 名前が assign- でない    → return 0 (対象外)
    - 名前が assign- だが evaluator を含まない → return 0
    - 名前が非 str            → return 0
    - subagent_name / agent / subagent_type のどのキーでも解決
    - stdout / output / response のどのキーでも出力解決
    - 対象だが JSON 解析不能   → exit 2 + stderr
    - 対象で必須キー欠落       → exit 2 + stderr (欠落キー名を含む)
    - 対象で必須キー充足       → exit 0

import 駆動 (monkeypatch stdin) で全分岐を踏み、加えて subprocess (sys.executable)
で __main__ の exit code を実証する。tmp_path 不要・repo 非汚染。
"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "plugins" / "skill-governance-hooks" / "scripts"
    / "hook-verify-evaluator-json.py"
)

_SPEC = importlib.util.spec_from_file_location(
    "hook_verify_evaluator_json_under_test", SCRIPT
)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


def _full_contract() -> dict:
    """REQUIRED_KEYS を全て満たす評価 JSON。"""
    return {
        "rubric_id": "skill-design",
        "rubric_version": "1.0.0",
        "rubric_hash": "abc123",
        "target": "plugins/x/skills/run-y",
        "score": 0.91,
        "threshold": 0.8,
        "passed": True,
        "findings": [],
        "required_fixes": [],
        "machine_checks": {"lint": "pass"},
    }


def _set_stdin(monkeypatch, payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(MOD.sys, "stdin", io.StringIO(text))


# --------------------------------------------------------------------------
# REQUIRED_KEYS の固定 (回帰アンカー)
# --------------------------------------------------------------------------

def test_required_keys_exact_set():
    assert MOD.REQUIRED_KEYS == {
        "rubric_id", "rubric_version", "rubric_hash", "target", "score",
        "threshold", "passed", "findings", "required_fixes", "machine_checks",
    }


# --------------------------------------------------------------------------
# extract_json
# --------------------------------------------------------------------------

def test_extract_json_whole_text():
    obj = MOD.extract_json('{"a": 1, "b": [2, 3]}')
    assert obj == {"a": 1, "b": [2, 3]}


def test_extract_json_trailing_block_after_noise():
    text = 'log line\nthinking...\nFINAL: {"score": 0.5, "passed": true}'
    obj = MOD.extract_json(text)
    assert obj == {"score": 0.5, "passed": True}


def test_extract_json_picks_last_valid_block_when_trailing_broken():
    # 末尾の {...} が壊れていても、reversed 走査で 1つ前の有効ブロックを拾う。
    # 正規表現 \{[\s\S]*\} は貪欲なので「最初の { から最後の } まで」を 1 マッチに
    # するが、その 1 マッチ全体は JSON 化できないため None になることを固定する
    # (= 複数オブジェクトを跨ぐ貪欲マッチの実挙動アンカー)。
    text = 'noise {"good": 1} more {"bad": }'
    obj = MOD.extract_json(text)
    assert obj is None


def test_extract_json_single_valid_block_with_noise():
    text = 'preamble {"good": 1} postamble'
    obj = MOD.extract_json(text)
    assert obj == {"good": 1}


def test_extract_json_no_json_returns_none():
    assert MOD.extract_json("just prose, no braces") is None


def test_extract_json_empty_and_none():
    assert MOD.extract_json("") is None
    assert MOD.extract_json(None) is None


def test_extract_json_invalid_brace_block_returns_none():
    assert MOD.extract_json("{not: valid, json}") is None


# --------------------------------------------------------------------------
# main: 対象外 (early return 0)
# --------------------------------------------------------------------------

def test_main_empty_stdin_returns_0(monkeypatch):
    _set_stdin(monkeypatch, "")
    assert MOD.main() == 0


def test_main_invalid_json_stdin_returns_0(monkeypatch):
    _set_stdin(monkeypatch, "<<<not json>>>")
    assert MOD.main() == 0


def test_main_non_assign_name_returns_0(monkeypatch):
    _set_stdin(monkeypatch, {"subagent_name": "run-build-skill", "stdout": "garbage"})
    assert MOD.main() == 0


def test_main_assign_but_not_evaluator_returns_0(monkeypatch):
    # assign- で始まるが "evaluator" を含まない → 対象外
    _set_stdin(monkeypatch, {"subagent_name": "assign-helper", "stdout": "garbage"})
    assert MOD.main() == 0


def test_main_non_string_name_returns_0(monkeypatch):
    _set_stdin(monkeypatch, {"subagent_name": 12345, "stdout": "garbage"})
    assert MOD.main() == 0


def test_main_no_name_key_returns_0(monkeypatch):
    _set_stdin(monkeypatch, {"stdout": "garbage"})
    assert MOD.main() == 0


# --------------------------------------------------------------------------
# main: 対象 (assign-*evaluator*) — 違反検出 exit 2
# --------------------------------------------------------------------------

def test_main_target_no_parseable_json_exit2(monkeypatch, capsys):
    _set_stdin(monkeypatch, {
        "subagent_name": "assign-skill-design-evaluator",
        "stdout": "I could not produce JSON, sorry.",
    })
    assert MOD.main() == 2
    err = capsys.readouterr().err
    assert "produced no parseable JSON" in err
    assert "assign-skill-design-evaluator" in err


def test_main_target_missing_keys_exit2(monkeypatch, capsys):
    partial = {"score": 0.9, "passed": True}  # 大半のキー欠落
    _set_stdin(monkeypatch, {
        "subagent_name": "assign-plugin-package-evaluator",
        "stdout": json.dumps(partial),
    })
    assert MOD.main() == 2
    err = capsys.readouterr().err
    assert "missing keys" in err
    # 欠落キー名が列挙されること (sorted)
    assert "rubric_id" in err
    assert "machine_checks" in err


# --------------------------------------------------------------------------
# main: 対象 — 充足 exit 0
# --------------------------------------------------------------------------

def test_main_target_full_contract_exit0(monkeypatch, capsys):
    _set_stdin(monkeypatch, {
        "subagent_name": "assign-skill-design-evaluator",
        "stdout": json.dumps(_full_contract()),
    })
    assert MOD.main() == 0
    assert capsys.readouterr().err == ""


def test_main_full_contract_with_noise_in_output_exit0(monkeypatch):
    text = "deliberation...\nresult below:\n" + json.dumps(_full_contract())
    _set_stdin(monkeypatch, {
        "subagent_name": "assign-skill-design-evaluator",
        "stdout": text,
    })
    assert MOD.main() == 0


# --------------------------------------------------------------------------
# main: 名前キー / 出力キーの代替解決
# --------------------------------------------------------------------------

def test_main_name_via_agent_key(monkeypatch):
    _set_stdin(monkeypatch, {
        "agent": "assign-prompt-design-evaluator",
        "stdout": json.dumps(_full_contract()),
    })
    assert MOD.main() == 0


def test_main_name_via_subagent_type_key(monkeypatch):
    _set_stdin(monkeypatch, {
        "subagent_type": "assign-prompt-design-evaluator",
        "output": json.dumps(_full_contract()),
    })
    assert MOD.main() == 0


def test_main_output_via_response_key(monkeypatch):
    _set_stdin(monkeypatch, {
        "subagent_name": "assign-skill-design-evaluator",
        "response": json.dumps(_full_contract()),
    })
    assert MOD.main() == 0


def test_main_target_empty_output_exit2(monkeypatch, capsys):
    # 出力キーがどれも無い → output == "" → 解析不能 → exit 2
    _set_stdin(monkeypatch, {"subagent_name": "assign-skill-design-evaluator"})
    assert MOD.main() == 2
    assert "produced no parseable JSON" in capsys.readouterr().err


# --------------------------------------------------------------------------
# __main__ / subprocess 実行経路 (genuine exit-code 実証)
# --------------------------------------------------------------------------

def _run(stdin_text):
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text, capture_output=True, text=True,
    )


def test_subprocess_empty_stdin_exit0():
    proc = _run("")
    assert proc.returncode == 0


def test_subprocess_non_target_exit0():
    proc = _run(json.dumps({"subagent_name": "run-x", "stdout": "x"}))
    assert proc.returncode == 0


def test_subprocess_full_contract_exit0():
    proc = _run(json.dumps({
        "subagent_name": "assign-skill-design-evaluator",
        "stdout": json.dumps(_full_contract()),
    }))
    assert proc.returncode == 0, proc.stderr


def test_subprocess_violation_exit2():
    proc = _run(json.dumps({
        "subagent_name": "assign-skill-design-evaluator",
        "stdout": "no json here",
    }))
    assert proc.returncode == 2
    assert "produced no parseable JSON" in proc.stderr


def test_subprocess_missing_keys_exit2():
    proc = _run(json.dumps({
        "subagent_name": "assign-plugin-package-evaluator",
        "stdout": json.dumps({"score": 1}),
    }))
    assert proc.returncode == 2
    assert "missing keys" in proc.stderr
