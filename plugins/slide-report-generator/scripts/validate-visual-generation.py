#!/usr/bin/env python3
"""生成則 (視覚生成規約 E1-E6 / VGCONST) の静的検査器。

既存の検査器はいずれも上限 (超えるな) を見る禁止則であり、面の上に階層を
「作れているか」を見る検査が存在しなかった。そのため意匠を手で直しても次の
生成で平板へ戻る。本検査器はその生成則のうち、生成済み deck の
index.html + CSS だけで確定できるものを機械で踏む。

正本: skills/run-slide-report-generate/references/visual-generation-rules.md
閾値はこのファイル内に直値で持たず、実行時に上記 md から抽出する。抽出でき
ない項目が 1 つでもあれば既定値へ落とさず即座に失敗する (fail-closed)。
値の写経こそが今回の病根であり、写経した瞬間に正本が 2 つになるため。

使い方:
    validate-visual-generation.py <deck-dir|index.html> [...] [--json] [--strict]
    validate-visual-generation.py --self-test

終了コード:
    0 = 検出なし / 1 = error 検出 (--strict では warn も) / 2 = 引数不正
    3 = 入力または規約が読めない (fail-closed)
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    import tinycss2
except ImportError as exc:  # pragma: no cover - 環境依存
    print(f"依存ライブラリが読めない: {exc} (bs4 / tinycss2 が要る)", file=sys.stderr)
    raise SystemExit(3)


# ---------------------------------------------------------------------------
# 規約 (SSOT) の読み込み
#
# visual-generation-rules.md は散文 Markdown であり構造化ブロックを持たない。
# そのため抽出は「条文の言い回しへ固定した錨」で行う。錨が外れた場合は黙って
# 既定値へ落ちず RuleLoadError を投げる (= 検査器が緑にならない)。
# ---------------------------------------------------------------------------

RULES_RELATIVE = Path("skills/run-slide-report-generate/references/visual-generation-rules.md")


class RuleLoadError(Exception):
    """規約から閾値を抽出できなかった。既定値で補わずに落とすための例外。"""


@dataclass
class RuleSet:
    source: str
    weight_intensity: dict[int, float]          # E1 W
    inversion_intensity: float                  # E1 C
    intensity_ratio_min: float                  # E1 I1/I2
    role_names: list[str]                       # E2 lead/body/label
    role_max_per_face: int                      # E2 面あたり役割種数の上限
    role_ratio_min: dict[tuple[str, str], float]  # E2 隣接役割比
    inversion_count_per_face: int               # E4 個数
    inversion_area_min: float                   # E4 面積比 (要 playwright)
    inversion_area_max: float                   # E4 面積比 (要 playwright)
    radius_default_px: float                    # VGCONST_003 角丸
    radius_figure_px: float                     # VGCONST_003 図版のみ
    hairline_px_min: float                      # VGCONST_003 hairline 帯
    hairline_px_max: float
    divider_px: float                           # VGCONST_003 下罫
    shadow_forbidden: bool                      # VGCONST_003 影
    stroke_steps_px: list[float]                # VGCONST_004 線幅 3 段
    weight_steps: list[int]                     # VGCONST_005 ウェイト 3 段
    weight_top: int                             # VGCONST_005 最上位ウェイト
    weight_top_max_per_face: int                # VGCONST_005 700 の面あたり箇所数
    color_paper: str                            # VGCONST_001
    color_ink: str
    color_inverted_text: str
    face_class_names: list[str]                 # 用語集「面」
    face_attributes: list[str]
    origin: str = "prose"                       # json / prose (どちらから読んだか)


def _search(pattern: str, text: str, what: str, flags: int = 0) -> re.Match:
    m = re.search(pattern, text, flags)
    if not m:
        raise RuleLoadError(
            f"規約から {what} を抽出できない (錨: /{pattern}/)。"
            "条文の言い回しが変わったなら錨を追随させる。直値で埋めてはいけない")
    return m


def load_rules(path: Path) -> RuleSet:
    """規約から閾値を読む。

    json ブロック (散文の写し) があればそれを採り、同時に散文からも抽出して
    突き合わせる。食い違えば「どちらが正しいか分からない」状態なので判定せず
    落とす。json が無ければ散文だけで読む。どちらも取れなければ落とす。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuleLoadError(f"規約 {path} を読めない ({exc})") from exc

    prose = load_rules_from_prose(path, text)
    block = extract_json_block(text)
    if block is None:
        return prose
    machine = load_rules_from_json(path, block)
    diffs = diff_rules(machine, prose)
    if diffs:
        raise RuleLoadError(
            "規約の json ブロックと散文の条文が食い違う。写しがズレた状態では"
            "どちらが正本か決められないため判定しない。両方を同じ値へ直すこと: "
            + " / ".join(diffs))
    return machine


def extract_json_block(text: str) -> str | None:
    """機械可読ブロック (```json ... ```) を取り出す。無ければ None。"""
    blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.S)
    if not blocks:
        return None
    if len(blocks) > 1:
        raise RuleLoadError(f"json ブロックが {len(blocks)} 個ある。写しは 1 つだけ置くこと")
    return blocks[0]


def _need(obj: dict, *keys):
    node = obj
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise RuleLoadError(f"json ブロックに {'.'.join(keys)} が無い")
        node = node[key]
    return node


