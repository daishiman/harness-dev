#!/usr/bin/env python3
# /// script
# name: validate-task-spec-contract
# purpose: C12 が package へ適用する契約 version を解決し task spec 本文を当該契約で検証する。
# inputs: argv なし (validate-system-plan.py から読み込まれる library module)
# outputs: 呼び出し側への戻り値のみ (stdout 出力なし)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [../assets/validation-contract-baseline.json]
# requires-python: ">=3.10"
# ///
"""C12 契約 version の正本。

promote 済み package は content-addressed で digest 不変のため、後から強化された契約を
満たすよう修正できない。修正すれば digest が変わり `published_digest` を記録済みの receipt が
偽になる。そこで validator 側が契約 version を持ち、各 package を **promote 時点で妥当だった
契約** で再検証する。この module はその version 定義・台帳解決・version 差のある本文検査を
`validate-system-plan.py` から分離して保持する (契約 version 管理という責務境界の維持)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT_BASELINE_ASSET = HERE.parent / "assets" / "validation-contract-baseline.json"

TASK_SPEC_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
P01_ENTRY_GATE_MARKER = "parent_feature.depends_on all done|closed"
METHODOLOGY_MARKER = "system-task-goal-seek/v1"
GOAL_SEEK_PASS_MARKER = "rubric verdict=PASS"
P13_WRITEBACK_MARKER = "P13 spec/architecture writeback: required"
GOAL_SEEK_SECTION = "Inner goal-seek execution loop"
REQUIRED_TASK_SPEC_SECTIONS = (
    "Machine-readable registration fields",
    "目的",
    "背景",
    "前提条件",
    "Workstream applicability",
    "Architecture and deploy unit",
    "成果物",
    "Tracker publication and completion",
    "Branch and worktree execution",
    "スコープ外",
    "Verification and evidence",
    GOAL_SEEK_SECTION,
    "Rollout and rollback",
    "Handoff",
    "参照情報",
)

# --- テスト戦略 section (qa-076 / qa-078 / qa-079 / qa-081) ---------------
TEST_STRATEGY_SECTION = "テスト戦略"
TEST_STRATEGY_ITEMS: tuple[tuple[str, str], ...] = (
    ("テストレベル選定", "test_levels"),
    ("カバレッジ目標", "coverage_target"),
    ("層別方針", "layer_policies"),
    ("保守性制約", "maintainability_constraints"),
)
TEST_STRATEGY_SCHEMA = "task-spec-test-strategy.schema.json"
TEST_STRATEGY_PLACEMENT = ("スコープ外", "Verification and evidence")
WORKSTREAM_SECTION = "Workstream applicability"
LAYER_BY_WORKSTREAM = {
    "Frontend": "frontend",
    "Backend": "backend",
    "API": "backend",
    "Data": "backend",
    "Infrastructure": "infrastructure",
}
LAYER_MARKERS = {
    "frontend": ("behavior",),
    "backend": ("API 契約", "DB 結合"),
    "infrastructure": ("IaC", "smoke"),
}
_ITEM_LABEL = re.compile(
    r"^[ \t]*[-*][ \t]*(" + "|".join(re.escape(label) for label, _ in TEST_STRATEGY_ITEMS) + r")[ \t]*[:：]",
    re.MULTILINE,
)
_WORKSTREAM_LINE = re.compile(
    r"^[ \t]*[-*][ \t]*([^:：]+?)[ \t]*[:：][ \t]*(.*)$",
    re.MULTILINE,
)

# --- 世代非依存 rerun command (HarnessHub-ji8y) --------------------------
RERUN_SCRIPT = "validate-system-plan.py"
# fenced block と inline code span だけを「実行されるコマンド」とみなす。
_FENCE_OPEN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*$")
_INLINE_CODE = re.compile(r"`+([^`\n]+)`+")
_LINE_CONTINUATION = re.compile(r"\\\n[ \t]*")
_STAGING_FLAG = re.compile(r"(?<![\w-])--staging(?![\w-])")
_FEATURE_PACKAGE_FLAG = re.compile(r"(?<![\w-])--feature-package[= \t]+[\"']?([^\s`\"']+)")

CONTRACT_VERSION_LATEST = "1.3.0"
# テスト戦略 section と qa semantic coverage は並行ブランチで同じ 1.2.0 として
# 導入されたため、統合後の 1.2.0 は両方を必須にする。
TEST_STRATEGY_CONTRACT_FROM = "1.2.0"
RERUN_COMMAND_CONTRACT_FROM = "1.3.0"
CONTRACT_VERSIONS: dict[str, dict] = {
    # 2026-07-22T13:53:21Z (367ba5c) 以前に promote された content-addressed package が
    # 準拠していた検査集合。digest 不変ゆえ後追い修正できないため、当時の契約で再検証する。
    "1.0.0": {
        "required_sections": tuple(s for s in REQUIRED_TASK_SPEC_SECTIONS if s != GOAL_SEEK_SECTION),
        "inner_goal_seek": False,
        "p13_writeback": False,
        "test_strategy": False,
        "qa_semantic_coverage": False,
        "rerun_command": False,
    },
    # 367ba5c で導入された task-spec 本文契約。qa semantic coverage gate の導入前に
    # promote された package を再検証できるよう、当時の検査集合を独立 version として残す。
    "1.1.0": {
        "required_sections": REQUIRED_TASK_SPEC_SECTIONS,
        "inner_goal_seek": True,
        "p13_writeback": True,
        "test_strategy": False,
        "qa_semantic_coverage": False,
        "rerun_command": False,
    },
    # テスト戦略必須化と qa-071 enforcement tooling 導入後の契約。新規生成
    # package はテスト戦略 4 項目に加え、feature tag、spec-state lineage、
    # goal-spec の意味被覆、exact-13 task trace も fail-closed で検証する。
    "1.2.0": {
        "required_sections": REQUIRED_TASK_SPEC_SECTIONS,
        "inner_goal_seek": True,
        "p13_writeback": True,
        "test_strategy": True,
        "qa_semantic_coverage": True,
        "rerun_command": False,
    },
    # 世代非依存 rerun command を必須化した現行契約 (HarnessHub-ji8y)。task spec 本文が
    # validate-system-plan を呼ぶ場合、promotion の atomic rename で消滅する --staging では
    # なく --feature-package <自 package> を要求する。1.2.0 以前は task spec 本文が
    # `--staging .` を書いたまま promote 済みで digest 不変ゆえ修正できないため免除する。
    "1.3.0": {
        "required_sections": REQUIRED_TASK_SPEC_SECTIONS,
        "inner_goal_seek": True,
        "p13_writeback": True,
        "test_strategy": True,
        "qa_semantic_coverage": True,
        "rerun_command": True,
    },
}


def _task_spec_sections(text: str) -> list[tuple[str, str]]:
    """`## ` 見出しを (見出し名, 本文) の出現順リストへ写す。"""
    headings = list(TASK_SPEC_HEADING.finditer(text))
    sections: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections.append((heading.group(1).strip(), text[heading.end():end]))
    return sections


def parse_test_strategy(text: str) -> tuple[dict | None, list[tuple[str, str]]]:
    """`## テスト戦略` を schema 検査可能な中間表現へ写す。"""
    sections = _task_spec_sections(text)
    names = [name for name, _ in sections]
    indices = [i for i, name in enumerate(names) if name == TEST_STRATEGY_SECTION]
    if not indices:
        return None, []
    if len(indices) > 1:
        return None, [("task-spec-test-strategy-duplicate", f"{len(indices)} occurrences")]

    index = indices[0]
    errors: list[tuple[str, str]] = []
    before, after = TEST_STRATEGY_PLACEMENT
    if before in names and after in names and not names.index(before) < index < names.index(after):
        errors.append(("task-spec-test-strategy-placement", f"must sit between `{before}` and `{after}`"))

    body = sections[index][1]
    if not body.strip():
        errors.append(("task-spec-test-strategy-empty", TEST_STRATEGY_SECTION))
        return None, errors

    matches = list(_ITEM_LABEL.finditer(body))
    found = [match.group(1) for match in matches]
    canonical = [label for label, _ in TEST_STRATEGY_ITEMS]
    missing = [label for label in canonical if label not in found]
    for label in missing:
        errors.append(("task-spec-test-strategy-item-missing", label))
    if not missing and found != canonical:
        errors.append(("task-spec-test-strategy-item-order", f"expected={canonical} actual={found}"))

    keys = dict(TEST_STRATEGY_ITEMS)
    value: dict = {"schema_version": "1.0.0"}
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(body)
        item = body[match.end():end].strip()
        if not item:
            errors.append(("task-spec-test-strategy-item-empty", match.group(1)))
            continue
        value.setdefault(keys[match.group(1)], item)
    return value, errors


def derive_required_layers(text: str) -> list[str]:
    """Workstream applicability の applicable 宣言から必須テスト層を導出する。"""
    body = dict(_task_spec_sections(text)).get(WORKSTREAM_SECTION)
    if body is None:
        return []
    applicable: set[str] = set()
    for match in _WORKSTREAM_LINE.finditer(body):
        layer = LAYER_BY_WORKSTREAM.get(match.group(1).strip())
        if layer is None or re.match(r"n/?a\b", match.group(2).strip(), re.I):
            continue
        applicable.add(layer)
    return [layer for layer in ("frontend", "backend", "infrastructure") if layer in applicable]


def load_contract_baseline(path: Path = CONTRACT_BASELINE_ASSET) -> dict[str, str]:
    """promote 済み package の canonical digest -> 当時の契約 version を読み出す。

    asset が欠落・破損していても例外を投げず空写像を返す。呼び出し側は未知 digest を
    最新契約で検証するため、配布漏れは「免除なし = より厳格」へ倒れて fail-closed が保たれる。
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = document.get("packages") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        return {}
    baseline: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        digest, version = entry.get("canonical_digest"), entry.get("contract_version")
        if isinstance(digest, str) and version in CONTRACT_VERSIONS:
            baseline[digest] = version
    return baseline


