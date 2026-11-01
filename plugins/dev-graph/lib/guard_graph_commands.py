"""Shell-command write-target analysis for the Dev Graph C10 guard."""
from __future__ import annotations

import re
import shlex
from pathlib import Path


GRAPH_OR_SCHEMA_TARGET = re.compile(
    r"(?:\.dev-graph/state/graph\.json\b|"
    r"(?:issues|tasks|specs|architecture|features|docs)/|"
    r"(?:schemas/)?graph-node\.schema\.json\b)",
    re.I,
)
GRAPH_AUTHORITY_DIR = re.compile(r"(?:^|/)\.dev-graph/?$", re.I)
GRAPH_AUTHORITY_PATH = re.compile(
    r"(?:^|/)\.dev-graph/(?:state(?:/|$)|config\.json$)"
    r"|(?:^|/)graph-node\.schema\.json$",
    re.I,
)
INDIRECT_MUTATION_TOOLS = frozenset(
    {"rm", "mv", "cp", "install", "truncate", "sed", "perl", "tee", "touch"}
)
GUARDED_SCAN_ROOT = re.compile(
    r"^(?:\./)?(?:issues|tasks|specs|architecture|features|docs|\.dev-graph)(?:/|$)",
    re.I,
)
GUARDED_ROOT_NAMES = frozenset(
    {"issues", "tasks", "specs", "architecture", "features", "docs", ".dev-graph"}
)
_REDIRECT_PUNCTUATION = "|<>"
_REDIRECT_OPERATOR = re.compile(r">{1,2}\|?")
_REDIRECT_FALLBACK = re.compile(
    r"(?:^|[\s;&|])(?:[0-9]+)?>{1,2}\s*"
    r"(?P<target>\"[^\"]+\"|'[^']+'|[^\s;&|]+)"
)
_DYNAMIC_OPERAND = "__DEV_GRAPH_DYNAMIC_OPERAND__"
_COMMAND_WRAPPERS = frozenset({"command", "env", "nice", "nohup", "sudo", "time"})
_XARGS_OPTIONS_WITH_VALUE = frozenset(
    {
        "-a",
        "--arg-file",
        "-d",
        "--delimiter",
        "-E",
        "--eof",
        "-I",
        "--replace",
        "-L",
        "--max-lines",
        "-n",
        "--max-args",
        "-P",
        "--max-procs",
        "-s",
        "--max-chars",
    }
)


def _guarded_target(value: str) -> bool:
    candidate = value.strip().strip("\"'")
    return bool(
        GRAPH_OR_SCHEMA_TARGET.search(candidate)
        or GRAPH_AUTHORITY_DIR.search(candidate)
        or GRAPH_AUTHORITY_PATH.search(candidate)
    )


def _expanded(value: str, assignments: dict[str, str]) -> str:
    match = re.fullmatch(
        r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|"
        r"(?P<plain>[A-Za-z_][A-Za-z0-9_]*))",
        value,
    )
    if not match:
        return value
    return assignments.get(match.group("braced") or match.group("plain"), value)


def _mutating_operands(command: str) -> list[str]:
    """Return operands that a recognised shell command can mutate.

    セグメント分割には改行を含める (HarnessHub-l1ru)。``shlex.split`` は改行を通常の空白と
    同じに扱うため、改行だけで連結された独立コマンド群を 1 セグメントに残すと、先頭行の
    ``git restore`` / ``git checkout --`` が後続行のトークンまで自分の operand として
    吸収する。実測では ``git restore <保護外>\\ngit add docs/foo.md`` が
    ``['eval-log/...', 'git', 'add', 'docs/foo.md', ...]`` を返し、保護外パスの復元だけの
    コマンドが誤って BLOCK になった。``_pipelines`` は既に改行で分割しており、ここでの
    追加は両者の分割規則の対称化である (過検知の解消であって遮断の緩和ではない)。
    """
    targets: list[str] = []
    for segment in re.split(r"(?:&&|\|\||[;|\n])", command):
        try:
            tokens = shlex.split(segment, comments=False, posix=True)
        except ValueError:
            continue
        assignments: dict[str, str] = {}
        operation_index = None
        operation = ""
        for index, token in enumerate(tokens):
            assignment = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", token)
            if assignment and operation_index is None:
                assignments[assignment.group(1)] = assignment.group(2)
                continue
            base = Path(token).name.lower()
            if base in {
                "rm",
                "mv",
                "cp",
                "install",
                "truncate",
                "sed",
                "perl",
                "git",
                "tee",
                "touch",
            }:
                operation_index, operation = index, base
                break
        if operation_index is None:
            continue
        raw = tokens[operation_index + 1 :]
        operands: list[str] = []
        skip_redirect_target = False
        for token in raw:
            if skip_redirect_target:
                skip_redirect_target = False
                continue
            if token in {">", ">>", "1>", "1>>", "2>", "2>>"}:
                skip_redirect_target = True
                continue
            if re.match(r"^[0-9]*>{1,2}", token):
                continue
            if token == "--" or token.startswith("-"):
                continue
            operands.append(_expanded(token, assignments))

        if operation in {"cp", "install"}:
            if operands:
                targets.append(operands[-1])
        elif operation == "mv":
            targets.extend(operands)
        elif operation in {"rm", "truncate", "tee", "touch"}:
            targets.extend(operands)
        elif operation in {"sed", "perl"}:
            has_in_place = any(
                token == "--in-place"
                or re.fullmatch(r"-[A-Za-z]*i(?:\..*)?", token)
                for token in raw
            )
            if has_in_place:
                targets.extend(operands)
        elif operation == "git" and raw:
            if raw[0] == "restore" or (raw[0] == "checkout" and "--" in raw):
                targets.extend(operands[1:])
    return targets


