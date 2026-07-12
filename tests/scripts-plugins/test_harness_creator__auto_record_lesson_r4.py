"""Genuine functional tests (scripts4) for
plugins/harness-creator/skills/run-build-skill/scripts/auto-record-lesson.py.

このスクリプトは Claude Code Hook の JSON(stdin)を読み、失敗シグネチャを検出したら
plugins/harness-creator/lessons-learned/ に構造化 lesson(frontmatter +
observation / hypothesis / proposed_action)を upsert する。git や repo の他領域には
触れない。network/keychain は使わない。

scripts4 では実ファイルパスを importlib でロードして純関数を実入力で検査し、
副作用境界(_lessons_dir への書き込み)は monkeypatch で tmp_path に向けて repo を
汚さない形で main / _upsert_lesson の全分岐・終了コードを検証する。CLI 全体は
subprocess(sys.executable + stdin)で exit code と書き込みの有無を assert する。

scripts3 と同名衝突を避けるため module 名・ファイル名に _r4 サフィックスを付す。
"""
import datetime as _dt
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "auto-record-lesson.py"
)

_SPEC = importlib.util.spec_from_file_location("auto_record_lesson_r4", SCRIPT)
ARL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ARL)


# ===================== _plugin_root / _lessons_dir =====================


def test_plugin_root_points_to_harness_creator_plugin():
    root = ARL._plugin_root()
    assert root.name == "harness-creator"
    # 実ファイルは .../harness-creator/skills/run-build-skill/scripts/auto-record-lesson.py
    assert root == SCRIPT.resolve().parents[3]


def test_lessons_dir_is_under_plugin_root():
    d = ARL._lessons_dir()
    assert d.name == "lessons-learned"
    assert d.parent.name == "harness-creator"


# ===================== _read_hook_input (stdin 解釈) =====================


def _set_stdin(monkeypatch, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))


def test_read_hook_input_parses_valid_json(monkeypatch):
    _set_stdin(monkeypatch, '{"tool_name": "Skill", "n": 3}')
    assert ARL._read_hook_input() == {"tool_name": "Skill", "n": 3}


def test_read_hook_input_blank_returns_empty(monkeypatch):
    _set_stdin(monkeypatch, "\n   \t ")
    assert ARL._read_hook_input() == {}


def test_read_hook_input_malformed_json_swallowed(monkeypatch):
    _set_stdin(monkeypatch, "{this is : not json")
    assert ARL._read_hook_input() == {}


def test_read_hook_input_non_object_json_returned_as_is(monkeypatch):
    # json.loads は list も受理する。例外を投げず素通しすることを確認。
    _set_stdin(monkeypatch, "[1, 2, 3]")
    assert ARL._read_hook_input() == [1, 2, 3]


# ===================== _flatten_text =====================


def test_flatten_text_collects_all_strings_recursively():
    payload = {
        "top": "alpha",
        "nest": {"mid": "beta", "arr": ["gamma", "delta"]},
        "mixed": [{"deep": "epsilon"}, 7, None, False],
    }
    lines = ARL._flatten_text(payload).split("\n")
    assert {"alpha", "beta", "gamma", "delta", "epsilon"} <= set(lines)
    # 非文字列の葉は混入しない
    assert "7" not in lines and "None" not in lines and "False" not in lines


def test_flatten_text_scalar_inputs():
    assert ARL._flatten_text("solo") == "solo"
    assert ARL._flatten_text(123) == ""  # 文字列でも dict でも list でもない
    assert ARL._flatten_text(None) == ""


# ===================== _detect_failure =====================


@pytest.mark.parametrize(
    "text",
    [
        "step FAILED",
        "FAIL: boom",
        "a FAILURE occurred",
        "got an ERROR",
        "Traceback (most recent call last):",
        "validator step FAIL now",
        "process had non-zero exit",
        "nonzero exit detected",  # ハイフン無しも \bnon-?zero exit\b に一致
        "exit code 7",
        "exit status: 130",
        "exit code=2 from child",
    ],
)
def test_detect_failure_positive(text):
    assert ARL._detect_failure(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "all good",
        "tests passed",
        "exit code 0",  # ゼロ終了は失敗扱いしない
        "exit status 0",
        "failsafe is enabled",  # 'fail' を含むが \bFAIL\b 境界に当たらない
        "non zero exit detected",  # 'non zero'(空白)は non-?zero に当たらず非検出
        "exit=2 from child",  # code/status キーワードが無いと非検出
        "",
    ],
)
def test_detect_failure_negative(text):
    assert ARL._detect_failure(text) is False


