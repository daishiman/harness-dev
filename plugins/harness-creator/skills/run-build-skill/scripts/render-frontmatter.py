#!/usr/bin/env python3
# /// script
# name: render-frontmatter
# purpose: Render a SKILL.md template by substituting brief and CLI variables.
# inputs:
#   - argv: --name, --kind, --template, --brief
# outputs:
#   - stdout: rendered SKILL.md
#   - stderr: validation errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Render a skill template by substituting {{var}} placeholders.

Usage: render-frontmatter.py --name <skill-name> --kind <kind> --template <path>
Prints rendered SKILL.md to stdout.
"""
from __future__ import annotations
import argparse
import datetime
import json
import re
import sys
from pathlib import Path


def _import_feedback_contract_ssot():
    """repo-root scripts/feedback_contract_ssot.py を探して import (SSOT 単一正本)。

    本ファイルは深い階層に置かれるため、親を遡って scripts/feedback_contract_ssot.py
    を持つディレクトリを repo-root とみなす (派生配備でも resolve 後の実体から辿る)。
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "scripts" / "feedback_contract_ssot.py"
        if cand.is_file():
            sys.path.insert(0, str(parent / "scripts"))
            import feedback_contract_ssot as fc_mod  # noqa: E402

            return fc_mod
    raise ModuleNotFoundError(
        "feedback_contract_ssot.py not found in any parent scripts/ dir"
    )


FC = _import_feedback_contract_ssot()

OS_PREAMBLE = "!`uname -s 2>/dev/null || ver`"
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_-]+)(?:\s*\|\s*default\(([^)]*)\))?\s*\}\}")


def _normalize_value(value: object) -> str:
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(str(item) for item in value) + "]"
    if value is None:
        return ""
    return str(value)


def _feedback_contract_mapping(data: dict[str, object]) -> dict[str, object]:
    """Return flat template vars for generated per-skill feedback criteria.

    The source of truth is brief.feedback_contract.criteria when present. When
    a brief does not provide concrete criteria yet, keep the generated SKILL.md
    fail-closed by deriving a minimal inner/outer pair from the goal/checklist
    context instead of leaving placeholders unresolved.
    """
    skill_name = str(data.get("skill_name") or data.get("name") or "this-skill")
    goal = str(data.get("goal") or data.get("output_contract") or skill_name).strip()
    checks = data.get("deterministic_checks") or []
    # fallback 文面の正本は repo-root scripts/feedback_contract_ssot.py
    # (fallback_inner_text / fallback_outer_text)。直書きせず SSOT を呼ぶことで
    # drift を構造的に排除する。値一致は tests/test_feedback_contract_parity.py が
    # 固定し、is_fallback_text が lint で残存を検出する。
    if isinstance(checks, list) and checks:
        inner = " / ".join(str(item).strip() for item in checks if str(item).strip())
    else:
        inner = FC.fallback_inner_text(skill_name)
    outer = FC.fallback_outer_text(goal)

    max_iterations: object = 3
    fc = data.get("feedback_contract")
    if isinstance(fc, dict):
        max_iterations = fc.get("max_iterations") or max_iterations
        criteria = fc.get("criteria")
        if isinstance(criteria, list):
            for item in criteria:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                scope = str(item.get("loop_scope", "")).strip().lower()
                if scope == "inner" and text:
                    inner = text
                elif scope == "outer" and text:
                    outer = text
    return {
        "feedback_contract_max_iterations": max_iterations,
        "feedback_contract_inner_criteria_text": inner,
        "feedback_contract_outer_criteria_text": outer,
    }


def _parse_default(raw: str | None) -> str:
    if raw is None:
        return ""
    val = raw.strip()
    if val in {"[]", "{}"}:
        return val
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    return val


def render(template: str, mapping: dict[str, object]) -> str:
    """Render {{var}} and {{var | default("...")}} placeholders.

    The templates are intentionally tiny, so a constrained renderer is safer
    than introducing Jinja/PyYAML dependencies and violating doc/22 no-deps.
    """

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = mapping.get(key)
        if value in (None, "", []):
            return _parse_default(match.group(2))
        return _normalize_value(value)

    return PLACEHOLDER_RE.sub(repl, template)


