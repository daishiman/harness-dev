#!/usr/bin/env python3
# /// script
# name: guard-graph-schema
# purpose: dev-graph の破壊操作、graph authority への Write/Edit・interpreter 直書き、無制限 gh write、bd-bridge を迂回する Beads mutation を PreToolUse で拒否する。
# inputs: [stdin Claude hook JSON, argv --repo-root]
# outputs: [exit 0 allow, exit 2 deny with stderr]
# contexts: [E]
# network: false
# write-scope: none
# dependencies: [scripts/resolve-repo-context.py, lib/guard_graph_commands.py, lib/guard_python_writes.py, lib/guard_python_path_eval.py]
# requires-python: ">=3.11"
# ///
"""C10: Bash mutation の単一 fail-closed guard。

遮断判定は subprocess を一切起動せずに確定させる (``static_denial``)。PreToolUse hook が
timeout すると Claude Code は tool を通すため、遮断経路の内側に置いた subprocess の
所要時間はそのまま fail-open の窓になる。HarnessHub-6in4 ではこの窓を通って
``.dev-graph/config.json`` と ``.dev-graph/state/graph.json`` への Bash 直書きが
live-trial 中に 2 回素通りした。context_ok() はこの判定を通過した入力に対してだけ呼ぶ。

この設計から導かれる遮断範囲の上限を、能力の誇張を避けるため明記する。判定材料は
PreToolUse に届くコマンド文字列だけであり、``python3 tools/writer.py`` のように書込みを
別 script file へ移した間接起動は「interpreter 起動 x 書込み動詞 x authority path」の
共起が文字列上で 1 つも成立しないため、ここでは遮断できない (HarnessHub-kzth)。script の
中身を読めば遮断できるが、それは上の遮断時間契約を破って fail-open 窓を再び開く。
遮断できない範囲は PostToolUse の ``audit-graph-authority-drift.py`` (graph_revision の
+1 不変条件による事後検出) と C11 の envelope 検査 (``lib/graph_envelope.py``) が受け持つ。
3 層の責務分担と、いずれの層でも閉じない残余は ``references/claude-code-hooks-contract.md``
に契約として書いてある。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 判定ロジックは import 専用の lib/ に置く。hooks/ には hooks.json が起動する entry point だけを置く
# (package-contract の entry_points.hooks は hooks/ の実体と完全一致で照合される)。
LIB_ROOT = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))
sys.dont_write_bytecode = True

from guard_graph_commands import (
    GRAPH_AUTHORITY_PATH,
    GUARDED_SCAN_ROOT,
    _pipelines,
    destructive_graph_or_schema_operation,
    indirect_mutation_over_guarded_area,
)
from guard_python_writes import inline_python_writes_graph_authority, python_sources

BD_MUTATION = re.compile(r"(?:^|[;&|]\s*)bd\s+(?:create|update|close|delete|purge|sql)\b", re.I)
GH_MUTATION = re.compile(r"\bgh\s+(?:issue\s+(?:create|edit|close|delete)|project\s+item-(?:add|edit|delete))\b", re.I)
# Write/Edit ツールと interpreter 経由の書込みで守る範囲。Bash の GRAPH_OR_SCHEMA_TARGET より
# 狭く graph authority だけを対象にする (content root への通常編集まで止めると日常作業が壊れる)。
# authority = graph store (`state/`) と repo-local config、および正準 schema。
# `.dev-graph/` 全体ではない — templates/ cache/ tmp/ は init が正当に書くため除外する
# (広く取りすぎると `cp plugins/dev-graph/templates .dev-graph/templates` まで止まる)。
FILE_WRITING_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
OWNERSHIP_MARKER = Path(".dev-graph") / "config.json"
# python/ruby/node 等に file path と書込みモードが同居する呼び出し。rm/sed 等の語彙しか持たない
# _mutating_operands では、インタプリタ本文に埋め込まれた open(...,'w') を検出できない。
# mode は named group で切り出し、書込み判定 (_open_mode_is_write) へ委ねる。文字クラス列挙
# ([waxr]\+?[bt]?) には 'r' が含まれ、読取専用の open(path, 'r') まで誤って BLOCK していた
# (HarnessHub-lp36)。'r' 単体は読取、'r+' は書込み可なので、+ の有無で分岐させる。
INTERPRETER_WRITE = re.compile(
    r"""open\s*\(\s*(?P<q>['"])(?P<path>[^'"]+)(?P=q)\s*,\s*(?P<q2>['"])(?P<mode>[a-zA-Z+]{1,3})(?P=q2)"""
    r"""|['"](?P<path2>[^'"]*\.dev-graph[^'"]*)['"]\s*,\s*['"](?P<mode2>[wax][a-zA-Z+]{0,2})""",
    re.I,
)
# graph authority path と同一コマンド内に現れたら BLOCK する書込み API の列挙 (HarnessHub-lp36)。
# pathlib (write_text/write_bytes/touch/unlink/rmdir/.open(w|a|x)) に加えて、shutil.copy* /
# shutil.move / os.replace / os.rename / json.dump を対象にする。path 引数の位置は API ごとに
# 異なる (shutil.copy は第2引数、json.dump はそもそも path を取らない) ため、この関数は
# 「同一コマンド内に書込み API 呼び出しと graph authority の文字列が共起するか」だけを見る
# 共起判定であり、それらが同一操作の path/mode を指しているかまでは解析しない。
PATHLIB_MUTATION = re.compile(
    r"""\.\s*(?:write_text|write_bytes|touch|unlink|rmdir)\s*\("""
    r"""|\.\s*open\s*\(\s*['"][wax]"""
    r"""|\bshutil\s*\.\s*copy\w*\s*\("""
    r"""|\bshutil\s*\.\s*move\s*\("""
    r"""|\bos\s*\.\s*(?:replace|rename)\s*\("""
    r"""|\bjson\s*\.\s*dump\s*\(""",
    re.I,
)
GRAPH_AUTHORITY_LITERAL = re.compile(
    r"""\.dev-graph/(?:state(?:/|['"]|$)|config\.json\b)"""
    r"""|graph-node\.schema\.json\b""",
    re.I,
)
# Unit-level callers historically pass a Python source fragment directly, while the hook receives a
# shell command.  The literal fallback may inspect direct source fragments, but must not scan prose
# emitted by ``echo``/``cat`` as if it were executable Python.
RAW_PYTHON_SOURCE = re.compile(
    r"^\s*(?:from\s+\w+\s+import\b|import\s+\w+\b|open\s*\(|(?:Path|pathlib\.|shutil\.|os\.|json\.)|\w+\s*=)",
    re.S,
)
# 変数経由の間接表現 (HarnessHub-f84o)。INTERPRETER_WRITE / PATHLIB_MUTATION は書込み先と
# mode を字面でしか読まないため、`p = '.dev-graph/state/graph.json'` のように一度変数へ退避
# されると 1 つも成立しない。ここでは inline Python の「文字列に畳める代入」だけを静的に解決し、
# 解決値を quote 済み literal へ展開した写しに対して同じ検出器をもう一度かける。
# 解決できない式 (関数呼出し・添字・実行時値) は None のままにして展開しない — 展開の失敗は
# 現状維持 (= 従来どおり ALLOW) であり、遮断の緩和にはならない。subprocess も file I/O も
# 使わないため HarnessHub-6in4 の fail-open 窓は再導入しない。
_MAX_TRACKED_VARIABLES = 64
_MAX_EXPANDED_COMMAND = 32_768
# 代入の開始境界には quote を含める。inline Python は `python3 -c "p='...'; ..."` の形で
# 渡るため、最初の代入は必ず quote の直後に現れる。
_ASSIGNMENT = re.compile(
    r"""(?:^|[;\n(,'"]|\s)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<expr>[^;\n]{1,512})"""
)
_EXPRESSION_TOKEN = re.compile(
    r"""(?P<call>(?:pathlib\s*\.\s*)?(?:Pure)?(?:Posix|Windows)?Path|os\s*\.\s*path\s*\.\s*join)\s*\(
      |(?P<literal>f?(?P<quote>['"])(?P<body>[^'"]*)(?P=quote))
      |(?P<name>[A-Za-z_][A-Za-z0-9_]*)
      |(?P<join>[/,])
      |(?P<concat>\+)
      |(?P<close>\))
      |(?P<space>\s+)""",
    re.X,
)
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def _resolve_expression(expr: str, known: dict[str, str]) -> str | None:
    """``'a'`` / ``Path('a')/'b'`` / ``os.path.join(a, 'b')`` / ``f'{a}/b'`` を path 文字列へ畳む。

    許可トークン以外が 1 つでも挟まれば None を返す (未解決は展開しない)。``/`` と ``,`` は
    path 区切り、``+`` は素の連結として扱う。
    """
    expr = expr.split("#", 1)[0].strip()
    if not expr:
        return None
    segments: list[tuple[str, str]] = []
    separator = ""
    position = 0
    for match in _EXPRESSION_TOKEN.finditer(expr):
        if match.start() != position:
            return None
        position = match.end()
        if match.group("space") or match.group("call") or match.group("close"):
            continue
        if match.group("join"):
            separator = "/"
            continue
        if match.group("concat"):
            separator = ""
            continue
        if match.group("literal") is not None:
            body = match.group("body")
            if match.group("literal").startswith("f"):
                try:
                    body = _PLACEHOLDER.sub(lambda hit: known[hit.group(1)], body)
                except KeyError:
                    return None
            elif "{" in body:
                return None
            segments.append((separator, body))
        else:
            value = known.get(match.group("name"))
            if value is None:
                return None
            segments.append((separator, value))
        separator = ""
    if position != len(expr) or not segments:
        return None
    resolved = segments[0][1]
    for boundary, value in segments[1:]:
        resolved = f"{resolved.rstrip('/')}/{value.lstrip('/')}" if boundary == "/" else resolved + value
    return resolved


