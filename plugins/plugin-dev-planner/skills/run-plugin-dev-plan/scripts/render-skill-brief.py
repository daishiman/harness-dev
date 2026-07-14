#!/usr/bin/env python3
# /// script
# name: render-skill-brief
# purpose: component-inventory.json の skill component を run-skill-create が消費する skill-brief JSON へ決定論射影する (planner 固有キー除去 + skill_kind→kind 写像 + 実 schema との required/余剰キー突合)。
# inputs:
#   - argv: --inventory FILE --component ID [--out PATH] | --self-test
# outputs:
#   - stdout: skill-brief JSON (--out 省略時) / OK サマリ
#   - stderr: 非 skill 射影・schema required 欠落・余剰キー violation / standalone 開示
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: --out 指定パスのみ (省略時 none)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""inventory の skill component から skill-brief JSON を決定論射影する。

handoff routes[].build_args.brief_path (plan_dir 相対・推奨 briefs/skill-brief-<id>.json) が
宣言する brief 実体を生成する renderer。射影は 3 段:

  (1) planner 固有キー (build 軸 routing / plan 品質ゲート / sibling coupling) を除去する
      (生成器入力である goal_seek は skill-brief へ保持する)
  (2) skill_kind→kind へ写像する (inventory は component_kind との衝突回避で skill_kind を
      canonical に携帯する。解決は specfm._skill_kind_of と同一)
  (3) 実 schema (plugins/harness-creator/skills/run-skill-create/schemas/skill-brief.schema.json
      additionalProperties:false) と突合し base required + allOf 条件付き required の充足と
      余剰キー 0 を自己検証する。単独 install 等で実 schema が無ければ突合を skip し
      standalone を stderr へ情報開示する (fail-open の明示)

skill-brief の語彙は実 schema を正本とする引用形連携で、harness-creator の解決ロジックは
再実装しない (base required 14 の複製は specfm.SKILL_BRIEF_FIELDS として二重保持台帳に登録済・
本 script はそれを import する)。突合は required 充足 + 余剰キー 0 の床のみで、型/pattern/
minItems 等の全量検証は消費側 run-skill-create の schema 検証に残す (二層分離)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# skill-brief.schema.json (additionalProperties:false) の properties に無い planner 固有キー。
# build 軸 routing / plan 品質ゲート / sibling coupling は plan 側
# (inventory/handoff) に残し brief へ写さない。goal_seek は生成器が
# inline/task-graph 変種を決める必要入力なので schema どおり pass-through する。
# skill_kind/kind は (2) の rename 対象として project_brief が別扱いする。
PLANNER_ONLY_KEYS = frozenset({
    "id", "component_kind", "name", "depends_on", "couples_with", "spec", "status",
    "build_target", "builder", "builder_status", "build_kind", "placement_scope", "gap_ref",
    "quality_gates", "harness_coverage", "entities_covered", "applicability",
    "prompt_layer", "combinators", "feedback_contract",
})
# 実 schema (owner) の plugins/ 配下相対パス。
SCHEMA_REL = "harness-creator/skills/run-skill-create/schemas/skill-brief.schema.json"


def find_schema_path() -> Path | None:
    """実 schema を script 位置起点 (cwd 非依存) で解決する。無ければ None (standalone)。"""
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if len(here.parents) > 4:
        candidates.append(here.parents[4] / SCHEMA_REL)  # <repo>/plugins/ 起点
    candidates.append(Path.cwd() / "plugins" / SCHEMA_REL)  # repo-root cwd fallback
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def project_brief(comp: dict) -> dict:
    """skill component を brief dict へ決定論射影する (planner キー除去 + skill_kind→kind)。

    キー順は base required 14 (specfm.SKILL_BRIEF_FIELDS 順) → 残余キー辞書順で安定させる
    (同一 inventory → byte 同一 brief の再現性)。
    """
    ck = str(comp.get("component_kind", "")).strip()
    if ck != "skill":
        raise ValueError(f"component_kind={ck!r} は skill-brief 射影の対象外 (skill のみ)")
    kind = specfm._skill_kind_of(comp)
    if not kind:
        raise ValueError("skill_kind/kind が空で brief の kind を解決できない")
    passthrough = {
        k: v for k, v in comp.items()
        if k not in PLANNER_ONLY_KEYS and k not in ("kind", "skill_kind")
    }
    brief: dict = {}
    for field in specfm.SKILL_BRIEF_FIELDS:
        if field == "kind":
            brief["kind"] = kind
        elif field in passthrough:
            brief[field] = passthrough.pop(field)
    brief.update(sorted(passthrough.items()))
    return brief


def _if_matches(brief: dict, if_clause: dict) -> bool:
    """allOf の if 節 (properties const/enum [+ required]) を最小評価する。

    property 欠落は JSON Schema 意味論どおり vacuously true (if は成立し then が適用される)。
    """
    for key in if_clause.get("required", []):
        if key not in brief:
            return False
    for key, cond in if_clause.get("properties", {}).items():
        if key not in brief:
            continue
        if "const" in cond and brief[key] != cond["const"]:
            return False
        if "enum" in cond and brief[key] not in cond["enum"]:
            return False
    return True


