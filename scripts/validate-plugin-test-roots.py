#!/usr/bin/env python3
# /// script
# name: validate-plugin-test-roots
# purpose: plugin 配下の全 pytest test_root を変更影響順の上限付き並列 subprocess で実行し、分離 log と集約結果を返す。
# inputs:
#   - discover_repo_tests.group_plugin_tests が列挙する plugin test roots
#   - git HEAD の changed paths (優先順のみに使用)
# outputs:
#   - stdout: test_root ごとの非インターリーブ log + 全件集約サマリ
# contexts: [C, E]
# network: false
# write-scope: temporary-log-only
# dependencies: [pytest]
# requires-python: ">=3.10"
# ///
"""CI 用 plugin pytest runner。

探索は ``discover_repo_tests.group_plugin_tests`` を SSOT とし、各 test_root は
従来通り個別 subprocess + 個別 cwd で実行する。変更 test_root / plugin を
先に submit し、最大4並列で全 root を最後まで実行する。出力は root ごとの
一時 file に分離し、完了した root 単位で GitHub log へ流す。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
from typing import Callable, NamedTuple, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import discover_repo_tests as discovery  # noqa: E402


MAX_WORKERS = 4


class TestGroup(NamedTuple):
    index: int
    priority: int
    test_root: str
    args: tuple[str, ...]


class TestResult(NamedTuple):
    item: TestGroup
    returncode: int
    seconds: float
    log_path: Path


def _plugin_prefix(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if len(parts) >= 2 and parts[0] == "plugins":
        return PurePosixPath(*parts[:2]).as_posix()
    return None


def _priority(test_root: str, changed_files: set[str]) -> int:
    root_prefix = test_root.rstrip("/") + "/"
    if any(path == test_root or path.startswith(root_prefix) for path in changed_files):
        return 0
    plugin_prefix = _plugin_prefix(test_root)
    if plugin_prefix:
        plugin_prefix += "/"
        if any(path.startswith(plugin_prefix) for path in changed_files):
            return 1
    return 2


def prioritize_groups(
    groups: dict[str, list[str]], changed_files: set[str]
) -> list[TestGroup]:
    """changed root -> same plugin -> others の順に安定ソートする。"""
    ordered = sorted(
        (
            _priority(test_root, changed_files),
            test_root,
            tuple(sorted(set(args))),
        )
        for test_root, args in groups.items()
    )
    return [
        TestGroup(index, priority, test_root, args)
        for index, (priority, test_root, args) in enumerate(ordered)
    ]


def discover_changed_files(repo_root: Path) -> set[str]:
    """HEAD が持つ差分 path を取得。失敗時は全 root 同順位で実行。"""
    result = subprocess.run(
        ["git", "show", "--format=", "--name-only", "--first-parent", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("[WARN] changed paths unavailable; falling back to lexical order", file=sys.stderr)
        return set()
    return {
        PurePosixPath(line.strip()).as_posix()
        for line in result.stdout.splitlines()
        if line.strip()
    }


def _log_path(log_dir: Path, item: TestGroup) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", item.test_root).strip("-")
    return log_dir / f"{item.index:03d}-{slug}.log"


def run_test_root(item: TestGroup, *, repo_root: Path, log_dir: Path) -> TestResult:
    """1 test_root を従来と同じ cwd / pytest args で実行する。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = _log_path(log_dir, item)
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *item.args, "-q"],
            cwd=repo_root / item.test_root,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return TestResult(item, result.returncode, time.monotonic() - started, log_path)


RunOne = Callable[..., TestResult]
OnComplete = Callable[[TestResult], None]