def load_rules_from_json(path: Path, raw: str) -> RuleSet:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuleLoadError(f"json ブロックを解釈できない ({exc})") from exc
    ratio = _need(data, "e2", "ratio_min")
    role_ratio: dict[tuple[str, str], float] = {}
    for key, value in ratio.items():
        if ">" not in key:
            raise RuleLoadError(f"e2.ratio_min のキー {key} は '大きい方>小さい方' の形で書く")
        big, small = key.split(">", 1)
        role_ratio[(big.strip(), small.strip())] = float(value)
    return RuleSet(
        source=str(path),
        weight_intensity={int(k): float(v) for k, v in _need(data, "e1", "weight_intensity").items()},
        inversion_intensity=float(_need(data, "e1", "inversion_intensity")),
        intensity_ratio_min=float(_need(data, "e1", "intensity_ratio_min")),
        role_names=list(_need(data, "e2", "roles")),
        role_max_per_face=int(_need(data, "e2", "role_max_per_face")),
        role_ratio_min=role_ratio,
        inversion_count_per_face=int(_need(data, "e4", "count_per_face")),
        inversion_area_min=float(_need(data, "e4", "area_ratio_min")),
        inversion_area_max=float(_need(data, "e4", "area_ratio_max")),
        radius_default_px=float(_need(data, "vgconst_003", "radius_px")),
        radius_figure_px=float(_need(data, "vgconst_003", "radius_figure_px")),
        hairline_px_min=float(_need(data, "vgconst_003", "hairline_px_min")),
        hairline_px_max=float(_need(data, "vgconst_003", "hairline_px_max")),
        divider_px=float(_need(data, "vgconst_003", "divider_px")),
        shadow_forbidden=bool(_need(data, "vgconst_003", "shadow_forbidden")),
        stroke_steps_px=[float(v) for v in _need(data, "vgconst_004", "stroke_steps_px")],
        weight_steps=[int(v) for v in _need(data, "vgconst_005", "weight_steps")],
        weight_top=int(_need(data, "vgconst_005", "top_weight")),
        weight_top_max_per_face=int(_need(data, "vgconst_005", "top_weight_max_per_face")),
        color_paper=str(_need(data, "vgconst_001", "paper")).lower(),
        color_ink=str(_need(data, "vgconst_001", "ink")).lower(),
        color_inverted_text=str(_need(data, "vgconst_001", "inverted_text")).lower(),
        face_class_names=list(_need(data, "face", "class_names")),
        face_attributes=list(_need(data, "face", "attributes")),
        origin="json",
    )


def diff_rules(machine: RuleSet, prose: RuleSet) -> list[str]:
    """写し (json) と正本 (散文) の食い違いを列挙する。"""
    diffs = []
    for field_name in RuleSet.__dataclass_fields__:
        if field_name in {"source", "origin"}:
            continue
        a = getattr(machine, field_name)
        b = getattr(prose, field_name)
        if isinstance(a, list) and isinstance(b, list):
            same = [str(x) for x in a] == [str(x) for x in b]
        else:
            same = a == b
        if not same:
            diffs.append(f"{field_name}: json={a} 散文={b}")
    return diffs


def load_rules_from_prose(path: Path, text: str) -> RuleSet:

    # E1: 強度式の係数 (コードブロック内)
    w_raw = _search(r"W:\s*font-weight\s*((?:\d+\s*->\s*[\d.]+\s*/?\s*)+)", text, "E1 の W (ウェイト係数)")
    weight_intensity = {int(a): float(b) for a, b in re.findall(r"(\d+)\s*->\s*([\d.]+)", w_raw.group(1))}
    if len(weight_intensity) < 2:
        raise RuleLoadError("E1 の W が 2 段未満しか取れない")
    c_raw = _search(r"C:\s*反転[^\n]*?->\s*([\d.]+)", text, "E1 の C (反転係数)")
    inversion_intensity = float(c_raw.group(1))
    ratio = float(_search(r"I1\s*/\s*I2\s*>=\s*([\d.]+)", text, "E1 の I1/I2 下限").group(1))

    # E2: 役割と隣接比
    roles_raw = _search(r"役割は\s*((?:`[a-z]+`\s*/?\s*)+)の\s*\d+\s*種のみ", text, "E2 の役割名")
    role_names = re.findall(r"`([a-z]+)`", roles_raw.group(1))
    role_max = int(_search(r"使ってよい役割は\s*\*\*(\d+)\s*種まで\*\*", text, "E2 の役割種数上限").group(1))
    role_ratio: dict[tuple[str, str], float] = {}
    for big, small, r in re.findall(r"\|\s*`([a-z]+)`\s*->\s*`([a-z]+)`\s*\|\s*\*\*([\d.]+)\*\*", text):
        role_ratio[(big, small)] = float(r)
    if not role_ratio:
        raise RuleLoadError("E2 の隣接役割比の表を抽出できない")

    # E4: 反転ブロック
    inv_count = int(_search(r"反転ブロックは面に\s*\*\*ちょうど\s*(\d+)\s*個\*\*", text, "E4 の反転ブロック個数").group(1))
    area = _search(r"stage\s*面積\s*が\s*\*\*([\d.]+)\s*以上\s*([\d.]+)\s*以下\*\*", text, "E4 の面積比レンジ")

    # VGCONST_003 / 004 / 005
    radius_default = float(_search(r"角丸は\s*([\d.]+)px", text, "VGCONST_003 の角丸既定値").group(1))
    radius_figure = float(_search(r"図版の外形のみ\s*([\d.]+)px", text, "VGCONST_003 の図版角丸").group(1))
    hair = _search(r"輪郭は\s*([\d.]+)-([\d.]+)px\s*の\s*hairline", text, "VGCONST_003 の hairline 帯")
    divider = float(_search(r"([\d.]+)px\s*の下罫", text, "VGCONST_003 の下罫").group(1))
    shadow_forbidden = bool(re.search(r"影は使わない", text))
    if not shadow_forbidden:
        raise RuleLoadError("VGCONST_003 の影の条文を抽出できない")
    steps_raw = _search(r"図解内の線は\s*((?:[\d.]+px\s*/?\s*)+)の\s*\d+\s*段のみ", text, "VGCONST_004 の線幅 3 段")
    stroke_steps = [float(v) for v in re.findall(r"([\d.]+)px", steps_raw.group(1))]
    weights_raw = _search(r"書体ウェイトは\s*((?:\d+\s*/?\s*)+)の\s*\d+\s*段", text, "VGCONST_005 のウェイト段")
    weight_steps = [int(v) for v in re.findall(r"(\d+)", weights_raw.group(1))]
    top = _search(r"\*\*(\d+)\s*は\s*1\s*面につき\s*(\d+)\s*箇所\*\*", text, "VGCONST_005 の最上位ウェイト箇所数")

    # VGCONST_001 (配色 3 値)
    paper = _search(r"`paper\s*(#[0-9A-Fa-f]{6})`", text, "VGCONST_001 の paper").group(1)
    ink = _search(r"`ink\s*(#[0-9A-Fa-f]{6})`", text, "VGCONST_001 の ink").group(1)
    inverted_text = _search(r"反転面の文字\s*`(#[0-9A-Fa-f]{6})`", text, "VGCONST_001 の反転面文字色").group(1)

    # 用語集「面」の定義 (engine 経路 / ひな形経路)
    face_line = _search(r"\|\s*面\s*\|([^|]+)\|", text, "用語集の「面」の定義").group(1)
    face_attrs = re.findall(r"`(data-[\w-]+)`", face_line)
    face_names = [t for t in re.findall(r"`([A-Za-z][\w-]*)`", face_line) if not t.startswith("data-")]
    if not face_names and not face_attrs:
        raise RuleLoadError("用語集の「面」から面の同定手段を抽出できない")

    return RuleSet(
        source=str(path),
        weight_intensity=weight_intensity,
        inversion_intensity=inversion_intensity,
        intensity_ratio_min=ratio,
        role_names=role_names,
        role_max_per_face=role_max,
        role_ratio_min=role_ratio,
        inversion_count_per_face=inv_count,
        inversion_area_min=float(area.group(1)),
        inversion_area_max=float(area.group(2)),
        radius_default_px=radius_default,
        radius_figure_px=radius_figure,
        hairline_px_min=float(hair.group(1)),
        hairline_px_max=float(hair.group(2)),
        divider_px=divider,
        shadow_forbidden=shadow_forbidden,
        stroke_steps_px=stroke_steps,
        weight_steps=weight_steps,
        weight_top=int(top.group(1)),
        weight_top_max_per_face=int(top.group(2)),
        color_paper=paper.lower(),
        color_ink=ink.lower(),
        color_inverted_text=inverted_text.lower(),
        face_class_names=face_names,
        face_attributes=face_attrs,
        origin="prose",
    )