# ===================== _estimate_severity =====================


@pytest.mark.parametrize(
    "text",
    [
        "FATAL: kernel panic",
        "this is CRITICAL",
        "Traceback (most recent call last):",
        "validator FAIL on rubric",
    ],
)
def test_estimate_severity_high(text):
    assert ARL._estimate_severity(text) == "high"


@pytest.mark.parametrize("text", ["plain ERROR", "FAILED softly", "exit code 1"])
def test_estimate_severity_medium(text):
    assert ARL._estimate_severity(text) == "medium"


# ===================== _slugify =====================


def test_slugify_basic_lowercase_and_dash():
    assert ARL._slugify("My Build Step") == "my-build-step"


def test_slugify_collapses_runs_and_trims():
    assert ARL._slugify("--Foo__BAR!! Baz--") == "foo-bar-baz"


def test_slugify_keeps_digits():
    assert ARL._slugify("R4 trace 2026") == "r4-trace-2026"


@pytest.mark.parametrize("value", ["", "!!!", "   ", "***---"])
def test_slugify_empty_or_symbol_only_fallback(value):
    assert ARL._slugify(value) == "lesson"


# ===================== _extract_slug =====================


def test_extract_slug_event_and_tool_only():
    hook = {"hook_event_name": "PostToolUse", "tool_name": "Write"}
    assert ARL._extract_slug(hook, "") == "posttooluse-write"


def test_extract_slug_path_hint_uses_basename():
    hook = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/deep/dir/capability.json"},
    }
    assert ARL._extract_slug(hook, "") == "posttooluse-edit-capability-json"


def test_extract_slug_plain_path_key_basenamed():
    # キーが 'path'(末尾 path)→ basename 採用
    hook = {"tool_name": "Read", "tool_input": {"path": "/a/b/notes.txt"}}
    slug = ARL._extract_slug(hook, "")
    assert slug == "post-read-notes-txt"


def test_extract_slug_skill_hint_not_basenamed():
    hook = {"event": "Stop", "tool": "Skill", "tool_input": {"skill": "run-build-skill"}}
    assert ARL._extract_slug(hook, "") == "stop-skill-run-build-skill"


def test_extract_slug_command_hint_used():
    hook = {"tool_name": "Bash", "tool_input": {"command": "make test"}}
    slug = ARL._extract_slug(hook, "")
    assert slug.startswith("post-bash-")
    assert "make" in slug and "test" in slug


def test_extract_slug_first_present_hint_wins():
    # 優先順 file_path > path > skill > command。両方あれば file_path 採用。
    hook = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/x/first.json", "skill": "ignored"},
    }
    assert ARL._extract_slug(hook, "") == "post-edit-first-json"


def test_extract_slug_empty_hint_value_skipped():
    # file_path が空文字なら hint 扱いしない(次の候補も無ければ event-tool のみ)
    hook = {"tool_name": "Edit", "tool_input": {"file_path": "", "command": "go"}}
    slug = ARL._extract_slug(hook, "")
    assert slug == "post-edit-go"


def test_extract_slug_non_dict_tool_input():
    hook = {"tool_name": "Edit", "tool_input": ["a", "b"]}
    assert ARL._extract_slug(hook, "") == "post-edit"


def test_extract_slug_all_defaults_when_empty_hook():
    assert ARL._extract_slug({}, "") == "post-event"


def test_extract_slug_truncated_to_60():
    hook = {"tool_name": "Bash", "tool_input": {"command": "y" * 300}}
    assert len(ARL._extract_slug(hook, "")) <= 60


# ===================== _build_entry =====================