def _string_assignments(command: str) -> dict[str, str]:
    """command 内の「文字列に畳める代入」を変数名 -> 値へ解決する。

    2 パス回すのは ``base = '.dev-graph'`` -> ``target = base + '/state/graph.json'`` の
    ような 1 段の後方参照を解くため。収束したら打ち切り、追跡数にも上限を置く。
    """
    known: dict[str, str] = {}
    for _ in range(2):
        changed = False
        for match in _ASSIGNMENT.finditer(command):
            if len(known) >= _MAX_TRACKED_VARIABLES:
                return known
            name = match.group("name")
            value = _resolve_expression(match.group("expr"), known)
            if value is not None and known.get(name) != value:
                known[name] = value
                changed = True
        if not changed:
            break
    return known


def _with_variables_expanded(command: str) -> str:
    """解決済み変数の参照を quote 済み literal へ置き換えた command の写しを返す。

    値は quoted literal 由来で ``'`` を含まないため、置換で quote 構造は壊れない。
    """
    if len(command) > _MAX_EXPANDED_COMMAND:
        return command
    known = _string_assignments(command)
    if not known:
        return command
    return _IDENTIFIER.sub(
        lambda hit: f"'{known[hit.group(0)]}'" if hit.group(0) in known else hit.group(0),
        command,
    )


