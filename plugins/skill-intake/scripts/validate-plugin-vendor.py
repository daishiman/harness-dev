#!/usr/bin/env python3
"""Smoke test for plugin-local Python vendor dependencies.

This verifies the marketplace/package install invariant: after `skill-intake`
is installed, scripts can import bundled runtime libraries from the installed
plugin root without user-side `pip install`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or SCRIPT_DIR.parent).resolve()
VENDOR_DIR = PLUGIN_ROOT / "vendor" / "python"


def main() -> int:
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    try:
        from _vendor import activate
    except Exception as exc:
        print(json.dumps({"ok": False, "reason": f"_vendor import failed: {exc}"}, ensure_ascii=False))
        return 2

    activate()
    checks = {
        "plugin_root": str(PLUGIN_ROOT),
        "vendor_dir": str(VENDOR_DIR),
        "vendor_exists": VENDOR_DIR.is_dir(),
        "jinja2_init": (VENDOR_DIR / "jinja2" / "__init__.py").is_file(),
        "markupsafe_init": (VENDOR_DIR / "markupsafe" / "__init__.py").is_file(),
        "typing_extensions": (VENDOR_DIR / "typing_extensions.py").is_file(),
        "pycache_count": len(list(PLUGIN_ROOT.rglob("__pycache__"))),
        "pyc_count": len(list(PLUGIN_ROOT.rglob("*.pyc*"))),
        "native_so_count": len(list(PLUGIN_ROOT.rglob("*.so"))),
    }
    try:
        import jinja2
        import markupsafe
        import typing_extensions
        import _jsonschema_compat as jsonschema
        jsonschema.validate({"x": "2026-06-07T00:00:00Z"}, {
            "type": "object",
            "required": ["x"],
            "properties": {"x": {"type": "string", "format": "date-time"}},
        })
        checks.update({
            "jinja2_file": str(Path(jinja2.__file__).resolve()),
            "markupsafe_file": str(Path(markupsafe.__file__).resolve()),
            "typing_extensions_file": str(Path(typing_extensions.__file__).resolve()),
        })
    except Exception as exc:
        checks["import_error"] = str(exc)

    # pycache_count / pyc_count は情報フィールドに留める。これらは runtime 生成の
    # bytecode で gitignore 対象 (配布されない) であり、CI の先行 py_compile ステップが
    # 必ず生成するため ok 条件に含めると環境依存で偽陽性になる。配布リスクとなる
    # native .so (プラットフォーム依存バイナリの混入) のみを ok の閉条件として保持する。
    ok = (
        checks["vendor_exists"]
        and checks["jinja2_init"]
        and checks["markupsafe_init"]
        and checks["typing_extensions"]
        and checks["native_so_count"] == 0
        and "import_error" not in checks
        and "/vendor/python/" in checks.get("jinja2_file", "")
        and "/vendor/python/" in checks.get("markupsafe_file", "")
        and "/vendor/python/" in checks.get("typing_extensions_file", "")
    )
    checks["ok"] = ok
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