def resolve_contract_version(canonical_digest: str | None, baseline: dict[str, str]) -> str:
    """検証対象 package へ適用する契約 version を決める。

    canonical_digest は staging-manifest.json の申告値ではなく実ファイル群から再計算した
    値が渡される。manifest は digest 対象外で改ざん可能なため、申告値で免除を決めてはならない。

    免除は「内容が暗号学的に確定した既 promote package」にのみ与える。digest を計算できない
    対象と台帳未登録の digest は最新契約へ倒し、台帳の欠落や削除が緩和経路にならないようにする。
    """
    if canonical_digest is None:
        return CONTRACT_VERSION_LATEST
    return baseline.get(canonical_digest, CONTRACT_VERSION_LATEST)


def task_spec_violations(text: str, required_sections: tuple[str, ...] = REQUIRED_TASK_SPEC_SECTIONS) -> list[tuple[str, str]]:
    """Return structural violations against the canonical task overlay.

    The template's prose says every standard section must be populated and
    names seven sections as the minimum readiness gate.  Treating all standard
    sections as required keeps C12 fail-closed and prevents a title plus one
    sentence from being promoted as an executable task specification.

    required_sections は適用契約 version が決める。version 間で差があるのは節の集合そのもの
    であり、違反 code 単位で免除すると他節の欠落まで見逃す fail-open になる。
    """
    headings = list(TASK_SPEC_HEADING.finditer(text))
    by_name: dict[str, list[int]] = {}
    for index, heading in enumerate(headings):
        by_name.setdefault(heading.group(1).strip(), []).append(index)

    errors: list[tuple[str, str]] = []
    for name in required_sections:
        occurrences = by_name.get(name, [])
        if not occurrences:
            errors.append(("task-spec-section-missing", name))
            continue
        if len(occurrences) > 1:
            errors.append(("task-spec-section-duplicate", name))
            continue
        heading_index = occurrences[0]
        start = headings[heading_index].end()
        end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        if not body:
            errors.append(("task-spec-section-empty", name))
    return errors


