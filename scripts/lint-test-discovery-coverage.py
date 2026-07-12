#!/usr/bin/env python3
# /// script
# name: lint-test-discovery-coverage
# purpose: repo 全域の全 test_*.py / *_test.py が CI のテスト実行で 1 回以上到達することを fail-closed 検証するメタ lint。境界外 (tests/・plugins/ 以外) に置かれた test の無言未実行を封鎖する。
# inputs:
#   - repo 全域の test_*.py / *_test.py (discover_repo_tests 経由)
#   - .github/workflows/harness-creator-kit-ci.yml (到達 root の実行 step 検証; 不在なら skip)
# outputs:
#   - stdout: 探索サマリ + OK
#   - stderr: orphan test と修正方法
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""全 test が CI で実行される機械保証 (test discovery coverage)。

背景 (elegant-review 2026-06-30, 3 analyst 収束 LS-F1 / SS-02 / SS-05):
  CI のテスト探索は harness-creator-kit-ci.yml の 2 機構 (機構A: `pytest tests/` /
  機構B: plugins/ walk) に分裂し、和集合 = 「tests/ または plugins/ 配下」。
  この境界の外 (repo-root 直下・scripts/・doc/・新規 top-level) に置いた test は
  どちらにも拾われず無言で未実行になる。にもかかわらず、実 test 集合が CI 到達集合に
  含まれることを保証する機械層が repo に存在しなかった (現状 orphan=0 だが fail-closed
  ガード不在で、将来サイレントに腐りうる)。

  本 lint は discover_repo_tests を SSOT に、(1) 全 test ファイルが CI 到達集合
  (discover_repo_tests.CI_REACHABLE_TOP_LEVEL) に属する (orphan=0) ことと、
  (2) harness-creator-kit-ci.yml が各到達 root を実際に pytest 実行している ことを fail-closed
  検証する。判定は *到達集合への set membership* で、test ファイル数や coverage% とは
  混ぜない (Goodhart 回避; coverage% は validate-harness-coverage.py の責務)。

  既存 lint-plugin-lint-coverage.py が「全 plugin が skill lint 配線済か」を保証するのと
  同型の *メタ被覆 lint* であり、本 lint は「全 test が CI 実行被覆済か」を保証する。

例外 (allowlist): CI で意図的に実行しない test (例: 手動専用 fixture) は
ALLOWLIST に repo-relative パスと非空の理由を宣言する。orphan でなくなった/存在しない
stale エントリはエラー (掃除を強制)。

Usage:
  lint-test-discovery-coverage.py [--repo-root /path/to/repo]

Exit 0 = ok, 1 = violation, 2 = usage error。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discover_repo_tests as drt  # noqa: E402

# 例外宣言: {repo-relative posix パス: 理由 (非空必須)}。
# 「なぜ CI で実行しない/到達集合の外に置くのか」と検出日を残し後日是正を追跡する。
# 現状は空 (orphan=0)。将来 tests/・plugins/ 外に test を置く正当な理由が生じたときのみ追加。
ALLOWLIST: dict[str, str] = {}

# 各到達 top-level が CI で実際に実行されている証跡 (harness-creator-kit-ci.yml 内の耐久的部分文字列)。
# 二次ガード: orphan=0 (test が root 配下にある) を満たしても、その root を CI が実行
# しなくなれば test は走らない。両方を閉じて「全 test が CI 実行される」を保証する。
CI_RUN_EVIDENCE: dict[str, tuple[str, ...]] = {
    # 機構A: repo-root tests/ を pytest で再帰実行する step
    "tests": ("pytest tests/",),
    # 機構B: plugins/ を os.walk で収集し per-plugin pytest を subprocess 実行する step
    "plugins": ('Path("plugins")', '"-m", "pytest"'),
}

CI_WORKFLOW_REL = ".github/workflows/harness-creator-kit-ci.yml"


def _join_continuations(text: str) -> str:
    """shell backslash 行継続を 1 行に連結する (run-ci-checks 等の折返し対策)。"""
    return re.sub(r"\\\s*\n", " ", text)


