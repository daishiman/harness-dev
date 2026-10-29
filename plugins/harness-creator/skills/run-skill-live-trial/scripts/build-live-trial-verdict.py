#!/usr/bin/env python3
"""Build the verdict and always reap the exactly-owned tmux session."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finalize(
    *, session: str, run_id: str, owner_pid: int, verdict_args: list[str],
    backend=None, verdict=None,
) -> int:
    """Run verdict generation with cleanup in a finally block."""
    backend = backend or _load_sibling("live-trial-backend")
    verdict = verdict or _load_sibling("live-trial-verdict")
    if (
        not backend.valid_session_name(session)
        or not backend.valid_run_id(run_id)
        or not backend.session_belongs_to_run(session, run_id)
        or owner_pid <= 0
    ):
        print("[ERROR] invalid session/run-id/owner-pid cleanup ownership", file=sys.stderr)
        return 2
    result = 1
    cleanup_error: Exception | None = None
    try:
        try:
            result = int(verdict.main(verdict_args))
        except SystemExit as exc:
            result = int(exc.code) if isinstance(exc.code, int) else 1
    finally:
        try:
            backend.reap(run_id, owner_pid)
            if backend.has_session(session):
                raise RuntimeError(
                    "session remains after scoped reap; tmux ownership metadata did not match"
                )
        except Exception as exc:  # fail-closed: verdict success cannot hide cleanup failure
            cleanup_error = exc
    if cleanup_error is not None:
        print(f"[ERROR] live-trial cleanup failed: {cleanup_error}", file=sys.stderr)
        return 1
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--owner-pid", required=True, type=int)
    parser.add_argument(
        "verdict_args", nargs=argparse.REMAINDER,
        help="`--` に続けて live-trial-verdict.py の引数を渡す",
    )
    args = parser.parse_args(argv)
    verdict_args = list(args.verdict_args)
    if verdict_args[:1] == ["--"]:
        verdict_args = verdict_args[1:]
    if not verdict_args:
        parser.error("`--` の後に verdict arguments が必要")
    return finalize(
        session=args.session,
        run_id=args.run_id,
        owner_pid=args.owner_pid,
        verdict_args=verdict_args,
    )


if __name__ == "__main__":
    raise SystemExit(main())