def _split_fenced_blocks(text: str) -> tuple[list[str], str]:
    """CommonMark の backtick/tilde fence を本文と外側テキストへ分ける。"""
    blocks: list[str] = []
    outside: list[str] = []
    body: list[str] | None = None
    fence_char = ""
    fence_length = 0
    for line in text.splitlines():
        if body is None:
            opening = _FENCE_OPEN.match(line)
            if opening is None:
                outside.append(line)
                continue
            marker = opening.group(1)
            fence_char, fence_length = marker[0], len(marker)
            body = []
            outside.append("")
            continue
        closing = re.fullmatch(
            rf"[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
            line,
        )
        if closing is None:
            body.append(line)
            continue
        blocks.append("\n".join(body))
        body = None
    # CommonMark では閉じ fence が無い場合も EOF まで code block として扱う。
    if body is not None:
        blocks.append("\n".join(body))
    return blocks, "\n".join(outside)


def _command_lines(text: str) -> list[str]:
    """Markdown が「実行するコマンド」として提示している断片だけを取り出す。

    散文中の script 名への言及 (「validate-system-plan.py 実行時に --repo-root を明示する」)
    までコマンド扱いすると、運用説明を書いただけで fail-closed になる。実際に promote 済みの
    package がその形の説明文を持っているため、fenced block と inline code span に絞る。
    fenced block 内の `\\` 継続行は 1 コマンドへ畳んでから行単位へ分解する。
    """
    commands: list[str] = []
    blocks, outside = _split_fenced_blocks(text)
    for block in blocks:
        commands.extend(_LINE_CONTINUATION.sub(" ", block).splitlines())
    # fenced block を除いた残りから inline code を拾う (同じ断片を二重に数えない)。
    commands.extend(match.group(1) for match in _INLINE_CODE.finditer(outside))
    return [command.strip() for command in commands if command.strip()]


