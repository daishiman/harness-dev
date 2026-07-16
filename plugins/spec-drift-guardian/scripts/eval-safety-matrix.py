#!/usr/bin/env python3
# /// script
# name: eval-safety-matrix
# purpose: C5 safety-matrix ゲートの end-to-end 実測器。C10 check-triage-complete.py を 15 シナリオで実 subprocess 起動する: close ゲート 6 (applied_verified / no-change の許可 2 + proposal-only / 未承認 / 監査FAIL / post-image hash drift の拒否 4) と apply 前ゲート 9 (--mode pre-apply。apply-allowed の許可 1 + pre-image hash drift / 未承認 / 監査FAIL / allowlist 外 / allowlist traversal escape / allowlist 絶対 path / verifier 不同意 / 別 diff への agree 流用 の拒否 8)。拒否経路では target 実ファイルの実行前後 sha256 が不変 (= 変更0件) であることを直接実測して safety-matrix-result.json を書く。pre-image drift は close ゲートでは構造上検出できない (適用後の実ファイルは post-image) ため apply 前ゲートで実測する。
# inputs:
#   - --c10-script FILE check-triage-complete.py のパス (既定 self-relative)
#   - --out FILE 実測結果 JSON の出力先
# outputs:
#   - --out に safety-matrix-result.json / stdout に人可読サマリ
#   - exit: 0=全シナリオ期待通り / 1=不一致あり / 2=usage/IO
# contexts: [E]
# network: false
# write-scope: --out path only (fixture は tempfile 内に閉じる)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C10 の close ゲートと apply 前ゲートの安全性を end-to-end で実測する (spec-drift-guardian)。

各シナリオで schema-valid な artifact (triage-report / triage-verdict / sync-proposal /
sync-audit-verdict) を tempfile に組み、実 C10 を subprocess 起動する。

- close ゲート (既定 --mode close): 拒否シナリオ (proposal-only / 未承認 / 監査FAIL /
  post-image hash drift) で exit1 (INCOMPLETE=close 遮断)、許可シナリオ
  (applied_verified / no-change) で exit0 と close 経路名を検証する。
- apply 前ゲート (--mode pre-apply): G1-G5 (監査PASS/承認/allowlist/pre-image一致/C03 agree + diff_sha256 束縛) を検証する。close ゲートは適用**後**の
  post-image を突合するため pre-image drift を構造上検出できない (適用後の実ファイルは
  post-image になっている)。pre-image hash drift / 未承認 / 監査FAIL / allowlist 外 /
  verifier 不同意 で exit1 (変更0件で停止)、全条件充足で exit0 (apply_allowed) を実測する。

いずれのシナリオでも target 実ファイルが C10 実行の前後で sha256 不変であること
(C10 は write-scope:none ゆえ副作用0) を確認する。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_C10 = Path(__file__).resolve().parent / "check-triage-complete.py"

ISSUE = 17
DIFF_SHA = "a" * 64
PROPOSAL_SHA = "b" * 64
TARGET_REL = "plugins/harness-creator/skills/ref-skill-design-rubric/rubric.json"
APPLIED_CONTENT = b'{\n  "id": "clarity",\n  "weight": 3\n}\n'


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def base_report(impacted: bool = True) -> dict:
    return {
        "issue": ISSUE,
        "base_commit": "da6d4e7",
        "source_commit": "6ddd645",
        "diff_sha256": DIFF_SHA,
        "complete": True,
        "impacts": [
            {
                "artifact_kind": "rubric",
                "artifact_path": TARGET_REL,
                "axis": "required",
                "before": "weight: 2",
                "after": "weight: 3",
                "impacted": impacted,
                "evidence": "rubric weight changed",
            }
        ],
    }


