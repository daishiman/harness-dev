#!/usr/bin/env python3
"""内容 adequacy 評価成果物の存在を機械検査する (offline, LLM 不実行)。

役割境界:
  - 機械層: SKILL.md が変更された skill について eval-log/<plugin>/<skill>/content-review/
            配下に elegance-verdict.json + rubric-verdict.json が存在し verdict=PASS であることを検査
  - LLM 層 (本 lint の対象外): 評価実行自体はローカル Claude Code で run-elegant-review +
            assign-skill-design-evaluator を SubAgent 起動して行う (リモート CI コスト回避)

ref kind は除外する。harness-creator 自身は自己改善(dogfooding)対象なので CI/pre-push では除外しない
(dogfooding 境界の SSOT = scripts/feedback_contract_ssot.py:is_content_review_exempt)。

Usage:
  python3 scripts/lint-content-review.py --changed-only [--base origin/main]
  python3 scripts/lint-content-review.py --all
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
EVAL_LOG = ROOT / "eval-log"

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402
REQUIRED_VERDICTS = ("elegance-verdict.json", "rubric-verdict.json")
# dogfooding 除外境界は SSOT (FC.is_content_review_exempt) が単一正本。
# content-review は生成器自身も除外しない (常に False) ため集合は空のままだが、
# 判定は SSOT 述語へ委譲しリテラル散在を排除する。
EXEMPT_KINDS = {"ref"}


def _git_changed_skills(base):
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return set()
    skills = set()
    pat = re.compile(r"^plugins/([^/]+)/skills/([^/]+)/SKILL\.md$")
    for line in diff.splitlines():
        m = pat.match(line.strip())
        if m:
            skills.add((m.group(1), m.group(2)))
    return skills


def _all_skills():
    skills = set()
    if not PLUGINS_DIR.exists():
        return skills
    for plugin_dir in PLUGINS_DIR.iterdir():
        if not plugin_dir.is_dir():
            continue
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if (s / "SKILL.md").is_file():
                # symlink は対象外 (実体側で評価される)
                if s.is_symlink():
                    continue
                skills.add((plugin_dir.name, s.name))
    return skills


def _read_kind(plugin, skill):
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    if not md.is_file():
        return None
    try:
        text = md.read_text(encoding="utf-8")
    except OSError:
        return None
    return FC.read_kind(text)  # kind 抽出は SSOT の単一実装に委譲 (lint 間の乖離を排除)


def _skill_sha256(plugin, skill):
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    try:
        return hashlib.sha256(md.read_bytes()).hexdigest()
    except OSError:
        return None


def _expected_review_kind(fname):
    if fname.startswith("elegance-"):
        return "elegance"
    if fname.startswith("rubric-"):
        return "rubric"
    return None


def _check_verdict(path, plugin, skill, fname):
    if not path.is_file():
        return "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"invalid-json: {exc}"
    for key in ("target", "review_kind", "verdict", "reviewer", "reviewed_at", "iterations", "feedback_loop"):
        if key not in data:
            return f"schema: missing {key}"
    target = data.get("target")
    if not isinstance(target, dict):
        return "schema: target must be object"
    if target.get("plugin") != plugin or target.get("skill") != skill:
        return (
            "target-mismatch: "
            f"expected {plugin}/{skill}, got {target.get('plugin')}/{target.get('skill')}"
        )
    expected_kind = _expected_review_kind(fname)
    if expected_kind and data.get("review_kind") != expected_kind:
        return f"review_kind={data.get('review_kind')} expected={expected_kind}"
    verdict = data.get("verdict")
    if verdict != "PASS":
        return f"verdict={verdict}"
    current_sha = _skill_sha256(plugin, skill)
    recorded_sha = target.get("skill_md_sha256")
    if not recorded_sha:
        return "schema: target.skill_md_sha256 missing"
    if current_sha and recorded_sha != current_sha:
        return f"stale-sha: {recorded_sha} != current {current_sha}"
    if not isinstance(data.get("iterations"), int):
        return "schema: iterations must be integer"
    feedback_loop = data.get("feedback_loop")
    if not isinstance(feedback_loop, dict):
        return "schema: feedback_loop must be object"
    criteria = feedback_loop.get("criteria_evaluated")
    if not isinstance(criteria, list) or not criteria:
        return "schema: feedback_loop.criteria_evaluated must be non-empty array"
    if len(criteria) != len(set(criteria)):
        return "schema: feedback_loop.criteria_evaluated has duplicates"
    if not isinstance(feedback_loop.get("iteration_limit"), int):
        return "schema: feedback_loop.iteration_limit must be integer"
    if not isinstance(feedback_loop.get("iteration"), int):
        return "schema: feedback_loop.iteration must be integer"
    if feedback_loop.get("loop_scope") not in {"inner", "outer", "both"}:
        return "schema: feedback_loop.loop_scope invalid"
    if not isinstance(feedback_loop.get("positive_feedback"), list):
        return "schema: feedback_loop.positive_feedback must be array"
    if not isinstance(feedback_loop.get("negative_feedback"), list):
        return "schema: feedback_loop.negative_feedback must be array"
    if feedback_loop.get("next_action") not in {"none", "improve", "re_evaluate", "human_review"}:
        return "schema: feedback_loop.next_action invalid"
    if not isinstance(feedback_loop.get("hook_trigger"), str) or not feedback_loop.get("hook_trigger").strip():
        return "schema: feedback_loop.hook_trigger missing"
    expected = _expected_criteria_ids(plugin, skill)
    if expected:
        missing = expected - set(criteria)
        if missing:
            return f"criteria-missing: {sorted(missing)}"
    return None


def _expected_criteria_ids(plugin, skill):
    """期待される feedback_contract.criteria id 集合を返す。

    正本は **量産先 SKILL.md frontmatter の feedback_contract**(携帯する評価基準)。
    frontmatter に無い場合のみ後方互換で build trace(skill-local→global)を best-effort
    で読む。どこにも無ければ空集合を返す(verdict 自体の必須構造のみ検査)。
    """
    # 1) frontmatter 正本 (SSOT)
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    try:
        fc = FC.extract_frontmatter_feedback_contract(md.read_text(encoding="utf-8"))
        ids = FC.criteria_ids(fc.get("criteria")) if isinstance(fc, dict) else set()
        if ids:
            return ids
    except OSError:
        pass

    # 2) 後方互換: build trace (世代差で skill-local→global)
    candidates = [
        EVAL_LOG / plugin / skill / "skill-build-trace.json",
        EVAL_LOG / "skill-build-trace.json",
    ]
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if path.name == "skill-build-trace.json" and data.get("skill_name") not in {None, skill}:
            continue
        fc = data.get("feedback_contract")
        if not isinstance(fc, dict):
            continue
        ids = FC.criteria_ids(fc.get("criteria"))
        if ids:
            return ids
    return set()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--changed-only", action="store_true")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()

    targets = _git_changed_skills(args.base) if args.changed_only else _all_skills()
    # filter
    filtered = []
    for plugin, skill in sorted(targets):
        if FC.is_content_review_exempt(plugin):
            continue
        kind = _read_kind(plugin, skill)
        if kind in EXEMPT_KINDS:
            continue
        # SKILL.md が削除された変更も target に含まれるので存在チェック
        if not (PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md").is_file():
            continue
        filtered.append((plugin, skill))

    if not filtered:
        print("[OK] content-review lint: no target skill")
        return 0

    violations = []
    for plugin, skill in filtered:
        review_dir = EVAL_LOG / plugin / skill / "content-review"
        for fname in REQUIRED_VERDICTS:
            err = _check_verdict(review_dir / fname, plugin, skill, fname)
            if err:
                violations.append(f"{plugin}/{skill}: {fname} {err}")

    if violations:
        print(f"[FAIL] content-review lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("Fix: ローカル Claude Code で assign-skill-design-evaluator の focused combined review を")
        print("     1 context 実行し、4条件/rubric を2 verdictへ分離保存してください。")
        print("     完全な run-elegant-review + rubric evaluator は exhaustive 明示時だけです。")
        print("     手順詳細: plugins/harness-creator/skills/run-build-skill/references/content-review-protocol.md")
        return 1

    print(f"[OK] content-review lint: {len(filtered)} skill(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
