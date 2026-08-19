"""C14 render-diagram-svg.py 受入テストの共通土台。

このモジュール自体はテストを持たない (discover の pattern test_*.py に一致しない)。
契約の出所はすべて plugin-plans/guide-doc-generator/briefs/script-brief-C14.json であり、
ここで新しい契約を発明しない。ブリーフに書かれていない事項は README.md の gaps へ記録する。

実装が無い状態を unittest の *error* ではなく *failure* として立てるため、
実体解決は必ず require_script() 経由で行い AssertionError を送出する。
setUpClass では一切例外を投げない (errors へ分類されてしまうため)。
"""

import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

# tests/render-diagram-svg.py/ -> tests/ -> guide-doc-generator/ -> plugins/ -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parent.parent
REPO_ROOT = PLUGIN_ROOT.parent.parent

SCRIPT = PLUGIN_ROOT / "scripts" / "render-diagram-svg.py"
GOLDEN_DIR = TESTS_DIR / "golden"

# script-brief-C14.json argv[--pattern]
PATTERNS = ("flow", "compare", "hierarchy", "cycle", "matrix", "versus")

# script-brief-C14.json argv[--width].default
DEFAULT_WIDTH = 860

# script-brief-C14.json algorithm 手順 6 / failure_modes
#   ノード label は最大 3 行、bullets は最大 2 行
MAX_LINES_NODE_LABEL = 3
MAX_LINES_BULLETS = 2

# script-brief-C16.json canonical_rules.external_reference_rule (CR-EXT) が列挙する
# 取得を発生させ得る参照属性。goal-spec C60 / SC-10 により data: 以外は一律違反。
FETCHING_ATTRS = (
    "href", "src", "srcset", "poster", "data", "action", "formaction",
    "cite", "background", "xlink:href",
)

# AC-C14-3 が名指しする外部参照の書き出し
EXTERNAL_PREFIXES = ("http://", "https://", "//")

# AC-C14-4 の絵文字レンジ
EMOJI_RANGES = ((0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0xFE0F, 0xFE0F))

# SC-09 (R21 C55) が DIAGRAM に要求する描画要素
DRAWING_TAGS = (
    "path", "rect", "circle", "ellipse", "line",
    "polyline", "polygon", "text", "image", "use",
)


# --------------------------------------------------------------------------
# 実体解決 (未実装を failure として立てる)
# --------------------------------------------------------------------------

def require_script():
    if not SCRIPT.is_file():
        raise AssertionError(
            "build_target が未実装: %s\n"
            "P05 が render-diagram-svg.py を実装するまで本テスト群は赤で固定される。" % SCRIPT
        )


def source_text():
    require_script()
    return SCRIPT.read_text(encoding="utf-8")


