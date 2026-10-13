#!/usr/bin/env python3
# /// script
# name: validate-design-rubric
# version: 0.2.0
# purpose: Inject the registered UBM L1 into the existing design-rubric evaluator.
# inputs: [--repo-root, --target]
# outputs:
#   - stdout: 採点できたとき (子が exit 0 で passed を持つ JSON object を出したとき) だけ render-findings-score.py の JSON をそのまま流す
#   - stderr: 子の stderr をそのまま流した後に印の行を出す。routing 不正は "UBM_REVIEW_ROUTING_INVALID: ..."、子の非0終了は
#             "UBM_REVIEW_EVALUATOR_EXIT=<code> ..."、子の異常終了は加えて "UBM_REVIEW_EVALUATOR_CRASHED: ..." の行。
#             引数不正では argparse の usage の後に印の行が出るので、先頭行でなく行単位で探す
#   - exit: 0=採点できた (合否は JSON の passed) / 1=子が契約の exit 1 を返した (--rubric-refs の先頭が L0 でない) /
#           2=子が契約の exit 2 を返した (入力エラー)・routing 不正 (repo-root がこの runner を含まない、registry・plugin.json・
#           L1 の欠落や不正、対象外の target、L0・L2・render-findings-score.py の欠落、子を起動できない、引数不正)・
#           子の異常終了 (signal・未捕捉例外の Traceback・0/1/2 以外の code・exit 0 なのに passed を持つ JSON object でない stdout)。
#           0/1/2 以外は返さない。どの 2 かは stderr の印で区別する
# contexts: [A, B]
# requires-python: ">=3.9"
# network: false
# write-scope: none
# dependencies: []
# ///
"""UBM-only review routing; semantic quality remains an independent review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

DOMAIN = "ubm-goal-setting"
# 子の未捕捉例外は CPython が stderr にこの行を書いて exit 1 にする。契約の exit 1 (L0 の順序違反) と分ける印。
TRACEBACK_HEADER = "Traceback (most recent call last):"


def load_object(path: Path, label: str) -> dict:
    """Fail closed with ValueError when the JSON is not an object, instead of an AttributeError later."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return data


def evaluation_command(repo_root: Path, target: Path) -> list[str]:
    root = repo_root.resolve(strict=True)
    plugin = (root / "plugins" / DOMAIN).resolve(strict=True)
    if plugin != Path(__file__).resolve().parents[1]:
        raise ValueError("repo-root does not contain this UBM evaluator runner")
    manifest = load_object(plugin / ".claude-plugin/plugin.json", "plugin.json")
    if manifest.get("name") != DOMAIN:
        raise ValueError("UBM plugin identity mismatch")
    source = target.resolve(strict=True)
    if (source.name != "SKILL.md" or source.parent.parent != plugin / "skills"
            or not source.parent.name.startswith("run-ubm-")):
        raise ValueError("target must be a UBM entrypoint in this plugin")
    registry = load_object(root / "plugins/skill-governance-config/config/rubric-registry.json", "rubric registry")
    rubrics = registry.get("rubrics", [])
    if not isinstance(rubrics, list) or not all(isinstance(item, dict) for item in rubrics):
        raise ValueError("rubric registry rubrics must be a list of objects")
    entries = [item for item in rubrics if item.get("domain") == DOMAIN]
    if len(entries) != 1:
        raise ValueError("exactly one registered UBM L1 is required")
    entry = entries[0]
    l0 = root / "plugins/harness-creator/skills/ref-skill-design-rubric/references/rubric.json"
    registered_path = root / entry["rubric"]
    l1 = registered_path.resolve(strict=True)
    expected_l1 = plugin / "skills/run-ubm-knowledge-sync/references/rubric.json"
    if (registered_path != expected_l1 or expected_l1.is_symlink()
            or not expected_l1.is_file() or l1 != expected_l1
            or not l1.is_relative_to(plugin)):
        raise ValueError("registered UBM L1 must resolve to its declared local owner")
    data = load_object(l1, "registered UBM L1")
    if (entry.get("layer") != "L1" or data.get("layer") != "L1"
            or data.get("domain") != DOMAIN
            or entry.get("merge_strategy") != "deep-merge"
            or entry.get("conflict_policy") != "most-specific-wins"):
        raise ValueError("invalid registered UBM L1 composition contract")
    evaluator = root / "plugins/harness-creator/skills/assign-skill-design-evaluator"
    l2 = evaluator / "references/rubric.json"
    renderer = evaluator / "scripts/render-findings-score.py"
    missing = [str(path) for path in (l0, l2, renderer) if not path.is_file()]
    if missing:
        # Otherwise the child's own exit 2 would be reported as an evaluator verdict, not a routing failure.
        raise ValueError(f"evaluator inputs are missing: {', '.join(missing)}")
    return [sys.executable, str(renderer),
            "--rubric-refs", str(l0), str(l1), str(l2), "--target", str(source),
            "--merge-strategy", "deep-merge", "--conflict-policy", "most-specific-wins",
            "--emit-hash"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        if exc.code:  # usage error; --help exits 0 without a marker
            print("UBM_REVIEW_ROUTING_INVALID: invalid arguments", file=sys.stderr)
        raise
    try:
        command = evaluation_command(args.repo_root, args.target)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(f"UBM_REVIEW_ROUTING_INVALID: {exc}", file=sys.stderr)
        return 2
    try:
        child = subprocess.run(command, check=False, capture_output=True)
    except OSError as exc:
        print(f"UBM_REVIEW_ROUTING_INVALID: evaluator could not start: {exc}", file=sys.stderr)
        return 2
    returncode = child.returncode
    child_err = child.stderr.decode("utf-8", errors="replace")
    sys.stderr.write(child_err)
    crash = crash_reason(returncode, child.stdout, child_err)
    if returncode != 0:
        # The child also exits 2 on usage errors; name the source so it is not read as a routing failure.
        print(f"UBM_REVIEW_EVALUATOR_EXIT={returncode} (render-findings-score.py)", file=sys.stderr)
    if crash is not None:
        # A crashed child has no verdict; a negative code would also leak as 256-n from SystemExit.
        print(f"UBM_REVIEW_EVALUATOR_CRASHED: {crash}", file=sys.stderr)
        return 2
    if returncode == 0:
        sys.stdout.write(child.stdout.decode("utf-8"))
    return returncode


def crash_reason(returncode: int, stdout: bytes, stderr: str) -> str | None:
    """子の終わり方が evaluator の契約 (0=採点 JSON / 1 / 2) の外なら、その理由を返す。"""
    if returncode < 0:
        return f"killed by signal {-returncode}"
    if returncode not in (0, 1, 2):
        return f"exit {returncode} is outside the evaluator contract 0/1/2"
    if TRACEBACK_HEADER in stderr.splitlines():
        return "uncaught exception (Traceback)"
    if returncode == 0:
        try:
            result = json.loads(stdout.decode("utf-8"))
        except (ValueError, RecursionError):
            return "exit 0 without a JSON verdict on stdout"
        if not isinstance(result, dict) or not isinstance(result.get("passed"), bool):
            return "exit 0 but stdout is not a JSON object with a boolean passed"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
