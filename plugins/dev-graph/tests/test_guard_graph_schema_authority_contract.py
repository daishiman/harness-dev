from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest


PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"


@pytest.fixture(autouse=True)
def managed_repository(tmp_path):
    """guard は所有 marker (`.dev-graph/config.json`) を持つ repo でだけ判定する。

    marker の無い repo では最初に no-op で抜けるため、各 test の --repo-root (tmp_path) に marker を置く。
    """
    marker = tmp_path / ".dev-graph" / "config.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}\n", encoding="utf-8")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def call_main(module, monkeypatch, capsys, *args, stdin=None):
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, args)])
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stdin)))
    code = module.main()
    captured = capsys.readouterr()
    return code, captured


def test_c10_blocks_graph_authority_writes_through_the_write_tool(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = load(HOOKS / "guard-graph-schema.py", "guard_write_tool_contract")
    monkeypatch.setattr(mod, "context_ok", lambda _root: (True, "{}"))

    for tool, payload in (
        (
            "Write",
            {
                "file_path": f"{tmp_path}/.dev-graph/state/graph.json",
                "content": "{}",
            },
        ),
        (
            "Write",
            {
                "file_path": f"{tmp_path}/.dev-graph/config.json",
                "content": "{}",
            },
        ),
        (
            "Edit",
            {
                "file_path": f"{tmp_path}/.dev-graph/state/graph.json",
                "old_string": "a",
                "new_string": "b",
            },
        ),
    ):
        code, captured = call_main(
            mod,
            monkeypatch,
            capsys,
            "--repo-root",
            tmp_path,
            stdin={"tool_name": tool, "tool_input": payload},
        )
        assert code == 2, f"{tool} {payload['file_path']} must be blocked"
        assert "C02" in captured.err

    code, _ = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={
            "tool_name": "Write",
            "tool_input": {
                "file_path": f"{tmp_path}/README.md",
                "content": "x",
            },
        },
    )
    assert code == 0


def test_c10_blocks_interpreter_writes_to_the_graph_authority(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = load(
        HOOKS / "guard-graph-schema.py",
        "guard_interpreter_write_contract",
    )
    monkeypatch.setattr(mod, "context_ok", lambda _root: (True, "{}"))

    blocked = [
        """python3 -c "import json; json.dump({}, open('.dev-graph/state/graph.json','w'))" """,
        """python3 - <<'PY'\nopen('.dev-graph/state/graph.json', 'w').write('{}')\nPY""",
        (
            """python3 -c "from pathlib import Path; """
            """Path('.dev-graph/state/graph.json').write_text('{}')" """
        ),
        (
            """python3 - <<'PY'\nfrom pathlib import Path\n"""
            """target = Path('.dev-graph/config.json')\n"""
            """target.write_bytes(b'{}')\nPY"""
        ),
    ]
    for command in blocked:
        code, captured = call_main(
            mod,
            monkeypatch,
            capsys,
            "--repo-root",
            tmp_path,
            stdin={
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
        )
        assert code == 2, f"must block: {command[:60]}"
        assert "C02" in captured.err

    code, _ = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    """python3 -c "import json; """
                    """print(json.load(open('.dev-graph/state/graph.json')))" """
                )
            },
        },
    )
    assert code == 0

    code, _ = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    """python3 -c "from pathlib import Path; """
                    """print(Path('.dev-graph/state/graph.json').read_text())" """
                )
            },
        },
    )
    assert code == 0


def test_c10_guard_is_registered_for_file_writing_tools() -> None:
    hooks = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in hooks["hooks"]["PreToolUse"]
        if any(
            "guard-graph-schema.py" in hook.get("command", "")
            for hook in entry.get("hooks", [])
        )
    ]
    assert entries, "guard-graph-schema.py must be registered on PreToolUse"
    matcher = entries[0]["matcher"]
    for tool in ("Bash", "Write", "Edit"):
        assert re.search(matcher, tool), f"{tool} must match {matcher!r}"


def test_c10_bash_redirect_covers_the_whole_graph_authority_dir(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = load(HOOKS / "guard-graph-schema.py", "guard_authority_dir_contract")
    monkeypatch.setattr(mod, "context_ok", lambda _root: (True, "{}"))

    for command in (
        "cat > /repo/.dev-graph/config.json <<'EOF'\n{}\nEOF",
        "printf '{}' > /repo/.dev-graph/config.json",
        "cp /tmp/x.json /repo/.dev-graph/config.json",
        "rm -f /repo/.dev-graph/state/graph.json",
    ):
        code, _ = call_main(
            mod,
            monkeypatch,
            capsys,
            "--repo-root",
            tmp_path,
            stdin={
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
        )
        assert code == 2, f"must block: {command[:50]}"

    code, _ = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={
            "tool_name": "Bash",
            "tool_input": {"command": "cat /repo/.dev-graph/config.json"},
        },
    )
    assert code == 0


def test_c10_graph_authority_block_does_not_depend_on_context_subprocess(
    tmp_path,
    monkeypatch,
    capsys,
):
    mod = load(
        HOOKS / "guard-graph-schema.py",
        "guard_authority_precedence_contract",
    )

    def must_not_run(_root):
        raise AssertionError("context_ok must not gate the graph authority check")

    monkeypatch.setattr(mod, "context_ok", must_not_run)
    code, captured = call_main(
        mod,
        monkeypatch,
        capsys,
        "--repo-root",
        tmp_path,
        stdin={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/repo/.dev-graph/state/graph.json",
                "content": "{}",
            },
        },
    )
    assert code == 2
    assert "C02" in captured.err
