#!/usr/bin/env python3
# /// script
# name: validate-build-plan
# purpose: skill-brief から必須成果物集合 (flags/ファイル/SKILL.md セクション) を決定論
#          導出し (既定動作、--out でファイル保存)、生成物のディスク実体と突合する
#          (--check)。フラグ設定・
#          成果物選択をモデル判断から機械層へ移し、低性能モデルでも抜け漏れが
#          構造的に起きないようにする再現性ゲート。
# inputs:
#   - argv: --brief <skill-brief.json> [--out <path>] [--check --skill-dir <dir>] [--flags <json>]
# outputs:
#   - stdout: plan JSON (既定) / OK summary (--check)
#   - stderr: findings
# contexts: [C, E]
# network: false
# write-scope: eval-log/build-plan.json (--out 指定時のみ)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""brief→build-plan の決定論導出と成果物突合。

設計原則 (2026-07-02 まんべんなく生成レビュー):
- **フラグはモデルが決めない**: `--with-*` の要否は brief の非空フィールドから
  純関数で導出する (responsibilities→prompts, generate_pair_evaluator→evaluator,
  hook_events→hooks, knowledge_loop→knowledge, with_subagent_hint→subagent)。
- **CLI モード**: `--check` なし = plan を stdout へ出力 (`--out <path>` 併用で
  ファイル保存)。`--check --skill-dir <dir>` = 充足検査。`--emit` フラグは存在しない
  (導出はオプションなしの既定動作)。
