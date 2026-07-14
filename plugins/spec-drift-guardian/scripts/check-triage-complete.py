#!/usr/bin/env python3
# /// script
# name: check-triage-complete
# purpose: C10 close 前共有ゲート。対象 issue の完全 diff triage-report・独立 triage-verdict・sync-proposal・独立 sync-audit-verdict・明示承認・実ファイル post-image を突合し、applied_verified または independently_verified_no_change のみ OK として proposal-only/未承認/未適用/hash 不一致/verdict FAIL/agree false を fail-closed で拒否する。
# inputs:
#   - argv: --issue NUMBER --triage-report FILE --triage-verdict FILE --sync-proposal FILE --sync-audit-verdict FILE --target-root DIR
# outputs:
#   - stdout: JSON {result, status, reasons} (result=OK|INCOMPLETE, status=applied_verified|independently_verified_no_change|理由)
#   - stderr: schema/close violation の逐条
#   - exit: 0=OK(close 可) / 1=INCOMPLETE(close 遮断) / 2=usage/schema error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""C10: triage 完了 close 前共有ゲート (spec-drift-guardian)。

C07 (issue close) / C06 (orchestrator) が close を許可する前に、対象 issue に紐づく
4 artifact (C01 triage-report / C03 triage-verdict / C02 sync-proposal / C04 sync-audit-verdict)
と C11 provenance、実ファイルの post-image を独立に突合する決定論ゲート。

close (exit 0) を許可するのは以下を全て満たすときのみ:
  1. 4 artifact が各 schema に妥当 (必須キー + enum。malformed は exit 2)。
  2. cross-artifact digest 整合:
     triage_verdict.diff_sha256 == triage_report.diff_sha256、
     sync_audit_verdict.proposal_sha256 == sync_proposal.proposal_sha256。
  3. triage_verdict.agree == true (独立 verifier が triage に同意)。
  4. sync_audit_verdict.verdict == "PASS" (proposer != approver)。
  5. 次のいずれかの close 経路:
     - applied_verified 経路: sync_proposal.status == "applied_verified" かつ
       approval.granted == true (issue 単位ゲート) かつ proposals[] の全要素が
       (post_image_sha256 非 null かつ --target-root/target_path の実ファイル
       sha256 == post_image_sha256 かつ validator_results が全 passed かつ
       target_path が allowlist 内)。→ status=applied_verified。
     - verified-no-change 経路: triage で impacted==true な軸が 0 件かつ
       agree == true (コード変更不要だが独立 verdict は必須)。
       → status=independently_verified_no_change。

上記以外 (proposal-only=status proposed / 未承認 / 未適用 / hash 不一致 /
validator fail / verdict FAIL / agree false) は INCOMPLETE (exit 1) とし、
拒否理由を reasons へ列挙する。fail-closed・stdlib only・network:false・write-scope:none。
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

# --- schema enum 定数 (schemas/*.schema.json と一致) ---
ARTIFACT_KINDS = {"rubric", "schema", "template", "other"}
AXES = {"name", "type", "required", "enum", "semantics"}
FINDING_KINDS = {"missed", "false-positive", "mismatch"}
PROPOSAL_STATUS = {"proposed", "applied_verified"}
AUDIT_VERDICTS = {"PASS", "FAIL"}

# --- allowlist glob (references/apply-gate-policy.md §1 と一致) ---
ALLOWLIST = [
    "plugins/harness-creator/**/rubric.json",
    "plugins/harness-creator/**/templates/**",
    "plugins/harness-creator/**/*.schema.json",
]


def in_allowlist(path: str) -> bool:
    """target_path が apply-gate allowlist glob のいずれかに一致するか (決定論照合)。"""
    p = PurePosixPath(path).as_posix()
    return any(fnmatch.fnmatch(p, g) for g in ALLOWLIST)


def _is_bool(v: object) -> bool:
    return isinstance(v, bool)


def _is_int(v: object) -> bool:
    # JSON の boolean は int の派生なので明示的に除外する。
    return isinstance(v, int) and not isinstance(v, bool)


def _require(d: object, keys: list[str], label: str, errors: list[str]) -> bool:
    """d が dict かつ全 required keys を持つか検査する。欠落は errors へ記録。"""
    if not isinstance(d, dict):
        errors.append(f"{label}: JSON オブジェクトでない")
        return False
    missing = [k for k in keys if k not in d]
    if missing:
        errors.append(f"{label}: 必須キー欠落: {', '.join(missing)}")
        return False
    return True


