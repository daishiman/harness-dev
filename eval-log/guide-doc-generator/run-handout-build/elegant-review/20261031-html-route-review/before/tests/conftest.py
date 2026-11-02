"""同名ファイルが並ぶテスト木を 1 プロセスで走らせるための隔離。

このプラグインのテストは `tests/<検査対象>/` という区切りで、1 ディレクトリが
1 component に対応する。区切りが component 側の名前をそのまま持つため、同じ
役割のファイルが各ディレクトリに同じ名前で並ぶ (`_harness.py` が 9 個、
`test_determinism.py` が 5 個)。これは読みやすさのための意図的な対称であって、
名前を一意化して崩す方向の解決は取らない。

一方 pytest は既定の import 方式 (prepend) で、テストファイルの親ディレクトリを
sys.path へ差し込み、モジュールを **basename で** sys.modules へ登録する。よって
1 プロセスで木全体を集めると:

- `test_determinism` は最初に読んだ 1 個が居座り、2 個目の収集で import mismatch
  になって収集そのものが止まる。
- `_harness` も先勝ちで、後のディレクトリのテストが別 component 用の harness を
  掴んで AttributeError で落ちる (CI が実際にこう落ちた)。

ローカルで 1 ディレクトリずつ回している間はどちらも起きないが、CI は plugin 単位で
1 プロセスにまとめるため必ず踏む。ここで 2 つ手当てする。

1. import 方式を importlib へ切り替える (`pytest.ini`)。テストモジュールの登録名が
   パス由来になり、basename の先勝ちが起きなくなる。
2. importlib 方式は sys.path を触らないので、`import _harness` のような同居ファイル
   への裸の import が解決しなくなる。収集の直前にそのテストの親ディレクトリを
   sys.path の先頭へ置き、前のディレクトリで読まれた同名の同居モジュールを
   sys.modules から外して、各テストが自分の隣にある版を読み直せるようにする。
   (収集時に import 済みのテストモジュールは実体を保持しているので、後から
   sys.modules を掃除しても既に集まったテストには影響しない。)
"""

import os
import sys
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _restore_cwd():
    """各テストの前後で cwd を戻す。

    多くのテストが一時ディレクトリへ降りて生成物を検査するが、戻さないまま
    終わるものがある。1 ディレクトリずつ回している間は次の実行が別プロセスなので
    表に出ないが、木全体を 1 プロセスで回すと後続テストの相対パス解決が崩れ、
    実行順によって落ちたり通ったりする。
    """
    prev = os.getcwd()
    try:
        yield
    finally:
        try:
            os.chdir(prev)
        except OSError:
            pass


def _sibling_helpers():
    """テストディレクトリに同居する、裸で import されうるモジュール名の集合。

    テストファイル自身は importlib 方式が一意に扱うのでここでは対象外。掃除が
    必要なのは `_harness` のような助手と、component の実体を読み込むために置かれた
    同名スクリプトの写しだけである。
    """
    names = set()
    for path in TESTS_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or path.name.startswith("test_"):
            continue
        if path.parent == TESTS_ROOT:
            continue
        names.add(path.stem)
    return names


_SIBLING_HELPERS = _sibling_helpers()


def _prefer_siblings_of(path):
    """path と同じディレクトリの助手を、次の裸 import が拾うようにする。"""
    parent = str(Path(path).parent)

    # 自分の隣を最優先で探させる。
    while parent in sys.path:
        sys.path.remove(parent)
    sys.path.insert(0, parent)

    # テスト木で読まれた助手を一律に外し、次の import で必ず隣の版を読ませる。
    # 「別ディレクトリの版だけ外す」では足りない: 助手同士が互いを裸で import
    # するため (contract_lib → _support など)、入口の 1 個を差し替えても連鎖の
    # 途中に前のディレクトリの版が残り、そこ経由で古い実体が漏れてくる。
    for name, module in list(sys.modules.items()):
        if name.split(".")[0] not in _SIBLING_HELPERS:
            continue
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        if str(Path(origin).resolve()).startswith(str(TESTS_ROOT)):
            del sys.modules[name]


def pytest_collectstart(collector):
    """収集 (= テストモジュールの import) の直前に隣を優先させる。"""
    if type(collector).__name__ != "Module":
        return
    module_path = getattr(collector, "path", None)
    if module_path is not None:
        _prefer_siblings_of(module_path)


def pytest_runtest_setup(item):
    """実行の直前にも同じ整理をする。

    収集時だけでは足りない。助手を関数の中で裸 import するテストがあり
    (`from _support import REPO_ROOT`)、その import が走るのは実行時である。
    そのとき sys.path の先頭は「最後に収集したモジュールの隣」になっているため、
    整えないと無関係な component の助手を掴む。
    """
    path = getattr(item, "path", None)
    if path is not None:
        _prefer_siblings_of(path)
