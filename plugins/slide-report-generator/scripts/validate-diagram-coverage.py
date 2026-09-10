#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# purpose: 「面が視覚構造を持つか」を面ごとに数える被覆検査 (DC1-DC6)。既存の validate-svg-diagram.py は
#          見つけた図の幾何・色 (上限) を、validate-diagram-information.py は見つけた図の情報 (下限) を見る。
#          どちらも **図が 0 個の面には検査対象が存在しない** ので緑を返す (分母 0 の緑)。文字リストだけの
#          deck は既存検査を全部通る。本検査器はその死角を踏み、分母 (全面数・除外後・判定できた数) を
#          必ず出力する。CLI と import (pytest) 両対応・Python 標準ライブラリのみ。
# ///
"""図解被覆 (diagram coverage) の検査器。

**この検査器が答える問い**: 「その面は視覚構造を持っているか」。
**既存 2 本が答える問い**: 「その面の図は正しいか」。図が 0 個なら後者は答える対象を持たない。

規約の正本は `skills/run-slide-report-generate/references/visual-generation-rules.md` §4
(カード化の分岐条件) の第 2 行 —「項目間に関係がある・3 件以上 → 図解」。条文はあったが、
**それを面ごとに数える主体が居なかった**。ここがその主体である。

## 判定の向き (重要・2026-08-14 の反例で組み直した)

素朴に「inline SVG / canvas / img があるか」で数えると **誤検出する**。実測した反例:
実運用 deck の面 4 (`slide-timeline`) は SVG も canvas も持たないが、`.timeline::before` の
縦軸と `.timeline-item::before` の節点で **CSS だけで経歴のタイムライン図が描かれている**。
SVG の数では、この面と `ul.list` の文字リストの面を区別できない。

そこで **主判定を「文字リストであること」の側に置く**。

  - 文字リストは機械で確実に取れる (`li` の並び・`.grid-cell` 等のカード羅列が 3 件以上で、
    要素間に接続線も位置関係も無い)。ここを赤にする。
  - 「視覚構造がある」は免責側に置く。SVG/canvas/図として意図された img/D3 に加えて、
    **CSS で描かれた図** (擬似要素の軸 + 反復する項目) を拾う。
  - どちらとも言えない面は **判定保留** として分母から外し、必ず名指しで出力する
    (黙って緑にも赤にもしない)。

誤検出の向きはこれで「見落とし」側になる。人が見て `data-diagram-exempt` で免責する形になり、
機械が勝手に赤を消す形にはならない。

## 拾えない形 (既知の死角・出力にも明記する)

  - CSS 判定は `<style>` に書かれた規則しか見ない。外部 CSS ファイル参照・JS が実行時に
    差し込む装飾・`background-image` の SVG data URI は見えない。
  - 擬似要素の「軸」は `content` + `position:absolute` + 対向する 2 辺 (top と bottom /
    left と right) の指定で当てている。斜めの接続線・`transform` だけで引いた線は当たらない。
  - 節点だけ (連番バッジ等) は軸が無いので図と数えない。番号付きリストと区別できないため。

判定 ID:
  DC1 face-text-list    非除外の面が文字リストのみ (面ごと・error)
  DC2 coverage-ratio    視覚構造を持つ面 / 判定できた面 が --min-ratio 未満 (deck 全体・error)
  DC3 no-target         面を 1 つも同定できない / 判定できた面が 0 件 (exit 2・PASS ではない)
  DC4 exempt-declared   除外した面とその理由 (info・必ず出力する。黙って分母から落とさない)
  DC5 unjudged          文字リストとも視覚構造とも言えない面 (info・分母から外すので必ず出力)
  DC6 blind-spot        本検査器が拾えない形の告知 (info・毎回出力する)

exit code:
  0  判定できた面 >= 1 かつ ratio >= --min-ratio
  1  ratio < --min-ratio (DC2)。DC1 の面一覧は stderr へ名指しで出る
  2  usage / 検査対象なし (DC3)。**これを緑と読まないこと**
  3  入力の読み取り不能 (ファイル不在・decode 不能)

除外 (exempt) の決め方:
  - **面の型で判定する。** 面番号の除外リストは持たない (deck が変わると意味を失い、
    「都合の悪い面を番号で外す」経路になるため)。
  - 型に加えて、QR/連絡先が主役の面 (QR 画像を持ち視覚構造を持たない面) も除外する。
  - 成果物側が `data-diagram-exempt="<理由>"` を面へ書いた場合も除外する。
    理由が空文字なら除外しない (理由の書かれていない除外は除外ではない)。
  - 除外した面は DC4 として **必ず一覧出力する**。分母から黙って落とさない。
"""

from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# 面 (face) の同定
#
# 面の定義の正本は visual-generation-rules.md の用語集
# 「engine 経路は `slider__item`、ひな形経路は `data-slide-skeleton` を持つ要素」。
# validate-visual-generation.py の collect_faces と同じ網を張る (綴り違いの
# `slider__slide` / `slider-item` も拾う)。片方だけが面を見つける状態を作らない。
# ---------------------------------------------------------------------------
FACE_CLASS_RE = re.compile(r"^slider[-_]{1,2}(item|slide|page)$")
FACE_ATTRS = ("data-slide-skeleton",)
# report 経路の面 = 節。render-report.js が `<section class="report-section">` を出す。
REPORT_FACE_CLASS = "report-section"