def validate_against_schema(brief: dict, schema: dict) -> list[str]:
    """brief を実 schema と突合する (base+allOf required 充足 / additionalProperties:false の余剰キー 0)。"""
    errors: list[str] = []
    props = set(schema.get("properties", {}))
    for key in schema.get("required", []):
        if key not in brief:
            errors.append(f"実 schema base required 欠落: {key}")
    extras = sorted(set(brief) - props)
    if extras:
        errors.append(
            f"実 schema properties 外の余剰キーが残る (additionalProperties:false で reject される): {extras}"
        )
    for clause in schema.get("allOf", []):
        if not isinstance(clause, dict) or not _if_matches(brief, clause.get("if", {})):
            continue
        for key in clause.get("then", {}).get("required", []):
            if key not in brief or brief[key] in (None, "", []):
                errors.append(f"実 schema allOf 条件付き required 欠落: {key}")
    return errors


# ─────────────────────────── self-test (埋め込み最小 fixture) ───────────────────────────
def _self_test() -> tuple[int, list[str]]:
    """specfm skeleton fixture で射影・kind 解決・非 skill 拒否・schema 突合を自己検査する。"""
    msgs: list[str] = []

    comp = specfm.minimal_frontmatter("skill", spec_id="C01", skill_kind="run")
    comp.update({
        "name": "run-sample", "skill_kind": "run", "builder": "run-skill-create",
        "build_kind": "skill", "build_target": "plugins/x/skills/run-sample/",
    })
    brief = project_brief(comp)
    leaked = sorted((set(brief) & PLANNER_ONLY_KEYS) | ({"skill_kind"} & set(brief)))
    if leaked:
        msgs.append(f"planner 固有キーが brief へ漏れた: {leaked}")
    missing = [f for f in specfm.SKILL_BRIEF_FIELDS if f not in brief]
    if missing:
        msgs.append(f"base required (SKILL_BRIEF_FIELDS) が brief に欠落: {missing}")
    if brief.get("kind") != "run":
        msgs.append(f"skill_kind→kind 写像が不正: {brief.get('kind')!r}")

    # 旧 golden 互換: skill_kind 無しで kind のみ携帯しても解決できる (fallback)
    legacy = {k: v for k, v in comp.items() if k != "skill_kind"}
    if project_brief(legacy).get("kind") != "run":
        msgs.append("kind fallback (skill_kind 欠落時) の解決が不正")

    # 非 skill component は明示エラー
    try:
        project_brief(specfm.minimal_frontmatter("script", spec_id="C09"))
        msgs.append("非 skill component の射影が明示エラーにならない")
    except ValueError:
        pass

    # 実 schema が在れば skeleton 射影が required 充足 + 余剰キー 0 を満たす (無ければ standalone skip)
    schema_path = find_schema_path()
    if schema_path is not None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errs = validate_against_schema(brief, schema)
        if errs:
            msgs.append(f"skeleton 射影が実 schema 突合に落ちる: {errs}")

    return (1 if msgs else 0), msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="inventory の skill component から skill-brief JSON を射影する")
    ap.add_argument("--inventory", default=None, help="component-inventory.json")
    ap.add_argument("--component", default=None, help="component id (例 C01)")
    ap.add_argument("--out", default=None, help="出力先 (省略時 stdout。推奨 <plan-dir>/briefs/skill-brief-<id>.json)")
    ap.add_argument("--self-test", action="store_true", help="埋め込み skeleton fixture で射影と schema 突合を自己検査する")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = _self_test()
        if code == 0:
            sys.stdout.write("OK: render-skill-brief の射影と schema 突合が期待どおり\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    if not args.inventory or not args.component:
        sys.stderr.write("usage: render-skill-brief.py --inventory FILE --component ID [--out PATH] | --self-test\n")
        return 2
    inventory_path = Path(args.inventory)
    if not inventory_path.is_file():
        sys.stderr.write(f"component-inventory.json が見つからない: {inventory_path}\n")
        return 2
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"component-inventory JSON parse error: {exc}\n")
        return 2
    components = data.get("components") if isinstance(data, dict) else None
    comp = next(
        (c for c in (components if isinstance(components, list) else [])
         if isinstance(c, dict) and str(c.get("id", "")).strip() == args.component),
        None,
    )
    if comp is None:
        sys.stderr.write(f"component {args.component!r} が components[] に存在しない: {inventory_path}\n")
        return 2

    try:
        brief = project_brief(comp)
    except ValueError as exc:
        sys.stderr.write(f"[{args.component}] {exc}\n")
        return 1

    schema_path = find_schema_path()
    if schema_path is None:
        sys.stderr.write(
            f"standalone: 実 schema (plugins/{SCHEMA_REL}) が見つからないため required/余剰キー突合を "
            "skip した (消費側 run-skill-create の schema 検証が最終防衛線)\n"
        )
    else:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"skill-brief.schema.json parse error: {exc}\n")
            return 2
        errors = validate_against_schema(brief, schema)
        if errors:
            for e in errors:
                sys.stderr.write(f"[{args.component}] {e}\n")
            return 1

    payload = json.dumps(brief, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        sys.stdout.write(f"OK: skill-brief を射影した ({args.component} → {out_path})\n")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