def check_orphans(
    root: Path, allowlist: dict[str, str] | None = None
) -> tuple[list[str], list[str]]:
    """(errors, report) を返す。orphan test と allowlist の健全性を検査する。"""
    allowlist = ALLOWLIST if allowlist is None else allowlist
    errors: list[str] = []
    report: list[str] = []

    all_tests = drt.discover_test_files(root)
    orphans = {str(p) for p in drt.orphan_test_files(root)}

    # allowlist 健全性: 理由は非空必須 / stale (もはや orphan でない) は掃除を強制
    for rel, reason in allowlist.items():
        if not str(reason).strip():
            errors.append(f"allowlist エントリ {rel!r} に理由が無い (理由必須)")
        if rel not in orphans:
            errors.append(
                f"allowlist エントリ {rel!r} は既に CI 到達集合内 (または不在) で "
                "orphan でない (stale)。scripts/lint-test-discovery-coverage.py の "
                "ALLOWLIST から削除すること"
            )

    real_orphans = sorted(orphans - set(allowlist))
    for rel in real_orphans:
        errors.append(
            f"{rel}: CI のテスト実行で到達しない位置に test がある "
            f"(到達 top-level = {list(drt.CI_REACHABLE_TOP_LEVEL)})。"
            "修正方法: (1) この test を tests/ または plugins/<plugin>/ 配下へ移す "
            "(CI 機構A/Bが拾う)、(2) CI 到達 root を増やすなら "
            "discover_repo_tests.CI_REACHABLE_TOP_LEVEL と harness-creator-kit-ci.yml の実行 step を "
            "連動更新する、(3) 意図的に CI 非実行なら ALLOWLIST に理由付きで宣言する"
        )

    reachable = len(all_tests) - len(orphans)
    report.append(
        f"test files: {len(all_tests)} (CI 到達 {reachable} / orphan {len(orphans)} / "
        f"allowlist {len(allowlist)})"
    )
    return errors, report


def check_evidence_parity() -> tuple[list[str], list[str]]:
    """CI_RUN_EVIDENCE のキー集合 == discover_repo_tests.CI_REACHABLE_TOP_LEVEL を強制する。

    両者が drift すると「到達 root と宣言したが CI 実行証跡を検証しない」死角が生じる
    (例: CI_REACHABLE_TOP_LEVEL に root を足したが CI_RUN_EVIDENCE 追加を忘れると、
    その root 配下の test は orphan 判定を素通りしつつ CI 実行は無検証になる)。
    この設定-設定間の不変条件を fail-closed で固定する (approver 指摘 / SSOT drift 封じ)。
    """
    errors: list[str] = []
    reachable = set(drt.CI_REACHABLE_TOP_LEVEL)
    evidenced = set(CI_RUN_EVIDENCE)
    if reachable != evidenced:
        missing = reachable - evidenced
        extra = evidenced - reachable
        errors.append(
            "CI_RUN_EVIDENCE のキーが discover_repo_tests.CI_REACHABLE_TOP_LEVEL と不一致 "
            f"(到達宣言のみ={sorted(missing)} / 証跡のみ={sorted(extra)})。"
            "両者を連動更新すること (到達 root には必ず CI 実行証跡を対で定義する)"
        )
    return errors, [f"evidence parity: OK ({sorted(reachable)})"] if not errors else []


def check_ci_runs_roots(root: Path) -> tuple[list[str], list[str]]:
    """harness-creator-kit-ci.yml が各到達 root を実際に pytest 実行しているか (二次ガード)。"""
    errors: list[str] = []
    report: list[str] = []
    ci_path = root / CI_WORKFLOW_REL
    if not ci_path.is_file():
        report.append(f"skip: {CI_WORKFLOW_REL} 不在 (repo 外文脈) — CI 実行 step 検証は省略")
        return errors, report
    ci = _join_continuations(ci_path.read_text(encoding="utf-8"))
    for top, evidences in CI_RUN_EVIDENCE.items():
        missing = [ev for ev in evidences if ev not in ci]
        if missing:
            errors.append(
                f"到達 root '{top}/' を CI が実行する証跡が harness-creator-kit-ci.yml に無い "
                f"(欠落: {missing})。'{top}/' 配下の test が無言で未実行になりうる。"
                "CI 実行 step を復元するか、root を廃止するなら "
                "discover_repo_tests.CI_REACHABLE_TOP_LEVEL と CI_RUN_EVIDENCE を連動更新する"
            )
        else:
            report.append(f"CI runs '{top}/': OK")
    return errors, report


def main(argv: list[str]) -> int:
    root = drt.repo_root_default()
    args = list(argv)
    if "--repo-root" in args:
        idx = args.index("--repo-root")
        if idx + 1 >= len(args):
            print("usage: lint-test-discovery-coverage.py [--repo-root /path]", file=sys.stderr)
            return 2
        root = Path(args[idx + 1]).resolve()

    errors: list[str] = []
    report: list[str] = []
    parity_errs, parity_rep = check_evidence_parity()
    errors.extend(parity_errs)
    report.extend(parity_rep)
    for fn in (check_orphans, check_ci_runs_roots):
        errs, rep = fn(root)
        errors.extend(errs)
        report.extend(rep)

    for line in report:
        print(f"  {line}")
    if errors:
        for e in errors:
            print(f"NG: {e}", file=sys.stderr)
        return 1
    print("ok: test discovery coverage (全 test が CI 実行被覆内 / orphan 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
