#!/usr/bin/env python3
# /// script
# name: validate-build-plan
# purpose: skill-brief から必須成果物集合 (flags/ファイル/SKILL.md セクション) を決定論
#          導出し (既定動作、--out でファイル保存)、生成物のディスク実体と突合する
#          (--check)。フラグ設定・
#          成果物選択をモデル判断から機械層へ移し、低性能モデルでも抜け漏れが
#          構造的に起きないようにする再現性ゲート。
# inputs:
#   - argv: [--brief <skill-brief.json>] [--out <path>] [--check --skill-dir <dir>] [--mode create|update] [--stage draft|release] [--flags <json-object>] | --self-test | --help
#   - file: --brief の JSON object (省略時は eval-log/skill-brief.json)・--skill-dir 配下の生成物 (--check / --mode update)
#   - file: この skill の templates/<kind>.md・templates/combinators/*.patch (必須セクションの正本)・templates/task-graph-engine/scripts/* (byte parity の比較元)
#   - file: --check で読む周辺: --skill-dir の隣の <pair>/SKILL.md、<plugin>/agents/*.md と cwd の .claude/agents/*.md (subagent 派生)
#   - file: 同じ dir の lint-capability-graph-knowledge.py (import して canonical_engine_refs を呼ぶ)
# outputs:
#   - stdout: plan JSON (既定) / OK summary (--check) / NOTE (--brief・--check・--out のどれも無く、既定の brief も無いとき)
#   - stderr: findings (--check で欠落があるとき) / invalid input・error の 1 行 (exit 2)
#   - file: --out の指定先へ plan JSON (同じ dir の一時ファイルに書いてから置き換える)
#   - exit: 0=OK (plan を出した・--check で欠落なし・NOTE で skip) / 1=--check で欠落あり / 2=usage error・不正な入力 (未知の引数、--check に --skill-dir が無い、--out が空、--mode が create・update 以外か update に --skill-dir が無い、明示した --brief か --check・--out で要る brief が無い、brief・--flags が JSON object でない、--flags に未知の key・型違い、brief の型が崩れている (kind が無い・未知、assign の role_suffix に template が無い、responsibilities の id が schema の形でない・prompt_required が bool でない、hook_events に空の event、goal_seek が object でない、JSON の入れ子が深すぎる)、SKILL.md が symlink か UTF-8 で読めない、--out に書けない、依存する lint・template・combinator を読めない)
# contexts: [C, E]
# network: false
# write-scope: --out の指定先 (Step 1 では eval-log/build-plan.json) と、置き換えまでの同じ dir の一時ファイル。--out の親 dir が無ければ作る (mkdir -p)。入力・usage・--check の読み取りで exit 2 になるときは書く前に止める
# dependencies: [lint-capability-graph-knowledge.py]
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
- brief が無い呼び出しで NOTE を出して exit 0 にするのは、--brief・--check・--out の
  どれも付けず、既定の eval-log/skill-brief.json も無いときだけ。明示した --brief が無い、
  または --check・--out に要る brief が無いときは exit 2 にする (検査しないまま成功扱いにしない)。

Exit 0 = ok, 1 = 欠落あり, 2 = usage error / 不正な入力。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import secrets
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
# skill-brief.schema.json の kind enum。無い・綴り違いの kind は template を引けず必須セクションが
# 空になる (検査しないまま PASS) ので、derive_plan が不正入力 (exit 2) にする。
BRIEF_KINDS = ("ref", "run", "wrap", "assign", "delegate")
# assign の role_suffix は template を持つ generator / evaluator だけ (template-selection.schema.json の
# match.role_suffix enum と render-combinators.py の with-assign-<role>.patch)。未指定は
# render-combinators.py selected_patches と同じく generator として読む。
ASSIGN_ROLES = ("generator", "evaluator")
ASSIGN_DEFAULT_ROLE = "generator"

# skill-brief.schema.json#/properties/responsibilities/items/properties/id/pattern。
# id は prompts/<id>*.md の glob に入るので、形を確かめずに使うと "../SKILL" が skill dir の外を指す。
RESPONSIBILITY_ID_PATTERN = r"^R[0-9]+[a-z]?(-[a-z0-9]+(-[a-z0-9]+)*)?$"
RESPONSIBILITY_ID_RE = re.compile(RESPONSIBILITY_ID_PATTERN)

# --flags が受け付ける key。opt-out / opt-in は bool、残りは enum の文字列 (derive_flags が値を確かめる)。
CLI_OPT_OUT_FLAGS = ("no_feedback_loop", "skip_content_review", "no_goal_seek")
CLI_OPT_IN_FLAGS = ("with_prompts", "with_evaluator", "with_hooks", "with_subagent", "with_knowledge")
CLI_STRING_FLAGS = ("verification_profile", "build_stage")

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
    "build-external-intelligence.py",
)