def find_rules_file(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    for env in ("SRG_ROOT", "CLAUDE_PLUGIN_ROOT"):
        root = os.environ.get(env)
        if root and (Path(root) / RULES_RELATIVE).exists():
            return Path(root) / RULES_RELATIVE
    return Path(__file__).resolve().parent.parent / RULES_RELATIVE


# ---------------------------------------------------------------------------
# CSS の静的カスケード
# ---------------------------------------------------------------------------

INHERITED = {"font-size", "font-weight", "color", "letter-spacing", "line-height"}
TRACKED = INHERITED | {
    "background-color", "background", "border-radius", "box-shadow", "display",
    "border", "border-width", "border-top", "border-right", "border-bottom",
    "border-left", "border-top-width", "border-right-width", "border-bottom-width",
    "border-left-width", "outline", "outline-width", "stroke-width",
}


@dataclass
class CssRule:
    selector: str
    decls: dict[str, tuple[str, bool]]  # prop -> (value, important)
    spec: tuple[int, int, int]
    order: int
    origin: str


def _specificity(selector: str) -> tuple[int, int, int]:
    s = re.sub(r"\[[^\]]*\]", " ATTR ", selector)
    ids = len(re.findall(r"#[\w-]+", s))
    cls = len(re.findall(r"\.[\w-]+", s)) + s.count("ATTR") + len(re.findall(r":(?!:)[\w-]+", s))
    tags = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", s))
    return (ids, cls, tags)


def parse_stylesheets(sheets: list[tuple[str, str]]) -> list[CssRule]:
    """(origin, css text) の並びをカスケード順のルール列へ。@media は展開して混ぜる。"""
    rules: list[CssRule] = []
    order = 0

    def walk(nodes, origin: str) -> None:
        nonlocal order
        for node in nodes:
            if node.type == "qualified-rule":
                selector = tinycss2.serialize(node.prelude).strip()
                decls: dict[str, tuple[str, bool]] = {}
                for d in tinycss2.parse_declaration_list(node.content, skip_whitespace=True):
                    if d.type != "declaration":
                        continue
                    name = d.lower_name if not d.name.startswith("--") else d.name
                    if name.startswith("--") or name in TRACKED:
                        decls[name] = (tinycss2.serialize(d.value).strip(), bool(d.important))
                if not decls:
                    continue
                for sel in [s.strip() for s in selector.split(",") if s.strip()]:
                    order += 1
                    rules.append(CssRule(sel, decls, _specificity(sel), order, origin))
            elif node.type == "at-rule" and node.content is not None:
                lower = tinycss2.serialize(node.prelude).lower()
                if node.lower_at_keyword == "media" and "print" in lower and "screen" not in lower:
                    continue  # 印刷専用は画面上の面の見え方ではない
                walk(tinycss2.parse_rule_list(node.content, skip_whitespace=True), origin)

    for origin, text in sheets:
        walk(tinycss2.parse_stylesheet(text, skip_whitespace=True), origin)
    return rules


def parse_inline(style_attr: str) -> dict[str, tuple[str, bool]]:
    decls: dict[str, tuple[str, bool]] = {}
    for d in tinycss2.parse_declaration_list(style_attr, skip_whitespace=True):
        if d.type != "declaration":
            continue
        name = d.name if d.name.startswith("--") else d.lower_name
        decls[name] = (tinycss2.serialize(d.value).strip(), bool(d.important))
    return decls


class Cascade:
    """soupsieve で選択子を実際に当てる静的カスケード。

    完全な CSSOM ではない (擬似要素・:hover・JS 由来の class 付与は見ない)。
    そのぶん、解決できなかった値は「取れなかった」として判定不能へ倒す。
    """

    def __init__(self, soup: BeautifulSoup, rules: list[CssRule]):
        self.soup = soup
        self.unsupported: list[str] = []
        self.matched: dict[int, list[CssRule]] = {}
        for rule in rules:
            sel = rule.selector
            if "::" in sel or re.search(r":(hover|focus|active|target|not\(|is\(|where\()", sel):
                sel = re.sub(r"::?[\w-]+(\([^)]*\))?", "", sel).strip()
                if not sel:
                    continue
            try:
                targets = soup.select(sel)
            except Exception:
                self.unsupported.append(rule.selector)
                continue
            for el in targets:
                self.matched.setdefault(id(el), []).append(rule)
        self._cache: dict[tuple[int, str], tuple[str, str] | None] = {}

    def declared(self, el, prop: str) -> tuple[str, str] | None:
        """(値, 由来) を返す。未指定なら None。"""
        best = None
        best_key = None
        for rule in self.matched.get(id(el), ()):
            if prop not in rule.decls:
                continue
            value, important = rule.decls[prop]
            key = (1 if important else 0,) + rule.spec + (rule.order,)
            if best_key is None or key > best_key:
                best_key, best = key, (value, f"{rule.origin}:{rule.selector}")
        style = el.get("style") if hasattr(el, "get") else None
        if style:
            inline = parse_inline(style)
            if prop in inline:
                value, important = inline[prop]
                if best_key is None or important or best_key[0] == 0:
                    best = (value, "inline style")
        if best is None and hasattr(el, "get") and el.get(prop) and prop in {"stroke-width", "font-size", "font-weight", "fill"}:
            return (str(el.get(prop)), "presentation attribute")
        return best

    def resolved(self, el, prop: str) -> tuple[str, str] | None:
        """継承を辿って値を決める。custom property (--x) も継承扱い。"""
        key = (id(el), prop)
        if key in self._cache:
            return self._cache[key]
        node = el
        out = None
        while node is not None and getattr(node, "name", None):
            got = self.declared(node, prop)
            if got is not None:
                out = got
                break
            if prop not in INHERITED and not prop.startswith("--"):
                break
            node = node.parent
        self._cache[key] = out
        return out

    def resolve_var(self, el, value: str, depth: int = 0) -> str:
        """var(--x, fallback) を展開する。展開しきれない場合は原文を残す。"""
        if depth > 8 or "var(" not in value:
            return value

        def sub(m: re.Match) -> str:
            name = m.group(1)
            fallback = m.group(2)
            got = self.resolved(el, name)
            if got is not None:
                return self.resolve_var(el, got[0], depth + 1)
            if fallback:
                return self.resolve_var(el, fallback.strip(), depth + 1)
            return m.group(0)

        return re.sub(r"var\(\s*(--[\w-]+)\s*(?:,([^()]*(?:\([^()]*\)[^()]*)*))?\)", sub, value)


# ---------------------------------------------------------------------------
# 値の解釈
# ---------------------------------------------------------------------------

LENGTH_RE = re.compile(r"(-?[\d.]+)\s*(px|rem|em|vw|vh|vmin|vmax|%|pt)?\b")


def parse_length(value: str) -> tuple[float, str] | None:
    """長さを (数値, 単位) で返す。calc(N<unit> * <係数>) は N<unit> を採る。

    面全体で同じ係数 (--font-scale) が掛かるため、比を測る用途では係数は約分
    される。単位が混ざる場合は呼び出し側で判定不能へ倒すこと。
    """
    value = value.strip()
    if not value:
        return None
    if value.startswith("calc("):
        # 掛け算だけで組まれた calc は積へ畳む。単位付きの項が 1 つで、残りが
        # 無名数のときに限る (加減算や除算・単位混在は畳まず判定不能へ倒す)。
        flat = re.sub(r"\bcalc\(", "(", value)
        if re.search(r"[+/]", flat) or re.search(r"\d\s*-|\)\s*-", flat):
            return None
        if "var(" in flat:
            # 展開しきれない係数 (--font-scale 等) は面内で共通に掛かるため、
            # 比を測る E1/E2 では約分される。長さの項が 1 つだけのときに限り採る。
            rest = re.sub(r"var\([^()]*(?:\([^()]*\)[^()]*)*\)", "1", flat)
            if "var(" in rest:
                return None
            flat = rest
        factors = [f.strip() for f in flat.replace("(", " ").replace(")", " ").split("*") if f.strip()]
        lengths = [parse_length(f) for f in factors]
        units = [x for x in lengths if x and x[1] not in {"", "%"}]
        if len(units) != 1 or any(x is None for x in lengths):
            return None
        product = 1.0
        for x in lengths:
            product *= x[0]
        return (product, units[0][1])
    if value.startswith(("clamp(", "min(", "max(")):
        return None
    m = LENGTH_RE.fullmatch(value)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2) or ("px" if num == 0 else "")
    return (num, unit)


