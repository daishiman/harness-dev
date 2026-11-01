#!/usr/bin/env python3
# /// script
# name: validate-qa-semantic-coverage
# purpose: feature が宣言する QA 要件の登録・goal・exact-13 task への意味伝播を検証する。
# inputs: imported Python API (staging/repo_root/parent/task_paths)
# outputs: QA semantic coverage violation tuples
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""C12 の QA semantic coverage 検査。

契約 version・JSON Schema・QA 意味伝播を一つの validator に詰め込まず、QA の
登録と意味被覆だけを担当する。呼び出し元は canonical task path を渡すため、この
module が phase/path の正本を複製することはない。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Sequence

QA_REF_PATTERN = re.compile(r"\bqa-\d{3}\b")
FRONTMATTER_TAGS = re.compile(r"^tags:[ \t]*(\[.*?\])[ \t]*$", re.MULTILINE)
GOAL_SPEC_COVERAGE_FIELDS = ("purpose", "goal", "scope_in", "scope_out", "acceptance")
QA_REQUIREMENT_HEADING = re.compile(
    r"【\d+\.\s*([^（(】]+?)(?:\s*[（(][^】]*[）)])?】"
)
SEMANTIC_COVERAGE_CONSTRAINT_ID = "semantic-coverage-not-tag-only"


def _frontmatter(text: str) -> str:
    """先頭 frontmatter だけを返し、本文中の tags: を宣言として扱わない。"""
    if not text.startswith("---"):
        return ""
    lines = text.splitlines()
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return ""


