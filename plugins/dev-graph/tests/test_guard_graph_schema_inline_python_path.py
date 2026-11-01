"""C10 guard: inline Python が変数経由で組み立てた graph path の遮断契約 (HarnessHub-f84o)。

背景:
  PR #72 の C19 live-trial で、``python3 - <<'PY'`` 本文が変数へ格納した
  ``.dev-graph/state/graph.json`` を書き換える経路が素通りした。旧判定は字面一致だけを
  見ていたため、``p = '.dev-graph/state/graph.json'`` の代入や
  ``Path('.dev-graph') / 'state' / 'graph.json'`` の結合で literal が分断されると、
  sanctioned C02 writer (build-graph-node.py / build-init-scaffold.py) を
  通らない書込みを遮断できなかった。

本 test が固定する 4 つの契約:
  1. MUST_BLOCK: 変数代入・Path 結合・os.path.join・f-string・% 書式・str.format で
     組み立てた書込み先を、字面が分断されていても遮断する。
  2. MUST_PASS: 読取専用呼出しと保護外領域 (.dev-graph/tmp/ cache/ templates/) への書込みを
     巻き込まない (HarnessHub-6in4 の教訓 — 正規手順まで塞ぐと agent が別の迂回を探す)。
  3. fail-closed: path を解決しきれない式は、確定した prefix が .dev-graph/ 配下から
     出ていない限り遮断する。「解決できなかったから通す」は fail-open である。
  4. 遮断経路は subprocess を起動しない (HarnessHub-6in4 が閉じた timeout fail-open 窓を
     再び開かない)。絶対所要時間は machine load まで測る proxy metric なので使わない。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HOOKS = PLUGIN / "hooks"
LIB = PLUGIN / "lib"
HOOK = HOOKS / "guard-graph-schema.py"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return load(HOOK, "guard_inline_python_path")


def heredoc(body: str) -> str:
    return f"python3 - <<'PY'\n{body}\nPY"


def dash_c(body: str) -> str:
    return f'python3 -c "{body}"'


STATE = ".dev-graph/state/graph.json"
CONFIG = ".dev-graph/config.json"

# 1. 字面が分断される代表的な間接表現。live-trial で素通りした形を先頭に置く。
MUST_BLOCK = {
    # 変数へ格納してから open (live-trial で観測された形)
    "variable-open-write": heredoc(f"p = '{STATE}'\nopen(p, 'w').write('{{}}')"),
    "variable-open-append": dash_c(f"p = '{CONFIG}'\nopen(p, 'a').write('x')"),
    # Path の / 結合。連続した .dev-graph/state という字面がどこにも現れない
    "path-division": heredoc(
        "from pathlib import Path\n"
        "p = Path('.dev-graph') / 'state' / 'graph.json'\np.write_text('{}')"
    ),
    "path-division-two-step": heredoc(
        "from pathlib import Path\n"
        "state = Path('.dev-graph') / 'state'\ntarget = state / 'graph.json'\n"
        "target.write_text('{}')"
    ),
    "path-joinpath": heredoc(
        "from pathlib import Path\n"
        "Path('.dev-graph').joinpath('state', 'graph.json').write_bytes(b'{}')"
    ),
    # os.path.join
    "os-path-join": heredoc(
        "import os\np = os.path.join('.dev-graph', 'state', 'graph.json')\n"
        "open(p, 'w').write('{}')"
    ),
    "os-path-join-nested": heredoc(
        "import os\nd = os.path.join('.dev-graph', 'state')\n"
        "open(os.path.join(d, 'graph.json'), 'w').write('{}')"
    ),
    # 文字列の組み立て
    "string-concat": heredoc(
        "root = '.dev-graph'\np = root + '/state/' + 'graph.json'\nopen(p, 'w')"
    ),
    "fstring": heredoc(
        "root = '.dev-graph'\np = f'{root}/state/graph.json'\nopen(p, 'w')"
    ),
    "percent-format": heredoc("p = '%s/state/graph.json' % '.dev-graph'\nopen(p, 'w')"),
    "str-format": heredoc(
        "p = '{}/config.json'.format('.dev-graph')\nopen(p, 'w')"
    ),
    "augmented-assign": heredoc(
        "p = '.dev-graph'\np += '/state/graph.json'\nopen(p, 'w')"
    ),
    # mode 側を変数化しても迂回できない
    "variable-mode": heredoc(f"p = '{STATE}'\nm = 'w'\nopen(p, m)"),
    # 解決できない mode は書込みでありうるため安全側 (fail-closed)
    "unresolved-mode": heredoc(f"p = '{STATE}'\nopen(p, mode)"),
    # 書込み API のバリエーション (path は変数経由)
    "pathlib-open-write": heredoc(
        "from pathlib import Path\np = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "p.open('w').write('{}')"
    ),
    "pathlib-unlink": heredoc(
        "from pathlib import Path\np = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "p.unlink()"
    ),
    "pathlib-touch": heredoc(
        "from pathlib import Path\np = Path('.dev-graph') / 'config.json'\np.touch()"
    ),
    "shutil-copy": heredoc(
        "import shutil\ndst = '.dev-graph' + '/state/graph.json'\n"
        "shutil.copy('/tmp/x.json', dst)"
    ),
    "shutil-move-keyword": heredoc(
        "import shutil\ndst = '.dev-graph' + '/config.json'\n"
        "shutil.move('/tmp/x.json', dst=dst)"
    ),
    "os-replace": heredoc(
        "import os\ndst = '.dev-graph' + '/state/graph.json'\n"
        "os.replace('/tmp/x.json', dst)"
    ),
    # relocate API は宛先だけでなく元 path も変更・削除する。
    "shutil-move-authority-source": heredoc(
        "import shutil\nsrc = '.dev-graph' + '/state/graph.json'\n"
        "shutil.move(src, '/tmp/backup.json')"
    ),
    "os-rename-authority-source": heredoc(
        "import os\nsrc = '.dev-graph' + '/config.json'\n"
        "os.rename(src, '/tmp/config.json')"
    ),
    "path-rename-authority-source": heredoc(
        "from pathlib import Path\n"
        "src = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "src.rename('/tmp/graph.json')"
    ),
    "path-replace-authority-destination": heredoc(
        "from pathlib import Path\n"
        "dst = Path('.dev-graph') / 'config.json'\nPath('/tmp/config.json').replace(dst)"
    ),
    "os-remove": heredoc(
        "import os\np = os.path.join('.dev-graph', 'state', 'graph.json')\nos.remove(p)"
    ),
    "json-dump-into-open": heredoc(
        "import json\np = '.dev-graph' + '/state/graph.json'\n"
        "json.dump({}, open(p, 'w'))"
    ),
    "io-open": heredoc(
        "import io\np = '.dev-graph' + '/config.json'\nio.open(p, 'w')"
    ),
    "with-statement": heredoc(
        f"p = '{STATE}'\nwith open(p, 'w') as fh:\n    fh.write('{{}}')"
    ),
    # ``os.open`` は mode 文字列ではなく整数 flag で書込みを表す。``open()`` を塞いで
    # こちらを残すと、f84o が指摘した「字面が違うと素通し」を低レベル API 側で再現する。
    "os-open-wronly": heredoc(
        f"import os\np = '{STATE}'\nfd = os.open(p, os.O_WRONLY)"
    ),
    "os-open-flag-or": heredoc(
        "import os\np = os.path.join('.dev-graph', 'config.json')\n"
        "fd = os.open(p, os.O_CREAT | os.O_TRUNC)"
    ),
    "os-open-unresolved-flags": heredoc(
        f"import os\nimport sys\np = '{STATE}'\nfd = os.open(p, int(sys.argv[1]))"
    ),
    "aliased-os-open": heredoc(
        f"from os import open as osopen\nimport os\nosopen('{STATE}', os.O_RDWR)"
    ),
    "open-keyword-arguments": heredoc(
        f"p = '{STATE}'\nopen(file=p, mode='w')"
    ),
    # import 別名で API 名を隠しても迂回できない (属性名一致だけでは追えない経路)
    "aliased-path-constructor": heredoc(
        "from pathlib import Path as P\np = P('.dev-graph') / 'config.json'\n"
        "p.write_text('{}')"
    ),
    "aliased-shutil-copy": heredoc(
        "from shutil import copy as cp\ndst = '.dev-graph' + '/state/graph.json'\n"
        "cp('/tmp/x.json', dst)"
    ),
    "aliased-module": heredoc(
        "import shutil as sh\ndst = '.dev-graph' + '/config.json'\n"
        "sh.move('/tmp/x.json', dst)"
    ),
    "aliased-os-path-join": heredoc(
        "from os.path import join\n"
        "open(join('.dev-graph', 'state', 'graph.json'), 'w')"
    ),
    "aliased-os-remove": heredoc(
        "from os import remove as rm\nrm('.dev-graph' + '/state/graph.json')"
    ),
    # 3. fail-closed: path を解決しきれない式
    "unresolved-segment-under-authority": heredoc(
        "from pathlib import Path\nimport sys\n"
        "p = Path('.dev-graph') / sys.argv[1] / 'graph.json'\np.write_text('{}')"
    ),
    "unresolved-root-with-state-tail": heredoc(
        "from pathlib import Path\nimport os\n"
        "p = Path(os.environ['ROOT']) / 'state' / 'graph.json'\np.write_text('{}')"
    ),
    "unresolved-authority-member-prefix": heredoc(
        "import sys\np = '.dev-graph/sta' + sys.argv[1]\nopen(p, 'w')"
    ),
    # AST 層は exec の source を再解析しないが、保護 path が字面に残る限り字面層 (lp36) が
    # 拾う。AST 層を足したことでこの既存保証が落ちていないことをここで固定する。
    "exec-with-literal-path": heredoc(
        f"exec(\"open('{STATE}', 'w').write('{{}}')\")"
    ),
    # ``python3 -c`` のセミコロン 1 行形式。heredoc と違い agent が最も書きやすい形で、
    # 実際に f84o を踏んだのもこの形だった。同じ式でも起動形が違えば別経路になりうる。
    "dash-c-semicolon-literal": dash_c(
        f"p='{STATE}'; open(p,'w').write('{{}}')"
    ),
    "dash-c-semicolon-path-division": dash_c(
        "from pathlib import Path; p = Path('.dev-graph') / 'state' / 'graph.json';"
        " p.write_text('{}')"
    ),
    "dash-c-semicolon-two-step": dash_c(
        "from pathlib import Path; d='.dev-graph/state'; p=d+'/graph.json';"
        " Path(p).write_text('{}')"
    ),
    "dash-c-semicolon-variable-mode": dash_c(f"p='{STATE}'; m='w'; open(p, m)"),
    # method 名を文字列へ逃がす形。path を変数へ逃がす形 (f84o 本体) と同じ回避なので、
    # 同じ境界で扱う。``getattr(x, '<リテラル>')`` を ``x.<リテラル>`` へ畳んでから照合する。
    "getattr-write-text": heredoc(
        "from pathlib import Path\n"
        "p = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "getattr(p, 'write_text')('{}')"
    ),
    "getattr-os-remove": heredoc(
        "import os\np = os.path.join('.dev-graph', 'config.json')\n"
        "getattr(os, 'remove')(p)"
    ),
    # path 構築側にも同じ畳み込みが要る。書込み判定だけ塞いでも os.path.join が
    # 解決できなければ書込み先が未確定になり、判定が空振りする
    "getattr-nested-join": heredoc(
        "import os\n"
        "p = getattr(getattr(os, 'path'), 'join')('.dev-graph', 'config.json')\n"
        "open(p, 'w')"
    ),
    # path を要素へ分解して字面を切る形。列を環境に保持して 3 経路とも同じ境界で扱う
    "str-join-of-bound-list": heredoc(
        "parts = ['.dev-graph', 'state', 'graph.json']\n"
        "p = '/'.join(parts)\nopen(p, 'w')"
    ),
    "str-join-inline-tuple": heredoc(
        "p = '/'.join(('.dev-graph', 'state', 'graph.json'))\nopen(p, 'w')"
    ),
    "path-starred-list": heredoc(
        "from pathlib import Path\nparts = ['.dev-graph', 'state', 'graph.json']\n"
        "p = Path(*parts)\np.write_text('{}')"
    ),
    "list-index-concat": heredoc(
        "parts = ['.dev-graph', 'state', 'graph.json']\n"
        "p = parts[0] + '/' + parts[1] + '/' + parts[2]\nopen(p, 'w')"
    ),
    # 区切りを定数属性で組む形
    "os-sep-concat": heredoc(
        "import os\np = '.dev-graph' + os.sep + 'state' + os.sep + 'graph.json'\n"
        "open(p, 'w')"
    ),
    # 保護対象の名前が最後の一手で現れる形
    "with-name-tail": heredoc(
        "from pathlib import Path\n"
        "p = (Path('.dev-graph') / 'state' / 'x.json').with_name('graph.json')\n"
        "p.write_text('{}')"
    ),
    "with-suffix-tail": heredoc(
        "from pathlib import Path\n"
        "p = (Path('.dev-graph') / 'state' / 'graph.txt').with_suffix('.json')\n"
        "p.write_text('{}')"
    ),
    "parent-property": heredoc(
        "from pathlib import Path\n"
        "p = (Path('.dev-graph') / 'state' / 'draft').parent / 'graph.json'\n"
        "p.write_text('{}')"
    ),
    # bytes path。字面が bytes になっただけで素通しさせない
    "bytes-path-concat": heredoc(
        "p = b'.dev-graph' + b'/state/graph.json'\nopen(p, 'wb')"
    ),
    # ``str(Path(...))`` は path を文字列へ戻す最も普通の書き方。identity として畳まないと
    # 1 段包むだけで書込み先が未解決になり素通しする (getattr より現実的な回避形)
    "str-wrapped-path": heredoc(
        "from pathlib import Path\n"
        "p = str(Path('.dev-graph') / 'state' / 'graph.json')\nopen(p, 'w')"
    ),
    "fspath-wrapped-path": heredoc(
        "import os\nfrom pathlib import Path\n"
        "p = os.fspath(Path('.dev-graph') / 'config.json')\nopen(p, 'w')"
    ),
    "str-wrapped-join-argument": heredoc(
        "import os\n"
        "p = os.path.join(str('.dev-graph'), 'state', 'graph.json')\n"
        "open(p, 'w')"
    ),
    "getattr-path-open-mode": heredoc(
        f"from pathlib import Path\np = Path('{STATE}')\ngetattr(p, 'open')('w')"
    ),
    "getattr-unlink": heredoc(
        f"from pathlib import Path\ngetattr(Path('{STATE}'), 'unlink')()"
    ),
    "dash-c-semicolon-multiarg-path": dash_c(
        "import pathlib; p = pathlib.Path('.dev-graph', 'config.json');"
        " p.write_text('{}')"
    ),
    # 起動形の違いで迂回できない
    "nested-bash-heredoc": (
        "bash -c 'python3 - <<PY\n"
        "p = \".dev-graph\" + \"/state/graph.json\"\nopen(p, \"w\")\nPY'"
    ),
}

# 2. 巻き込んではならない入力。誤検知を増やさない契約 (受入条件)。
MUST_PASS = {
    "variable-open-read": heredoc(f"p = '{STATE}'\nprint(open(p).read())"),
    "variable-open-mode-r": heredoc(f"p = '{STATE}'\nopen(p, 'r').read()"),
    "path-division-read": heredoc(
        "from pathlib import Path\n"
        "p = Path('.dev-graph') / 'state' / 'graph.json'\nprint(p.read_text())"
    ),
    "json-load": heredoc(f"import json\np = '{STATE}'\nprint(json.load(open(p)))"),
    # os.O_RDONLY は値 0 の読取専用。flag 名で判定するので読取は巻き込まない
    "os-open-rdonly": heredoc(
        f"import os\np = '{STATE}'\nfd = os.open(p, os.O_RDONLY)"
    ),
    # getattr の畳み込みは書込み動詞を見て判定する。読取 method まで巻き込まない
    "getattr-read-text": heredoc(
        "from pathlib import Path\n"
        "p = Path('.dev-graph') / 'state' / 'graph.json'\n"
        "print(getattr(p, 'read_text')())"
    ),
    # method 名が実行時決定かつ書込み先が保護外。名前を畳めなくても誤遮断しない
    "getattr-dynamic-name-unprotected": heredoc(
        "from pathlib import Path\nimport sys\n"
        "p = Path('docs') / 'note.md'\ngetattr(p, sys.argv[1])('x')"
    ),
    # 列・区切り定数・bytes の各経路とも、保護外への書込みは巻き込まない
    "join-into-tmp": heredoc(
        "parts = ['.dev-graph', 'tmp', 'draft.json']\np = '/'.join(parts)\nopen(p, 'w')"
    ),
    "starred-into-tmp": heredoc(
        "from pathlib import Path\nparts = ['.dev-graph', 'tmp', 'draft.json']\n"
        "Path(*parts).write_text('{}')"
    ),
    "os-sep-into-tmp": heredoc(
        "import os\np = '.dev-graph' + os.sep + 'tmp' + os.sep + 'draft.json'\n"
        "open(p, 'w')"
    ),
    "bytes-into-docs": heredoc("p = b'docs' + b'/note.md'\nopen(p, 'wb')"),
    "with-name-into-tmp": heredoc(
        "from pathlib import Path\n"
        "p = (Path('.dev-graph') / 'tmp' / 'x.json').with_name('draft.json')\n"
        "p.write_text('{}')"
    ),
    # 再代入で古い列が残ると、無関係な書込みを graph 宛と誤認する
    "sequence-rebound-to-unprotected": heredoc(
        "parts = ['.dev-graph', 'state', 'graph.json']\nparts = ['docs', 'note.md']\n"
        "p = '/'.join(parts)\nopen(p, 'w')"
    ),
    # 範囲外の添字で例外を出さず、未解決として扱う
    "index-out-of-range": heredoc("parts = ['docs']\np = parts[5]\nopen(p, 'w')"),
    # join が path 用途でない形
    "join-non-path-payload": heredoc(
        "row = '/'.join(['a', 'b'])\nopen('docs/out.csv', 'w').write(row)"
    ),
    # str を identity として畳んでも、保護外への書込みは巻き込まない
    "str-wrapped-tmp-write": heredoc(
        "from pathlib import Path\n"
        "p = str(Path('.dev-graph') / 'tmp' / 'draft.json')\nopen(p, 'w')"
    ),
    # str() の非 path 用途。畳んだ結果は "123" で保護領域と一致しない
    "str-of-non-path": heredoc(
        "p = 'docs/' + str(123) + '.md'\nopen(p, 'w')"
    ),
    # 保護外領域: init が正当に書く再生成可能な場所
    "tmp-draft-write": heredoc(
        "from pathlib import Path\n"
        "p = Path('.dev-graph') / 'tmp' / 'config-draft.json'\np.write_text('{}')"
    ),
    "cache-write": heredoc(
        "import os\np = os.path.join('.dev-graph', 'cache', 'pretty.json')\n"
        "open(p, 'w').write('{}')"
    ),
    "templates-copy": heredoc(
        "import shutil\ndst = '.dev-graph' + '/templates/issue.md'\n"
        "shutil.copy('/tmp/issue.md', dst)"
    ),
    # 保護外だと確定した prefix の下は、以降が動的でも通す (fail-closed の過剰適用防止)
    "tmp-unresolved-leaf": heredoc(
        "from pathlib import Path\nimport sys\n"
        "p = Path('.dev-graph') / 'tmp' / sys.argv[1]\np.write_text('{}')"
    ),
    # 未解決 root の下の config.json は tmp 置場でありうる (巻き込まない)
    "unresolved-root-config": heredoc(
        "from pathlib import Path\nimport tempfile\n"
        "p = Path(tempfile.mkdtemp()) / 'config.json'\np.write_text('{}')"
    ),
    "aliased-constructor-into-tmp": heredoc(
        "from pathlib import Path as P\np = P('.dev-graph') / 'tmp' / 'draft.json'\n"
        "p.write_text('{}')"
    ),
    "outside-repository": heredoc(
        "from pathlib import Path\np = Path('/tmp') / 'state' / 'draft.json'\n"
        "p.write_text('{}')"
    ),
    "unrelated-write": heredoc(
        "from pathlib import Path\np = Path('docs') / 'note.md'\np.write_text('x')"
    ),
    # 散文として保護 path を含むだけの入力 (7dw の誤遮断回帰アンカー)
    "prose-commit-message": (
        'git commit -m "guard: 変数経由の .dev-graph/state/graph.json 書換を遮断する"'
    ),
    "prose-bd-notes": (
        "python3 plugins/dev-graph/scripts/bd-bridge.py update HarnessHub-f84o"
        " --notes 'p = .dev-graph/state/graph.json への代入経由の書換を閉じた'"
    ),
    # -c を持つが python ではないコマンド (grep -c 等) を Python source と誤認しない
    "grep-count-flag": "grep -c 'open' plugins/dev-graph/hooks/guard-graph-schema.py",
    # 標準 library と同名のユーザー定義関数は qualified API ではない。
    "local-copy-function": heredoc(
        "def copy(src, dst):\n    return dst\n"
        "copy('/tmp/source', '.dev-graph/state/graph.json')"
    ),
    # Python の字面を説明・保存するだけの command は実行ではない。command 位置を見ずに
    # 全 heredoc / token を解析すると、README 生成やデバッグ出力まで誤遮断する。
    "echo-python-dash-c-snippet": (
        "echo python3 -c \"p='.dev-graph'+'/state/graph.json';open(p,'w')\""
    ),
    "cat-python-heredoc-snippet": (
        "cat <<'PY'\np = '.dev-graph' + '/state/graph.json'\nopen(p, 'w')\nPY"
    ),
}


@pytest.mark.parametrize("command", MUST_BLOCK.values(), ids=list(MUST_BLOCK))
def test_indirect_python_writes_to_graph_authority_are_blocked(guard, command):
    assert guard.interpreter_writes_graph_authority(command) is True, command


@pytest.mark.parametrize("command", MUST_PASS.values(), ids=list(MUST_PASS))
def test_reads_and_unprotected_targets_are_not_blocked(guard, command):
    assert guard.interpreter_writes_graph_authority(command) is False, command


def test_denial_does_not_launch_a_subprocess(guard, monkeypatch):
    """AST 解析経路が subprocess を起動しない (fail-open 窓の再導入防止)。

    PreToolUse hook が timeout すると Claude Code は tool を通す。遮断経路の内側に
    置いた subprocess の所要時間はそのまま fail-open の窓になるため、判定は
    標準ライブラリの ast だけで確定させる。
    """

    def forbidden(*_args, **_kwargs):
        raise AssertionError("遮断経路が subprocess を起動している")

    monkeypatch.setattr(guard.subprocess, "run", forbidden)
    command = heredoc(
        "from pathlib import Path\n"
        "p = Path('.dev-graph') / 'state' / 'graph.json'\np.write_text('{}')"
    )
    assert guard.interpreter_writes_graph_authority(command) is True