def imported_modules():
    """script が import しているトップレベルモジュール名の集合 (AC-C14-8)。"""
    src = source_text()
    names = set()
    for m in re.finditer(r"^\s*import\s+([A-Za-z_][\w.]*)", src, re.M):
        names.add(m.group(1).split(".")[0])
    for m in re.finditer(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import", src, re.M):
        names.add(m.group(1).split(".")[0])
    return names


def load_module():
    """C11 が import 経由で呼ぶ module API を取り出す (dependencies.invoked_by)。"""
    require_script()
    import importlib.util

    spec = importlib.util.spec_from_file_location("hb_diagram", str(SCRIPT))
    if spec is None or spec.loader is None:
        raise AssertionError("module として読み込めない: %s" % SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# 起動
# --------------------------------------------------------------------------

class Result:
    def __init__(self, proc):
        self.returncode = proc.returncode
        self.stdout_bytes = proc.stdout
        self.stderr_bytes = proc.stderr
        self.stdout = proc.stdout.decode("utf-8", "replace")
        self.stderr = proc.stderr.decode("utf-8", "replace")

    def __repr__(self):  # pragma: no cover - 診断用
        return "<Result exit=%d stdout=%r stderr=%r>" % (
            self.returncode, self.stdout[:200], self.stderr[:200],
        )


def run_diagram(args, cwd=None, env_extra=None):
    """render-diagram-svg.py を subprocess で起動する。"""
    require_script()
    env = dict(os.environ)
    env["HB_ROOT"] = str(PLUGIN_ROOT)
    env.setdefault("PYTHONHASHSEED", "0")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + [str(a) for a in args],
        capture_output=True,
        cwd=str(cwd or REPO_ROOT),
        env=env,
    )
    return Result(proc)


def write_diagram(path, spec):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render(tmpdir, spec, pattern=None, width=None, cwd=None):
    """spec を書き出して起動する。pattern 省略時は spec['pattern'] を使う。"""
    if pattern is None:
        pattern = spec.get("pattern")
    path = write_diagram(Path(tmpdir) / "diagram.json", spec)
    args = ["--diagram", path, "--pattern", pattern]
    if width is not None:
        args += ["--width", width]
    return run_diagram(args, cwd=cwd)


# --------------------------------------------------------------------------
# fixture (script-brief-C14.json algorithm 手順 4 の必須フィールド定義から起こす)
# --------------------------------------------------------------------------

def flow_spec(**over):
    spec = {
        "id": "dg-flow",
        "title": "申請から承認までの流れ",
        "description": "申請者が出してから承認が下りるまでの 3 段階",
        "pattern": "flow",
        "steps": [
            {"id": "st1", "label": "申請する", "note": "様式Aを使う"},
            {"id": "st2", "label": "確認する"},
            {"id": "st3", "label": "承認する"},
        ],
    }
    spec.update(over)
    return spec


def compare_spec(**over):
    spec = {
        "id": "dg-compare",
        "title": "案Aと案Bの比較",
        "pattern": "compare",
        "axes": ["費用", "速さ"],
        "items": ["案A", "案B"],
        # gaps: cells の形はブリーフ未定義。items x axes の 2 次元配列と解釈した
        "cells": [["高い", "速い"], ["安い", "遅い"]],
    }
    spec.update(over)
    return spec


def hierarchy_spec(**over):
    spec = {
        "id": "dg-hier",
        "title": "組織の階層",
        "pattern": "hierarchy",
        "root": {"label": "全社"},
        "children": [
            {"label": "営業部", "children": [{"label": "第1課"}]},
            {"label": "開発部"},
        ],
    }
    spec.update(over)
    return spec


def cycle_spec(**over):
    spec = {
        "id": "dg-cycle",
        "title": "改善のサイクル",
        "pattern": "cycle",
        "steps": [
            {"id": "cy1", "label": "計画する"},
            {"id": "cy2", "label": "実行する"},
            {"id": "cy3", "label": "見直す"},
        ],
    }
    spec.update(over)
    return spec


def matrix_spec(**over):
    spec = {
        "id": "dg-matrix",
        "title": "施策の位置づけ",
        "pattern": "matrix",
        "x_axis": {"low": "低い", "high": "高い"},
        "y_axis": {"low": "小さい", "high": "大きい"},
        "items": [
            {"id": "mx1", "label": "施策A", "x": 0.2, "y": 0.8},
            {"id": "mx2", "label": "施策B", "x": 0.7, "y": 0.3},
        ],
    }
    spec.update(over)
    return spec


def versus_spec(**over):
    spec = {
        "id": "dg-versus",
        "title": "自前で作るか既製品を使うか",
        "pattern": "versus",
        "left": {"label": "自前で作る", "bullets": ["自由度が高い", "工数がかかる"]},
        "right": {"label": "既製品を使う", "bullets": ["早く始められる"]},
    }
    spec.update(over)
    return spec


SPEC_BUILDERS = {
    "flow": flow_spec,
    "compare": compare_spec,
    "hierarchy": hierarchy_spec,
    "cycle": cycle_spec,
    "matrix": matrix_spec,
    "versus": versus_spec,
}


def spec_for(pattern, **over):
    return SPEC_BUILDERS[pattern](**over)


def without(spec, *keys):
    out = dict(spec)
    for k in keys:
        out.pop(k, None)
    return out


# --------------------------------------------------------------------------
# SVG 走査 (標準ライブラリのみ・HTML へ inline 埋め込みされる断片なので寛容に読む)
# --------------------------------------------------------------------------

VOID_TAGS = {"br", "hr", "img", "input", "link", "meta", "source"}


class _AttrDict(dict):
    """属性名を case-insensitive に引ける dict。

    H-01: HTML の属性名は仕様上 case-insensitive であり `html.parser.HTMLParser`
    は `parse_starttag` 内で必ず `attrname.lower()` する。一方 SVG 仕様は
    `viewBox` をキャメルケースで書くことを要求するため、素の dict では
    `get("viewBox")` が生成側の出力に関わらず必ず None になる。
    照合を case-insensitive にすることで、仕様どおりの照合へ戻す
    (受入基準の緩和ではなく、ハーネス側の照合誤りの是正)。
    """

    def _resolve(self, key):
        if dict.__contains__(self, key):
            return key
        if isinstance(key, str):
            low = key.lower()
            if dict.__contains__(self, low):
                return low
            for k in dict.keys(self):
                if isinstance(k, str) and k.lower() == low:
                    return k
        return key

    def __getitem__(self, key):
        return dict.__getitem__(self, self._resolve(key))

    def __contains__(self, key):
        return dict.__contains__(self, self._resolve(key))

    def get(self, key, default=None):
        return dict.get(self, self._resolve(key), default)


class Element:
    __slots__ = ("tag", "attrs", "text", "children", "parent")

    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = attrs if isinstance(attrs, _AttrDict) else _AttrDict(attrs)
        self.text = ""
        self.children = []
        self.parent = parent

    def get(self, name, default=None):
        return self.attrs.get(name, default)

    def __repr__(self):  # pragma: no cover - 診断用
        return "<%s %r>" % (self.tag, self.attrs)


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self._stack = []

    def _make(self, tag, attrs):
        el = Element(
            tag,
            _AttrDict((k, v if v is not None else "") for k, v in attrs),
            self._stack[-1] if self._stack else None,
        )
        if el.parent is not None:
            el.parent.children.append(el)
        self.elements.append(el)
        return el

    def handle_starttag(self, tag, attrs):
        el = self._make(tag, attrs)
        if tag not in VOID_TAGS:
            self._stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self._make(tag, attrs)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        for el in self._stack:
            el.text += data


def parse(svg_text):
    parser = _Collector()
    parser.feed(svg_text)
    parser.close()
    return parser.elements


def root_svg(svg_text):
    for el in parse(svg_text):
        if el.tag == "svg":
            return el
    return None


def tags(svg_text):
    return [el.tag for el in parse(svg_text)]


def drawing_elements(svg_text):
    return [el for el in parse(svg_text) if el.tag in DRAWING_TAGS]


def all_attr_values(svg_text, name):
    return [el.attrs[name] for el in parse(svg_text) if name in el.attrs]


def all_ids(svg_text):
    return all_attr_values(svg_text, "id")


def emoji_hits(text):
    out = []
    for ch in text:
        cp = ord(ch)
        for lo, hi in EMOJI_RANGES:
            if lo <= cp <= hi:
                out.append(ch)
                break
    return out


# AC-C14-5: var(--token, #hex) のフォールバック位置以外に 16 進カラーリテラルを置かない
VAR_FALLBACK_RE = re.compile(r"var\(\s*--[A-Za-z0-9_-]+\s*,\s*#[0-9A-Fa-f]{3,8}\s*\)")
HEX_LITERAL_RE = re.compile(r"#[0-9A-Fa-f]{3,8}(?![0-9A-Za-z_-])")


def raw_hex_literals(svg_text):
    stripped = VAR_FALLBACK_RE.sub("", svg_text)
    return HEX_LITERAL_RE.findall(stripped)


def external_reference_hits(svg_text):
    """AC-C14-3 / SC-10: 取得を発生させ得る参照で data: 以外を指すもの。

    同一文書内の fragment 参照 (`#id` / `url(#id)`) は取得を発生させないため対象外
    (SC-02 が確立した境界。README の gaps 参照)。
    """
    hits = []
    for el in parse(svg_text):
        for name, value in el.attrs.items():
            low = name.lower()
            if low not in FETCHING_ATTRS and not low.endswith(":href"):
                continue
            v = value.strip()
            if v.startswith("data:") or v.startswith("#") or v == "":
                continue
            hits.append((el.tag, name, value))
    for m in re.finditer(r"url\(\s*['\"]?([^'\")]*)['\"]?\s*\)", svg_text):
        v = m.group(1).strip()
        if v.startswith("data:") or v.startswith("#"):
            continue
        hits.append(("css", "url()", v))
    for prefix in EXTERNAL_PREFIXES:
        if prefix in svg_text:
            hits.append(("text", "prefix", prefix))
    if "@import" in svg_text:
        hits.append(("css", "@import", "@import"))
    return hits


def stderr_mentions(res, candidates):
    return any(str(c) in res.stderr for c in candidates)
