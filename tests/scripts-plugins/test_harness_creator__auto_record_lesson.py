"""Genuine functional tests for
plugins/harness-creator/skills/run-build-skill/scripts/auto-record-lesson.py.

このスクリプトは Claude Code Hook の JSON(stdin)を読み、失敗シグネチャを検出したら
lessons-learned/ に構造化 lesson(frontmatter + observation/hypothesis/proposed_action)を
upsert する。git や repo の他領域には触れない。

network/keychain は無い。唯一の副作用は _lessons_dir() への書き込みのため、
- 純関数 (_flatten_text/_detect_failure/_estimate_severity/_slugify/_extract_slug/
  _build_entry/_render_markdown) を実ファイルから import して実入力で assert
- _upsert_lesson / main() は _lessons_dir を monkeypatch で tmp_path に向けて repo 非汚染
- main() の終了コード・サイレント正常系・OSError 経路は in-process で検査
- CLI 全体は subprocess(sys.executable + stdin)で exit code と書き込み有無を assert

を行う。
"""
import datetime as _dt
import importlib.util
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

_SPEC = importlib.util.spec_from_file_location("auto_record_lesson_s3", SCRIPT)
ARL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ARL)


# ===================== _flatten_text =====================

def test_flatten_text_recurses_dict_list_str():
    payload = {
        "a": "top",
        "b": {"c": "nested", "d": ["l1", "l2"]},
        "e": [{"f": "deep"}, 42, None, True],
    }
    out = ARL._flatten_text(payload)
    lines = out.split("\n")
    assert "top" in lines
    assert "nested" in lines
    assert "l1" in lines and "l2" in lines
    assert "deep" in lines
    # 非文字列 (42/None/True) は無視される
    assert "42" not in lines
    assert "None" not in lines


def test_flatten_text_bare_string():
    assert ARL._flatten_text("just a string") == "just a string"


def test_flatten_text_empty_payload():
    assert ARL._flatten_text({}) == ""
    assert ARL._flatten_text([]) == ""


# ===================== _detect_failure =====================

@pytest.mark.parametrize(
    "text",
    [
        "the test FAILED here",
        "FAIL: assertion",
        "FAILURE detected",
        "some ERROR happened",
        "Traceback (most recent call last):",
        "validator something FAIL now",
        "process exited with non-zero exit",
        "exit code 1",
        "exit status: 42",
    ],
)
def test_detect_failure_true(text):
    assert ARL._detect_failure(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "everything is fine",
        "all tests passed",
        "exit code 0",  # 0 はゼロ終了 → 失敗扱いしない
        "exit status 0",
        "",
    ],
)
def test_detect_failure_false(text):
    assert ARL._detect_failure(text) is False


# ===================== _estimate_severity =====================

@pytest.mark.parametrize(
    "text",
    ["FATAL error", "this is CRITICAL", "Traceback (most recent call last)", "validator FAIL"],
)
def test_estimate_severity_high(text):
    assert ARL._estimate_severity(text) == "high"


def test_estimate_severity_medium_default():
    assert ARL._estimate_severity("plain ERROR with no strong hint") == "medium"
    assert ARL._estimate_severity("FAILED") == "medium"


# ===================== _slugify =====================

def test_slugify_lowercases_and_dashes():
    assert ARL._slugify("Hello World") == "hello-world"


def test_slugify_collapses_and_strips():
    assert ARL._slugify("  Foo___Bar!!! baz  ") == "foo-bar-baz"


def test_slugify_empty_fallback():
    assert ARL._slugify("") == "lesson"
    assert ARL._slugify("!!!") == "lesson"  # 記号のみ → 空 → fallback


# ===================== _extract_slug =====================

def test_extract_slug_uses_tool_and_event():
    hook = {"hook_event_name": "PostToolUse", "tool_name": "Edit"}
    assert ARL._extract_slug(hook, "") == "posttooluse-edit"


def test_extract_slug_with_file_path_hint_basename():
    hook = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "/some/dir/rubric.json"},
    }
    # *_path は basename だけ採用
    assert ARL._extract_slug(hook, "") == "posttooluse-edit-rubric-json"


def test_extract_slug_with_skill_hint_not_basenamed():
    hook = {"event": "Stop", "tool": "Skill", "tool_input": {"skill": "run-build-skill"}}
    assert ARL._extract_slug(hook, "") == "stop-skill-run-build-skill"


def test_extract_slug_command_hint():
    hook = {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}}
    slug = ARL._extract_slug(hook, "")
    assert slug.startswith("post-bash-")  # event 既定 'post'
    assert "pytest" in slug