def _validate_impacts(items: object, label: str, errors: list[str]) -> None:
    """triage-report.impacts / triage-verdict.rederived_impacts の共通構造検査。"""
    if not isinstance(items, list):
        errors.append(f"{label}: 配列でない")
        return
    keys = ["artifact_kind", "artifact_path", "axis", "before", "after", "impacted", "evidence"]
    for i, it in enumerate(items):
        if not _require(it, keys, f"{label}[{i}]", errors):
            continue
        if it.get("artifact_kind") not in ARTIFACT_KINDS:
            errors.append(f"{label}[{i}].artifact_kind={it.get('artifact_kind')!r} が enum 外")
        if it.get("axis") not in AXES:
            errors.append(f"{label}[{i}].axis={it.get('axis')!r} が enum 外")
        if not _is_bool(it.get("impacted")):
            errors.append(f"{label}[{i}].impacted が boolean でない")


def validate_triage_report(d: object, errors: list[str]) -> None:
    label = "triage-report"
    if not _require(d, ["issue", "base_commit", "source_commit", "diff_sha256", "complete", "impacts"], label, errors):
        return
    if not _is_int(d.get("issue")):
        errors.append(f"{label}.issue が integer でない")
    if d.get("complete") is not True:
        errors.append(f"{label}.complete が true でない (完全 diff 証明が無い)")
    if not isinstance(d.get("diff_sha256"), str):
        errors.append(f"{label}.diff_sha256 が文字列でない")
    _validate_impacts(d.get("impacts"), f"{label}.impacts", errors)


def validate_triage_verdict(d: object, errors: list[str]) -> None:
    label = "triage-verdict"
    if not _require(d, ["issue", "diff_sha256", "rederived_impacts", "agree", "findings", "verdict_sha256"], label, errors):
        return
    if not _is_int(d.get("issue")):
        errors.append(f"{label}.issue が integer でない")
    if not isinstance(d.get("diff_sha256"), str):
        errors.append(f"{label}.diff_sha256 が文字列でない")
    if not _is_bool(d.get("agree")):
        errors.append(f"{label}.agree が boolean でない")
    _validate_impacts(d.get("rederived_impacts"), f"{label}.rederived_impacts", errors)
    findings = d.get("findings")
    if not isinstance(findings, list):
        errors.append(f"{label}.findings が配列でない")
    else:
        for i, it in enumerate(findings):
            if not _require(it, ["kind", "axis", "artifact_path", "detail"], f"{label}.findings[{i}]", errors):
                continue
            if it.get("kind") not in FINDING_KINDS:
                errors.append(f"{label}.findings[{i}].kind={it.get('kind')!r} が enum 外")
            if it.get("axis") not in AXES:
                errors.append(f"{label}.findings[{i}].axis={it.get('axis')!r} が enum 外")


def validate_sync_proposal(d: object, errors: list[str]) -> None:
    """sync-proposal コンテナ形の妥当性検査。

    issue/proposal_sha256/status/approval は issue 単位のゲート、proposals[] は
    proposal 単位の適用証跡 (minItems 1)。
    """
    label = "sync-proposal"
    keys = ["issue", "proposal_sha256", "status", "approval", "proposals"]
    if not _require(d, keys, label, errors):
        return
    if not _is_int(d.get("issue")):
        errors.append(f"{label}.issue が integer でない")
    if not isinstance(d.get("proposal_sha256"), str):
        errors.append(f"{label}.proposal_sha256 が文字列でない")
    if d.get("status") not in PROPOSAL_STATUS:
        errors.append(f"{label}.status={d.get('status')!r} が enum 外 (proposed|applied_verified)")
    approval = d.get("approval")
    if not _require(approval, ["granted", "by", "evidence"], f"{label}.approval", errors):
        pass
    elif not _is_bool(approval.get("granted")):
        errors.append(f"{label}.approval.granted が boolean でない")
    proposals = d.get("proposals")
    if not isinstance(proposals, list) or len(proposals) < 1:
        errors.append(f"{label}.proposals が 1 件以上の配列でない")
        return
    p_keys = [
        "target_path", "axis", "before", "after",
        "proposed_diff", "pre_image_sha256", "post_image_sha256", "validator_results",
    ]
    for i, p in enumerate(proposals):
        plabel = f"{label}.proposals[{i}]"
        if not _require(p, p_keys, plabel, errors):
            continue
        if not (isinstance(p.get("target_path"), str) and p.get("target_path")):
            errors.append(f"{plabel}.target_path が非空文字列でない")
        if p.get("axis") not in AXES:
            errors.append(f"{plabel}.axis={p.get('axis')!r} が enum 外")
        post = p.get("post_image_sha256")
        if post is not None and not isinstance(post, str):
            errors.append(f"{plabel}.post_image_sha256 が文字列/null でない")
        vr = p.get("validator_results")
        if not isinstance(vr, list):
            errors.append(f"{plabel}.validator_results が配列でない")
        else:
            for j, it in enumerate(vr):
                if not _require(it, ["validator", "exit_code", "passed"], f"{plabel}.validator_results[{j}]", errors):
                    continue
                if not _is_int(it.get("exit_code")):
                    errors.append(f"{plabel}.validator_results[{j}].exit_code が integer でない")
                if not _is_bool(it.get("passed")):
                    errors.append(f"{plabel}.validator_results[{j}].passed が boolean でない")