def run_groups(
    plan: Sequence[TestGroup],
    *,
    repo_root: Path,
    log_dir: Path,
    max_workers: int = MAX_WORKERS,
    run_one: RunOne = run_test_root,
    on_complete: OnComplete | None = None,
) -> list[TestResult]:
    """全rootを省略せず実行し、結果をdeterministic plan順に集約する。"""
    if not plan:
        return []
    workers = max(1, min(int(max_workers), MAX_WORKERS, len(plan)))
    results: dict[int, TestResult] = {}
    log_dir.mkdir(parents=True, exist_ok=True)

    def guarded(item: TestGroup) -> TestResult:
        try:
            return run_one(item, repo_root=repo_root, log_dir=log_dir)
        except BaseException:  # runner 自体の例外も他 root を skip させない
            log_path = _log_path(log_dir, item)
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
            return TestResult(item, 2, 0.0, log_path)

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="plugin-pytest") as pool:
        future_to_item = {pool.submit(guarded, item): item for item in plan}
        for future in as_completed(future_to_item):
            result = future.result()
            results[result.item.index] = result
            if on_complete is not None:
                on_complete(result)

    return [results[item.index] for item in plan]


def emit_result(result: TestResult) -> None:
    status = "PASS" if result.returncode == 0 else "FAIL"
    title = f"pytest {result.item.test_root} [{status}, {result.seconds:.1f}s]"
    print(f"::group::{title}")
    try:
        print(result.log_path.read_text(encoding="utf-8"), end="")
    except OSError as exc:
        print(f"unable to read isolated log: {exc}")
    print("::endgroup::")
    if result.returncode:
        print(
            f"::error title=plugin pytest failed::{result.item.test_root} "
            f"exited {result.returncode}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=SCRIPT_DIR.parent,
        help="repository root (default: script parent)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        choices=range(1, MAX_WORKERS + 1),
        default=MAX_WORKERS,
        help=f"bounded parallel workers (1-{MAX_WORKERS}, default: {MAX_WORKERS})",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="priority input override; repeatable (default: git HEAD diff)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print deterministic execution plan without running pytest",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # GitHub Actions の pipe stdout でも、完了した test-root の log を
    # プロセス終了までbufferせずすぐ表示する。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    # plugin existence is checked explicitly; discovery remains the shared SSOT.
    plugins_root = Path("plugins")
    if not (repo_root / plugins_root).is_dir():
        print(f"ERROR: plugins root not found: {repo_root / plugins_root}", file=sys.stderr)
        return 1
    groups = discovery.group_plugin_tests(repo_root)
    if not groups:
        print(
            "ERROR: no plugin test files discovered under "
            "plugins/**/{test_*.py,*_test.py}",
            file=sys.stderr,
        )
        return 1

    changed_files = set(args.changed_file) or discover_changed_files(repo_root)
    plan = prioritize_groups(groups, changed_files)
    counts = {priority: sum(item.priority == priority for item in plan) for priority in range(3)}
    print(
        f"plugin pytest plan: roots={len(plan)} workers={args.workers} "
        f"priority(exact/plugin/other)={counts[0]}/{counts[1]}/{counts[2]}"
    )
    for item in plan:
        print(f"  [{item.priority}] {item.test_root} ({len(item.args)} files)")
    if args.list:
        return 0

    temp_parent = os.environ.get("RUNNER_TEMP")
    with tempfile.TemporaryDirectory(prefix="plugin-test-logs-", dir=temp_parent) as temp_dir:
        results = run_groups(
            plan,
            repo_root=repo_root,
            log_dir=Path(temp_dir),
            max_workers=args.workers,
            on_complete=emit_result,
        )
        failures = [result for result in results if result.returncode]
        elapsed = sum(result.seconds for result in results)
        wall = max((result.seconds for result in results), default=0.0)
        print(
            f"plugin pytest summary: roots={len(results)} pass={len(results) - len(failures)} "
            f"fail={len(failures)} cumulative={elapsed:.1f}s longest-root={wall:.1f}s"
        )
        if failures:
            print("failed roots:", file=sys.stderr)
            for result in failures:
                print(
                    f"  - {result.item.test_root}: exit={result.returncode} "
                    f"time={result.seconds:.1f}s",
                    file=sys.stderr,
                )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