def test_extract_slug_fallback_event_tool_when_no_hint():
    hook = {}  # tool/event とも欠落 → 既定 event/post
    assert ARL._extract_slug(hook, "") == "post-event"


def test_extract_slug_truncates_to_60():
    hook = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"command": "x" * 200},
    }
    assert len(ARL._extract_slug(hook, "")) <= 60


def test_extract_slug_ignores_non_string_tool_input():
    hook = {"tool_name": "Edit", "tool_input": ["not", "a", "dict"]}
    # tool_input が dict でない → hint 無し
    assert ARL._extract_slug(hook, "") == "post-edit"


# ===================== _build_entry =====================

def test_build_entry_maps_capability_and_picks_first_failing_line():
    hook = {"hook_event_name": "PostToolUse", "tool_name": "Bash"}
    text = "line ok\nthis ERROR line\nanother FAIL line"
    entry = ARL._build_entry(hook, text, "high")
    assert entry["date"] == _dt.date.today().isoformat()
    assert entry["trigger_event"] == "PostToolUse"
    assert entry["tool"] == "Bash"
    assert entry["severity"] == "high"
    assert entry["capability"] == "shell"  # Bash -> shell
    assert entry["observation"] == "this ERROR line"  # 先頭の失敗行


def test_build_entry_unknown_tool_capability():
    entry = ARL._build_entry({"tool_name": "Mystery"}, "ERROR x", "medium")
    assert entry["capability"] == "unknown"
    assert entry["tool"] == "Mystery"


def test_build_entry_observation_truncated_to_240():
    long_line = "ERROR " + "z" * 400
    entry = ARL._build_entry({"tool_name": "Edit"}, long_line, "medium")
    assert len(entry["observation"]) == 240


def test_build_entry_fallback_observation_when_no_line_matches():
    # _flatten_text の都合で text 全体としては検出されうるが、splitlines 各行が
    # 単独では失敗判定されないケース(行に分かれて壊れる failure)を作る。
    # 行内に必ずパターンがある通常ケースでは観測が取れるので、ここでは
    # 多語にまたがり 1 行毎には一致しないシグネチャを使う。
    text = "non-zero\nexit"  # "non-zero exit" は連結時のみ一致、行単位では不一致
    entry = ARL._build_entry({"tool_name": "Edit"}, text, "medium")
    assert entry["observation"] == "(失敗シグネチャは検出されたが該当行抽出に失敗)"


def test_build_entry_all_capability_map_entries():
    for tool, cap in {"Edit": "edit", "Write": "write", "Bash": "shell",
                      "Skill": "skill-invoke", "Read": "read"}.items():
        entry = ARL._build_entry({"tool_name": tool}, "ERROR", "medium")
        assert entry["capability"] == cap


# ===================== _render_markdown =====================

def test_render_markdown_contains_frontmatter_and_sections():
    entry = {
        "date": "2026-06-24",
        "trigger_event": "PostToolUse",
        "tool": "Edit",
        "severity": "high",
        "capability": "edit",
        "observation": "boom ERROR",
    }
    md = ARL._render_markdown(entry)
    assert md.startswith("---\n")
    assert "date: 2026-06-24" in md
    assert "trigger_event: PostToolUse" in md
    assert "severity: high" in md
    assert "capability: edit" in md
    assert "## observation" in md
    assert "boom ERROR" in md
    assert "## hypothesis" in md
    assert "## proposed_action" in md


# ===================== _upsert_lesson =====================

def test_upsert_lesson_creates_new_file(tmp_path):
    entry = {
        "date": "2026-06-24",
        "trigger_event": "Stop",
        "tool": "Skill",
        "severity": "medium",
        "capability": "skill-invoke",
        "observation": "first ERROR",
    }
    target = tmp_path / "nested" / "2026-06-24-stop-skill.md"
    ARL._upsert_lesson(target, entry)
    assert target.exists()  # 親ディレクトリも自動生成
    content = target.read_text(encoding="utf-8")
    assert "first ERROR" in content
    assert content.startswith("---")


def test_upsert_lesson_appends_when_exists(tmp_path):
    entry1 = {
        "date": "2026-06-24", "trigger_event": "Stop", "tool": "Skill",
        "severity": "medium", "capability": "skill-invoke", "observation": "first ERROR",
    }
    entry2 = dict(entry1, observation="second ERROR")
    target = tmp_path / "2026-06-24-stop-skill.md"
    ARL._upsert_lesson(target, entry1)
    ARL._upsert_lesson(target, entry2)
    content = target.read_text(encoding="utf-8")
    assert "first ERROR" in content
    assert "second ERROR" in content
    # 追記分には timestamp 付き observation 見出しが入る
    assert content.count("## observation") >= 2


