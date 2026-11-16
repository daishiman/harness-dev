"""extract-harness-run-metrics.py が 1 回の実行を transcript から数えることを固める (harness-hxi)。

小さな transcript を組み立て、各数値を固定する。区切りが見つからない transcript では
推測で数えずに exit 2 で止まることも示す。
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "harness-creator" / "scripts" / "extract-harness-run-metrics.py"
SPEC = importlib.util.spec_from_file_location("extract_harness_run_metrics", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

REPORT = "## 完了レポート\n- mode: draft\n- gates_passed: [gate-1, gate-2]\n- build_lint_receipt: PASS"


def _user(ts, text):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def _assistant(ts, msg_id, blocks, usage=None):
    message = {"id": msg_id, "role": "assistant", "content": blocks}
    if usage:
        message["usage"] = usage
    return {"type": "assistant", "timestamp": ts, "message": message}


def _use(tool_id, name, **args):
    return {"type": "tool_use", "id": tool_id, "name": name, "input": args}


def _result(ts, tool_id, content="", extra=None):
    event = {"type": "user", "timestamp": ts,
             "message": {"role": "user", "content": [
                 {"type": "tool_result", "tool_use_id": tool_id, "content": content}]}}
    if extra is not None:
        event["toolUseResult"] = extra
    return event


def _transcript():
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100}
    return [
        _user("2026-11-14T00:00:00Z", "前の作業"),
        _assistant("2026-11-14T00:00:01Z", "m0", [{"type": "text", "text": "了解"}], usage),
        _user("2026-11-14T00:01:00Z", "議事録を要約する skill を作って"),
        _assistant("2026-11-14T00:01:05Z", "m1", [_use("s1", "Skill", skill="harness-creator:capability-build")], usage),
        # 同じ message.id の分割 entry は usage を 1 回だけ数える
        _assistant("2026-11-14T00:01:06Z", "m1", [_use("r1", "Read", file_path="/x/SKILL.md")], usage),
        _result("2026-11-14T00:01:07Z", "r1", extra={"type": "text", "file": {"filePath": "/x/SKILL.md", "content": "abcd"}}),
        _assistant("2026-11-14T00:01:08Z", "m2", [
            _use("r2", "Read", file_path="/p/references/yaml-spec-cache.md", offset=10, limit=5),
            _use("b1", "Bash", command="awk '/hooks/' references/yaml-spec-cache.md"),
            _use("b2", "Bash", command="python3 validate-build-trace.py --x && python3 validate-build-trace.py --y; python3 scripts/lint-skill-name.py"),
        ]),
        _result("2026-11-14T00:01:09Z", "r2", extra={"type": "text", "file": {"filePath": "/p/references/yaml-spec-cache.md", "content": "あい"}}),
        _result("2026-11-14T00:01:10Z", "b1", extra={"stdout": "12345", "stderr": ""}),
        _result("2026-11-14T00:01:11Z", "b2", extra={"stdout": "", "stderr": ""}),
        _assistant("2026-11-14T00:01:12Z", "m3", [_use("q1", "AskUserQuestion", questions=[{"q": 1}, {"q": 2}])]),
        _result("2026-11-14T00:02:00Z", "q1", content="answered"),
        _assistant("2026-11-14T00:02:01Z", "m4", [
            _use("a1", "Agent", description="sync", prompt="p"),
            _use("a2", "Agent", description="bg", prompt="p", run_in_background=True),
            _use("a3", "Task", description="lost", prompt="p"),
            _use("s2", "Skill", skill="harness-creator:run-build-skill"),
        ]),
        _result("2026-11-14T00:03:00Z", "a1", extra={"status": "completed", "totalTokens": 700}),
        _result("2026-11-14T00:03:01Z", "a2", extra={"status": "async_launched"}),
        _user("2026-11-14T00:04:00Z", "<task-notification>\n<tool-use-id>a2</tool-use-id>\n<usage><subagent_tokens>300</subagent_tokens></usage>\n</task-notification>"),
        # 新しい Claude Code は通知と途中の発言を attachment で残す。通知は tool-use-id で重複を除く
        {"type": "attachment", "timestamp": "2026-11-14T00:04:00Z", "attachment": {
            "type": "queued_command", "commandMode": "task-notification",
            "prompt": "<task-notification>\n<tool-use-id>a2</tool-use-id>\n<usage><subagent_tokens>300</subagent_tokens></usage>"}},
        {"type": "attachment", "timestamp": "2026-11-14T00:04:00Z", "attachment": {
            "type": "queued_command", "commandMode": "prompt", "prompt": "急いで"}},
        _assistant("2026-11-14T00:04:01Z", "m5", [{"type": "text", "text": "Gate 1 を承認しますか?"}]),
        _user("2026-11-14T00:05:00Z", "承認"),
        {"type": "user", "timestamp": "2026-11-14T00:05:01Z", "isMeta": True, "message": {"role": "user", "content": "meta"}},
        _assistant("2026-11-14T00:10:00Z", "m6", [{"type": "text", "text": REPORT}]),
        _user("2026-11-14T00:11:00Z", "ありがとう"),
    ]


def _write(tmp_path, events, name="t.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    return path


def _run(tmp_path, capsys, events, *args):
    rc = MOD.main([str(_write(tmp_path, events)), *args])
    captured = capsys.readouterr()
    return rc, (json.loads(captured.out) if rc == 0 else None), captured.err


def test_counts_one_run(tmp_path, capsys):
    rc, report, _ = _run(tmp_path, capsys, _transcript())
    assert rc == 0
    assert report["runs_found"] == 1
    assert report["boundaries"]["request_at"] == "2026-11-14T00:01:00Z"
    assert report["boundaries"]["end_at"] == "2026-11-14T00:10:00Z"
    assert report["wall_seconds"] == 540.0
    assert report["questions"] == {"ask_user_question_calls": 1, "ask_user_question_items": 2,
                                   "user_turns": 1, "round_trips": 2, "queued_prompts": 1}
    # 結果に agentId が無いので subagent の transcript は辿れない (3 本とも missing)。
    # final_context_tokens は最後の呼び出しの context の和で、累計の usage とは別に出す
    assert report["agents"] == {"launched": 3, "forked_skills": 0,
                                "transcripts": {"found": 0, "missing": 3, "nested": 0}, "usage": {},
                                "final_context_tokens": 1000, "final_context_unknown": 1}
    # m1 (2 entry) を 1 回、m2-m6 は usage 無し
    assert report["main_tokens"] == {"cache_read_input_tokens": 100, "input_tokens": 10, "output_tokens": 5}
    assert report["read"] == {"calls": 2, "bytes": 4 + 6, "yaml_spec_cache_bytes": 6 + 5,
                              "bash_calls": 2, "bash_output_bytes": 5}
    assert report["checkers"] == {"lint-skill-name": 1, "validate-build-trace": 2}
    assert report["skills"] == {"harness-creator:capability-build": 1, "harness-creator:run-build-skill": 1}


def test_slash_command_start_uses_the_command_as_request(tmp_path, capsys):
    events = [
        _user("2026-11-14T01:00:00Z", "<command-message>capability-build</command-message>\n<command-name>/capability-build</command-name>"),
        _assistant("2026-11-14T01:00:30Z", "m1", [{"type": "text", "text": REPORT}]),
    ]
    rc, report, _ = _run(tmp_path, capsys, events)
    assert rc == 0
    assert report["boundaries"]["request_event"] == report["boundaries"]["start_event"] == 0
    assert report["wall_seconds"] == 30.0
    assert report["questions"]["user_turns"] == 0


def test_second_run_is_selectable(tmp_path, capsys):
    events = _transcript() + _transcript()[2:]
    rc, report, _ = _run(tmp_path, capsys, events, "--run", "2")
    assert rc == 0 and report["runs_found"] == 2
    assert report["questions"]["round_trips"] == 2


@pytest.mark.parametrize("events, reason", [
    ([e for e in _transcript() if "gates_passed" not in json.dumps(e)], "終わりの目印"),
    ([e for e in _transcript() if '"Skill"' not in json.dumps(e)], "始まりの skill"),
])
def test_stops_when_boundary_missing(tmp_path, capsys, events, reason):
    rc, report, err = _run(tmp_path, capsys, events)
    assert rc == 2 and report is None
    assert reason in err


def test_rejects_missing_run_and_broken_line(tmp_path, capsys):
    rc, _, err = _run(tmp_path, capsys, _transcript(), "--run", "2")
    assert rc == 2 and "--run 2" in err
    path = tmp_path / "broken.jsonl"
    path.write_text('{"type": "user"}\n{broken\n', encoding="utf-8")
    assert MOD.main([str(path)]) == 2
    assert "broken.jsonl:2" in capsys.readouterr().err


def test_custom_boundaries_and_out(tmp_path, capsys):
    events = [
        _user("2026-11-14T02:00:00Z", "dev-graph を進めて"),
        _assistant("2026-11-14T02:00:01Z", "m1", [_use("s1", "Skill", skill="dev-graph:run-dev-graph-node")]),
        _assistant("2026-11-14T02:00:09Z", "m2", [{"type": "text", "text": "node DONE"}]),
    ]
    out = tmp_path / "m.json"
    rc = MOD.main([str(_write(tmp_path, events)), "--start-skill", "run-dev-graph-node$",
                   "--end-marker", "DONE", "--out", str(out)])
    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8"))["wall_seconds"] == 9.0


def _sub(msg_id, usage, extra=None):
    event = {"type": "assistant", "isSidechain": True, "timestamp": "2026-11-14T00:00:00Z",
             "message": {"id": msg_id, "role": "assistant", "content": [], "usage": usage}}
    if extra is not None:
        event = [event, {"type": "user", "isSidechain": True, "toolUseResult": extra,
                         "message": {"role": "user", "content": []}}]
    return event


def test_subagent_usage_is_summed_from_their_transcripts(tmp_path, capsys):
    """totalTokens は最後の呼び出しの context の大きさ。累計は subagent の transcript から足す。
    fork された Skill と、subagent がさらに起動した subagent も数える。"""
    events = [
        _user("2026-11-14T00:00:00Z", "skill を作って"),
        _assistant("2026-11-14T00:00:01Z", "m1", [
            _use("s1", "Skill", skill="harness-creator:run-skill-create"),
            _use("a1", "Agent", description="sync", prompt="p"),
            _use("f1", "Skill", skill="harness-creator:assign-plugin-package-evaluator"),
            _use("a2", "Agent", description="gone", prompt="p"),
        ]),
        _result("2026-11-14T00:00:02Z", "a1", extra={"status": "completed", "agentId": "aaa", "totalTokens": 50}),
        _result("2026-11-14T00:00:03Z", "f1", extra={"success": True, "status": "forked", "agentId": "fff"}),
        _result("2026-11-14T00:00:04Z", "a2", extra={"status": "completed", "agentId": "zzz", "totalTokens": 9}),
        _assistant("2026-11-14T00:00:05Z", "m2", [{"type": "text", "text": REPORT}]),
    ]
    subs = tmp_path / "t" / "subagents"
    subs.mkdir(parents=True)
    rows = {
        # 同じ message.id の 2 entry は 1 回だけ。aaa は ccc を起動した
        "aaa": [_sub("x1", {"input_tokens": 1, "cache_read_input_tokens": 100}),
                _sub("x1", {"input_tokens": 1, "cache_read_input_tokens": 100}),
                *_sub("x2", {"input_tokens": 2, "cache_read_input_tokens": 200}, extra={"agentId": "ccc"})],
        "ccc": [_sub("y1", {"output_tokens": 7})],
        "fff": [_sub("z1", {"input_tokens": 3, "cache_creation_input_tokens": 30})],
    }
    for agent_id, lines in rows.items():
        (subs / f"agent-{agent_id}.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    rc, report, _ = _run(tmp_path, capsys, events)
    assert rc == 0
    assert report["subagents_dir"] == str(subs)
    assert report["agents"] == {
        "launched": 2, "forked_skills": 1,
        "transcripts": {"found": 3, "missing": 1, "nested": 1},
        "usage": {"cache_creation_input_tokens": 30, "cache_read_input_tokens": 300,
                  "input_tokens": 6, "output_tokens": 7},
        "final_context_tokens": 59, "final_context_unknown": 0}


def test_nested_subagent_found_only_by_meta_parent(tmp_path, capsys):
    """親の transcript に子の toolUseResult が残らなくても、meta の parentAgentId で辿る。
    壊れた meta は飛ばし、関係の無い agent (別の親) は数えない。"""
    events = [
        _user("2026-11-14T00:00:00Z", "skill を作って"),
        _assistant("2026-11-14T00:00:01Z", "m1", [
            _use("s1", "Skill", skill="harness-creator:run-skill-create"),
            _use("a1", "Agent", description="review", prompt="p"),
        ]),
        _result("2026-11-14T00:00:02Z", "a1", extra={"status": "completed", "agentId": "ppp", "totalTokens": 5}),
        _assistant("2026-11-14T00:00:05Z", "m2", [{"type": "text", "text": REPORT}]),
    ]
    subs = tmp_path / "t" / "subagents"
    subs.mkdir(parents=True)
    rows = {"ppp": [_sub("p1", {"output_tokens": 1})],
            "kid": [_sub("k1", {"output_tokens": 10})],
            "other": [_sub("o1", {"output_tokens": 100})]}
    for agent_id, lines in rows.items():
        (subs / f"agent-{agent_id}.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
    (subs / "agent-kid.meta.json").write_text(json.dumps({"parentAgentId": "ppp", "spawnDepth": 2}), encoding="utf-8")
    (subs / "agent-other.meta.json").write_text(json.dumps({"parentAgentId": "elsewhere"}), encoding="utf-8")
    (subs / "agent-broken.meta.json").write_text("{not json", encoding="utf-8")
    rc, report, _ = _run(tmp_path, capsys, events)
    assert rc == 0
    assert report["agents"]["transcripts"] == {"found": 2, "missing": 0, "nested": 1}
    assert report["agents"]["usage"] == {"output_tokens": 11}


@pytest.mark.parametrize("command, expected", [
    ("python3 validate-a.py && python3 -I scripts/validate-a.py; ./x/lint-b.py", ["validate-a", "validate-a", "lint-b"]),
    ("( cd sub && FOO=1 python3 ../check-c.py --x )", ["check-c"]),
    ("for f in a b; do python3 lint-d.py $f; done", ["lint-d"]),
    ("uv run --script lint-e.py", ["lint-e"]),
    # 名前が出ただけのものは数えない
    ("grep -n validate-a.py notes.md", []),
    ("cat plugins/x/scripts/lint-b.py | head", []),
    ("echo 'python3 validate-a.py'", []),
    ('python3 -c "import runpy; runpy.run_path(\'validate-a.py\')"', []),
    ("git diff -- scripts/check-c.py", []),
    # heredoc の本文は shell の文ではない (閉じていない quote があっても止まらない)
    ("python3 - <<'EOF'\n# don't\nsubprocess.run(['python3', 'validate-a.py'])\nEOF\npython3 lint-b.py", ["lint-b"]),
])
def test_checkers_count_invocations_not_mentions(command, expected):
    assert MOD.invoked_checkers(command) == expected


def test_run_without_end_marker_is_not_merged_into_the_next(tmp_path, capsys):
    first = [e for e in _transcript() if "gates_passed" not in json.dumps(e)]
    rc, report, err = _run(tmp_path, capsys, first + _transcript()[2:])
    assert rc == 2 and report is None
    assert "同じ skill (capability-build) の次の起動" in err


def test_line_separator_inside_json_does_not_split_lines(tmp_path, capsys):
    events = _transcript()
    events[1]["message"]["content"][0]["text"] = "了 解\x85"
    rc, report, _ = _run(tmp_path, capsys, events)
    assert rc == 0 and report["runs_found"] == 1


def test_malformed_inputs_exit_2_without_traceback(tmp_path, capsys):
    events = _transcript() + [{"type": "assistant", "timestamp": "2026-11-14T00:12:00Z", "message": ["x"]}]
    rc, report, _ = _run(tmp_path, capsys, events)
    assert rc == 0
    assert _run(tmp_path, capsys, _transcript(), "--start-skill", "(")[0] == 2
    assert _run(tmp_path, capsys, _transcript(), "--out", str(tmp_path))[0] == 2
    assert _run(tmp_path, capsys, _transcript(), "--subagents-dir", str(tmp_path / "none"))[0] == 2
