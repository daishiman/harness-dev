"""共有 harness (plugin の実体) に bytecode cache を書かないことを確かめる。

plugin は、利用者の環境では読取り専用の共有 harness として使われる。script や hook が plugin の module
(`_common` ほか) を import すると、Python は「読み込まれた側」の dir の `__pycache__` に `.pyc` を書く。
これを2段で確かめる。

- 静的: sibling を import する script は、それより前に `sys.dont_write_bytecode = True` を置く。
  `sys.executable` で起こす子と、利用者に示す修復手順の argv (`"python3"` で始まる list) は `-B` を渡す。
  `hooks.json` のコマンドは `python3 -B` で起動する。
- 動的: `PYTHONDONTWRITEBYTECODE` に頼らず、写した plugin で全 script と全 hook を起動しても、
  `__pycache__` が1つもできない。
"""
from __future__ import annotations

import ast
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
ENTRY_GLOBS = ("scripts/*.py", "hooks/*.py", "skills/*/scripts/*.py")
IMPORTERS = ("spec_from_file_location", "import_module", "run_path")


def entry_files(root: Path) -> list[Path]:
    return sorted(path for pattern in ENTRY_GLOBS for path in root.glob(pattern))


def sibling_import_lines(tree: ast.Module, local: set[str]) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in local:
            lines.append(node.lineno)
        elif isinstance(node, ast.Import) and any(alias.name in local for alias in node.names):
            lines.append(node.lineno)
        elif isinstance(node, ast.Call) and ast.unparse(node.func).endswith(IMPORTERS):
            lines.append(node.lineno)
    return lines


def flag_line(tree: ast.Module) -> int | None:
    """module の top level にある `sys.dont_write_bytecode = True` の行。関数の中の代入は数えない。"""
    for node in tree.body:
        if (isinstance(node, ast.Assign) and [ast.unparse(t) for t in node.targets] == ["sys.dont_write_bytecode"]
                and isinstance(node.value, ast.Constant) and node.value.value is True):
            return node.lineno
    return None


def test_every_sibling_import_comes_after_the_bytecode_flag() -> None:
    files = entry_files(PLUGIN)
    local = {path.stem for path in files}
    checked, problems = 0, []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = sibling_import_lines(tree, local)
        if not imports:
            continue
        checked += 1
        flag = flag_line(tree)
        if flag is None or flag > min(imports):
            problems.append(f"{path.relative_to(PLUGIN)}: flag={flag} first_sibling_import={min(imports)}")
    assert checked >= 15, checked  # 検査が空回りしていない
    assert problems == []


def starts_python(node: ast.AST) -> bool:
    """子として起こす argv (`sys.executable` で始まる) と、利用者が実行する修復手順の argv (`"python3"` で始まる)。"""
    if not (isinstance(node, (ast.List, ast.Tuple)) and node.elts):
        return False
    first = node.elts[0]
    return ast.unparse(first) == "sys.executable" or (isinstance(first, ast.Constant) and first.value == "python3")


def test_every_python_child_is_started_with_minus_b() -> None:
    checked, problems = 0, []
    for path in entry_files(PLUGIN):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if starts_python(node):
                checked += 1
                second = node.elts[1] if len(node.elts) > 1 else None
                if not (isinstance(second, ast.Constant) and second.value == "-B"):
                    problems.append(f"{path.relative_to(PLUGIN)}:{node.lineno}")
    assert checked >= 20, checked
    assert problems == []


def hook_commands(root: Path) -> list[str]:
    config = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    return [hook["command"] for groups in config["hooks"].values() for group in groups for hook in group["hooks"]]


def test_every_hook_command_starts_python_with_minus_b() -> None:
    commands = hook_commands(PLUGIN)
    assert len(commands) == 5
    assert [command for command in commands if not command.startswith("python3 -B ")] == []


def bytecode_entries(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc")


def test_running_every_script_and_hook_leaves_no_bytecode_in_the_harness(tmp_path: Path) -> None:
    harness = tmp_path / "harness"
    shutil.copytree(PLUGIN, harness, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))
    # 呼出し側の環境に頼らない: script 自身の止め方だけで書かないことを見る。
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}

    started = 0
    for script in entry_files(harness):
        if "ArgumentParser" not in script.read_text(encoding="utf-8"):
            continue  # 引数を解かない script は --help で止まらないので起動しない (sibling の import も無い)
        subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=60, check=False)
        started += 1
    assert started >= 20, started

    # 所有の marker だけを持つ、git でない dir。reconcile hook は resolver を子として起こし、resolver は
    # `_common` を import してから git の検査で止まる (外部への送信や lease の操作には進まない)。
    # guard は lib/ の判定 module を import し、subprocess を起こさずに `bd close` を止める。
    # audit は lib/graph_envelope を import し、初回の基準化だけをして通す (保護外の tmp/ に台帳を書く)。
    repo = tmp_path / "repo"
    (repo / ".dev-graph").mkdir(parents=True)
    (repo / ".dev-graph" / "config.json").write_text("{}\n", encoding="utf-8")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "bd close dg-1"}})
    expected = {"audit-graph-authority-drift.py": 0}
    for command in hook_commands(harness):
        argv = shlex.split(command.replace("${CLAUDE_PLUGIN_ROOT}", str(harness)).replace("${CLAUDE_PROJECT_DIR}", str(repo)))
        # 外側の -B にも頼らない (hooks.json の形は上の静的な test が見る): hook が子に渡す -B と、
        # 子 script 自身の止め方だけを見る。
        script_argv = [arg for arg in argv[1:] if arg != "-B"]
        proc = subprocess.run([sys.executable, *script_argv], cwd=tmp_path, env=env, input=payload,
                              capture_output=True, text=True, timeout=60, check=False)
        assert proc.returncode == expected.get(Path(script_argv[0]).name, 2), (argv, proc.stdout, proc.stderr)

    assert bytecode_entries(harness) == []