def is_managed_repository(root: Path) -> bool:
    """A repo is hook-managed only when its local dev-graph ownership marker exists."""
    try:
        resolved_root = Path(root).resolve(strict=True)
        marker = (resolved_root / OWNERSHIP_MARKER).resolve(strict=True)
        marker.relative_to(resolved_root)
    except (FileNotFoundError, OSError, ValueError):
        return False
    return marker.is_file()


def payload() -> dict:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def command_of(value: dict) -> str:
    tool_input = value.get("tool_input") or {}
    return str(tool_input.get("command") or "") if isinstance(tool_input, dict) else ""


def written_paths_of(value: dict) -> list[str]:
    """Write/Edit 系ツールが書込む対象 path を返す (Bash 以外の C02 迂回経路)。"""
    if str(value.get("tool_name") or "") not in FILE_WRITING_TOOLS:
        return []
    tool_input = value.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return []
    return [
        str(tool_input[key])
        for key in ("file_path", "notebook_path")
        if isinstance(tool_input.get(key), str) and tool_input[key]
    ]


def _open_mode_is_write(mode: str) -> bool:
    """open() の mode 文字列が書込みを含むか (w/a/x、または ``+`` を含む)。"""
    mode = mode.lower()
    if not mode:
        return False
    # Python の open() は ``rb+`` だけでなく ``br+`` / ``+rb``、``wb`` だけでなく
    # ``bw`` も受理する。先頭文字だけを見ると同じ有効 mode の並び替えで guard を迂回
    # できるため、書込み能力を与える文字が mode 内のどこにあるかで判定する。
    return bool(set(mode) & {"w", "a", "x"}) or "+" in mode