def test_build_entry_full_fields_and_first_failing_line():
    hook = {"hook_event_name": "PostToolUse", "tool_name": "Skill"}
    text = "ok line\nnext ERROR boom\ntail FAIL"
    entry = ARL._build_entry(hook, text, "high")
    assert entry["date"] == _dt.date.today().isoformat()
    assert entry["trigger_event"] == "PostToolUse"
    assert entry["tool"] == "Skill"
    assert entry["severity"] == "high"
    assert entry["capability"] == "skill-invoke"
    assert entry["observation"] == "next ERROR boom"


@pytest.mark.parametrize(
    "tool,cap",
    [("Edit", "edit"), ("Write", "write"), ("Bash", "shell"),
     ("Skill", "skill-invoke"), ("Read", "read")],
)
def test_build_entry_capability_map_full(tool, cap):
    assert ARL._build_entry({"tool_name": tool}, "ERROR", "medium")["capability"] == cap


def test_build_entry_unknown_tool_maps_unknown():
    e = ARL._build_entry({"tool_name": "Glob"}, "ERROR", "medium")
    assert e["capability"] == "unknown"
    assert e["tool"] == "Glob"


def test_build_entry_defaults_when_tool_event_absent():
    e = ARL._build_entry({}, "ERROR x", "medium")
    assert e["tool"] == "unknown"
    assert e["trigger_event"] == "unknown"
    assert e["capability"] == "unknown"


def test_build_entry_observation_truncated_to_240():
    e = ARL._build_entry({"tool_name": "Edit"}, "ERROR " + "q" * 500, "medium")
    assert len(e["observation"]) == 240


def test_build_entry_fallback_when_no_single_line_matches():
    # "non-zero exit" は連結時のみ一致。行で割ると個々は不一致 → fallback 観測。
    e = ARL._build_entry({"tool_name": "Edit"}, "non-zero\nexit", "medium")
    assert e["observation"] == "(失敗シグネチャは検出されたが該当行抽出に失敗)"


# ===================== _render_markdown =====================


def test_render_markdown_structure():
    entry = {
        "date": "2026-06-24",
        "trigger_event": "Stop",
        "tool": "Skill",
        "severity": "high",
        "capability": "skill-invoke",
        "observation": "kaboom ERROR",
    }
    md = ARL._render_markdown(entry)
    assert md.startswith("---\n")
    for needle in (
        "date: 2026-06-24",
        "trigger_event: Stop",
        "tool: Skill",
        "severity: high",
        "capability: skill-invoke",
        "## observation",
        "kaboom ERROR",
        "## hypothesis",
        "## proposed_action",
    ):
        assert needle in md


# ===================== _upsert_lesson =====================


def test_upsert_lesson_creates_file_and_parents(tmp_path):
    entry = {
        "date": "2026-06-24", "trigger_event": "Stop", "tool": "Skill",
        "severity": "medium", "capability": "skill-invoke", "observation": "first ERROR",
    }
    target = tmp_path / "a" / "b" / "2026-06-24-stop.md"
    ARL._upsert_lesson(target, entry)
    assert target.exists()
    body = target.read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "first ERROR" in body


def test_upsert_lesson_appends_on_existing(tmp_path):
    base = {
        "date": "2026-06-24", "trigger_event": "Stop", "tool": "Skill",
        "severity": "medium", "capability": "skill-invoke", "observation": "first ERROR",
    }
    target = tmp_path / "2026-06-24-stop.md"
    ARL._upsert_lesson(target, base)
    ARL._upsert_lesson(target, dict(base, observation="second ERROR"))
    body = target.read_text(encoding="utf-8")
    assert "first ERROR" in body and "second ERROR" in body
    # 追記分には timestamp 付き observation 見出しが増える
    assert body.count("## observation") >= 2


# ===================== _has_genuine_context (断片ノイズ封鎖) =====================


def test_genuine_context_requires_tool_hint_and_response_failure():
    hook = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "tool_response": {"stderr": "ERROR exit code 1"},
    }
    assert ARL._has_genuine_context(hook) is True


