"""Inline Python guard の性能・意図的な境界・path 評価規則を固定する。"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"
LIB = PLUGIN / "lib"
HOOK = HOOKS / "guard-graph-schema.py"
REPO_ROOT = PLUGIN.parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return load(HOOK, "guard_inline_python_boundaries")


@pytest.fixture(scope="module")
def evaluator():
    return load(LIB / "guard_python_writes.py", "guard_python_writes_unit")


def heredoc(body: str) -> str:
    return f"python3 - <<'PY'\n{body}\nPY"


def test_large_inline_python_stays_far_from_the_hook_time_limit(guard):
    """2000 行の入力でも AST 判定が hook timeout から十分離れている。"""
    noise = "\n".join(
        f"value_{index} = base_{index % 7} / 'segment-{index}' / 'file-{index}.json'"
        for index in range(2000)
    )
    benign = heredoc(f"from pathlib import Path\n{noise}")
    hidden = heredoc(
        f"from pathlib import Path\n{noise}\n"
        "target = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "target.write_text('{}')"
    )

    started = time.perf_counter()
    assert guard.interpreter_writes_graph_authority(benign) is False
    assert guard.interpreter_writes_graph_authority(hidden) is True
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"静的遮断が {elapsed:.2f}s を要した (hook timeout の窓になる)"


def test_hook_effective_denial_path_stays_within_the_time_contract(guard):
    """``static_denial`` 全体も hook timeout から十分離れている。"""
    noise = "\n".join(
        f"value_{index} = base_{index % 7} / 'segment-{index}' / 'file-{index}.json'"
        for index in range(500)
    )
    hidden = heredoc(
        f"from pathlib import Path\n{noise}\n"
        "target = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "target.write_text('{}')"
    )

    started = time.perf_counter()
    assert guard.static_denial(hidden, [], REPO_ROOT) is not None
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"実効遮断経路が {elapsed:.2f}s を要した (hook timeout の窓になる)"


def test_variable_path_write_is_denied_in_a_real_process(tmp_path):
    """live-trial と同じ実プロセス起動で exit 2 になる。

    guard は所有 marker を持つ repo でだけ判定するため、marker を置いた fixture を --repo-root に渡す。
    """
    marker = tmp_path / ".dev-graph" / "config.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}\n", encoding="utf-8")
    command = heredoc(
        "from pathlib import Path\n"
        "root = Path('.dev-graph')\n"
        "target = root / 'state' / 'graph.json'\n"
        "target.write_text('{}')"
    )
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, "-B", str(HOOK), "--repo-root", str(tmp_path)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, f"遮断されていない: {proc.stderr}"
    assert "C02 atomic writer" in proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "python3 tools/writer.py",
        "python3 tools/writer.py .dev-graph/state/graph.json",
        "bash tools/writer.sh",
        "./scripts/regen-graph.sh",
    ],
)
def test_script_file_indirection_stays_outside_the_pretooluse_range(guard, command):
    """任意 script の読込みは遮断時間を入力 file に依存させるため C10 範囲外。"""
    assert guard.static_denial(command, [], REPO_ROOT) is None, command


def test_constant_propagation_gives_up_past_the_depth_limit(guard, evaluator):
    """深さ上限で root が未解決でも graph store の確定末尾は fail-closed にする。"""
    limit = evaluator._MAX_DEPTH

    def wrapped(depth: int, *tail: str) -> str:
        expression = "'.dev-graph'"
        for _ in range(depth):
            expression = f"str({expression})"
        arguments = ", ".join([expression, *(repr(part) for part in tail)])
        return heredoc(f"import os\np = os.path.join({arguments})\nopen(p, 'w')")

    assert guard.interpreter_writes_graph_authority(wrapped(1, "state", "graph.json"))
    assert guard.interpreter_writes_graph_authority(wrapped(1, "config.json"))
    assert guard.interpreter_writes_graph_authority(
        wrapped(limit * 2, "state", "graph.json")
    ) is True
    # 未解決 root の config.json は tmp draft の可能性があるため巻き込まない。
    assert guard.interpreter_writes_graph_authority(
        wrapped(limit * 2, "config.json")
    ) is False


@pytest.mark.parametrize(
    "command",
    [
        heredoc(
            "exec(\"import pathlib\\n\"\n"
            "     \"p = pathlib.Path('.dev-graph') / 'state' / 'graph.json'\\n\"\n"
            "     \"p.write_text('{}')\")"
        ),
        heredoc(
            "root = '.dev-graph'\n"
            "exec(\"open(root + '/state/graph.json', 'w')\", {'root': root})"
        ),
        heredoc("p = '.dev-graphXX/state/graph.json'.replace('XX', '')\nopen(p, 'w')"),
        heredoc("raw = '.dev-graph/state/graph.jsonEXTRA'\np = raw[:-5]\nopen(p, 'w')"),
    ],
)
def test_obfuscated_paths_remain_the_documented_gap(guard, command):
    """exec/eval や任意の文字列変換は、性能境界を守るため意図的に再実行しない。

    これは安全性を保証する PASS ではなく、実装と contract 文書で同じ既知の限界を
    明示する同期テストである。塞いだ場合は MUST_BLOCK へ移し、文書も更新する。
    """
    assert guard.static_denial(command, [], REPO_ROOT) is None, command


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("p = '.dev-graph' / 'state'", ".dev-graph/state"),
        (
            "p = Path('.dev-graph') / 'state' / 'graph.json'",
            ".dev-graph/state/graph.json",
        ),
        ("p = os.path.join('a', 'b')", "a/b"),
        ("p = Path('/abs') / '/other'", "/other"),
        ("p = 'a' + '/b'", "a/b"),
        ("root = 'a'\np = f'{root}/b'", "a/b"),
        (
            "p = (Path('.dev-graph') / 'state' / 'draft').parent / 'graph.json'",
            ".dev-graph/state/graph.json",
        ),
    ],
)
def test_path_expressions_are_evaluated_by_constant_propagation(
    evaluator, source, expected
):
    import ast

    collector = evaluator._WriteTargetCollector()
    collector.visit(ast.parse(source))
    assert collector.evaluator.env.get("p") == expected


@pytest.mark.parametrize(
    ("path", "blocked"),
    [
        (".dev-graph/state/graph.json", True),
        (".dev-graph/config.json", True),
        ("schemas/graph-node.schema.json", True),
        (".dev-graph/tmp/draft.json", False),
        (".dev-graph/cache/pretty.json", False),
        (".dev-graph/\x00", True),
        (".dev-graph/\x00/graph.json", True),
        (".dev-graph/sta\x00", True),
        (".dev-graph/tmp/\x00", False),
        (".dev-graph/cache/\x00.json", False),
        ("\x00/state/graph.json", True),
        ("\x00/config.json", False),
        ("\x00/docs/note.md", False),
    ],
)
def test_unresolved_paths_fall_to_the_closed_side_only_inside_the_authority(
    evaluator, path, blocked
):
    assert evaluator._may_target_authority(path) is blocked, path


@pytest.mark.parametrize(
    ("command", "count"),
    [
        ("python3 -c 'print(1)'", 1),
        ("python3 -X utf8 -c 'print(1)'", 1),
        ("python3 -W ignore -c 'print(1)'", 1),
        ("python3 - <<'PY'\nprint(1)\nPY", 1),
        ("MODE=dev python3 - <<'PY'\nprint(1)\nPY", 1),
        ("env MODE=dev python3 -X utf8 - <<'PY'\nprint(1)\nPY", 1),
        ("python3 script.py <<'PY'\nprint(1)\nPY", 0),
        ("python3 -c 'print(1)' && python3 -c 'print(2)'", 2),
        ("MODE=dev python3 -c 'print(1)'", 1),
        ("env MODE=dev python3 -c 'print(1)'", 1),
        ("grep -c open file.py", 0),
        ("echo python3 -c 'print(1)'", 0),
        ("cat <<'PY'\nprint(1)\nPY", 0),
        ("echo hi", 0),
    ],
)
def test_inline_python_sources_are_extracted_per_invocation(evaluator, command, count):
    assert len(evaluator.python_sources(command)) == count


def test_malformed_python_is_delegated_to_the_literal_layer(guard):
    command = heredoc(
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text('{}')  # .dev-graph/state/graph.json\n"
        "if True  # syntax error"
    )
    assert guard.inline_python_writes_graph_authority(command) is False
    assert guard.interpreter_writes_graph_authority(command) is True