def base_verdict(agree: bool = True) -> dict:
    return {
        "issue": ISSUE,
        "diff_sha256": DIFF_SHA,
        "rederived_impacts": [
            {
                "artifact_kind": "rubric",
                "artifact_path": TARGET_REL,
                "axis": "required",
                "before": "weight: 2",
                "after": "weight: 3",
                "impacted": True,
                "evidence": "independently rederived",
            }
        ],
        "agree": agree,
        "findings": [],
        "verdict_sha256": "c" * 64,
    }


def proposal_item(post_image: str | None, validators_pass: bool = True) -> dict:
    return {
        "target_path": TARGET_REL,
        "axis": "required",
        "before": "weight: 2",
        "after": "weight: 3",
        "proposed_diff": "- weight: 2\n+ weight: 3\n",
        "pre_image_sha256": "d" * 64,
        "post_image_sha256": post_image,
        "validator_results": [
            {"validator": "jsonschema", "exit_code": 0 if validators_pass else 1, "passed": validators_pass}
        ],
    }


def base_proposal(status: str = "applied_verified", granted: bool = True,
                  post_image: str | None = None, validators_pass: bool = True) -> dict:
    return {
        "issue": ISSUE,
        "proposal_sha256": PROPOSAL_SHA,
        "status": status,
        "approval": {
            "granted": granted,
            "by": "user" if granted else None,
            "evidence": "2026-07-13 承認発話" if granted else None,
        },
        "proposals": [proposal_item(post_image, validators_pass)],
    }


def base_audit(verdict: str = "PASS") -> dict:
    return {
        "issue": ISSUE,
        "proposal_sha256": PROPOSAL_SHA,
        "audited_targets": [{"target_path": TARGET_REL, "axis": "required"}],
        "omissions": [],
        "excesses": [],
        "allowlist_violations": [],
        "verdict": verdict,
    }