def _pipelines(command: str) -> list[list[str]]:
    """Split a command into pipeline-scoped token groups."""
    groups: list[list[str]] = []
    for group in re.split(r"&&|\|\||[;\n]", command):
        tokens = _tokens(group)
        if tokens:
            groups.append(tokens)
    return groups


def _tokens(group: str) -> list[str]:
    """Respect quotes while separating an unquoted pipe token."""
    lexer = shlex.shlex(group, posix=True, punctuation_chars="|")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return group.split()


def _operation(tokens: list[str]) -> tuple[int, str] | None:
    for index, token in enumerate(tokens):
        if token in _COMMAND_WRAPPERS or re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*=.*",
            token,
        ):
            continue
        operation = Path(token).name.lower()
        if operation in INDIRECT_MUTATION_TOOLS:
            return index, operation
        return None
    return None


def _contains_dynamic_operand(token: str) -> bool:
    return _DYNAMIC_OPERAND in token


def _target_directory(args: list[str]) -> tuple[bool, bool]:
    for index, token in enumerate(args):
        if token in {"-t", "--target-directory"}:
            target = args[index + 1] if index + 1 < len(args) else ""
            return True, _contains_dynamic_operand(target)
        if token.startswith("--target-directory="):
            return True, _contains_dynamic_operand(token.split("=", 1)[1])
        if token.startswith("-t") and len(token) > 2:
            return True, _contains_dynamic_operand(token[2:])
    return False, False


def _dynamic_operand_is_mutated(tokens: list[str]) -> bool:
    found = _operation(tokens)
    if found is None:
        return False
    operation_index, operation = found
    args = tokens[operation_index + 1 :]
    dynamic_args = [token for token in args if _contains_dynamic_operand(token)]
    if not dynamic_args:
        return False
    if operation in {"rm", "mv", "truncate", "tee", "touch"}:
        return True
    if operation in {"cp", "install"}:
        has_target_directory, dynamic_target_directory = _target_directory(args)
        if has_target_directory:
            return dynamic_target_directory
        operands = [token for token in args if not token.startswith("-")]
        return bool(operands and _contains_dynamic_operand(operands[-1]))
    if operation in {"sed", "perl"}:
        return any(
            token == "--in-place"
            or token.startswith("--in-place=")
            or re.fullmatch(r"-[A-Za-z]*i(?:\..*)?", token)
            for token in args
        )
    return False


def _xargs_replacement(
    tokens: list[str],
    xargs_index: int,
    operation_index: int,
) -> str | None:
    option_tokens = tokens[xargs_index + 1 : operation_index]
    for index, token in enumerate(option_tokens):
        if token in {"-I", "--replace"}:
            return option_tokens[index + 1] if index + 1 < len(option_tokens) else None
        if token.startswith("--replace="):
            return token.split("=", 1)[1]
        if token.startswith("-I") and len(token) > 2:
            return token[2:]
    return None


def _xargs_command_index(
    tokens: list[str],
    xargs_index: int,
    stage_end: int,
) -> int | None:
    index = xargs_index + 1
    while index < stage_end:
        token = tokens[index]
        if token == "--":
            return index + 1 if index + 1 < stage_end else None
        if token in _XARGS_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if token.startswith("--") and "=" in token:
            index += 1
            continue
        if token.startswith("-I") and len(token) > 2:
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return index
    return None