# brief.goal_seek.engine=task-graph の生成先へ無改変コピーする checklist-graph
# engine 資産。build-plan / materializer / lint が同じファイル名集合を使い、prose の
# Step 10.6 に依存せず欠落と byte drift を fail-closed にする。
TASK_GRAPH_ENGINE_SCRIPTS = (
    "extract-ready-set-from-checklist.py",
    "build-self-reflection-entry.py",
    "extract-capability-dependency-graph.py",
    "build-capability-graph-knowledge-entry.py",
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


class CheckerDependencyError(RuntimeError):
    """plan の導出・--check が頼る template・combinator・peer の lint を読めない・使えない。

    判定できないので「要求なし」「参照なし」に倒さず exit 2 にする。
    """


def _read_dependency(path: Path, what: str) -> str:
    """template・combinator を読む。無い・読めないときは CheckerDependencyError (空の要求集合で PASS させない)。"""
    if not path.is_file():
        raise CheckerDependencyError(f"{what} が無い: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerDependencyError(f"{what} を読めない: {path} ({type(exc).__name__})") from exc


def _template_headings(path: Path) -> list[str]:
    """テンプレート本文の ##/### 見出しを返す (frontmatter/コメントブロック除外)。

    template が無い・読めない・## 見出しを 1 つも持たないときは CheckerDependencyError にする
    (必須セクションが空のまま --check を通さない)。
    """
    headings: list[str] = []
    in_fm = 0
    for line in _read_dependency(path, "kind template").splitlines():
        if line.strip() == "---" and in_fm < 2:
            in_fm += 1
            continue
        if in_fm < 2:
            continue
        m = HEADING_RE.match(line)
        if m and m.group(1) == "##":  # 必須集合は ## のみ (### は本文裁量)
            headings.append(_normalize_heading(m.group(2)))
    if not headings:
        raise CheckerDependencyError(f"kind template に ## 見出しが無い: {path}")
    return headings


def _patch_headings(patch_name: str) -> list[str]:
    """combinator patch が足す ## 見出し。patch が無い・読めないときは CheckerDependencyError。

    with-goal-seek.patch のように ### しか足さない patch もあるので、見出し 0 件は正常として扱う。
    """
    path = COMBINATORS_DIR / patch_name
    headings = []
    for line in _read_dependency(path, "combinator patch").splitlines():
        m = PATCH_HEADING_RE.match(line)
        if m and m.group(1) == "##":
            headings.append(_normalize_heading(m.group(2)))
    return headings


def _load_brief(path: Path) -> dict:
    brief = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(brief, dict):
        raise ValueError(f"brief must be a JSON object, got {type(brief).__name__}: {path}")
    return brief


# brief のうち derive_plan が要素を数え上げる field と、受け付ける型 (空値は「無い」と同じ扱い)。
# skill-brief.schema.json では responsibilities / hook_events が array。allowed-tools は
# frontmatter と同じく "Read, Bash" の文字列も許す (derive_acceptance_tier が両方を読む)。
_BRIEF_ITERABLE_FIELDS: dict[str, tuple[type, ...]] = {
    "responsibilities": (list,),
    "hook_events": (list,),
    "allowed_tools": (list, str),
    "allowed-tools": (list, str),
}


def _require_brief_shape(brief: object) -> None:
    """derive_plan が数え上げる field の型を確かめ、崩れていれば ValueError (exit 2) にする。"""
    if not isinstance(brief, dict):
        raise ValueError(f"brief must be a JSON object, got {type(brief).__name__}")
    for key, allowed in _BRIEF_ITERABLE_FIELDS.items():
        value = brief.get(key)
        if value and not isinstance(value, allowed):
            names = " or ".join("array" if t is list else "string" for t in allowed)
            raise ValueError(f"brief.{key} must be {names}, got {type(value).__name__}")


def derive_flags(brief: dict, cli_flags: dict | None = None) -> dict:
    """brief の非空フィールドから --with-* フラグ集合を純関数導出する。

    cli_flags は明示 opt-out (no_feedback_loop / skip_content_review /
    no_goal_seek)、stage/profile、明示 opt-in の上書きのみ許す。
    """
    if cli_flags is not None and not isinstance(cli_flags, dict):
        raise ValueError(f"--flags must be a JSON object, got {type(cli_flags).__name__}")
    cli = cli_flags or {}
    # 綴り違いの key や "false" の文字列を黙って読むと、opt-out の意図と逆の plan を出す
    # (`not "false"` は False)。key は既知のものだけ、bool の flag は JSON の true/false だけ受け付ける。
    unknown = sorted(set(cli) - set(CLI_OPT_OUT_FLAGS) - set(CLI_OPT_IN_FLAGS) - set(CLI_STRING_FLAGS))
    if unknown:
        raise ValueError(f"--flags has unknown keys: {unknown}")
    for key in (*CLI_OPT_OUT_FLAGS, *CLI_OPT_IN_FLAGS):
        if key in cli and not isinstance(cli[key], bool):
            raise ValueError(f"--flags.{key} must be true or false, got {type(cli[key]).__name__}")
    for key in CLI_STRING_FLAGS:
        if key in cli and not isinstance(cli[key], str):
            raise ValueError(f"--flags.{key} must be a string, got {type(cli[key]).__name__}")
    verification_profile = str(cli.get("verification_profile", "incremental")).strip()
    if verification_profile not in {"incremental", "exhaustive", "build-only"}:
        raise ValueError(
            "verification_profile must be incremental, exhaustive, or build-only"
        )
    build_stage = str(cli.get("build_stage", "draft")).strip()
    if build_stage not in {"draft", "release"}:
        raise ValueError("build_stage must be draft or release")
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
        "build_stage": build_stage,
    }
    # 明示 opt-in 上書き (brief に無くても CLI で足す運用を許容)
    for key in ("with_prompts", "with_evaluator", "with_hooks", "with_subagent", "with_knowledge"):
        if cli.get(key) is True:
            flags[key] = True
    return flags


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1].strip()
    return value.strip("'\"").strip()