def _plain_file(root: Path, relative: str) -> bool:
    """staging 内の symlink 成分を辿らず、通常ファイルだけを対象にする。"""
    cursor = root
    for part in Path(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return False
    return (root / relative).is_file()


def _registered_qa(
    spec_state_path: Path,
    spec_state_rel: str,
) -> tuple[dict[str, dict], list[tuple[str, str, str]]]:
    if not spec_state_path.is_file():
        return {}, []
    try:
        spec_state = json.loads(spec_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, [("qa-ref-unregistered", spec_state_rel, "spec-state を JSON として読めない")]
    if not isinstance(spec_state, dict):
        return {}, [("qa-ref-unregistered", spec_state_rel, "spec-state の root は object 必須")]
    qa_log = spec_state.get("qa_log")
    if not isinstance(qa_log, list):
        return {}, [("qa-ref-unregistered", spec_state_rel, "spec-state.qa_log は array 必須")]
    registered = {
        str(entry["id"]): entry
        for entry in qa_log
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    return registered, []


def qa_semantic_violations(
    staging: Path,
    repo_root: Path,
    parent: str,
    task_paths: Sequence[str],
) -> list[tuple[str, str, str]]:
    """QA 宣言を登録・goal 意味被覆・exact-13 task trace の三軸で検証する。"""
    feature_md = repo_root / "features" / f"{parent}.md"
    if not parent or not feature_md.is_file():
        return []

    tags_match = FRONTMATTER_TAGS.search(
        _frontmatter(feature_md.read_text(encoding="utf-8", errors="replace"))
    )
    if tags_match is None:
        return []
    try:
        raw_tags = json.loads(tags_match.group(1))
    except json.JSONDecodeError:
        return [(
            "qa-tags-unparsable",
            f"features/{parent}.md",
            "frontmatter tags を JSON として読めない",
        )]
    if not isinstance(raw_tags, list):
        return [(
            "qa-tags-unparsable",
            f"features/{parent}.md",
            "frontmatter tags は array 必須",
        )]
    declared = list(dict.fromkeys(
        tag
        for tag in raw_tags
        if isinstance(tag, str) and QA_REF_PATTERN.fullmatch(tag)
    ))
    if not declared:
        return []

    errors: list[tuple[str, str, str]] = []
    spec_state_rel = Path("system-spec", "spec-state.json").as_posix()
    registered, spec_state_errors = _registered_qa(
        repo_root / "system-spec" / "spec-state.json",
        spec_state_rel,
    )
    errors.extend(spec_state_errors)

    goal_spec_path = staging / "goal-spec.json"
    goal_spec: dict = {}
    coverage_text = ""
    if goal_spec_path.is_file():
        try:
            loaded_goal_spec = json.loads(goal_spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append((
                "qa-semantic-coverage",
                "goal-spec.json",
                "goal-spec を JSON として読めない",
            ))
        else:
            if isinstance(loaded_goal_spec, dict):
                goal_spec = loaded_goal_spec
                coverage_text = json.dumps(
                    {key: goal_spec.get(key) for key in GOAL_SPEC_COVERAGE_FIELDS},
                    ensure_ascii=False,
                )
            else:
                errors.append((
                    "qa-semantic-coverage",
                    "goal-spec.json",
                    "goal-spec の root は object 必須",
                ))
    else:
        errors.append((
            "qa-semantic-coverage",
            "goal-spec.json",
            "qa 要件を宣言する feature の staging に goal-spec.json が無く被覆判定できない",
        ))

    semantic_qa_ids: set[str] = set()
    quality_constraints = goal_spec.get("quality_constraints", [])
    if isinstance(quality_constraints, list):
        for constraint in quality_constraints:
            if (
                isinstance(constraint, dict)
                and constraint.get("id") == SEMANTIC_COVERAGE_CONSTRAINT_ID
            ):
                constraint_refs = QA_REF_PATTERN.findall(
                    json.dumps(constraint, ensure_ascii=False)
                )
                semantic_qa_ids.update(constraint_refs or declared)

    task_texts = {
        relative: (staging / relative).read_text(encoding="utf-8", errors="replace")
        for relative in task_paths
        if _plain_file(staging, relative)
    }
    for qa_id in declared:
        if qa_id not in registered:
            errors.append((
                "qa-ref-unregistered",
                f"features/{parent}.md#tags",
                f"{qa_id} が {spec_state_rel} の qa_log に未登録 (系譜未接地)",
            ))
        if coverage_text and qa_id not in coverage_text:
            errors.append((
                "qa-semantic-coverage",
                "goal-spec.json",
                f"{qa_id} が purpose/goal/scope_in/scope_out/acceptance "
                "のいずれにも現れない (tag のみの宣言)",
            ))

        markers: list[str] = []
        if qa_id in semantic_qa_ids and qa_id in registered:
            answer = registered[qa_id].get("answer")
            if isinstance(answer, str):
                markers = list(dict.fromkeys(
                    marker.strip()
                    for marker in QA_REQUIREMENT_HEADING.findall(answer)
                    if marker.strip()
                ))
            if not markers:
                errors.append((
                    "qa-semantic-coverage",
                    f"{spec_state_rel}#qa_log[{qa_id}]",
                    f"{qa_id} は semantic coverage 対象だが確定回答から要件見出しを抽出できない",
                ))
            missing_goal = [marker for marker in markers if marker not in coverage_text]
            if missing_goal:
                errors.append((
                    "qa-semantic-coverage",
                    "goal-spec.json",
                    f"{qa_id} の意味要件が未反映: {', '.join(missing_goal)}",
                ))

        missing_paths = [relative for relative in task_paths if relative not in task_texts]
        if missing_paths:
            errors.append((
                "qa-task-trace",
                "task-specs/",
                f"{qa_id} の trace を検証できない task spec: {', '.join(missing_paths)}",
            ))
        missing_qa = [
            relative for relative, task_text in task_texts.items()
            if qa_id not in task_text
        ]
        if missing_qa:
            errors.append((
                "qa-task-trace",
                "task-specs/",
                f"{qa_id} が未伝播の task spec: {', '.join(missing_qa)}",
            ))
        semantic_gaps = {
            relative: [marker for marker in markers if marker not in task_text]
            for relative, task_text in task_texts.items()
        }
        semantic_gaps = {
            relative: gaps for relative, gaps in semantic_gaps.items() if gaps
        }
        if semantic_gaps:
            detail = "; ".join(
                f"{relative}: {', '.join(gaps)}"
                for relative, gaps in semantic_gaps.items()
            )
            errors.append((
                "qa-task-trace",
                "task-specs/",
                f"{qa_id} の意味要件が未伝播: {detail}",
            ))

    for qa_id in sorted(set(QA_REF_PATTERN.findall(coverage_text))):
        if qa_id not in registered:
            errors.append((
                "qa-ref-unregistered",
                "goal-spec.json",
                f"{qa_id} を本文が参照するが spec-state qa_log に未登録",
            ))
    return errors
