#!/usr/bin/env python3
"""lint-harness-plan-writeguard.py — 片方向 writer 不変条件の横断 AST ガード (S1)。

harness-creator の task-graph consumer scripts が producer=plugin-dev-planner 所有の plan
成果物 (plugin-plans/ 配下・task-graph.json・component-inventory.json・phase-NN-*.md・
handoff-run-plugin-dev-plan.json) へ **書き込み** しないことを AST で静的検査する。
各 script の per-script test (C08 のバイト不変 / C04 の source-grep 等) を補完し、新 script・
新 code-path への被覆を自動化する — 誰かが後で harness script に plan 直書きを足したら CI が
fail-closed で落ちる (frontmatter write-scope 宣言は documentary で機械強制ではないため=S1)。

対象選定 (task-graph consumer):
  - 既知の consumer 7 本 (dispatch/sync/inject/emit/summarize/manage/record)、または
  - `resolve_build_dir` を参照する script (新規 consumer を自動被覆)。

write sink:
  - open(path, 'w'|'a'|'x'|'+' ...) / io.open(...) の write-mode
  - <expr>.write_text(...) / <expr>.write_bytes(...)
  - <expr>.open('w'...) (Path.open の write-mode)
  - os.replace(...) / os.rename(...) / <expr>.rename(...) / <expr>.replace(...)
  - shutil.move(...) / shutil.copy(...) / shutil.copyfile(...) / shutil.copy2(...)

判定: write sink の 出力先 path 式 (ast.unparse) が forbidden token を含む、または path が
forbidden token を含む式から代入された局所変数のとき violation。
例外: 当該 sink の行範囲に `writeguard: allow` マーカー (理由付きコメント) があれば許可
(dispatch の tempfile task-graph.json コピー等・非永続 / plan 非書込の正当例外を明示監査)。

usage: lint-harness-plan-writeguard.py [--scripts-dir <dir>]
exit: 0=OK / 1=violation / 2=usage/IO error
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

# plan 成果物を指す forbidden token (write sink の path 式に現れたら違反)。
_FORBIDDEN = re.compile(
    r"plugin-plans|task-graph\.json|component-inventory\.json|handoff-run-plugin-dev-plan|phase-\d\d"
)
# 正当例外を明示するインラインマーカー (理由をコメントに添える運用)。
_ALLOW_MARKER = "writeguard: allow"

# 既知の task-graph consumer (最低被覆保証)。resolve_build_dir 参照でも自動被覆する。
_KNOWN_CONSUMERS = {
    "dispatch-ready-set.py",
    "sync-task-state.py",
    "inject-task-inputs.py",
    "emit-discovered-task.py",
    "summarize-task-progress.py",
    "manage-build-lease.py",
    "record-task-graph-knowledge.py",
}

_WRITE_MODE_CHARS = set("wax+")
_RENAME_METHODS = {"rename", "replace"}
_WRITE_METHODS = {"write_text", "write_bytes"}
_SHUTIL_MOVES = {"move", "copy", "copyfile", "copy2"}


def _default_scripts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "plugins" / "harness-creator" / "scripts"


def _is_write_mode(s: str) -> bool:
    return bool(set(s) & _WRITE_MODE_CHARS)


def _mode_arg_is_write(call: ast.Call) -> bool:
    """open(...) / .open(...) の mode 引数 (2nd positional or mode=) が write-mode か。"""
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        return _is_write_mode(call.args[1].value)
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return _is_write_mode(kw.value.value)
    # mode 不明 (変数) の open は read 既定と解釈しない = 保守的に write 候補とする…と誤検出が増える。
    # open は既定 'r' なので mode 定数が無ければ read とみなす (write は必ず mode 定数を伴う慣習)。
    return False


def _sink_target(call: ast.Call) -> ast.expr | None:
    """write sink 呼出しから「出力先 (destination) path 式」ノードを取り出す (非 sink は None)。"""
    func = call.func
    if isinstance(func, ast.Attribute):
        method = func.attr
        if method in _WRITE_METHODS:
            return func.value  # Path.write_text/write_bytes → レシーバが出力先
        if method == "open" and _mode_arg_is_write(call):
            return func.value  # Path.open('w') → レシーバが出力先
        if method in _RENAME_METHODS:
            if _is_module_call(func, "os"):
                # os.replace(src, dst) / os.rename(src, dst): dst (2nd) が出力先
                return call.args[1] if len(call.args) >= 2 else None
            # Path.replace(dst) / Path.rename(dst): 引数 dst が出力先
            return call.args[0] if call.args else None
        if method in _SHUTIL_MOVES and _is_module_call(func, "shutil"):
            # shutil.move/copy/copyfile/copy2(src, dst): dst (2nd) が出力先
            return call.args[1] if len(call.args) >= 2 else None
        return None
    if isinstance(func, ast.Name) and func.id == "open" and _mode_arg_is_write(call):
        return call.args[0] if call.args else None  # open(dst, 'w')
    return None


def _is_module_call(func: ast.Attribute, module: str) -> bool:
    return isinstance(func.value, ast.Name) and func.value.id == module


def _collect_forbidden_vars(tree: ast.AST) -> set[str]:
    """forbidden token を含む式から代入された局所変数名を集める (1-hop 追跡)。"""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None:
                continue
            try:
                rendered = ast.unparse(value)
            except Exception:
                continue
            if not _FORBIDDEN.search(rendered):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for tgt in targets:
                if isinstance(tgt, ast.Name):
                    out.add(tgt.id)
    return out


def _line_has_allow(src_lines: list[str], node: ast.AST) -> bool:
    """sink ノードの行範囲に writeguard: allow マーカーがあるか。"""
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", start)
    if start is None:
        return False
    for i in range(start, (end or start) + 1):
        if 0 < i <= len(src_lines) and _ALLOW_MARKER in src_lines[i - 1]:
            return True
    return False


def check_source(text: str, rel: str) -> list[str]:
    """1 script の AST を走査し plan 書込 sink の violation を返す。"""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"{rel}: parse error: {exc}"]
    src_lines = text.splitlines()
    forbidden_vars = _collect_forbidden_vars(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = _sink_target(node)
        if target is None:
            continue
        try:
            rendered = ast.unparse(target)
        except Exception:
            continue
        hit = bool(_FORBIDDEN.search(rendered)) or (
            isinstance(target, ast.Name) and target.id in forbidden_vars
        )
        if not hit:
            continue
        if _line_has_allow(src_lines, node):
            continue
        line = getattr(node, "lineno", "?")
        violations.append(
            f"{rel}:{line}: plan 成果物への書込みの疑い (path={rendered!r})。"
            f"片方向 writer 違反 — plan 更新は producer 限定。正当な非 plan 書込なら "
            f"同行に `# {_ALLOW_MARKER}: <理由>` を付す"
        )
    return violations


def select_targets(scripts_dir: Path) -> list[Path]:
    """task-graph consumer script を選ぶ (既知 7 本 ∪ resolve_build_dir 参照)。"""
    out: list[Path] = []
    for p in sorted(scripts_dir.glob("*.py")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if p.name in _KNOWN_CONSUMERS or "resolve_build_dir" in text:
            out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lint-harness-plan-writeguard.py")
    parser.add_argument("--scripts-dir", default=None,
                        help="省略時 plugins/harness-creator/scripts/")
    args = parser.parse_args(argv)

    scripts_dir = Path(args.scripts_dir) if args.scripts_dir else _default_scripts_dir()
    if not scripts_dir.is_dir():
        print(f"not a directory: {scripts_dir}", file=sys.stderr)
        return 2

    targets = select_targets(scripts_dir)
    if not targets:
        print(f"warning: task-graph consumer script が見つからない: {scripts_dir}", file=sys.stderr)

    all_violations: list[str] = []
    for p in targets:
        rel = str(p.relative_to(scripts_dir.parent.parent.parent)) if _under_repo(p) else p.name
        all_violations += check_source(p.read_text(encoding="utf-8"), rel)

    if all_violations:
        for v in all_violations:
            print(v)
        print(f"\nFAIL: {len(all_violations)} 件の片方向 writer 違反 (S1)", file=sys.stderr)
        return 1
    print(f"OK: {len(targets)} task-graph consumer scripts が plan 非書込 (S1・片方向 writer)")
    return 0


def _under_repo(p: Path) -> bool:
    return "plugins" in p.parts


if __name__ == "__main__":
    sys.exit(main())