@pytest.mark.parametrize(
    "hook",
    [
        {"tool_name": "Edit", "x": "ERROR boom"},  # tool_input なし ("ERROR boom" 型)
        {"tool_input": {"command": "x"}, "tool_response": {"e": "ERROR"}},  # tool 名なし
        {"tool_name": "Bash", "tool_input": {}, "tool_response": {"e": "ERROR"}},  # ヒントなし
        {"tool_name": "Bash", "tool_input": {"command": ""}, "tool_response": {"e": "ERROR"}},
        # 失敗語が tool_response 外の無関係キーのみ (引用・テスト副産物の混入形)
        {"tool_name": "Bash", "tool_input": {"command": "x"}, "note": "ERROR boom"},
        {"tool_name": "Bash", "tool_input": {"command": "x"}, "tool_response": {"out": "ok"}},
        "not a dict",
        {},
    ],
)
def test_genuine_context_rejects_fragments(hook):
    assert ARL._has_genuine_context(hook) is False


def test_main_skips_fragment_noise(monkeypatch, tmp_path):
    # 失敗語はあるが文脈不足 → 記録しない (2026-06-24 "ERROR boom" 再発防止)。
    _set_stdin(monkeypatch, json.dumps({"tool_name": "Edit", "x": "ERROR boom"}))
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    assert ARL.main() == 0
    assert not lessons.exists()


# ===================== 索引 append (Loop B 断線修理) =====================


def _entry_fixture(observation="validator FAIL: rule X"):
    return {
        "date": "2026-07-02", "trigger_event": "PostToolUse", "tool": "Bash",
        "severity": "high", "capability": "shell", "observation": observation,
    }


def test_lessons_index_path_is_sibling_knowledge(tmp_path):
    d = tmp_path / "lessons-learned"
    assert ARL._lessons_index_path(d) == tmp_path / "knowledge" / "knowledge-lessons-index.json"


def test_append_index_entry_creates_index_when_absent(tmp_path):
    index = tmp_path / "knowledge" / "knowledge-lessons-index.json"
    lesson = tmp_path / "lessons-learned" / "2026-07-02-x.md"
    assert ARL._append_index_entry(index, lesson, _entry_fixture()) is True
    data = json.loads(index.read_text(encoding="utf-8"))
    assert data["category"] == "lessons-index"
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == "lessons-index_001"
    assert "validator FAIL: rule X" in item["title"]
    assert item["source"]["type"] == "lesson"
    assert item["source"]["date"] == "2026-07-02"


def test_append_index_entry_is_idempotent_per_source_file(tmp_path):
    index = tmp_path / "knowledge" / "knowledge-lessons-index.json"
    lesson = tmp_path / "lessons-learned" / "2026-07-02-x.md"
    assert ARL._append_index_entry(index, lesson, _entry_fixture()) is True
    # 同一 lesson (同日 slug への observation 追記) は再登録しない。
    assert ARL._append_index_entry(index, lesson, _entry_fixture("second ERROR")) is False
    assert len(json.loads(index.read_text(encoding="utf-8"))["items"]) == 1


def test_append_index_entry_sequences_id_from_existing_max(tmp_path):
    index = tmp_path / "knowledge" / "knowledge-lessons-index.json"
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({
        "category": "lessons-index",
        "items": [{"id": "lessons-index_002", "source": {"file": "other.md"}}],
    }), encoding="utf-8")
    lesson = tmp_path / "lessons-learned" / "2026-07-02-x.md"
    assert ARL._append_index_entry(index, lesson, _entry_fixture()) is True
    ids = [i["id"] for i in json.loads(index.read_text(encoding="utf-8"))["items"]]
    assert "lessons-index_003" in ids


def test_append_index_entry_swallows_broken_index(tmp_path):
    index = tmp_path / "knowledge" / "knowledge-lessons-index.json"
    index.parent.mkdir(parents=True)
    index.write_text("{broken", encoding="utf-8")
    lesson = tmp_path / "lessons-learned" / "2026-07-02-x.md"
    # 壊れた索引でも例外にせず False (lesson 記録は巻き込まない)。
    assert ARL._append_index_entry(index, lesson, _entry_fixture()) is False


def test_main_appends_index_alongside_lesson(monkeypatch, tmp_path):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "tool_response": {"stderr": "Traceback (most recent call last):\nERROR boom"},
    }
    _set_stdin(monkeypatch, json.dumps(payload))
    lessons = tmp_path / "lessons-learned"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    assert ARL.main() == 0
    index = tmp_path / "knowledge" / "knowledge-lessons-index.json"
    assert index.exists()
    items = json.loads(index.read_text(encoding="utf-8"))["items"]
    assert len(items) == 1
    assert items[0]["source"]["file"].endswith(".md")


