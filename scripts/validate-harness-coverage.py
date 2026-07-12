#!/usr/bin/env python3
# /// script
# name: validate-harness-coverage
# purpose: ハーネス仕様「全 artifact 種別 × 二軸(機械的/LLM性能評価) で テストカバレッジ >=80%」の整備状況を横断集計する。
# inputs:
#   - argv: [--threshold 80] [--json <path>] [--gate]
#   - reads: eval-log/code-coverage.json, eval-log/llm-coverage.json, eval-log/*/*/content-review/*-verdict.json
# outputs:
#   - stdout: 種別×二軸のダッシュボード + 総合 PASS/FAIL
#   - eval-log/harness-coverage.json
#   - exit: 0=計測完了(--gate無) / 1=--gate時に仕様未達 / 2=usage
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: eval-log
# ///
"""ハーネス仕様のカバレッジ整備状況を honest に集計する横断ダッシュボード。

ユーザー基準 (2026-06-24): テストカバレッジ >=80% をハーネス仕様の最低条件とし、
対象は scripts / skills / agents / commands / hooks / docs の全 artifact 種別。
二軸で測る:
  - 機械的軸 (mechanical): 行カバレッジ / criteria-test 被覆 / test・fixture 存在率
  - LLM性能評価軸 (llm_eval): LLM 評価器 (content-review / elegance / rubric verdict) が
    PASS かつ score>=threshold である artifact の割合

honest 原則: まだ計測機構が無い種別×軸は instrumented=false として報告し、
総合 spec_met を false にする (未計測を緑に偽装しない)。Goodhart 回避。

事前に `make coverage` と `validate-llm-coverage.py --all` を走らせ eval-log の
*-coverage.json を生成しておくと機械的軸が埋まる。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
DOC_DIR = ROOT / "doc"
EVAL_LOG = ROOT / "eval-log"


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def _real_dirs(parent: Path) -> list[Path]:
    return [d for d in parent.iterdir() if d.is_dir() and not d.is_symlink()] if parent.is_dir() else []


def _skills() -> list[tuple[str, str, Path]]:
    out = []
    for plugin in _real_dirs(PLUGINS_DIR):
        for s in _real_dirs(plugin / "skills"):
            if (s / "SKILL.md").is_file():
                out.append((plugin.name, s.name, s))
    return out


def _md_artifacts(subdir: str) -> list[Path]:
    out: list[Path] = []
    for plugin in _real_dirs(PLUGINS_DIR):
        d = plugin / subdir
        if d.is_dir():
            out.extend(f for f in d.glob("*.md") if f.is_file())
    return out


COV_DIR = EVAL_LOG / "coverage"  # 非コード artifact の coverage レコード置場 (実テスト/実レビューの産物)
_TESTS_BLOB_CACHE: str | None = None


def _tests_blob() -> str:
    global _TESTS_BLOB_CACHE
    if _TESTS_BLOB_CACHE is None:
        parts: list[str] = []
        td = ROOT / "tests"
        if td.is_dir():
            for f in td.rglob("*.py"):
                try:
                    parts.append(f.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    pass
        _TESTS_BLOB_CACHE = "\n".join(parts)
    return _TESTS_BLOB_CACHE


def _slug(*parts: str) -> str:
    return "__".join(re.sub(r"[^A-Za-z0-9._-]", "-", p) for p in parts)


def _cov_record(type_name: str, key: str) -> dict | None:
    return _load_json(COV_DIR / type_name / f"{key}.json")


def _llm_eval_ok(rec: dict | None, threshold: float) -> bool:
    """coverage レコードの llm_eval verdict が PASS かつ score>=threshold か。"""
    if not isinstance(rec, dict):
        return False
    le = rec.get("llm_eval")
    if not isinstance(le, dict) or str(le.get("verdict", "")).upper() != "PASS":
        return False
    score = le.get("score")
    if isinstance(score, (int, float)) and score > 1 and score < threshold:
        return False
    return True


def _script_files() -> list[Path]:
    out: list[Path] = []
    sd = ROOT / "scripts"
    if sd.is_dir():
        out += [f for f in sd.glob("*.py") if not f.is_symlink()]
    for plugin in _real_dirs(PLUGINS_DIR):
        for f in plugin.rglob("scripts/*.py"):
            if not f.is_symlink() and "__pycache__" not in f.parts:
                out.append(f)
    return out


def measure_scripts(threshold: float) -> dict:
    cov = _load_json(EVAL_LOG / "code-coverage.json")
    mech = round(cov["totals"]["percent_covered"], 1) if cov else None
    # LLM性能評価軸 = code-review verdict(eval-log/coverage/scripts/<slug>.json) が PASS の script 割合
    scripts = _script_files()
    le_cov = sum(1 for f in scripts
                 if _llm_eval_ok(_cov_record("scripts", _slug(str(f.relative_to(ROOT)))), threshold))
    lp = _pct(le_cov, len(scripts)) if scripts else 100.0
    return {
        "type": "scripts",
        "count": len(scripts),
        "mechanical": {"instrumented": mech is not None, "coverage_pct": mech,
                       "met": (mech is not None and mech >= threshold),
                       "note": "pytest-cov 行カバレッジ (subprocess 込み)"},
        "llm_eval": {"instrumented": True, "coverage_pct": lp,
                     "met": lp >= threshold,
                     "note": "code-review verdict(eval-log/coverage/scripts) PASS の script 割合"},
    }


def _skill_has_passing_verdict(plugin: str, skill: str, threshold: float) -> bool:
    base = EVAL_LOG / plugin / skill / "content-review"
    ok = 0
    for name in ("elegance-verdict.json", "rubric-verdict.json"):
        v = _load_json(base / name)
        if not isinstance(v, dict):
            return False
        if str(v.get("verdict", "")).upper() != "PASS":
            return False
        score = v.get("score")
        if isinstance(score, (int, float)) and score < threshold and score <= 1.0 * threshold:
            # score が 0-100 表現で threshold 未満なら不合格 (0-1 表現は別途許容)
            if score > 1:
                return False
        ok += 1
    return ok == 2


def _read_skill_kind(skill_dir: Path) -> str | None:
    try:
        m = re.search(r"^kind:\s*([a-z-]+)", (skill_dir / "SKILL.md").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def _skill_ref_review_ok(plugin: str, skill: str, threshold: float) -> bool:
    """ref-kind の ref-review verdict (source-traceability) が PASS か。

    ref は behavioral criteria/content-review を持たない代わりに、
    eval-log/coverage/skills/<plugin>__<skill>.json の llm_eval verdict で
    source-traceability(参照内容と source の整合)を担保する (ハーネス仕様 §kind 別パス)。
    """
    rec = _cov_record("skills", _slug(plugin, skill))
    return _llm_eval_ok(rec, threshold)


def measure_skills(threshold: float) -> dict:
    llm = _load_json(EVAL_LOG / "llm-coverage.json")
    skills = _skills()
    # 機械的軸 = criteria 被覆 (validate-llm-coverage の平均。loop-kind のみ対象)
    mech = llm.get("average_coverage_pct") if isinstance(llm, dict) else None
    # LLM性能評価軸 = kind 別の品質 verdict が PASS の skill 割合 (ref も除外せず計測)。
    #   - 非 ref: content-review (elegance+rubric) verdict=PASS
    #   - ref   : ref-review verdict=PASS (source-traceability。eval-log/coverage/skills/)
    passing = 0
    for plugin, skill, d in skills:
        if _read_skill_kind(d) == "ref":
            if _skill_ref_review_ok(plugin, skill, threshold):
                passing += 1
        elif _skill_has_passing_verdict(plugin, skill, threshold):
            passing += 1
    le = _pct(passing, len(skills)) if skills else None
    return {
        "type": "skills",
        "count": len(skills),
        "mechanical": {"instrumented": mech is not None, "coverage_pct": mech,
                       "met": (mech is not None and mech >= threshold),
                       "note": "criteria+checklist 被覆 (validate-llm-coverage, loop-kind)"},
        "llm_eval": {"instrumented": True, "coverage_pct": le,
                     "met": (le is not None and le >= threshold),
                     "note": "非ref=content-review verdict / ref=ref-review verdict(source-traceability) PASS 率"},
    }


def measure_md_type(type_name: str, subdir: str, threshold: float) -> dict:
    arts = _md_artifacts(subdir)
    blob = _tests_blob()
    mech_cov = le_cov = 0
    for f in arts:
        plugin = f.parent.parent.name
        name = f.stem
        rec = _cov_record(type_name, _slug(plugin, name))
        # 機械的軸: coverage レコード mechanical=true、または tests/ から実参照される
        if (isinstance(rec, dict) and rec.get("mechanical") is True) or (name in blob):
            mech_cov += 1
        if _llm_eval_ok(rec, threshold):
            le_cov += 1
    n = len(arts)
    mp = _pct(mech_cov, n) if n else 100.0
    lp = _pct(le_cov, n) if n else 100.0
    return {
        "type": type_name,
        "count": n,
        "mechanical": {"instrumented": True, "coverage_pct": mp, "met": mp >= threshold,
                       "note": f"{type_name}: tests 参照 or coverage レコード mechanical=true の割合"},
        "llm_eval": {"instrumented": True, "coverage_pct": lp, "met": lp >= threshold,
                     "note": f"{type_name}: coverage レコード llm_eval verdict=PASS の割合"},
    }


# 外部参考資料(他者 Skill コピー/書籍)は harness の挙動でないため coverage 対象外
# (ユーザー指示 2026-06-24: 外部参考資料に test/coverage は不要)。
DOC_EXTERNAL_REFERENCE = ("参考Skill", "Agent Skill大全")


def _is_external_reference_doc(path: Path) -> bool:
    return any(any(tok in part for tok in DOC_EXTERNAL_REFERENCE) for part in path.parts)


def measure_docs(threshold: float) -> dict:
    docs = [f for f in DOC_DIR.rglob("*.md")
            if f.is_file() and not _is_external_reference_doc(f)] if DOC_DIR.is_dir() else []
    blob = _tests_blob()
    mech_cov = le_cov = 0
    for f in docs:
        key = _slug(str(f.relative_to(DOC_DIR)))
        rec = _cov_record("docs", key)
        if (isinstance(rec, dict) and rec.get("mechanical") is True) or (f.name in blob):
            mech_cov += 1
        if _llm_eval_ok(rec, threshold):
            le_cov += 1
    n = len(docs)
    mp = _pct(mech_cov, n) if n else 100.0
    lp = _pct(le_cov, n) if n else 100.0
    return {
        "type": "docs",
        "count": n,
        "mechanical": {"instrumented": True, "coverage_pct": mp, "met": mp >= threshold,
                       "note": "docs: tests 参照 or coverage レコード mechanical=true の割合"},
        "llm_eval": {"instrumented": True, "coverage_pct": lp, "met": lp >= threshold,
                     "note": "docs: coverage レコード llm_eval verdict=PASS の割合"},
    }


def build_report(threshold: float) -> dict:
    sections = [
        measure_scripts(threshold),
        measure_skills(threshold),
        measure_md_type("agents", "agents", threshold),
        measure_md_type("commands", "commands", threshold),
        measure_md_type("hooks", "hooks", threshold),
        measure_docs(threshold),
    ]
    axes = [(sec["type"], axis, sec[axis]) for sec in sections for axis in ("mechanical", "llm_eval")]
    instrumented = [a for *_, a in axes if a["instrumented"]]
    met = [a for a in instrumented if a["met"]]
    spec_met = len(instrumented) == len(axes) and all(a["met"] for a in instrumented)
    return {
        "threshold": threshold,
        "spec_met": spec_met,
        "axes_total": len(axes),
        "axes_instrumented": len(instrumented),
        "axes_met": len(met),
        "sections": sections,
    }


# --- ratchet-floor: spec(80%)↔enforcement 乖離を埋める回帰ガード -----------------
# 80% 絶対 gate (--gate) は現状 4 軸未達で即赤になるため CI では non-blocking WARN に
# 留まっていた (spec と enforcement の二枚舌)。--ratchet は「現値が floor を下回ったら
# fail」に変換し、80% への漸進を妨げず回帰 (verdict/test 未添付の新規 artifact 追加に
# よる率低下) だけを blocking で止める。floor は改善時に --update-floor で引き上げる
# (ratchet up・回帰は焼かない)。
FLOOR_JSON = EVAL_LOG / "harness-coverage-floor.json"
RATCHET_TOLERANCE = 0.1  # 丸め誤差のみ吸収。1 artifact 追加 (≈0.4pt) の率低下は検出する。


def build_floor_from_report(report: dict) -> dict:
    floors = {}
    for sec in report["sections"]:
        floors[sec["type"]] = {
            "mechanical": sec["mechanical"].get("coverage_pct"),
            "llm_eval": sec["llm_eval"].get("coverage_pct"),
        }
    return {
        "threshold": report.get("threshold"),
        "floors": floors,
        "note": "各軸カバレッジの下限 floor。現値がこれを下回ると --ratchet が exit1。"
                "改善時は --update-floor で floor を引き上げる (ratchet up・回帰は焼かない)。",
    }


def compare_to_floor(report: dict, floor: dict, tolerance: float = RATCHET_TOLERANCE) -> list[str]:
    """report の各軸 coverage_pct が floor を tolerance 超で下回る軸を violation 文字列で返す。"""
    violations: list[str] = []
    floors = floor.get("floors", {})
    for sec in report["sections"]:
        t = sec["type"]
        fl = floors.get(t, {})
        for axis in ("mechanical", "llm_eval"):
            cur = sec[axis].get("coverage_pct")
            floor_v = fl.get(axis)
            if cur is None or floor_v is None:
                continue
            if cur < floor_v - tolerance:
                violations.append(
                    f"{t}/{axis}: {cur}% < floor {floor_v}% "
                    "(回帰: test/verdict 未添付の新規 artifact の疑い)"
                )
    return violations


def merge_floor_up(old_floor: dict, report: dict) -> tuple[dict, list[str]]:
    """floor を max(old, 現値) へ引き上げる。現値が旧 floor 未満の軸は据え置き (回帰を焼かない)。"""
    new = build_floor_from_report(report)
    warns: list[str] = []
    old_floors = old_floor.get("floors", {})
    for t, axes in new["floors"].items():
        for axis, cur in list(axes.items()):
            old_v = old_floors.get(t, {}).get(axis)
            if old_v is not None and cur is not None and cur < old_v:
                new["floors"][t][axis] = old_v
                warns.append(
                    f"{t}/{axis}: 現値 {cur}% < 既存 floor {old_v}% のため据え置き "
                    "(回帰は --ratchet が検出)"
                )
    return new, warns


def _self_test() -> int:
    rep = {"threshold": 80.0, "sections": [
        {"type": "scripts", "mechanical": {"coverage_pct": 85.6}, "llm_eval": {"coverage_pct": 62.7}},
        {"type": "agents", "mechanical": {"coverage_pct": 68.0}, "llm_eval": {"coverage_pct": 56.0}},
    ]}
    floor = build_floor_from_report(rep)
    assert floor["floors"]["scripts"]["llm_eval"] == 62.7
    assert compare_to_floor(rep, floor) == []  # 同値 → 違反なし
    lowered = json.loads(json.dumps(rep))
    lowered["sections"][0]["llm_eval"]["coverage_pct"] = 62.0  # 0.7 低下
    assert any("scripts/llm_eval" in v for v in compare_to_floor(lowered, floor))
    rounding = json.loads(json.dumps(rep))
    rounding["sections"][0]["llm_eval"]["coverage_pct"] = 62.65  # 丸め誤差は許容
    assert compare_to_floor(rounding, floor) == []
    raised = json.loads(json.dumps(rep))
    raised["sections"][0]["llm_eval"]["coverage_pct"] = 90.0
    assert compare_to_floor(raised, floor) == []  # 上昇 → 違反なし
    up, _ = merge_floor_up(floor, raised)
    assert up["floors"]["scripts"]["llm_eval"] == 90.0  # ratchet up
    down = json.loads(json.dumps(rep))
    down["sections"][0]["llm_eval"]["coverage_pct"] = 50.0
    held, warns = merge_floor_up(floor, down)
    assert held["floors"]["scripts"]["llm_eval"] == 62.7  # 据え置き (回帰は焼かない)
    assert any("scripts/llm_eval" in w for w in warns)
    print("OK: validate-harness-coverage ratchet self-test (6 checks)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=80.0)
    ap.add_argument("--json", default=str(EVAL_LOG / "harness-coverage.json"))
    ap.add_argument("--gate", action="store_true", help="仕様未達(spec_met=false)で exit1")
    ap.add_argument("--ratchet", action="store_true",
                    help="floor ledger を下回る軸があれば exit1 (回帰ガード)")
    ap.add_argument("--update-floor", action="store_true",
                    help="floor を現値へ ratchet up (下げない)")
    ap.add_argument("--floor", default=str(FLOOR_JSON))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    rep = build_report(args.threshold)
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[harness-coverage] 閾値 {args.threshold}% / 二軸×種別 {rep['axes_total']} 中 "
          f"計測済 {rep['axes_instrumented']} / 達成 {rep['axes_met']}")
    for sec in rep["sections"]:
        for axis in ("mechanical", "llm_eval"):
            a = sec[axis]
            mark = "OK " if a["met"] else ("～  " if a["instrumented"] else "—  ")
            pct = f"{a['coverage_pct']}%" if a["coverage_pct"] is not None else "未計測"
            print(f"  [{mark}] {sec['type']:<9} {axis:<10} {pct}")
    verdict = "PASS (ハーネス仕様 充足)" if rep["spec_met"] else "FAIL (ハーネス仕様 未達)"
    print(f"[harness-coverage] 総合: {verdict}")
    if args.update_floor:
        floor_path = Path(args.floor)
        old_floor = _load_json(floor_path)
        if old_floor is None:
            new_floor, warns = build_floor_from_report(rep), []
        else:
            new_floor, warns = merge_floor_up(old_floor, rep)
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(json.dumps(new_floor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for w in warns:
            print(f"  [floor据置] {w}")
        print(f"[harness-coverage] floor を {floor_path} に更新 (ratchet up)")
        return 0

    if args.ratchet:
        floor_path = Path(args.floor)
        old_floor = _load_json(floor_path)
        if old_floor is None:
            print(f"[harness-coverage] floor ledger 不在 ({floor_path})。"
                  "初回は --update-floor で初期化する。", file=sys.stderr)
            return 2
        violations = compare_to_floor(rep, old_floor)
        if violations:
            print(f"[harness-coverage] RATCHET FAIL: {len(violations)} 軸が floor を下回った (回帰)",
                  file=sys.stderr)
            for v in violations:
                print(f"  - {v}", file=sys.stderr)
            print("  → 新規 artifact に test/verdict を添付するか、"
                  "意図した floor 変更なら --update-floor で更新する。", file=sys.stderr)
            return 1
        print("[harness-coverage] RATCHET OK: 全軸が floor 以上 (回帰なし)")
        return 0

    if args.gate and not rep["spec_met"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
