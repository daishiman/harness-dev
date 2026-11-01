"""Inline Python の path 式を副作用なしで評価する C10 guard support module。

実行時の Python を起動せず、AST と定数伝播だけで path を組み立てる。評価不能な
部分式には ``UNRESOLVED`` を残し、呼び出し側が graph authority への到達可能性を
安全側で判定できるようにする。
"""
from __future__ import annotations

import ast

# shell command にも Python source にも通常現れない制御文字を使う。
UNRESOLVED = "\x00"

# 深い式による RecursionError が hook の fail-open を招かないように上限を設ける。
_MAX_DEPTH = 40


def _names(*qualified: str) -> frozenset[str]:
    """完全名と import 別名解決後の末尾名を受理する集合を作る。"""
    return frozenset(qualified) | {name.rsplit(".", 1)[-1] for name in qualified}


_PATH_CONSTRUCTORS = _names(
    "pathlib.Path", "pathlib.PurePath", "pathlib.PurePosixPath", "pathlib.PosixPath"
)
_JOIN_FUNCTIONS = frozenset({"os.path.join", "posixpath.join"})
_PATH_IDENTITY_METHODS = frozenset(
    {"resolve", "absolute", "expanduser", "as_posix", "__fspath__"}
)
_PATH_TAIL_METHODS = frozenset({"with_name", "with_suffix"})
_PATH_CONSTANTS = {
    "os.sep": "/",
    "os.path.sep": "/",
    "posixpath.sep": "/",
    "os.altsep": "/",
    "os.extsep": ".",
    "os.curdir": ".",
}
_PATH_IDENTITY_FUNCTIONS = (
    frozenset(
        {
            f"{module}.{function}"
            for module in ("os.path", "posixpath")
            for function in (
                "abspath",
                "normpath",
                "realpath",
                "expanduser",
                "expandvars",
            )
        }
    )
    | _names("os.fspath")
    | {"str"}
)


def _open_mode_is_write(mode: str) -> bool:
    """open() の mode が書込み能力を含むかを返す。未解決なら安全側で True。"""
    if UNRESOLVED in mode:
        return True
    mode = mode.lower()
    if not mode:
        return False
    return bool(set(mode) & {"w", "a", "x"}) or "+" in mode


def _dotted(node: ast.AST | None) -> str | None:
    """``os.path.join`` のような属性チェーンをドット名へ畳む。"""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _collect_flag_names(node: ast.AST, into: set[str]) -> bool:
    """``os.O_WRONLY | os.O_CREAT`` からフラグ名を集める。"""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.BitAnd)):
        left = _collect_flag_names(node.left, into)
        return _collect_flag_names(node.right, into) and left
    dotted = _dotted(node)
    if dotted is None:
        return False
    into.add(dotted.rsplit(".", 1)[-1])
    return True


def _os_open_flags_are_write(node: ast.AST | None) -> bool:
    """``os.open(path, flags)`` が書込み能力を含むかを返す。"""
    if node is None:
        return False
    names: set[str] = set()
    if not _collect_flag_names(node, names):
        return True
    return bool(names & {"O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"})


def _join(left: str, right: str) -> str:
    """``Path`` の ``/`` と ``os.path.join`` に共通する結合規則。"""
    if not left:
        return right
    if not right:
        return left
    if right.startswith("/"):
        return right
    return left.rstrip("/") + "/" + right


def _argument(call: ast.Call, index: int, *names: str) -> ast.AST | None:
    if index < len(call.args):
        argument = call.args[index]
        return None if isinstance(argument, ast.Starred) else argument
    for keyword in call.keywords:
        if keyword.arg and keyword.arg in names:
            return keyword.value
    return None


def _unwrap_getattr(func: ast.AST | None, evaluator: "_PathEvaluator") -> ast.AST | None:
    """リテラル名を使う ``getattr(x, 'name')`` を ``x.name`` へ畳む。"""
    if not isinstance(func, ast.Call):
        return func
    if evaluator.resolve(_dotted(func.func)) != "getattr":
        return func
    name = _argument(func, 1, "name")
    target = _argument(func, 0, "object")
    if target is None or not isinstance(name, ast.Constant):
        return func
    if not isinstance(name.value, str):
        return func
    return ast.Attribute(
        value=_unwrap_getattr(target, evaluator), attr=name.value, ctx=ast.Load()
    )


