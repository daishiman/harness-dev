#!/usr/bin/env python3
# /// script
# name: discover-repo-tests
# purpose: repo 全域の pytest テストファイルを列挙し CI が実行する到達集合を単一 SSOT で定義する。lint-test-discovery-coverage と (将来は) CI 双方の消費元。
# inputs:
#   - repo 全域の test_*.py / *_test.py (除外ディレクトリを剪定)
# outputs:
#   - stdout: --list / --orphans / --ci-plan に応じた一覧 (text または JSON)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""repo 全域のテスト探索 SSOT (single source of truth)。

背景 (elegant-review 2026-06-30):
  CI のテスト探索は harness-creator-kit-ci.yml の 2 機構に分裂している —
    機構A: `pytest tests/`(repo-root tests/ を再帰) + plugins/skill-governance-lint/tests/
    機構B: root=Path("plugins") の os.walk で test_*.py / *_test.py を収集
  両者の和集合 = 「repo-relative パスの先頭成分が tests/ または plugins/」。
  この境界の外 (repo-root 直下 / scripts/ / doc/ / 新規 top-level dir) に置かれた
  test は、どちらの機構にも拾われず *無言で未実行* になりうる。過去 harness-creator-kit-ci.yml に
  「これが無いと一度も実行されず保証が無言で腐る」という反応的な穴埋めコメントが
  3 箇所再発しているのは、探索契約が検証可能な SSOT になっていない症状である。

  本 module は探索集合と CI 到達モデルを唯一の真実として定義し、
  lint-test-discovery-coverage.py が「実 test 集合 ⊆ CI 到達集合」を fail-closed
  検証する基盤を与える。判定は *ファイル数* でなく *到達集合への set membership*
  で行う (test ファイルを stub で水増ししても membership は満たせない = Goodhart 回避)。

CLI:
  discover_repo_tests.py --list      # 全 test ファイル (repo-relative posix, 1 行 1 件)
  discover_repo_tests.py --orphans   # CI 到達集合の外にある test (空が正常)
  discover_repo_tests.py --ci-plan   # 機構B の per-plugin グルーピング (JSON)
  discover_repo_tests.py --json      # {tests, orphans, reachable_top_level} を JSON で
  オプション --repo-root /path で起点を上書き (既定 = この script の親の親)。

Exit 0 = ok, 2 = usage error。--orphans は orphan があっても exit 0 (列挙のみ;
fail-closed 判定は lint-test-discovery-coverage.py の責務)。
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
from pathlib import Path, PurePosixPath

# walk 時に剪定するディレクトリ名。VCS / cache / 仮想環境 / vendored 3rd-party を除外する。
# (これらの配下にある test は「我々が書いた CI 対象テスト」ではないため探索母集合に入れない。)
EXCLUDE_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".worktrees",
        ".venv",
        "venv",
        "site-packages",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "build",
        "dist",
        "vendor",
    }
)

# pytest が収集するテストファイル名パターン (harness-creator-kit-ci.yml 機構B と同一規約)。
TEST_GLOBS: tuple[str, ...] = ("test_*.py", "*_test.py")

# CI がテストを実行する到達 top-level。各成分が harness-creator-kit-ci.yml の実行 step に対応する:
#   "tests"   -> 機構A: `python3 -m pytest tests/ ...` が tests/ を再帰実行
#   "plugins" -> 機構B: root=Path("plugins") の os.walk が plugins/ 配下を収集実行
# repo-relative パスの *先頭成分* がこの集合に属する test が「CI 到達」とみなされる。
# この定数を更新するときは harness-creator-kit-ci.yml の実行 step も必ず連動させること
# (連動の機械検証は run-plugin-dev-plan/tests/test_ci_integration.py へ将来昇格)。
CI_REACHABLE_TOP_LEVEL: tuple[str, ...] = ("tests", "plugins")


def repo_root_default() -> Path:
    """この script (scripts/discover_repo_tests.py) から見た repo root。"""
    return Path(__file__).resolve().parents[1]


