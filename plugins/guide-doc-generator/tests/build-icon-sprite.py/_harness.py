"""C15 build-icon-sprite.py の受入テスト共通ヘルパ (P04-C15-01)。

方針:
- 契約は `plugin-plans/guide-doc-generator/briefs/script-brief-C15.json` の
  argv / stdout / stderr / exit_codes / algorithm / acceptance_checks /
  failure_modes / icon_set_source と、
  `plugin-plans/guide-doc-generator/briefs/script-brief-C16.json` の
  detections SC-05 / SC-06 / SC-07 (canonical_rules CR-EMOJI を含む) からだけ起こす。
  推測で新しい契約を発明しない。判断が必要だった点は README の gaps に書いた。
- 実装が未存在でも import 例外にしない。require_script() が「実装が未存在」という
  診断可能なアサーション失敗 (failures) として赤を出す。setUpClass でも例外を投げない。
- 実 plugin ツリーへ 1 バイトも書かない。アイコンセット正本も構成データも tempdir に作る。
  C15 の write_scope は none であり、テスト側も同じ制約で書く。

C15 と C16 の関係 (couples_with):
  C15 が出す symbols_svg は C11 が **無加工で** <body> 直後へ置く契約
  (script-brief-C11.json algorithm 9)。したがって C16 の SC-06 / SC-07 が
  生成 HTML に対して課す条件は、そのまま C15 の出力へ課される。
  本ハーネスは SC-05 / SC-06 / SC-07 の判定を C16 ブリーフの記述から
  テスト側に実装し (assert_sc06_style / assert_sc07_pairing / find_emoji)、
  C15 の出力へ掛ける。C16 の実装有無に依存させないためである。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

# tests/build-icon-sprite.py/ -> tests -> guide-doc-generator -> plugins -> repo root
TESTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TESTS_DIR.parents[1]
REPO_ROOT = TESTS_DIR.parents[3]

SCRIPT = PLUGIN_ROOT / "scripts" / "build-icon-sprite.py"
PLUGIN_NAME = "guide-doc-generator"

# P04-x-05 G-03: 絵文字判定の唯一の正本は C16 の CR-EMOJI であり、C15 は
# この script を importlib で読み込んで scan_emoji(text) を呼ぶ (独自判定を持たない)。
# 解決できない場合 C15 は fail-closed で exit 2 になる契約なので、
# plugin ツリーを模す際は既定でこの script も複製する。
C16_SCRIPT = PLUGIN_ROOT / "scripts" / "verify-handout-selfcontained.py"
C16_MODULE_FUNCTION = "scan_emoji"

# AC-C15-11: 絵文字判定に関するコードポイント列挙が script 本文に 0 件。
# 旧 algorithm[4] がハードコードしていたレンジと、CR-EMOJI 側の代表値。
EMOJI_CODEPOINT_TOKENS = (
    "1F300", "1FAFF", "1F600", "1F64F", "1F900", "2600", "27BF",
    "2190", "21FF", "FE0F", "20E3", "2714", "2699",
)

# --------------------------------------------------------------------------
# ブリーフ由来の定数 (script-brief-C15.json)
# --------------------------------------------------------------------------

# argv: --format の enum (既定 both)
FORMATS = ("both", "symbols", "manifest")
DEFAULT_FORMAT = "both"

# icon_set_source.schema
SET_VERSION_KEY = "set_version"
ICONS_KEY = "icons"

# algorithm 8: id = "hbic-" + name
SYMBOL_ID_PREFIX = "hbic-"

# algorithm 4: stroke_width の許容域 (--strict-style 時は範囲外で exit 1)
STROKE_WIDTH_MIN = 2.2
STROKE_WIDTH_MAX = 2.6

# algorithm 4: name の字種
NAME_RE = re.compile(r"^[a-z0-9-]+$")

# stdout 契約 (--format=both の結果 JSON のキー)
OUT_SYMBOLS = "symbols_svg"
OUT_USED = "used"
OUT_UNUSED = "unused_in_set"
OUT_SET_VERSION = "set_version"
USED_FIELDS = ("name", "symbol_id", "use_href", "ref_count", "ref_paths")

# icon_set_source.vocabulary (41 語)。AC-C15-10 の grep 対象でもある。
VOCABULARY = (
    "check", "cross", "arrow-right", "arrow-down", "clock", "calendar",
    "user", "users", "chat", "document", "folder", "download", "upload",
    "link", "search", "settings", "lightbulb", "warning", "info", "star",
    "flag", "target", "book", "pencil", "list", "grid", "chart", "play",
    "pause", "refresh", "lock", "unlock", "mail", "bell", "bookmark",
    "sparkle", "puzzle", "compass", "step-1", "step-2", "step-3",
)

# AC-C15-9 が名指しする標準ライブラリ (「など」なので上位集合を許すが yaml は 0 件)
DECLARED_IMPORTS = {
    "json", "sys", "os", "argparse", "html", "re", "difflib", "pathlib",
}
FORBIDDEN_IMPORTS = {
    "yaml", "lxml", "bs4", "requests", "urllib", "urllib3", "http",
    "socket", "PIL", "numpy", "jinja2", "cairosvg", "svgwrite",
}

# --------------------------------------------------------------------------
# C16 ブリーフ由来の定数 (SC-06 / CR-EMOJI)
# --------------------------------------------------------------------------

# SC-06: data-hb-kind の語彙は C11 html_attribute_contract が正本 (icon|mascot|decor|figure)
KIND_ATTR = "data-hb-kind"
KIND_VALUES = ("icon", "mascot", "decor", "figure")

# SC-06: data-hb-kind="icon" が満たすべき 5 属性 (完全一致)
ICON_STYLE = {
    "viewBox": "0 0 24 24",
    "fill": "none",
    "stroke": "currentColor",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
}

# algorithm 9 が固定する属性の並び (data-hb-kind の位置はブリーフに記述が無いため
# 部分列として検査する。README gaps G-02 を参照)
SYMBOL_ATTR_ORDER = (
    "id", "viewBox", "fill", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin",
)

# CR-EMOJI 層 1 (単独で違反) — script-brief-C16.json SC-05 より
_EMOJI_L1_RANGES = (
    (0x1F000, 0x1F02F), (0x1F0A0, 0x1F0FF), (0x1F100, 0x1F1FF),
    (0x1F200, 0x1F2FF), (0x1F300, 0x1F5FF), (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF), (0x1F700, 0x1F8FF), (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FAFF), (0xE0020, 0xE007F),
    (0x2648, 0x2653), (0x2753, 0x2755), (0x2795, 0x2797), (0x2B05, 0x2B07),
)
_EMOJI_L1_SINGLES = frozenset(
    [
        0xFE0F, 0x20E3, 0x203C, 0x2049, 0x2614, 0x2615, 0x267F, 0x2693,
        0x26A1, 0x26AA, 0x26AB, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE,
        0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5, 0x26FA, 0x26FD, 0x2705,
        0x270A, 0x270B, 0x2728, 0x274C, 0x274E, 0x2757, 0x27B0, 0x27BF,
        0x2934, 0x2935, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55,
    ]
)

# CR-EMOJI 層 2 (直後に U+FE0F が続くときのみ違反) の代表値。
# 本テストで使うのは「VS16 なしなら通る」ことの回帰なので全件は要らない。
EMOJI_L2_SAMPLES = ("✔", "©", "⚙", "▶", "❤")

# CR-EMOJI が明示的に非検出とする記号 (★ ✔ © ♪ ■ 等)
NON_EMOJI_SYMBOLS = "★☆✔©♪■→…〜"


def is_layer1_emoji(cp: int) -> bool:
    if cp in _EMOJI_L1_SINGLES:
        return True
    return any(lo <= cp <= hi for lo, hi in _EMOJI_L1_RANGES)


def find_emoji(text: str) -> list[tuple[int, int]]:
    """CR-EMOJI (SC-05 二層規則) を適用し (index, codepoint) を返す。

    層 1 は単独で違反。層 2 は U+FE0F を伴うときだけ違反だが、U+FE0F 自体が
    層 1 なので、層 1 の走査だけで層 2 + VS16 の組も必ず 1 件以上検出される。
    ブロック丸ごとの denylist は用いない (RESOLUTION-P03 Y-03)。
    """
    hits = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if is_layer1_emoji(cp):
            hits.append((i, cp))
    return hits


def format_codepoints(text: str) -> str:
    return " ".join("U+{:04X}".format(ord(c)) for c in text)


# --------------------------------------------------------------------------
# 実装の存在確認 (赤は import 例外ではなく failures で出す)
# --------------------------------------------------------------------------


def require_script(tc: unittest.TestCase) -> Path:
    if not SCRIPT.is_file():
        tc.fail(
            "実装が未存在: {} (P04 時点ではこの失敗が期待値。P05 で解消する)".format(SCRIPT)
        )
    return SCRIPT


def script_source(tc: unittest.TestCase) -> str:
    require_script(tc)
    return SCRIPT.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 実行
# --------------------------------------------------------------------------


def clean_env(**overrides) -> dict:
    env = dict(os.environ)
    for key in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT"):
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    for k, v in overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


def run_raw(script: Path, args, env=None, cwd=None, stdin_data: str | None = None):
    cmd = [sys.executable, str(script), *[str(a) for a in args]]
    return subprocess.run(
        cmd,
        input=(stdin_data or "").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env if env is not None else clean_env(),
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        timeout=60,
    )


def run_sprite(
    tc: unittest.TestCase,
    config_path=None,
    icon_set=None,
    fmt=None,
    strict_style=False,
    extra_args=(),
    env=None,
    cwd=None,
    stdin_data: str | None = None,
    script=None,
):
    """C15 を argv 契約どおりに起動する。"""
    if script is None:
        script = require_script(tc)
    args = []
    if config_path is not None:
        args += ["--config", config_path]
    if icon_set is not None:
        args += ["--icon-set", icon_set]
    if fmt is not None:
        args += ["--format", fmt]
    if strict_style:
        args += ["--strict-style"]
    args += list(extra_args)
    return run_raw(script, args, env=env, cwd=cwd, stdin_data=stdin_data)


def out_text(proc) -> str:
    return proc.stdout.decode("utf-8")


def err_text(proc) -> str:
    return proc.stderr.decode("utf-8")


def describe(proc) -> str:
    return "exit={}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        proc.returncode, out_text(proc)[:4000], err_text(proc)[:4000]
    )


def expect_exit(tc: unittest.TestCase, proc, code: int, why: str = ""):
    if proc.returncode != code:
        tc.fail("exit {} を期待したが {} だった{}\n{}".format(
            code, proc.returncode, (" / " + why) if why else "", describe(proc)
        ))


def parse_stdout_json(tc: unittest.TestCase, proc):
    text = out_text(proc)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        tc.fail("stdout が結果 JSON として読めない ({}):\n{}".format(exc, describe(proc)))


def sprite_result(tc: unittest.TestCase, proc):
    """--format=both の結果 JSON をキー存在確認つきで取り出す。"""
    expect_exit(tc, proc, 0)
    data = parse_stdout_json(tc, proc)
    if not isinstance(data, dict):
        tc.fail("--format=both の stdout は 1 オブジェクトである契約: {}".format(type(data)))
    for key in (OUT_SYMBOLS, OUT_USED, OUT_UNUSED, OUT_SET_VERSION):
        if key not in data:
            tc.fail("結果 JSON に {} が無い (stdout 契約): keys={}".format(key, sorted(data)))
    return data


# --------------------------------------------------------------------------
# アイコンセット正本の組み立て (icon_set_source.schema)
# --------------------------------------------------------------------------


def icon(name: str, paths=None, stroke_width: float = 2.2, title=None) -> dict:
    # paths=[] は「空配列」という検査対象の値。既定値へ丸めない。
    if paths is None:
        paths = ["M4 12l5 5L20 6"]
    entry = {"name": name, "paths": list(paths), "stroke_width": stroke_width}
    if title is not None:
        entry["title"] = title
    return entry


def make_icon_set(names=None, icons=None, set_version: str = "1") -> dict:
    """配列順が正本の順 (icon_set_source.why_single_json_not_directory)。"""
    if icons is None:
        icons = [icon(n) for n in (names or VOCABULARY)]
    return {SET_VERSION_KEY: set_version, ICONS_KEY: list(icons)}


def write_icon_set(tmp: Path, data, name: str = "icon-set.json") -> Path:
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    else:
        text = str(data)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# 構成データの組み立て (algorithm 5 の走査対象キーだけを使う)
# --------------------------------------------------------------------------


def block(btype: str = "text", block_icon=None, items=None, cards=None, tabs=None) -> dict:
    b = {"type": btype}
    if block_icon is not None:
        b["icon"] = block_icon
    if items is not None:
        b["items"] = [{"label": "項目", "icon": i} if isinstance(i, str) else i for i in items]
    if cards is not None:
        b["cards"] = [{"label": "カード", "icon": i} if isinstance(i, str) else i for i in cards]
    if tabs is not None:
        b["tabs"] = [{"label": "タブ", "icon": i} if isinstance(i, str) else i for i in tabs]
    return b


def section(sid: str, section_icon=None, blocks=None) -> dict:
    s = {"id": sid, "title": "セクション " + sid, "blocks": list(blocks or [])}
    if section_icon is not None:
        s["icon"] = section_icon
    return s


def make_config(sections=None, nav_icon=None, goal_chips=None, title: str = "研修ハンドアウト") -> dict:
    """C12 --normalize 出力相当の最小構成データ。

    走査対象キー (algorithm 5): sections[].icon / sections[].blocks[].icon /
    blocks[].items[].icon / blocks[].cards[].icon / blocks[].tabs[].icon /
    nav.icon / hero.goal_chips[].icon
    """
    cfg = {
        "schema_version": 1,
        "title": title,
        "nav": {"label": "目次"},
        "hero": {"goal": "できるようになること"},
        "sections": list(sections or []),
    }
    if nav_icon is not None:
        cfg["nav"]["icon"] = nav_icon
    if goal_chips is not None:
        cfg["hero"]["goal_chips"] = [
            {"label": "チップ", "icon": c} if isinstance(c, str) else c for c in goal_chips
        ]
    return cfg


def write_config(tmp: Path, config, name: str = "handout-config.json") -> Path:
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(config, (dict, list)):
        text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    else:
        text = str(config)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# SVG の読み取り (html.parser。標準ライブラリのみ)
# --------------------------------------------------------------------------


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []  # (tagname, {attr: value}, order)
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs), [k for k, _ in attrs]))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs), [k for k, _ in attrs]))

    def handle_data(self, data):
        self.text.append(data)


def parse_svg(tc: unittest.TestCase, markup: str) -> _TagCollector:
    parser = _TagCollector()
    try:
        parser.feed(markup)
        parser.close()
    except Exception as exc:  # pragma: no cover - 整形式が契約
        tc.fail("symbols_svg が HTML パーサで読めない: {}\n{}".format(exc, markup[:2000]))
    return parser


def tags_named(collector: _TagCollector, name: str):
    return [t for t in collector.tags if t[0] == name.lower()]


def symbol_ids(collector: _TagCollector) -> list[str]:
    return [attrs.get("id") for _tag, attrs, _order in tags_named(collector, "symbol")]


def use_refs(collector: _TagCollector) -> list[str]:
    refs = []
    for _tag, attrs, _order in tags_named(collector, "use"):
        href = attrs.get("href") or attrs.get("xlink:href")
        if href is not None:
            refs.append(href)
    return refs


# --------------------------------------------------------------------------
# C16 detection をテスト側に実装したもの
# --------------------------------------------------------------------------


def assert_no_emoji(tc: unittest.TestCase, text: str, where: str = "出力"):
    """AC-C15-3 / SC-05。"""
    hits = find_emoji(text)
    if hits:
        sample = ", ".join("U+{:04X}@{}".format(cp, i) for i, cp in hits[:10])
        tc.fail("{}に絵文字 (CR-EMOJI 層 1) が {} 件: {}".format(where, len(hits), sample))


def assert_sc06_style(tc: unittest.TestCase, markup: str):
    """SC-06。data-hb-kind の分類漏れが無く、icon は 5 属性 + stroke-width を満たす。"""
    collector = parse_svg(tc, markup)
    targets = [t for t in collector.tags if t[0] in ("svg", "symbol")]
    if not targets:
        tc.fail("symbols_svg に <svg>/<symbol> が 1 個も無い:\n{}".format(markup[:2000]))
    for tag, attrs, _order in targets:
        kind = attrs.get(KIND_ATTR)
        if kind is None:
            tc.fail(
                "SC-06 分類不能: <{}> に {} が無い (未分類は C16 が違反へ計上する)\n{}".format(
                    tag, KIND_ATTR, markup[:2000]
                )
            )
        if kind not in KIND_VALUES:
            tc.fail("SC-06 {}=\"{}\" は語彙外 (許容 {})".format(KIND_ATTR, kind, KIND_VALUES))
        if kind != "icon":
            continue
        for attr, want in ICON_STYLE.items():
            got = attrs.get(attr.lower())
            if got is None:
                tc.fail("SC-06 <{} {}=icon> に {} が無い: {}".format(tag, KIND_ATTR, attr, attrs))
            if " ".join(got.split()) != want:
                tc.fail(
                    "SC-06 <{} {}=icon> の {} が \"{}\" (期待 \"{}\")".format(
                        tag, KIND_ATTR, attr, got, want
                    )
                )
        raw = attrs.get("stroke-width")
        if raw is None:
            tc.fail("SC-06 <{} {}=icon> に stroke-width が無い: {}".format(tag, KIND_ATTR, attrs))
        try:
            width = float(raw)
        except ValueError:
            tc.fail("SC-06 stroke-width が数値でない: {!r}".format(raw))
        if not (STROKE_WIDTH_MIN <= width <= STROKE_WIDTH_MAX):
            tc.fail(
                "SC-06 stroke-width={} が [{}, {}] の外".format(
                    width, STROKE_WIDTH_MIN, STROKE_WIDTH_MAX
                )
            )


def assert_sc07_pairing(tc: unittest.TestCase, result: dict):
    """SC-07 の C15 側。symbol 定義集合と参照表 (used) が 1:1 で、重複が無い。

    C15 単体の出力には <use> が含まれない (参照は C11 が use_href から書く)。
    したがって C15 が保証すべきは「定義 = 参照表」の 1:1 である。
    """
    collector = parse_svg(tc, result[OUT_SYMBOLS] or "")
    defined = symbol_ids(collector)
    if len(defined) != len(set(defined)):
        tc.fail("SC-07 symbol id が重複している: {}".format(defined))
    if any(sid is None for sid in defined):
        tc.fail("SC-07 id を持たない <symbol> がある: {}".format(defined))

    used = result[OUT_USED]
    if not isinstance(used, list):
        tc.fail("used が配列でない: {!r}".format(type(used)))
    manifest_ids = []
    for entry in used:
        if not isinstance(entry, dict):
            tc.fail("used の要素がオブジェクトでない: {!r}".format(entry))
        for field in USED_FIELDS:
            if field not in entry:
                tc.fail("used の要素に {} が無い: keys={}".format(field, sorted(entry)))
        if entry["symbol_id"] != SYMBOL_ID_PREFIX + entry["name"]:
            tc.fail(
                "algorithm 8 違反: symbol_id={} は hbic-{} でない".format(
                    entry["symbol_id"], entry["name"]
                )
            )
        if entry["use_href"] != "#" + entry["symbol_id"]:
            tc.fail("use_href={} が #symbol_id でない".format(entry["use_href"]))
        manifest_ids.append(entry["symbol_id"])

    if len(manifest_ids) != len(set(manifest_ids)):
        tc.fail("SC-07 参照表に重複がある: {}".format(manifest_ids))
    if defined != manifest_ids:
        tc.fail(
            "SC-07 1:1 違反。symbol 定義 {} と参照表 {} が (順序を含め) 一致しない".format(
                defined, manifest_ids
            )
        )

    # 未使用は sprite へ出さない (algorithm 11 / checklist C11)
    unused = result[OUT_UNUSED]
    if not isinstance(unused, list):
        tc.fail("unused_in_set が配列でない: {!r}".format(type(unused)))
    leaked = [n for n in unused if (SYMBOL_ID_PREFIX + str(n)) in set(defined)]
    if leaked:
        tc.fail("SC-07 未使用アイコンが sprite に混入している: {}".format(leaked))


# --------------------------------------------------------------------------
# plugin 実体解決の検査用に一時 plugin ツリーを作る (algorithm 2)
# --------------------------------------------------------------------------


def make_plugin_tree(
    tc: unittest.TestCase,
    root: Path,
    icon_set_data=None,
    plugin_name: str = PLUGIN_NAME,
    with_manifest: bool = True,
    with_icon_set: bool = True,
    with_script: bool = True,
    with_c16: bool = True,
) -> Path:
    """tempdir に plugin 実体 (scripts/ + assets/icons/ + .claude-plugin/) を作る。

    実 plugin ツリーへは書かず、script を tempdir へ複製して __file__ 相対解決を
    検査できるようにする。戻り値は複製された script のパス。
    """
    root = Path(root)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    if with_manifest:
        (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": plugin_name, "version": "0.1.0"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if with_icon_set:
        write_icon_set(root / "assets" / "icons", icon_set_data or make_icon_set())
    copied = root / "scripts" / SCRIPT.name
    if with_script:
        require_script(tc)
        shutil.copy2(SCRIPT, copied)
    # P04-x-05 G-03: C15 は絵文字判定を C16 へ委譲するため、模した plugin ツリーにも
    # C16 の script が要る。存在しない間は C15 が fail-closed で exit 2 になるのが正しく、
    # その赤は「C16 未実装」を指す (ここで stub を置くと第 2 の正本になるので置かない)。
    if with_c16 and C16_SCRIPT.is_file():
        shutil.copy2(C16_SCRIPT, root / "scripts" / C16_SCRIPT.name)
    return copied


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tree_snapshot(root: Path) -> dict:
    snap = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_symlink():
            snap[str(path.relative_to(root))] = b"<symlink>" + os.readlink(path).encode("utf-8")
        elif path.is_file():
            snap[str(path.relative_to(root))] = path.read_bytes()
    return snap