def rerun_command_violations(text: str, package_id: str | None = None) -> list[tuple[str, str]]:
    """task spec が書く validate-system-plan 再実行コマンドが解決可能かを検証する。

    promotion は staging generation を content-addressed path へ atomic rename するため、
    `--staging .` は promotion 後に指す先が無く、記載どおり実行すると必ず失敗する
    (`references/feature-execution-package-contract.md` §2.3)。generation id の直書きも
    再計画のたびに stale になる。したがって feature 別 current pointer から現行世代を
    解決する `--feature-package <自 package>` だけを正本形式として受理する。

    package_id を渡すと、他 package の id をコピーした再実行 (別 package を検証して
    緑になる fail-open) も拒否する。
    """
    errors: list[tuple[str, str]] = []
    for command in _command_lines(text):
        if RERUN_SCRIPT not in command:
            continue
        if _STAGING_FLAG.search(command):
            errors.append((
                "task-spec-rerun-staging-path",
                f"--staging は promotion の atomic rename 後に解決できない: {command}",
            ))
            continue
        found = _FEATURE_PACKAGE_FLAG.search(command)
        if found is None:
            errors.append((
                "task-spec-rerun-package-missing",
                f"世代非依存の `--feature-package <feature_package_id>` が必要: {command}",
            ))
        elif package_id is not None and found.group(1) != package_id:
            errors.append((
                "task-spec-rerun-package-mismatch",
                f"expected={package_id} actual={found.group(1)}",
            ))
    return errors