def _is_test_filename(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in TEST_GLOBS)


def discover_test_files(root: Path) -> list[PurePosixPath]:
    """root 配下の全 test ファイルを repo-relative posix パスで返す (除外 dir を剪定)。"""
    root = root.resolve()
    found: list[PurePosixPath] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # in-place 書換えで os.walk の降下を剪定する。
        dirnames[:] = [
            d
            for d in dirnames
            if d not in EXCLUDE_DIR_NAMES
            and not (Path(dirpath) / d / ".git").exists()
        ]
        base = Path(dirpath)
        for filename in filenames:
            if not _is_test_filename(filename):
                continue
            rel = (base / filename).relative_to(root)
            found.append(PurePosixPath(rel.as_posix()))
    return sorted(found, key=str)


def is_ci_reachable(rel: PurePosixPath) -> bool:
    """repo-relative パスが CI のテスト実行で到達する位置にあるか。"""
    return bool(rel.parts) and rel.parts[0] in CI_REACHABLE_TOP_LEVEL


def orphan_test_files(root: Path) -> list[PurePosixPath]:
    """CI 到達集合の外にある test ファイル (= 無言で未実行になりうるもの)。"""
    return [rel for rel in discover_test_files(root) if not is_ci_reachable(rel)]


def group_plugin_tests(root: Path) -> dict[str, list[str]]:
    """機構B (plugins/ walk) のグルーピングを再現する SSOT 実装。

    harness-creator-kit-ci.yml の per-plugin pytest と同一の規約で
    {test_root(repo-relative posix): [pytest 引数(test_root 相対 posix)]} を返す。
    将来 CI heredoc と test_ci_integration.py がこの関数を import して
    探索ロジックの二重定義を解消するための土台 (現時点では未配線)。
    """
    plugins_root = (root / "plugins").resolve()
    groups: dict[str, list[str]] = {}
    if not plugins_root.is_dir():
        return groups
    for dirpath, dirnames, filenames in os.walk(plugins_root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in EXCLUDE_DIR_NAMES
            and not (Path(dirpath) / d / ".git").exists()
        ]
        base = Path(dirpath)
        for filename in filenames:
            if not _is_test_filename(filename):
                continue
            rel = (base / filename).relative_to(root)
            parts = rel.parts
            if "tests" in parts:
                idx = parts.index("tests")
                test_root = PurePosixPath(*parts[:idx]).as_posix()
                test_arg = PurePosixPath(*parts[idx:]).as_posix()
            else:
                test_root = rel.parent.as_posix()
                test_arg = rel.name
            groups.setdefault(test_root, []).append(test_arg)
    return {k: sorted(set(v)) for k, v in sorted(groups.items())}


def _parse_repo_root(argv: list[str]) -> tuple[Path, list[str]]:
    rest = list(argv)
    root = repo_root_default()
    if "--repo-root" in rest:
        idx = rest.index("--repo-root")
        if idx + 1 >= len(rest):
            raise ValueError("--repo-root にパス引数が必要")
        root = Path(rest[idx + 1]).resolve()
        del rest[idx : idx + 2]
    return root, rest


def main(argv: list[str]) -> int:
    try:
        root, rest = _parse_repo_root(argv)
    except ValueError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    mode = rest[0] if rest else "--list"
    if mode == "--list":
        for rel in discover_test_files(root):
            print(rel)
    elif mode == "--orphans":
        for rel in orphan_test_files(root):
            print(rel)
    elif mode == "--ci-plan":
        print(json.dumps(group_plugin_tests(root), indent=2, ensure_ascii=False))
    elif mode == "--json":
        payload = {
            "reachable_top_level": list(CI_REACHABLE_TOP_LEVEL),
            "tests": [str(p) for p in discover_test_files(root)],
            "orphans": [str(p) for p in orphan_test_files(root)],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"usage error: unknown mode {mode!r}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