- **セクション正本はテンプレート**: 必須セクション集合は templates/<kind>.md の
  `## ` 見出しと、有効フラグに対応する combinators/*.patch の `+## ` 見出しから
  パースする (別マトリクスを持たない = SSOT)。
- **check はディスク実体が真実**: trace の自己申告でなく生成物ファイル・セクション
  の実在と非スタブ (見出し直下に本文がある) を検査する。
- brief が無い呼び出し (フラグ明示の単発 build) は NOTE を出して exit 0
  (orchestrated 経路 = 量産経路は常に brief を持つ)。

Exit 0 = ok, 1 = 欠落あり, 2 = usage error。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = SKILL_ROOT / "templates"
COMBINATORS_DIR = TEMPLATES_DIR / "combinators"

LOOP_KINDS = {"run", "wrap", "delegate"}

# 受入検証の最低段 (この順で厳格化)。宣言が導出を下回る (緩め方向) のは violation。
ACCEPTANCE_TIERS = ("static", "fork", "live")
# 実セッションでしか挙動を観測できない静的信号 (allowed-tools 内のツール名)。
_LIVE_SIGNAL_TOOLS = {"Skill", "Agent", "AskUserQuestion"}

# kind (+role_suffix) → kind テンプレート。selection_rules (template-selection.schema.json
# examples[0]) は composite 付き一致を持つため、composite 無し brief の fallback を兼ねる。
KIND_TEMPLATE_FALLBACK = {
    ("run", ""): "run.md",
    ("ref", ""): "ref.md",
    ("wrap", ""): "wrap.md",
    ("delegate", ""): "delegate.md",
    ("assign", "evaluator"): "assign-evaluator.md",
    ("assign", "generator"): "assign-generator.md",
}

# flag → (combinator patch, 検査対象の追加資産)。パッチ見出しはファイルから動的パース。
FLAG_PATCH = {
    "with_evaluator": "with-evaluator.patch",
    "with_hooks": "with-hooks.patch",
    "with_subagent": "with-subagent.patch",
    "with_knowledge": "with-knowledge.patch",
    "with_goal_seek": "with-goal-seek.patch",
}

KNOWLEDGE_SCRIPTS = (
    "search_knowledge.py",
    "build_index.py",
    "record_usage.py",
    "add_entry.py",
)

# brief.goal_seek.engine=task-graph の生成先へ無改変コピーする checklist-graph
# engine 資産。build-plan / materializer / lint が同じファイル名集合を使い、prose の
# Step 10.6 に依存せず欠落と byte drift を fail-closed にする。
TASK_GRAPH_ENGINE_SCRIPTS = (
    "ready-set-from-checklist.py",
    "self-reflect-append.py",
    "extract-capability-dependency-graph.py",
    "record-capability-graph-knowledge.py",
)
TASK_GRAPH_TEMPLATE_PREFIX = "templates/task-graph-engine/scripts"

# 現 engine は checklist depends_on を逐次消費する縮小 profile であり、planner の
# task-spec graph / envelope / projection / 2-loop と同等ではない。この差を build-plan
# の machine-readable negative capability として固定し、full graph 成功の誤申告を防ぐ。
CHECKLIST_GRAPH_CAPABILITY_GAPS = (
    "task-spec-artifact-graph",
    "parallel-ready-set-dispatch-with-write-scope",
    "execution-envelope-state-projection",
    "discovered-task-spec-improvement-outer-loop",
)

HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")
PATCH_HEADING_RE = re.compile(r"^\+(#{2,3})\s+(.*)$")
# テンプレート由来の未展開プレースホルダ ({{skill_name}} 等)。抽象化変数
# ({{PROJECT_ROOT}} 等の大文字) は lint-template-variables の管轄なので対象外。
TEMPLATE_VAR_RE = re.compile(r"\{\{\s*[a-z][a-zA-Z0-9_.| ()\"']*\}\}")


def _normalize_heading(text: str) -> str:
    """見出しの比較用正規化: 括弧補足と末尾記号を落とす。"""
    text = re.sub(r"[（(].*$", "", text)
    return text.strip().rstrip(":：")


def _template_headings(path: Path) -> list[str]:
    """テンプレート本文の ##/### 見出しを返す (frontmatter/コメントブロック除外)。"""
    if not path.exists():
        return []
    headings: list[str] = []
    in_fm = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---" and in_fm < 2:
            in_fm += 1
            continue
        if in_fm < 2:
            continue
        m = HEADING_RE.match(line)
        if m and m.group(1) == "##":  # 必須集合は ## のみ (### は本文裁量)
            headings.append(_normalize_heading(m.group(2)))
    return headings


def _patch_headings(patch_name: str) -> list[str]:
    path = COMBINATORS_DIR / patch_name
    if not path.exists():
        return []
    headings = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = PATCH_HEADING_RE.match(line)
        if m and m.group(1) == "##":
            headings.append(_normalize_heading(m.group(2)))
    return headings


def _load_brief(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def derive_flags(brief: dict, cli_flags: dict | None = None) -> dict:
    """brief の非空フィールドから --with-* フラグ集合を純関数導出する。

    cli_flags は明示 opt-out (no_feedback_loop / skip_content_review /
    no_goal_seek) と明示 opt-in の上書きのみ許す。
    """
    cli = cli_flags or {}
    verification_profile = str(cli.get("verification_profile", "incremental")).strip()
    if verification_profile not in {"incremental", "exhaustive", "build-only"}:
        raise ValueError(
            "verification_profile must be incremental, exhaustive, or build-only"
        )
    kind = str(brief.get("kind", "")).strip()
    prompt_policy = str(brief.get("prompt_creator_policy", "")).strip().lower()
    responsibilities = brief.get("responsibilities") or []
    flags = {
        "with_prompts": bool(responsibilities) and prompt_policy != "skip",
        "with_evaluator": brief.get("generate_pair_evaluator") is True,
        "with_hooks": bool(brief.get("hook_events")) or brief.get("with_hooks") is True,
        "with_subagent": brief.get("with_subagent_hint") is True,
        "with_knowledge": bool(brief.get("knowledge_loop")),
        "with_goal_seek": kind in LOOP_KINDS and not cli.get("no_goal_seek", False),
        "feedback_contract_required": kind in LOOP_KINDS,
        "feedback_loop_deploy": not cli.get("no_feedback_loop", False),
        "content_review": not cli.get("skip_content_review", False),
        "verification_profile": verification_profile,
    }
    # 明示 opt-in 上書き (brief に無くても CLI で足す運用を許容)
    for key in ("with_prompts", "with_evaluator", "with_hooks", "with_subagent", "with_knowledge"):
        if cli.get(key) is True:
            flags[key] = True
    return flags


def derive_acceptance_tier(kind: str, has_hooks: bool, allowed_tools: object) -> str:
    """静的信号から受入検証の最低段を決定論導出する純関数 (D8)。

    hooks 配線 / allowed-tools の Skill・Agent・AskUserQuestion は実セッションで
    しか挙動を観測できないため live。それ以外の loop 実行系 (run/wrap/delegate) は
    fork 実行で受入可能、非実行系 (ref/assign) は静的検査のみで足りる (static)。
    """
    raw = allowed_tools or []
    if isinstance(raw, str):
        raw = re.split(r",\s*", raw)
    tools = {str(t).strip().split("(")[0] for t in raw}
    if has_hooks or (tools & _LIVE_SIGNAL_TOOLS):
        return "live"
    if str(kind or "").strip() in LOOP_KINDS:
        return "fork"
    return "static"


def derive_goal_seek_engine(brief: dict) -> str:
    """brief.goal_seek.engine の明示値を型安全かつ決定論的に正規化する。

    無指定 ("") の loop kind への task-graph defaulting は derive_plan が
    flags 導出後 (with_goal_seek 確定後) に適用する。opt-out は brief に
    `goal_seek.engine: inline` (または run-goal-seek) を明示するか --no-goal-seek。
    """
    goal_seek = brief.get("goal_seek")
    if not isinstance(goal_seek, dict):
        return ""
    return str(goal_seek.get("engine", "")).strip()


def derive_plan(brief: dict, cli_flags: dict | None = None) -> dict:
    kind = str(brief.get("kind", "")).strip()
    role_suffix = str(brief.get("role_suffix", "") or "").strip()
    flags = derive_flags(brief, cli_flags)
    goal_seek_engine = derive_goal_seek_engine(brief)
    # engine 既定 = task-graph: loop kind で goal-seek 配線が有効かつ brief が engine を
    # 明示しない場合、依存順駆動 (checklist-graph) を既定で焼き込む。明示値は常に優先
    # (inline/run-goal-seek が opt-out)。render-combinators._brief_requests_task_graph と同一規則。
    engine_defaulted = False
    if not goal_seek_engine and kind in LOOP_KINDS and flags["with_goal_seek"]:
        goal_seek_engine = "task-graph"
        engine_defaulted = True

    template = KIND_TEMPLATE_FALLBACK.get((kind, role_suffix if kind == "assign" else ""))
    sections = _template_headings(TEMPLATES_DIR / template) if template else []
    for flag, patch in FLAG_PATCH.items():
        if flags.get(flag):
            for h in _patch_headings(patch):
                if h not in sections:
                    sections.append(h)

    deliverables: list[dict] = [
        {"id": "skill-md", "type": "file", "path": "SKILL.md", "source": "kind"},
    ]
    for item in brief.get("responsibilities") or []:
        rid = str(item.get("id", "")).strip() if isinstance(item, dict) else str(item)
        if rid and flags["with_prompts"]:
            deliverables.append(
                {
                    "id": f"prompt:{rid}",
                    "type": "glob",
                    "path": f"prompts/{rid}*.md",
                    "source": "brief.responsibilities",
                }
            )
    if flags["with_knowledge"]:
        deliverables.append(
            {"id": "knowledge-dir", "type": "dir", "path": "knowledge", "source": "brief.knowledge_loop"}
        )
        for script in KNOWLEDGE_SCRIPTS:
            deliverables.append(
                {
                    "id": f"knowledge-script:{script}",
                    "type": "file",
                    "path": f"scripts/{script}",
                    "source": "brief.knowledge_loop",
                }
            )
        deliverables.append(
            {
                "id": "frontmatter:knowledge_loop",
                "type": "frontmatter-key",
                "path": "knowledge_loop",
                "source": "brief.knowledge_loop",
            }
        )
    if flags["with_hooks"]:
        for event in brief.get("hook_events") or []:
            deliverables.append(
                {
                    "id": f"hook:{event}",
                    "type": "glob",
                    "path": "scripts/hook-*.py",
                    "must_contain": str(event),
                    "source": "brief.hook_events",
                }
            )
    if flags["with_evaluator"]:
        deliverables.append(
            {
                "id": "evaluator-pair",
                "type": "pair-skill",
                "path": "",  # frontmatter `pair:` から解決
                "source": "brief.generate_pair_evaluator",
            }
        )
    if flags["with_subagent"]:
        deliverables.append(
            {
                "id": "subagent",
                "type": "agent-file",
                "path": "",  # <plugin>/agents/ か .claude/agents/ から解決
                "source": "brief.with_subagent_hint",
            }
        )
    if flags["feedback_contract_required"]:
        deliverables.append(
            {
                "id": "frontmatter:feedback_contract",
                "type": "frontmatter-key",
                "path": "feedback_contract",
                "source": "kind (loop 実行系)",
                "verified_by": "lint-feedback-contract.py",  # 内容規則は既存 lint に委譲
            }
        )

    if goal_seek_engine == "task-graph":
        engine_source = (
            "default: loop kind + with_goal_seek (engine unset in brief)"
            if engine_defaulted
            else "brief.goal_seek.engine"
        )
        deliverables.extend(
            [
                {
                    "id": "frontmatter:goal_seek.engine",
                    "type": "frontmatter-value",
                    "path": "goal_seek.engine",
                    "expected": "task-graph",
                    "source": engine_source,
                },
                {
                    "id": "frontmatter:goal_seek.engine_profile",
                    "type": "frontmatter-value",
                    "path": "goal_seek.engine_profile",
                    "expected": "checklist-graph",
                    "source": f"derived from goal_seek_engine=task-graph ({engine_source})",
                },
                {
                    "id": "frontmatter:goal_seek.full_task_spec_graph",
                    "type": "frontmatter-value",
                    "path": "goal_seek.full_task_spec_graph",
                    "expected": "false",
                    "source": "checklist-graph capability boundary",
                },
            ]
        )
        for script in TASK_GRAPH_ENGINE_SCRIPTS:
            deliverables.append(
                {
                    "id": f"task-graph-engine:{script}",
                    "type": "template-copy",
                    "path": f"scripts/{script}",
                    "template": f"{TASK_GRAPH_TEMPLATE_PREFIX}/{script}",
                    "source": f"goal_seek_engine=task-graph ({engine_source})",
                    "verified_by": "validate-build-plan.py --check (byte parity)",
                }
            )

    notes: list[str] = []
    if brief.get("needs_independent_context") is True and not flags["with_subagent"]:
        notes.append(
            "needs_independent_context=true だが with_subagent_hint 未設定。"
            "SubAgent 化の要否を layer_decisions に理由付きで記録すること。"
        )
    if brief.get("external_systems"):
        notes.append(
            "external_systems 非空: 疎通確認 (doctor) / fail-closed / portability 対応の"
            "要否を CL-11 に照らして判断し、trace に記録すること。"
        )
        notes.append(
            "外部システムへ書込む投入系の場合は Skill(ref-output-routing) の Sink Contract"
            " (schema SSOT / 冪等 upsert / fail-closed) を必須参照し、その不変条件を"
            " feedback_contract.criteria と deterministic_checks に反映すること"
            " (モデル知識で毎回再発明しない)。"
        )

    if goal_seek_engine == "task-graph":
        notes.append(
            "engine_profile=checklist-graph: checklist depends_on の逐次消費・self-reflect・"
            "cross-surface knowledge を提供する縮小 engine。plugin-dev-planner の task-spec graph / "
            "parallel dispatch / execution envelope・state projection / discovered-task spec-improvement "
            "outer loop と同等ではなく、full task-spec graph として成功扱いしてはならない。"
        )
        if kind not in LOOP_KINDS or not flags.get("with_goal_seek"):
            notes.append(
                "FAIL-CLOSED: task-graph engine は loop kind (run/wrap/delegate) + with_goal_seek=true "
                "でのみ実行可能。現在の brief は配線条件を満たさない。"
            )

    plan = {
        "schema": "schemas/build-plan.schema.json",
        "skill_name": brief.get("skill_name", ""),
        "kind": kind,
        "role_suffix": role_suffix,
        "template": template or "",
        "goal_seek_engine": goal_seek_engine,
        "engine_profile": "checklist-graph" if goal_seek_engine == "task-graph" else "",
        "full_task_spec_graph": False if goal_seek_engine == "task-graph" else None,
        "capability_gaps": (
            list(CHECKLIST_GRAPH_CAPABILITY_GAPS) if goal_seek_engine == "task-graph" else []
        ),
        "flags": flags,
        "acceptance_tier": derive_acceptance_tier(
            kind, flags["with_hooks"], brief.get("allowed_tools") or brief.get("allowed-tools")
        ),
        "required_sections": sections,
        "required_deliverables": deliverables,
        "notes": notes,
    }
    if goal_seek_engine == "task-graph":
        plan["materializer"] = {
            "tool": "scripts/render-combinators.py",
            "command": (
                "python3 scripts/render-combinators.py --brief <skill-brief.json> "
                "--materialize-task-graph-engine <skill-dir>"
            ),
            "idempotent": True,
        }
    return plan


# --- check ----------------------------------------------------------------


def _parse_frontmatter_keys(text: str) -> set[str]:
    if not text.startswith("---"):
        return set()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return set()
    keys = set()
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:", line)
        if m:
            keys.add(m.group(1))
    return keys


def _frontmatter_value(text: str, key: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*(#.*)?$", line)
        if m:
            return m.group(1).strip().strip("'\"")
    return ""


def _frontmatter_nested_value(text: str, dotted_key: str) -> str:
    """stdlib のみで 2 段 YAML scalar (例 goal_seek.engine) を読む。

    build-plan が要求する machine-readable 境界値専用。複雑な YAML 解釈は行わず、
    同一親 block 内の scalar だけを fail-closed に取得する。
    """
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    bits = dotted_key.split(".")
    if len(parts) < 3 or len(bits) != 2:
        return ""
    parent, child = bits
    in_parent = False
    parent_indent = -1
    for line in parts[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if re.match(rf"^{re.escape(parent)}\s*:\s*(?:#.*)?$", line):
            in_parent = True
            parent_indent = indent
            continue
        if in_parent and indent <= parent_indent:
            in_parent = False
        if in_parent:
            m = re.match(
                rf"^\s+{re.escape(child)}\s*:\s*(.*?)\s*(?:#.*)?$", line
            )
            if m:
                return m.group(1).strip().strip("'\"")
    return ""


def _body_sections(text: str) -> dict[str, int]:
    """SKILL.md 本文の ## 見出し → 見出し直下の本文行数 (非空・非見出し)。"""
    parts = text.split("---", 2)
    body = parts[2] if text.startswith("---") and len(parts) >= 3 else text
    sections: dict[str, int] = {}
    current: str | None = None
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if current is not None:
                sections[current] += 1
            continue
        m = HEADING_RE.match(line) if not in_fence else None
        if m and m.group(1) == "##":
            current = _normalize_heading(m.group(2))
            sections.setdefault(current, 0)
            continue
        if current is not None and line.strip() and not line.startswith("#"):
            sections[current] += 1
    return sections


def check_plan(plan: dict, skill_dir: Path) -> list[str]:
    errs: list[str] = []
    if plan.get("goal_seek_engine") == "task-graph" and not plan.get("flags", {}).get(
        "with_goal_seek"
    ):
        errs.append(
            "task-graph engine requested but with_goal_seek=false: "
            "loop kind (run/wrap/delegate) 以外では checklist-graph を成功扱いできない"
        )
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"SKILL.md not found: {skill_md}"]
    text = skill_md.read_text(encoding="utf-8")

    # 1. 未展開テンプレートプレースホルダ (低性能モデルの穴埋め忘れ検出)
    for m in TEMPLATE_VAR_RE.finditer(text):
        token = m.group(0)
        if token == "{{...}}":  # 散文中のメタ表記は許容
            continue
        errs.append(f"unexpanded template placeholder: {token}")

    # 2. 必須セクション (テンプレート正本 ⊆ 生成物) + 非スタブ
    present = _body_sections(text)
    for required in plan.get("required_sections", []):
        if required not in present:
            errs.append(f"missing required section: ## {required} (template={plan.get('template')})")
        elif present[required] == 0:
            errs.append(f"stub section (本文 0 行): ## {required}")

    # 3. 必須成果物のディスク実在
    fm_keys = _parse_frontmatter_keys(text)
    for d in plan.get("required_deliverables", []):
        dtype = d.get("type")
        path = d.get("path", "")
        if dtype == "file":
            if not (skill_dir / path).exists():
                errs.append(f"missing deliverable: {path} (source={d.get('source')})")
        elif dtype == "template-copy":
            dest = skill_dir / path
            template = SKILL_ROOT / str(d.get("template", ""))
            if not dest.is_file():
                errs.append(f"missing deliverable: {path} (source={d.get('source')})")
            elif not template.is_file():
                errs.append(f"template source not found: {template}")
            elif dest.read_bytes() != template.read_bytes():
                errs.append(
                    f"byte drift: {path} != {d.get('template')} "
                    "(task-graph engine assets must be unmodified template copies)"
                )
        elif dtype == "dir":
            if not (skill_dir / path).is_dir():
                errs.append(f"missing deliverable dir: {path}/ (source={d.get('source')})")
        elif dtype == "glob":
            matches = sorted(skill_dir.glob(path))
            need = str(d.get("must_contain", "")).lower().replace("-", "")
            if need:
                matches = [
                    p for p in matches
                    if need in p.name.lower().replace("-", "").replace("_", "")
                ]
            if not matches:
                errs.append(
                    f"missing deliverable: {path}"
                    + (f" (filename must contain '{d.get('must_contain')}')" if need else "")
                    + f" (source={d.get('source')})"
                )
        elif dtype == "frontmatter-key":
            if path not in fm_keys:
                errs.append(f"missing frontmatter key: {path} (source={d.get('source')})")
        elif dtype == "frontmatter-value":
            actual = _frontmatter_nested_value(text, path)
            expected = str(d.get("expected", ""))
            if actual != expected:
                errs.append(
                    f"frontmatter value mismatch: {path}={actual!r}, expected {expected!r} "
                    f"(source={d.get('source')})"
                )
        elif dtype == "pair-skill":
            pair = _frontmatter_value(text, "pair")
            if not pair:
                errs.append("generate_pair_evaluator=true だが frontmatter `pair:` が無い")
            elif not (skill_dir.parent / pair / "SKILL.md").exists():
                errs.append(f"pair evaluator skill not found: ../{pair}/SKILL.md")
        elif dtype == "agent-file":
            name = plan.get("skill_name", "")
            plugin_root = skill_dir.parent.parent
            candidates = list((plugin_root / "agents").glob(f"*{name}*.md")) if name else []
            if not candidates:
                candidates = list(Path(".claude/agents").glob(f"*{name}*.md")) if name else []
            if not candidates:
                errs.append(
                    f"subagent 派生ファイルが見つからない: {plugin_root}/agents/*{name}*.md"
                    " (Step 7 build-subagent.py 未実行の疑い)"
                )

    # 4. acceptance_tier: 宣言 < 導出 (static<fork<live) は受入検証の緩め方向なので違反。
    #    宣言は任意 (旧 SKILL.md 後方互換)。導出はディスク実体の静的信号 (frontmatter
    #    allowed-tools / hook スクリプト実在 or plan の with_hooks / kind) から行う。
    declared = _frontmatter_value(text, "acceptance_tier")
    if declared:
        fm_tools = _frontmatter_value(text, "allowed-tools")
        has_hooks = bool(plan.get("flags", {}).get("with_hooks")) or bool(
            list(skill_dir.glob("scripts/hook-*.py"))
        )
        derived = derive_acceptance_tier(
            _frontmatter_value(text, "kind") or plan.get("kind", ""), has_hooks, fm_tools
        )
        if declared not in ACCEPTANCE_TIERS:
            errs.append(
                f"unknown acceptance_tier: {declared!r} (expected one of {list(ACCEPTANCE_TIERS)})"
            )
        elif ACCEPTANCE_TIERS.index(declared) < ACCEPTANCE_TIERS.index(derived):
            errs.append(
                f"acceptance_tier declared={declared} < derived={derived}"
                " (順序 static<fork<live): 静的信号が要求する受入段より緩い宣言は禁止"
            )
    return errs


# --- CLI ------------------------------------------------------------------


def _self_test() -> int:
    brief = {
        "skill_name": "run-demo",
        "kind": "run",
        "responsibilities": [{"id": "R1"}, {"id": "R2"}],
        "generate_pair_evaluator": True,
        "hook_events": ["PostToolUse"],
        "knowledge_loop": {"pattern": "index-search"},
        "with_subagent_hint": True,
    }
    plan = derive_plan(brief)
    assert plan["flags"]["with_prompts"] is True
    assert plan["flags"]["with_evaluator"] is True
    assert plan["flags"]["with_hooks"] is True
    assert plan["flags"]["with_knowledge"] is True
    assert plan["flags"]["with_subagent"] is True
    assert plan["flags"]["with_goal_seek"] is True
    assert plan["flags"]["feedback_contract_required"] is True
    ids = {d["id"] for d in plan["required_deliverables"]}
    assert {"prompt:R1", "prompt:R2", "knowledge-dir", "evaluator-pair", "subagent"} <= ids
    assert "目的と出力契約" in plan["required_sections"]
    assert "評価・改善ループ契約" in plan["required_sections"]
    assert "ナレッジループ" in plan["required_sections"]

    # ref: 評価セクション不要・フラグ全 false
    ref_plan = derive_plan({"skill_name": "ref-demo", "kind": "ref"})
    assert ref_plan["flags"]["feedback_contract_required"] is False
    assert "評価・改善ループ契約" not in ref_plan["required_sections"]
    assert "手順" in ref_plan["required_sections"]

    # acceptance_tier: 静的信号からの決定論導出 (D8)
    assert derive_acceptance_tier("ref", False, []) == "static"
    assert derive_acceptance_tier("run", False, ["Read", "Bash(python3:*)"]) == "fork"
    assert derive_acceptance_tier("run", True, []) == "live"
    assert derive_acceptance_tier("ref", False, ["Skill"]) == "live"
    assert derive_acceptance_tier("wrap", False, "Read, AskUserQuestion") == "live"
    assert plan["acceptance_tier"] == "live"  # hook_events あり brief
    assert ref_plan["acceptance_tier"] == "static"

    # task-graph brief は同一入力から checklist-graph 契約と全4資産を常に導出する。
    tg_brief = {
        "skill_name": "run-graph-demo",
        "kind": "run",
        "goal_seek": {"engine": "task-graph"},
    }
    tg_plan = derive_plan(tg_brief)
    assert tg_plan == derive_plan(tg_brief)
    assert tg_plan["engine_profile"] == "checklist-graph"
    assert tg_plan["full_task_spec_graph"] is False
    assert set(tg_plan["capability_gaps"]) == set(CHECKLIST_GRAPH_CAPABILITY_GAPS)
    tg_ids = {d["id"] for d in tg_plan["required_deliverables"]}
    assert {f"task-graph-engine:{s}" for s in TASK_GRAPH_ENGINE_SCRIPTS} <= tg_ids

    # prompt_creator_policy=skip で prompts 免除
    p = derive_plan({"kind": "run", "responsibilities": [{"id": "R1"}], "prompt_creator_policy": "skip"})
    assert p["flags"]["with_prompts"] is False

    # check: 不足検出 (tmp なしで純関数検査)
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "skills" / "run-demo"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: run-demo\nkind: run\n---\n\n# run-demo\n\n## 目的と出力契約\n\n本文。\n",
            encoding="utf-8",
        )
        errs = check_plan(plan, d)
        assert any("評価・改善ループ契約" in e for e in errs), errs
        assert any("prompt" in e for e in errs), errs
        # プレースホルダ検出
        (d / "SKILL.md").write_text(
            "---\nname: run-demo\n---\n\n## 目的と出力契約\n\n{{description}}\n", encoding="utf-8"
        )
        errs = check_plan(plan, d)
        assert any("unexpanded" in e for e in errs), errs
        # スタブ検出 (見出しのみ)
        (d / "SKILL.md").write_text(
            "---\nname: run-demo\n---\n\n## 目的と出力契約\n\n## 境界\n\nx\n", encoding="utf-8"
        )
        errs = check_plan(derive_plan({"kind": "ref"}), d)
        assert any("stub section" in e and "目的と出力契約" in e for e in errs), errs
        # acceptance_tier 宣言 < 導出 (run kind なのに static 宣言) を検出
        (d / "SKILL.md").write_text(
            "---\nname: run-demo\nkind: run\nacceptance_tier: static\n---\n\n"
            "## 目的と出力契約\n\n本文。\n",
            encoding="utf-8",
        )
        errs = check_plan(derive_plan({"kind": "run"}), d)
        assert any("acceptance_tier declared=static < derived=fork" in e for e in errs), errs
        # 宣言 >= 導出 (live 宣言) は違反にならない
        (d / "SKILL.md").write_text(
            "---\nname: run-demo\nkind: run\nacceptance_tier: live\n---\n\n"
            "## 目的と出力契約\n\n本文。\n",
            encoding="utf-8",
        )
        errs = check_plan(derive_plan({"kind": "run"}), d)
        assert not any("acceptance_tier" in e for e in errs), errs
    print("OK: validate-build-plan self-test (6 groups)")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()
    args = list(argv)

    def _opt(name: str) -> str | None:
        if name in args:
            i = args.index(name)
            if i + 1 < len(args):
                return args[i + 1]
        return None

    brief_path = _opt("--brief") or "eval-log/skill-brief.json"
    check = "--check" in args
    skill_dir = _opt("--skill-dir")
    out = _opt("--out")
    cli_flags_raw = _opt("--flags")

    bp = Path(brief_path)
    if not bp.exists():
        print(
            f"NOTE: brief not found ({bp}) — フラグ明示の単発 build とみなし skip。"
            "量産経路 (run-skill-create) では brief が必須のため本ゲートが有効になる。",
        )
        return 0
    try:
        brief = _load_brief(bp)
        cli_flags = json.loads(cli_flags_raw) if cli_flags_raw else None
    except (json.JSONDecodeError, OSError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2

    try:
        plan = derive_plan(brief, cli_flags)
    except ValueError as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not check:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if not skill_dir:
        print("usage: --check には --skill-dir <dir> が必要", file=sys.stderr)
        return 2
    errs = check_plan(plan, Path(skill_dir))
    if errs:
        print(f"FAIL: build-plan fulfillment ({len(errs)} 件)", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        print(
            "  → 必須成果物は brief から決定論導出されている"
            " (--check なし実行で stdout に一覧)。"
            "モデル判断で省略せず、欠落分を生成してから再実行する。",
            file=sys.stderr,
        )
        return 1
    print(f"OK: build-plan fulfilled ({plan['skill_name'] or skill_dir})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
