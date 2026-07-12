#!/usr/bin/env python3
# /// script
# name: lint-feedback-contract
# purpose: 量産先 loop-kind スキルが frontmatter に per-skill 評価基準(feedback_contract)を携帯することを強制する。
# inputs:
#   - argv: --changed-only [--base origin/main] | --all | --self-test
# outputs:
#   - stdout: OK/FAIL サマリ
#   - exit: 0=PASS / 1=violation / 2=usage
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""loop 実行系スキル(kind=run/wrap/delegate)の SKILL.md frontmatter に
`feedback_contract.criteria` が存在し SSOT 制約を満たすことを機械検査する。

これは「harness-creator が量産するスキルへ評価基準を毎回 frontmatter に焼き込む」
仕組みの fail-closed ゲート。criteria の中身は各スキル固有のため AI が brief から
導出するが(内容判断の自由度)、欠落・不正は本 lint が CI/pre-push で必ず落とす(機構保証)。

ref/assign/agent 等の非ループ系は対象外。skip_reason での N/A escape は SSOT の
FEEDBACK_SKIP_KINDS (ref/assign) 限定で、loop-kind は skip_reason では免除されない
(criteria を実際に整備させる。任意 kind の skip_reason 素通し穴 PF-ABST の封鎖)。

live-trial ratchet (D7 P2): acceptance_tier=live と導出される loop-kind skill は
OUT (loop_scope=outer) criteria に verify_by: live-trial を最低1件携帯すること。
tier 導出は run-build-skill/scripts/validate-build-plan.py の derive_acceptance_tier
を importlib 再利用 (二重実装禁止)。既存 skill は live-trial-criteria-baseline.json
で WARN 免除 (baseline 追記禁止 = 新規 build のみ FAIL する ratchet)。

criteria 制約の正本: repo-root scripts/feedback_contract_ssot.py。

Usage:
  python3 scripts/lint-feedback-contract.py --changed-only [--base origin/main]
  python3 scripts/lint-feedback-contract.py --all
  python3 scripts/lint-feedback-contract.py --self-test
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402

# 評価基準を frontmatter に携帯すべき loop 実行系。ref/assign/agent 等は対象外。
LOOP_KINDS = FC.FEEDBACK_LOOP_KINDS

# tier 導出正本の所在は PLUGINS_DIR と独立に固定する (テストが PLUGINS_DIR を
# tmp へ差し替えても derive_acceptance_tier のロード元は実 repo のまま。
# lint-live-trial-verdict.py の HARNESS_SKILL_DIR と同じ流儀)。
_BUILD_PLAN_PATH = (
    ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
    / "scripts" / "validate-build-plan.py"
)
# live-trial ratchet の既存免除 (baseline)。ファイル不在 = 免除ゼロ (fail-closed)。
BASELINE_PATH = ROOT / "scripts" / "live-trial-criteria-baseline.json"