WEIGHT_WORDS = {"normal": 400, "bold": 700}


def parse_weight(value: str) -> int | None:
    value = value.strip().lower()
    if value in WEIGHT_WORDS:
        return WEIGHT_WORDS[value]
    if re.fullmatch(r"\d{3}", value):
        return int(value)
    return None


def normalize_color(value: str) -> str | None:
    v = value.strip().lower()
    m = re.match(r"#([0-9a-f]{3})\b", v)
    if m:
        return "#" + "".join(c * 2 for c in m.group(1))
    m = re.match(r"#([0-9a-f]{6})\b", v)
    if m:
        return "#" + m.group(1)
    m = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)", v)
    if m:
        return "#" + "".join(f"{int(float(x)):02x}" for x in m.groups())
    if v in {"black", "#000", "#000000"}:
        return "#000000"
    if v in {"white"}:
        return "#ffffff"
    return None


def color_distance(a: str, b: str) -> int:
    try:
        return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (1, 3, 5))
    except ValueError:
        return 255 * 3


# ---------------------------------------------------------------------------
# 検査
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str   # error / warn
    code: str
    face: str
    message: str


@dataclass
class DeckResult:
    deck: str
    faces: int
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warns(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warn")


CODES = {
    "VG01": "E1 第 1 位が一意でない",
    "VG02": "E1 I1/I2 が下限未満",
    "VG03": "E2 役割 (data-role) が宣言されておらず判定できない",
    "VG04": "E2 隣接役割比が下限未満",
    "VG05": "E2 面あたりの役割種数が上限超過",
    "VG06": "E4 反転ブロックの個数が規定と違う",
    "VG07": "VGCONST_003 角丸",
    "VG08": "VGCONST_003 影",
    "VG09": "VGCONST_004 線幅が 3 段のいずれでもない",
    "VG10": "VGCONST_005 ウェイトが 3 段のいずれでもない",
    "VG11": "VGCONST_005 最上位ウェイトが面あたり上限を超過",
    "VG99": "静的解析で値が取れず判定不能 (fail-closed)",
}

SKIP_TEXT_PARENTS = {"script", "style", "title", "noscript"}


def face_label(el, index: int) -> str:
    cls = ".".join(el.get("class") or [])
    ident = el.get("id") or cls or el.name
    return f"面{index + 1}({ident})"


def collect_faces(soup: BeautifulSoup, rules: RuleSet) -> list:
    faces = []
    for attr in rules.face_attributes:
        faces.extend(soup.select(f"[{attr}]"))
    if not faces:
        # 規約は面の class を `slider__item` と書く。ここを完全一致にしないのは、
        # 同じ engine が `slider__slide` / `slider-item` のような区切り違いの綴りを
        # 出す経路が過去に存在し、綴り 1 文字の差で面 0 件 (= 何も検査しない状態)
        # へ落ちるのを避けるため。拾える範囲は接頭辞 + 区切り + item/slide/page に
        # 限り、無関係な class まで面と見なさない。
        for name in rules.face_class_names:
            prefix = re.split(r"[-_]", name)[0]
            for el in soup.find_all(True):
                for cls in el.get("class") or []:
                    if re.fullmatch(rf"{re.escape(prefix)}[-_]{{1,2}}(item|slide|page)", cls):
                        faces.append(el)
                        break
    # 入れ子は外側だけを面とする
    uniq = []
    for el in faces:
        if not any(el is other for other in uniq):
            uniq.append(el)
    return [el for el in uniq if not any(other is not el and other in el.parents for other in uniq)]


def text_units(face, cascade: Cascade) -> list:
    """視覚単位の近似: 自分自身が直接テキストを持つ要素。図解内 (svg) は除く。"""
    units = []
    for el in face.find_all(True):
        if el.name in SKIP_TEXT_PARENTS or el.name == "svg":
            continue
        if any(p.name == "svg" for p in el.parents):
            continue
        own = "".join(c for c in el.children if isinstance(c, str)).strip()
        if not own:
            continue
        disp = cascade.resolved(el, "display")
        if disp and cascade.resolve_var(el, disp[0]).strip().lower().startswith("none"):
            continue
        units.append(el)
    return units


def is_inverted(el, cascade: Cascade, rules: RuleSet) -> bool:
    for prop in ("background-color", "background"):
        got = cascade.declared(el, prop)
        if not got:
            continue
        bg = normalize_color(cascade.resolve_var(el, got[0]).split()[0] if got[0].strip() else "")
        if bg and color_distance(bg, rules.color_ink) <= 24:
            return True
    return False


def check_deck(deck_dir: Path, rules: RuleSet) -> DeckResult:
    index = deck_dir / "index.html" if deck_dir.is_dir() else deck_dir
    try:
        html = index.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuleLoadError(f"{index} を読めない ({exc})")
    soup = BeautifulSoup(html, "html.parser")
    result = DeckResult(deck=str(index.parent), faces=0)

    sheets: list[tuple[str, str]] = []
    for i, st in enumerate(soup.find_all("style")):
        sheets.append((f"<style#{i + 1}>", st.get_text()))
    for link in soup.find_all("link", rel="stylesheet"):
        href = (link.get("href") or "").split("#")[0].split("?")[0]
        if not href or re.match(r"^(https?:)?//", href):
            continue
        path = (index.parent / href).resolve()
        try:
            sheets.append((href, path.read_text(encoding="utf-8")))
        except OSError as exc:
            # T1 で潰したのと同じ穴。参照先 CSS が無いのに緑にしない。
            result.findings.append(Finding(
                "error", "VG99", "-",
                f"link された CSS {href} を解決できない ({exc.strerror or exc})。"
                "CSS 層を読めない状態では生成則を判定できない"))
    if not sheets:
        result.findings.append(Finding("error", "VG99", "-", "CSS が 1 枚も見つからない"))
        return result

    css_rules = parse_stylesheets(sheets)
    cascade = Cascade(soup, css_rules)
    if cascade.unsupported:
        result.notes.append(f"選択子を解釈できなかった規則 {len(cascade.unsupported)} 件 (例: {cascade.unsupported[0]})")

    faces = collect_faces(soup, rules)
    result.faces = len(faces)
    if not faces:
        result.findings.append(Finding(
            "error", "VG99", "-",
            f"面を 1 つも同定できない (規約の面定義: class {rules.face_class_names} / 属性 {rules.face_attributes})"))
        return result

    check_tone(soup, cascade, css_rules, rules, result)
    for i, face in enumerate(faces):
        label = face_label(face, i)
        units = text_units(face, cascade)
        check_intensity(face, units, cascade, rules, result, label)
        check_roles(face, units, cascade, rules, result, label)
        check_inversion(face, cascade, rules, result, label)
        check_weight_top(units, cascade, rules, result, label)
    return result


def check_tone(soup, cascade: Cascade, css_rules: list[CssRule], rules: RuleSet, result: DeckResult) -> None:
    """VGCONST_003 / 004 / 005 の「使ってよい値の集合」をデッキ全体で見る。"""
    allowed_radius = {rules.radius_default_px}
    seen_radius: dict[str, str] = {}
    seen_shadow: dict[str, str] = {}
    seen_width: dict[str, str] = {}
    seen_weight: dict[str, str] = {}

    def note(store: dict[str, str], key: str, where: str) -> None:
        store.setdefault(key, where)

    for rule in css_rules:
        for prop, (raw, _imp) in rule.decls.items():
            value = raw.strip()
            where = f"{rule.origin} {rule.selector}"
            if prop == "border-radius":
                for token in value.split():
                    length = parse_length(token)
                    if token.strip() in {"0", "0px"} or (length and length[0] in allowed_radius and length[1] in {"px", ""}):
                        continue
                    if length and length[1] == "px" and length[0] == rules.radius_figure_px:
                        continue  # 図版外形のみ許容。data-role の照合は E3 の担当
                    note(seen_radius, f"{value}", where)
            elif prop == "box-shadow" and rules.shadow_forbidden:
                if value.lower().replace("!important", "").strip() not in {"none", ""}:
                    note(seen_shadow, value, where)
            elif prop in {"border", "border-top", "border-right", "border-bottom", "border-left",
                          "border-width", "border-top-width", "border-right-width",
                          "border-bottom-width", "border-left-width", "outline", "outline-width",
                          "stroke-width"}:
                if "var(" in value:
                    continue  # トークン経由。実値はトークン定義側で見る
                m = LENGTH_RE.search(value)
                if not m or value.strip().lower().startswith("none"):
                    continue
                length = parse_length(m.group(0))
                if not length:
                    continue
                num, unit = length
                if num == 0:
                    continue
                if unit != "px":
                    note(seen_width, f"{value} (px 以外)", where)
                    continue
                if num in rules.stroke_steps_px or num == rules.divider_px:
                    continue
                if rules.hairline_px_min <= num <= rules.hairline_px_max:
                    continue
                note(seen_width, value, where)
            elif prop == "font-weight":
                w = parse_weight(value)
                if w is None:
                    if "var(" not in value:
                        note(seen_weight, value, where)
                    continue
                if w not in rules.weight_steps:
                    note(seen_weight, str(w), where)

    for value, where in seen_radius.items():
        result.findings.append(Finding(
            "error", "VG07", "-",
            f"border-radius: {value} ({where})。許すのは {rules.radius_default_px:g}px と"
            f"図版外形の {rules.radius_figure_px:g}px のみ"))
    for value, where in seen_shadow.items():
        result.findings.append(Finding("error", "VG08", "-", f"box-shadow: {value} ({where})。影は使わない"))
    for value, where in seen_width.items():
        steps = " / ".join(f"{s:g}px" for s in rules.stroke_steps_px)
        result.findings.append(Finding(
            "error", "VG09", "-",
            f"線幅 {value} ({where})。許すのは {steps} と下罫 {rules.divider_px:g}px・"
            f"hairline {rules.hairline_px_min:g}-{rules.hairline_px_max:g}px"))
    for value, where in seen_weight.items():
        steps = " / ".join(str(s) for s in rules.weight_steps)
        result.findings.append(Finding("error", "VG10", "-", f"font-weight: {value} ({where})。許すのは {steps} の 3 段"))


def unit_intensity(el, cascade: Cascade, rules: RuleSet) -> tuple[float, str, str] | str:
    got = cascade.resolved(el, "font-size")
    if got is None:
        return "font-size が解決できない"
    length = parse_length(cascade.resolve_var(el, got[0]))
    if length is None:
        return f"font-size: {got[0]} を数値化できない"
    size, unit = length
    if unit in {"", "%"}:
        return f"font-size: {got[0]} の単位を決められない"
    wgot = cascade.resolved(el, "font-weight")
    weight = parse_weight(cascade.resolve_var(el, wgot[0])) if wgot else 400
    if weight is None:
        return f"font-weight: {wgot[0]} を数値化できない"
    w = rules.weight_intensity.get(weight)
    if w is None:
        nearest = min(rules.weight_intensity, key=lambda k: abs(k - weight))
        w = rules.weight_intensity[nearest]
    inverted = any(is_inverted(node, cascade, rules) for node in [el] + list(el.parents)[:6])
    c = rules.inversion_intensity if inverted else 1.0
    return (size * w * c, unit, f"{size:g}{unit} w{weight}{' 反転' if inverted else ''}")


def check_intensity(face, units, cascade: Cascade, rules: RuleSet, result: DeckResult, label: str) -> None:
    if not units:
        result.findings.append(Finding("error", "VG99", label, "テキストを持つ視覚単位が 0 件で E1 を測れない"))
        return
    scored = []
    for el in units:
        got = unit_intensity(el, cascade, rules)
        if isinstance(got, str):
            result.findings.append(Finding("error", "VG99", label, f"E1 判定不能: {got}"))
            return
        scored.append((got[0], got[1], got[2], el))
    unitset = {u for _, u, _, _ in scored}
    if len(unitset) > 1:
        result.findings.append(Finding(
            "error", "VG99", label,
            f"E1 判定不能: 面内の font-size に単位が混在 ({'・'.join(sorted(unitset))})。静的には比を出せない"))
        return
    scored.sort(key=lambda t: -t[0])
    if len(scored) < 2:
        result.notes.append(f"{label}: 視覚単位が 1 件のため I1/I2 は定義されない (第 1 位は一意)")
        return
    i1, i2 = scored[0][0], scored[1][0]
    if i1 <= 0:
        result.findings.append(Finding("error", "VG99", label, "E1 判定不能: 強度が 0 以下"))
        return
    ties = sum(1 for s in scored if abs(s[0] - i1) < 1e-9)
    if ties > 1:
        result.findings.append(Finding(
            "error", "VG01", label,
            f"第 1 位が {ties} 単位で同点 (I={i1:.3f}・例 {scored[0][2]} と {scored[1][2]})"))
        return
    ratio = i1 / i2
    if ratio < rules.intensity_ratio_min:
        result.findings.append(Finding(
            "error", "VG02", label,
            f"I1/I2 = {ratio:.3f} < {rules.intensity_ratio_min}"
            f" (1 位 {scored[0][2]} I={i1:.3f} / 2 位 {scored[1][2]} I={i2:.3f}・不足 {rules.intensity_ratio_min - ratio:.3f})"))


def check_roles(face, units, cascade: Cascade, rules: RuleSet, result: DeckResult, label: str) -> None:
    roles: dict[str, list[float]] = {}
    unitset = set()
    for el in units:
        role = None
        for node in [el] + list(el.parents)[:4]:
            if getattr(node, "get", None) and node.get("data-role"):
                role = node.get("data-role")
                break
        if role not in rules.role_names:
            continue
        got = cascade.resolved(el, "font-size")
        if got is None:
            continue
        length = parse_length(cascade.resolve_var(el, got[0]))
        if length is None:
            continue
        roles.setdefault(role, []).append(length[0])
        unitset.add(length[1])
    if not roles:
        result.findings.append(Finding(
            "error", "VG03", label,
            f"data-role ({' / '.join(rules.role_names)}) を持つ文字要素が 0 件。E2 の隣接比を測る対象が無い"))
        return
    if len(unitset) > 1:
        result.findings.append(Finding("error", "VG99", label, f"E2 判定不能: 役割間で単位が混在 ({'・'.join(sorted(unitset))})"))
        return
    if len(roles) > rules.role_max_per_face:
        result.findings.append(Finding(
            "error", "VG05", label, f"役割 {len(roles)} 種 ({'・'.join(sorted(roles))}) > 上限 {rules.role_max_per_face} 種"))
    for (big, small), floor in rules.role_ratio_min.items():
        if big not in roles or small not in roles:
            continue
        b = max(roles[big])
        s = max(roles[small])
        if s <= 0:
            continue
        ratio = b / s
        if ratio < floor:
            result.findings.append(Finding(
                "error", "VG04", label,
                f"{big} -> {small} の比 {ratio:.3f} < {floor} ({b:g} / {s:g}・不足 {floor - ratio:.3f})"))


def check_inversion(face, cascade: Cascade, rules: RuleSet, result: DeckResult, label: str) -> None:
    count = 0
    for el in [face] + face.find_all(True):
        if el.name == "svg" or any(p.name == "svg" for p in el.parents):
            continue
        if is_inverted(el, cascade, rules):
            if any(is_inverted(p, cascade, rules) for p in list(el.parents)[:6]):
                continue  # 反転面の内側の塗りは同じ 1 ブロックとして数える
            count += 1
    if count != rules.inversion_count_per_face:
        result.findings.append(Finding(
            "error", "VG06", label,
            f"反転ブロック {count} 個 (規定 ちょうど {rules.inversion_count_per_face} 個・地 {rules.color_ink})"))


def check_weight_top(units, cascade: Cascade, rules: RuleSet, result: DeckResult, label: str) -> None:
    hits = []
    for el in units:
        got = cascade.resolved(el, "font-weight")
        if not got:
            continue
        w = parse_weight(cascade.resolve_var(el, got[0]))
        if w == rules.weight_top:
            hits.append(el.name + ("." + ".".join(el.get("class") or []) if el.get("class") else ""))
    if len(hits) > rules.weight_top_max_per_face:
        result.findings.append(Finding(
            "error", "VG11", label,
            f"font-weight {rules.weight_top} の文字要素が {len(hits)} 箇所 "
            f"(上限 {rules.weight_top_max_per_face}・例 {'・'.join(hits[:3])})"))


# ---------------------------------------------------------------------------
# 未実装 (静的解析では確定できないもの)
# ---------------------------------------------------------------------------

UNIMPLEMENTED = [
    ("E4 面積比 0.08-0.15", "反転ブロックの外接矩形面積 / stage 面積。要 playwright (getBoundingClientRect)"),
    ("E1 視覚単位の切り出し", "本検査器は「直接テキストを持つ要素」で近似する。真の視覚単位 (見える塊) は描画後の矩形が要る。要 playwright"),
    ("VGCONST_010 第 1 位の stage 高 10% 上限", "stage 実高に対する比。要 playwright"),
    ("VGCONST_011 最大空き矩形 40%", "面内の空き矩形分割。要 playwright"),
    ("E3 部材語彙 4 種以内", "四つ組 (塗り/角丸/影/輪郭) の異なり数。描画後の実効値が要る。要 playwright"),
    ("E6 命題数 3-7 / 1 文 48 字", "命題判定は自然言語処理であり静的な字面では確定できない"),
    ("VGCONST_002 濃度段 S15-30%", "図解内部の色。SVG 側の検査器 (validate-svg-diagram.py) の管轄"),
]


# ---------------------------------------------------------------------------
# 自己テスト
# ---------------------------------------------------------------------------

_COMPLIANT = """<!doctype html><html><head><style>
:root { --fs-lead: 6rem; --fs-body: 2rem; }
.slider__item { background: #F7F6F3; }
.lead { font-size: var(--fs-lead); font-weight: 700; }
.body { font-size: var(--fs-body); font-weight: 400; }
.label { font-size: 1.6rem; font-weight: 400; }
.accent { background-color: #141412; color: #F7F6F3; }
.rule { border-bottom: 1px solid #141412; }
</style></head><body>
<div class="slider__item">
  <div class="accent"><p class="lead" data-role="lead">見出し</p></div>
  <p class="body" data-role="body">本文である。</p>
  <p class="label" data-role="label">注記</p>
  <div class="rule"></div>
</div></body></html>"""

_SELF_TEST_CASES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("規約どおりの面", _COMPLIANT, (), ("VG01", "VG02", "VG03", "VG04", "VG05", "VG06", "VG07", "VG08", "VG09", "VG10", "VG11", "VG99")),
    # 同じ強度の単位を 2 つ置く (第 1 位が決まらない面)
    ("第 1 位が同点 (E1)",
     _COMPLIANT.replace('<p class="lead" data-role="lead">見出し</p>',
                        '<p class="lead" data-role="lead">見出し</p>'
                        '<p class="lead" data-role="lead">もう一つの見出し</p>'),
     ("VG01",), ()),
    # 1 位 6rem*1.40*1.50 = 12.6 に対し 2 位 8rem*1.00 = 8.0 -> 比 1.575 < 1.60
    ("I1/I2 が下限未満 (E1)",
     _COMPLIANT.replace("--fs-body: 2rem;", "--fs-body: 8rem;"),
     ("VG02",), ("VG01",)),
    ("役割未宣言 (E2)",
     _COMPLIANT.replace(' data-role="lead"', "").replace(' data-role="body"', "").replace(' data-role="label"', ""),
     ("VG03",), ()),
    ("lead->body 比が下限未満 (E2)",
     _COMPLIANT.replace("--fs-body: 2rem;", "--fs-body: 4.5rem;"),
     ("VG04",), ()),
    ("反転ブロック 0 個 (E4)",
     _COMPLIANT.replace("background-color: #141412;", "background-color: #F7F6F3;"),
     ("VG06",), ()),
    ("角丸 (VGCONST_003)",
     _COMPLIANT.replace(".rule { ", ".rule { border-radius: 12px; "),
     ("VG07",), ()),
    ("影 (VGCONST_003)",
     _COMPLIANT.replace(".rule { ", ".rule { box-shadow: 0 2px 8px rgba(0,0,0,.2); "),
     ("VG08",), ()),
    # 4px は 3 段 (1.25/2/3) のいずれでもなく、下罫 1px でも hairline 0.5-0.75px でもない。
    # 段の値を動かしたらここも動かすこと。旧 3 段 (2/1/0.5) では 3px が段外だったが、
    # 3px は現行では最も太い段そのものなので、この case は黙って通るようになる。
    ("線幅 3 段外 (VGCONST_004)",
     _COMPLIANT.replace("border-bottom: 1px solid", "border-bottom: 4px solid"),
     ("VG09",), ()),
    ("ウェイト 3 段外 (VGCONST_005)",
     _COMPLIANT.replace(".label { font-size: 1.6rem; font-weight: 400; }",
                        ".label { font-size: 1.6rem; font-weight: 600; }"),
     ("VG10",), ()),
    ("700 が 1 面に 2 箇所 (VGCONST_005)",
     _COMPLIANT.replace(".body { font-size: var(--fs-body); font-weight: 400; }",
                        ".body { font-size: var(--fs-body); font-weight: 700; }"),
     ("VG11",), ()),
    ("面が 0 件 (fail-closed)",
     _COMPLIANT.replace('class="slider__item"', 'class="wrapper"'),
     ("VG99",), ()),
    ("CSS が無い (fail-closed)",
     '<!doctype html><html><body><div class="slider__item"><p>本文</p></div></body></html>',
     ("VG99",), ()),
    ("font-size を解決できない (fail-closed)",
     _COMPLIANT.replace("--fs-body: 2rem;", "--fs-body: clamp(1rem, 2vw, 3rem);"),
     ("VG99",), ()),
    ("単位が混在して比を出せない (fail-closed)",
     _COMPLIANT.replace("--fs-body: 2rem;", "--fs-body: 3vh;"),
     ("VG99",), ()),
)