def _literal_interpreter_write(command: str) -> bool:
    """字面に現れる path/mode だけで interpreter 経由の graph authority 書込みを判定する。

    保証範囲 (HarnessHub-lp36): 字面パターンに一致する次の書込み API のみを検出する。
    ``open(path, mode)`` (mode が w/a/x/r+ 系)・``Path.write_text``・``Path.write_bytes``・
    ``Path.touch``・``Path.unlink``・``Path.rmdir``・``Path.open(w/a/x)``・``shutil.copy*``・
    ``shutil.move``・``os.replace``・``os.rename``・``json.dump``。これらは静的正規表現一致で
    あり、変数を経由した path/mode (例: ``open(p, m)``)・エイリアス import
    (``from shutil import copy as cp``)・``exec``/``eval`` 経由の間接呼出し・``os.open`` の
    低レベル fd 系は検出できない。これらは C02 atomic writer (``build-graph-node.py`` /
    ``build-init-scaffold.py`` / ``register-package.py``) の使用を運用規約として要求すること
    でしか閉じられない。
    """
    sources = python_sources(command)
    candidates = sources or ([command] if RAW_PYTHON_SOURCE.match(command) else [])
    for source in candidates:
        for match in INTERPRETER_WRITE.finditer(source):
            path = match.group("path") or match.group("path2") or ""
            if not GRAPH_AUTHORITY_PATH.search(path):
                continue
            mode = match.group("mode") or match.group("mode2") or ""
            if _open_mode_is_write(mode):
                return True
        # ``Path.write_text`` / ``shutil.copy`` 等は path を ``open(...)`` の第 1 引数として
        # 渡さないため上の枝では検出できない。API 呼出しと graph authority の文字列が同一
        # source 内に共起するかだけを見る粗い判定にとどめ、``Path.read_text`` のような
        # 読取専用呼出しは対象外のまま残す。
        if PATHLIB_MUTATION.search(source) and GRAPH_AUTHORITY_LITERAL.search(source):
            return True
    return False


def interpreter_writes_graph_authority(command: str) -> bool:
    """interpreter 経由の authority 書込みを AST・字面・代入展開で判定する。

    AST 層 (HarnessHub-f84o) は inline Python の変数・Path・join・format・alias と主要
    write API を解析する。字面層 (HarnessHub-lp36) と main 由来の shell 定数代入展開は、
    AST 化できない断片と既存保証を保持する。3 層は加算的で、いずれも subprocess や
    repository file を読まない。

    別 script file、``exec``/``eval`` 内 source、任意の文字列難読化は PostToolUse drift
    audit と C02/C11 が補完する。
    """
    if inline_python_writes_graph_authority(command) or _literal_interpreter_write(command):
        return True
    expanded = _with_variables_expanded(command)
    if expanded == command:
        return False
    return inline_python_writes_graph_authority(expanded) or _literal_interpreter_write(expanded)


def context_ok(root: Path) -> tuple[bool, str]:
    resolver = Path(__file__).resolve().parents[1] / "scripts" / "resolve-repo-context.py"
    if not resolver.is_file():
        return False, f"required resolver missing: {resolver}"
    proc = subprocess.run(
        [sys.executable, "-B", str(resolver), "--repo-root", str(root), "--mode", "read"],
        capture_output=True, text=True, check=False,
    )
    return proc.returncode == 0, (proc.stderr.strip() or proc.stdout.strip())