# ---------------------------------------------------------------------------
# 図が要らない面の型 (意味判定なので表で持つ。番号ではなく型で持つ)
#
# 「1 つの言明だけを置く面」「デッキの構造を示す面」「連絡先・QR の面」。
# これらは項目を 3 件以上並べないので §4 の分岐条件に入らない。
# 綴りは engine の `slideType` / ひな形の `layout-<役割>` の両方を受ける。
# ---------------------------------------------------------------------------
EXEMPT_TYPES = {
    # 表紙・章扉
    "hero", "slide-hero", "title", "slide-title", "cover", "layout-cover",
    "section-divider", "slide-section-divider", "layout-section-divider", "divider",
    # 1 言明だけの面
    "message", "slide-message", "layout-message",
    "quote", "slide-quote", "layout-quote",
    "highlight", "slide-highlight",
    # 目次・締め・連絡先
    "closing", "slide-closing", "layout-closing",
    "contact", "slide-contact", "layout-contact",
    "qa", "slide-qa", "layout-qa",
    "profile", "slide-profile", "layout-profile",
    "team", "slide-team", "layout-team",
}

# 図表要素ではないが「散文でない構造化表示」として図に準じる型。
# 表とコードは関係を持つ情報を非散文で見せる器なので、図の代替として算入する。
# (ここを算入しないと、表を出すべき面に無理やり図を足す圧力が生まれる)
STRUCTURED_TYPES = {
    "table", "slide-table", "layout-table", "diagram-table-advanced",
    "code", "slide-code", "code-compare", "slide-code-compare",
}

# 図として意図された <img> の目印。QR・顔写真・ロゴを図と数えないための条件。
FIGURE_IMG_HINT_RE = re.compile(
    r"(diagram|figure|chart|graph|visual|infographic|図解|図版|グラフ|チャート)", re.I
)
# QR の目印。src が data URI のときは base64 本文に "qr" が偶然含まれるので **見ない**
# (class / alt / データでない src のファイル名だけを見る)。
QR_HINT_RE = re.compile(r"(\bqr\b|qr-?code|qr-?img|QRコード)", re.I)

