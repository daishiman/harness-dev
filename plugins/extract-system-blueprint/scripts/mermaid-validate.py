#!/usr/bin/env python3
# /// script
# name: mermaid-validate
# version: 0.1.0
# purpose: extract-system-blueprint 生成物に製品出力契約の5種 Mermaid 図(①全体構成/②事実↔推測区別レイヤ/③画面遷移/④データフロー・シーケンス/⑤データモデル)が全て存在し構文的に妥当かを mmdc 非依存の決定論ロジックで検証する共有ゲート。C01 自己検証と C02 独立評価が同一ロジックで判定して基準乖離を防ぐ。harness-meta 図(as-is/Before-After/責務分離)は必須図種 enum から除外する。
# inputs:
#   - argv: --docs-dir DIR
# outputs:
#   - stdout: OK(+検出図種サマリ)
#   - stderr: 欠落図種別・構文violation
#   - exit: 0=OK / 1=欠落・構文不正 / 2=usage
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""必須5種 Mermaid 図の存在+構文妥当性を決定論検証する共有ゲート。

図種の意味的分類は plan に明示規約が無いため、本 validator が共有 SSOT として
次の決定論優先順位で図を分類する:

  1. 明示マーカー: fence 内 ``%% blueprint-diagram: <slug>`` または直前の
     ``<!-- blueprint-diagram: <slug> -->`` (最も権威的)
  2. 図種構造: ``sequenceDiagram`` → ④, ``erDiagram``/``classDiagram`` → ⑤
     (図種キーワードは書き換え不能な事実)
  3. キャプション/``%%`` コメントの日英キーワード (①②③ は graph/flowchart を
     共有するため、マーカーかキャプションが必要)

ノードラベル本文は分類に用いない(誤検出を避ける)。harness-meta と判定した図は
必須図種の計数から除外する。分類できない図はエラーにせず「追加図」として構文のみ
検査する。5種のいずれかが欠落 or いずれかの図が構文不正なら exit 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---- 必須図種 enum (表示順=①..⑤) ------------------------------------------

REQUIRED_TYPES: list[tuple[str, str]] = [
    ("system-architecture", "① 対象システム全体構成図"),
    ("fact-inference-layers", "② 事実↔推測区別レイヤ図"),
    ("screen-flow", "③ 画面遷移図 (screen-flow)"),
    ("data-flow-sequence", "④ データフロー・リクエスト/レスポンスのシーケンス図"),
    ("data-model", "⑤ 主要エンティティのデータモデル図"),
]
REQUIRED_SLUGS = [slug for slug, _ in REQUIRED_TYPES]
LABEL_BY_SLUG = dict(REQUIRED_TYPES)
HARNESS_META = "harness-meta"

# マーカー slug の別名 → 正準 slug。未知 slug は None(=未分類)。
SLUG_ALIASES: dict[str, str] = {
    "system-architecture": "system-architecture",
    "architecture": "system-architecture",
    "overall-architecture": "system-architecture",
    "system-overview": "system-architecture",
    "fact-inference-layers": "fact-inference-layers",
    "fact-inference": "fact-inference-layers",
    "fact-vs-inference": "fact-inference-layers",
    "screen-flow": "screen-flow",
    "screenflow": "screen-flow",
    "screen-transition": "screen-flow",
    "navigation": "screen-flow",
    "data-flow-sequence": "data-flow-sequence",
    "dataflow-sequence": "data-flow-sequence",
    "sequence": "data-flow-sequence",
    "request-response": "data-flow-sequence",
    "data-model": "data-model",
    "datamodel": "data-model",
    "entity": "data-model",
    "entities": "data-model",
    "er": "data-model",
    "harness-meta": HARNESS_META,
    "meta": HARNESS_META,
    "as-is": HARNESS_META,
    "before-after": HARNESS_META,
    "responsibility-split": HARNESS_META,
}