# ===================== main() in-process =====================


def test_main_silent_success_when_no_failure(monkeypatch, tmp_path):
    _set_stdin(monkeypatch, json.dumps({"tool_name": "Edit", "msg": "all green"}))
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    assert ARL.main() == 0
    assert not lessons.exists()  # 書き込み無し


def test_main_silent_success_on_empty_stdin(monkeypatch, tmp_path):
    _set_stdin(monkeypatch, "")
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    assert ARL.main() == 0
    assert not lessons.exists()


def test_main_writes_high_severity_lesson(monkeypatch, tmp_path):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "tool_response": {"stderr": "Traceback (most recent call last):\nERROR boom"},
    }
    _set_stdin(monkeypatch, json.dumps(payload))
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    assert ARL.main() == 0
    files = list(lessons.glob("*.md"))
    assert len(files) == 1
    assert files[0].name.startswith(_dt.date.today().isoformat())
    assert "bash" in files[0].name
    body = files[0].read_text(encoding="utf-8")
    assert "severity: high" in body  # Traceback -> high
    assert "capability: shell" in body


def test_main_upsert_same_slug_single_file(monkeypatch, tmp_path):
    payload = {
        "hook_event_name": "Stop",
        "tool_name": "Skill",
        "tool_input": {"skill": "run-build-skill"},
        "tool_response": {"out": "validator FAIL"},
    }
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    _set_stdin(monkeypatch, json.dumps(payload))
    assert ARL.main() == 0
    _set_stdin(monkeypatch, json.dumps(payload))
    assert ARL.main() == 0
    files = list(lessons.glob("*.md"))
    assert len(files) == 1  # 同日同 slug → 追記、新規作成しない
    assert files[0].read_text(encoding="utf-8").count("## observation") >= 2


def test_main_oserror_degrades_to_noop_exit0(monkeypatch, capsys):
    """移植性: 全候補が書込不能なら graceful degrade で exit 0 / Traceback 無し。

    read-only install を模す。旧仕様の exit 1 は廃し hook を絶対に
    クラッシュさせない (no writable sink → silent no-op)。
    """
    _set_stdin(monkeypatch, json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "/x/rubric.json"},
        "tool_response": {"stderr": "ERROR boom exit code 1"},
    }))
    monkeypatch.setattr(ARL, "_dir_is_writable", lambda d: False)
    assert ARL.main() == 0
    err = capsys.readouterr().err
    assert "no writable sink" in err
    assert "Traceback" not in err


# ===================== CLI subprocess (exit code + 書き込み) =====================


def _run_cli(stdin_payload, lessons_dir):
    """子プロセスで起動。_lessons_dir は wrapper で tmp に差し替えて repo 非汚染。
    COVERAGE_PROCESS_START があれば sitecustomize 経由で子プロセスも計測される。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    wrapper = (
        "import importlib.util,sys,pathlib\n"
        f"spec=importlib.util.spec_from_file_location('m', {str(SCRIPT)!r})\n"
        "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        f"m._lessons_dir=lambda: pathlib.Path({str(lessons_dir)!r})\n"
        "sys.exit(m.main())\n"
    )
    return subprocess.run(
        [sys.executable, "-c", wrapper],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_no_failure_exit0_no_write(tmp_path):
    lessons = tmp_path / "lessons"
    res = _run_cli(json.dumps({"tool_name": "Edit", "x": "fine"}), lessons)
    assert res.returncode == 0
    assert not lessons.exists()


def test_cli_failure_exit0_and_writes(tmp_path):
    lessons = tmp_path / "lessons"
    payload = json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/x/rubric.json"},
        "tool_response": {"stderr": "ERROR something exit code 1"},
    })
    res = _run_cli(payload, lessons)
    assert res.returncode == 0
    files = list(lessons.glob("*.md"))
    assert len(files) == 1
    assert "rubric-json" in files[0].name


def test_cli_invalid_json_stdin_exit0(tmp_path):
    lessons = tmp_path / "lessons"
    res = _run_cli("{broken", lessons)
    assert res.returncode == 0
    assert not lessons.exists()
