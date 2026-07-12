#!/usr/bin/env python3

# /// script
# name: adapter-dispatch
# purpose: Resolve output route and dispatch payload to the selected sink adapter.
# inputs:
#   - argv: --kind, --payload, optional --dry-run
# outputs:
#   - stdout: Sink Contract JSON result
#   - stderr: adapter errors
# contexts: [E]
# network: false
# write-scope: output-dir
# dependencies: []
# ///
"""統合dispatcher: task_kind → routing解決 → adapter起動。

使い方:
    python dispatch.py --kind task-spec --payload payload.json

workflow skill側はこのscript1本を呼べばよい。
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ADAPTERS_DIR = REPO_ROOT / "scripts/adapters"


def run_adapter(adapter: str, script_ref: str, payload_path: str, params: dict, dry_run: bool) -> dict:
    script = (REPO_ROOT / script_ref).resolve()
    if not script.exists():
        return {"status": "failure", "adapter": adapter, "errors": [f"adapter script not found: {script}"]}

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(params, f)
        params_path = f.name

    cmd = [sys.executable, str(script), "--payload", payload_path, "--params", params_path]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"status": "failure", "adapter": adapter, "errors": [f"adapter returned non-JSON: {result.stdout[:200]} stderr={result.stderr[:200]}"]}
    except subprocess.TimeoutExpired:
        return {"status": "failure", "adapter": adapter, "errors": ["adapter timeout"]}
    finally:
        Path(params_path).unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--payload", required=True, help="path to payload.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Step 1: routing解決
    resolve = subprocess.run(
        [sys.executable, str(ADAPTERS_DIR / "resolve_route.py"), "--kind", args.kind],
        capture_output=True, text=True, timeout=10
    )
    if resolve.returncode != 0:
        print(json.dumps({"status": "failure", "errors": [f"route resolution failed: {resolve.stderr}"]}))
        sys.exit(1)
    resolved = json.loads(resolve.stdout)

    # Step 2: adapter起動 (multi-sink対応)
    results = []
    if resolved.get("multi"):
        for adapter in resolved["adapters"]:
            adapter_params = resolved["params"].get(adapter, {})
            script_ref = resolved.get("registry", {}).get(adapter, {}).get("script", f"scripts/adapters/sink_{adapter}.py")
            results.append(run_adapter(adapter, script_ref, args.payload, adapter_params, args.dry_run))
    else:
        adapter = resolved["adapter"]
        script_ref = resolved.get("registry", {}).get(adapter, {}).get("script", f"scripts/adapters/sink_{adapter}.py")
        primary = run_adapter(adapter, script_ref, args.payload, resolved.get("params", {}), args.dry_run)
        if primary["status"] == "failure" and resolved.get("fallback"):
            # fallback起動
            fb_params = {"path": "fallback/", "format": "json"} if resolved["fallback"] == "local" else {}
            fb_adapter = resolved["fallback"]
            fb_script = resolved.get("registry", {}).get(fb_adapter, {}).get("script", f"scripts/adapters/sink_{fb_adapter}.py")
            fb = run_adapter(fb_adapter, fb_script, args.payload, fb_params, args.dry_run)
            fb["fallback_from"] = resolved["adapter"]
            results = [primary, fb]
        else:
            results = [primary]

    failures = [r for r in results if r.get("status") == "failure"]
    status = "failure" if failures else "success"
    first_success = next((r for r in results if r.get("status") == "success"), {})
    print(json.dumps({
        "status": status,
        "adapter": "multi" if len(results) > 1 else results[0].get("adapter"),
        "location": first_success.get("location"),
        "external_id": first_success.get("external_id"),
        "errors": [e for r in results for e in r.get("errors", [])],
        "kind": args.kind,
        "results": results
    }, ensure_ascii=False))
    return 1 if failures and not first_success else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
