#!/usr/bin/env python3
# /// script
# name: resolve-brief-to-category
# purpose: Resolve skill-brief.json fields to resource-map categories deterministically.
# inputs:
#   - argv: --brief <skill-brief.json> --resource-map <resource-map.yaml>
# outputs:
#   - stdout: category-resolution JSON
#   - stderr: validation errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""resolve-brief-to-category.py

skill-brief.json の field 値から、参照すべき設計書 category を **決定論的** に解決する。
LLM 主観依存を排除し、再現性を担保するための写像スクリプト。

入力: skill-brief.json (path)
出力: JSON `{"categories": [...], "rationale": {...}, "read_first": [...]}`

使い方:
    python3 resolve-brief-to-category.py \
        --brief eval-log/skill-brief.json \
        --resource-map plugins/harness-creator/skills/run-build-skill/references/resource-map.yaml \
        > eval-log/category-resolution.json
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


# brief field -> 必ず引くべき category (固定写像)。
# kind や prefix から決定論的に最低限読むべき設計書セットを決める。
KIND_TO_REQUIRED_CATEGORIES: dict[str, list[str]] = {
    "ref": ["baseline-skill-build", "naming-classification", "progressive-disclosure", "reproducible-skill-writing", "complete-examples"],
    "run": ["baseline-skill-build", "layering-placement", "naming-classification", "evaluator-orchestration", "template-rendering", "complete-examples", "checklist-gates"],
    "assign": ["baseline-skill-build", "evaluator-orchestration", "naming-classification", "template-rendering", "complete-examples"],
    "wrap": ["baseline-skill-build", "naming-classification", "template-rendering", "complete-examples"],
    "delegate": ["baseline-skill-build", "layering-placement", "subagent-hook-integration", "agent-teams", "complete-examples"],
}

# brief の boolean / 配列 field が真なら追加する category。
CONDITIONAL_CATEGORIES: list[tuple[str, str]] = [
    ("needs_independent_context", "agent-teams"),
    ("needs_lifecycle_enforcement", "subagent-hook-integration"),
    ("with_subagent_hint", "agent-teams"),
    ("with_hooks", "subagent-hook-integration"),
]

# 障害対応が必要な状況（resume / fast / loop_exceeded など）
TROUBLESHOOTING_TRIGGERS = {"resume_from", "loop_exceeded", "fast_mode_override"}


def load_brief(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
    if value.isdigit():
        return int(value)
    if value in {"true", "false"}:
        return value == "true"
    return value.strip("\"'")


def load_resource_map(path: Path) -> dict[str, dict]:
    """Load the limited resource-map.yaml shape using only stdlib.

    Supported shape:
      resources:
        - category: name
          key: scalar
          list_key:
            - item
    """
    resources: list[dict] = []
    current: dict | None = None
    current_list_key: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped == "resources:":
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if ":" in item:
                if item.startswith("category:") or current is None:
                    current = {}
                    resources.append(current)
                key, value = item.split(":", 1)
                current[key.strip()] = _parse_scalar(value)
                current_list_key = None
            elif current is not None and current_list_key:
                current.setdefault(current_list_key, []).append(_parse_scalar(item))
            continue
        if current is None or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if value.strip():
            current[key] = _parse_scalar(value)
            current_list_key = None
        else:
            current[key] = []
            current_list_key = key

    return {entry["category"]: entry for entry in resources if "category" in entry}




def resolve(brief: dict, resource_map: dict[str, dict]) -> dict:
    rationale: dict[str, str] = {}
    categories: list[str] = []

    kind = brief.get("kind")
    if kind in KIND_TO_REQUIRED_CATEGORIES:
        for cat in KIND_TO_REQUIRED_CATEGORIES[kind]:
            if cat in resource_map and cat not in categories:
                categories.append(cat)
                rationale[cat] = f"kind={kind} requires {cat}"

    for flag, cat in CONDITIONAL_CATEGORIES:
        if brief.get(flag) and cat in resource_map and cat not in categories:
            categories.append(cat)
            rationale[cat] = f"brief.{flag}=true triggers {cat}"

    if any(k in brief for k in TROUBLESHOOTING_TRIGGERS):
        if "troubleshooting" in resource_map and "troubleshooting" not in categories:
            categories.append("troubleshooting")
            rationale["troubleshooting"] = "resume/fast/loop_exceeded context detected"

    # 優先順位ロジック（ベストプラクティス選定）:
    #   1. baseline-skill-build は **常に先頭**（基礎章を必ず最初に読む）
    #   2. troubleshooting は **常に末尾**（障害時のみ参照する性質のため）
    #   3. それ以外は match 順を保持（kind 必須 → conditional の論理順）
    #   4. hierarchy_level に応じた **doc budget** を適用:
    #        L0=4 docs, L1=7 docs, L2=10 docs（max_docs 合計でカットオフ）
    #   5. budget 超過時は **末尾側から drop**（先頭は基礎で必須、途中は kind 必須で重要）
    HEAD_CATEGORY = "baseline-skill-build"
    TAIL_CATEGORY = "troubleshooting"
    BUDGET_BY_LEVEL = {"L0": 4, "L1": 7, "L2": 10}

    head = [c for c in categories if c == HEAD_CATEGORY]
    tail = [c for c in categories if c == TAIL_CATEGORY]
    middle = [c for c in categories if c not in (HEAD_CATEGORY, TAIL_CATEGORY)]
    ordered = head + middle + tail

    level = str(brief.get("hierarchy_level", "L1")).upper()
    budget = BUDGET_BY_LEVEL.get(level, 7)

    sorted_categories: list[str] = []
    used_docs = 0
    for cat in ordered:
        cost = int(resource_map[cat].get("max_docs", 1) or 1)
        if used_docs + cost > budget and cat != HEAD_CATEGORY:
            rationale[cat] = rationale.get(cat, "") + f" [dropped: budget={budget} exceeded]"
            continue
        sorted_categories.append(cat)
        used_docs += cost
    rationale["_budget"] = f"hierarchy_level={level} budget={budget} used={used_docs}"

    read_first: list[str] = []
    for cat in sorted_categories:
        for doc in resource_map[cat].get("read_first", []):
            if doc not in read_first:
                read_first.append(doc)

    return {
        "categories": sorted_categories,
        "rationale": rationale,
        "read_first": read_first,
        "brief_fields_used": {
            "kind": kind,
            "needs_independent_context": brief.get("needs_independent_context"),
            "needs_lifecycle_enforcement": brief.get("needs_lifecycle_enforcement"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, type=Path)
    ap.add_argument("--resource-map", required=True, type=Path)
    args = ap.parse_args()

    brief = load_brief(args.brief)
    resource_map = load_resource_map(args.resource_map)

    result = resolve(brief, resource_map)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
