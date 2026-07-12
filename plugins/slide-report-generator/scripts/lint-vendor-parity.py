#!/usr/bin/env python3
"""lint-vendor-parity.py — vendor byte-parity ゲート。

vendor/ 配下の byte 携行ツリー (scripts/ assets/ schemas-fixtures/ package.json
package-lock.json) を、plan 同梱の再現性アンカー ``vendor-digest-manifest.json``
(191 files sha256 pin) と照合する。移植元 live tree には依存しない。

additive_new_files (report 新規 Node: render-report.js / mermaid-render.js、
および vendor/tests/ 配下、manifest 自身) と package.json/package-lock.json の
Mermaid依存・実test配線は parity 対象外 (excluded_additive)。package 2ファイルは
byte比較の代わりに依存とtest配線をsemantic検証する。

exit 0 = 全 pin 一致 (missing/mismatch 0)、exit 1 = 不一致あり。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(PLUGIN_ROOT, "vendor", "vendor-digest-manifest.json")

# manifest.subtrees[].source -> vendor/ 配下の実 target ディレクトリ/ファイル
SUBTREE_TARGETS = {
    "presentation-slide-generator/scripts/": "vendor/scripts/",
    "presentation-slide-generator/assets/": "vendor/assets/",
    "presentation-slide-generator/schemas/": "vendor/schemas-fixtures/",
    "presentation-slide-generator/schemas/ (example fixtures + README のみ)": "vendor/schemas-fixtures/",
    "presentation-slide-generator/package.json": "vendor/",
    "presentation-slide-generator/package-lock.json": "vendor/",
}
ADDITIVE_PACKAGE_FILES = {"package.json", "package-lock.json"}
_EXACT_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# Mermaid <=11.14.0 は既知の injection / DoS advisories の対象。
_MIN_SAFE_MERMAID = (11, 15, 0)


def _validate_mermaid_pin(version: object, filename: str) -> list[str]:
    """Mermaid が range でなく安全床以上の exact SemVer pin か検査する。"""
    if not isinstance(version, str):
        return [f"{filename}: mermaid dependency missing"]
    match = _EXACT_SEMVER_RE.fullmatch(version)
    if not match:
        return [f"{filename}: mermaid must use an exact SemVer pin (got {version!r})"]
    if tuple(map(int, match.groups())) < _MIN_SAFE_MERMAID:
        floor = ".".join(map(str, _MIN_SAFE_MERMAID))
        return [f"{filename}: mermaid {version} is below security floor {floor}"]
    return []

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_additive_package(path: str, filename: str) -> list[str]:
    """C19 parity_scope.excluded_additive のsemantic gate。"""
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{filename}: JSON invalid ({exc})"]
    if filename == "package.json":
        deps = data.get("dependencies", {})
        test = data.get("scripts", {}).get("test", "")
        errors = _validate_mermaid_pin(deps.get("mermaid"), "package.json")
        if not isinstance(deps.get("playwright"), str):
            errors.append("package.json: playwright dependency missing")
        if not test or "no test specified" in test or "test-render-report.js" not in test or "test-mermaid-render.js" not in test:
            errors.append("package.json: npm test must execute real report/mermaid suites")
        return errors
    root = data.get("packages", {}).get("", {}).get("dependencies", {})
    errors = _validate_mermaid_pin(root.get("mermaid"), "package-lock.json")
    mermaid_package = data.get("packages", {}).get("node_modules/mermaid")
    if not isinstance(mermaid_package, dict):
        errors.append("package-lock.json: node_modules/mermaid entry missing")
    elif mermaid_package.get("version") != root.get("mermaid"):
        errors.append(
            "package-lock.json: root mermaid pin and node_modules/mermaid version differ"
        )
    if not isinstance(root.get("playwright"), str):
        errors.append("package-lock.json: playwright root dependency missing")
    return errors


def main() -> int:
    if not os.path.exists(MANIFEST):
        print(f"FAIL: manifest not found: {MANIFEST}", file=sys.stderr)
        return 1
    manifest = json.load(open(MANIFEST, encoding="utf-8"))

    total = ok = missing = mismatch = additive = 0
    for subtree in manifest.get("subtrees", []):
        target = SUBTREE_TARGETS.get(subtree["source"])
        if target is None:
            print(f"FAIL: unmapped manifest subtree source: {subtree['source']}", file=sys.stderr)
            return 1
        for filename, digest in subtree.get("files", {}).items():
            total += 1
            path = os.path.join(PLUGIN_ROOT, target, filename)
            display = f"{target}{filename}"
            if not os.path.exists(path):
                missing += 1
                print(f"MISSING {display}", file=sys.stderr)
            elif filename in ADDITIVE_PACKAGE_FILES:
                errors = validate_additive_package(path, filename)
                if errors:
                    mismatch += 1
                    for error in errors:
                        print(f"MISMATCH {display}: {error}", file=sys.stderr)
                else:
                    ok += 1
                    additive += 1
            elif sha256(path) != digest:
                mismatch += 1
                print(f"MISMATCH {display}", file=sys.stderr)
            else:
                ok += 1

    result = "PASS" if (missing == 0 and mismatch == 0) else "FAIL"
    print(f"vendor parity: total={total} ok={ok} additive-semantic={additive} missing={missing} mismatch={mismatch} -> {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