def _split_tool_scalar(value: str) -> list[str]:
    """allowed-tools の文字列を括弧の外のカンマと空白で区切る。

    "Read, Skill"・"Read Skill"・"[Read, Skill]" (flow) を同じ集合に読み、
    "Bash(git diff *)" のような括弧内の空白では区切らない (build-subagent.py と同じ区切り方)。
    """
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    items: list[str] = []
    buf = ""
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        if depth == 0 and (ch == "," or ch.isspace()):
            if buf.strip():
                items.append(buf.strip())
            buf = ""
            continue
        buf += ch
    if buf.strip():
        items.append(buf.strip())
    return items


def _tool_base(item: str) -> str:
    """"'Bash(python3 *)'" → "Bash"。引用符と括弧の引数を落としたツール名。"""
    return _strip_quotes(item).split("(", 1)[0].strip()


def derive_acceptance_tier(kind: str, has_hooks: bool, allowed_tools: object) -> str:
    """静的信号から受入検証の最低段を決定論導出する純関数 (D8)。

    hooks 配線 / allowed-tools の Skill・Agent・AskUserQuestion は実セッションで
    しか挙動を観測できないため live。それ以外の loop 実行系 (run/wrap/delegate) は
    fork 実行で受入可能、非実行系 (ref/assign) は静的検査のみで足りる (static)。
    """
    raw = allowed_tools or []
    if isinstance(raw, str):
        raw = _split_tool_scalar(raw)
    tools = {_tool_base(str(t)) for t in raw}
    if has_hooks or (tools & _LIVE_SIGNAL_TOOLS):
        return "live"
    if str(kind or "").strip() in LOOP_KINDS:
        return "fork"
    return "static"


def derive_goal_seek_engine(brief: dict) -> str:
    """brief.goal_seek.engine の明示値を型安全かつ決定論的に正規化する。

    無指定 ("") の loop kind は derive_plan が最小構成 `inline` へ
    defaulting する。task-graph / run-goal-seek は brief で明示された
    場合だけ使い、複雑性を「必要かもしれない」という推測で追加しない。
    """
    goal_seek = brief.get("goal_seek")
    if goal_seek is None:
        return ""
    if not isinstance(goal_seek, dict):
        # skill-brief.schema.json の goal_seek は object。"task-graph" の文字列を「無指定」と読むと
        # create では inline へ黙って倒れ、update (preserve_update_runtime_profile) では exit 2 になる
        raise ValueError("brief.goal_seek must be an object")
    engine = str(goal_seek.get("engine", "")).strip()
    if engine and engine not in {"inline", "run-goal-seek", "task-graph"}:
        raise ValueError(f"unknown goal_seek.engine: {engine!r}")
    return engine