def static_denial(command: str, written: list[str], root: Path) -> str | None:
    """subprocess を起動せずに確定できる遮断理由を返す (無ければ None)。

    遮断に必要な判定を全てここへ集約するのが本 hook の fail-closed 契約である。
    PreToolUse hook が timeout すると Claude Code は tool を通すため、遮断経路の内側で
    subprocess を回すとその所要時間がそのまま fail-open の窓になる。以前は Bash の
    破壊操作枝だけが ``context_ok()`` の後段にあり、さらに遮断/許可を左右しない
    ``schema_ok()`` (= graph 全件の C11 検証) を理由文の出し分けのためだけに呼んでいた。
    実測 (HarnessHub-6in4) では Write 枝 0.10s に対し Bash 枝は 39.79s を要し、
    run-dev-graph-init の live-trial で ``.dev-graph/config.json`` と
    ``.dev-graph/state/graph.json`` への直書きが実際に 2 回素通りした。

    C11 検証をここへ戻してはならない。遮断は既に確定しており理由文の精度しか上がらない
    一方、その所要時間は fail-open の窓に直結する。C11 は C02 writer
    (build-graph-node.py / build-init-scaffold.py) の書込み前検証が別途強制する。
    """
    if any(GRAPH_AUTHORITY_PATH.search(path) for path in written):
        # 保護範囲は GRAPH_AUTHORITY_PATH と一致させる。「.dev-graph/ 配下」と広く名乗ると、
        # 実際は保護外の tmp/ へ draft を置く正規手順まで塞がれていると読まれ、遮断された
        # agent が別の迂回を探しに行く (6in4 の fail-open はまさにその局面で起きた)。
        return (
            "graph authority (.dev-graph/state/、.dev-graph/config.json、"
            "graph-node.schema.json) への Write/Edit は C02 atomic writer を迂回できない "
            "(config と初期 graph は scripts/build-init-scaffold.py、node 更新は "
            "scripts/build-graph-node.py 経由。draft は保護外の .dev-graph/tmp/ へ置く)"
        )
    if not command:
        return None
    if interpreter_writes_graph_authority(command):
        return (
            "interpreter 経由の graph authority 書込みは C02 atomic writer を迂回できない "
            "(初期 graph は scripts/build-init-scaffold.py、node 更新は "
            "scripts/build-graph-node.py 経由)"
        )
    if BD_MUTATION.search(command) and "bd-bridge.py" not in command:
        return "Beads mutation は scripts/bd-bridge.py の単一チョークポイント経由に限定"
    if GH_MUTATION.search(command) and "gh-bridge.py" not in command:
        return "GitHub bulk/write は scripts/gh-bridge.py の dry-run/ledger 経由に限定"
    if destructive_graph_or_schema_operation(command, root):
        return (
            "graph/schema の直接破壊操作は C02 atomic writer を迂回できない "
            "(.dev-graph/config.json と初期 graph は scripts/build-init-scaffold.py、"
            "node 更新は scripts/build-graph-node.py 経由で書く)"
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    # dev-graph の所有 marker を持たない repository では判定しない (無関係な repo の操作を止めない)。
    if not is_managed_repository(Path(args.repo_root)):
        return 0
    value = payload()
    command = command_of(value)
    written = written_paths_of(value)
    if not command and not written:
        return 0

    root = Path(args.repo_root).resolve()
    # 第 1 段: subprocess 非依存の遮断判定。timeout 由来の fail-open 窓を持たない。
    reason = static_denial(command, written, root)
    if reason:
        sys.stderr.write(f"[guard-graph-schema] BLOCKED: {reason}\n")
        return 2

    # 第 2 段: 遮断対象ではない入力に対してだけ repository context の健全性を確認する。
    # ここでの timeout は「遮断すべき操作を通す」のではなく「無害な操作の検査を省く」に留まる。
    if not command:
        return 0
    ok, detail = context_ok(root)
    if not ok:
        sys.stderr.write(f"[guard-graph-schema] BLOCKED: repository context invalid: {detail}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