def is_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def apply_dynamic_context_contract(content: str, mapping: dict[str, object]) -> str:
    """Apply 14章 OS preamble contract from brief fields to rendered SKILL.md."""
    needs_preamble = is_true(mapping.get("cross_platform")) or is_true(
        mapping.get("os_preamble_required")
    )
    if not needs_preamble:
        return content

    if not content.startswith("---"):
        return f"{OS_PREAMBLE}\n\n{content}"

    end = content.find("---", 3)
    if end == -1:
        return f"{OS_PREAMBLE}\n\n{content}"

    frontmatter = content[: end + 3]
    body = content[end + 3 :]
    additions = []
    if "\ncross_platform:" not in frontmatter:
        additions.append("cross_platform: true")
    if "\nos_preamble_required:" not in frontmatter:
        additions.append("os_preamble_required: true")
    if additions:
        frontmatter = frontmatter[:-3] + "\n" + "\n".join(additions) + "\n---"

    if OS_PREAMBLE not in body.splitlines()[:30]:
        fallback = (
            f"{OS_PREAMBLE}\n\n"
            '<important if="os=unknown">\n'
            "OS 判定に失敗した。ユーザーに macOS / Linux / Windows のいずれかを確認してから続行する。\n"
            "</important>\n\n"
        )
        body = "\n\n" + fallback + body.lstrip("\n")
    return frontmatter + body