# <svg> を図と数える下限。アイコン 1 個 (path 1 本) を図と数えないための閾値。
SVG_SHAPE_TAGS = ("rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "g")
SVG_MIN_SHAPES = 3

# 文字リストと判定する下限。§4 の「3 件以上並ぶなら関係を決めて図にする」に合わせる。
LIST_MIN_ITEMS = 3
# CSS 図と判定するときに要求する項目の反復数 (軸に沿って並ぶ節点の数)。
CSS_REPEAT_MIN = 3

DEFAULT_MIN_RATIO = 0.50
# 既定 0.50 の根拠:
#   規約 §4 の正論値は 1.00 である (項目が 3 件以上並び関係があるなら図解、
#   関係が無いなら並べる必要を疑う、なので「判定できた面」は本来すべて視覚構造を持つ)。
#   だが 1.00 をいきなり当てると既存 deck が軒並み赤になり、検査ごと無視される
#   (赤が既定になった検査は読まれなくなる)。順序は「値を直してから検査を締める」
#   なので、まず床として 0.50 を置き、deck 側が追いついた時点で --min-ratio で
#   段階的に 1.00 へ寄せる。この既定値は目標ではなく床である。


# ---------------------------------------------------------------------------
# CSS の取り出しと「CSS で描かれた図」の signal
# ---------------------------------------------------------------------------
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
_RULE_RE = re.compile(r"([^{}]{1,400}?)\{([^{}]{0,800}?)\}", re.S)
_CLASS_IN_SEL_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")


def extract_css_rules(text: str) -> list[tuple[str, str]]:
    """HTML の <style> (または CSS 本文) から (selector, declarations) を返す。

    コメントを先に落とす。落とさないと、コメント中の日本語や `//` が selector として
    数えられる (この repo で実際に踏んだ形)。
    """
    if "<style" in text.lower():
        css = "\n".join(_STYLE_RE.findall(text))
    else:
        css = text
    css = _CSS_COMMENT_RE.sub(" ", css)
    out: list[tuple[str, str]] = []
    for m in _RULE_RE.finditer(css):
        sel = " ".join(m.group(1).split())
        body = " ".join(m.group(2).split())
        if sel and body:
            out.append((sel, body))
    return out


def _has_opposing_pair(body: str) -> bool:
    """対向する 2 辺が指定されている = その擬似要素は「渡っている」= 軸/接続線。"""
    def has(prop: str) -> bool:
        return re.search(r"(^|;|\s)" + prop + r"\s*:", body) is not None
    return (has("top") and has("bottom")) or (has("left") and has("right"))


def css_visual_signals(face_classes: dict[str, int],
                       rules: list[tuple[str, str]]) -> list[str]:
    """面のクラス集合に対して「CSS で描かれた図」の signal を返す。

    条件 (すべて満たしたときだけ図と数える):
      1. 擬似要素 (::before / ::after) の規則で `content` と `position:absolute` を持つ
      2. その擬似要素が対向する 2 辺を指定している (= 軸・接続線として渡っている)
      3. 規則の主語クラスが面の中に存在する
      4. 面の中に 3 件以上反復する子要素クラスがある (軸に沿って並ぶ節点)

    節点だけ (連番バッジ等) は 2 を満たさないので図と数えない。番号付き箇条書きと
    区別できないため。返り値は当たった selector の一覧 (空なら signal 無し)。
    """
    if not face_classes:
        return []
    repeated = any(n >= CSS_REPEAT_MIN for n in face_classes.values())
    if not repeated:
        return []
    hits: list[str] = []
    for sel, body in rules:
        if "::before" not in sel and "::after" not in sel:
            continue
        if "content" not in body:
            continue
        if not re.search(r"position\s*:\s*absolute", body):
            continue
        if not _has_opposing_pair(body):
            continue
        classes = set(_CLASS_IN_SEL_RE.findall(sel))
        if classes and classes <= set(face_classes):
            hits.append(sel)
    return hits


# ---------------------------------------------------------------------------
# HTML パース
# ---------------------------------------------------------------------------
class _FaceParser(HTMLParser):
    """面ごとに図表要素・リスト項目・クラス反復・見出しを数える。

    入れ子の面は外側だけを面とする (validate-visual-generation.py と同じ扱い)。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.faces: list[dict] = []
        self._stack: list[str] = []          # 現在開いているタグ名
        self._face: dict | None = None
        self._face_depth = 0                 # 面要素を開いた時点の stack 深さ
        self._svg_depth = 0                  # svg の中にいるか
        self._cur_svg: dict | None = None
        self._heading_depth: int | None = None
        self._figure_depth = 0

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _classes(attrs: dict) -> list[str]:
        return (attrs.get("class") or "").split()

    def _face_type(self, tag: str, attrs: dict) -> str:
        for key in ("data-slide-type", "data-type", "data-layout", "data-slide-skeleton"):
            val = (attrs.get(key) or "").strip()
            if val and val not in ("true", "1", ""):
                return val
        for cls in self._classes(attrs):
            if FACE_CLASS_RE.match(cls) or cls == REPORT_FACE_CLASS:
                continue
            if re.match(r"^(slide|diagram|chart|d3|layout)-", cls):
                # render-slide.cjs のひな形は `slide-slide-list` のように接頭辞が
                # 二重に付く。二重ぶんだけ落として schema の綴りへ寄せる。
                return re.sub(r"^slide-(slide-)", r"\1", cls)
        role = (attrs.get("data-role") or attrs.get("data-section-role") or "").strip()
        if role:
            return f"role:{role}"
        return "unknown"

    def _is_face(self, tag: str, attrs: dict) -> bool:
        if any(a in attrs for a in FACE_ATTRS):
            return True
        for cls in self._classes(attrs):
            if FACE_CLASS_RE.match(cls) or cls == REPORT_FACE_CLASS:
                return True
        return False

    # -- HTMLParser -------------------------------------------------------
    def handle_starttag(self, tag, attrs_list):  # noqa: D102
        attrs = {k.lower(): (v or "") for k, v in attrs_list}
        self._stack.append(tag)
        depth = len(self._stack)

        if self._face is None and self._is_face(tag, attrs):
            exempt_attr = attrs.get("data-diagram-exempt")
            self._face = {
                "index": len(self.faces) + 1,
                "tag": tag,
                "type": self._face_type(tag, attrs),
                "heading": "",
                "svgs": 0, "canvas": 0, "d3": 0,
                "figure_img": 0, "plain_img": 0, "qr_img": 0,
                "li": 0, "cells": 0,
                "classes": {},
                "declared_exempt": (exempt_attr or "").strip() if exempt_attr is not None else None,
            }
            self._face_depth = depth
            return

        if self._face is None:
            return

        for cls in self._classes(attrs):
            self._face["classes"][cls] = self._face["classes"].get(cls, 0) + 1

        if tag == "svg":
            self._svg_depth += 1
            if self._svg_depth == 1:
                self._cur_svg = {"shapes": 0}
            return
        if self._svg_depth > 0:
            if self._cur_svg is not None and tag in SVG_SHAPE_TAGS:
                self._cur_svg["shapes"] += 1
            return

        if tag == "figure":
            self._figure_depth += 1
        elif tag == "canvas":
            self._face["canvas"] += 1
        elif tag == "img":
            cls = " ".join(self._classes(attrs))
            alt = attrs.get("alt") or ""
            src = attrs.get("src") or ""
            src_name = "" if src.startswith("data:") else os.path.basename(src.split("?")[0])
            role = attrs.get("data-role") or ""
            is_qr = bool(QR_HINT_RE.search(cls) or QR_HINT_RE.search(alt)
                         or QR_HINT_RE.search(src_name))
            is_fig = (
                self._figure_depth > 0
                or bool(FIGURE_IMG_HINT_RE.search(cls))
                or bool(FIGURE_IMG_HINT_RE.search(alt))
                or role.strip().lower() in ("diagram", "figure", "chart")
            )
            if is_qr:
                self._face["qr_img"] += 1
            if is_fig and not is_qr:
                self._face["figure_img"] += 1
            elif not is_qr:
                self._face["plain_img"] += 1
        elif tag == "li":
            self._face["li"] += 1
        elif tag in ("h1", "h2", "h3") and not self._face["heading"]:
            self._heading_depth = depth

        if "data-d3-mount" in attrs or "d3-mount" in self._classes(attrs):
            self._face["d3"] += 1
        if any(c in ("grid-cell", "card", "grid-card") for c in self._classes(attrs)):
            self._face["cells"] += 1

    def handle_startendtag(self, tag, attrs_list):  # noqa: D102
        self.handle_starttag(tag, attrs_list)
        self.handle_endtag(tag)

    def handle_data(self, data):  # noqa: D102
        if self._face is not None and self._heading_depth is not None and self._svg_depth == 0:
            self._face["heading"] += data

    def handle_endtag(self, tag):  # noqa: D102
        depth = len(self._stack)
        if tag in self._stack:
            while self._stack and self._stack[-1] != tag:
                self._stack.pop()
            if self._stack:
                self._stack.pop()
        else:
            return

        if self._face is None:
            return
        if self._heading_depth is not None and depth <= self._heading_depth:
            self._face["heading"] = " ".join(self._face["heading"].split())[:60]
            self._heading_depth = None
        if tag == "svg" and self._svg_depth > 0:
            self._svg_depth -= 1
            if self._svg_depth == 0 and self._cur_svg is not None:
                if self._cur_svg["shapes"] >= SVG_MIN_SHAPES:
                    self._face["svgs"] += 1
                self._cur_svg = None
            return
        if self._svg_depth > 0:
            return
        if tag == "figure" and self._figure_depth > 0:
            self._figure_depth -= 1
        if depth <= self._face_depth:
            if self._heading_depth is not None:
                self._face["heading"] = " ".join(self._face["heading"].split())[:60]
                self._heading_depth = None
            self.faces.append(self._face)
            self._face = None
            self._face_depth = 0


def parse_faces(html_text: str) -> list[dict]:
    """HTML から面の一覧を返す。面が 0 件なら空リスト。"""
    p = _FaceParser()
    p.feed(html_text)
    if p._face is not None:      # 閉じ忘れた最後の面を回収する
        p.faces.append(p._face)
    return p.faces


# ---------------------------------------------------------------------------
# 面の分類
# ---------------------------------------------------------------------------
def classify_face(face: dict, exempt_types: set[str],
                  css_rules: list[tuple[str, str]] | None = None) -> dict:
    """1 つの面を exempt / figure / css-visual / structured / text-list / unjudged へ分類する。

    順序が意味を持つ。**視覚構造の判定を QR 免責より先に行う** — 面 4 のように
    「CSS 製の図の脇に QR がある」面を QR 面として分母から落とさないため。
    """
    out = dict(face)
    ftype = (face.get("type") or "unknown").strip()
    base = ftype[5:] if ftype.startswith("role:") else ftype

    declared = face.get("declared_exempt")
    if declared:
        out["verdict"] = "exempt"
        out["reason"] = f"成果物が data-diagram-exempt で宣言: {declared}"
        return out
    if declared == "":
        out["verdict_note"] = "data-diagram-exempt が空文字のため除外しない"

    if base in exempt_types:
        out["verdict"] = "exempt"
        out["reason"] = f"型 {base} は 1 言明・構造提示・連絡先の面で、3 件以上の並列を持たない"
        return out

    figures = face["svgs"] + face["canvas"] + face["d3"] + face["figure_img"]
    if figures > 0:
        out["verdict"] = "figure"
        out["reason"] = (
            f"svg={face['svgs']} canvas={face['canvas']} d3={face['d3']} figure-img={face['figure_img']}"
        )
        return out

    hits = css_visual_signals(face.get("classes") or {}, css_rules or [])
    if hits:
        out["verdict"] = "css-visual"
        out["css_signals"] = hits
        out["reason"] = "CSS で描かれた図 (擬似要素の軸 + 反復する項目): " + " / ".join(hits[:3])
        return out

    if base in STRUCTURED_TYPES:
        out["verdict"] = "structured"
        out["reason"] = f"型 {base} は表・コードの構造化表示で、散文ではない"
        return out

    if face["qr_img"] > 0:
        out["verdict"] = "exempt"
        out["reason"] = (
            f"QR/連絡先が主役の面 (QR 画像={face['qr_img']})。行動導線であって説明図ではない"
        )
        return out

    items = max(face["li"], face["cells"])
    if items >= LIST_MIN_ITEMS:
        out["verdict"] = "text-list"
        out["reason"] = (
            f"文字リストのみ (li={face['li']} カード/セル={face['cells']} "
            f"図でない画像={face['plain_img']})。接続線も位置関係も無い"
        )
        return out

    out["verdict"] = "unjudged"
    out["reason"] = (
        f"文字リストとも視覚構造とも判定できない (li={face['li']} カード/セル={face['cells']} "
        f"画像={face['plain_img']})。分母から外すので目視で判断すること"
    )
    return out


def evaluate(faces: list[dict], min_ratio: float, exempt_types: set[str],
             css_rules: list[tuple[str, str]] | None = None) -> dict:
    classified = [classify_face(f, exempt_types, css_rules) for f in faces]
    exempt = [f for f in classified if f["verdict"] == "exempt"]
    unjudged = [f for f in classified if f["verdict"] == "unjudged"]
    with_vis = [f for f in classified if f["verdict"] in ("figure", "css-visual", "structured")]
    text_list = [f for f in classified if f["verdict"] == "text-list"]
    judged = len(with_vis) + len(text_list)
    ratio = (len(with_vis) / judged) if judged else None
    if not faces or not judged:
        verdict = "no-target"
    elif ratio is not None and ratio + 1e-9 >= min_ratio:
        verdict = "pass"
    else:
        verdict = "fail"
    return {
        "faces": len(faces),
        "exempt": len(exempt),
        "needs_figure": len(faces) - len(exempt),
        "judged": judged,
        "with_visual": len(with_vis),
        "css_visual": len([f for f in with_vis if f["verdict"] == "css-visual"]),
        "text_list": len(text_list),
        "unjudged": len(unjudged),
        "ratio": ratio,
        "min_ratio": min_ratio,
        "verdict": verdict,
        "classified": classified,
        "exempt_faces": exempt,
        "text_list_faces": text_list,
        "unjudged_faces": unjudged,
    }


# ---------------------------------------------------------------------------
# 構成 (structure.json) 段階の被覆
#
# 生成前に「文字リストしか無い」と判るなら、生成してから測るより手戻りが短い。
# ここで使う「その slideType は図を出すか」は **写経しない**。
# vendor/scripts/templates/<type>.html.tpl を実行時に読み、svg / d3 マウントの
# 有無で判定する。写経すると、テンプレートを直した日に判定だけが古い値で残る。
#
# ただし **この段階では CSS 製の図が見えない** (テンプレートに svg が無くても
# skeleton CSS が軸と節点を描く型がある。実例: slide-timeline)。よって構成段階の
# 判定は「候補」であり、生成後の判定が正本である。出力にもそう書く。
# ---------------------------------------------------------------------------
def plugin_root() -> str:
    env = os.environ.get("SRG_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env and os.path.isdir(os.path.join(env, "vendor", "scripts", "templates")):
        return env
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def figure_emitting_types(template_dir: str | None = None) -> tuple[set[str], set[str]]:
    """テンプレート実体から (図を出す型, 図を出さない型) を実測して返す。

    テンプレートが読めない場合は両方空集合を返す (呼び手が fail-closed 判断する)。
    """
    tdir = template_dir or os.path.join(plugin_root(), "vendor", "scripts", "templates")
    emitting: set[str] = set()
    silent: set[str] = set()
    if not os.path.isdir(tdir):
        return emitting, silent
    for name in sorted(os.listdir(tdir)):
        if not name.endswith(".html.tpl"):
            continue
        stem = name[: -len(".html.tpl")]
        try:
            body = open(os.path.join(tdir, name), encoding="utf-8").read()
        except OSError:
            continue
        if "<svg" in body or "{{{svg}}}" in body or "data-d3-mount" in body:
            emitting.add(stem)
        else:
            silent.add(stem)
    return emitting, silent


_CSS_SOURCE_RELPATHS = (
    os.path.join("vendor", "scripts", "style-builder.cjs"),
    os.path.join("assets", "slide-templates", "slide-skeleton.css"),
)
_CLASS_IN_HTML_RE = re.compile(r'class="([^"]*)"')


def engine_css_rules(root: str | None = None) -> list[tuple[str, str]]:
    """engine が焼き込む CSS の規則を読む。

    面の CSS は成果物の <style> にしか無いように見えるが、その出所は
    vendor/scripts/style-builder.cjs である。構成段階で「この型は CSS で図になるか」
    を判定するには出所側を読む必要がある。読めなければ空を返す (呼び手が候補判定を諦める)。
    """
    base = root or plugin_root()
    rules: list[tuple[str, str]] = []
    for rel in _CSS_SOURCE_RELPATHS:
        path = os.path.join(base, rel)
        if not os.path.isfile(path):
            continue
        try:
            rules.extend(extract_css_rules(open(path, encoding="utf-8").read()))
        except OSError:
            continue
    return rules


def css_figure_types(template_dir: str | None = None,
                     css_rules: list[tuple[str, str]] | None = None) -> set[str]:
    """テンプレートのクラスと engine CSS を突き合わせ「CSS で図になる型」を実測する。

    反復数は構成段階では判らないので、テンプレートに出るクラスは反復するものとみなす
    (候補判定なので、生成後の判定が正本)。
    """
    tdir = template_dir or os.path.join(plugin_root(), "vendor", "scripts", "templates")
    rules = css_rules if css_rules is not None else engine_css_rules()
    out: set[str] = set()
    if not os.path.isdir(tdir) or not rules:
        return out
    for name in sorted(os.listdir(tdir)):
        if not name.endswith(".html.tpl"):
            continue
        try:
            body = open(os.path.join(tdir, name), encoding="utf-8").read()
        except OSError:
            continue
        classes: dict[str, int] = {}
        for chunk in _CLASS_IN_HTML_RE.findall(body):
            for cls in chunk.split():
                if "{{" in cls or "}}" in cls:
                    continue
                classes[cls] = CSS_REPEAT_MIN
        if classes and css_visual_signals(classes, rules):
            out.add(name[: -len(".html.tpl")])
    return out


def evaluate_structure(structure: dict, min_ratio: float, exempt_types: set[str],
                       template_dir: str | None = None) -> dict:
    """structure.json の slides[] を型だけで分類する (生成前ゲート・候補判定)。

    構成段階で判るのは **型** だけである。QR が主役かどうか・実際に何項目並ぶかは
    見えないので、ここでの赤は「候補」であり、生成後の判定が正本である。
    """
    emitting, silent = figure_emitting_types(template_dir)
    css_types = css_figure_types(template_dir)
    slides = structure.get("slides") or structure.get("sections") or []
    faces = []
    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            continue
        stype = (s.get("slideType") or s.get("type") or "unknown").strip()
        known = stype in emitting or stype in silent
        items = s.get("items") or s.get("cards") or s.get("events") or []
        face = {
            "index": i + 1,
            "tag": "slide",
            "type": stype,
            "heading": str(s.get("title") or "")[:60],
            "svgs": 1 if stype in emitting else 0,
            "canvas": 0, "d3": 0, "figure_img": 0, "plain_img": 0, "qr_img": 0,
            # 型が判っていて図を出さないなら、項目数が構成に書かれていなくても
            # 「文字リストになる型」として数える (項目数 0 で判定保留にすると、
            # 構成段階の判定が丸ごと分母から消えて 分母 0 の緑になる)。
            "li": len(items) if isinstance(items, list) and items else (
                LIST_MIN_ITEMS if known and stype not in emitting and stype not in css_types else 0),
            "cells": 0,
            "classes": {},
            "declared_exempt": None,
            "template_known": known,
        }
        if stype in css_types and stype not in emitting:
            # CSS で図になる型。engine CSS を実測して判っているので図として数える。
            face["classes"] = {"__css_figure__": CSS_REPEAT_MIN}
        faces.append(face)

    css_marker_rule = [(".__css_figure__::before",
                        'content: ""; position: absolute; top: 0; bottom: 0;')]
    res = evaluate(faces, min_ratio, exempt_types, css_rules=css_marker_rule)
    res["stage"] = "structure"
    for f in res["text_list_faces"]:
        # 項目数は構成に書かれていないことがあり、その場合 li は判定用の代入値である。
        # 実数と読めてしまうので、構成段階の理由文では型の話に書き換える。
        f["reason"] = (
            f"型 {f['type']} のテンプレートは図を出さず、engine CSS にも軸の規則が無い "
            "(文字リストになる型)"
        )
    res["template_types_measured"] = len(emitting) + len(silent)
    res["css_figure_types"] = sorted(css_types)
    res["unknown_types"] = sorted({f["type"] for f in faces if not f.get("template_known")})
    return res


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------
BLIND_SPOT = (
    "INFO [DC6] 拾えない形がある: 外部 CSS ファイル・JS が実行時に差し込む装飾・"
    "background-image の SVG data URI・transform だけで引いた斜線は見えない。"
    "節点だけ (連番バッジ等) は軸が無いので図と数えない。判定保留 (DC5) は目視で決めること"
)


def format_report(path: str, res: dict) -> tuple[str, list[str]]:
    ratio = res["ratio"]
    ratio_s = "n/a" if ratio is None else f"{ratio:.2f}"
    label = {"pass": "PASS", "fail": "FAIL", "no-target": "NO-TARGET"}[res["verdict"]]
    stage = " (構成段階・候補判定)" if res.get("stage") == "structure" else ""
    summary = (
        f"diagram coverage{stage} [{path}]: faces={res['faces']} exempt={res['exempt']} "
        f"needs-figure={res['needs_figure']} judged={res['judged']} "
        f"with-visual={res['with_visual']} (css={res['css_visual']}) "
        f"text-list={res['text_list']} unjudged={res['unjudged']} "
        f"ratio={ratio_s} min={res['min_ratio']:.2f} -> {label}"
    )
    lines: list[str] = [BLIND_SPOT]
    if res.get("stage") == "structure":
        lines.append(
            "INFO [DC6] 構成段階では型しか判らない: QR が主役の面・実際の項目数・面ごとの図の"
            "差し込みは見えないので、ここの赤は候補である (過剰に赤が出うる)。正本は生成後の判定。"
            f"(テンプレート実測={res.get('template_types_measured')} 型 / "
            f"CSS で図になる型={','.join(res.get('css_figure_types') or []) or 'なし'})"
        )
        if res.get("unknown_types"):
            lines.append(
                "INFO [DC5] テンプレートを同定できない型 (判定保留): "
                + ", ".join(res["unknown_types"])
            )
    for f in res["exempt_faces"]:
        lines.append(
            f"INFO [DC4] 面{f['index']}({f['type']}) 除外: {f['reason']} / 見出し={f['heading'] or '(なし)'}"
        )
    for f in res["unjudged_faces"]:
        lines.append(
            f"INFO [DC5] 面{f['index']}({f['type']}) 判定保留 (分母外): {f['reason']} / "
            f"見出し={f['heading'] or '(なし)'}"
        )
    for f in res["text_list_faces"]:
        lines.append(
            f"ERROR [DC1] 面{f['index']}({f['type']}) 文字リストのみ: {f['reason']} / "
            f"見出し={f['heading'] or '(なし)'}"
        )
    lines.append(
        f"INFO 分母: 全面={res['faces']} / 図が要る面(除外後)={res['needs_figure']} / "
        f"判定できた面={res['judged']} (判定保留={res['unjudged']} は分母外)"
    )
    if res["verdict"] == "no-target":
        lines.append(
            "ERROR [DC3] 判定できた面が 0 件。**これは PASS ではない** — "
            "面を同定できなかった (面の class/属性が規約と違う) か、全面が除外・判定保留か。"
            f"(同定した面={res['faces']} / うち除外={res['exempt']} / 判定保留={res['unjudged']})"
        )
    elif res["verdict"] == "fail":
        lines.append(
            f"ERROR [DC2] 図解被覆 {res['with_visual']}/{res['judged']} = {ratio_s} が "
            f"下限 {res['min_ratio']:.2f} 未満。規約 visual-generation-rules.md §4 は "
            "「項目間に関係があり 3 件以上なら図解」と定める。文字リストは図ではない"
        )
    return summary, lines


# ---------------------------------------------------------------------------
# 自己テスト
#
# **自己テストが通ることは、本番の面に当たっていることを意味しない。**
# 内蔵 HTML は本検査器の分類器を試すだけで、実物の成果物が同じ綴りの面を
# 出している保証にはならない。実物へ当てて faces>0 を確認すること。
#
# 面 4 相当の反例 (SVG が 0 個でも CSS で図になっている面) は、実運用 deck
# slide-2026-08-15-AI質問会-v2-ink-on-paper/index.html の面 4 から採った実物である。
# ---------------------------------------------------------------------------
_SELF_TEST_HTML = """<!doctype html><html><head><style>
/* 実運用 deck の面 4 から採った CSS 製タイムライン (軸 + 節点) */
.timeline { position: relative; padding-left: 2vw; }
.timeline::before { content: ""; position: absolute; left: 0.6vw; top: 0; bottom: 0;
  width: 0.2vw; background: var(--accent-blue-vivid); }
.timeline-item { position: relative; padding-bottom: 1vw; }
.timeline-item::before { content: ""; position: absolute; left: -1.4vw; top: 0.4vw;
  width: 1.2vw; height: 1.2vw; border-radius: 50%; background: var(--accent-blue-vivid); }
/* 連番バッジ。節点だけで軸が無いので図と数えてはいけない (番号付き箇条書きと同じ) */
.list-item::before { content: counter(step); position: absolute; left: 1vw; top: 50%;
  width: 2.4vw; height: 2.4vw; border-radius: 50%; background: #ccc; }
</style></head><body>
<div class="slider">
  <div class="slider__item slide-hero"><h1>表紙</h1></div>
  <div class="slider__item slide-list"><h2>文字だけの面</h2>
    <ul class="list"><li class="list-item">あ</li><li class="list-item">い</li>
    <li class="list-item">う</li><li class="list-item">え</li></ul></div>
  <div class="slider__item slide-circle"><h2>図のある面</h2>
    <svg viewBox="0 0 100 100"><circle cx="1" cy="1" r="1"/><rect x="0" y="0" width="2" height="2"/>
    <text x="1" y="1">a</text></svg></div>
  <div class="slider__item d3-bar"><h2>D3 の面</h2>
    <div class="d3-mount"></div>
    <script type="application/json" data-d3-mount>{}</script></div>
  <div class="slider__item slide-timeline"><h2>SVG が無い CSS 製の図</h2>
    <ol class="timeline">
      <li class="timeline-item"><div class="timeline-date">建設業</div></li>
      <li class="timeline-item"><div class="timeline-date">IT業界</div></li>
      <li class="timeline-item"><div class="timeline-date">AI領域</div></li>
      <li class="timeline-item"><div class="timeline-date">現在</div></li>
    </ol>
    <aside class="tl-side"><img class="tl-side-qr" src="x.png" alt="XのQRコード"/></aside></div>
  <div class="slider__item slide-grid"><h2>QR が主役の面</h2>
    <div class="grid-cell"><img class="qr-img" src="qr.png" alt="QRコード"></div>
    <div class="grid-cell">x</div><div class="grid-cell">y</div></div>
  <div class="slider__item slide-table" data-slide-type="slide-table"><h2>表の面</h2>
    <table><tr><td>a</td></tr></table></div>
  <div class="slider__item slide-grid" data-diagram-exempt="登壇者紹介のため図を置かない">
    <h2>宣言除外</h2><div class="grid-cell">z</div></div>
  <div class="slider__item slide-grid"><h2>項目が 2 件だけ</h2>
    <div class="grid-cell">a</div><div class="grid-cell">b</div></div>
</div></body></html>"""

_SELF_TEST_EMPTY = "<!doctype html><html><body><p>面が 1 つも無い</p></body></html>"

_SELF_TEST_ICON_ONLY = """<div class="slider__item slide-list"><h2>アイコンだけ</h2>
<ul><li><svg viewBox="0 0 16 16"><path d="M0 0"/></svg>あ</li><li>い</li><li>う</li></ul></div>"""


def _self_test() -> int:
    failed = 0

    def check(label: str, got, want) -> None:
        nonlocal failed
        if got == want:
            print(f"  ok   - {label}")
        else:
            failed += 1
            print(f"  NG   - {label}: got={got!r} want={want!r}", file=sys.stderr)

    faces = parse_faces(_SELF_TEST_HTML)
    rules = extract_css_rules(_SELF_TEST_HTML)
    check("面を 9 件同定する", len(faces), 9)
    check("CSS 規則を取り出せる (> 0)", len(rules) > 0, True)
    res = evaluate(faces, DEFAULT_MIN_RATIO, EXEMPT_TYPES, rules)
    by_type = {f["index"]: f["verdict"] for f in res["classified"]}
    check("面1 表紙は除外", by_type[1], "exempt")
    check("面2 文字リストは赤", by_type[2], "text-list")
    check("面3 SVG は図", by_type[3], "figure")
    check("面4 D3 は図", by_type[4], "figure")
    check("面5 SVG 0 個の CSS 製タイムラインを図と数える (実物由来の反例)",
          by_type[5], "css-visual")
    check("面6 QR 主役は除外", by_type[6], "exempt")
    check("面7 表は構造化表示", by_type[7], "structured")
    check("面8 宣言除外", by_type[8], "exempt")
    check("面9 項目 2 件は判定保留 (赤にしない)", by_type[9], "unjudged")
    check("除外は 3 件", res["exempt"], 3)
    check("判定できた面は 5 件 (保留と除外は分母外)", res["judged"], 5)
    check("視覚構造を持つ面は 4 件", res["with_visual"], 4)
    check("うち CSS 製は 1 件", res["css_visual"], 1)
    check("ratio は 4/5", round(res["ratio"], 4), 0.8)
    check("ratio 0.80 >= 既定 0.50 なので pass", res["verdict"], "pass")
    check("min=1.00 なら fail", evaluate(faces, 1.0, EXEMPT_TYPES, rules)["verdict"], "fail")
    check("連番バッジ (軸が無い) を CSS 図と誤認しない",
          css_visual_signals({"list-item": 4}, rules), [])

    empty = evaluate(parse_faces(_SELF_TEST_EMPTY), DEFAULT_MIN_RATIO, EXEMPT_TYPES, [])
    check("面 0 件は no-target (緑にしない)", empty["verdict"], "no-target")
    check("面 0 件の分母は 0", empty["judged"], 0)

    icon = evaluate(parse_faces(_SELF_TEST_ICON_ONLY), DEFAULT_MIN_RATIO, EXEMPT_TYPES, [])
    check("path 1 本のアイコン svg は図と数えない", icon["with_visual"], 0)

    emitting, silent = figure_emitting_types()
    check("テンプレートを実測できている (合計 > 0)", len(emitting) + len(silent) > 0, True)
    if emitting or silent:
        check("slide-list は図を出さない型", "slide-list" in silent, True)
        check("slide-circle は図を出す型", "slide-circle" in emitting, True)
        check("d3-bar は図を出す型 (マウント点)", "d3-bar" in emitting, True)
        css_types = css_figure_types()
        check("engine CSS を読めている (規則 > 0)", len(engine_css_rules()) > 0, True)
        check("slide-timeline は CSS で図になる型 (テンプレートに svg が無い)",
              "slide-timeline" in css_types and "slide-timeline" in silent, True)
        check("slide-list は CSS で図になる型ではない", "slide-list" in css_types, False)
        st = evaluate_structure(
            {"slides": [{"slideType": "slide-hero"}, {"slideType": "slide-list"},
                        {"slideType": "slide-timeline"}, {"slideType": "slide-circle"}]},
            DEFAULT_MIN_RATIO, EXEMPT_TYPES)
        st_by = {f["index"]: f["verdict"] for f in st["classified"]}
        check("構成段階: hero は除外", st_by[1], "exempt")
        check("構成段階: slide-list は文字リスト候補", st_by[2], "text-list")
        check("構成段階: slide-timeline は CSS 図として数える", st_by[3], "css-visual")
        check("構成段階: slide-circle は図", st_by[4], "figure")
        check("構成段階: 判定できた面は 3 件", st["judged"], 3)

    total = 34 if (emitting or silent) else 23
    print(f"validate-diagram-coverage self-test: {total - failed}/{total} "
          f"{'PASS' if not failed else 'FAIL'}")
    print("注意: この self-test が通っても、実物の成果物の面に当たっている保証にはならない。"
          "実物へ当てて faces>0 を確認すること", file=sys.stderr)
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
USAGE = (
    "usage: validate-diagram-coverage.py <index.html|report.html|structure.json> [...] "
    "[--min-ratio R] [--exempt-type T[,T...]] [--json] | --self-test"
)


def main(argv: list[str]) -> int:
    args = argv[1:]
    if "--help" in args or "-h" in args:
        print(USAGE)
        print(__doc__)
        return 0
    if "--self-test" in args:
        return _self_test()

    min_ratio = DEFAULT_MIN_RATIO
    extra_exempt: set[str] = set()
    as_json = "--json" in args
    paths: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--min-ratio":
            i += 1
            if i >= len(args):
                print(USAGE, file=sys.stderr)
                return 2
            try:
                min_ratio = float(args[i])
            except ValueError:
                print(f"--min-ratio が数値でない: {args[i]}", file=sys.stderr)
                return 2
        elif a.startswith("--min-ratio="):
            try:
                min_ratio = float(a.split("=", 1)[1])
            except ValueError:
                print(f"--min-ratio が数値でない: {a}", file=sys.stderr)
                return 2
        elif a == "--exempt-type":
            i += 1
            if i >= len(args):
                print(USAGE, file=sys.stderr)
                return 2
            extra_exempt |= {t.strip() for t in args[i].split(",") if t.strip()}
        elif a.startswith("--exempt-type="):
            extra_exempt |= {t.strip() for t in a.split("=", 1)[1].split(",") if t.strip()}
        elif a == "--json":
            pass
        elif a.startswith("-"):
            print(f"未知のオプション: {a}\n{USAGE}", file=sys.stderr)
            return 2
        else:
            paths.append(a)
        i += 1

    if not paths:
        print(USAGE, file=sys.stderr)
        return 2

    exempt_types = EXEMPT_TYPES | extra_exempt
    if extra_exempt:
        print(f"diagram coverage: --exempt-type で追加除外した型: {sorted(extra_exempt)}",
              file=sys.stderr)

    worst = 0
    payload = []
    for path in paths:
        if not os.path.isfile(path):
            print(f"ERROR [DC0] {path}: ファイルが無い", file=sys.stderr)
            worst = max(worst, 3)
            continue
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"ERROR [DC0] {path}: 読めない ({exc})", file=sys.stderr)
            worst = max(worst, 3)
            continue
        if path.endswith(".json"):
            try:
                res = evaluate_structure(json.loads(text), min_ratio, exempt_types)
            except json.JSONDecodeError as exc:
                print(f"ERROR [DC0] {path}: JSON として読めない ({exc})", file=sys.stderr)
                worst = max(worst, 3)
                continue
        else:
            res = evaluate(parse_faces(text), min_ratio, exempt_types,
                           extract_css_rules(text))
        summary, lines = format_report(path, res)
        for ln in lines:
            print(ln, file=sys.stderr)
        print(summary)
        payload.append({k: v for k, v in res.items()
                        if k not in ("classified", "exempt_faces", "text_list_faces",
                                     "unjudged_faces")}
                       | {"path": path,
                          "text_list_faces": [{"index": f["index"], "type": f["type"],
                                               "heading": f["heading"], "li": f["li"],
                                               "cells": f["cells"]} for f in res["text_list_faces"]],
                          "unjudged_faces": [{"index": f["index"], "type": f["type"],
                                              "heading": f["heading"]} for f in res["unjudged_faces"]],
                          "exempt_faces": [{"index": f["index"], "type": f["type"],
                                            "reason": f["reason"]} for f in res["exempt_faces"]]})
        if res["verdict"] == "no-target":
            worst = max(worst, 2)
        elif res["verdict"] == "fail":
            worst = max(worst, 1)

    if as_json:
        print(json.dumps({"results": payload}, ensure_ascii=False, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
