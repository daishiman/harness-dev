"""ref-handout-design-system (C04) の SKILL.md 宣言的契約チェッカ。

skill component は実行そのものを機械検査できないため、検査対象は SKILL.md の
**宣言** (frontmatter / 必須セクション / 規範文言 / 語彙を複製していないこと /
vendoring 実体の実在) である。

契約の出典:
  - plugin-plans/guide-doc-generator/briefs/skill-brief-C04.json (契約の正本)
  - plugin-plans/guide-doc-generator/component-inventory.json #C04
  - plugin-plans/guide-doc-generator/goal-spec.json R08 / R10 の criterion
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-P03.md (Y-05 / Y-06 / Y-08)
  - plugin-plans/guide-doc-generator/briefs/RESOLUTION-R21.md (C52)
  - plugin-plans/guide-doc-generator/briefs/script-brief-C11.json algorithm 11 / 12 / 18
  - plugin-plans/guide-doc-generator/briefs/script-brief-C15.json (アイコン様式と sprite owner)

標準ライブラリのみを使う (PyYAML は使わない)。frontmatter は本 plugin の
SKILL.md が使う YAML 部分集合だけを解釈する簡易パーサで読む。
"""

from __future__ import annotations

import re
from collections import namedtuple
from pathlib import Path

Violation = namedtuple("Violation", ["contract_id", "message"])


# --------------------------------------------------------------------------
# 契約の定数 (すべてブリーフ / inventory / goal-spec / RESOLUTION 由来)
# --------------------------------------------------------------------------

SKILL_NAME = "ref-handout-design-system"
BUILD_TARGET = "plugins/guide-doc-generator/skills/ref-handout-design-system/"

# skill-brief-C04.json の identity
IDENTITY = {
    "name": SKILL_NAME,
    "prefix": "ref",
    "kind": "ref",
    "hierarchy_level": "L1",
}

# skill-brief-C04.json trigger_conditions の 3 件から取る発見語彙
TRIGGER_TERMS = ("部品カタログ", "トークン", "アイコン")

# ref kind は実行系の宣言を持たない (inventory #C04: cli_tools / mcp_tools /
# deterministic_checks / combinators がいずれも空、feedback_contract は skip)
FORBIDDEN_FRONTMATTER_KEYS = (
    "goal_seek",
    "deterministic_checks",
    "cli_tools",
    "mcp_tools",
    "external_systems",
)

# skill-brief-C04.json output_contract の 4 面
REQUIRED_FACES = {
    "AC-C04-8a": ("部品カタログ", "部品カタログ の構成データ表現"),
    "AC-C04-8b": ("トークン", "CSS 変数トークン一覧"),
    "AC-C04-8c": ("アイコン", "アイコン規約"),
    "AC-C04-8d": ("文章設計", "文章設計の型"),
}

# RESOLUTION-P03 付記の正本表
CATALOG_POINTERS = {
    "AC-C04-10": ("config/handout-parts.json", "C11"),
    "AC-C04-11": ("config/handout-purposes.json", "C23"),
    "AC-C04-12": ("config/handout-sections.json", "C12"),
}

# script-brief-C11.json algorithm 11 (:root へ展開するアクセント 1 色 + 明度 4 段階)
ACCENT_TOKENS = (
    "--pop-primary",
    "--pop-primary-pastel",
    "--pop-primary-soft",
    "--pop-primary-deep",
)

# goal-spec R08 のアイコン様式 4 点
ICON_STYLE = (
    'viewBox="0 0 24 24"',
    'stroke="currentColor"',
    'fill="none"',
    'stroke-linecap="round"',
)

# P03 Y-06 / Y-08 の語彙 (1 行に 2 語以上並べたら「列挙」とみなす)
PURPOSE_VOCAB = ("guide", "report", "lecture", "onboarding", "agenda")
SECTION_KIND_VOCAB = (
    "standard",
    "agenda-timebox",
    "decisions",
    "action-items",
    "sources",
    "known-unknown-next",
    "flow-overview",
    "logistics",
    "capability-explainer",
    "handson",
    "anticipated-qa",
    "dialogue",
)

# 自己完結 (R10): 参照してはならないユーザーグローバル資産の書き方
HOME_PATH_PATTERNS = (r"~/\.claude", r"~/\.config", r"\$HOME", r"\$\{HOME\}")
ABSOLUTE_PATH_PATTERN = r"(?<![\w.])/(?:Users|home|opt|usr/local)/"
# 否定文脈でだけ言及を許す (「~/.claude を参照しない」は違反にしない)
NEGATION_MARKERS = ("しない", "禁止", "依存させない", "0 件", "ゼロ", "持たない", "避ける")

