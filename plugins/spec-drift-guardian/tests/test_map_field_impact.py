#!/usr/bin/env python3
# /// script
# name: test-map-field-impact
# purpose: C09 の data-driven field impact 写像、入力検証、決定論出力を検証する。
# inputs: scripts/map-field-impact.py / references/field-impact-map.json / tmp_path parsed hunks
# outputs: pytest assertions and coverage evidence
# contexts: [E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///
"""C09 map-field-impact.py の決定論 unit test。

写像規則が data (field-impact-map.json) 由来で code に hardcode されていないこと
(--map 差し替えで出力が変わること) を含め、各 axis 判定・kind 判定・fallback・
exit code 契約 (0/1/2) を赤テストで固定する。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "map-field-impact.py"


def run(hunks, *, extra_args=None, map_path=None):
    """script を --stdin で実行し (returncode, candidates|None, stderr) を返す。"""
    argv = [sys.executable, str(_SCRIPT), "--stdin"]
    if map_path is not None:
        argv += ["--map", str(map_path)]
    if extra_args:
        argv += list(extra_args)
    payload = hunks if isinstance(hunks, str) else json.dumps(hunks)
    proc = subprocess.run(
        argv, input=payload, capture_output=True, text=True, check=False
    )
    parsed = None
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            parsed = None
    return proc.returncode, parsed, proc.stderr


def schema_hunk(added=None, removed=None, path="plugins/x/schemas/foo.schema.json"):
    return {"file_path": path, "added_lines": added or [], "removed_lines": removed or []}


# ---------------------------------------------------------------------------
# (a) schema ファイル変更 hunk → axis=required/type/enum/name の各判定
# ---------------------------------------------------------------------------


def test_schema_required_axis():
    rc, out, _ = run([schema_hunk(added=['  "required": ["email", "id"],'])])
    assert rc == 0
    assert len(out) == 1
    c = out[0]
    assert c["artifact_kind"] == "schema"
    assert c["axis"] == "required"
    assert c["required"] is True
    assert c["type"] is False and c["name"] is False
    assert c["after"] == '  "required": ["email", "id"],'
    assert c["before"] is None  # 追加のみ
    assert "foo.schema.json" in c["evidence"]


def test_schema_type_axis():
    rc, out, _ = run(
        [schema_hunk(added=['  "type": "integer"'], removed=['  "type": "string"'])]
    )
    assert rc == 0
    c = out[0]
    assert c["axis"] == "type"
    assert c["type"] is True
    assert c["before"] == '  "type": "string"'
    assert c["after"] == '  "type": "integer"'


def test_schema_enum_axis():
    rc, out, _ = run([schema_hunk(added=['  "enum": ["a", "b", "c"]'])])
    assert rc == 0
    assert out[0]["axis"] == "enum"
    assert out[0]["enum"] is True


def test_schema_name_axis():
    rc, out, _ = run([schema_hunk(added=['    "emailAddress": {'])])
    assert rc == 0
    assert out[0]["axis"] == "name"
    assert out[0]["name"] is True


def test_schema_semantics_fallback_when_no_specific_rule():
    # description は schema の semantics 規則に一致する。
    rc, out, _ = run([schema_hunk(added=['  "description": "ユーザーの氏名"'])])
    assert rc == 0
    assert out[0]["axis"] == "semantics"
    assert out[0]["semantics"] is True


# ---------------------------------------------------------------------------
# (b) rubric 変更
# ---------------------------------------------------------------------------


def test_rubric_required_axis():
    rc, out, _ = run(
        [{"file_path": "plugins/x/rubric.json", "added_lines": ['  "weight": 0.4,']}]
    )
    assert rc == 0
    c = out[0]
    assert c["artifact_kind"] == "rubric"
    assert c["axis"] == "required"


def test_rubric_enum_axis():
    rc, out, _ = run(
        [
            {
                "file_path": "plugins/x/rubrics/sub/eval.json",
                "added_lines": ['  "verdict": "PASS",'],
            }
        ]
    )
    assert rc == 0
    assert out[0]["artifact_kind"] == "rubric"
    assert out[0]["axis"] == "enum"


# ---------------------------------------------------------------------------
# (c) 分類外 → other / semantics フォールバック
# ---------------------------------------------------------------------------


def test_unclassified_falls_back_to_other_semantics():
    rc, out, _ = run(
        [{"file_path": "docs/notes.md", "added_lines": ["arbitrary prose change"]}]
    )
    assert rc == 0
    c = out[0]
    assert c["artifact_kind"] == "other"
    assert c["axis"] == "semantics"
    assert c["semantics"] is True
    assert c["after"] == "arbitrary prose change"


def test_template_placeholder_name_axis():
    rc, out, _ = run(
        [
            {
                "file_path": "plugins/x/templates/report.tmpl",
                "added_lines": ["Hello {{ user_name }}"],
            }
        ]
    )
    assert rc == 0
    assert out[0]["artifact_kind"] == "template"
    assert out[0]["axis"] == "name"


# ---------------------------------------------------------------------------
# (d) --map 差し替えで規則が data 由来 (hardcode でない) であることの確認
# ---------------------------------------------------------------------------


def test_rules_are_data_driven_via_custom_map(tmp_path):
    hunk = [{"file_path": "weird.thing", "added_lines": ["marker XYZ here"]}]

    # 既定 map: weird.thing はどの kind にも一致せず other/semantics。
    rc_default, out_default, _ = run(hunk)
    assert rc_default == 0
    assert out_default[0]["artifact_kind"] == "other"
    assert out_default[0]["axis"] == "semantics"

    # カスタム map: *.thing を custom kind とし XYZ を name 軸へ写像する。
    custom_map = {
        "artifact_kinds": {
            "custom": {
                "path_globs": ["*.thing"],
                "rules": [{"axis": "name", "match_any": ["XYZ"]}],
            },
            "other": {
                "path_globs": ["**"],
                "rules": [{"axis": "semantics", "match_any": [".*"]}],
            },
        }
    }
    map_file = tmp_path / "custom-map.json"
    map_file.write_text(json.dumps(custom_map), encoding="utf-8")

    rc_custom, out_custom, _ = run(hunk, map_path=map_file)
    assert rc_custom == 0
    assert out_custom[0]["artifact_kind"] == "custom"
    assert out_custom[0]["axis"] == "name"
    # 同一入力で出力が変わる => 規則は data 由来で code に hardcode されていない。
    assert out_default[0]["axis"] != out_custom[0]["axis"]


# ---------------------------------------------------------------------------
# lines (raw unified diff) 入力形式と before/after
# ---------------------------------------------------------------------------


def test_raw_lines_input_with_before_after():
    hunk = [
        {
            "file_path": "plugins/x/schemas/foo.schema.json",
            "lines": [
                " context",
                '-  "type": "string"',
                '+  "type": "integer"',
            ],
        }
    ]
    rc, out, _ = run(hunk)
    assert rc == 0
    c = out[0]
    assert c["axis"] == "type"
    assert c["before"] == '  "type": "string"'
    assert c["after"] == '  "type": "integer"'
    assert '+  "type": "integer"' in c["evidence"]


# ---------------------------------------------------------------------------
# exit code 契約 (0/1/2)
# ---------------------------------------------------------------------------


def test_empty_hunks_is_ok_empty_array():
    rc, out, _ = run([])
    assert rc == 0
    assert out == []


def test_malformed_hunk_missing_file_path_is_violation_exit1():
    hunk = [
        schema_hunk(added=['  "required": ["id"]']),  # 正常
        {"added_lines": ["no file_path"]},  # file_path 欠落
    ]
    rc, out, err = run(hunk)
    assert rc == 1  # violation
    assert len(out) == 1  # 正常 hunk の候補は出力される
    assert "file_path" in err


def test_missing_input_source_is_usage_error_exit2():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 2


def test_hunks_file_not_found_is_exit2(tmp_path):
    missing = tmp_path / "nope.json"
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--hunks", str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2


def test_invalid_json_is_exit2():
    rc, _, err = run("{ not json")
    assert rc == 2
    assert err.strip()


def test_bad_map_is_exit2(tmp_path):
    bad_map = tmp_path / "bad.json"
    bad_map.write_text(json.dumps({"no_artifact_kinds": True}), encoding="utf-8")
    rc, _, err = run([schema_hunk(added=['  "type": "string"'])], map_path=bad_map)
    assert rc == 2
    assert err.strip()


def test_help_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--hunks" in proc.stdout and "--map" in proc.stdout


# ---------------------------------------------------------------------------
# 既定 map (self-relative) が読めること
# ---------------------------------------------------------------------------


def test_default_map_resolves_self_relative():
    # --map を渡さなくても既定の self-relative map で写像できる。
    rc, out, _ = run([schema_hunk(added=['  "type": "boolean"'])])
    assert rc == 0
    assert out[0]["axis"] == "type"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ───────── C08 契約: added_lines/removed_lines は marker 除去済み本文 ─────────
def test_body_leading_dash_is_not_stripped_again():
    """C08 は line[1:] で marker 除去済み本文を渡す。C09 が再除去すると YAML list の
    `- item` や markdown 箇条書きが先頭 1 文字を失い、エラーなく写像対象が変質する。"""
    hunk = {
        "file_path": "plugins/harness-creator/skills/x/templates/t.yaml",
        "change_type": "modify",
        "added_lines": ["- new_item"],
        "removed_lines": ["- old_item"],
    }
    rc, candidates, _ = run([hunk])
    assert rc == 0 and candidates
    c = candidates[0]
    # before/after が本文そのまま (先頭 '-' を保持) であること。
    assert c["after"] == "- new_item", c
    assert c["before"] == "- old_item", c
    # evidence にも本文が欠けずに載る。
    assert "- new_item" in c["evidence"] and "- old_item" in c["evidence"]


def test_raw_lines_path_still_strips_diff_markers():
    """raw unified diff 行 (lines) を渡す経路では marker 除去が正しい挙動。"""
    hunk = {
        "file_path": "plugins/harness-creator/skills/x/templates/t.yaml",
        "lines": ["+added_body", "-removed_body", " context", "+++ b/x", "--- a/x"],
    }
    rc, candidates, _ = run([hunk])
    assert rc == 0 and candidates
    c = candidates[0]
    assert c["after"] == "added_body" and c["before"] == "removed_body"