# 規約の読み込み経路そのものの自己テスト。
# (label, 規約テキストの改変, 期待する結果) の対で、写しと正本のズレが
# 「黙って通る」ことがないことを固定する。
_RULE_SOURCE_CASES: tuple[tuple[str, "object", str], ...] = (
    ("json と散文がズレたら落ちる",
     lambda t: t.replace('"intensity_ratio_min": 1.60', '"intensity_ratio_min": 1.20'),
     "error"),
    # 左辺は規約 md の json ブロックの literal と一字一句同じでなければ replace が
    # 空振りし、ズレを作らないまま「error が出ない」で落ちる。段の値を動かしたら
    # ここの左辺も同時に動かすこと。
    ("json の配列が散文とズレても落ちる",
     lambda t: t.replace('"stroke_steps_px": [1.25, 2, 3]', '"stroke_steps_px": [1.25, 2, 4]'),
     "error"),
    ("json が壊れていたら落ちる",
     lambda t: t.replace('"e1": {', '"e1": {,'),
     "error"),
    ("json が無ければ散文で読む",
     lambda t: re.sub(r"```json\s*\n.*?\n```", "", t, flags=re.S),
     "prose"),
    ("散文の錨が外れたら落ちる",
     lambda t: t.replace("W: font-weight", "W: 太さの係数"),
     "error"),
)


