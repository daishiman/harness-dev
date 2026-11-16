"""C19 live-trial (20261115T1805-r44-sysspec) の隔離 fixture を作る factory。

- 種: ROOT/eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261102T010423-ci-full/fixture-final/system-spec
  (ci12 の preflight 入力と bytes 一致を確認済み)。README.md は ci12 の FX root に無かったので入れない。
- 作り方は 20261102T004729-pr86-source-scope-context/fixture-preparation.py と ci12 task.md の記述に合わせる:
  空 commit 1 つ、system-spec/ は未追跡、dev-graph は C01 正規 builder で初期化、graph.nodes は空。
- 評価 report・PASS・登録結果・取込 payload・監査台帳は置かない。
- 既存 FX があれば何もせず止める (上書き・削除しない)。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path("/Users/dm/orca/workspaces/harness/harness-creatorの改善")
BASE = Path("/private/tmp/claude-501/-Users-dm-orca-workspaces-harness-harness-creator---/"
            "f6429ecb-7e3e-4750-b72b-ebfe022771f9/scratchpad/lt/system-spec2")
FX = BASE / "fx"
CONTROL = BASE / "control"
SEED = ROOT / "eval-log/dev-graph/run-dev-graph-system-spec/live-trial/20261102T010423-ci-full/fixture-final/system-spec"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(argv, **kw):
    cp = subprocess.run(argv, capture_output=True, text=True, **kw)
    return {"argv": [str(a) for a in argv], "exit": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}


def main() -> int:
    if FX.exists():
        print(f"STOP: fixture already exists: {FX}", file=sys.stderr)
        return 3
    if not SEED.is_dir():
        print(f"STOP: seed missing: {SEED}", file=sys.stderr)
        return 3
    CONTROL.mkdir(parents=True, exist_ok=True)
    FX.mkdir(parents=True)

    git_env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    git_env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    git_env["GIT_CONFIG_NOSYSTEM"] = "1"
    log = []
    log.append(run(["git", "-c", "core.hooksPath=/dev/null", "init", "-q", "-b", "main", str(FX)], env=git_env))
    log.append(run(["git", "-C", str(FX), "-c", "core.hooksPath=/dev/null", "-c", "user.name=live-trial",
                    "-c", "user.email=live-trial@example.invalid", "commit", "-q", "--allow-empty",
                    "-m", "fixture: canonical resume inputs"], env=git_env))
    for entry in log:
        if entry["exit"] != 0:
            print(json.dumps(log, ensure_ascii=False, indent=2), file=sys.stderr)
            return 4
    (FX / ".git/info/exclude").write_text(".claude/\n", encoding="utf-8")

    shutil.copytree(SEED, FX / "system-spec", copy_function=shutil.copy2)

    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    init = run([sys.executable, "-B", str(ROOT / "plugins/dev-graph/scripts/build-init-scaffold.py"),
                "--repo-root", str(FX), "--hook-source", "plugin"], env=env, cwd=str(FX))
    (CONTROL / "fixture-init-receipt.json").write_text(init["stdout"], encoding="utf-8")
    (CONTROL / "fixture-init-run.json").write_text(json.dumps(init, ensure_ascii=False, indent=2) + "\n",
                                                  encoding="utf-8")
    if init["exit"] != 0:
        print(init["stderr"], file=sys.stderr)
        return 5
    graph = json.loads((FX / ".dev-graph/state/graph.json").read_text(encoding="utf-8"))
    assert graph["nodes"] == [], "graph.nodes must be empty"

    pre = {
        "graph_schema": run([sys.executable, "-B", str(ROOT / "plugins/dev-graph/scripts/validate-graph-schema.py"),
                             "--repo-root", str(FX), "--graph", str(FX / ".dev-graph/state/graph.json")],
                            env=env, cwd=str(FX)),
        "source_lineage": run([sys.executable, "-B", str(ROOT / "plugins/dev-graph/scripts/validate-source-lineage.py"),
                               "--repo-root", str(FX)], env=env, cwd=str(FX)),
        "git_log": run(["git", "-C", str(FX), "log", "--format=%H %s"], env=git_env),
        "git_status": run(["git", "-C", str(FX), "status", "--porcelain=v1", "--untracked-files=all"], env=git_env),
    }
    (CONTROL / "fixture-preflight.json").write_text(json.dumps(pre, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")

    seed_files = sorted(p for p in SEED.rglob("*") if p.is_file())
    copied = {}
    for p in seed_files:
        rel = p.relative_to(SEED).as_posix()
        dst = FX / "system-spec" / rel
        copied[f"system-spec/{rel}"] = {"seed_sha256": sha(p), "fixture_sha256": sha(dst),
                                        "byte_identical": p.read_bytes() == dst.read_bytes()}
    dev_graph = {p.relative_to(FX).as_posix(): sha(p)
                 for p in sorted((FX / ".dev-graph").rglob("*")) if p.is_file()}
    summary = {
        "fx": str(FX),
        "fx_realpath": str(FX.resolve()),
        "seed": str(SEED),
        "factory": str(Path(__file__).resolve()),
        "factory_sha256": sha(Path(__file__).resolve()),
        "init_exit": init["exit"],
        "init_receipt_sha256": sha(CONTROL / "fixture-init-receipt.json"),
        "graph_nodes_initial": len(graph["nodes"]),
        "preflight_exits": {k: v["exit"] for k, v in pre.items()},
        "system_spec": copied,
        "all_byte_identical": all(v["byte_identical"] for v in copied.values()),
        "dev_graph_files": dev_graph,
    }
    (CONTROL / "fixture-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                                  encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("fx", "fx_realpath", "init_exit", "graph_nodes_initial",
                                              "preflight_exits", "all_byte_identical")}, ensure_ascii=False))
    print("files:", len(copied), "dev_graph_files:", len(dev_graph))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