def derive_goal_seek_fork(brief: dict) -> str:
    """ゴールシークの context 配置を最小で十分な形に導出する。

    明示値を最優先し、無指定では
    needs_independent_context=true のときだけ subagent、それ以外は inline。
    Agent Team はユーザー/設計者が brief で明示した場合に限る。
    """
    goal_seek = brief.get("goal_seek")
    explicit = (
        str(goal_seek.get("fork", "")).strip() if isinstance(goal_seek, dict) else ""
    )
    if explicit:
        if explicit not in {"inline", "subagent", "agent-team"}:
            raise ValueError(f"unknown goal_seek.fork: {explicit!r}")
        return explicit
    return "subagent" if brief.get("needs_independent_context") is True else "inline"


def resolve_template(brief: dict) -> tuple[str, str, str]:
    """brief の kind / role_suffix から (kind, role_suffix, template) を決める。引けなければ ValueError。

    - kind は skill-brief.schema.json の enum だけ受け付ける (無い・綴り違いは exit 2)。
    - assign の role_suffix は template を持つ generator / evaluator だけ (template-selection.schema.json
      と render-combinators.py の with-assign-<role>.patch)。schema が許す contributor / delegate も
      template が無いので exit 2。未指定 (null / "") は render-combinators.py selected_patches と同じく
      generator。ただし skill_name の role suffix (-generator / -evaluator、lint-skill-name.py 第5条) と
      食い違うときは、違う template の要求で検査しないよう exit 2 にする。
    - assign 以外の role_suffix (workflow 等) は template の選択に使わないので、そのまま plan に写す。
    """
    kind = str(brief.get("kind", "")).strip()
    if kind not in BRIEF_KINDS:
        raise ValueError(f"brief.kind must be one of {list(BRIEF_KINDS)}, got {brief.get('kind')!r}")
    role_suffix = str(brief.get("role_suffix", "") or "").strip()
    if kind != "assign":
        return kind, role_suffix, KIND_TEMPLATE_FALLBACK[(kind, "")]
    explicit = bool(role_suffix)
    role = role_suffix or ASSIGN_DEFAULT_ROLE
    if role not in ASSIGN_ROLES:
        raise ValueError(
            f"brief.role_suffix={role_suffix!r} has no assign template (expected one of {list(ASSIGN_ROLES)})"
        )
    name = str(brief.get("skill_name", "") or "").strip()
    name_role = next((r for r in ASSIGN_ROLES if name.endswith(f"-{r}")), "")
    if name_role and name_role != role:
        source = "brief.role_suffix" if explicit else "role_suffix 未指定時の既定"
        raise ValueError(
            f"{source}={role!r} が skill_name={name!r} の role suffix -{name_role} と食い違う"
            " (brief に role_suffix を明示する)"
        )
    return kind, role, KIND_TEMPLATE_FALLBACK[(kind, role)]


def _responsibility_prompt_ids(brief: dict) -> list[str]:
    """prompts/<id>*.md を要求する responsibilities の id。

    prompt_required: false の項目は対象外 (skill-brief.schema.json と validate-build-trace.py の
    per_responsibility 集合と同じ規則)。id は glob に入るので schema の pattern で確かめる。
    """
    ids: list[str] = []
    for idx, item in enumerate(brief.get("responsibilities") or []):
        if isinstance(item, dict):
            required = item.get("prompt_required", True)
            if not isinstance(required, bool):
                raise ValueError(
                    f"brief.responsibilities[{idx}].prompt_required must be true or false, got {type(required).__name__}"
                )
            if required is False:
                continue
            rid = str(item.get("id", "")).strip()
        else:
            rid = str(item).strip()
        if not RESPONSIBILITY_ID_RE.match(rid):
            raise ValueError(
                f"brief.responsibilities[{idx}].id={rid!r} must match {RESPONSIBILITY_ID_PATTERN}"
            )
        ids.append(rid)
    return ids