# キャプション/コメント語彙 (ja は生文字列, en は小文字化して部分一致)。
KEYWORDS_JA: dict[str, list[str]] = {
    "system-architecture": ["全体構成", "システム構成", "システム全体", "アーキテクチャ全体", "システムアーキテクチャ", "全体アーキ"],
    "screen-flow": ["画面遷移", "画面フロー", "遷移図", "ナビゲーション"],
    "data-flow-sequence": ["シーケンス", "データフロー", "データの流れ", "リクエスト", "レスポンス", "要求応答"],
    "data-model": ["データモデル", "エンティティ", "ER図", "ＥＲ図", "エンティティ関連", "データ構造"],
}
KEYWORDS_EN: dict[str, list[str]] = {
    "system-architecture": ["overall architecture", "system architecture", "architecture overview", "system overview", "system configuration"],
    "screen-flow": ["screen flow", "screen-flow", "screen transition", "navigation flow", "user flow", "page flow"],
    "data-flow-sequence": ["sequence diagram", "sequence", "data flow", "request/response", "request-response", "req/res"],
    "data-model": ["data model", "entity", "er diagram", "entity relationship", "entity-relationship", "schema diagram"],
}
HARNESS_META_JA = ["責務分離", "責務", "ハーネス", "as-is", "ビフォー", "アフター"]
HARNESS_META_EN = ["harness-meta", "harness meta", "responsibility", "before-after", "before/after", "as-is", "as is"]