class _PathEvaluator:
    """代入で伝播した定数と import 別名だけを使って path 式を評価する。"""

    def __init__(self) -> None:
        self.env: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.sequences: dict[str, list[str]] = {}

    def sequence(self, node: ast.AST | None, depth: int = 0) -> list[str] | None:
        """list/tuple リテラル、またはそれを束縛した名前を要素列として返す。"""
        if node is None or depth > _MAX_DEPTH:
            return None
        if isinstance(node, ast.Name):
            return self.sequences.get(node.id)
        if isinstance(node, (ast.List, ast.Tuple)):
            elements: list[str] = []
            for element in node.elts:
                if isinstance(element, ast.Starred):
                    inner = self.sequence(element.value, depth + 1)
                    if inner is None:
                        return None
                    elements.extend(inner)
                    continue
                elements.append(self.evaluate(element, depth + 1))
            return elements
        return None

    def resolve(self, dotted: str | None) -> str | None:
        """``cp`` → ``shutil.copy`` のように import 別名を完全名へ戻す。"""
        if not dotted:
            return None
        head, _, rest = dotted.partition(".")
        base = self.aliases.get(head, head)
        return f"{base}.{rest}" if rest else base

    def bind_import(self, node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                self.aliases[bound] = alias.name if alias.asname else bound
            return
        module = node.module or ""
        for alias in node.names:
            self.aliases[alias.asname or alias.name] = (
                f"{module}.{alias.name}" if module else alias.name
            )

    def evaluate(self, node: ast.AST | None, depth: int = 0) -> str:
        if node is None or depth > _MAX_DEPTH:
            return UNRESOLVED
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return node.value
            if isinstance(node.value, bytes):
                try:
                    return node.value.decode()
                except UnicodeDecodeError:
                    return UNRESOLVED
            return UNRESOLVED
        if isinstance(node, ast.Name):
            return self.env.get(node.id, UNRESOLVED)
        if isinstance(node, ast.Attribute):
            if node.attr == "parent":
                owner = self.evaluate(node.value, depth + 1)
                if UNRESOLVED in owner:
                    return UNRESOLVED
                head, separator, _ = owner.rstrip("/").rpartition("/")
                return head if separator else "."
            return _PATH_CONSTANTS.get(self.resolve(_dotted(node)) or "", UNRESOLVED)
        if isinstance(node, ast.BinOp):
            return self._binary(node, depth)
        if isinstance(node, ast.JoinedStr):
            return "".join(self.evaluate(part, depth + 1) for part in node.values)
        if isinstance(node, ast.FormattedValue):
            return self.evaluate(node.value, depth + 1)
        if isinstance(node, ast.Call):
            return self._call(node, depth)
        if isinstance(node, ast.Subscript):
            return self._subscript(node, depth)
        return UNRESOLVED

    def _subscript(self, node: ast.Subscript, depth: int) -> str:
        elements = self.sequence(node.value, depth + 1)
        index = node.slice
        if elements is None or not isinstance(index, ast.Constant):
            return UNRESOLVED
        if not isinstance(index.value, int) or isinstance(index.value, bool):
            return UNRESOLVED
        try:
            return elements[index.value]
        except IndexError:
            return UNRESOLVED

    def _binary(self, node: ast.BinOp, depth: int) -> str:
        left = self.evaluate(node.left, depth + 1)
        right = self.evaluate(node.right, depth + 1)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Div):
            return _join(left, right)
        if isinstance(node.op, ast.Mod):
            return self._percent(left, node.right, depth)
        return UNRESOLVED

    def _percent(self, template: str, right: ast.AST, depth: int) -> str:
        if UNRESOLVED in template:
            return UNRESOLVED
        operands = right.elts if isinstance(right, ast.Tuple) else [right]
        values = [self.evaluate(operand, depth + 1) for operand in operands]
        try:
            return template % tuple(values)
        except (TypeError, ValueError, KeyError):
            return UNRESOLVED

    def _call(self, node: ast.Call, depth: int) -> str:
        function = _unwrap_getattr(node.func, self)
        qualified = self.resolve(_dotted(function))
        if qualified in _PATH_CONSTRUCTORS or qualified in _JOIN_FUNCTIONS:
            return self._join_arguments(node, depth)
        if qualified in _PATH_IDENTITY_FUNCTIONS:
            return self.evaluate(_argument(node, 0, "path"), depth + 1)
        if not isinstance(function, ast.Attribute):
            return UNRESOLVED
        if function.attr == "join":
            separator = self.evaluate(function.value, depth + 1)
            elements = self.sequence(_argument(node, 0, "iterable"), depth + 1)
            if elements is None or UNRESOLVED in separator:
                return UNRESOLVED
            return separator.join(elements)
        if function.attr in _PATH_TAIL_METHODS:
            return self._replace_tail(function, node, depth)
        if function.attr == "joinpath":
            joined = self.evaluate(function.value, depth + 1)
            for argument in node.args:
                joined = _join(joined, self.evaluate(argument, depth + 1))
            return joined
        if function.attr in _PATH_IDENTITY_METHODS:
            return self.evaluate(function.value, depth + 1)
        if function.attr == "format":
            return self._format(function.value, node, depth)
        return UNRESOLVED

    def _replace_tail(self, function: ast.Attribute, node: ast.Call, depth: int) -> str:
        base = self.evaluate(function.value, depth + 1)
        replacement = self.evaluate(_argument(node, 0, "name", "suffix"), depth + 1)
        if UNRESOLVED in base or UNRESOLVED in replacement:
            return UNRESOLVED
        head, separator, tail = base.rpartition("/")
        if function.attr == "with_name":
            return f"{head}{separator}{replacement}"
        stem = tail.rsplit(".", 1)[0] if "." in tail else tail
        return f"{head}{separator}{stem}{replacement}"

    def _join_arguments(self, node: ast.Call, depth: int) -> str:
        joined = ""
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                elements = self.sequence(argument.value, depth + 1)
                if elements is None:
                    return UNRESOLVED
                for element in elements:
                    joined = _join(joined, element)
                continue
            joined = _join(joined, self.evaluate(argument, depth + 1))
        return joined

    def _format(self, owner: ast.AST, node: ast.Call, depth: int) -> str:
        template = self.evaluate(owner, depth + 1)
        if UNRESOLVED in template or node.keywords:
            return UNRESOLVED
        values = [self.evaluate(argument, depth + 1) for argument in node.args]
        try:
            return template.format(*values)
        except (IndexError, KeyError, ValueError):
            return UNRESOLVED

    def bind(self, node: ast.AST) -> None:
        """代入文の左辺 Name へ右辺の評価結果を束ねる。"""
        if isinstance(node, ast.Assign):
            value, targets = self.evaluate(node.value), node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = self.evaluate(node.value), [node.target]
        elif isinstance(node, ast.AugAssign):
            name = node.target.id if isinstance(node.target, ast.Name) else ""
            value = self._augmented(self.env.get(name, UNRESOLVED), node)
            targets = [node.target]
        else:
            return
        source = node.value if not isinstance(node, ast.AugAssign) else None
        elements = self.sequence(source) if source is not None else None
        for target in targets:
            if isinstance(target, ast.Name):
                self.env[target.id] = value
                if elements is None:
                    self.sequences.pop(target.id, None)
                else:
                    self.sequences[target.id] = elements

    def _augmented(self, current: str, node: ast.AugAssign) -> str:
        operand = self.evaluate(node.value)
        if isinstance(node.op, ast.Add):
            return current + operand
        if isinstance(node.op, ast.Div):
            return _join(current, operand)
        return UNRESOLVED