def derive_plan(brief: dict, cli_flags: dict | None = None) -> dict:
    _require_brief_shape(brief)
    kind, role_suffix, template = resolve_template(brief)
    for idx, event in enumerate(brief.get("hook_events") or []):
        # 空の event は must_contain が空になり、どの hook-*.py でも満たしてしまう
        if not isinstance(event, str) or not event.strip():
            raise ValueError(f"brief.hook_events[{idx}] must be a non-empty string, got {event!r}")
    flags = derive_flags(brief, cli_flags)
    goal_seek_engine = derive_goal_seek_engine(brief)
    goal_seek_fork = derive_goal_seek_fork(brief) if flags["with_goal_seek"] else ""
    # engine 既定 = inline: 実在する依存グラフが brief で明示されない
    # loop kind へ task-graph engine と 4 スクリプトを予防的に同梱しない。
    # 明示値は常に優先。render-combinators._brief_requests_task_graph と同一規則。
    engine_defaulted = False
    if not goal_seek_engine and kind in LOOP_KINDS and flags["with_goal_seek"]:
        goal_seek_engine = "inline"
        engine_defaulted = True

    sections = _template_headings(TEMPLATES_DIR / template)
    for flag, patch in FLAG_PATCH.items():
        if flags.get(flag):
            for h in _patch_headings(patch):
                if h not in sections:
                    sections.append(h)

    deliverables: list[dict] = [
        {"id": "skill-md", "type": "file", "path": "SKILL.md", "source": "kind"},
    ]
    for rid in _responsibility_prompt_ids(brief) if flags["with_prompts"] else []:
        if rid:
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

    if flags["with_goal_seek"]:
        engine_source = (
            "default: minimum-sufficient inline (engine unset in brief)"
            if engine_defaulted
            else "brief.goal_seek.engine"
        )
        goal_seek = brief.get("goal_seek")
        fork_explicit = isinstance(goal_seek, dict) and bool(
            str(goal_seek.get("fork", "")).strip()
        )
        fork_source = (
            "brief.goal_seek.fork"
            if fork_explicit
            else (
                "default: needs_independent_context=true"
                if brief.get("needs_independent_context") is True
                else "default: minimum-sufficient inline context"
            )
        )
        deliverables.extend(
            [
                {
                    "id": "frontmatter:goal_seek.engine",
                    "type": "frontmatter-value",
                    "path": "goal_seek.engine",
                    "expected": goal_seek_engine,
                    "source": engine_source,
                },
                {
                    "id": "frontmatter:goal_seek.engine_profile",
                    "type": "frontmatter-value",
                    "path": "goal_seek.engine_profile",
                    "expected": (
                        "checklist-graph" if goal_seek_engine == "task-graph" else "goal-loop"
                    ),
                    "source": f"derived from goal_seek_engine={goal_seek_engine} ({engine_source})",
                },
                {
                    "id": "frontmatter:goal_seek.fork",
                    "type": "frontmatter-value",
                    "path": "goal_seek.fork",
                    "expected": goal_seek_fork,
                    "source": fork_source,
                },
            ]
        )

    if goal_seek_engine == "task-graph":
        engine_source = "brief.goal_seek.engine"
        deliverables.append(
            {
                "id": "frontmatter:goal_seek.full_task_spec_graph",
                "type": "frontmatter-value",
                "path": "goal_seek.full_task_spec_graph",
                "expected": "false",
                "source": "checklist-graph capability boundary",
            }
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
    elif goal_seek_engine == "inline":
        notes.append(
            "minimum-sufficient runtime: checklist と検証契約は維持し、"
            "task-graph engine 資産は同梱しない。依存グラフが必要な場合だけ "
            "brief.goal_seek.engine=task-graph を明示する。"
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


def _split_frontmatter(text: str) -> tuple[list[str] | None, str]:
    """先頭行の `---` から次の `---` 行までを frontmatter の行、残りを本文として返す。

    `text.split("---", 2)` だと `description: a---b` のような値の途中で切れるので、行単位で区切る。
    先頭が `---` でない・閉じる行が無いときは (None, text) (frontmatter 無し・本文は全体)。
    """
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None, text
    for idx in range(1, len(lines)):
        if lines[idx].rstrip() == "---":
            return lines[1:idx], "\n".join(lines[idx + 1 :])
    return None, text


def _parse_frontmatter_keys(text: str) -> set[str]:
    fm_lines, _ = _split_frontmatter(text)
    keys = set()
    for line in fm_lines or []:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:", line)
        if m:
            keys.add(m.group(1))
    return keys


def _frontmatter_value(text: str, key: str) -> str:
    fm_lines, _ = _split_frontmatter(text)
    for line in fm_lines or []:
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*(#.*)?$", line)
        if m:
            return m.group(1).strip().strip("'\"")
    return ""


_YAML_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")


def _frontmatter_allowed_tools(text: str) -> list[str]:
    """frontmatter の allowed-tools をツールの並びで返す。

    inline (`allowed-tools: Read, Skill`)・flow (`allowed-tools: [Read, Skill]`、複数行も可)・
    block list (`allowed-tools:` の次行から `  - Read`) のどれでも同じ並びになる。
    以前は 1 行の scalar だけ読み、flow や block の Skill / Agent を見落として acceptance_tier の
    宣言 static を通していた。
    """
    fm_lines = _split_frontmatter(text)[0] or []
    for idx, line in enumerate(fm_lines):
        m = re.match(r"^allowed-tools\s*:(.*)$", line)
        if not m:
            continue
        value = _YAML_COMMENT_RE.sub("", m.group(1)).strip()
        if value.startswith("[") and not value.endswith("]"):
            for cont in fm_lines[idx + 1 :]:
                value += " " + _YAML_COMMENT_RE.sub("", cont).strip()
                if value.endswith("]"):
                    break
        if value:
            return _split_tool_scalar(value)
        items: list[str] = []
        for cont in fm_lines[idx + 1 :]:
            if not cont.strip() or cont.lstrip().startswith("#"):
                continue
            item = re.match(r"^\s*-\s*(.*)$", cont)
            if not item:
                break  # 次の key
            tool = _YAML_COMMENT_RE.sub("", item.group(1)).strip()
            if tool:
                items.append(tool)
        return items
    return []


def _frontmatter_nested_value(text: str, dotted_key: str) -> str:
    """stdlib のみで 2 段 YAML scalar (例 goal_seek.engine) を読む。

    build-plan が要求する machine-readable 境界値専用。複雑な YAML 解釈は行わず、
    同一親 block 内の scalar だけを fail-closed に取得する。
    """
    fm_lines, _ = _split_frontmatter(text)
    bits = dotted_key.split(".")
    if fm_lines is None or len(bits) != 2:
        return ""
    parent, child = bits
    in_parent = False
    parent_indent = -1
    for line in fm_lines:
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


def preserve_update_runtime_profile(brief: dict, skill_dir: Path) -> dict:
    """update で brief が省略した runtime profile を現行生成物から引き継ぐ。

    新規生成の既定値を inline へ変えても、update 時に必要な
    task-graph/subagent を黙示ダウングレードしない。brief の明示値が常に優先。
    """
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_symlink() or not skill_md.is_file():
        raise ValueError(f"update target SKILL.md is missing or unsafe: {skill_md}")
    text = skill_md.read_text(encoding="utf-8")
    effective = copy.deepcopy(brief)
    goal_seek = effective.get("goal_seek")
    if goal_seek is None:
        goal_seek = {}
        effective["goal_seek"] = goal_seek
    if not isinstance(goal_seek, dict):
        raise ValueError("brief.goal_seek must be an object")

    for key, allowed in (
        ("engine", {"inline", "run-goal-seek", "task-graph"}),
        ("fork", {"inline", "subagent", "agent-team"}),
    ):
        if str(goal_seek.get(key, "")).strip():
            continue
        current = _frontmatter_nested_value(text, f"goal_seek.{key}")
        if current:
            if current not in allowed:
                raise ValueError(f"unknown current goal_seek.{key}: {current!r}")
            goal_seek[key] = current

    if "max_loops" not in goal_seek:
        current_max = _frontmatter_nested_value(text, "goal_seek.max_loops")
        if current_max:
            if not current_max.isdigit() or int(current_max) < 1:
                raise ValueError(f"invalid current goal_seek.max_loops: {current_max!r}")
            goal_seek["max_loops"] = int(current_max)
    return effective


def _body_sections(text: str) -> dict[str, int]:
    """SKILL.md 本文の ## 見出し → 見出し直下の本文行数 (非空・非見出し)。"""
    _, body = _split_frontmatter(text)
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


def _same_plugin_engine_refs(skill_md: Path) -> set[str]:
    """builder と同じ plugin の skill が script_refs で正本を指している engine script の名前。

    判定は lint-capability-graph-knowledge.py の canonical_engine_refs をそのまま使う。
    写しの無い本をここで受理し、lint では受理する (逆も) という食い違いを作らないため。
    lint を読めない・呼べないときは「参照なし」に倒さず CheckerDependencyError にする
    (欠落の指摘に見せかけず、判定できないことを exit 2 で返す)。
    """
    import importlib.util

    lint_path = Path(__file__).resolve().with_name("lint-capability-graph-knowledge.py")
    try:
        spec = importlib.util.spec_from_file_location("lint_capability_graph_knowledge_for_build_plan", lint_path)
        if spec is None or spec.loader is None:
            raise ImportError("module spec を作れない")
        lint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lint)
        same_plugin, _ = lint.canonical_engine_refs(skill_md, SKILL_ROOT / TASK_GRAPH_TEMPLATE_PREFIX)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — lint の中で何が起きても「判定できない」にする
        # NameError・KeyError・import 時の sys.exit も「参照なし」に倒さず exit 2 に寄せる
        raise CheckerDependencyError(
            f"依存する lint を使えない: {lint_path} ({type(exc).__name__}: {exc})"
        ) from exc
    if not isinstance(same_plugin, set) or not all(isinstance(name, str) for name in same_plugin):
        raise CheckerDependencyError(
            f"依存する lint の canonical_engine_refs が名前の set を返さない: {lint_path}"
        )
    return same_plugin


def _fold_event_name(text: str) -> str:
    """hook event 名とファイル名の比較用: 小文字にし `-` と `_` を落とす。"""
    return text.lower().replace("-", "").replace("_", "")


def _read_bytes(path: Path, error: type[Exception], what: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise error(f"{what}を読めない: {path} ({type(exc).__name__})") from exc


def check_plan(plan: dict, skill_dir: Path) -> list[str]:
    errs: list[str] = []
    if plan.get("goal_seek_engine") == "task-graph" and not plan.get("flags", {}).get(
        "with_goal_seek"
    ):
        errs.append(
            "task-graph engine requested but with_goal_seek=false: "
            "loop kind (run/wrap/delegate) 以外では checklist-graph を成功扱いできない"
        )

    if plan.get("goal_seek_engine") not in {"", "task-graph"}:
        stale_names = set(TASK_GRAPH_ENGINE_SCRIPTS) | {
            "ready-set-from-checklist.py",
            "self-reflect-append.py",
            "record-capability-graph-knowledge.py",
        }
        stale = [
            f"scripts/{name}"
            for name in sorted(stale_names)
            if (skill_dir / "scripts" / name).exists()
            or (skill_dir / "scripts" / name).is_symlink()
        ]
        if stale:
            errs.append(
                f"goal_seek.engine={plan.get('goal_seek_engine')} だが task-graph engine 資産が残存: {stale}"
                " (update では canonical bytes のみ除去し、改変済み/symlink は fail-closed で手動判断)"
            )
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_symlink():
        # update (preserve_update_runtime_profile) と同じく、symlink の先は検査しない (exit 2)
        raise ValueError(f"check target SKILL.md is unsafe (symlink): {skill_md}")
    if not skill_md.exists():
        return [f"SKILL.md not found: {skill_md}"]
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # 有るのに読めない SKILL.md (dir・非 UTF-8・権限) は検査できないので、欠落の指摘ではなく不正入力にする
        raise ValueError(f"SKILL.md を UTF-8 のテキストとして読めない: {skill_md} ({type(exc).__name__})") from exc

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
    same_plugin_refs: set[str] | None = None
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
                # builder と同じ plugin の skill は、写しの代わりに script_refs で正本を指してよい
                # (lint-capability-graph-knowledge.py / lint-skill-runtime-profiles.py と同じ判定)。
                if same_plugin_refs is None:
                    same_plugin_refs = _same_plugin_engine_refs(skill_md)
                if template.parent == SKILL_ROOT / TASK_GRAPH_TEMPLATE_PREFIX and dest.name in same_plugin_refs:
                    continue
                errs.append(f"missing deliverable: {path} (source={d.get('source')})")
            elif not template.is_file():
                errs.append(f"template source not found: {template}")
            elif _read_bytes(dest, ValueError, "生成物") != _read_bytes(
                template, CheckerDependencyError, "engine 正本"
            ):
                errs.append(
                    f"byte drift: {path} != {d.get('template')} "
                    "(task-graph engine assets must be unmodified template copies)"
                )
        elif dtype == "dir":
            if not (skill_dir / path).is_dir():
                errs.append(f"missing deliverable dir: {path}/ (source={d.get('source')})")
        elif dtype == "glob":
            matches = sorted(skill_dir.glob(path))
            # brief の綴り (PreCompact / pre_compact / pre-compact) とファイル名の綴りを同じ規則で畳む
            need = _fold_event_name(str(d.get("must_contain", "")))
            if need:
                matches = [
                    p for p in matches
                    if need in _fold_event_name(p.name)
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
        fm_tools = _frontmatter_allowed_tools(text)
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
    assert plan["flags"]["build_stage"] == "draft"
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
    # prompt_required: false の責務は prompts/<id>*.md を求めない
    p = derive_plan({"kind": "run", "responsibilities": [{"id": "R1"}, {"id": "R2", "prompt_required": False}]})
    assert [d["id"] for d in p["required_deliverables"] if d["id"].startswith("prompt:")] == ["prompt:R1"]

    # assign の role_suffix 未指定は generator の template。allowed-tools は inline・flow・block を同じに読む
    assert derive_plan({"kind": "assign"})["template"] == "assign-generator.md"
    for fm in ("allowed-tools: Read, Skill", "allowed-tools: [Read, Skill]", "allowed-tools:\n  - Read\n  - Skill"):
        assert _frontmatter_allowed_tools(f"---\n{fm}\n---\n") == ["Read", "Skill"], fm

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
    print("OK: validate-build-plan self-test (8 groups)")
    return 0


DEFAULT_BRIEF = "eval-log/skill-brief.json"


def _build_parser() -> argparse.ArgumentParser:
    # 未知の引数・値の無い option は argparse が usage error (exit 2) にする。略記は受け付けない
    # (--chek を --check と読み替えたり、黙って無視して plan を出したりしない)。
    parser = argparse.ArgumentParser(
        prog="validate-build-plan.py",
        description="skill-brief から build-plan を決定論導出し (既定)、--check で生成物と突合する。",
        epilog="exit: 0=OK / 1=--check で欠落あり / 2=usage error・不正な入力",
        allow_abbrev=False,
    )
    parser.add_argument("--brief", help=f"skill-brief の JSON object (省略時は {DEFAULT_BRIEF})")
    parser.add_argument("--out", help="plan JSON の保存先 (同じ dir の一時ファイルに書いてから置き換える)")
    parser.add_argument("--check", action="store_true", help="--skill-dir の生成物が plan を満たすか突合する")
    parser.add_argument("--skill-dir", help="--check と --mode update で読む生成先 skill dir")
    parser.add_argument("--mode", help="create (既定) | update")
    parser.add_argument("--stage", help="draft (既定) | release")
    parser.add_argument("--flags", help="明示 opt-out / opt-in の JSON object")
    parser.add_argument("--self-test", action="store_true", help="組み込みの self-test を走らせる")
    return parser


def _write_atomic(path: Path, text: str) -> None:
    """同じ dir の一時ファイルに書き切ってから置き換える (途中で落ちても前の中身か新しい中身のどちらか)。

    一時ファイルは O_EXCL で作り、mode は write_text と同じく 0o666 から umask を引いた値になる。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    if args.self_test:
        return _self_test()
    try:
        return _run(args)
    except RecursionError:
        # 入れ子の深い JSON (brief・--flags) は json.loads・deepcopy・repr のどこでも RecursionError になる。
        # どこで起きても書く前 (--out の置き換え前) なので、traceback でなく不正入力として止める
        print("invalid input: JSON の入れ子が深すぎる (brief か --flags)", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    check = args.check
    skill_dir = args.skill_dir
    out = args.out
    mode = args.mode or "create"
    build_stage = args.stage

    # usage の誤りは brief を読む前・何かを書く前に止める (以前は --check --out で --skill-dir が無いと
    # plan を書いてから usage error にし、--out '' は書かずに exit 0 にしていた)
    if out is not None and not out.strip():
        print("usage: --out には空でないパスが必要", file=sys.stderr)
        return 2
    if check and not skill_dir:
        print("usage: --check には --skill-dir <dir> が必要", file=sys.stderr)
        return 2
    if mode not in {"create", "update"}:
        print("invalid input: mode must be create or update", file=sys.stderr)
        return 2
    if mode == "update" and not skill_dir:
        print("invalid input: --mode update requires --skill-dir <existing-skill-dir>", file=sys.stderr)
        return 2

    bp = Path(DEFAULT_BRIEF if args.brief is None else args.brief)  # --brief '' を既定に読み替えない
    if not bp.exists():
        if args.brief is not None or check or out is not None:
            # 明示した brief が無い・--check / --out に要る brief が無い: 検査も保存もしないまま
            # exit 0 にすると、Step 4 や contract の checker が PASS と記録しうるので不正入力にする
            print(f"invalid input: brief not found: {bp}", file=sys.stderr)
            return 2
        print(
            f"NOTE: brief not found ({bp}) — フラグ明示の単発 build とみなし skip。"
            "量産経路 (run-skill-create) では brief が必須のため本ゲートが有効になる。",
        )
        return 0
    try:
        brief = _load_brief(bp)
        if mode == "update":
            brief = preserve_update_runtime_profile(brief, Path(skill_dir))
        cli_flags = json.loads(args.flags) if args.flags else {}
        if not isinstance(cli_flags, dict):
            raise ValueError(f"--flags must be a JSON object, got {type(cli_flags).__name__}")
        if build_stage is not None:
            cli_flags["build_stage"] = build_stage
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2

    try:
        plan = derive_plan(brief, cli_flags)
    except CheckerDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2
    plan_text = json.dumps(plan, ensure_ascii=False, indent=2)

    errs: list[str] = []
    if check:
        # 突合を先に済ませる。読めない生成物・依存で exit 2 になるときは --out を書き換えない
        try:
            errs = check_plan(plan, Path(skill_dir))
        except CheckerDependencyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except (OSError, ValueError) as exc:
            print(f"invalid input: {exc}", file=sys.stderr)
            return 2

    if out is not None:
        try:
            _write_atomic(Path(out), plan_text + "\n")
        except OSError as exc:
            print(f"invalid input: --out に書けない: {out} ({type(exc).__name__}: {exc})", file=sys.stderr)
            return 2

    if not check:
        print(plan_text)
        return 0

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