def _self_test_rule_source(rules_path: Path, tmp: Path) -> int:
    """規約の読み込み経路 (json 優先・散文と突き合わせ) を踏む。"""
    failed = 0
    try:
        original = rules_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  NG   - 規約ファイルを読めない ({exc})", file=sys.stderr)
        return len(_RULE_SOURCE_CASES)
    for i, (label, mutate, expect) in enumerate(_RULE_SOURCE_CASES):
        target = tmp / f"rules-{i}.md"
        target.write_text(mutate(original), encoding="utf-8")
        try:
            got = load_rules(target)
            outcome = got.origin
        except RuleLoadError as exc:
            outcome = "error"
            detail = str(exc)
        if outcome != expect:
            failed += 1
            print(f"  NG   - {label} (期待 {expect} / 実際 {outcome})", file=sys.stderr)
        else:
            note = detail.split("。")[0][:60] if outcome == "error" else "散文から読めた"
            print(f"  ok   - {label} ({note})")
    return failed


def _self_test(rules: RuleSet) -> int:
    import tempfile

    failed = 0
    print(f"  ok   - 規約の読み込み ({rules.source} / 由来 {rules.origin})")
    print(f"         E1 W={rules.weight_intensity} C={rules.inversion_intensity} I1/I2>={rules.intensity_ratio_min}")
    print(f"         E2 {rules.role_ratio_min} 役割上限={rules.role_max_per_face}")
    print(f"         E4 個数={rules.inversion_count_per_face} 面積={rules.inversion_area_min}-{rules.inversion_area_max}")
    print(f"         VGCONST_003 角丸={rules.radius_default_px:g}/{rules.radius_figure_px:g}px "
          f"hairline={rules.hairline_px_min:g}-{rules.hairline_px_max:g}px 下罫={rules.divider_px:g}px")
    print(f"         VGCONST_004 {rules.stroke_steps_px} / VGCONST_005 {rules.weight_steps} "
          f"({rules.weight_top} は 1 面 {rules.weight_top_max_per_face} 箇所)")
    with tempfile.TemporaryDirectory() as tmp:
        for label, html, expect, forbid in _SELF_TEST_CASES:
            deck = Path(tmp) / re.sub(r"\W+", "_", label)
            deck.mkdir(parents=True, exist_ok=True)
            (deck / "index.html").write_text(html, encoding="utf-8")
            res = check_deck(deck, rules)
            codes = {f.code for f in res.findings}
            missing = [c for c in expect if c not in codes]
            extra = [c for c in forbid if c in codes]
            if missing or extra:
                failed += 1
                detail = []
                if missing:
                    detail.append(f"出るべきだが出ない: {', '.join(missing)}")
                if extra:
                    detail.append(f"出てはいけないのに出た: {', '.join(extra)}"
                                  f" [{'; '.join(f.message for f in res.findings if f.code in extra)}]")
                print(f"  NG   - {label} ({' / '.join(detail)})", file=sys.stderr)
            else:
                print(f"  ok   - {label}")
        failed += _self_test_rule_source(Path(rules.source), Path(tmp))
    total = len(_SELF_TEST_CASES) + 1 + len(_RULE_SOURCE_CASES)
    print(f"validate-visual-generation self-test: {total - failed}/{total} {'PASS' if not failed else 'FAIL'}")
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