def brief_mapping(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    triggers = data.get("trigger_conditions") or []
    key_constraints = data.get("key_constraints") or []
    add_res = data.get("additional_resources") or []
    add_res_lines = []
    for item in add_res:
        if isinstance(item, dict):
            p = item.get("path", "").strip()
            w = item.get("when_to_read", "").strip()
            if p:
                add_res_lines.append(f"- `{p}`: {w}" if w else f"- `{p}`")
    deterministic_checks = data.get("deterministic_checks") or []
    placement_candidates = data.get("placement_candidates") or []
    pattern_refs = data.get("pattern_refs") or []
    variant_axes = data.get("variant_axes") or []
    reuse_targets = data.get("reuse_targets") or []
    hook_events = data.get("hook_events") or []
    abstraction_variables = data.get("abstraction_variables") or []
    template_inputs = data.get("template_inputs") or []
    template_non_goals = data.get("template_non_goals") or []
    mapping = {
        "name": data.get("skill_name", ""),
        "skill_name": data.get("skill_name", ""),
        "kind": data.get("kind") or data.get("prefix", ""),
        "topic": data.get("skill_name", ""),
        "verb": data.get("verb", "実行する"),
        "object": data.get("object", data.get("skill_name", "ワークフロー")),
        "trigger1": triggers[0] if len(triggers) >= 1 else "ユーザーが依頼した",
        "trigger2": triggers[1] if len(triggers) >= 2 else "ワークフローで必要になった",
        "trigger3": triggers[2] if len(triggers) >= 3 else "",
        "output_contract": data.get("output_contract", "未設定。briefで出力契約を指定する。"),
        "boundary": data.get("boundary", "未設定。briefで非責務を指定する。"),
        "key_constraints": "\n".join(f"{i + 1}. {item}" for i, item in enumerate(key_constraints)) or "1. 未設定。briefで制約を指定する。",
        "role_suffix": data.get("role_suffix") or "none",
        "hierarchy_level": data.get("hierarchy_level") or "L1",
        "rubric_refs": data.get("rubric_refs") or [],
        "pattern_refs": pattern_refs,
        "pattern_intent": data.get("pattern_intent") or "none: 特殊パターンを採用しない",
        "variant_axes": variant_axes,
        "reuse_targets": reuse_targets,
        "deterministic_checks": deterministic_checks,
        "placement_candidates": placement_candidates,
        "hook_events": hook_events,
        "base_skill": data.get("base_skill") or "none",
        "delegate_agent": data.get("delegate_agent") or "none",
        "source_url_or_path": data.get("source_url_or_path")
        or data.get("source")
        or "internal",
        "source_tier": data.get("source_tier")
        or data.get("source-tier")
        or "internal",
        "last_audited_date": data.get("last_audited_date")
        or data.get("last-audited")
        or datetime.date.today().isoformat(),
        "audit_trigger": data.get("audit_trigger")
        or data.get("audit-trigger")
        or "quarterly",
        "cross_platform": str(bool(data.get("cross_platform", False))).lower(),
        "os_preamble_required": str(
            bool(data.get("os_preamble_required", data.get("cross_platform", False)))
        ).lower(),
        "additional_resources": "\n".join(add_res_lines),
        "output_language": data.get("output_language") or "ja",
        "parameter_language_exception": str(
            bool(data.get("parameter_language_exception", True))
        ).lower(),
        "abstraction_variables": abstraction_variables,
        "template_inputs": template_inputs,
        "template_non_goals": template_non_goals,
        "mass_production_profile": data.get("mass_production_profile") or "standard",
        "generated_steps": _generated_steps(
            deterministic_checks,
            placement_candidates,
            pattern_refs,
            hook_events,
        ),
        "generated_checks": _generated_checks(deterministic_checks, reuse_targets),
        "generated_gotchas": _generated_gotchas(pattern_refs, variant_axes),
        "variable_contract": _variable_contract(
            abstraction_variables,
            template_inputs,
            template_non_goals,
        ),
    }
    mapping.update(_feedback_contract_mapping(data))
    return mapping


def _lines(items: list[object], empty: str) -> list[str]:
    values = [str(item).strip() for item in items if str(item).strip()]
    return values or [empty]


def _generated_steps(
    deterministic_checks: list[object],
    placement_candidates: list[object],
    pattern_refs: list[object],
    hook_events: list[object],
) -> str:
    steps = [
        "1. 入力 brief と境界を確認し、目的・出力契約・非責務を確定する。",
        "2. 配置候補を確認し、Skill / SubAgent / Hook / script の責務を分ける。",
        "3. テンプレート変数を展開し、成果物本文はパラメーター名を除き日本語で作成する。",
    ]
    if placement_candidates:
        steps.append(
            "4. 配置判断を `skill-build-trace.json` に記録する: "
            + ", ".join(_lines(placement_candidates, "Skill"))
            + "。"
        )
    if deterministic_checks:
        steps.append(
            "5. 決定論的検査を script / hook に分離する: "
            + ", ".join(_lines(deterministic_checks, "なし"))
            + "。"
        )
    if pattern_refs:
        steps.append(
            "6. 採用パターンを適用し、不採用条件を trace に残す: "
            + ", ".join(_lines(pattern_refs, "なし"))
            + "。"
        )
    if hook_events:
        steps.append(
            "7. Hook 配線案を生成し、settings への反映はユーザー承認後に行う: "
            + ", ".join(_lines(hook_events, "なし"))
            + "。"
        )
    return "\n".join(steps)


def _generated_checks(deterministic_checks: list[object], reuse_targets: list[object]) -> str:
    checks = [
        "- `validate-frontmatter.py` と `lint-skill-tree.py` を通す。",
        "- `skill-build-trace.json` に source_docs / doc_coverage / layer_decisions を残す。",
        "- 4条件（矛盾なし・漏れなし・整合性あり・依存関係整合）を確認する。",
    ]
    for item in _lines(deterministic_checks, ""):
        if item:
            checks.append(f"- 決定論的検査: {item}")
    if reuse_targets:
        checks.append(
            "- 横展開候補: " + ", ".join(_lines(reuse_targets, "none")) + "。"
        )
    return "\n".join(checks)


def _generated_gotchas(pattern_refs: list[object], variant_axes: list[object]) -> str:
    gotchas = [
        "- 固有名詞・固定パス・固定URL・固定ownerを再利用成果物へ直書きしない。",
        "- rubric を緩めて合格させず、評価基準変更は governance 経由にする。",
        "- `TODO` を残したまま完了扱いにしない。",
    ]
    if pattern_refs:
        gotchas.append(
            "- pattern_refs 採用時は negative cases を必ず trace に残す。"
        )
    if variant_axes:
        gotchas.append(
            "- variant_axes を増やす時はテンプレート増殖ではなく変数・combinator・rubric差分で吸収する。"
        )
    return "\n".join(gotchas)


def _variable_contract(
    abstraction_variables: list[object],
    template_inputs: list[object],
    template_non_goals: list[object],
) -> str:
    lines = [
        "- パラメーター名・frontmatterキー・JSONキーは英語を許可する。",
        "- 説明文、手順、注意点、評価コメントは日本語で書く。",
    ]
    for item in _lines(abstraction_variables, ""):
        if item:
            lines.append(f"- 変数化対象: {item}")
    for item in _lines(template_inputs, ""):
        if item:
            lines.append(f"- 入力変数: {item}")
    for item in _lines(template_non_goals, ""):
        if item:
            lines.append(f"- 非対象: {item}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--owner", default="team-skills")
    ap.add_argument("--brief", help="skill-brief.json path; values override placeholder defaults")
    ap.add_argument("--out", help="write rendered output to this path instead of stdout")
    ap.add_argument("--pair", help="override pair/generator placeholder")
    ap.add_argument("--rubric-refs", help="comma-separated rubric refs")
    args = ap.parse_args()

    tpath = Path(args.template)
    if not tpath.exists():
        print(f"template not found: {tpath}", file=sys.stderr)
        return 2
    prefix = args.name.split("-", 1)[0] if "-" in args.name else ""
    if prefix and prefix != args.kind:
        print(f"name/kind mismatch: name prefix '{prefix}' != kind '{args.kind}'", file=sys.stderr)
        return 2
    allowed_templates = {
        "run": {"run", "orchestrator", "agent-team", "hook-integrated"},
        "assign": {"assign-generator", "assign-evaluator"},
        "ref": {"ref"},
        "wrap": {"wrap"},
        "delegate": {"delegate"},
    }
    if tpath.stem not in allowed_templates.get(args.kind, {args.kind}):
        print(f"template/kind mismatch: template '{tpath.stem}' is not valid for kind '{args.kind}'", file=sys.stderr)
        return 2
    text = tpath.read_text(encoding="utf-8")

    today = datetime.date.today().isoformat()
    mapping = {
        "name": args.name,
        "skill_name": args.name,
        "kind": args.kind,
        "owner": args.owner,
        "date": today,
        "verb": "実行する",
        "object": "対象",
        "topic": args.name,
        "trigger1": "ユーザーが依頼した",
        "trigger2": "ワークフローで必要になった",
        "artifact": "artifact",
        "evaluator": f"assign-{args.name}-evaluator",
        "generator": f"run-{args.name}-generator",
        "upstream-rubric": "ref-skill-design-rubric",
        "external-tool": "tool",
        "tool": "tool",
        "subagent": "general-purpose",
        "output_contract": "未設定。briefで出力契約を指定する。",
        "boundary": "未設定。briefで非責務を指定する。",
        "key_constraints": "1. 未設定。briefで制約を指定する。",
        "role_suffix": "none",
        "base_skill": "none",
        "delegate_agent": "none",
        "additional_resources": "",
        "hierarchy_level": "L1",
        "rubric_refs": [],
        "source_url_or_path": "internal",
        "source_tier": "internal",
        "last_audited_date": today,
        "audit_trigger": "quarterly",
        "output_language": "ja",
        "parameter_language_exception": "true",
        "abstraction_variables": [],
        "template_inputs": [],
        "template_non_goals": [],
        "mass_production_profile": "standard",
        "generated_steps": _generated_steps([], [], [], []),
        "generated_checks": _generated_checks([], []),
        "generated_gotchas": _generated_gotchas([], []),
        "variable_contract": _variable_contract([], [], []),
    }
    mapping.update(
        _feedback_contract_mapping(
            {
                "skill_name": args.name,
                "output_contract": mapping["output_contract"],
                "deterministic_checks": [],
            }
        )
    )
    if args.brief:
        bpath = Path(args.brief)
        if not bpath.exists():
            print(f"brief not found: {bpath}", file=sys.stderr)
            return 2
        brief_values = brief_mapping(bpath)
        if brief_values.get("kind") and brief_values["kind"] != args.kind:
            print(f"brief/kind mismatch: brief '{brief_values['kind']}' != kind '{args.kind}'", file=sys.stderr)
            return 2
        if args.kind == "wrap" and brief_values.get("base_skill") in {"", "none"}:
            print("wrap requires base_skill in brief", file=sys.stderr)
            return 2
        if args.kind == "delegate" and brief_values.get("delegate_agent") in {"", "none"}:
            print("delegate requires delegate_agent in brief", file=sys.stderr)
            return 2
        mapping.update({k: v for k, v in brief_values.items() if v})
    if args.pair:
        mapping["pair"] = args.pair
        mapping["generator"] = args.pair
        mapping["evaluator"] = args.pair
    if args.rubric_refs:
        mapping["rubric_refs"] = [x.strip() for x in args.rubric_refs.split(",") if x.strip()]
        if mapping["rubric_refs"]:
            mapping["upstream-rubric"] = mapping["rubric_refs"][0]
    rendered = apply_dynamic_context_contract(render(text, mapping), mapping)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
