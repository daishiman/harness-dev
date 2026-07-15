#!/usr/bin/env python3
# /// script
# name: test-check-triage-complete
# purpose: C10 の artifact schema、cross-artifact digest、適用証跡、no-change close gate を検証する。
# inputs: scripts/check-triage-complete.py / tmp_path artifact
# outputs: pytest assertions and coverage evidence
# contexts: [E]
# network: false
# write-scope: pytest tmp_path only
# dependencies: [pytest]
# ///
"""C10 check-triage-complete.py の決定論 unit test。

sync-proposal は proposals[] を正本とするコンテナ形。close 経路
(applied_verified / independently_verified_no_change) と拒否経路
(proposal-only / 未承認 / ある proposal の hash 不一致 / verdict FAIL) を
exit code 契約で固定する。fixture JSON は tmp に書いて argv で渡す
(network:false / write-scope:none / stdlib only)。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys

import pytest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-triage-complete.py"
_SPEC = importlib.util.spec_from_file_location("check_triage_complete", SCRIPT)
C10 = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(C10)

ISSUE = 17
DIFF_SHA = "a" * 64
PROPOSAL_SHA = "b" * 64
VERDICT_SHA = "c" * 64
PRE_IMAGE_SHA = "d" * 64
# allowlist (apply-gate-policy §1) に一致するパス。
TARGET_REL = "plugins/harness-creator/skills/assign-skill-design-evaluator/references/rubric.json"
TARGET_REL2 = "plugins/harness-creator/skills/run-skill-create/schemas/build-trace.schema.json"
APPLIED_CONTENT = b'{"rubric": "synced"}\n'
APPLIED_CONTENT2 = b'{"$schema": "x", "type": "object"}\n'


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def base_report(impacted: bool = True) -> dict:
    """triage-report。impacted=True なら影響ありの軸を 1 件含む。"""
    return {
        "issue": ISSUE,
        "base_commit": "0000000",
        "source_commit": "1111111",
        "diff_sha256": DIFF_SHA,
        "complete": True,
        "impacts": [
            {
                "artifact_kind": "rubric",
                "artifact_path": TARGET_REL,
                "axis": "enum",
                "before": "old",
                "after": "new",
                "impacted": impacted,
                "evidence": "hunk @@ -1 +1 @@",
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
                "axis": "enum",
                "before": "old",
                "after": "new",
                "impacted": True,
                "evidence": "independent rederivation",
            }
        ],
        "agree": agree,
        "findings": [],
        "verdict_sha256": VERDICT_SHA,
    }


def proposal_item(
    target_path: str = TARGET_REL,
    post_image: str | None = None,
    validators_pass: bool = True,
    axis: str = "enum",
) -> dict:
    """proposals[] の 1 要素 (proposal 単位の適用証跡)。"""
    return {
        "target_path": target_path,
        "axis": axis,
        "before": "old",
        "after": "new",
        "proposed_diff": "- old\n+ new\n",
        "pre_image_sha256": PRE_IMAGE_SHA,
        "post_image_sha256": post_image,
        "validator_results": [
            {"validator": "lint-rubric", "exit_code": 0 if validators_pass else 1, "passed": validators_pass}
        ],
    }


def base_proposal(
    status: str = "applied_verified",
    granted: bool = True,
    post_image: str | None = None,
    validators_pass: bool = True,
    proposals: list[dict] | None = None,
) -> dict:
    """sync-proposal コンテナ。issue/proposal_sha256/status/approval は issue 単位のゲート。"""
    if proposals is None:
        proposals = [proposal_item(TARGET_REL, post_image, validators_pass)]
    return {
        "issue": ISSUE,
        "proposal_sha256": PROPOSAL_SHA,
        "status": status,
        "approval": {
            "granted": granted,
            "by": "user" if granted else None,
            "evidence": "2026-07-13 承認発話" if granted else None,
        },
        "proposals": proposals,
    }


def base_audit(verdict: str = "PASS") -> dict:
    return {
        "issue": ISSUE,
        "proposal_sha256": PROPOSAL_SHA,
        "audited_targets": [{"target_path": TARGET_REL, "axis": "enum"}],
        "omissions": [],
        "excesses": [],
        "allowlist_violations": [],
        "verdict": verdict,
    }


def _write(tmp_path: Path, name: str, obj: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return p


def run(tmp_path: Path, report, verdict, proposal, audit, target_root: Path | None = None):
    rp = _write(tmp_path, "triage-report.json", report)
    vp = _write(tmp_path, "triage-verdict.json", verdict)
    pp = _write(tmp_path, "sync-proposal.json", proposal)
    ap = _write(tmp_path, "sync-audit-verdict.json", audit)
    root = target_root if target_root is not None else tmp_path
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--issue",
            str(ISSUE),
            "--triage-report",
            str(rp),
            "--triage-verdict",
            str(vp),
            "--sync-proposal",
            str(pp),
            "--sync-audit-verdict",
            str(ap),
            "--target-root",
            str(root),
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _make_target(tmp_path: Path, rel: str, content: bytes) -> str:
    """target_root 配下に実ファイルを配置し、その sha256 を返す。"""
    target_file = tmp_path / rel
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(content)
    return _sha256_bytes(content)


def _make_applied_target(tmp_path: Path) -> str:
    """デフォルト単一 target を配置し sha256 を返す。"""
    return _make_target(tmp_path, TARGET_REL, APPLIED_CONTENT)


# --- (a) 完全な applied_verified 一式 (複数 proposal 全 pass) → OK / exit0 ---
def test_applied_verified_ok(tmp_path):
    post1 = _make_target(tmp_path, TARGET_REL, APPLIED_CONTENT)
    post2 = _make_target(tmp_path, TARGET_REL2, APPLIED_CONTENT2)
    proposals = [
        proposal_item(TARGET_REL, post1, True, "enum"),
        proposal_item(TARGET_REL2, post2, True, "type"),
    ]
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=True, proposals=proposals),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 0, proc.stderr
    assert payload["result"] == "OK"
    assert payload["status"] == "applied_verified"
    assert payload["reasons"] == []


# --- (b) status=proposed (proposal-only) → INCOMPLETE / exit1 ---
def test_proposal_only_incomplete(tmp_path):
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="proposed", granted=False, post_image=None),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert payload["result"] == "INCOMPLETE"
    assert any("applied_verified" in r for r in payload["reasons"])


# --- (c) approval.granted=false → INCOMPLETE ---
def test_unapproved_incomplete(tmp_path):
    post = _make_applied_target(tmp_path)
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=False, post_image=post, validators_pass=True),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert payload["result"] == "INCOMPLETE"
    assert any("approval.granted" in r for r in payload["reasons"])


# --- (d) ある proposal の post-image hash 不一致 (他は一致) → INCOMPLETE ---
def test_post_image_hash_mismatch_incomplete(tmp_path):
    post1 = _make_target(tmp_path, TARGET_REL, APPLIED_CONTENT)
    _make_target(tmp_path, TARGET_REL2, APPLIED_CONTENT2)  # 実ファイルは配置するが post_image を別 hash にする
    wrong = "e" * 64
    proposals = [
        proposal_item(TARGET_REL, post1, True, "enum"),
        proposal_item(TARGET_REL2, wrong, True, "type"),
    ]
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=True, proposals=proposals),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert payload["result"] == "INCOMPLETE"
    assert any("post-image" in r or "drift" in r for r in payload["reasons"])


# --- (e) verdict=FAIL → INCOMPLETE ---
def test_audit_fail_incomplete(tmp_path):
    post = _make_applied_target(tmp_path)
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=True, post_image=post, validators_pass=True),
        base_audit(verdict="FAIL"),
    )
    assert proc.returncode == 1
    assert payload["result"] == "INCOMPLETE"
    assert any("verdict" in r and "PASS" in r for r in payload["reasons"])


# --- (f) no-impact + agree=true → OK status=independently_verified_no_change ---
def test_no_change_ok(tmp_path):
    proc, payload = run(
        tmp_path,
        base_report(impacted=False),
        base_verdict(agree=True),
        base_proposal(status="proposed", granted=False, post_image=None),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 0, proc.stderr
    assert payload["result"] == "OK"
    assert payload["status"] == "independently_verified_no_change"
    assert payload["reasons"] == []


# --- 追加: validator fail → INCOMPLETE ---
def test_validator_fail_incomplete(tmp_path):
    post = _make_applied_target(tmp_path)
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=True, post_image=post, validators_pass=False),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert any("validator_results" in r for r in payload["reasons"])


# --- 追加: allowlist 外 target_path → INCOMPLETE ---
def test_allowlist_violation_incomplete(tmp_path):
    outside_rel = "plugins/spec-drift-guardian/schemas/x.schema.json"
    post = _make_target(tmp_path, outside_rel, APPLIED_CONTENT2)
    proposals = [proposal_item(outside_rel, post, True, "type")]
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=True, proposals=proposals),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert any("allowlist" in r for r in payload["reasons"])


# --- 追加: agree=false → INCOMPLETE ---
def test_disagree_incomplete(tmp_path):
    post = _make_applied_target(tmp_path)
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=False),
        base_proposal(status="applied_verified", granted=True, post_image=post, validators_pass=True),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert any("agree" in r for r in payload["reasons"])


# --- 追加: digest 不一致 → INCOMPLETE ---
def test_digest_mismatch_incomplete(tmp_path):
    post = _make_applied_target(tmp_path)
    verdict = base_verdict(agree=True)
    verdict["diff_sha256"] = "f" * 64  # triage-report と不一致
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        verdict,
        base_proposal(status="applied_verified", granted=True, post_image=post, validators_pass=True),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 1
    assert any("diff_sha256" in r for r in payload["reasons"])


# --- 追加: schema violation (必須キー欠落) → exit2 ---
def test_schema_error_exit2(tmp_path):
    report = base_report(impacted=True)
    del report["diff_sha256"]
    proc, payload = run(
        tmp_path,
        report,
        base_verdict(agree=True),
        base_proposal(status="applied_verified", granted=True, post_image="e" * 64, validators_pass=True),
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 2
    assert payload["result"] == "ERROR"


# --- 追加: sync-proposal の proposals[] 欠落 → exit2 ---
def test_proposal_missing_proposals_exit2(tmp_path):
    proposal = base_proposal(status="applied_verified", granted=True, post_image="e" * 64)
    del proposal["proposals"]
    proc, payload = run(
        tmp_path,
        base_report(impacted=True),
        base_verdict(agree=True),
        proposal,
        base_audit(verdict="PASS"),
    )
    assert proc.returncode == 2
    assert payload["result"] == "ERROR"


# --- 追加: --help が exit0 ---
def test_help_exit0():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "--issue" in proc.stdout


def test_schema_validators_cover_malformed_field_boundaries():
    """各 schema validator が型/enum 境界をまとめて fail-closed にする。"""
    errors: list[str] = []
    C10.validate_triage_report([], errors)
    report = base_report()
    report.update({"issue": True, "complete": False, "diff_sha256": 1})
    report["impacts"] = [
        {
            "artifact_kind": "invalid",
            "artifact_path": "x",
            "axis": "invalid",
            "before": None,
            "after": None,
            "impacted": "yes",
            "evidence": "x",
        },
        {"artifact_kind": "rubric"},
    ]
    C10.validate_triage_report(report, errors)

    verdict = base_verdict()
    verdict.update({
        "issue": True,
        "diff_sha256": 2,
        "agree": "yes",
        "rederived_impacts": "bad",
        "findings": [
            {"kind": "invalid", "axis": "invalid", "artifact_path": "x", "detail": "x"},
            {"kind": "missed"},
        ],
    })
    C10.validate_triage_verdict(verdict, errors)
    verdict["findings"] = "bad"
    C10.validate_triage_verdict(verdict, errors)

    proposal = base_proposal()
    proposal.update({"issue": True, "proposal_sha256": 2, "status": "invalid"})
    proposal["approval"] = {"granted": "yes", "by": None, "evidence": None}
    proposal["proposals"] = [{
        "target_path": "",
        "axis": "invalid",
        "before": None,
        "after": None,
        "proposed_diff": "",
        "pre_image_sha256": "",
        "post_image_sha256": 42,
        "validator_results": [
            {"validator": "x", "exit_code": True, "passed": "yes"},
            {"validator": "missing"},
        ],
    }]
    C10.validate_sync_proposal(proposal, errors)
    proposal["approval"] = []
    proposal["proposals"] = []
    C10.validate_sync_proposal(proposal, errors)
    proposal["proposals"] = "bad"
    C10.validate_sync_proposal(proposal, errors)

    audit = base_audit()
    audit.update({
        "issue": True,
        "proposal_sha256": 3,
        "verdict": "invalid",
        "audited_targets": [
            {"target_path": "x", "axis": "invalid"},
            {"target_path": "x"},
        ],
        "omissions": "bad",
        "excesses": "bad",
        "allowlist_violations": "bad",
    })
    C10.validate_sync_audit_verdict(audit, errors)
    audit["audited_targets"] = []
    C10.validate_sync_audit_verdict(audit, errors)

    assert len(errors) >= 25
    assert any("artifact_kind" in error for error in errors)
    assert any("validator_results" in error for error in errors)
    assert any("audited_targets" in error for error in errors)


def test_load_json_missing_and_invalid(tmp_path):
    errors: list[str] = []
    assert C10._load_json(tmp_path / "missing.json", "missing", errors) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{bad", encoding="utf-8")
    assert C10._load_json(bad, "bad", errors) is None
    assert len(errors) == 2


def test_evaluate_reports_issue_mismatch_missing_target_and_empty_validators(tmp_path):
    proposal = base_proposal(
        status="applied_verified",
        granted=True,
        proposals=[proposal_item(TARGET_REL, "e" * 64, True)],
    )
    proposal["proposals"][0]["validator_results"] = []
    report = base_report(impacted=True)
    report["issue"] = 99
    result, _, reasons = C10.evaluate(
        ISSUE, report, base_verdict(), proposal, base_audit(), tmp_path
    )
    assert result == "INCOMPLETE"
    assert any("issue=99" in reason for reason in reasons)
    assert any("存在しない" in reason for reason in reasons)
    assert any("validator_results が空" in reason for reason in reasons)


# ───────────── apply 前ゲート (--mode pre-apply / apply-gate-policy §2 G1-G5) ─────────────
# close ゲートは適用後の post-image を見るため構造上 pre-image drift を検出できない
# (適用後の実ファイルは post-image になっている)。G4 を LLM 手順だけに委ねず機械検証する。
def _seed_target(root: Path, rel: str = TARGET_REL, body: str = '{"seed": 1}') -> str:
    """target-root 配下に実ファイルを置き、その sha256 を返す。"""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _run_pre_apply(tmp_path: Path, proposal, audit, target_root: Path, verdict=None, report=None):
    pp = _write(tmp_path, "sync-proposal.json", proposal)
    ap = _write(tmp_path, "sync-audit-verdict.json", audit)
    vp = _write(tmp_path, "triage-verdict.json", verdict if verdict is not None else base_verdict(True))
    rp = _write(tmp_path, "triage-report.json", report if report is not None else base_report(True))
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "pre-apply", "--issue", str(ISSUE),
         "--triage-report", str(rp), "--triage-verdict", str(vp),
         "--sync-proposal", str(pp), "--sync-audit-verdict", str(ap),
         "--target-root", str(target_root)],
        capture_output=True, text=True,
    )


def _proposed(pre_sha, *, granted=True, target_path=TARGET_REL):
    item = proposal_item(target_path, None, True)
    item["pre_image_sha256"] = pre_sha
    return base_proposal(status="proposed", granted=granted, proposals=[item])


def test_pre_apply_allows_when_all_four_gates_pass(tmp_path):
    root = tmp_path / "repo"
    sha = _seed_target(root)
    proc = _run_pre_apply(tmp_path, _proposed(sha), base_audit("PASS"), root)
    assert proc.returncode == 0
    assert "apply_allowed" in proc.stdout


def test_pre_apply_blocks_on_pre_image_hash_drift(tmp_path):
    # G4: 提案作成後に対象ファイルが第三者に書き換えられた = pre-image drift。
    root = tmp_path / "repo"
    _seed_target(root)
    proc = _run_pre_apply(tmp_path, _proposed("a" * 64), base_audit("PASS"), root)
    assert proc.returncode == 1
    assert "hash drift" in proc.stderr and "G4" in proc.stderr


def test_pre_apply_blocks_when_unapproved(tmp_path):
    root = tmp_path / "repo"
    sha = _seed_target(root)
    proc = _run_pre_apply(tmp_path, _proposed(sha, granted=False), base_audit("PASS"), root)
    assert proc.returncode == 1 and "G2" in proc.stderr


def test_pre_apply_blocks_on_audit_fail(tmp_path):
    root = tmp_path / "repo"
    sha = _seed_target(root)
    proc = _run_pre_apply(tmp_path, _proposed(sha), base_audit("FAIL"), root)
    assert proc.returncode == 1 and "G1" in proc.stderr


def test_pre_apply_blocks_outside_allowlist(tmp_path):
    root = tmp_path / "repo"
    outside = "src/secret.py"
    sha = _seed_target(root, rel=outside)
    proc = _run_pre_apply(tmp_path, _proposed(sha, target_path=outside), base_audit("PASS"), root)
    assert proc.returncode == 1 and "G3" in proc.stderr


def test_pre_apply_blocks_audit_of_other_proposal(tmp_path):
    # G1: container digest が違う監査 (別提案の PASS) を流用させない。
    root = tmp_path / "repo"
    sha = _seed_target(root)
    audit = base_audit("PASS")
    audit["proposal_sha256"] = "e" * 64
    proc = _run_pre_apply(tmp_path, _proposed(sha), audit, root)
    assert proc.returncode == 1 and "別提案の監査" in proc.stderr


def test_pre_apply_allows_new_file_proposal_with_null_pre_image(tmp_path):
    # 対象ファイル不在 = 新規作成提案 (apply-gate-policy §3)。pre=null で通る。
    root = tmp_path / "repo"
    root.mkdir()
    proc = _run_pre_apply(tmp_path, _proposed(None), base_audit("PASS"), root)
    assert proc.returncode == 0


def test_pre_apply_blocks_null_pre_image_when_file_exists(tmp_path):
    # 新規作成提案のはずが実在する = 提案の前提が崩れている。
    root = tmp_path / "repo"
    _seed_target(root)
    proc = _run_pre_apply(tmp_path, _proposed(None), base_audit("PASS"), root)
    assert proc.returncode == 1 and "G4" in proc.stderr


def test_pre_apply_blocks_agree_for_other_diff(tmp_path):
    # agree=true は「特定の diff への同意」。C01 再実行後に C03 未再実行だと旧 agree が
    # 流用され誤 triage の Edit が着弾するため、diff_sha256 一致で主語を束縛する。
    root = tmp_path / "repo"
    sha = _seed_target(root)
    stale = base_verdict(True)
    stale["diff_sha256"] = "9" * 64  # triage-report とは別 diff への verdict
    proc = _run_pre_apply(tmp_path, _proposed(sha), base_audit("PASS"), root, verdict=stale)
    assert proc.returncode == 1
    assert "diff_sha256" in proc.stderr


def test_pre_apply_blocks_when_verifier_disagrees(tmp_path):
    # IN1: 独立 verifier が triage の見逃し/誤検出を指摘したまま (agree=false) は apply 不可。
    # close で初めて弾くのでは、誤った triage に基づく Edit が既に入っている。
    root = tmp_path / "repo"
    sha = _seed_target(root)
    proc = _run_pre_apply(tmp_path, _proposed(sha), base_audit("PASS"), root,
                          verdict=base_verdict(False))
    assert proc.returncode == 1
    assert "agree" in proc.stderr


def test_pre_apply_requires_triage_artifacts(tmp_path):
    # --triage-verdict / --triage-report 未指定は usage error
    # (agree と diff_sha256 束縛を検証せずに apply させない)。
    root = tmp_path / "repo"
    sha = _seed_target(root)
    pp = _write(tmp_path, "p.json", _proposed(sha))
    ap = _write(tmp_path, "a.json", base_audit("PASS"))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "pre-apply", "--issue", str(ISSUE),
         "--sync-proposal", str(pp), "--sync-audit-verdict", str(ap),
         "--target-root", str(root)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "--triage-report" in proc.stderr or "--triage-verdict" in proc.stderr


def test_close_mode_still_requires_triage_artifacts(tmp_path):
    # 後方互換: 既定 mode=close は C01/C03 必須のまま (usage error)。
    pp = _write(tmp_path, "p.json", base_proposal())
    ap = _write(tmp_path, "a.json", base_audit())
    vp = _write(tmp_path, "v.json", base_verdict(True))
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--issue", str(ISSUE),
         "--sync-proposal", str(pp), "--sync-audit-verdict", str(ap),
         "--triage-verdict", str(vp), "--target-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2 and "--triage-report" in proc.stderr


# ───────────── allowlist の path 正規化 (apply-gate-policy §1) ─────────────
# fnmatch は純字句照合で `*` が `/` を跨ぐため、正規化前に glob 照合すると `..` 列を
# allowlist が吸収して fail-open する。policy §1 は「先頭 `./`・`..` を排除」を要求する。
@pytest.mark.parametrize("path,allowed", [
    ("plugins/harness-creator/skills/x/references/rubric.json", True),
    ("./plugins/harness-creator/skills/x/references/rubric.json", True),
    ("plugins/harness-creator/skills/x/schemas/y.schema.json", True),
    # `..` で allowlist prefix を抜けて外部を指す (実体は repo/outside/rubric.json)
    ("plugins/harness-creator/../../outside/rubric.json", False),
    ("plugins/harness-creator/../../../etc/rubric.json", False),
    ("plugins/harness-creator/skills/../../other-plugin/rubric.json", False),
    # repo-root より上へ出る / 絶対 path
    ("../outside/rubric.json", False),
    ("/etc/passwd", False),
    ("/plugins/harness-creator/x/rubric.json", False),
    ("", False),
])
def test_allowlist_normalizes_before_glob_match(path, allowed):
    assert C10.in_allowlist(path) is allowed


def test_pre_apply_blocks_path_traversal_escape(tmp_path):
    """G3: `..` で allowlist の外を指す target_path を apply させない (fail-open 防止)。

    他の全ゲート (承認・監査PASS・agree・pre-image 一致) を満たしていても止まること。
    """
    root = tmp_path / "repo"
    outside = root / "outside"
    outside.mkdir(parents=True)
    victim = outside / "rubric.json"
    victim.write_text('{"victim": true}', encoding="utf-8")
    sha = hashlib.sha256(victim.read_bytes()).hexdigest()
    escape = "plugins/harness-creator/../../outside/rubric.json"
    proc = _run_pre_apply(tmp_path, _proposed(sha, target_path=escape), base_audit("PASS"), root)
    assert proc.returncode == 1
    assert "G3" in proc.stderr and "allowlist 外" in proc.stderr
    # ゲート自身は副作用なし (write-scope:none)
    assert victim.read_text(encoding="utf-8") == '{"victim": true}'
