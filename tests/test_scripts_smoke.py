"""全スクリプトの import smoke テスト (ハーネス仕様: scripts 機械的カバレッジ底上げ)。

各スクリプトを importlib で読み込み、module-body(import/定数/関数定義/argparse 構築の一部)が
例外なくロードできることを検証する。`__name__ != "__main__"` のため main() は実行されない(副作用なし)。
import 自体が失敗するスクリプトは「壊れている」という本物の検出。standalone import できない既知の
スクリプト(repo-root を sys.path 前提にした相対 import 等)は SKIP_REASON に理由付きで除外する。
"""
import importlib.util
import subprocess
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


def _import_roots(script: Path) -> list[Path]:
    """本番 entrypoint が sys.path へ入れているのと同じディレクトリ集合を返す。

    skills/<skill>/scripts/ 配下のモジュールは、同階層と owning plugin の scripts/
    (plugin_resources・foundation_provenance 等) の両方から素の名前で import する。本番の
    entrypoint は両方を sys.path へ入れて解決するので、ここが片方しか入れていないと smoke だけが落ちる。
    """
    roots = [script.parent, ROOT / "scripts"]
    parts = script.relative_to(ROOT).parts
    if parts[0] == "plugins" and len(parts) > 2:
        roots.insert(1, ROOT / "plugins" / parts[1] / "scripts")
    return [root for root in dict.fromkeys(roots) if root.is_dir()]


def _is_repo_module(module: object) -> bool:
    """repo 内のファイルから読まれたモジュールだけを捨てる対象にする。

    site-packages 側 (jsonschema が引く rpds 等の PyO3 拡張) は 1 プロセスで 1 回しか
    初期化できず、sys.modules から外すと次の import が ImportError になる。順序依存の
    原因になるのは repo の素の名前の import だけなので、掃除はそこに限る。
    """
    file = getattr(module, "__file__", None)
    return bool(file) and Path(file).resolve().is_relative_to(ROOT)


@pytest.mark.parametrize("script", _SCRIPTS, ids=[str(f.relative_to(ROOT)) for f in _SCRIPTS])
def test_script_imports_without_error(script):
    rel = str(script.relative_to(ROOT))
    if rel in SKIP_REASON:
        pytest.skip(SKIP_REASON[rel])
    roots = _import_roots(script)
    for root in reversed(roots):
        sys.path.insert(0, str(root))
    # 対象が推移的に持ち込んだモジュールを毎回捨てる。残すと後続テストの import が
    # 「先に誰かが読んでくれていたから通った」状態になり、単体実行と CI で結果が割れる。
    modules_before = set(sys.modules)
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
        for name in set(sys.modules) - modules_before:
            if _is_repo_module(sys.modules.get(name)):
                sys.modules.pop(name, None)
        for _ in roots:
            sys.path.pop(0)


def test_smoke_covers_scripts():
    """少なくとも 30 本以上のスクリプトを smoke 対象にしている(計測の網羅性自体を固定)。"""
    assert len(_SCRIPTS) >= 30


# owning plugin の scripts/ から素の名前で import する skill 配下 script。
# plugin_resources (harness-creator) と foundation_provenance (system-spec-harness) の 2 系統を見張る。
_SKILL_SCRIPTS_WITH_PLUGIN_IMPORT = {
    "harness-creator": ROOT / "plugins/harness-creator/skills/run-plugin-package-check/scripts/lint-pkg-009.py",
    "system-spec-harness": (
        ROOT / "plugins/system-spec-harness/skills/run-system-spec-elicit/scripts/apply-spec-transition.py"
    ),
}


@pytest.mark.parametrize("plugin", sorted(_SKILL_SCRIPTS_WITH_PLUGIN_IMPORT))
def test_skill_scripts_can_see_their_owning_plugin_scripts_dir(plugin):
    """skills/<skill>/scripts/ の対象には owning plugin の scripts/ を必ず通す。

    ここが欠けると plugin 共有 module の素の import が単体実行でだけ失敗し、
    フルスイートでは先行テストの sys.modules 残留で通ってしまう。CI の赤が再現不能に
    なって無関係な PR へ誤帰属するため、順序ではなく sys.path で保証する。
    """
    script = _SKILL_SCRIPTS_WITH_PLUGIN_IMPORT[plugin]
    assert script.is_file(), "回帰の見張り対象が移動している。パスを更新すること"
    roots = _import_roots(script)
    assert script.parent in roots
    assert ROOT / "plugins" / plugin / "scripts" in roots
    assert ROOT / "scripts" in roots


@pytest.mark.parametrize("plugin", sorted(_SKILL_SCRIPTS_WITH_PLUGIN_IMPORT))
def test_import_roots_are_scoped_to_the_owning_plugin(plugin):
    """他 plugin の scripts/ は混ぜない(素の import が偶然解決するのを防ぐ)。"""
    roots = _import_roots(_SKILL_SCRIPTS_WITH_PLUGIN_IMPORT[plugin])
    others = [root for root in roots if root.is_relative_to(ROOT / "plugins")]
    assert all(root.is_relative_to(ROOT / "plugins" / plugin) for root in others)


def test_visual_generation_validator_imports_without_optional_dependencies() -> None:
    """CI 最小環境で bs4/tinycss2 が無くても module import は無副作用。"""
    script = ROOT / "plugins/slide-report-generator/scripts/validate-visual-generation.py"
    code = """
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("visual_validator_without_site", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
"""
    got = subprocess.run(
        [sys.executable, "-S", "-c", code, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert got.returncode == 0, got.stdout + got.stderr


def test_visual_generation_validator_fails_closed_when_executed_without_dependencies() -> None:
    """import-safe化しても、実検査を依存不足のまま通さない。"""
    script = ROOT / "plugins/slide-report-generator/scripts/validate-visual-generation.py"
    got = subprocess.run(
        [sys.executable, "-S", str(script), "--self-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert got.returncode == 3
    assert "bs4 / tinycss2" in got.stderr