# vendoring 元 (R10 / C13)
VENDOR_SOURCE_TERMS = ("jp-web-design",)
VENDOR_MODE_TERMS = ("モードB", "モード B", "Pop")
VENDOR_DIRS = ("assets", "references")


# --------------------------------------------------------------------------
# 絵文字判定 (CR-EMOJI 層 1 の部分集合)
# --------------------------------------------------------------------------
# 正本は script-brief-C16.json canonical_rules.emoji_rule (CR-EMOJI)。本テストは
# SKILL.md というテキスト 1 面にしか適用しないため、層 1 のうち「単独で絵文字表示
# が既定」の範囲だけを見る。層 2 (VS16 を伴うときだけ違反) は U+FE0F の存在自体を
# 層 1 が捕えるので、部分集合でも取りこぼさない。ブロック丸ごとの denylist は
# CR-EMOJI が明示的に禁じているので使わない (★ ✔ © 等の記号は通す)。

_EMOJI_RANGES = (
    (0x1F000, 0x1F02F), (0x1F0A0, 0x1F0FF), (0x1F100, 0x1F1FF),
    (0x1F200, 0x1F2FF), (0x1F300, 0x1F5FF), (0x1F600, 0x1F64F),
    (0x1F680, 0x1F6FF), (0x1F700, 0x1F8FF), (0x1F900, 0x1F9FF),
    (0x1FA00, 0x1FAFF), (0xE0020, 0xE007F),
)
_EMOJI_SINGLES = frozenset(
    [0xFE0F, 0x20E3, 0x203C, 0x2049, 0x2614, 0x2615, 0x267F, 0x2693, 0x26A1,
     0x26AA, 0x26AB, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE, 0x26D4, 0x26EA,
     0x26F2, 0x26F3, 0x26F5, 0x26FA, 0x26FD, 0x2705, 0x270A, 0x270B, 0x2728,
     0x274C, 0x274E, 0x2757, 0x27B0, 0x27BF, 0x2934, 0x2935, 0x2B1B, 0x2B1C,
     0x2B50, 0x2B55]
    + list(range(0x2648, 0x2654))
    + list(range(0x2753, 0x2756))
    + list(range(0x2795, 0x2798))
    + list(range(0x2B05, 0x2B08))
)


def find_emoji(text: str) -> list:
    """絵文字コードポイントを `U+XXXX` 表記で返す (CR-EMOJI 層 1 の部分集合)。"""
    hits = []
    for ch in text:
        cp = ord(ch)
        if cp in _EMOJI_SINGLES or any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES):
            hits.append(f"U+{cp:04X}")
    return hits


# --------------------------------------------------------------------------
# 最小 YAML 部分集合パーサ (tests/run-handout-build/contract_lib.py と同一方式)
# --------------------------------------------------------------------------

_MAPPING_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*\s*:(\s|$)")


def _scalar(raw: str):
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _lines(text: str):
    out = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        out.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    return out


def _parse(lines, idx, indent):
    if idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
        seq = []
        while idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
            content = lines[idx][1][2:].strip()
            sub = [(indent + 2, content)] if content else []
            idx += 1
            while idx < len(lines) and lines[idx][0] > indent:
                sub.append(lines[idx])
                idx += 1
            if not sub:
                seq.append(None)
                continue
            if len(sub) == 1 and not _MAPPING_LINE.match(sub[0][1]):
                seq.append(_scalar(sub[0][1]))
                continue
            base = min(item[0] for item in sub)
            value, _ = _parse([(i - base, c) for i, c in sub], 0, 0)
            seq.append(value)
        return seq, idx

    mapping = {}
    while idx < len(lines) and lines[idx][0] == indent:
        line = lines[idx][1]
        if ":" not in line:
            break
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        idx += 1
        if rest:
            mapping[key] = _scalar(rest)
            continue
        if idx < len(lines) and lines[idx][0] > indent:
            value, idx = _parse(lines, idx, lines[idx][0])
            mapping[key] = value
        elif idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
            value, idx = _parse(lines, idx, indent)
            mapping[key] = value
        else:
            mapping[key] = None
    return mapping, idx


def parse_yaml_subset(text: str):
    lines = _lines(text)
    if not lines:
        return {}
    value, _ = _parse(lines, 0, lines[0][0])
    return value


