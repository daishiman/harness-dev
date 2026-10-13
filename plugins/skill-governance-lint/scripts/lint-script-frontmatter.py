#!/usr/bin/env python3
# /// script
# name: lint-script-frontmatter
# version: 0.3.0
# purpose: 28章§7 規格に従い、指定したディレクトリ配下の *.py（tests なども含む）と指定した .py ファイルの PEP 723 frontmatter 必須キーを検証する meta-lint
# inputs:
#   - argv: 検査対象のディレクトリか .py ファイル（既定 plugins）。-h/--help は使い方を出して 0。他の - で始まる引数・存在しないパス・.py でないファイルは 2
# outputs:
#   - stdout: 違反一覧（path: missing_key1, missing_key2 ... / 読めないファイルは path: unreadable (例外名)）
#   - exit: 0=OK / 1=違反あり / 2=usage error
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: none
# ///
"""scripts/*.py の PEP 723 inline frontmatter を機械検証する。"""
from __future__ import annotations
import sys
from pathlib import Path

REQUIRED_KEYS = ("name", "purpose", "inputs", "outputs", "contexts", "network", "write-scope", "dependencies")
EXEMPT_NAMES = {"__init__.py"}
# PENDING_FRONTMATTER: doc/migration/phase3/pending-frontmatter.md の移行計画に沿って段階補完中。
# このセットに含まれるファイルは frontmatter 不備でも警告にダウングレードする（EXCEPTION 扱い）。
PENDING_FILES = {
    "render-findings-score.py",
    "resolve-brief-to-category.py",
    "diff-rubric-impact.py",
    "lint-rubric-violation.py",
    "pre-commit-secret-scan.py",
    "guard-change-category.py",
}


def extract_frontmatter(text: str) -> dict | None:
    lines = text.splitlines()
    in_block = False
    keys: dict = {}
    last_key = None
    for ln in lines:
        s = ln.strip()
        if s == "# /// script":
            in_block = True
            continue
        if in_block and s == "# ///":
            return keys
        if in_block:
            body = ln[1:].lstrip() if ln.startswith("#") else ""
            if not body:
                continue
            if ":" in body and not body.lstrip().startswith("-"):
                k, _, v = body.partition(":")
                k = k.strip()
                keys[k] = v.strip()
                last_key = k
            elif body.lstrip().startswith("-") and last_key:
                keys[last_key] = keys.get(last_key, "") + " " + body.strip()
    return None


def _iter_scripts(targets: list[Path]):
    """検査する .py を順に返す。ディレクトリは配下を再帰で、ファイルはそのものを。同じファイルは1回だけ。

    tests/<script>.py/ のように .py で終わるディレクトリもあるので、rglob の結果からディレクトリを除く。
    壊れた symlink はディレクトリではないので残り、読めないファイルとして報告される。
    """
    seen: set[Path] = set()
    for t in targets:
        found = [t] if t.is_file() else sorted(t.rglob("*.py"))
        for p in found:
            if p.name in EXEMPT_NAMES or "__pycache__" in p.parts or p in seen or p.is_dir():
                continue
            seen.add(p)
            yield p


USAGE = "usage: lint-script-frontmatter.py [DIR|FILE.py ...]  (既定 plugins)"


def main() -> int:
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(USAGE)
        print(__doc__)
        return 0
    unknown = [a for a in args if a.startswith("-")]
    if unknown:
        # オプションの綴り違いをディレクトリ名と見なして OK を返すと、CI が何も検査せずに通る
        print(f"unknown option: {' '.join(unknown)}\n{USAGE}", file=sys.stderr)
        return 2
    targets = [Path(p) for p in args] if args else [Path("plugins")]
    # 名前の変更や打ち間違いで対象が消えたとき、何も検査せずに OK を返すと CI が素通りする
    bad = [f"not found: {t}" for t in targets if not t.exists()]
    bad += [f"not a .py file: {t}" for t in targets if t.is_file() and t.suffix != ".py"]
    if bad:
        print("\n".join(bad) + f"\n{USAGE}", file=sys.stderr)
        return 2

    violations = []
    pending = []
    checked = 0
    for p in _iter_scripts(targets):
        checked += 1
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            # 壊れた symlink や非 UTF-8 は traceback で止めず、違反として報告する
            violations.append(f"{p}: unreadable ({type(e).__name__})")
            continue
        fm = extract_frontmatter(text)
        if fm is None:
            msg = f"{p}: missing # /// script ... # /// block"
        else:
            missing = [k for k in REQUIRED_KEYS if k not in fm]
            if not missing:
                continue
            msg = f"{p}: missing keys: {', '.join(missing)}"
        if p.name in PENDING_FILES:
            pending.append("PENDING " + msg)
        else:
            violations.append(msg)

    for w in pending:
        print(w, file=sys.stderr)
    if violations:
        for v in violations:
            print(v)
        print(f"\nchecked={checked} violations={len(violations)} pending={len(pending)}", file=sys.stderr)
        return 1
    print(f"OK (checked={checked} pending={len(pending)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