def validate_sync_audit_verdict(d: object, errors: list[str]) -> None:
    label = "sync-audit-verdict"
    keys = ["issue", "proposal_sha256", "audited_targets", "omissions", "excesses", "allowlist_violations", "verdict"]
    if not _require(d, keys, label, errors):
        return
    if not _is_int(d.get("issue")):
        errors.append(f"{label}.issue が integer でない")
    if not isinstance(d.get("proposal_sha256"), str):
        errors.append(f"{label}.proposal_sha256 が文字列でない")
    if d.get("verdict") not in AUDIT_VERDICTS:
        errors.append(f"{label}.verdict={d.get('verdict')!r} が enum 外 (PASS|FAIL)")
    targets = d.get("audited_targets")
    if not isinstance(targets, list) or len(targets) < 1:
        errors.append(f"{label}.audited_targets が 1 件以上の配列でない")
    else:
        for i, it in enumerate(targets):
            if not _require(it, ["target_path", "axis"], f"{label}.audited_targets[{i}]", errors):
                continue
            if it.get("axis") not in AXES:
                errors.append(f"{label}.audited_targets[{i}].axis={it.get('axis')!r} が enum 外")
    for arr_key in ("omissions", "excesses", "allowlist_violations"):
        if not isinstance(d.get(arr_key), list):
            errors.append(f"{label}.{arr_key} が配列でない")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(
    issue: int,
    report: dict,
    verdict: dict,
    proposal: dict,
    audit: dict,
    target_root: Path,
) -> tuple[str, str, list[str]]:
    """close 判定を行い (result, status, reasons) を返す。

    result="OK" のとき status は close 経路名。"INCOMPLETE" のとき status は primary 拒否理由。
    """
    global_reasons: list[str] = []

    # 2. cross-artifact digest 整合。
    if verdict.get("diff_sha256") != report.get("diff_sha256"):
        global_reasons.append("triage_verdict.diff_sha256 が triage_report.diff_sha256 と不一致 (別 diff の検証)")
    if audit.get("proposal_sha256") != proposal.get("proposal_sha256"):
        global_reasons.append("sync_audit_verdict.proposal_sha256 が sync_proposal.proposal_sha256 と不一致 (別提案の監査)")

    # 対象 issue の一貫性 (4 artifact + --issue)。
    for name, art in (
        ("triage_report", report),
        ("triage_verdict", verdict),
        ("sync_proposal", proposal),
        ("sync_audit_verdict", audit),
    ):
        if art.get("issue") != issue:
            global_reasons.append(f"{name}.issue={art.get('issue')!r} が --issue={issue} と不一致")

    # 3. 独立 verifier が triage に同意。
    agree = verdict.get("agree")
    if agree is not True:
        global_reasons.append("triage_verdict.agree が true でない (独立 verifier が triage に不同意)")

    # 4. 独立 auditor の verdict。
    if audit.get("verdict") != "PASS":
        global_reasons.append(f"sync_audit_verdict.verdict={audit.get('verdict')!r} が PASS でない")

    # 5. close 経路。
    impacts = report.get("impacts") or []
    has_impact = any(isinstance(i, dict) and i.get("impacted") is True for i in impacts)

    # --- applied_verified 経路 (issue 単位ゲート + 全 proposal の適用証跡) ---
    applied_reasons: list[str] = []
    status_val = proposal.get("status")
    if status_val != "applied_verified":
        applied_reasons.append(f"sync_proposal.status={status_val!r} が applied_verified でない (proposal-only は close 不可)")
    approval = proposal.get("approval") or {}
    if approval.get("granted") is not True:
        applied_reasons.append("sync_proposal.approval.granted が true でない (明示承認なし)")
    # proposals[] を走査し、全要素が適用証跡を満たすことを要求する。
    proposals = proposal.get("proposals") or []
    for idx, p in enumerate(proposals):
        p = p if isinstance(p, dict) else {}
        target_rel = str(p.get("target_path") or "")
        if not in_allowlist(target_rel):
            applied_reasons.append(f"sync_proposal.proposals[{idx}].target_path={target_rel!r} が allowlist 外")
        post = p.get("post_image_sha256")
        if not post:
            applied_reasons.append(f"sync_proposal.proposals[{idx}].post_image_sha256 が null/空 (未適用)")
        else:
            actual_file = target_root / target_rel
            if not actual_file.is_file():
                applied_reasons.append(f"sync_proposal.proposals[{idx}] post-image 対象ファイルが存在しない: {actual_file}")
            else:
                actual = sha256_file(actual_file)
                if actual != post:
                    applied_reasons.append(
                        f"sync_proposal.proposals[{idx}] 実ファイル post-image sha256 が post_image_sha256 と不一致 (drift): actual={actual} expected={post}"
                    )
        vr = p.get("validator_results") or []
        if not vr:
            applied_reasons.append(f"sync_proposal.proposals[{idx}].validator_results が空 (適用後 validator 未実行)")
        else:
            failed = [v.get("validator") for v in vr if not (isinstance(v, dict) and v.get("passed") is True)]
            if failed:
                applied_reasons.append(f"sync_proposal.proposals[{idx}].validator_results に fail あり: {failed}")
    applied_ok = not applied_reasons

    # --- verified-no-change 経路 ---
    nochange_reasons: list[str] = []
    if has_impact:
        nochange_reasons.append("triage_report.impacts に impacted==true があり (コード変更が必要)")
    if agree is not True:
        nochange_reasons.append("triage_verdict.agree が true でない (独立 verdict 必須)")
    nochange_ok = not nochange_reasons

    if not global_reasons:
        if applied_ok:
            return "OK", "applied_verified", []
        if nochange_ok:
            return "OK", "independently_verified_no_change", []

    # INCOMPLETE: 情報量の多い経路の理由を添える。
    path_reasons = applied_reasons if has_impact else nochange_reasons
    reasons = global_reasons + path_reasons
    if not reasons:
        # global_reasons が空でも両経路 NG (has_impact だが applied_reasons 空はありえない構造。防御的)。
        reasons = ["close 経路 (applied_verified / independently_verified_no_change) を満たさない"]
    status = reasons[0]
    return "INCOMPLETE", status, reasons