USAGE = ("usage: validate-visual-generation.py <deck-dir|index.html> [...] "
         "[--json] [--strict] [--rules <path>] | --self-test | --unimplemented")


def main(argv: list[str]) -> int:
    args = argv[1:]
    if "--help" in args or "-h" in args:
        print(USAGE)
        print("\n検査コード:")
        for code, desc in CODES.items():
            print(f"  {code}  {desc}")
        return 0
    rules_path = None
    if "--rules" in args:
        i = args.index("--rules")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        rules_path = args[i + 1]
        del args[i:i + 2]
    as_json = "--json" in args
    strict = "--strict" in args
    paths = [a for a in args if not a.startswith("-")]

    try:
        rules = load_rules(find_rules_file(rules_path))
    except RuleLoadError as exc:
        print(f"規約を読めない (fail-closed): {exc}", file=sys.stderr)
        return 3

    if "--unimplemented" in args:
        for name, why in UNIMPLEMENTED:
            print(f"未実装 - {name}: {why}")
        return 0
    if "--self-test" in args:
        return _self_test(rules)
    if not paths:
        print(USAGE, file=sys.stderr)
        return 2

    results: list[DeckResult] = []
    for p in paths:
        try:
            results.append(check_deck(Path(p), rules))
        except RuleLoadError as exc:
            print(f"入力を読めない (fail-closed): {exc}", file=sys.stderr)
            return 3

    if as_json:
        print(json.dumps({
            "rules": rules.source,
            "decks": [
                {
                    "deck": r.deck,
                    "faces": r.faces,
                    "errors": r.errors,
                    "warns": r.warns,
                    "notes": r.notes,
                    "findings": [{"severity": f.severity, "code": f.code, "face": f.face, "message": f.message}
                                 for f in r.findings],
                } for r in results
            ],
        }, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"\n{r.deck} (面 {r.faces})")
            if not r.findings:
                print("  検出なし")
            for f in r.findings:
                print(f"  {f.severity:5s} {f.code} {f.face}: {f.message}")
            for n in r.notes:
                print(f"  note  {n}")
        total_err = sum(r.errors for r in results)
        total_warn = sum(r.warns for r in results)
        failed_decks = sum(1 for r in results if r.errors or (strict and r.warns))
        print(f"\n合計: deck {len(results)} 本中 {failed_decks} 本が不合格 / error {total_err} 件 warn {total_warn} 件")

    if any(r.errors for r in results) or (strict and any(r.warns for r in results)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
