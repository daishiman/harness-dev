"""テスト共通フィクスチャ: 作業ディレクトリ(cwd)と plugin-local モジュールの汚染を防ぐ。

多数の機能テストが os.chdir(tmp_path) を使うが restore しないため、pytest-randomly の
ランダム順で後続テストの相対パス解決が崩れ flaky になる。autouse フィクスチャで全テストの
前後に cwd を保存・復元し、cwd 汚染由来の順序依存failureを構造的に排除する。

加えて、複数 plugin が同名の bare-import モジュール (例: notion_config.py が
harness-creator / company-master / skill-intake に各1) を持つため、repo-root の
`pytest tests/` が全テストを単一プロセスで回すと最初に import された別 plugin の版が
sys.modules を占有し、後続 plugin のテストが AttributeError 等で落ちる (本番は各 plugin
単独実行なので無害な、テスト harness 限定の分離不全)。pytest_collectstart で各テスト
モジュールの import 直前に plugin-local production モジュールを sys.modules から退避し、
各テストが自分の plugin 版を fresh import し直せるようにして順序非依存にする。
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_cwd():
    """各テストの実行前 cwd を記録し、終了後に必ず戻す。"""
    prev = os.getcwd()
    try:
        yield
    finally:
        try:
            os.chdir(prev)
        except OSError:
            pass


def _is_plugin_local_production_path(file_path: str) -> bool:
    """plugins/<plugin>/{scripts,lib,hooks}/ 配下の production ファイルか判定する。"""
    norm = file_path.replace(os.sep, "/")
    if "/plugins/" not in norm or "/tests/" in norm or "/__pycache__/" in norm:
        return False
    return any(seg in norm for seg in ("/scripts/", "/lib/", "/hooks/"))


def _colliding_module_basenames() -> set[str]:
    """複数 plugin に同名で実在する bare-import モジュール名の集合を返す。

    衝突 (sys.modules を先勝ちで奪い合う) のはこの「2 つ以上の plugin-local パスに
    同じ basename で存在する」モジュールだけ。単一実在のモジュール (postal_api 等) は
    衝突しないため退避してはならない — 退避すると、collection と run の間に sys.modules
    から消え、run 時に関数内 `import postal_api` が monkeypatch 済みモジュールではなく
    新しい未patch モジュールを生成してしまう (doctor egress 等が壊れる)。
    """
    counts: dict[str, set[str]] = {}
    plugins_dir = ROOT / "plugins"
    if not plugins_dir.is_dir():
        return set()
    for py in plugins_dir.rglob("*.py"):
        s = str(py)
        if not _is_plugin_local_production_path(s):
            continue
        counts.setdefault(py.stem, set()).add(s)
    return {name for name, paths in counts.items() if len(paths) >= 2}


_COLLIDING_BASENAMES = _colliding_module_basenames()


def pytest_collectstart(collector):
    """各テストモジュールの収集 (=import) 直前に「衝突する同名モジュール」だけ退避する。

    複数 plugin に同名で存在するモジュール (notion_config 等) は、repo-root の単一プロセス
    実行で最初に import された別 plugin の版が sys.modules を占有し、後続 plugin のテストが
    その別版を掴んで AttributeError 等で落ちる。当該モジュール名だけを import 直前に退避し、
    各テストが自分の plugin 版を sys.path 先頭から fresh import し直せるようにする。

    重要: 退避対象は「2 plugin 以上で重複する basename」に限定する。単一実在モジュール
    (postal_api 等) を退避すると、run 時の関数内 bare import が monkeypatch 済みモジュールを
    取り逃がす回帰を生むため対象外とする (本番は各 plugin 単独実行なので衝突しない)。
    """
    if type(collector).__name__ != "Module" or not _COLLIDING_BASENAMES:
        return
    for name, mod in list(sys.modules.items()):
        if name.split(".")[0] not in _COLLIDING_BASENAMES:
            continue
        file_path = getattr(mod, "__file__", None)
        if file_path and _is_plugin_local_production_path(file_path):
            del sys.modules[name]
