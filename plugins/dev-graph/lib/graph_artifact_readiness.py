"""C11 が artifact 本文の readiness を判定する部品 (import 専用 module)。

heading の有無 (`missing_required_headings`) と、見出しはあるが本文が template の既定文のまま
(`placeholder_sections`) を node 単位で返す。graph の妥当性 (valid) と node の readiness は
別の判定であり、この module は後者の材料だけを返す。どちらを violation に格上げするかは
`validate-graph-schema.py` の呼出し側が決める。
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import re
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import ContractError

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
ANGLE_PLACEHOLDER = re.compile(r"<[^>\n]+>")


def _markdown_shape(
    path: Path,
) -> tuple[list[str], list[str], list[tuple[int, int, str]]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContractError(f"cannot read artifact {path}: {exc}") from exc
    start = 0
    if lines and lines[0].strip() == "---":
        try:
            start = next(
                index + 1
                for index, line in enumerate(lines[1:], 1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise ContractError(f"artifact frontmatter is not terminated: {path}") from exc

    visible_lines = list(lines)
    headings: list[tuple[int, int, str]] = []
    fence: str | None = None
    for index in range(start, len(lines)):
        marker = lines[index].lstrip()[:3]
        if fence is not None:
            visible_lines[index] = ""
            if marker == fence:
                fence = None
            continue
        if marker in {"```", "~~~"}:
            visible_lines[index] = ""
            fence = marker
            continue
        match = HEADING.match(lines[index])
        if match:
            visible_lines[index] = ""
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    return lines, visible_lines, headings


def markdown_sections_of(
    path: Path, *, include_subsections: bool = False
) -> dict[str, str]:
    """Return ATX heading bodies without frontmatter, fences, or heading text."""
    lines, visible_lines, headings = _markdown_shape(path)
    sections: dict[str, str] = {}
    for offset, (index, level, title) in enumerate(headings):
        boundary = next(
            (
                candidate[0]
                for candidate in headings[offset + 1 :]
                if not include_subsections or candidate[1] <= level
            ),
            len(lines),
        )
        sections[title] = "\n".join(visible_lines[index + 1 : boundary]).strip()
    return sections


def _descendants_of(path: Path) -> dict[str, list[str]]:
    _, _, headings = _markdown_shape(path)
    descendants: dict[str, list[str]] = {}
    for offset, (_, level, title) in enumerate(headings):
        nested: list[str] = []
        for _, candidate_level, candidate_title in headings[offset + 1 :]:
            if candidate_level <= level:
                break
            nested.append(candidate_title)
        descendants[title] = nested
    return descendants


def _template_placeholders(
    kind: str, template_contract: dict[str, Any], template_root: Path
) -> dict[str, set[str]]:
    artifact_contract = (template_contract.get("artifacts") or {}).get(kind) or {}
    template = artifact_contract.get("template")
    if not isinstance(template, str):
        return {}
    sections = markdown_sections_of(template_root / template)
    sentinels = [
        token for token in template_contract.get("placeholder_tokens", []) if token != "<"
    ]
    return {
        section: set(ANGLE_PLACEHOLDER.findall(body))
        | {token for token in sentinels if token in body}
        for section, body in sections.items()
    }


def _matches_trigger_rule(rule: dict[str, Any], lineage: dict[str, Any]) -> bool:
    """Check one declarative trigger rule against a node's source_lineage.

    ``family`` 以外の key は全て lineage の同名 field への完全一致条件として扱う
    (AND 結合)。条件を 1 つも書かない rule は全 node に当たってしまうため無効にする。
    """
    conditions = {key: value for key, value in rule.items() if key != "family"}
    if not conditions:
        return False
    return all(lineage.get(key) == value for key, value in conditions.items())


def _conditional_trigger(
    kind: str, node: dict[str, Any] | None, artifact_contract: dict[str, Any] | None = None
) -> str | None:
    """Identify which conditional_required_sections family a node belongs to.

    2 系統ある。

    1. contract 宣言型 (``conditional_triggers``): source_lineage の field 一致で family を
       決める。system-spec-harness の import は kind だけでは見分けられない —
       同じ ``origin_kind`` から、compile 済み index (4 見出し) / requirements (U1-U9) /
       章 (architecture テンプレート準拠) の 3 形が出るため、origin_kind へ family を
       紐付けると章 import まで巻き添えで緩む。``source_path`` まで
       見て初めて形が一意に決まるので、条件は contract 側にデータとして置く。
    2. 既定の task 規則: system-dev-planner の task は origin_kind でしか見分けられない。
       frontmatter の template_id/template_version は全世代で同一 ("task"/"1.0.0") のままで、
       生成元テンプレートの世代 (軽量 3 見出しの baseline と標準 14 見出しが混在し、
       phase_ref は世代と相関しない) を区別する情報を持たない。
    """
    if not node:
        return None
    lineage = node.get("source_lineage") or {}
    if not isinstance(lineage, dict):
        lineage = {}

    triggers = (artifact_contract or {}).get("conditional_triggers")
    if isinstance(triggers, list):
        for rule in triggers:
            if not isinstance(rule, dict):
                continue
            family = rule.get("family")
            if isinstance(family, str) and _matches_trigger_rule(rule, lineage):
                return family

    if kind == "task" and lineage.get("origin_kind") == "system-dev-planner":
        return "system_development"
    return None


def _required_section_variants(
    kind: str,
    node: dict[str, Any] | None,
    artifact_contract: dict[str, Any],
) -> list[list[str]]:
    """Enumerate the acceptable required-section sets for one node.

    base (テンプレート完全準拠) は常に variant として残す。conditional 側だけに絞ると、
    「full template に完全準拠しているのに family の軽量版と一致しないので違反」という
    到達しえない判定が生まれる。full 準拠は定義上どの family より厳しい。
    """
    base = artifact_contract.get("required_sections") or []
    base_variant = [base] if isinstance(base, list) else []
    conditional = artifact_contract.get("conditional_required_sections") or {}
    trigger = _conditional_trigger(kind, node, artifact_contract)
    if trigger is None or not isinstance(conditional, dict):
        return base_variant
    variants = [
        sections
        for name, sections in conditional.items()
        if isinstance(sections, list) and (name == trigger or name.startswith(f"{trigger}_"))
    ]
    return variants + base_variant if variants else base_variant


def missing_required_headings(
    artifact: Path,
    kind: str,
    template_contract: dict[str, Any],
    node: dict[str, Any] | None = None,
) -> list[str]:
    """List required sections whose heading is entirely absent from the body.

    Distinct from placeholder_sections: that function only inspects headings
    that already exist. A required heading that was never written (e.g. a
    template revision adds a section an older artifact predates) is invisible
    to placeholder_sections because it never enters `sections`/`direct_invalid`.

    ``node`` を渡すと、conditional_required_sections に登録された代替 section 集合
    (例: system-dev-planner の複数テンプレート世代) のうち、実体と最も一致する
    variant で判定する。1 つでも完全一致すれば missing なしとして扱う (fail-closed
    ではなく既知の正当な世代差を許容する側へ倒す)。
    """
    artifact_contract = (template_contract.get("artifacts") or {}).get(kind) or {}
    variants = _required_section_variants(kind, node, artifact_contract)
    if not variants:
        return []
    present = set(markdown_sections_of(artifact))
    best: list[str] | None = None
    for required in variants:
        missing = sorted(section for section in required if section not in present)
        if not missing:
            return []
        if best is None or len(missing) < len(best):
            best = missing
    return best or []


def placeholder_sections(
    artifact: Path,
    kind: str,
    template_contract: dict[str, Any],
    template_root: Path,
) -> list[str]:
    """List present required sections that contain no substantive prose."""
    artifact_contract = (template_contract.get("artifacts") or {}).get(kind) or {}
    required = artifact_contract.get("required_sections") or []
    if not isinstance(required, list):
        return []

    sections = markdown_sections_of(artifact)
    descendants = _descendants_of(artifact)
    markers = _template_placeholders(kind, template_contract, template_root)
    sentinels = [
        token for token in template_contract.get("placeholder_tokens", []) if token != "<"
    ]
    direct_invalid: dict[str, bool] = {}
    for section, body in sections.items():
        scalar = re.sub(r"[\s`*_>#\-\[\]():.]+", "", body)
        sentinel_only = any(scalar.casefold() == token.casefold() for token in sentinels)
        direct_invalid[section] = (
            not body
            or any(marker in body for marker in markers.get(section, set()))
            or sentinel_only
        )

    def substantive(section: str) -> bool:
        if not direct_invalid.get(section, True):
            return True
        if sections.get(section):
            return False
        return any(
            substantive(child)
            for child in descendants.get(section, [])
        )

    return sorted(
        section
        for section in required
        if section in direct_invalid and not substantive(section)
    )