def _xargs_mutates_enumerated_paths(tokens: list[str]) -> bool:
    try:
        xargs_index = next(
            index
            for index, token in enumerate(tokens)
            if Path(token).name.lower() == "xargs"
        )
    except StopIteration:
        return False
    try:
        stage_end = tokens.index("|", xargs_index + 1)
    except ValueError:
        stage_end = len(tokens)
    operation_index = _xargs_command_index(tokens, xargs_index, stage_end)
    if operation_index is None:
        return False
    command = tokens[operation_index:stage_end]
    if _operation(command) is None:
        return False
    replacement = _xargs_replacement(tokens, xargs_index, operation_index)
    if replacement:
        command = [
            token.replace(replacement, _DYNAMIC_OPERAND) for token in command
        ]
    else:
        command = [*command, _DYNAMIC_OPERAND]
    return _dynamic_operand_is_mutated(command)


def _find_exec_mutates_enumerated_paths(tokens: list[str]) -> bool:
    try:
        exec_index = next(
            index
            for index, token in enumerate(tokens)
            if token in {"-exec", "-execdir"}
        )
    except StopIteration:
        return False
    try:
        stage_end = tokens.index("|", exec_index + 1)
    except ValueError:
        stage_end = len(tokens)
    command = [
        token.replace("{}", _DYNAMIC_OPERAND)
        for token in tokens[exec_index + 1 : stage_end]
        if token not in {";", "\\;", "\\", "+"}
    ]
    return _dynamic_operand_is_mutated(command)


def _pipeline_has_indirect_mutation(tokens: list[str]) -> bool:
    has_find = any(Path(token).name.lower() == "find" for token in tokens)
    if has_find and "-delete" in tokens:
        return True
    return _xargs_mutates_enumerated_paths(
        tokens
    ) or _find_exec_mutates_enumerated_paths(tokens)


def _scans_guarded_area(
    tokens: list[str],
    repo_root: Path | None = None,
) -> bool:
    root = repo_root.resolve() if repo_root is not None else None
    guarded_roots = (
        [root / name for name in GUARDED_ROOT_NAMES] if root is not None else []
    )
    for token in tokens:
        candidate = token.strip("\"'")
        if not candidate or candidate == "|":
            continue
        if root is None:
            if GUARDED_SCAN_ROOT.match(candidate) or _guarded_target(candidate):
                return True
            continue
        candidate = candidate.replace("${PWD}", str(root)).replace("$PWD", str(root))
        if candidate.startswith("$(pwd)"):
            candidate = str(root) + candidate[len("$(pwd)") :]
        if any(character in candidate for character in "*?[]{}"):
            candidate = re.split(
                r"[*?\[\]{}]",
                candidate,
                maxsplit=1,
            )[0].rstrip("/")
        if not candidate or candidate.startswith("-"):
            continue
        path = Path(candidate)
        resolved = (
            path if path.is_absolute() else root / path
        ).resolve(strict=False)
        if resolved == root or resolved in root.parents:
            return True
        if any(
            resolved == guarded or guarded in resolved.parents
            for guarded in guarded_roots
        ):
            return True
    return False


def indirect_mutation_over_guarded_area(
    command: str,
    repo_root: Path | None = None,
) -> bool:
    for tokens in _pipelines(command):
        if _pipeline_has_indirect_mutation(tokens) and _scans_guarded_area(
            tokens,
            repo_root,
        ):
            return True
    return False


def _redirect_targets(command: str) -> list[str]:
    """Return destinations of redirect operators that occur outside quotes."""
    lexer = shlex.shlex(
        command,
        posix=True,
        punctuation_chars=_REDIRECT_PUNCTUATION,
    )
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return [
            match.group("target").strip("\"'")
            for match in _REDIRECT_FALLBACK.finditer(command)
        ]
    targets: list[str] = []
    pending = False
    for token in tokens:
        if pending:
            if token == "&":
                continue
            pending = False
            targets.append(token.strip("\"'"))
            continue
        if _REDIRECT_OPERATOR.fullmatch(token):
            pending = True
    return targets


def destructive_graph_or_schema_operation(
    command: str,
    repo_root: Path | None = None,
) -> bool:
    if any(_guarded_target(target) for target in _redirect_targets(command)):
        return True
    if any(_guarded_target(target) for target in _mutating_operands(command)):
        return True
    return indirect_mutation_over_guarded_area(command, repo_root)