def _load_derive_acceptance_tier():
    spec = importlib.util.spec_from_file_location("validate_build_plan", _BUILD_PLAN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.derive_acceptance_tier


derive_acceptance_tier = _load_derive_acceptance_tier()


def _load_baseline() -> set[str]:
    """baseline の "plugin/skill" 集合。呼び出し毎に読む (テスト差し替え可能)。"""
    if not BASELINE_PATH.is_file():
        return set()
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {str(e) for e in data.get("exempt", [])}


def _git_changed_skills(base: str) -> set[tuple[str, str]]:
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return set()
    pat = re.compile(r"^plugins/([^/]+)/skills/([^/]+)/SKILL\.md$")
    out: set[tuple[str, str]] = set()
    for line in diff.splitlines():
        m = pat.match(line.strip())
        if m:
            out.add((m.group(1), m.group(2)))
    return out


def _all_skills() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not PLUGINS_DIR.exists():
        return out
    for plugin_dir in PLUGINS_DIR.iterdir():
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if s.is_symlink():  # symlink は実体側で検査
                continue
            if (s / "SKILL.md").is_file():
                out.add((plugin_dir.name, s.name))
    return out


def _read_kind(text: str) -> str | None:
    return FC.read_kind(text)  # kind 抽出は SSOT の単一実装に委譲 (lint 間の正規表現乖離を排除)


def _read_allowed_tools(text: str) -> list[str]:
    """frontmatter の allowed-tools を flow ([a, b] / a, b) とブロックリスト両形式で抽出。"""
    if not text.startswith("---"):
        return []
    fm_lines = text.split("\n---", 1)[0].splitlines()
    for i, line in enumerate(fm_lines):
        m = re.match(r"^allowed-tools:\s*(.*)$", line)
        if not m:
            continue
        inline = re.sub(r"\s+#.*$", "", m.group(1)).strip()
        if inline:
            return [t.strip().strip("'\"") for t in inline.strip("[]").split(",") if t.strip()]
        items: list[str] = []
        for nxt in fm_lines[i + 1:]:
            mi = re.match(r"^\s+-\s+(.+?)\s*$", nxt)
            if mi:
                items.append(re.sub(r"\s+#.*$", "", mi.group(1)).strip().strip("'\""))
            elif nxt.strip():  # 別キー到達でブロック終了
                break
        return items
    return []


def _live_trial_ratchet(
    plugin: str, skill: str, kind: str, text: str, fc: dict, baseline: set[str]
) -> tuple[list[str], list[str]]:
    """D7 P2 ratchet: live 導出 skill の OUT criteria に verify_by: live-trial を要求。

    返り値は (violations, warnings)。tier 導出はディスク実体の静的信号
    (frontmatter kind/allowed-tools + scripts/hook-*.py 実在) から行い、正本
    derive_acceptance_tier (validate-build-plan.py) に委譲する。criteria 欠落自体は
    _check_skill の既存 violation が報告するため、ここでは criteria list がある
    skill のみ検査する (二重報告回避)。
    """
    skill_dir = PLUGINS_DIR / plugin / "skills" / skill
    has_hooks = bool(list(skill_dir.glob("scripts/hook-*.py")))
    if derive_acceptance_tier(kind, has_hooks, _read_allowed_tools(text)) != "live":
        return [], []
    criteria = fc.get("criteria")
    if not isinstance(criteria, list):
        return [], []
    ok = any(
        isinstance(c, dict)
        and str(c.get("loop_scope", "")).strip() == "outer"
        and str(c.get("verify_by", "")).strip() == "live-trial"
        for c in criteria
    )
    if ok:
        return [], []
    msg = (
        f"{plugin}/{skill}: acceptance_tier=live 導出 (hooks 配線 or allowed-tools の "
        "Skill/Agent/AskUserQuestion) だが feedback_contract.criteria に "
        "loop_scope=outer かつ verify_by: live-trial が1件もない"
    )
    if f"{plugin}/{skill}" in baseline:
        return [], [msg + " (baseline 免除中 = 既存 skill。criteria 追記で baseline から削除可)"]
    return [
        msg + " (D7 ratchet: 新規 build は必須。tier 導出正本 = "
        "run-build-skill/scripts/validate-build-plan.py derive_acceptance_tier。"
        "baseline への追記は禁止)"
    ], []


def _fallback_warnings(plugin: str, skill: str, fc: dict) -> list[str]:
    """criteria が brief 非導出のフォールバック既定 (同語反復) のままなら WARN を返す。

    機構 (lint) は criteria の「存在」を fail-closed 保証するが「内容の per-skill 性」は
    LLM 層の責務。ただしフォールバック既定の残存だけは機械検出して可視化し、
    content-review が見落とした空洞 criteria を CI で surface する (Goodhart 対策)。
    """
    criteria = fc.get("criteria")
    if not isinstance(criteria, list):
        return []
    warns: list[str] = []
    for item in criteria:
        if isinstance(item, dict) and FC.is_fallback_text(item.get("text")):
            warns.append(
                f"{plugin}/{skill}: criteria[{item.get('id', '?')}] が brief 非導出の"
                " フォールバック既定文のまま (per-skill 評価基準へ具体化推奨)"
            )
    return warns


def _check_skill(plugin: str, skill: str) -> list[str]:
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    if not md.is_file():
        return []
    text = md.read_text(encoding="utf-8")
    kind = _read_kind(text)
    if kind not in LOOP_KINDS:
        return []  # 非ループ系は評価基準携帯の対象外

    fc = FC.extract_frontmatter_feedback_contract(text)
    if not isinstance(fc, dict):
        return [
            f"{plugin}/{skill}: frontmatter に feedback_contract がありません "
            f"(kind={kind} は loop 実行系。brief.goal/Checklist から criteria を導出し "
            "frontmatter へ焼き込むこと。skip_reason での N/A escape は "
            f"kind={sorted(FC.FEEDBACK_SKIP_KINDS)} のみ)"
        ]
    skip_reason = str(fc.get("skip_reason", "")).strip()
    criteria = fc.get("criteria")
    if (not isinstance(criteria, list) or not criteria) and skip_reason:
        # skip_reason の N/A escape は SSOT の FEEDBACK_SKIP_KINDS (ref/assign) 限定。
        # ここへ到達する kind は LOOP_KINDS のみのため、loop 実行系の skip_reason は
        # criteria 必須の免除にならず violation (任意 kind の素通し穴を封鎖)。
        if kind in FC.FEEDBACK_SKIP_KINDS:
            return []  # 明示的 N/A escape (ref/assign)
        return [
            f"{plugin}/{skill}: kind={kind} は loop 実行系のため feedback_contract."
            "skip_reason では criteria 必須を免除できません (escape は "
            f"kind={sorted(FC.FEEDBACK_SKIP_KINDS)} 限定。inner/outer criteria を整備すること)"
        ]
    errs = FC.validate_criteria(
        criteria, require_both_scopes=True, prefix=f"{plugin}/{skill}: feedback_contract.criteria"
    )
    return errs


def _self_test() -> int:
    """合成 fixture で live-trial ratchet (D7 P2) の 正/負/免除/非live を自己検査。"""
    global PLUGINS_DIR, BASELINE_PATH
    import tempfile

    # allowed-tools パーサ: flow / ブロックリスト両形式
    assert _read_allowed_tools("---\nallowed-tools: [Read, Bash(python3 *)]\n---\n") == [
        "Read", "Bash(python3 *)"
    ]
    assert _read_allowed_tools(
        "---\nallowed-tools:\n  - Read\n  - Agent\nkind: run\n---\n"
    ) == ["Read", "Agent"]

    fc_live = {
        "criteria": [
            {"id": "IN1", "loop_scope": "inner", "text": "x", "verify_by": "test"},
            {"id": "OUT1", "loop_scope": "outer", "text": "y", "verify_by": "live-trial"},
        ]
    }
    fc_no_live = {
        "criteria": [
            {"id": "IN1", "loop_scope": "inner", "text": "x", "verify_by": "test"},
            {"id": "OUT1", "loop_scope": "outer", "text": "y", "verify_by": "elegant-review"},
        ]
    }
    md_agent = "---\nname: s\nkind: run\nallowed-tools:\n  - Read\n  - Agent\n---\nbody\n"
    md_plain = "---\nname: s\nkind: run\nallowed-tools: [Read, Bash(python3 *)]\n---\nbody\n"

    orig = (PLUGINS_DIR, BASELINE_PATH)
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            PLUGINS_DIR = root / "plugins"
            BASELINE_PATH = root / "absent-baseline.json"
            (PLUGINS_DIR / "p" / "skills" / "run-x").mkdir(parents=True)

            # 正: live 導出 + OUT live-trial 携帯 → findings なし
            if _live_trial_ratchet("p", "run-x", "run", md_agent, fc_live, set()) != ([], []):
                failures.append("live+criteria あり が clean にならない")
            # 負: live 導出 + live-trial 欠落 + baseline 外 → violation
            v, w = _live_trial_ratchet("p", "run-x", "run", md_agent, fc_no_live, set())
            if not (len(v) == 1 and not w and "live-trial" in v[0]):
                failures.append(f"live+欠落+baseline外 が violation にならない: {(v, w)}")
            # 免除: baseline 内 → WARN のみ
            v, w = _live_trial_ratchet("p", "run-x", "run", md_agent, fc_no_live, {"p/run-x"})
            if not (not v and len(w) == 1 and "baseline 免除中" in w[0]):
                failures.append(f"baseline 内 が WARN にならない: {(v, w)}")
            # 非 live: fork 導出 (live 信号なし) → 検査対象外
            if _live_trial_ratchet("p", "run-x", "run", md_plain, fc_no_live, set()) != ([], []):
                failures.append("fork 導出 が検査対象外にならない")
            # hooks 配線 (scripts/hook-*.py 実在) でも live 導出 → violation
            hooks_dir = PLUGINS_DIR / "p" / "skills" / "run-x" / "scripts"
            hooks_dir.mkdir()
            (hooks_dir / "hook-demo.py").write_text("# hook\n", encoding="utf-8")
            v, w = _live_trial_ratchet("p", "run-x", "run", md_plain, fc_no_live, set())
            if len(v) != 1:
                failures.append(f"hooks 配線 skill が live 導出されない: {(v, w)}")
    finally:
        PLUGINS_DIR, BASELINE_PATH = orig

    if failures:
        print(f"[FAIL] self-test: {len(failures)} failure(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[OK] self-test: live-trial ratchet 6 case(s) passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--changed-only", action="store_true")
    g.add_argument("--all", action="store_true")
    g.add_argument("--self-test", action="store_true", help="合成 fixture で ratchet を自己検査")
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()
    if args.self_test:
        return _self_test()

    baseline = _load_baseline()
    targets = _git_changed_skills(args.base) if args.changed_only else _all_skills()
    violations: list[str] = []
    warnings: list[str] = []
    checked = 0
    for plugin, skill in sorted(targets):
        md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
        if not md.is_file():
            continue
        text = md.read_text(encoding="utf-8")
        kind = _read_kind(text)
        if kind in LOOP_KINDS:
            checked += 1
            fc = FC.extract_frontmatter_feedback_contract(text)
            if isinstance(fc, dict):
                warnings.extend(_fallback_warnings(plugin, skill, fc))
                r_viol, r_warn = _live_trial_ratchet(plugin, skill, kind, text, fc, baseline)
                violations.extend(r_viol)
                warnings.extend(r_warn)
        violations.extend(_check_skill(plugin, skill))

    if warnings:
        print(f"[WARN] lint-feedback-contract: {len(warnings)} warning(s) (非 fail)")
        for w in warnings:
            print(f"  ~ {w}")
        print(
            "  fallback criteria WARN は brief 既定文の残存 (per-skill 性が空洞の可能性、"
            "固有の検証対象へ書き換え推奨)。baseline 免除 WARN は live-trial ratchet の"
            "既存 skill 免除 (OUT criteria へ verify_by: live-trial 追記で解消)。"
        )
        print()

    if violations:
        print(f"[FAIL] lint-feedback-contract: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("Fix: loop 実行系スキルの SKILL.md frontmatter に feedback_contract.criteria を")
        print("     inner/outer 各1件以上で記載してください(id=^(IN|OUT|C)[0-9]+$ / verify_by enum)。")
        print("     正本制約: scripts/feedback_contract_ssot.py / 配置: commonCore.feedback_contract")
        return 1

    print(f"[OK] lint-feedback-contract: {checked} loop-kind skill(s) carry per-skill criteria")
    return 0


if __name__ == "__main__":
    sys.exit(main())