def _write(d: Path, name: str, obj: dict) -> Path:
    p = d / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def run_c10(c10: Path, workdir: Path, report, verdict, proposal, audit, target_root: Path):
    """C10 を subprocess 起動し (exit_code, payload) を返す。"""
    rp = _write(workdir, "triage-report.json", report)
    vp = _write(workdir, "triage-verdict.json", verdict)
    pp = _write(workdir, "sync-proposal.json", proposal)
    ap = _write(workdir, "sync-audit-verdict.json", audit)
    proc = subprocess.run(
        [sys.executable, str(c10), "--issue", str(ISSUE),
         "--triage-report", str(rp), "--triage-verdict", str(vp),
         "--sync-proposal", str(pp), "--sync-audit-verdict", str(ap),
         "--target-root", str(target_root)],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return proc.returncode, payload


def scenarios(applied_post: str):
    """(name, allow?, expected_exit, expected_status_substr, build_artifacts) を列挙。"""
    return [
        ("applied_verified", True, 0, "applied_verified",
         lambda: (base_report(True), base_verdict(True),
                  base_proposal("applied_verified", True, applied_post, True), base_audit("PASS"))),
        ("no-change", True, 0, "independently_verified_no_change",
         lambda: (base_report(False), base_verdict(True),
                  base_proposal("proposed", False, None, True), base_audit("PASS"))),
        ("proposal-only", False, 1, "applied_verified",
         lambda: (base_report(True), base_verdict(True),
                  base_proposal("proposed", False, None, True), base_audit("PASS"))),
        ("unapproved", False, 1, "approval.granted",
         lambda: (base_report(True), base_verdict(True),
                  base_proposal("applied_verified", False, applied_post, True), base_audit("PASS"))),
        ("audit-FAIL", False, 1, "PASS",
         lambda: (base_report(True), base_verdict(True),
                  base_proposal("applied_verified", True, applied_post, True), base_audit("FAIL"))),
        ("post-image-hash-drift", False, 1, "post-image",
         lambda: (base_report(True), base_verdict(True),
                  base_proposal("applied_verified", True, "f" * 64, True), base_audit("PASS"))),
    ]


def _pre_apply_proposal(pre: str | None, *, granted: bool = True,
                        target_path: str = TARGET_REL) -> dict:
    """status=proposed (apply 直前) の sync-proposal を pre_image/承認/対象を変えて組む。"""
    item = proposal_item(None, True)
    item["target_path"] = target_path
    item["pre_image_sha256"] = pre
    prop = base_proposal("proposed", granted, None, True)
    prop["proposals"] = [item]
    return prop


def pre_apply_scenarios(real_pre: str):
    """apply 前ゲート (--mode pre-apply / G1-G5) の (name, allow?, exit, substr, build) 列挙。

    close ゲートは適用**後**の post-image を突合するため pre-image drift を構造上検出できない
    (適用後の実ファイルは post-image になっている)。G4 (適用直前の pre-image 一致) はここで実測する。
    """
    return [
        ("apply-allowed", True, 0, "apply_allowed",
         lambda: (_pre_apply_proposal(real_pre), base_audit("PASS"), base_verdict(True))),
        ("pre-image-hash-drift", False, 1, "hash drift",
         lambda: (_pre_apply_proposal("a" * 64), base_audit("PASS"), base_verdict(True))),
        ("unapproved", False, 1, "G2",
         lambda: (_pre_apply_proposal(real_pre, granted=False), base_audit("PASS"), base_verdict(True))),
        ("audit-FAIL", False, 1, "G1",
         lambda: (_pre_apply_proposal(real_pre), base_audit("FAIL"), base_verdict(True))),
        ("outside-allowlist", False, 1, "G3",
         lambda: (_pre_apply_proposal(real_pre, target_path="src/secret.py"), base_audit("PASS"), base_verdict(True))),
        # 素朴な外部 path だけでは、`..` で allowlist prefix を抜ける fail-open を検出できない
        # (fnmatch の `*` は `/` を跨ぐため `..` 列を吸収する)。traversal を明示的に測る。
        ("allowlist-traversal-escape", False, 1, "G3",
         lambda: (_pre_apply_proposal(real_pre, target_path="plugins/harness-creator/../../outside/rubric.json"),
                  base_audit("PASS"), base_verdict(True))),
        ("allowlist-absolute-path", False, 1, "G3",
         lambda: (_pre_apply_proposal(real_pre, target_path="/etc/passwd"),
                  base_audit("PASS"), base_verdict(True))),
        # IN1: 独立 verifier が不同意のまま apply させない (close 前に止める)。
        ("verifier-disagrees", False, 1, "agree",
         lambda: (_pre_apply_proposal(real_pre), base_audit("PASS"), base_verdict(False))),
        # agree=true でも「別 diff への同意」なら流用不可 (主語の束縛)。
        ("agree-for-other-diff", False, 1, "diff_sha256",
         lambda: (_pre_apply_proposal(real_pre), base_audit("PASS"), _verdict_other_diff())),
    ]


def _verdict_other_diff() -> dict:
    """agree=true だが triage-report とは別 diff への verdict (stale verdict 流用)。"""
    v = base_verdict(True)
    v["diff_sha256"] = "9" * 64
    return v


def run_c10_pre_apply(c10: Path, workdir: Path, proposal: dict, audit: dict,
                      verdict: dict, target_root: Path):
    """C10 を --mode pre-apply で起動し (exit_code, payload) を返す。"""
    pp = _write(workdir, "sync-proposal.json", proposal)
    ap = _write(workdir, "sync-audit-verdict.json", audit)
    vp = _write(workdir, "triage-verdict.json", verdict)
    rp = _write(workdir, "triage-report.json", base_report(True))
    proc = subprocess.run(
        [sys.executable, str(c10), "--mode", "pre-apply", "--issue", str(ISSUE),
         "--triage-report", str(rp), "--triage-verdict", str(vp),
         "--sync-proposal", str(pp), "--sync-audit-verdict", str(ap),
         "--target-root", str(target_root)],
        capture_output=True, text=True,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return proc.returncode, payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="C10 close ゲートの安全性 end-to-end 実測器")
    ap.add_argument("--c10-script", default=str(DEFAULT_C10))
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    c10 = Path(args.c10_script)
    if not c10.is_file():
        sys.stderr.write(f"c10-script not found: {c10}\n")
        return 2

    results = []
    all_match = True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        target_root = root / "repo"
        target_file = target_root / TARGET_REL
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_bytes(APPLIED_CONTENT)
        applied_post = _sha256_bytes(APPLIED_CONTENT)

        for name, allow, exp_exit, exp_status_sub, build in scenarios(applied_post):
            work = root / name
            work.mkdir(parents=True, exist_ok=True)
            report, verdict, proposal, audit = build()
            before = _sha256_bytes(target_file.read_bytes())
            code, payload = run_c10(c10, work, report, verdict, proposal, audit, target_root)
            after = _sha256_bytes(target_file.read_bytes())
            status = payload.get("status", "")
            reasons = payload.get("reasons", [])
            exit_ok = code == exp_exit
            status_ok = (exp_status_sub in status) if allow else \
                any(exp_status_sub in r for r in reasons)
            unchanged = before == after  # C10 は副作用0 のはず (write-scope:none)
            close_blocked = code != 0
            # 拒否シナリオは「close 遮断 かつ target 不変 (=apply が close を越えず変更0件)」を要求。
            scenario_match = exit_ok and status_ok and unchanged and (close_blocked != allow)
            all_match = all_match and scenario_match
            results.append({
                "scenario": name,
                "expected": {"allow_close": allow, "exit": exp_exit, "status_or_reason_contains": exp_status_sub},
                "actual": {"exit": code, "status": status, "close_blocked": close_blocked},
                "target_unchanged": unchanged,
                "match": scenario_match,
            })

        # ── apply 前ゲート (G1-G5)。close ゲートでは検出不能な pre-image drift / agree を実測する ──
        real_pre = _sha256_bytes(target_file.read_bytes())
        for name, allow, exp_exit, exp_sub, build in pre_apply_scenarios(real_pre):
            work = root / f"pre-apply-{name}"
            work.mkdir(parents=True, exist_ok=True)
            proposal, audit, verdict = build()
            before = _sha256_bytes(target_file.read_bytes())
            code, payload = run_c10_pre_apply(c10, work, proposal, audit, verdict, target_root)
            after = _sha256_bytes(target_file.read_bytes())
            status = payload.get("status", "")
            reasons = payload.get("reasons", [])
            exit_ok = code == exp_exit
            status_ok = (exp_sub in status) if allow else any(exp_sub in r for r in reasons)
            unchanged = before == after  # ゲート自身は write-scope:none
            blocked = code != 0
            scenario_match = exit_ok and status_ok and unchanged and (blocked != allow)
            all_match = all_match and scenario_match
            results.append({
                "scenario": f"pre-apply:{name}",
                "expected": {"allow_close": allow, "exit": exp_exit, "status_or_reason_contains": exp_sub},
                "actual": {"exit": code, "status": status, "close_blocked": blocked},
                "target_unchanged": unchanged,
                "match": scenario_match,
            })

    result = {
        "schema_version": "1.0.0",
        "target_plugin_slug": "spec-drift-guardian",
        "c10_script": str(c10),
        "scenario_count": len(results),
        "reject_scenarios_block_and_no_change": all(
            r["actual"]["close_blocked"] and r["target_unchanged"]
            for r in results if not r["expected"]["allow_close"]
        ),
        "allow_scenarios_permit": all(
            (not r["actual"]["close_blocked"]) for r in results if r["expected"]["allow_close"]
        ),
        "all_scenarios_match": all_match,
        "scenarios": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if all_match else "FAIL"
    sys.stdout.write(f"[{status}] scenarios={len(results)} all_match={all_match} -> {out}\n")
    for r in results:
        flag = "OK " if r["match"] else "XX "
        sys.stdout.write(f"  {flag}{r['scenario']:16s} exit={r['actual']['exit']} "
                         f"blocked={r['actual']['close_blocked']} unchanged={r['target_unchanged']}\n")
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
