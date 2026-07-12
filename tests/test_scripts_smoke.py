"""全スクリプトの import smoke テスト (ハーネス仕様: scripts 機械的カバレッジ底上げ)。

各スクリプトを importlib で読み込み、module-body(import/定数/関数定義/argparse 構築の一部)が
例外なくロードできることを検証する。`__name__ != "__main__"` のため main() は実行されない(副作用なし)。
import 自体が失敗するスクリプトは「壊れている」という本物の検出。standalone import できない既知の
スクリプト(repo-root を sys.path 前提にした相対 import 等)は SKIP_REASON に理由付きで除外する。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# standalone import が本質的に不可能なスクリプト(理由付き honest skip)。
# import 時に file 読込/argparse 実行等の副作用を持つ = module-level 実行の設計 smell。
# follow-up: main ガード化して import-safe にすれば smoke 対象へ復帰できる。
SKIP_REASON: dict[str, str] = {
    "plugins/skill-intake/scripts/_jsonschema_compat.py": "import 時に互換 shim を実行し standalone import 不可",
    "plugins/skill-intake/skills/run-intake-interview/scripts/validate-interview-json.py": "import 時に file 読込の副作用あり",
    "plugins/skill-intake/skills/run-intake-visualize/scripts/verify-visuals.py": "import 時に file 読込の副作用あり",
}


def _script_files() -> list[Path]:
    files: list[Path] = []
    sd = ROOT / "scripts"
    if sd.is_dir():
        files += [f for f in sd.glob("*.py") if not f.is_symlink() and f.name != "sitecustomize.py"]
    for f in (ROOT / "plugins").rglob("scripts/*.py"):
        if not f.is_symlink() and "__pycache__" not in f.parts:
            files.append(f)
    return sorted(files)


_SCRIPTS = _script_files()


@pytest.mark.parametrize("script", _SCRIPTS, ids=[str(f.relative_to(ROOT)) for f in _SCRIPTS])
def test_script_imports_without_error(script):
    rel = str(script.relative_to(ROOT))
    if rel in SKIP_REASON:
        pytest.skip(SKIP_REASON[rel])
    # repo-root scripts/ を sys.path に入れて feedback_contract_ssot 等の同階層 import を解決
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(script.parent))
    mod_name = "smoke_" + rel.replace("/", "_").replace("-", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(mod_name, script)
    assert spec and spec.loader, f"cannot load spec for {rel}"
    mod = importlib.util.module_from_spec(spec)
    # @dataclass + `from __future__ import annotations` を持つスクリプトは、dataclasses._is_type が
    # sys.modules[cls.__module__].__dict__ を引くため、exec 前にモジュールを登録しておく
    # (未登録だと Python 3.11 で AttributeError: 'NoneType' object has no attribute '__dict__')。
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)  # __main__ ガードにより main() は走らない
    finally:
        sys.modules.pop(mod_name, None)
        sys.path.pop(0)
        sys.path.pop(0)


def test_smoke_covers_scripts():
    """少なくとも 30 本以上のスクリプトを smoke 対象にしている(計測の網羅性自体を固定)。"""
    assert len(_SCRIPTS) >= 30