# ===================== _lessons_dir / _plugin_root =====================

def test_lessons_dir_points_to_harness_creator_plugin():
    d = ARL._lessons_dir()
    assert d.name == "lessons-learned"
    assert d.parent.name == "harness-creator"


# ===================== _read_hook_input (stdin) =====================

def test_read_hook_input_valid_json(monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"tool_name": "Edit"}'))
    assert ARL._read_hook_input() == {"tool_name": "Edit"}


def test_read_hook_input_empty_returns_empty_dict(monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("   \n  "))
    assert ARL._read_hook_input() == {}


def test_read_hook_input_invalid_json_swallowed(monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    assert ARL._read_hook_input() == {}


# ===================== main() in-process =====================

def _set_stdin(monkeypatch, payload):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))


def test_main_no_failure_silent_success(monkeypatch, tmp_path):
    _set_stdin(monkeypatch, json.dumps({"tool_name": "Edit", "ok": "all green"}))
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: tmp_path / "lessons")
    assert ARL.main() == 0
    # 失敗未検出 → ファイルは作られない
    assert not (tmp_path / "lessons").exists()


def test_main_empty_input_silent_success(monkeypatch, tmp_path):
    _set_stdin(monkeypatch, "")
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: tmp_path / "lessons")
    assert ARL.main() == 0
    assert not (tmp_path / "lessons").exists()


def test_main_writes_lesson_on_failure(monkeypatch, tmp_path):
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
    name = files[0].name
    today = _dt.date.today().isoformat()
    assert name.startswith(today)
    assert "bash" in name  # slug に tool 名
    body = files[0].read_text(encoding="utf-8")
    assert "severity: high" in body  # Traceback -> high
    assert "shell" in body  # Bash capability


def test_main_upsert_same_slug_appends(monkeypatch, tmp_path):
    payload = {
        "hook_event_name": "Stop",
        "tool_name": "Skill",
        "tool_input": {"skill": "run-build-skill"},
        "tool_response": {"out": "validator FAIL"},
    }
    _set_stdin(monkeypatch, json.dumps(payload))
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(ARL, "_lessons_dir", lambda: lessons)
    assert ARL.main() == 0
    # 二回目: 同日同 slug → 追記
    _set_stdin(monkeypatch, json.dumps(payload))
    assert ARL.main() == 0
    files = list(lessons.glob("*.md"))
    assert len(files) == 1  # 同一ファイルに追記、新規作成しない
    assert files[0].read_text(encoding="utf-8").count("## observation") >= 2


def test_main_oserror_degrades_to_noop_exit0(monkeypatch, capsys):
    """移植性: 全候補が書込不能なら graceful degrade で exit 0 / Traceback 無し。

    read-only install を模す。旧仕様の exit 1 は廃し、PostToolUse hook を絶対に
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


def test_main_oserror_on_primary_falls_back_exit0(monkeypatch, tmp_path, capsys):
    """primary の upsert が OSError でも fallback 候補へ退避し exit 0。"""
    _set_stdin(monkeypatch, json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "/x/rubric.json"},
        "tool_response": {"stderr": "ERROR boom exit code 1"},
    }))
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    monkeypatch.setattr(ARL, "_candidate_dirs", lambda: [primary, fallback])
    monkeypatch.setattr(ARL, "_dir_is_writable", lambda d: True)
    orig = ARL._upsert_lesson

    def boom(path, entry):
        if primary in path.parents:
            raise OSError("disk full")
        return orig(path, entry)

    monkeypatch.setattr(ARL, "_upsert_lesson", boom)
    assert ARL.main() == 0
    assert list(fallback.glob("*.md")), "fallback に退避されていない"
    assert "Traceback" not in capsys.readouterr().err


# ===================== CLI subprocess (exit code + 書き込み) =====================

def _run_cli(stdin_payload, lessons_dir):
    """auto-record-lesson を子プロセスで起動。_lessons_dir を上書きできないので
    書き込み先を tmp に向けるため、スクリプトを wrapper 経由で実行する。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # COVERAGE_PROCESS_START があれば子プロセス計測 (sitecustomize 経由)
    wrapper = (
        "import importlib.util,sys\n"
        f"spec=importlib.util.spec_from_file_location('m', {str(SCRIPT)!r})\n"
        "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        f"m._lessons_dir=lambda: __import__('pathlib').Path({str(lessons_dir)!r})\n"
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
    res = _run_cli(json.dumps({"tool_name": "Edit", "x": "all good"}), lessons)
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
    res = _run_cli("{broken json", lessons)
    # 不正入力は握りつぶしてサイレント正常終了
    assert res.returncode == 0
    assert not lessons.exists()
