"""Inline Python の graph authority 書込みを検出する C10 guard module。

HarnessHub-f84o では、変数代入や ``Path`` 結合によって保護 path の字面を分断した
inline Python が旧来の正規表現判定を迂回できた。ここでは ``-c`` / heredoc の本文を
AST で解析し、副作用のない定数伝播で書込み対象を復元する。

分岐・ループ・関数境界を跨ぐ伝播、``exec`` / ``eval``、任意の文字列変換は意図的に
実行しない。評価不能な path は ``UNRESOLVED`` を含む候補として保持し、
``.dev-graph/`` prefix または authority 固有の末尾が確定していれば安全側で遮断する。
"""
from __future__ import annotations

import ast
import re
import shlex
import sys
import textwrap
from pathlib import PurePosixPath

sys.dont_write_bytecode = True

from guard_graph_commands import GRAPH_AUTHORITY_PATH
from guard_python_path_eval import (
    UNRESOLVED,
    _MAX_DEPTH,
    _PathEvaluator,
    _argument,
    _dotted,
    _open_mode_is_write,
    _os_open_flags_are_write,
    _unwrap_getattr,
)

_PYTHON_INTERPRETER = re.compile(r"^(?:python|python\d(?:\.\d+)?|py)$", re.I)
_SHELL_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", re.S)
_COMMAND_SEPARATORS = frozenset({";", "&&", "||", "|", "&", "("})
_HEREDOC = re.compile(
    r"<<-?\s*(?P<quote>['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)[^\n]*\n"
    r"(?P<body>.*?)\n[ \t]*(?P=tag)(?=[^A-Za-z0-9_]|$)",
    re.S,
)
_NESTED_SHELL_PREFIX = re.compile(
    r"(?:^|[;&|]\s*)(?:[^\s;&|'\"]*/)?(?:ba|da|z)?sh\s+-c\s+['\"](?P<inner>.*)$",
    re.I,
)
_OPEN_FUNCTIONS = frozenset({"open", "io.open", "codecs.open"})
_DESTINATION_ONLY_FUNCTIONS = frozenset(
    {
    "shutil.copy",
    "shutil.copyfile",
    "shutil.copy2",
    "shutil.copytree",
    "shutil.copymode",
    "shutil.copystat",
    }
)
_SOURCE_AND_DESTINATION_FUNCTIONS = frozenset(
    {"shutil.move", "os.replace", "os.rename"}
)
_FIRST_ARGUMENT_FUNCTIONS = frozenset(
    {"os.remove", "os.unlink", "os.truncate", "os.rmdir", "os.removedirs"}
)
# 組込み open と衝突するため、完全名だけを受理する。
_OS_OPEN_FUNCTIONS = frozenset({"os.open"})
_PATH_WRITE_METHODS = frozenset({"write_text", "write_bytes", "touch", "unlink", "rmdir"})
_PATH_RELOCATE_METHODS = frozenset({"replace", "rename"})