def split_frontmatter(text: str):
    """(frontmatter_dict, body_text) を返す。frontmatter が無ければ (None, text)。"""
    if not text.startswith("---"):
        return None, text
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return None, text
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            fm = "\n".join(parts[1:i])
            body = "\n".join(parts[i + 1:])
            parsed = parse_yaml_subset(fm)
            return (parsed if isinstance(parsed, dict) else {}), body
    return None, text


# --------------------------------------------------------------------------
# パス解決
# --------------------------------------------------------------------------


def plugin_root() -> Path:
    """plugins/guide-doc-generator/ を返す。"""
    return Path(__file__).resolve().parents[2]


def build_target_dir() -> Path:
    """inventory #C04 build_target のディレクトリ。"""
    return plugin_root() / "skills" / SKILL_NAME


# --------------------------------------------------------------------------
# 本文の下ごしらえ
# --------------------------------------------------------------------------


def strip_code_fences(body: str) -> str:
    """```〜``` のフェンス内を落とした散文だけを返す。"""
    out, inside = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def headings(body: str) -> list:
    return [ln.strip() for ln in body.splitlines() if ln.strip().startswith("##")]


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _root_block_span(body: str):
    """`:root {` 〜 対応する `}` の (start, end) を返す。無ければ None。"""
    m = re.search(r":root\s*\{", body)
    if not m:
        return None
    depth = 0
    for i in range(m.end() - 1, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                return (m.start(), i + 1)
    return (m.start(), len(body))


def _count_vocab_on_one_line(prose: str, vocab) -> list:
    """1 行に語彙を 2 語以上並べている箇所 (= 列挙) を返す。"""
    hits = []
    for line in prose.splitlines():
        found = [w for w in vocab if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", line)]
        if len(found) >= 2:
            hits.append((line.strip()[:80], found))
    return hits


# --------------------------------------------------------------------------
# 検査本体
# --------------------------------------------------------------------------


def check_skill(skill_dir) -> list:
    """SKILL.md 一式を検査し Violation の一覧を返す。空リストなら受入。"""
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    v = []

    # AC-C04-1: build_target に SKILL.md が実在する
    if not skill_md.is_file():
        v.append(Violation("AC-C04-1", f"SKILL.md が存在しない: {skill_md}"))
        return v

    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        v.append(Violation("AC-C04-2", "SKILL.md に YAML frontmatter (--- で囲む) が無い"))
        fm, body = {}, text

    prose = strip_code_fences(body)
    head = headings(body)

    v += _check_identity(fm)
    v += _check_ref_kind(fm)
    v += _check_faces(head, body)
    v += _check_boundary(prose)
    v += _check_vocabulary_pointers(prose)
    v += _check_tokens(prose, body)
    v += _check_typography_motion(body)
    v += _check_icons(body, prose)
    v += _check_emoji(prose)
    v += _check_selfcontained(prose)
    v += _check_vendoring(skill_dir, prose)
    return v


def _check_identity(fm) -> list:
    v = []
    # AC-C04-2: identity が brief と一致する
    for key, want in IDENTITY.items():
        got = fm.get(key)
        if got != want:
            v.append(Violation("AC-C04-2", f"frontmatter {key} が {want!r} でない (実際: {got!r})"))

    # AC-C04-3: description が trigger 語彙で発見可能
    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        v.append(Violation("AC-C04-3", "frontmatter description が空"))
    else:
        missing = [t for t in TRIGGER_TERMS if t not in desc]
        if missing:
            v.append(Violation(
                "AC-C04-3",
                f"description に trigger 語彙が欠落: {missing} (trigger_conditions 3 件由来)",
            ))
        if "とき" not in desc:
            v.append(Violation("AC-C04-3", "description が「〜するとき」の発火条件形でない"))

    # AC-C04-4: 出力言語
    if fm.get("output_language") != "ja":
        v.append(Violation("AC-C04-4", f"output_language が ja でない (実際: {fm.get('output_language')!r})"))

    # AC-C04-5: 追跡性
    source = str(fm.get("source") or "")
    if "component-inventory.json#C04" not in source.replace(" ", ""):
        v.append(Violation("AC-C04-5", f"source が component-inventory.json#C04 を指していない (実際: {source!r})"))
    return v


def _check_ref_kind(fm) -> list:
    v = []
    # AC-C04-6: allowed-tools は Read のみ (参照回答しかしないため書込も実行も持たない)
    tools = [str(t).strip() for t in _as_list(fm.get("allowed-tools"))]
    if not tools:
        v.append(Violation("AC-C04-6", "allowed-tools が宣言されていない"))
    else:
        if "Read" not in tools:
            v.append(Violation("AC-C04-6", f"allowed-tools に Read が無い (実際: {tools})"))
        extra = [t for t in tools if t != "Read"]
        if extra:
            v.append(Violation(
                "AC-C04-6",
                f"ref skill は参照回答のみ。allowed-tools に Read 以外がある: {extra}",
            ))

    # AC-C04-7: 実行系 / ループ系の宣言を持たない (inventory #C04 は全て空)
    for key in FORBIDDEN_FRONTMATTER_KEYS:
        if fm.get(key):
            v.append(Violation("AC-C04-7", f"ref kind は {key} を持たない (inventory #C04 は空)"))
    if fm.get("combinators"):
        v.append(Violation("AC-C04-7", "inventory #C04 の combinators は空。宣言してはならない"))
    if fm.get("feedback_contract"):
        v.append(Violation(
            "AC-C04-7",
            "inventory #C04 の feedback_contract は skip_reason のみ。反復ループを宣言してはならない",
        ))
    return v


def _check_faces(head, body) -> list:
    v = []
    # AC-C04-8: output_contract の 4 面それぞれに見出しがある
    if not any(h.startswith("## Purpose & Output Contract") for h in head):
        v.append(Violation("AC-C04-8", "本文に `## Purpose & Output Contract` が無い (repo の SKILL.md 骨格)"))
    for cid, (term, label) in REQUIRED_FACES.items():
        if not any(term in h for h in head):
            v.append(Violation(cid, f"output_contract の面「{label}」に対応する見出しが無い ('{term}' を含む ## 見出し)"))
    return v


def _check_boundary(prose) -> list:
    v = []
    # AC-C04-9: HTML の生成・検証をしない / 委譲先を名指しする
    has_heading = any("境界" in ln or "Boundary" in ln for ln in prose.splitlines() if ln.strip().startswith("##"))
    if not has_heading:
        v.append(Violation("AC-C04-9", "責務境界の見出し (境界 / Boundary) が無い"))
    if not re.search(r"HTML[^\n]{0,40}(生成|レンダリング)[^\n]{0,40}しない", prose):
        v.append(Violation("AC-C04-9", "「HTML の生成をしない」旨の明記が無い (brief boundary)"))
    if not re.search(r"検証[^\n]{0,30}しない", prose):
        v.append(Violation("AC-C04-9", "「検証をしない」旨の明記が無い (brief boundary)"))
    for owner in ("C11", "C16"):
        if owner not in prose:
            v.append(Violation("AC-C04-9", f"委譲先 {owner} の名指しが無い (brief boundary: C11/C16-C18 の責務)"))
    return v


def _check_vocabulary_pointers(prose) -> list:
    v = []
    # AC-C04-10 / 11 / 12: 語彙の正本ファイルを指し、値をこちらへ複製しない
    for cid, (path, owner) in CATALOG_POINTERS.items():
        if path not in prose:
            v.append(Violation(cid, f"語彙の正本 {path} へのポインタが無い (P03 の正本表)"))
        if owner not in prose:
            v.append(Violation(cid, f"{path} の owner {owner} を明記していない"))

    # AC-C04-10: 部品 id を本文へ列挙しない (P03 Y-05)
    part_ids = re.findall(r"(?<![\w-])B\d{2}(?![\w-])", prose)
    if part_ids:
        v.append(Violation(
            "AC-C04-10",
            f"部品 id を本文へ列挙している (P03 Y-05 違反): {sorted(set(part_ids))}",
        ))
    if not re.search(r"(カタログを読ん|カタログを参照|読んで答え)", prose):
        v.append(Violation("AC-C04-10", "「常にカタログを読んで答える」旨の明記が無い (brief output_contract)"))

    # AC-C04-11 / 12: 用途語彙・section_kind 値を列挙しない (P03 Y-06 / Y-08)
    for line, found in _count_vocab_on_one_line(prose, PURPOSE_VOCAB):
        v.append(Violation("AC-C04-11", f"用途語彙を列挙している (P03 Y-06 違反) {found}: {line}"))
    for line, found in _count_vocab_on_one_line(prose, SECTION_KIND_VOCAB):
        v.append(Violation("AC-C04-12", f"section_kind 値を列挙している (P03 Y-08 違反) {found}: {line}"))
    return v


def _check_tokens(prose, body) -> list:
    v = []
    # AC-C04-13: アクセント 1 色 + 明度 4 段階の CSS 変数名 (C11 algorithm 11 と同語彙)
    missing = [t for t in ACCENT_TOKENS if t not in body]
    if missing:
        v.append(Violation("AC-C04-13", f"アクセントの CSS 変数が欠落: {missing} (C11 algorithm 11)"))
    if not re.search(r"明度[^\n]{0,20}4\s*段階|4\s*段階[^\n]{0,20}明度", prose):
        v.append(Violation("AC-C04-13", "「アクセント 1 色 + 明度 4 段階」の規範が明記されていない (R10)"))

    # AC-C04-14: CSS 変数駆動 (実値は :root だけ / 以降は var() 参照)
    # 「var( が本文のどこかにある」では、アクセントを直値で書いた例示を通して
    # しまう。実値の出現位置そのものを見る。
    root_span = _root_block_span(body)
    if root_span is None:
        v.append(Violation("AC-C04-14", ":root ブロックの例示が無い (C11 algorithm 11)"))
    outside = [
        m.group(0)
        for m in re.finditer(r"#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])", body)
        if root_span is None or not (root_span[0] <= m.start() < root_span[1])
    ]
    if outside:
        v.append(Violation(
            "AC-C04-14",
            f"アクセント実値が :root の外に現れている: {sorted(set(outside))}。以降は var() 参照にする (R10)",
        ))
    if not re.search(r"var\(\s*--pop-", body[root_span[1]:] if root_span else body):
        v.append(Violation("AC-C04-14", ":root 以降でトークンを var() 参照する例示が無い (R10: CSS 変数駆動)"))

    # AC-C04-15: 値の正本はテーマトークンファイル。実値を散文へ焼かない
    if "assets/tokens/" not in prose:
        v.append(Violation("AC-C04-15", "テーマトークンの所在 assets/tokens/ が示されていない"))
    if "差し替え" not in prose:
        v.append(Violation("AC-C04-15", "テーマ (アクセント色) 差し替え可能である旨の明記が無い (R10)"))
    hexes = re.findall(r"#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])", prose)
    if hexes:
        v.append(Violation(
            "AC-C04-15",
            f"散文にアクセント実値 (hex) を列挙している: {sorted(set(hexes))}。値の正本は assets/tokens/<theme>.json",
        ))

    # AC-C04-16: R21 C52 のテーマトークン拡張。値も折り畳み規則も owner は自分ではない
    if "text_limits.block_body_max_chars" not in body:
        v.append(Violation("AC-C04-16", "text_limits.block_body_max_chars の言及が無い (R21 C52)"))
    if "400" not in body:
        v.append(Violation("AC-C04-16", "block_body_max_chars の既定 400 が示されていない (R21 C52)"))
    if not re.search(r"(スキーマ|schema)[^\n]{0,40}C11", prose):
        v.append(Violation("AC-C04-16", "テーマトークンのスキーマ owner が C11 であると明記していない (R21 C52)"))
    if "CR-TEXT-FOLD" not in prose:
        v.append(Violation("AC-C04-16", "折り畳み規則の正本 CR-TEXT-FOLD (C12) を指していない (R21 C52)"))
    return v


def _check_typography_motion(body) -> list:
    v = []
    # AC-C04-17: 和文タイポグラフィと数値表記 (C11 algorithm 12)
    if 'font-feature-settings' not in body or '"palt"' not in body:
        v.append(Violation("AC-C04-17", 'font-feature-settings:"palt" の規約が無い (C11 algorithm 12)'))
    if "tabular-nums" not in body:
        v.append(Violation("AC-C04-17", "数値の tabular-nums 規約が無い (C11 algorithm 12)"))

    # AC-C04-18: rise-in スタガー入場 (C11 algorithm 18 / R10)
    if "rise-in" not in body:
        v.append(Violation("AC-C04-18", "入場アニメーション rise-in の言及が無い (C11 algorithm 18)"))
    if "--stagger" not in body:
        v.append(Violation("AC-C04-18", "--stagger インライン変数の言及が無い (R10)"))
    if not re.search(r"(JS|JavaScript)[^\n]{0,30}(非依存|使わない|不要|用いない)", body):
        v.append(Violation("AC-C04-18", "スタガー入場が JS 非依存である旨の明記が無い (R10)"))
    if "prefers-reduced-motion" not in body:
        v.append(Violation("AC-C04-18", "prefers-reduced-motion の配慮が書かれていない (C11 algorithm 18)"))
    return v


def _check_icons(body, prose) -> list:
    v = []
    # AC-C04-19: アイコン様式 4 点 (goal-spec R08)
    missing = [s for s in ICON_STYLE if s not in body]
    if missing:
        v.append(Violation("AC-C04-19", f"アイコン様式の明記が欠落: {missing} (R08)"))

    # AC-C04-20: symbol 定義 + use 参照 / 未使用 0 件 / sprite 生成は C15
    if "<symbol" not in body:
        v.append(Violation("AC-C04-20", "<symbol> 定義の規約が無い (R08)"))
    if "<use" not in body:
        v.append(Violation("AC-C04-20", "<use> 参照の規約が無い (R08)"))
    if not re.search(r"未使用[^\n]{0,20}(0|ゼロ)", prose):
        v.append(Violation("AC-C04-20", "未使用 symbol が 0 件である規範が無い (R08)"))
    if "C15" not in prose:
        v.append(Violation("AC-C04-20", "sprite 生成の owner C15 (build-icon-sprite.py) を名指ししていない"))
    return v


def _check_emoji(prose) -> list:
    v = []
    # AC-C04-21: 絵文字を使わない規範と、自分自身が絵文字を含まないこと (R08)
    if not re.search(r"絵文字[^\n]{0,30}(使わない|禁止|用いない|使用しない)", prose):
        v.append(Violation("AC-C04-21", "「絵文字は使わない」規範の明記が無い (R08)"))
    hits = find_emoji(prose)
    if hits:
        v.append(Violation("AC-C04-21", f"SKILL.md 自身が絵文字を含む: {sorted(set(hits))}"))
    return v


def _check_selfcontained(prose) -> list:
    v = []
    # AC-C04-22: ユーザーグローバル資産 / 絶対パスへの参照 0 件 (R10)
    for line in prose.splitlines():
        for pat in HOME_PATH_PATTERNS:
            if re.search(pat, line):
                if any(marker in line for marker in NEGATION_MARKERS):
                    continue  # 「参照しない」という否定文脈での言及は違反にしない
                v.append(Violation(
                    "AC-C04-22",
                    f"ユーザーグローバル資産への参照がある (R10 違反): {line.strip()[:80]}",
                ))
        if re.search(ABSOLUTE_PATH_PATTERN, line):
            v.append(Violation(
                "AC-C04-22",
                f"絶対パスを直書きしている (実行時可搬性違反): {line.strip()[:80]}",
            ))
    return v


def _check_vendoring(skill_dir: Path, prose: str) -> list:
    v = []
    # AC-C04-23: vendoring 元の明記と、skill 配下の vendoring 実体
    if not any(t in prose for t in VENDOR_SOURCE_TERMS):
        v.append(Violation("AC-C04-23", "vendoring 元 jp-web-design の明記が無い (R10)"))
    if not any(t in prose for t in VENDOR_MODE_TERMS):
        v.append(Violation("AC-C04-23", "採用モード (モードB「Pop・親しみ」) の明記が無い (R10)"))

    vendored = []
    for d in VENDOR_DIRS:
        base = skill_dir / d
        if base.is_dir():
            vendored += [p for p in sorted(base.rglob("*")) if p.is_file()]
    if not vendored:
        v.append(Violation(
            "AC-C04-23",
            f"vendoring 実体が無い: {skill_dir}/{{{'|'.join(VENDOR_DIRS)}}}/ 配下にファイルが 1 件も無い",
        ))
        return v

    referenced = [p for p in vendored if p.relative_to(skill_dir).as_posix() in prose]
    if not referenced:
        v.append(Violation(
            "AC-C04-23",
            "SKILL.md が vendoring 実体を 1 件も参照していない "
            f"(実体: {[p.relative_to(skill_dir).as_posix() for p in vendored][:5]})",
        ))
    return v


def violation_ids(violations) -> set:
    return {x.contract_id for x in violations}


ALL_CONTRACT_IDS = (
    "AC-C04-1", "AC-C04-2", "AC-C04-3", "AC-C04-4", "AC-C04-5", "AC-C04-6",
    "AC-C04-7", "AC-C04-8", "AC-C04-8a", "AC-C04-8b", "AC-C04-8c", "AC-C04-8d",
    "AC-C04-9", "AC-C04-10", "AC-C04-11", "AC-C04-12", "AC-C04-13", "AC-C04-14",
    "AC-C04-15", "AC-C04-16", "AC-C04-17", "AC-C04-18", "AC-C04-19", "AC-C04-20",
    "AC-C04-21", "AC-C04-22", "AC-C04-23",
)
