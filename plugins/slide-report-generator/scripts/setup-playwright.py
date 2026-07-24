#!/usr/bin/env python3
# /// script
# name: setup-playwright
# purpose: Playwright Node依存とOS/CPU別Chromiumをplugin-local vendor配下へ復元・検査する。
# inputs:
#   - CLI: --install または --check
# outputs:
#   - stdout: setup/probe結果JSON
#   - exit: 0=ready / 1=checkで未準備 / 2=install失敗
# contexts: [glue]
# network: true
# write-scope: plugin-local vendor/node_modules, vendor/playwright-browsers
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Bootstrap a relocatable, plugin-local Playwright runtime.

Chromium is platform-specific, so the binary is restored after plugin install
under ``vendor/playwright-browsers``. Runtime scripts force
``PLAYWRIGHT_BROWSERS_PATH`` to that directory and never depend on the user's
global Playwright cache.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def plugin_root() -> Path:
    env_root = os.environ.get("SRG_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def runtime_paths(root: Path) -> dict[str, Path]:
    vendor = root / "vendor"
    return {
        "root": root,
        "vendor": vendor,
        "node_modules": vendor / "node_modules",
        "browser_dir": vendor / "playwright-browsers",
        "playwright_cli": vendor / "node_modules" / "playwright" / "cli.js",
        "playwright_package": vendor / "node_modules" / "playwright" / "package.json",
        "installer": vendor / "scripts" / "install-playwright-browser.js",
        "package_lock": vendor / "package-lock.json",
    }


def playwright_env(paths: dict[str, Path]) -> dict[str, str]:
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(paths["browser_dir"])
    return env


def _json_version(path: Path, *keys: str) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        for key in keys:
            value = value[key]
        return value if isinstance(value, str) else None
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def dependency_versions(paths: dict[str, Path]) -> dict:
    expected = _json_version(
        paths["package_lock"], "packages", "node_modules/playwright", "version"
    )
    installed = _json_version(paths["playwright_package"], "version")
    return {
        "expected": expected,
        "installed": installed,
        "current": bool(expected and installed and expected == installed),
    }


def _probe_chromium(paths: dict[str, Path], node: str | None) -> dict:
    if not node or not paths["playwright_cli"].is_file():
        return {"ready": False, "executable": None, "plugin_local": False}
    probe = (
        "import { chromium } from 'playwright';"
        "import { existsSync } from 'fs';"
        "const executable = chromium.executablePath();"
        "console.log(JSON.stringify({executable, exists: existsSync(executable)}));"
    )
    returncode = 1
    try:
        proc = subprocess.run(
            [node, "--input-type=module", "-e", probe],
            cwd=paths["vendor"],
            env=playwright_env(paths),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        returncode = proc.returncode
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        payload = {}
    executable = payload.get("executable")
    local = False
    if executable:
        try:
            Path(executable).resolve().relative_to(paths["browser_dir"].resolve())
            local = True
        except ValueError:
            local = False
    ready = returncode == 0 and bool(payload.get("exists")) and local
    return {"ready": ready, "executable": executable, "plugin_local": local}


def inspect_runtime(root: Path | None = None) -> dict:
    paths = runtime_paths(root or plugin_root())
    node = shutil.which("node")
    npm = shutil.which("npm")
    versions = dependency_versions(paths)
    chromium = _probe_chromium(paths, node)
    return {
        "ready": bool(
            node
            and npm
            and paths["vendor"].is_dir()
            and paths["node_modules"].is_dir()
            and paths["playwright_cli"].is_file()
            and versions["current"]
            and chromium["ready"]
        ),
        "detected": {
            "node": node,
            "npm": npm,
            "vendor": str(paths["vendor"]) if paths["vendor"].is_dir() else None,
            "node_modules": (
                str(paths["node_modules"]) if paths["node_modules"].is_dir() else None
            ),
            "playwright_expected_version": versions["expected"],
            "playwright_installed_version": versions["installed"],
            "playwright_dependencies_current": versions["current"],
            "browser_dir": str(paths["browser_dir"]),
            "chromium_executable": chromium["executable"],
            "plugin_local": chromium["plugin_local"],
        },
        "warnings": [],
    }


def install_runtime(root: Path | None = None) -> tuple[dict, list[str]]:
    paths = runtime_paths(root or plugin_root())
    node = shutil.which("node")
    npm = shutil.which("npm")
    steps: list[str] = []
    if not node or not npm:
        result = inspect_runtime(paths["root"])
        result["warnings"].append("node/npm が PATH に必要")
        return result, steps
    if not paths["package_lock"].is_file():
        result = inspect_runtime(paths["root"])
        result["warnings"].append(f"package-lock.json missing: {paths['package_lock']}")
        return result, steps

    try:
        paths["browser_dir"].mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result = inspect_runtime(paths["root"])
        result["warnings"].append(f"browser directory is not writable: {exc}")
        return result, steps
    env = playwright_env(paths)
    versions = dependency_versions(paths)
    if not paths["playwright_cli"].is_file() or not versions["current"]:
        proc = subprocess.run(
            [npm, "ci", "--no-audit", "--no-fund"],
            cwd=paths["vendor"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        steps.append("npm ci")
        if proc.returncode != 0:
            result = inspect_runtime(paths["root"])
            result["warnings"].append(
                f"npm ci failed: {(proc.stderr or proc.stdout)[-2000:]}"
            )
            return result, steps

    result = inspect_runtime(paths["root"])
    if result["ready"]:
        return result, steps

    try:
        proc = subprocess.run(
            [node, str(paths["installer"])],
            cwd=paths["vendor"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        result["warnings"].append(f"Chromium installer failed to start: {exc}")
        return result, steps
    steps.append("playwright install chromium")
    result = inspect_runtime(paths["root"])
    if proc.returncode != 0:
        result["warnings"].append(
            f"Chromium install failed: {(proc.stderr or proc.stdout)[-2000:]}"
        )
    return result, steps


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restore/check plugin-local Playwright Chromium"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true", help="依存とChromiumを復元")
    mode.add_argument("--check", action="store_true", help="network/writeなしで検査")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.install:
        result, steps = install_runtime()
        result["steps"] = steps
        exit_code = 0 if result["ready"] else 2
    else:
        result = inspect_runtime()
        result["steps"] = []
        exit_code = 0 if result["ready"] else 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