class _WriteTargetCollector(ast.NodeVisitor):
    """書込み API の呼出しから、変更されうる path の評価結果を集める。"""

    def __init__(self) -> None:
        self.evaluator = _PathEvaluator()
        self.targets: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        self.evaluator.bind_import(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        self.evaluator.bind_import(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        self.generic_visit(node)
        self.evaluator.bind(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        self.generic_visit(node)
        self.evaluator.bind(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        self.generic_visit(node)
        self.evaluator.bind(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self.generic_visit(node)
        function = _unwrap_getattr(node.func, self.evaluator)
        qualified = self.evaluator.resolve(_dotted(function))
        if qualified in _OPEN_FUNCTIONS:
            self._record_open(node)
            return
        if qualified in _OS_OPEN_FUNCTIONS:
            if _os_open_flags_are_write(_argument(node, 1, "flags")):
                self._record(_argument(node, 0, "path"))
            return
        if qualified in _DESTINATION_ONLY_FUNCTIONS:
            self._record(_argument(node, 1, "dst", "destination"))
            return
        if qualified in _SOURCE_AND_DESTINATION_FUNCTIONS:
            # rename/move は宛先だけでなく、元 path の削除・置換も行う。
            self._record(_argument(node, 0, "src", "source"))
            self._record(_argument(node, 1, "dst", "destination"))
            return
        if qualified in _FIRST_ARGUMENT_FUNCTIONS:
            self._record(_argument(node, 0, "path"))
            return
        if not isinstance(function, ast.Attribute):
            return
        if function.attr in _PATH_WRITE_METHODS:
            self._record(function.value)
            return
        if function.attr in _PATH_RELOCATE_METHODS:
            self._record(function.value)
            self._record(_argument(node, 0, "target"))
            return
        if function.attr == "open":
            mode = _argument(node, 0, "mode")
            if mode is not None and _open_mode_is_write(self.evaluator.evaluate(mode)):
                self._record(function.value)

    def _record_open(self, node: ast.Call) -> None:
        mode = _argument(node, 1, "mode")
        if mode is None or not _open_mode_is_write(self.evaluator.evaluate(mode)):
            return
        self._record(_argument(node, 0, "file", "path"))

    def _record(self, node: ast.AST | None) -> None:
        if node is not None:
            self.targets.append(self.evaluator.evaluate(node))


_AUTHORITY_MARKER = re.compile(r"(?:^|/)\.dev-graph/", re.I)
_AUTHORITY_MEMBERS = ("state", "config.json")
_DYNAMIC_ROOT_AUTHORITY = re.compile(
    r"(?:^|/)state/graph\.json$|graph-node\.schema\.json$", re.I
)


def _may_target_authority(path: str) -> bool:
    """評価済み path が graph authority を指しうるかを返す。"""
    if UNRESOLVED not in path:
        return bool(GRAPH_AUTHORITY_PATH.search(path))
    head, _, tail = path.partition(UNRESOLVED)
    if GRAPH_AUTHORITY_PATH.search(head) or GRAPH_AUTHORITY_PATH.search(tail):
        return True
    marker = _AUTHORITY_MARKER.search(head)
    if marker is not None:
        remainder = head[marker.end():]
        segment = remainder.split("/", 1)[0].lower()
        if "/" in remainder:
            return segment in _AUTHORITY_MEMBERS
        return any(member.startswith(segment) for member in _AUTHORITY_MEMBERS)
    return bool(_DYNAMIC_ROOT_AUTHORITY.search(tail))


def _heredoc_bodies(command: str) -> list[str]:
    bodies: list[str] = []
    for match in _HEREDOC.finditer(command):
        line_start = command.rfind("\n", 0, match.start()) + 1
        prefix = command[line_start:match.start()]
        if _python_reads_stdin(prefix):
            bodies.append(match.group("body"))
    return bodies


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _is_command_position(tokens: list[str], index: int) -> bool:
    """interpreter token が command 名の位置にあるかを保守的に判定する。"""
    start = index
    while start and tokens[start - 1] not in _COMMAND_SEPARATORS:
        start -= 1
    prefix = tokens[start:index]
    if not prefix or all(_SHELL_ASSIGNMENT.match(token) for token in prefix):
        return True
    if PurePosixPath(prefix[0]).name != "env":
        return False
    return all(token.startswith("-") or _SHELL_ASSIGNMENT.match(token) for token in prefix[1:])


def _python_reads_stdin(prefix: str) -> bool:
    """heredoc の受け手が command 位置の Python であるか判定する。"""
    try:
        tokens = _shell_tokens(prefix)
    except ValueError:
        nested = _NESTED_SHELL_PREFIX.search(prefix)
        return bool(nested and _python_reads_stdin(nested.group("inner")))
    for index, token in enumerate(tokens):
        if (
            _PYTHON_INTERPRETER.match(PurePosixPath(token).name) is None
            or not _is_command_position(tokens, index)
        ):
            continue
        cursor = index + 1
        while cursor < len(tokens):
            option = tokens[cursor]
            if option in _COMMAND_SEPARATORS:
                break
            if option in {"-X", "-W"}:
                cursor += 2
                continue
            if option == "--":
                cursor += 1
                continue
            if option.startswith("-"):
                cursor += 1
                continue
            break
        if cursor == len(tokens):
            return True
    return False


def _dash_c_sources(command: str) -> list[str]:
    """``python -c <source>`` の source を取り出す。"""
    try:
        tokens = _shell_tokens(command)
    except ValueError:
        return []
    sources: list[str] = []
    index = 0
    while index < len(tokens):
        if (
            _PYTHON_INTERPRETER.match(PurePosixPath(tokens[index]).name) is None
            or not _is_command_position(tokens, index)
        ):
            index += 1
            continue
        cursor = index + 1
        while cursor < len(tokens):
            token = tokens[cursor]
            if token in {"-c", "--command"} and cursor + 1 < len(tokens):
                sources.append(tokens[cursor + 1])
                cursor += 2
                break
            if token in {"-X", "-W"}:
                cursor += 2
                continue
            if token == "--" or not token.startswith("-"):
                break
            cursor += 1
        index = max(cursor, index + 1)
    return sources


def python_sources(command: str) -> list[str]:
    """command 内の inline Python 本文を返す。"""
    sources = _heredoc_bodies(command)
    sources.extend(_dash_c_sources(_HEREDOC.sub(" ", command)))
    return sources


def inline_python_writes_graph_authority(command: str) -> bool:
    """inline Python が graph authority を書き換えうるかを AST で判定する。"""
    for source in python_sources(command):
        try:
            tree = ast.parse(textwrap.dedent(source))
        except (SyntaxError, ValueError, RecursionError):
            continue
        collector = _WriteTargetCollector()
        try:
            collector.visit(tree)
        except RecursionError:
            return True
        if any(_may_target_authority(target) for target in collector.targets):
            return True
    return False
