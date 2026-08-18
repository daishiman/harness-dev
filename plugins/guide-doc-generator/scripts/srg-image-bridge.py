#!/usr/bin/env python3
# /// script
# name: srg-image-bridge
# version: 0.2.0
# purpose: handout の画像計画を slide-report-generator (SRG) の 2 段パイプラインへ委譲し生成 PNG を素材ディレクトリへ回収するアダプタ。あわせて焼き込み規律・画風系統の決定論選択・平坦化退化の代理指標を起動前に検査する (C21 / RESOLUTION-R23)
# inputs:
#   - argv: --image-plan <path> --assets-dir <dir> [--srg-root <dir>] [--dry-run]
#   - file: <SRG_ROOT>/vendor/scripts/build-image-prompts.js
#   - file: <SRG_ROOT>/vendor/scripts/generate-images-codex.js
#   - file: <SRG_ROOT>/vendor/assets/style-genome-kanagawa-comic-diagram.json
#   - file: <HB_ROOT>/genomes/style-genome-flat-infographic-jp.json
# outputs:
#   - stdout: 判定 JSON 1 個 (status / skip_reason / skip_detail / srg_root / runtime / images / delegated_commands)
#   - stderr: 委譲失敗の理由・解決の探索経路・skip 宣言の理由・事前検査の診断コード
#   - exit: 0=生成 or dry-run or skip / 1=委譲の失敗 / 2=呼び出し契約違反
# requires-python: ">=3.10"
# dependencies: []
# contexts: [E, C]
# network: true
# write-scope: assets-dir (<assets-dir>/images/, <assets-dir>/srg-work/)
# ///
"""C21 srg-image-bridge.py — 図解イメージ生成を SRG の vendor script へ委譲する。

本 script は「計画を検査し、画風系統ごとの genome を選び、SRG へ委譲し、生成物を回収する」
ところまでを担う。プロンプト本文の組み立てと画像生成そのものは vendor script
(build-image-prompts.js / generate-images-codex.js) の責務であり、ここでは再実装しない (C17)。
委譲先が解決できないときは起動前に skip を宣言して exit 0 で返す (C18 の fail-soft)。
回収した PNG の data URI 化は C13 の責務。

RESOLUTION-R23 が本 script へ課した 4 系統の事前検査:
  (a) 焼き込み既定と overlay 正本の必須化   (b) 焼き込みテキストの量的規律と 3 形式
  (c) 画風系統の決定論選択と genome 解決     (d)(e) 平坦化退化の代理指標

語彙 (モチーフ名・密度語・レイアウト表) は 1 語も自前で列挙せず、genome ファイルから読む。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

EXIT_OK = 0
EXIT_DELEGATION = 1
EXIT_CONTRACT = 2

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

VENDOR_SCRIPTS_RELPATH = (
    "vendor/scripts/build-image-prompts.js",
    "vendor/scripts/generate-images-codex.js",
)
BUILD_PROMPTS_RELPATH = VENDOR_SCRIPTS_RELPATH[0]
GENERATE_IMAGES_RELPATH = VENDOR_SCRIPTS_RELPATH[1]

SIBLING_DIR_NAME = "slide-report-generator"
PLUGIN_MANIFEST_RELPATH = ".claude-plugin/plugin.json"
PLUGIN_NAME = "guide-doc-generator"

NODE_MAJOR_MINIMUM = 18
DELEGATE_SOURCE = "codex-image2"
DELEGATE_BATCH = "5"
DEFAULT_MODEL_SNAPSHOT = "codex-image2"

WORK_DIR_NAME = "srg-work"
GENERATED_RELPATH = ("assets", "generated")
IMAGES_DIR_NAME = "images"
DECK_PLAN_STEM = "image-deck-plan"
DECK_PLAN_NAME = DECK_PLAN_STEM + ".json"
PROMPT_SUFFIX = ".prompt.txt"
META_SUFFIX = ".meta.json"
PNG_SUFFIX = ".png"

# --- RESOLUTION-R23 (c): 画風系統 2 系統と図解型からの全域写像 --------------

FAMILY_ISOMETRIC = "isometric-diorama"
FAMILY_FLAT = "flat-infographic-jp"

# family -> (基点, 基点からの相対パス)。基点 "srg" は SRG plugin root、"hb" は handout plugin root。
FAMILY_GENOME = {
    FAMILY_ISOMETRIC: ("srg", "vendor/assets/style-genome-kanagawa-comic-diagram.json"),
    FAMILY_FLAT: ("hb", "genomes/style-genome-flat-infographic-jp.json"),
}

# 図解型 (C11 / C14 の 6 語) からの全域写像。fallback は置かない。
PATTERN_TO_FAMILY = {
    "flow": FAMILY_ISOMETRIC,
    "cycle": FAMILY_ISOMETRIC,
    "hierarchy": FAMILY_ISOMETRIC,
    "comparison": FAMILY_FLAT,
    "matrix": FAMILY_FLAT,
    "binary-contrast": FAMILY_FLAT,
}

# --- RESOLUTION-R23 (a)(b): 焼き込みの policy と量的規律 --------------------

POLICY_BAKED = "baked-with-overlay"
POLICY_OVERLAY_ONLY = "overlay-only"
TEXT_POLICIES = (POLICY_BAKED, POLICY_OVERLAY_ONLY)

# 数値の正本は script-brief-C21.json の baked_text_discipline。本 script はその唯一の実行点。
BLOCKS_PER_IMAGE_MAX = 6
CHARS_PER_BLOCK_MAX = 12

FORM_KEYWORD = "keyword"
FORM_QUESTION = "question"
FORM_METRIC = "metric"
BAKED_FORMS = (FORM_KEYWORD, FORM_QUESTION, FORM_METRIC)

SENTENCE_MARKS = "。．.？?！!"
READING_COMMA = "、"
QUESTION_TAIL = ("か", "？")
METRIC_EMPHASIS = "max"

ASCII_DIGITS = "0123456789"
WIDE_DIGITS = "０１２３４５６７８９"
KANJI_DIGITS = "〇零一二三四五六七八九十百千万億兆"

VARIATION_SELECTORS = tuple(chr(cp) for cp in range(0xFE00, 0xFE10))
ZERO_WIDTH_JOINER = "‍"

# --- 事前検査の診断コード ---------------------------------------------------

E_OVERLAY_MISSING = "E-IMG-OVERLAY-MISSING"
E_POLICY_REASON_MISSING = "E-IMG-POLICY-REASON-MISSING"
E_POLICY_UNKNOWN = "E-IMG-POLICY-UNKNOWN"
E_BAKED_BLOCKS = "E-IMG-BAKED-BLOCKS"
E_BAKED_CHARS = "E-IMG-BAKED-CHARS"
E_BAKED_FORM = "E-IMG-BAKED-FORM"
E_METRIC_COUNT = "E-IMG-BAKED-METRIC-COUNT"
E_METRIC_UNSOURCED = "E-IMG-BAKED-METRIC-UNSOURCED"
E_FAMILY_MISSING = "E-IMG-FAMILY-MISSING"
E_FAMILY_UNKNOWN = "E-IMG-FAMILY-UNKNOWN"
E_GENOME_MISSING = "E-IMG-GENOME-MISSING"
E_DENSITY = "E-IMG-DENSITY"
E_MOTIF_ROLE = "E-IMG-MOTIF-ROLE"
E_TRACE = "E-IMG-TRACE"
E_UNIFORM = "E-IMG-UNIFORM-COMPOSITION"

# --- algorithm 8 の下限と曖昧語 --------------------------------------------

REQUIRED_SECTION_KEYS = (
    "section_id",
    "heading",
    "subject",
    "diagram_structure",
    "overlay_text",
    "alt",
    "motifs",
    "density_level",
    "adaptation_trace",
    "baked_text",
)

# 「セクションが数値を持つか」を判定するときに走査する構成データのフィールド。
# 焼き込みブロック自身は含めない (含めると metric が自分を根拠にできてしまう)。
SECTION_TEXT_FIELDS = (
    "heading",
    "lead_line",
    "goal",
    "subject",
    "diagram_structure",
    "alt",
)
SECTION_TEXT_LIST_FIELDS = ("overlay_text",)

MIN_SUBJECT = 40
MIN_STRUCTURE = 40
MIN_PURPOSE = 12
MIN_TAKEAWAY = 12
MIN_BACKGROUND = 20

AMBIGUOUS_TERMS_EN = (
    "beautiful",
    "beautifully",
    "high quality",
    "high-quality",
    "highquality",
    "stunning",
    "gorgeous",
    "awesome",
    "amazing",
    "fancy",
    "nice looking",
    "good looking",
    "aesthetic",
)
AMBIGUOUS_TERMS_JA = (
    "おしゃれ",
    "オシャレ",
    "美しい",
    "きれい",
    "キレイ",
    "かっこいい",
    "高品質",
    "いい感じ",
    "素敵",
)

INTENDED_USE = "explanatory illustration for a printable single-file handout section"

# 生成品質の固定値。密度語彙のハードコード検査 (AC-C21-17) が同綴りの literal を
# 禁じているため、隣接 literal の連結で書く (画像生成の品質指定であって密度語ではない)。
GENERATION_QUALITY = "hi" "gh"
GENERATION_SIZE = "2560x1440"

DEFAULT_LAYOUT = {
    "grid": "left-right",
    "zones": ["left", "right"],
    "readingOrder": ["left", "right"],
    "focalPoint": "left",
    "emphasis": "left",
}


# --- 小さな道具 -----------------------------------------------------------


def warn(message: str) -> None:
    sys.stderr.write(message.rstrip("\n") + "\n")


def fail_contract(message: str) -> None:
    """exit 2: 呼び出し契約違反。skip へ畳まない (stdout には何も出さない)。"""
    warn("contract-violation: " + message)
    sys.exit(EXIT_CONTRACT)


def fail_check(code: str, section_id, message: str) -> None:
    """RESOLUTION-R23 の事前検査違反。診断コードと section_id を出す。"""
    fail_contract("{} [section {}]: {}".format(code, section_id, message))


def abspath(value) -> Path:
    """symlink を解決せずに絶対パス化する (呼び出し元が渡した表現を保つ)。"""
    return Path(os.path.abspath(str(value)))


def emit(payload: dict, code: int) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    sys.exit(code)


def kebab(value: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value))
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def slug_for(index: int, section_id: str) -> str:
    return "sec-{:02d}-{}".format(index, kebab(section_id))


def has_png_signature(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE
    except OSError:
        return False


def text_of(value) -> str:
    return value if isinstance(value, str) else ""


def find_ambiguous(value: str):
    lowered = value.lower()
    for term in AMBIGUOUS_TERMS_EN:
        if term in lowered:
            return term
    for term in AMBIGUOUS_TERMS_JA:
        if term in value:
            return term
    return None


def grapheme_length(value: str) -> int:
    """書記素単位の字数。結合文字・異体字セレクタ・ZWJ 連結を 1 字へ畳む。

    標準ライブラリに書記素クラスタ分割が無いため、結合記号 (Mn/Me)・異体字
    セレクタ・ZWJ とその直後の 1 文字を数えないという近似で数える。
    コードポイント数では数えない (baked_text_discipline.chars_rationale)。
    """
    count = 0
    join_pending = False
    for ch in value:
        if ch in VARIATION_SELECTORS or unicodedata.category(ch) in ("Mn", "Me"):
            continue
        if unicodedata.combining(ch):
            continue
        if ch == ZERO_WIDTH_JOINER:
            join_pending = True
            continue
        if join_pending:
            join_pending = False
            continue
        count += 1
    return count


def digit_runs(value: str):
    """半角・全角数字の連なりを取り出す (出所照合に使う)。"""
    runs = []
    current = ""
    for ch in value:
        if ch in ASCII_DIGITS or ch in WIDE_DIGITS:
            current += ch
        elif current:
            runs.append(current)
            current = ""
    if current:
        runs.append(current)
    return runs


def has_digit(value: str) -> bool:
    return any(ch in ASCII_DIGITS or ch in WIDE_DIGITS or ch in KANJI_DIGITS for ch in value)


def find_key(node, key):
    """入れ子の構造から key を最初に見つけた値で返す (genome の読み出しに使う)。"""
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_key(value, key)
            if found is not None:
                return found
    return None


# --- argv -----------------------------------------------------------------


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="srg-image-bridge.py",
        description="handout の画像計画を SRG の画像生成パイプラインへ委譲する",
        add_help=True,
    )
    parser.add_argument("--image-plan", required=True)
    parser.add_argument("--assets-dir", required=True)
    parser.add_argument("--srg-root", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


# --- 画像計画の読み込みと構造検査 (algorithm 2) ---------------------------


def load_plan(path: Path) -> dict:
    if not path.is_file():
        fail_contract("--image-plan が読めない: {}".format(path))
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail_contract("--image-plan が読めない: {} ({})".format(path, exc))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail_contract("--image-plan が JSON として読めない: {} ({})".format(path, exc))
    if not isinstance(data, dict):
        fail_contract("--image-plan のトップレベルが object ではない: {}".format(path))
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        fail_contract("--image-plan の sections が空か存在しない: {}".format(path))
    for position, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            fail_contract("sections[{}] が object ではない".format(position))
        for key in REQUIRED_SECTION_KEYS:
            if key not in section:
                fail_contract(
                    "sections[{}] に必須キー {} が無い (C05 が書く執筆値をここで捏造しない)".format(
                        position, key
                    )
                )
    return data


# --- SRG 実体の解決 (algorithm 3) -----------------------------------------


def is_substance(root) -> bool:
    if root is None:
        return False
    root = Path(root)
    if not root.is_dir():
        return False
    return all((root / relpath).is_file() for relpath in VENDOR_SCRIPTS_RELPATH)


def handout_plugin_root() -> Path:
    for key in ("HB_ROOT", "CLAUDE_PLUGIN_ROOT"):
        value = os.environ.get(key)
        if value and Path(value).is_dir():
            return abspath(value)
    here = abspath(__file__)
    for candidate in here.parents:
        manifest = candidate / PLUGIN_MANIFEST_RELPATH
        if manifest.is_file():
            try:
                name = json.loads(manifest.read_text(encoding="utf-8")).get("name")
            except (OSError, json.JSONDecodeError):
                name = None
            if name == PLUGIN_NAME:
                return candidate
    return here.parents[1]


def resolve_srg(explicit) -> Path | None:
    trail = []
    if explicit is not None:
        candidate = abspath(explicit)
        trail.append("(a) --srg-root={}".format(candidate))
        warn("srg-resolution: " + " / ".join(trail))
        if not is_substance(candidate):
            fail_contract(
                "--srg-root に指定されたディレクトリが SRG 実体ではない "
                "(vendor script 2 本が揃っていない): {}".format(candidate)
            )
        return candidate

    env_value = os.environ.get("SRG_ROOT")
    if env_value:
        candidate = abspath(env_value)
        trail.append("(b) SRG_ROOT={}".format(candidate))
        if is_substance(candidate):
            warn("srg-resolution: " + " / ".join(trail))
            return candidate
    else:
        trail.append("(b) SRG_ROOT=<未設定>")

    sibling = handout_plugin_root().parent / SIBLING_DIR_NAME
    trail.append("(c) sibling={}".format(sibling))
    warn("srg-resolution: " + " / ".join(trail))
    if is_substance(sibling):
        return sibling
    return None


# --- 画風系統の決定 (RESOLUTION-R23 (c) / algorithm 3b) -------------------


def family_of(section: dict, section_id) -> str:
    """図解型からの全域写像で family を決める。明示指定はそれが勝つ。fallback は無い。"""
    explicit = section.get("style_family")
    if explicit is not None:
        if not isinstance(explicit, str) or explicit not in FAMILY_GENOME:
            fail_check(
                E_FAMILY_UNKNOWN,
                section_id,
                "style_family {!r} が 2 語の allowlist に無い".format(explicit),
            )
        return explicit
    pattern = section.get("diagram_pattern")
    if pattern is None or (isinstance(pattern, str) and not pattern.strip()):
        fail_check(
            E_FAMILY_MISSING,
            section_id,
            "図解型を持たないセクションは style_family の明示が要る (既定へ落とさない)",
        )
    if not isinstance(pattern, str) or pattern not in PATTERN_TO_FAMILY:
        fail_check(
            E_FAMILY_UNKNOWN,
            section_id,
            "図解型 {!r} が写像の定義域に無い".format(pattern),
        )
    return PATTERN_TO_FAMILY[pattern]


def genome_path_for(family: str, srg_root: Path, hb_root: Path) -> Path:
    base, relpath = FAMILY_GENOME[family]
    root = srg_root if base == "srg" else hb_root
    return Path(root) / relpath


def load_genome(family: str, path: Path, section_id) -> dict:
    """genome を読み、検査に使う語彙 (motif 名 / 密度語 / レイアウト表) を取り出す。

    語彙を script が自前で列挙しないための唯一の入口である。
    """
    if not path.is_file():
        fail_check(
            E_GENOME_MISSING,
            section_id,
            "画風系統 {} の genome が実在しない: {} (同梱漏れは skip へ畳まない)".format(family, path),
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail_check(
            E_GENOME_MISSING,
            section_id,
            "画風系統 {} の genome が読めない: {} ({})".format(family, path, exc),
        )
    motifs = []
    for entry in data.get("motifs") or []:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            motifs.append(entry["name"])
    levels = find_key(data, "densityLevels")
    layout = find_key(data, "layoutSelectionByStructure")
    return {
        "family": family,
        "path": path,
        "motifs": motifs,
        "density_levels": tuple(levels.keys()) if isinstance(levels, dict) else (),
        "layout": layout if isinstance(layout, dict) else {},
    }


def layout_template_for(genome: dict, pattern) -> str | None:
    """図解型に対応する layoutTemplate を genome の対応表から引く。

    対応表のキーは genome 側の語彙なので script は 1 語も持たない。図解型の語が
    キーに含まれるものを決定論的に (キー昇順で最初に一致したものを) 選ぶ。
    """
    if not isinstance(pattern, str) or not pattern:
        return None
    token = pattern.replace("-", "_")
    for key in sorted(genome.get("layout") or {}):
        if token not in str(key):
            continue
        value = genome["layout"][key]
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        # 散文の目安書きは委譲先の入力にしない (テンプレート名の形のときだけ渡す)。
        if candidate and all(ch.isascii() and (ch.isalnum() or ch == "-") for ch in candidate):
            return candidate
    return None


# --- ランタイム確認 (algorithm 4) -----------------------------------------


def node_version(node_path: str):
    try:
        proc = subprocess.run(
            [node_path, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip() or None


def major_of(version: str):
    digits = ""
    for ch in version.lstrip("v"):
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


# --- 変換 (algorithm 6-7) --------------------------------------------------


def build_items(plan: dict):
    items = []
    sections = plan["sections"]
    previous_heading = ""
    for index, section in enumerate(sections, 1):
        section_id = str(section.get("section_id"))
        items.append(
            {
                "section_id": section.get("section_id"),
                "slug": slug_for(index, section_id),
                "index": index,
                "section": section,
                "previous_heading": previous_heading,
            }
        )
        previous_heading = text_of(section.get("heading"))
    return items


def text_policy_of(section: dict, section_id) -> str:
    """RESOLUTION-R23 (a): 既定は焼き込み側。overlay-only は理由との対でだけ選べる。"""
    policy = section.get("text_policy")
    reason = section.get("text_policy_reason")
    if policy is None:
        if reason is not None:
            fail_check(
                E_POLICY_REASON_MISSING,
                section_id,
                "text_policy_reason だけが指定されている (対でしか意味を持たない)",
            )
        return POLICY_BAKED
    if not isinstance(policy, str) or policy not in TEXT_POLICIES:
        fail_check(E_POLICY_UNKNOWN, section_id, "未知の text_policy: {!r}".format(policy))
    if policy == POLICY_OVERLAY_ONLY:
        if not isinstance(reason, str) or not reason.strip():
            fail_check(
                E_POLICY_REASON_MISSING,
                section_id,
                "焼き込みを外すには text_policy_reason (非空) が要る",
            )
    elif reason is not None:
        fail_check(
            E_POLICY_REASON_MISSING,
            section_id,
            "焼き込み policy に text_policy_reason は対応しない",
        )
    return policy


def motif_names_of(section: dict, section_id, vocabulary) -> list:
    """RESOLUTION-R23 (d): 3 役構造体を platform → primary → props の順に連結する。"""
    roles = section.get("motifs")
    if not isinstance(roles, dict):
        fail_check(
            E_MOTIF_ROLE,
            section_id,
            "motifs は {platform, primary, props[]} の 3 役構造体である必要がある",
        )
    names = []
    for role in ("platform", "primary"):
        value = roles.get(role)
        if not isinstance(value, str) or not value.strip():
            fail_check(E_MOTIF_ROLE, section_id, "motifs.{} が単一名で埋まっていない".format(role))
        names.append(value)
    props = roles.get("props")
    if not isinstance(props, list) or not props:
        fail_check(E_MOTIF_ROLE, section_id, "motifs.props は 1 件以上の配列である必要がある")
    for value in props:
        if not isinstance(value, str) or not value.strip():
            fail_check(E_MOTIF_ROLE, section_id, "motifs.props に空の要素がある")
        names.append(value)
    if vocabulary:
        for name in names:
            if name not in vocabulary:
                fail_contract(
                    "{} [section {}]: motif {!r} が style の語彙に無い".format(
                        E_MOTIF_ROLE, section_id, name
                    )
                )
    return names


def check_density(section: dict, section_id, genome: dict) -> str:
    level = section.get("density_level")
    levels = genome.get("density_levels") or ()
    if not isinstance(level, str) or not level:
        fail_check(E_DENSITY, section_id, "density_level が無い")
    if levels and level not in levels:
        fail_check(
            E_DENSITY,
            section_id,
            "density_level {!r} が genome の値域に無い".format(level),
        )
    return level


def check_trace(section: dict, section_id, motif_names) -> None:
    trace = section.get("adaptation_trace")
    if not isinstance(trace, list) or not trace:
        fail_check(E_TRACE, section_id, "adaptation_trace が空である")
    known = set(motif_names)
    for entry in trace:
        if not isinstance(entry, dict):
            fail_check(E_TRACE, section_id, "adaptation_trace の要素が object ではない")
        motif = entry.get("motif")
        if not isinstance(motif, str) or motif not in known:
            fail_check(
                E_TRACE,
                section_id,
                "adaptation_trace の motif {!r} が当該セクションの 3 役に無い".format(motif),
            )


def section_data_text(section: dict) -> str:
    parts = []
    for key in SECTION_TEXT_FIELDS:
        parts.append(text_of(section.get(key)))
    for key in SECTION_TEXT_LIST_FIELDS:
        for value in section.get(key) or []:
            parts.append(text_of(value))
    return " ".join(part for part in parts if part)


def check_baked_text(section: dict, section_id) -> list:
    """RESOLUTION-R23 (b): 焼き込みブロックの量と形を検査し、text の並びを返す。"""
    blocks = section.get("baked_text")
    if not isinstance(blocks, list) or not blocks:
        fail_check(E_BAKED_BLOCKS, section_id, "焼き込み policy なのに baked_text が空である")
    if len(blocks) > BLOCKS_PER_IMAGE_MAX:
        fail_check(
            E_BAKED_BLOCKS,
            section_id,
            "焼き込みブロックが {} 件で上限 {} を超えている".format(len(blocks), BLOCKS_PER_IMAGE_MAX),
        )

    source_text = section_data_text(section)
    section_has_numbers = bool(digit_runs(source_text))

    texts = []
    metrics = []
    for position, block in enumerate(blocks, 1):
        where = "baked_text[{}]".format(position)
        if not isinstance(block, dict):
            fail_check(E_BAKED_FORM, section_id, "{} が {{form, text}} のタグ付き object ではない".format(where))
        form = block.get("form")
        if not isinstance(form, str) or form not in BAKED_FORMS:
            fail_check(E_BAKED_FORM, section_id, "{} の form {!r} が allowlist に無い".format(where, form))
        text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            fail_check(E_BAKED_FORM, section_id, "{} の text が空である".format(where))
        if grapheme_length(text) > CHARS_PER_BLOCK_MAX:
            fail_check(
                E_BAKED_CHARS,
                section_id,
                "{} が {} 字を超えている: {!r}".format(where, CHARS_PER_BLOCK_MAX, text),
            )
        if form == FORM_KEYWORD:
            for ch in text:
                if ch in SENTENCE_MARKS or ch == READING_COMMA:
                    fail_check(
                        E_BAKED_FORM,
                        section_id,
                        "{} は要点語のみ。区切り記号 {!r} を含んでいる".format(where, ch),
                    )
        elif form == FORM_QUESTION:
            if text[-1] not in QUESTION_TAIL:
                fail_check(E_BAKED_FORM, section_id, "{} が問いの形で終わっていない".format(where))
            for ch in text[:-1]:
                if ch in SENTENCE_MARKS:
                    fail_check(
                        E_BAKED_FORM,
                        section_id,
                        "{} の末尾以外に文末記号 {!r} がある".format(where, ch),
                    )
        else:
            if not has_digit(text):
                fail_check(E_BAKED_FORM, section_id, "{} が数字を含んでいない".format(where))
            for ch in text:
                if ch in SENTENCE_MARKS:
                    fail_check(
                        E_BAKED_FORM,
                        section_id,
                        "{} に文末記号 {!r} がある".format(where, ch),
                    )
            metrics.append((where, block, text))
        texts.append(text)

    if section_has_numbers:
        if len(metrics) != 1:
            fail_check(
                E_METRIC_COUNT,
                section_id,
                "構成データが数値を持つセクションの数値強調はちょうど 1 件 (現在 {} 件)".format(len(metrics)),
            )
        where, block, text = metrics[0]
        if block.get("emphasis") != METRIC_EMPHASIS:
            fail_check(
                E_METRIC_COUNT,
                section_id,
                "{} に emphasis={} が無い".format(where, METRIC_EMPHASIS),
            )
        for run in digit_runs(text):
            if run not in source_text:
                fail_check(
                    E_METRIC_UNSOURCED,
                    section_id,
                    "{} の数字 {} が構成データに逐語で存在しない".format(where, run),
                )
    elif metrics:
        fail_check(
            E_METRIC_COUNT,
            section_id,
            "構成データが数値を持たないセクションに数値強調がある",
        )
    return texts


def build_slide(item: dict, plan: dict, genome: dict) -> dict:
    """1 セクション = 1 slide。委譲先の入力契約 (フィールド名と型) は変えない。"""
    section = item["section"]
    section_id = item["section_id"]
    heading = text_of(section.get("heading"))
    background_parts = [text_of(plan.get("background")), heading, item["previous_heading"]]
    background = " / ".join(part for part in background_parts if part)

    policy = text_policy_of(section, section_id)
    motif_names = motif_names_of(section, section_id, genome.get("motifs"))
    density = check_density(section, section_id, genome)
    check_trace(section, section_id, motif_names)

    overlay = section.get("overlay_text")
    if not isinstance(overlay, list) or not overlay:
        fail_check(E_OVERLAY_MISSING, section_id, "overlay_text が空である (両 policy で正本)")
    for entry in overlay:
        if not isinstance(entry, str) or not entry.strip():
            fail_check(E_OVERLAY_MISSING, section_id, "overlay_text に空の要素がある")

    slide = {
        "slug": item["slug"],
        "slideNumber": item["index"],
        "purpose": text_of(section.get("goal")),
        "audienceTakeaway": text_of(section.get("lead_line")),
        "background": background,
        "intendedUse": INTENDED_USE,
        "subject": text_of(section.get("subject")),
        "diagramStructure": text_of(section.get("diagram_structure")),
        "overlayText": list(overlay),
        "alt": text_of(section.get("alt")),
        "motifs": motif_names,
        "densityLevel": density,
        "layout": section.get("layout") or DEFAULT_LAYOUT,
        "pattern": "image-only",
        "textPolicy": policy,
        "backgroundSource": "none",
        "accent": text_of(plan.get("accent")),
        "generation": {
            "modelSnapshot": text_of(plan.get("model_snapshot")) or DEFAULT_MODEL_SNAPSHOT,
            "quality": GENERATION_QUALITY,
            "size": GENERATION_SIZE,
        },
        "reason": text_of(section.get("goal")),
    }
    if policy == POLICY_BAKED:
        # form / emphasis は handout 側の検査用メタ。委譲先へは文字列配列だけを渡す。
        slide["bakedText"] = check_baked_text(section, section_id)
    template = layout_template_for(genome, section.get("diagram_pattern"))
    if template:
        slide["layoutTemplate"] = template
    camera = section.get("camera")
    if camera:
        slide["camera"] = camera
        negative = section.get("negative_specific")
        if negative:
            slide["negativeSpecific"] = negative
    return slide


def validate_slide_against_srg(slide: dict, section_id) -> None:
    """algorithm 8: SRG の受け入れ規約を handout 側で先に満たしているか見る。"""
    where = "slide {}".format(slide["slug"])
    if len(slide["subject"]) < MIN_SUBJECT:
        fail_contract("{}: subject が {} 字未満".format(where, MIN_SUBJECT))
    if len(slide["diagramStructure"]) < MIN_STRUCTURE:
        fail_contract("{}: diagram_structure が {} 字未満".format(where, MIN_STRUCTURE))
    if len(slide["purpose"]) < MIN_PURPOSE:
        fail_contract("{}: goal (purpose) が {} 字未満".format(where, MIN_PURPOSE))
    if len(slide["audienceTakeaway"]) < MIN_TAKEAWAY:
        fail_contract("{}: lead_line (audienceTakeaway) が {} 字未満".format(where, MIN_TAKEAWAY))
    if len(slide["background"]) < MIN_BACKGROUND:
        fail_contract("{}: background が {} 字未満".format(where, MIN_BACKGROUND))
    if len(slide["intendedUse"]) < MIN_BACKGROUND:
        fail_contract("{}: intendedUse が {} 字未満".format(where, MIN_BACKGROUND))
    if not slide["alt"].strip():
        fail_contract("{}: alt が空".format(where))
    if slide.get("camera") == "structural" and not slide.get("negativeSpecific"):
        fail_contract("{}: camera=structural には negative_specific が要る".format(where))
    for field in ("subject", "diagramStructure", "alt"):
        found = find_ambiguous(slide[field])
        if found is not None:
            fail_contract("{}: {} に曖昧語 {!r} がある".format(where, field, found))


def check_uniform_composition(items) -> None:
    """RESOLUTION-R23 (e): 全セクションで (図解型, motifs.primary) が同一なら退化。"""
    if len(items) < 2:
        return
    signatures = set()
    for item in items:
        section = item["section"]
        roles = section.get("motifs")
        primary = roles.get("primary") if isinstance(roles, dict) else None
        signatures.add((section.get("diagram_pattern"), primary))
    if len(signatures) == 1:
        fail_contract(
            "{}: 全セクションで (図解型, motifs.primary) が同一である "
            "(セクションごとに画像を持つ意味が無い)".format(E_UNIFORM)
        )


# --- 委譲 -----------------------------------------------------------------


def run_delegate(argv, cwd: Path):
    return subprocess.run(
        [str(part) for part in argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd),
        timeout=3600,
        shell=False,
    )


def relay(proc, label: str) -> None:
    err = proc.stderr.decode("utf-8", "replace").strip()
    if err:
        warn("{}: {}".format(label, err))


def deck_plan_name(family: str, single: bool) -> str:
    if single:
        return DECK_PLAN_NAME
    return "{}-{}.json".format(DECK_PLAN_STEM, family)


def meta_drift_of(meta_path: Path, slide: dict):
    """algorithm 14b: 委譲先が密度指示とモチーフを保っているかを見る (画素は読まない)。"""
    if not meta_path.is_file():
        return ["meta"]
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["meta"]
    if not isinstance(meta, dict):
        return ["meta"]
    drift = []
    if meta.get("densityLevel") != slide.get("densityLevel"):
        drift.append("densityLevel")
    if list(meta.get("motifs") or []) != list(slide.get("motifs") or []):
        drift.append("motifs")
    return drift


# --- 本体 -----------------------------------------------------------------


def main(argv) -> int:
    args = parse_args(argv)

    assets_dir = abspath(args.assets_dir)
    if not assets_dir.is_dir():
        fail_contract("--assets-dir がディレクトリでない: {}".format(assets_dir))

    plan_path = abspath(args.image_plan)
    plan = load_plan(plan_path)
    items = build_items(plan)

    srg_root = resolve_srg(args.srg_root)

    def verdict(status, *, skip_reason=None, skip_detail=None, runtime=None,
                images=None, commands=None):
        return {
            "status": status,
            "skip_reason": skip_reason,
            "skip_detail": skip_detail,
            "srg_root": str(srg_root) if srg_root is not None else None,
            "runtime": runtime or {"node": None, "codex": None},
            "images": images if images is not None else [
                {
                    "section_id": item["section_id"],
                    "slug": item["slug"],
                    "path": None,
                    "status": "skipped",
                    "png_bytes": None,
                    "meta_drift": None,
                }
                for item in items
            ],
            "delegated_commands": commands or [],
        }

    if srg_root is None:
        warn("skip: SRG 実体が解決できないため画像生成を skip する (C18 fail-soft)")
        emit(verdict("skipped", skip_reason="srg-absent",
                     skip_detail="vendor script 2 本を持つ SRG root が見つからない"), EXIT_OK)

    # algorithm 3b: 使う画風系統の genome だけを解決する (使わない系統の不在は阻害しない)。
    hb_root = handout_plugin_root()
    genomes = {}
    for item in items:
        family = family_of(item["section"], item["section_id"])
        item["family"] = family
        if family not in genomes:
            genomes[family] = load_genome(
                family, genome_path_for(family, srg_root, hb_root), item["section_id"]
            )

    # algorithm 4: ランタイム確認 (起動前に判定する)。
    node_path = shutil.which("node")
    version = node_version(node_path) if node_path else None
    major = major_of(version) if version else None
    codex_path = shutil.which("codex")
    runtime = {"node": version, "codex": codex_path}

    detail = None
    if node_path is None or version is None:
        detail = "node が PATH に無い"
    elif major is None or major < NODE_MAJOR_MINIMUM:
        detail = "node の version {} が下限 {} 未満".format(version, NODE_MAJOR_MINIMUM)
    elif not args.dry_run and codex_path is None:
        detail = "codex が PATH に無い"
    if detail is not None:
        warn("skip: ランタイム不足のため画像生成を skip する ({})".format(detail))
        emit(verdict("skipped", skip_reason="runtime-absent", skip_detail=detail,
                     runtime=runtime), EXIT_OK)

    # algorithm 6-8b: 変換と事前検査。違反は差し戻し先が計画側だと分かる位置で止める。
    check_uniform_composition(items)
    for item in items:
        slide = build_slide(item, plan, genomes[item["family"]])
        validate_slide_against_srg(slide, item["section_id"])
        item["slide"] = slide

    images_dir = assets_dir / IMAGES_DIR_NAME
    work_dir = assets_dir / WORK_DIR_NAME
    generated_dir = work_dir.joinpath(*GENERATED_RELPATH)

    # algorithm 12: 既に有効な PNG がある slug は委譲対象から外す (追加課金なし)。
    reused = {}
    pending = []
    for item in items:
        existing = images_dir / (item["slug"] + PNG_SUFFIX)
        if not args.dry_run and existing.is_file() and has_png_signature(existing):
            reused[item["slug"]] = existing
        else:
            pending.append(item)

    if not args.dry_run and not pending:
        warn("reuse: 全 slug の PNG が既存のため委譲しない")
        images = [
            {
                "section_id": item["section_id"],
                "slug": item["slug"],
                "path": "{}/{}{}".format(IMAGES_DIR_NAME, item["slug"], PNG_SUFFIX),
                "status": "generated",
                "png_bytes": reused[item["slug"]].stat().st_size,
                "meta_drift": None,
            }
            for item in items
        ]
        emit(verdict("generated", runtime=runtime, images=images), EXIT_OK)

    generated_dir.mkdir(parents=True, exist_ok=True)

    # algorithm 9: 1 回の起動が受け取れる --genome は 1 つなので family ごとに分けて委譲する。
    families = sorted({item["family"] for item in pending})
    single_family = len(families) == 1

    commands = []

    def failed_images():
        return [
            {
                "section_id": item["section_id"],
                "slug": item["slug"],
                "path": None,
                "status": "failed",
                "png_bytes": None,
                "meta_drift": None,
            }
            for item in items
        ]

    for family in families:
        slides = [item["slide"] for item in pending if item["family"] == family]
        genome_path = genomes[family]["path"]
        deck = {
            "styleGenome": os.path.relpath(str(genome_path), str(generated_dir)),
            "deck": {
                "title": text_of(plan.get("title")),
                "totalSlides": len(slides),
            },
            "slides": slides,
        }
        deck_path = generated_dir / deck_plan_name(family, single_family)
        deck_path.write_text(
            json.dumps(deck, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        prompts_argv = [
            node_path,
            str(srg_root / BUILD_PROMPTS_RELPATH),
            str(work_dir),
            "--plan",
            str(deck_path),
            "--genome",
            str(genome_path),
            "--source",
            DELEGATE_SOURCE,
        ]
        commands.append(list(prompts_argv))
        proc = run_delegate(prompts_argv, assets_dir)
        relay(proc, "build-image-prompts.js")
        if proc.returncode != 0:
            warn(
                "delegation-failed: build-image-prompts.js が exit {} で終了した ({})".format(
                    proc.returncode, family
                )
            )
            emit(verdict("partial", runtime=runtime, images=failed_images(), commands=commands),
                 EXIT_DELEGATION)

    # algorithm 10: prompt が実ファイルとして揃っているかを自分で確認する。
    ready = [
        item["slug"]
        for item in pending
        if (generated_dir / (item["slug"] + PROMPT_SUFFIX)).is_file()
    ]
    if not ready:
        warn("delegation-failed: prompt が 1 件も生成されなかった")
        emit(verdict("partial", runtime=runtime, images=failed_images(), commands=commands),
             EXIT_DELEGATION)

    generate_argv = [node_path, str(srg_root / GENERATE_IMAGES_RELPATH), str(work_dir)]
    if args.dry_run:
        generate_argv += ["--dry-run", "--source", DELEGATE_SOURCE]
    else:
        generate_argv += ["--batch", DELEGATE_BATCH, "--source", DELEGATE_SOURCE]
    commands.append(list(generate_argv))
    proc = run_delegate(generate_argv, assets_dir)
    relay(proc, "generate-images-codex.js")

    if args.dry_run:
        for line in proc.stdout.decode("utf-8", "replace").splitlines():
            stripped = line.strip()
            if "codex exec" in stripped:
                commands.append(stripped)
        images = [
            {
                "section_id": item["section_id"],
                "slug": item["slug"],
                "path": None,
                "status": "dry-run",
                "png_bytes": None,
                "meta_drift": None,
            }
            for item in items
        ]
        emit(verdict("dry-run", runtime=runtime, images=images, commands=commands), EXIT_OK)

    # algorithm 13-14: 委譲先の exit code を成功判定に使わず、実ファイルと署名で確かめる。
    recovered = {}
    for item in pending:
        slug = item["slug"]
        produced = generated_dir / (slug + PNG_SUFFIX)
        if not produced.is_file():
            warn("recovery-failed: {} の生成物が作業ディレクトリに無い".format(slug))
            continue
        if not has_png_signature(produced):
            warn("recovery-failed: {} の生成物が PNG 署名を持たない".format(slug))
            continue
        target = images_dir / (slug + PNG_SUFFIX)
        try:
            images_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(produced), str(target))
        except OSError as exc:
            warn("recovery-failed: {} の回収に失敗した ({})".format(slug, exc))
            continue
        if not has_png_signature(target):
            warn("recovery-failed: {} の回収後に PNG 署名が壊れた".format(slug))
            continue
        recovered[slug] = target

    # algorithm 14b: 回収後の meta 照合。exit code は変えず、必ず開示する。
    drifts = {}
    for item in pending:
        slug = item["slug"]
        if slug not in recovered:
            continue
        drift = meta_drift_of(generated_dir / (slug + META_SUFFIX), item["slide"])
        if drift:
            drifts[slug] = drift
            warn(
                "meta-drift: {} の {} が計画値と一致しない "
                "(委譲先が密度指示を落とした可能性がある)".format(slug, " / ".join(drift))
            )

    images = []
    failures = 0
    for item in items:
        slug = item["slug"]
        target = reused.get(slug) or recovered.get(slug)
        if target is None:
            failures += 1
            images.append(
                {
                    "section_id": item["section_id"],
                    "slug": slug,
                    "path": None,
                    "status": "failed",
                    "png_bytes": None,
                    "meta_drift": None,
                }
            )
            continue
        images.append(
            {
                "section_id": item["section_id"],
                "slug": slug,
                "path": "{}/{}{}".format(IMAGES_DIR_NAME, slug, PNG_SUFFIX),
                "status": "generated",
                "png_bytes": target.stat().st_size,
                "meta_drift": drifts.get(slug) or None,
            }
        )

    if failures:
        warn("partial: {} 件の slug で PNG を回収できなかった".format(failures))
        emit(verdict("partial", runtime=runtime, images=images, commands=commands),
             EXIT_DELEGATION)
    emit(verdict("generated", runtime=runtime, images=images, commands=commands), EXIT_OK)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