def _load_json(path: Path, label: str, errors: list[str]):
    if not path.is_file():
        errors.append(f"{label} が見つからない: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"{label} の JSON parse error: {exc}")
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="C10 close 前共有ゲート: 4 artifact + 実 post-image を突合し applied_verified / independently_verified_no_change のみ close 可とする",
    )
    ap.add_argument("--issue", type=int, required=True, help="対象 GitHub issue 番号")
    ap.add_argument("--triage-report", required=True, help="C01 triage-report.json")
    ap.add_argument("--triage-verdict", required=True, help="C03 triage-verdict.json")
    ap.add_argument("--sync-proposal", required=True, help="C02 sync-proposal.json")
    ap.add_argument("--sync-audit-verdict", required=True, help="C04 sync-audit-verdict.json")
    ap.add_argument("--target-root", required=True, help="post-image 実ファイルを解決する repo-root ディレクトリ")
    args = ap.parse_args(argv)

    # --- 入力ロード (usage error → exit 2) ---
    load_errors: list[str] = []
    report = _load_json(Path(args.triage_report), "triage-report", load_errors)
    verdict = _load_json(Path(args.triage_verdict), "triage-verdict", load_errors)
    proposal = _load_json(Path(args.sync_proposal), "sync-proposal", load_errors)
    audit = _load_json(Path(args.sync_audit_verdict), "sync-audit-verdict", load_errors)
    if load_errors:
        for e in load_errors:
            sys.stderr.write(e + "\n")
        _emit(sys.stdout, "ERROR", load_errors[0], load_errors)
        return 2

    # --- schema 妥当性 (malformed → exit 2) ---
    schema_errors: list[str] = []
    validate_triage_report(report, schema_errors)
    validate_triage_verdict(verdict, schema_errors)
    validate_sync_proposal(proposal, schema_errors)
    validate_sync_audit_verdict(audit, schema_errors)
    if schema_errors:
        for e in schema_errors:
            sys.stderr.write(e + "\n")
        _emit(sys.stdout, "ERROR", "schema error", schema_errors)
        return 2

    # --- close 判定 ---
    result, status, reasons = evaluate(
        args.issue, report, verdict, proposal, audit, Path(args.target_root)
    )
    _emit(sys.stdout, result, status, reasons)
    if result != "OK":
        for r in reasons:
            sys.stderr.write(r + "\n")
        return 1
    return 0


def _emit(stream, result: str, status: str, reasons: list[str]) -> None:
    stream.write(
        json.dumps({"result": result, "status": status, "reasons": reasons}, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
