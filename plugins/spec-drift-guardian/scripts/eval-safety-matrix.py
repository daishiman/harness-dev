#!/usr/bin/env python3
# /// script
# name: eval-safety-matrix
# purpose: C5 safety-matrix ゲートの end-to-end 実測器。C10 check-triage-complete.py を 6 シナリオ (applied_verified / no-change の許可 2 + proposal-only / 未承認 / 監査FAIL / hash drift の拒否 4) で実 subprocess 起動し、拒否経路では target 実ファイルの実行前後 sha256 が不変 (= apply が close ゲートを越えず変更0件) であることを直接実測して safety-matrix-result.json を書く。
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
"""C10 close ゲートの安全性を end-to-end で実測する (spec-drift-guardian)。

各シナリオで schema-valid な 4 artifact (triage-report / triage-verdict /
sync-proposal / sync-audit-verdict) を tempfile に組み、実 C10 を subprocess 起動する。
拒否シナリオ (proposal-only / 未承認 / 監査FAIL / hash drift) では C10 が exit1
(INCOMPLETE=close 遮断) を返すこと、かつ target 実ファイルが C10 実行の前後で
sha256 不変であること (C10 は write-scope:none ゆえ副作用0=apply が close を越えない)
を実測する。許可シナリオ (applied_verified / no-change) では exit0 と close 経路名を検証する。
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
        ("hash-drift", False, 1, "post-image",
         lambda: (base_report(True), base_verdict(True),
                  base_proposal("applied_verified", True, "f" * 64, True), base_audit("PASS"))),
    ]


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