# 既知の Mermaid 図種(先頭キーワード)。未知なら「不明な図種」違反。
KNOWN_KIND_TOKENS = {
    "graph", "flowchart", "sequencediagram", "erdiagram", "classdiagram",
    "statediagram", "statediagram-v2", "journey", "gantt", "pie", "mindmap",
    "timeline", "gitgraph", "quadrantchart", "requirementdiagram", "c4context",
    "c4container", "c4component", "c4dynamic", "xychart-beta", "block-beta",
    "sankey-beta", "packet-beta", "kanban", "architecture-beta", "radar-beta",
    "treemap-beta",
}
VALID_DIRECTIONS = {"TB", "TD", "BT", "RL", "LR"}
MARKER_RE = re.compile(r"blueprint-diagram\s*:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass
class Diagram:
    source: str          # repo/docs 相対でなく実パス表記(人間可読)
    line: int            # 1-based 開始行(md fence の開始行)
    body: list[str]      # fence 内(または .mmd 全体)の生の行
    caption: str = ""    # 直前キャプション(md)またはファイル名幹(.mmd)
    classification: str | None = field(default=None)
    violations: list[str] = field(default_factory=list)


# ---- 抽出 ------------------------------------------------------------------

_FENCE_OPEN = re.compile(r"^(\s{0,3})(`{3,}|~{3,})\s*([^\s`~]*)")


def _preceding_caption(lines: list[str], fence_start: int) -> str:
    """fence 開始行の直上、空行を飛ばした最寄りの非空行ブロックを返す。

    見出し/太字/HTMLコメント/短い説明文がここに来る。ノード本文は含めない。
    """
    i = fence_start - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    block: list[str] = []
    while i >= 0 and lines[i].strip() and len(block) < 6:
        block.append(lines[i].strip())
        i -= 1
    block.reverse()
    return "\n".join(block)


def extract_md_diagrams(text: str, source: str) -> list[Diagram]:
    """markdown からフェンス化 mermaid ブロックを抽出する。

    mermaid 以外のコードフェンスは中身を走査対象にせずスキップする(誤検出防止)。
    """
    diagrams: list[Diagram] = []
    lines = text.split("\n")
    n = len(lines)
    i = 0
    while i < n:
        m = _FENCE_OPEN.match(lines[i])
        if not m:
            i += 1
            continue
        fence_char = m.group(2)[0]
        fence_len = len(m.group(2))
        info = m.group(3).lower()
        start = i
        body: list[str] = []
        i += 1
        closed = False
        while i < n:
            cm = re.match(r"^(\s{0,3})(`{3,}|~{3,})\s*$", lines[i])
            if cm and cm.group(2)[0] == fence_char and len(cm.group(2)) >= fence_len:
                closed = True
                break
            body.append(lines[i])
            i += 1
        if info == "mermaid":
            diagrams.append(
                Diagram(source=source, line=start + 1, body=body,
                        caption=_preceding_caption(lines, start))
            )
        # 閉じフェンス行(または EOF)を消費して次へ
        i += 1 if closed else 0
        if not closed:
            break
    return diagrams


def extract_mmd_diagram(text: str, source: str, name_stem: str) -> list[Diagram]:
    body = text.split("\n")
    if not any(l.strip() for l in body):
        return []
    return [Diagram(source=source, line=1, body=body, caption=name_stem)]


def collect_diagrams(docs_dir: Path) -> list[Diagram]:
    diagrams: list[Diagram] = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        src = str(path)
        if suffix in (".md", ".markdown"):
            diagrams.extend(extract_md_diagrams(text, src))
        elif suffix in (".mmd", ".mermaid"):
            diagrams.extend(extract_mmd_diagram(text, src, path.stem))
    return diagrams


# ---- 分類 ------------------------------------------------------------------

def _strip_init_directives(line: str) -> str:
    return re.sub(r"%%\{.*?\}%%", "", line)


def meaningful_lines(body: list[str]) -> list[str]:
    """YAML frontmatter・空行・``%%`` コメントを除いた本文行(init 指令は除去)。"""
    out: list[str] = []
    lines = [l for l in body]
    idx = 0
    # 先頭 YAML frontmatter (--- ... ---) をスキップ
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and lines[idx].strip() == "---":
        j = idx + 1
        while j < len(lines) and lines[j].strip() != "---":
            j += 1
        if j < len(lines):
            idx = j + 1
    for raw in lines[idx:]:
        stripped_directive = _strip_init_directives(raw)
        s = stripped_directive.strip()
        if not s:
            continue
        if s.startswith("%%"):
            continue
        out.append(stripped_directive)
    return out


def detect_kind(diagram: Diagram) -> str | None:
    """正規化した図種トークン(小文字)を返す。判定不能なら None。"""
    for line in meaningful_lines(diagram.body):
        token = line.strip().split()[0] if line.strip().split() else ""
        token = token.rstrip(";").lower()
        if not token:
            continue
        if token in KNOWN_KIND_TOKENS:
            return token
        # 先頭が未知でも既知プレフィックスに寄せる(例: statediagram-v2)
        for known in KNOWN_KIND_TOKENS:
            if token == known:
                return known
        return token  # 未知トークン(呼び出し側で「不明な図種」判定に使う)
    return None


def _fence_comment_text(body: list[str]) -> str:
    return "\n".join(l.strip() for l in body if l.strip().startswith("%%"))


def _explicit_marker(diagram: Diagram) -> str | None:
    hay = _fence_comment_text(diagram.body) + "\n" + diagram.caption
    m = MARKER_RE.search(hay)
    if m:
        return m.group(1).lower()
    return None


def _match_any_ja_en(text: str, ja: list[str], en: list[str]) -> bool:
    low = text.lower()
    return any(k in text for k in ja) or any(k in low for k in en)


def _keyword_type(signal: str) -> str | None:
    """キャプション/コメント語彙から必須 slug を1つ返す(enum 順優先)。"""
    # ② は「事実」AND(推測/推論/区別/レイヤ/層)の複合条件
    low = signal.lower()
    fi_ja = "事実" in signal and any(k in signal for k in ["推測", "推論", "区別", "レイヤ", "層"])
    fi_en = "fact" in low and any(k in low for k in ["inference", "inferred", "layer"])
    # enum 順に判定(② を優先評価するため system-architecture より前に置く必要はなく、
    # ①③④⑤ は KEYWORDS で、② は複合条件で判定)
    for slug in REQUIRED_SLUGS:
        if slug == "fact-inference-layers":
            if fi_ja or fi_en:
                return slug
            continue
        if _match_any_ja_en(signal, KEYWORDS_JA.get(slug, []), KEYWORDS_EN.get(slug, [])):
            return slug
    return None


def classify(diagram: Diagram) -> str | None:
    """図の意味的種別 slug / 'harness-meta' / None(未分類) を決定論で返す。"""
    marker = _explicit_marker(diagram)
    if marker is not None:
        return SLUG_ALIASES.get(marker)  # 未知 slug は None

    signal = diagram.caption + "\n" + _fence_comment_text(diagram.body)
    if _match_any_ja_en(signal, HARNESS_META_JA, HARNESS_META_EN):
        return HARNESS_META

    kind = detect_kind(diagram)
    if kind == "sequencediagram":
        return "data-flow-sequence"
    if kind in ("erdiagram", "classdiagram"):
        return "data-model"

    kw = _keyword_type(signal)
    if kw is not None:
        return kw

    if kind in ("statediagram", "statediagram-v2"):
        return "screen-flow"
    return None


# ---- 構文検証 --------------------------------------------------------------

def _strip_quotes_and_comments(line: str) -> str:
    line = _strip_init_directives(line)
    # ``%%`` 以降を除去
    idx = line.find("%%")
    if idx != -1:
        line = line[:idx]
    # ダブルクォート文字列を除去(内部の括弧を数えない)
    return re.sub(r'"[^"]*"', '""', line)


# erDiagram のクロウズフット記法(例: ``||--o{`` ``}o--|{``)は括弧ではないため
# 波括弧の平衡計数から除外する。
_ER_CARDINALITY_RE = re.compile(r"[|}{o]+\s*(?:--|\.\.)\s*[|}{o]+")


def _check_balance(lines: list[str], kind: str | None = None) -> list[str]:
    violations: list[str] = []
    counts = {"[": 0, "]": 0, "(": 0, ")": 0, "{": 0, "}": 0}
    for line in lines:
        cleaned = _strip_quotes_and_comments(line)
        if kind == "erdiagram":
            cleaned = _ER_CARDINALITY_RE.sub(" ", cleaned)
        for ch in cleaned:
            if ch in counts:
                counts[ch] += 1
    pairs = [("[", "]", "角括弧 []"), ("(", ")", "丸括弧 ()"), ("{", "}", "波括弧 {}")]
    for open_ch, close_ch, label in pairs:
        if counts[open_ch] != counts[close_ch]:
            violations.append(
                f"{label} が非平衡 (open={counts[open_ch]} close={counts[close_ch]})"
            )
    return violations


_EDGE_RE = re.compile(r"(-{2,3}>|-{3}|={2,}>|={3,}|-\.-*>|\.-+>|-{1,2}[xo]|<-{1,2}>|o-{2,}o|x-{2,}x|~{3})")
_NODE_SHAPE_RE = re.compile(r"[A-Za-z0-9_]+\s*[\[\(\{>]")
_SEQ_MSG_RE = re.compile(r"-{1,2}>{1,2}|-{1,2}x|-{1,2}\)")
_SEQ_BLOCK_OPENERS = ("alt", "opt", "loop", "par", "critical", "rect", "break", "box")
_ER_REL_RE = re.compile(r"[|}o][|o{]?\s*(--|\.\.)\s*[|o{][|}o]?")


def _validate_flowchart(body: list[str], lines: list[str]) -> list[str]:
    violations: list[str] = []
    # 方向宣言
    first = lines[0].strip()
    dm = re.match(r"^(graph|flowchart)\b\s*([A-Za-z]{2})?", first)
    direction = (dm.group(2) or "").upper() if dm else ""
    if direction not in VALID_DIRECTIONS:
        violations.append(
            "方向宣言が欠落または不正 (graph/flowchart は TB/TD/BT/RL/LR のいずれかが必須)"
        )
    # ノード/エッジの存在
    rest = "\n".join(lines[1:])
    has_edge = bool(_EDGE_RE.search(_strip_quotes_and_comments(rest)))
    has_node = any(_NODE_SHAPE_RE.search(_strip_quotes_and_comments(l)) for l in lines[1:])
    if not has_edge and not has_node:
        violations.append("ノードもエッジも存在しない(空の flowchart)")
    # subgraph / end の平衡 と subgraph id 重複
    sub_ids: list[str] = []
    depth = 0
    for line in lines:
        s = _strip_quotes_and_comments(line).strip()
        if re.match(r"^subgraph\b", s):
            depth += 1
            mm = re.match(r"^subgraph\s+([A-Za-z0-9_]+)", s)
            if mm:
                sub_ids.append(mm.group(1))
        elif s == "end":
            depth -= 1
    if depth != 0:
        violations.append(f"subgraph と end が非平衡 (残 depth={depth})")
    dups = sorted({sid for sid in sub_ids if sub_ids.count(sid) > 1})
    if dups:
        violations.append(f"subgraph ID の重複: {', '.join(dups)}")
    return violations


def _validate_sequence(lines: list[str]) -> list[str]:
    violations: list[str] = []
    body_text = "\n".join(_strip_quotes_and_comments(l) for l in lines[1:])
    if not _SEQ_MSG_RE.search(body_text):
        violations.append("メッセージ矢印(->>/-->>/->/-->/-x など)が存在しない")
    opens = 0
    for line in lines[1:]:
        s = _strip_quotes_and_comments(line).strip()
        head = s.split()[0].lower() if s.split() else ""
        if head in _SEQ_BLOCK_OPENERS:
            opens += 1
        elif s == "end":
            opens -= 1
    if opens != 0:
        violations.append(f"ブロック(alt/opt/loop/par/rect/critical/break/box)と end が非平衡 (残={opens})")
    return violations


def _validate_er(lines: list[str]) -> list[str]:
    violations: list[str] = []
    body_text = "\n".join(_strip_quotes_and_comments(l) for l in lines[1:])
    has_rel = bool(_ER_REL_RE.search(body_text))
    has_entity_block = bool(re.search(r"[A-Za-z0-9_]+\s*\{", body_text))
    if not has_rel and not has_entity_block:
        violations.append("エンティティ定義もリレーションも存在しない")
    return violations


def _validate_class(lines: list[str]) -> list[str]:
    violations: list[str] = []
    body_text = "\n".join(_strip_quotes_and_comments(l) for l in lines[1:])
    signals = ["class ", "-->", "--|>", "..>", "..|>", "--*", "--o", " : ", "<|--", "*--", "o--"]
    if not any(sig in body_text for sig in signals):
        violations.append("クラス定義も関連も存在しない")
    return violations


def _validate_state(lines: list[str]) -> list[str]:
    violations: list[str] = []
    body_text = "\n".join(_strip_quotes_and_comments(l) for l in lines[1:])
    if "-->" not in body_text:
        violations.append("状態遷移(-->) が存在しない")
    return violations


def validate_syntax(diagram: Diagram) -> list[str]:
    lines = meaningful_lines(diagram.body)
    if not lines:
        return ["図の本文が空"]
    kind = detect_kind(diagram)
    if kind is None:
        return ["図種宣言(先頭行)が存在しない"]
    if kind not in KNOWN_KIND_TOKENS:
        return [f"不明な図種宣言: '{lines[0].strip().split()[0]}'"]

    violations = _check_balance(lines, kind)
    if kind in ("graph", "flowchart"):
        violations += _validate_flowchart(diagram.body, lines)
    elif kind == "sequencediagram":
        violations += _validate_sequence(lines)
    elif kind == "erdiagram":
        violations += _validate_er(lines)
    elif kind == "classdiagram":
        violations += _validate_class(lines)
    elif kind in ("statediagram", "statediagram-v2"):
        violations += _validate_state(lines)
    return violations


# ---- 集約 ------------------------------------------------------------------

@dataclass
class Result:
    diagrams: list[Diagram]
    found_types: set[str]
    missing_types: list[str]
    syntax_violations: list[tuple[Diagram, str]]

    @property
    def ok(self) -> bool:
        return not self.missing_types and not self.syntax_violations


def validate_docs(docs_dir: Path) -> Result:
    diagrams = collect_diagrams(docs_dir)
    found: set[str] = set()
    syntax_violations: list[tuple[Diagram, str]] = []
    for d in diagrams:
        d.classification = classify(d)
        # harness-meta は必須図種の計数・構文検査から除外する
        if d.classification == HARNESS_META:
            continue
        if d.classification in REQUIRED_SLUGS:
            found.add(d.classification)
        for v in validate_syntax(d):
            d.violations.append(v)
            syntax_violations.append((d, v))
    missing = [slug for slug in REQUIRED_SLUGS if slug not in found]
    return Result(diagrams, found, missing, syntax_violations)


# ---- CLI -------------------------------------------------------------------

def _emit_report(result: Result) -> None:
    for slug in result.missing_types:
        sys.stderr.write(f"MISSING DIAGRAM TYPE: {LABEL_BY_SLUG[slug]} (slug={slug})\n")
    for diagram, violation in result.syntax_violations:
        sys.stderr.write(
            f"SYNTAX VIOLATION: {diagram.source}:{diagram.line} {violation}\n"
        )
    if not result.ok:
        sys.stderr.write(
            f"\n図={len(result.diagrams)} 必須図種={len(result.found_types)}/5 "
            f"欠落={len(result.missing_types)} 構文違反={len(result.syntax_violations)}\n"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="製品出力の必須5種 Mermaid 図の存在+構文を mmdc 非依存で決定論検証する",
        add_help=True,
    )
    ap.add_argument("--docs-dir", required=True, help="検証対象の生成物ディレクトリ")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2

    docs_dir = Path(args.docs_dir)
    if not docs_dir.exists() or not docs_dir.is_dir():
        sys.stderr.write(f"docs-dir がディレクトリとして存在しない: {docs_dir}\n")
        return 2

    result = validate_docs(docs_dir)
    if result.ok:
        found_order = [LABEL_BY_SLUG[s] for s in REQUIRED_SLUGS if s in result.found_types]
        sys.stdout.write("OK\n")
        sys.stdout.write(
            f"diagrams={len(result.diagrams)} required=5/5 "
            f"[{', '.join(found_order)}]\n"
        )
        return 0

    _emit_report(result)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
