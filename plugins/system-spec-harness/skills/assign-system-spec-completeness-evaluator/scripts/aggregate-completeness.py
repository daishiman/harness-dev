#!/usr/bin/env python3
# /// script
# name: aggregate-completeness
# version: 0.2.0
# purpose: C05 完成度評価レポートを fail-closed で集約し、matrix/知識グラフの決定論ゲートを実行する
# inputs:
#   - argv: --report FILE [--fork-ledger FILE] [--session ID] [--spec-dir DIR] / --matrix FILE [--require-complete] / --knowledge-graph / --hearing FILE --state FILE
# outputs:
#   - stdout: OK/violation 一覧または gate 結果 JSON
#   - exit: 0=OK / 1=violation or gate fail / 2=usage error
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: [audit_fork_attribution.py, validate-json-schema-subset.py]
# requires-python: ">=3.9"
# ///
"""C05 完成度レポートを検証・集約する CLI。

report 形状、全 6 観点の fail-closed verdict、high finding、独立監査の実 fork
証跡を一つの入口で検証する。台帳読取りと receipt 照合は
`audit_fork_attribution.py` に分離し、ここでは集約と CLI を所有する。

- `spec_dir_violations(report, spec_dir)` — report の spec_dir が評価を頼まれた dir に
  解決するかを照合する (呼び出し側の C02 が取込元と照合する前に、ラベル混入を落とす)。
- `derive_hearing_verdict(audit, spec_state)` — C06 (hearing-auditor) の重大度付き検出から、
  matrix_coverage の sub-input 判定を `references/aspect-criteria.md` の対応表どおりに導く。
  C06 自身の verdict は使わない (low 1 件で観点が FAIL になっていた不整合の是正)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# Keep the legacy names re-exported for callers while attribution lives in its local module.
from audit_fork_attribution import (  # noqa: E402,F401
    ASPECTS,
    ASPECT_VERDICTS,
    DELEGATION_ROLES,
    EVALUATOR_NAME,
    LEDGER_ENV,
    LEDGER_RELPATH,
    LEDGER_TOOL_NAMES,
    OVERALL_VERDICTS,
    SEVERITIES,
    SUB_INPUT_AUDITORS,
    agent_definition_exists,
    default_ledger_path,
    empty_ledger,
    ledger_corroborates,
    load_fork_ledger,
    required_delegations,
    validate_attribution,
)
_JSON_SCHEMA_SUBSET = Path(__file__).with_name("validate-json-schema-subset.py")
_SPEC = importlib.util.spec_from_file_location("json_schema_subset", _JSON_SCHEMA_SUBSET)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules["json_schema_subset"] = _MODULE
_SPEC.loader.exec_module(_MODULE)
Draft7SubsetValidator = _MODULE.Draft7SubsetValidator
SchemaDefinitionError = _MODULE.SchemaDefinitionError


SNAPSHOT_SCHEMA_VERSION = "system-spec-artifact-snapshot/v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMPLETENESS_SCHEMA = _SCRIPT_DIR.parent / "schemas" / "completeness-findings.schema.json"
PASS_GATE_IDS = {"G-matrix", "G-source-citation", "G-knowledge-graph"}
KNOWLEDGE_PROFILES = {"knowledge", "doctrine", "required-info", "cross"}


def validate_schema(report: dict) -> list[str]:
    """Validate the entire public report schema instead of duplicating its field rules."""
    try:
        schema = json.loads(COMPLETENESS_SCHEMA.read_text(encoding="utf-8"))
        validator = Draft7SubsetValidator(schema)
    except (OSError, json.JSONDecodeError, SchemaDefinitionError) as exc:
        return [f"schema の読取/構築に失敗: {exc}"]
    violations = []
    for error in sorted(
        validator.iter_errors(report),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        violations.append(f"schema {location}: {error.message}")
    return violations


def aggregate_verdict(aspect_verdicts: dict, high_count: int) -> str:
    """全観点と high finding から総合 verdict を fail-closed で再導出する。"""
    if set(aspect_verdicts) != set(ASPECTS):
        return "FAIL"
    if any(value not in ASPECT_VERDICTS for value in aspect_verdicts.values()):
        return "FAIL"
    if high_count > 0:
        return "FAIL"
    return "PASS" if all(value == "PASS" for value in aspect_verdicts.values()) else "FAIL"


def _high_count(findings: list) -> int:
    return sum(1 for finding in findings if isinstance(finding, dict) and finding.get("severity") == "high")


def validate_report(
    report: dict, ledger: dict | None = None, expected_session: str | None = None
) -> list[str]:
    """レポート形状、総合判定、実 fork 帰属を検証し違反リストを返す。"""
    violations: list[str] = []
    if not isinstance(report, dict):
        return ["report: オブジェクトでない"]

    violations.extend(validate_schema(report))

    evaluator = report.get("evaluator")
    if not isinstance(evaluator, dict):
        violations.append("evaluator: オブジェクトでない")
    else:
        if evaluator.get("name") != EVALUATOR_NAME:
            violations.append(f"evaluator.name != {EVALUATOR_NAME!r}")
        if evaluator.get("context") != "fork":
            violations.append("evaluator.context != 'fork' (独立 context 必須)")
        if not evaluator.get("version"):
            violations.append("evaluator.version が空")

    verdict = report.get("verdict")
    if verdict not in OVERALL_VERDICTS:
        violations.append(f"verdict={verdict!r} が {sorted(OVERALL_VERDICTS)} 外")

    snapshot = report.get("artifact_snapshot")
    if not isinstance(snapshot, dict):
        violations.append("artifact_snapshot: オブジェクトでない (評価入力への束縛必須)")
    else:
        if set(snapshot) != {"schema_version", "artifacts"}:
            violations.append("artifact_snapshot: field set が不正")
        if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            violations.append(
                f"artifact_snapshot.schema_version != {SNAPSHOT_SCHEMA_VERSION!r}"
            )
        snapshot_artifacts = snapshot.get("artifacts")
        if not isinstance(snapshot_artifacts, dict) or not snapshot_artifacts:
            violations.append("artifact_snapshot.artifacts: 非空オブジェクトでない")
        else:
            for relative, value in snapshot_artifacts.items():
                if not isinstance(relative, str) or not relative:
                    violations.append("artifact_snapshot.artifacts: 空または非文字列 path")
                if not isinstance(value, str) or SHA256.fullmatch(value) is None:
                    violations.append(
                        f"artifact_snapshot.artifacts[{relative!r}]: sha256 が不正"
                    )

    aspects = report.get("aspects")
    aspect_verdicts: dict[str, str] = {}
    if not isinstance(aspects, dict):
        violations.append("aspects: オブジェクトでない")
    else:
        extra = set(aspects) - set(ASPECTS)
        missing = set(ASPECTS) - set(aspects)
        if extra:
            violations.append(f"aspects: 未知の観点 {sorted(extra)}")
        if missing:
            violations.append(f"aspects: 観点欠落 {sorted(missing)} (全観点を過不足なく)")
        for aspect_id, specification in ASPECTS.items():
            aspect = aspects.get(aspect_id)
            if not isinstance(aspect, dict):
                continue
            aspect_verdict = aspect.get("verdict")
            if aspect_verdict not in ASPECT_VERDICTS:
                violations.append(f"aspects[{aspect_id}].verdict={aspect_verdict!r} が {sorted(ASPECT_VERDICTS)} 外")
            else:
                aspect_verdicts[aspect_id] = aspect_verdict
            if aspect.get("auditor") != specification["auditor"]:
                violations.append(f"aspects[{aspect_id}].auditor != {specification['auditor']!r} (観点↔監査 agent 対応)")
            if aspect.get("component") != specification["component"]:
                violations.append(f"aspects[{aspect_id}].component != {specification['component']!r}")
            if not aspect.get("summary"):
                violations.append(f"aspects[{aspect_id}].summary が空")

    gaps = report.get("gaps")
    if not isinstance(gaps, list):
        violations.append("gaps: 配列でない (不足事項一覧)")
        gaps = []

    findings = report.get("findings")
    if not isinstance(findings, list) or not findings:
        violations.append("findings: 非空配列でない (PASS 時も info を 1 件以上残す)")
        findings = []
    else:
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                violations.append(f"findings[{index}]: オブジェクトでない")
                continue
            if finding.get("severity") not in SEVERITIES:
                violations.append(f"findings[{index}].severity={finding.get('severity')!r} が {sorted(SEVERITIES)} 外")
            if not finding.get("bucket"):
                violations.append(f"findings[{index}].bucket が空")
            if not finding.get("observation"):
                violations.append(f"findings[{index}].observation が空")

    gate_results = report.get("gate_results")
    if verdict == "PASS":
        by_id = {
            item.get("id"): item
            for item in gate_results
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        } if isinstance(gate_results, list) else {}
        for gate_id in sorted(PASS_GATE_IDS):
            result = by_id.get(gate_id)
            if not isinstance(result, dict) or result.get("exit_code") != 0:
                violations.append(f"PASS report lacks passing gate: {gate_id}")
        knowledge = by_id.get("G-knowledge-graph")
        subgates = knowledge.get("subgates") if isinstance(knowledge, dict) else None
        profiles = {
            item.get("profile")
            for item in subgates
            if isinstance(item, dict) and item.get("exit_code") == 0
        } if isinstance(subgates, list) else set()
        if profiles != KNOWLEDGE_PROFILES or len(subgates or []) != len(KNOWLEDGE_PROFILES):
            violations.append(
                "PASS report knowledge gate lacks four passing profiles: "
                + ",".join(sorted(KNOWLEDGE_PROFILES))
            )

    if isinstance(aspects, dict) and verdict in OVERALL_VERDICTS:
        derived = aggregate_verdict(aspect_verdicts, _high_count(findings))
        if derived != verdict:
            violations.append(
                f"verdict={verdict!r} が 全観点 + high finding 数からの fail-closed 再導出 "
                f"{derived!r} と不一致 (総合判定が観点スコアに接地していない)"
            )
    if verdict == "FAIL" and not gaps:
        violations.append("verdict=FAIL だが gaps (不足事項一覧) が空 (差し戻し材料が無い)")
    violations.extend(validate_attribution(report, ledger, expected_session))
    return violations


def spec_dir_violations(report, spec_dir: str) -> list[str]:
    """report の spec_dir が、評価を頼まれた spec_dir と同じ dir に解決するかを照合する (空=OK)。

    呼び出し側 (dev-graph の C02) は report の spec_dir を取込元のディレクトリと照合し、
    一致しなければ確定の取込を拒む。ラベルや注記を混ぜた spec_dir をここで先に落とす。
    相対パスは cwd から解決し、両方を resolve して比べる。
    """
    declared = report.get("spec_dir") if isinstance(report, dict) else None
    if not isinstance(declared, str) or not declared:
        return [f"spec_dir_mismatch: report に spec_dir (文字列) が無い (--spec-dir={spec_dir!r})"]
    if Path(declared).expanduser().resolve() != Path(spec_dir).expanduser().resolve():
        return [f"spec_dir_mismatch: report の spec_dir={declared!r} が --spec-dir={spec_dir!r} と同じ dir に解決しない"]
    return []


# --------------------------------------------------------------------------- #
# C06 (hearing-auditor) の検出 → matrix_coverage の sub-input 判定             #
# --------------------------------------------------------------------------- #
# 軸の id は R6-audit-hearing.md の監査 5 軸と 1 対 1 (番号は R6 の軸番号)。
HEARING_AXES: dict[str, int] = {
    "missed-collection": 1,
    "leading-question": 2,
    "premature-stop": 3,
    "traceability": 4,
    "foundation-trace": 5,
}
HEARING_SEVERITIES = {"high", "medium", "low", "info"}


def _primary_qa_refs(spec_state: dict) -> set[str]:
    """確定セルの主たる接地根拠 (qa_ref) の集合。裏付け (qa_refs) と対象外セルは含めない。"""
    out: set[str] = set()
    for row in (spec_state.get("matrix") or {}).values():
        if not isinstance(row, dict):
            continue
        for cell in row.values():
            if isinstance(cell, dict) and cell.get("state") == "確定" and isinstance(cell.get("qa_ref"), str):
                out.add(cell["qa_ref"])
    return out


def _supersession_gap(qa_id: str, finding: dict, entries: dict, primary: set[str], findings: list) -> str | None:
    """置き換えが有効なら None、無効ならその理由を返す。

    有効の条件 (neutral-question-criteria.md): (a) 新しい問が中立 (b) 同じ論点
    (c) 利用者の回答が記録されている。(a)(b) は意味の判定なので C06 の
    ``supersession_valid`` を要し、(a) はさらに置き換え先に medium 以上の
    誘導の検出が無いことで裏を取る。(c) はここで決定論に再検査する。
    """
    if finding.get("supersession_valid") is not True:
        return "C06 が置き換えの有効性 (a)(b) を認めていない (supersession_valid が true でない)"
    if qa_id in primary:
        return "旧い問が確定セルの主たる接地根拠 (qa_ref) のまま"
    seen = {qa_id}
    current = qa_id
    while True:
        nxt = entries[current].get("superseded_by")
        if nxt is None:
            break
        if nxt not in entries:
            return f"置き換え先 {nxt!r} が qa_log に無い"
        if nxt in seen:
            return f"置き換えが循環している ({nxt!r})"
        seen.add(nxt)
        current = nxt
    retired_primary = sorted((seen - {current}) & primary)
    if retired_primary:
        return f"置き換え済みの問 {retired_primary} が確定セルの主たる接地根拠 (qa_ref) のまま"
    final = entries[current]
    if not str(final.get("answer") or "").strip() or final.get("basis") != "user-decision" or not final.get("answered_at"):
        return f"置き換え先 {current!r} に利用者の回答 (answer / basis=user-decision / answered_at) が揃っていない"
    for other in findings:
        if (
            other.get("axis") == "leading-question"
            and other.get("qa_id") == current
            and other.get("severity") in ("high", "medium")
        ):
            return f"置き換え先 {current!r} にも {other.get('severity')} の誘導の検出がある (中立な問でない)"
    return None


def derive_hearing_verdict(audit, spec_state) -> dict:
    """C06 の検出と重大度から matrix_coverage の sub-input 判定を導く (副作用なし)。

    対応の正本は ``references/aspect-criteria.md`` の「ヒアリング監査 (C06) の重大度と
    判定の対応」。ここはその表の決定論実装で、表と食い違ったら表を正とする。

    - 置き換えが有効な問への誘導の検出 → closed (閉じた検出。判定に数えず報告に残す)
    - high → blocking
    - medium → 誘導の検出 (軸 2) は、その問が確定セルの主たる接地根拠 (qa_ref) の
      ときだけ blocking。それ以外の軸の medium は blocking (問に限った緩和である)
    - low / info → notes (PASS に残す注記)
    - C06 が INDETERMINATE、入力の形が不正 → INDETERMINATE (C06 の再実行・入力補完)

    C06 自身が返した verdict は判定に使わない (``declared`` として返すだけ)。以前は
    C06 が「1 軸以上に検出があれば FAIL」としていたため、low 1 件で matrix_coverage が
    FAIL になり、総合判定まで落ちていた。
    """
    result = {
        "verdict": "INDETERMINATE",
        "declared": audit.get("verdict") if isinstance(audit, dict) else None,
        "blocking": [],
        "notes": [],
        "closed": [],
        "errors": [],
    }
    if not isinstance(audit, dict):
        result["errors"].append("C06 の出力がオブジェクトでない")
        return result
    if audit.get("verdict") == "INDETERMINATE":
        result["errors"].append("C06 が INDETERMINATE (監査不能) を返した")
        return result
    if not isinstance(spec_state, dict) or not isinstance(spec_state.get("qa_log"), list) \
            or not isinstance(spec_state.get("matrix"), dict):
        result["errors"].append("spec-state に qa_log (配列) と matrix (オブジェクト) が無い")
        return result
    findings = audit.get("findings")
    if not isinstance(findings, list):
        result["errors"].append("findings が配列でない")
        return result

    entries = {e["id"]: e for e in spec_state["qa_log"] if isinstance(e, dict) and isinstance(e.get("id"), str)}
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            result["errors"].append(f"findings[{i}]: オブジェクトでない")
            continue
        if f.get("axis") not in HEARING_AXES:
            result["errors"].append(f"findings[{i}].axis={f.get('axis')!r} が {sorted(HEARING_AXES)} 外")
        if f.get("severity") not in HEARING_SEVERITIES:
            result["errors"].append(f"findings[{i}].severity={f.get('severity')!r} が {sorted(HEARING_SEVERITIES)} 外")
        if not str(f.get("observation") or "").strip():
            result["errors"].append(f"findings[{i}].observation が空")
        if f.get("axis") == "leading-question":
            if f.get("qa_id") not in entries:
                result["errors"].append(f"findings[{i}].qa_id={f.get('qa_id')!r} が qa_log に無い (誘導の検出は問を指す)")
        elif not any(f.get(k) for k in ("qa_id", "cell", "u_item", "field")):
            result["errors"].append(f"findings[{i}]: 対象 (qa_id / cell / u_item / field) が無い")
    if result["errors"]:
        return result

    primary = _primary_qa_refs(spec_state)
    for f in findings:
        item = dict(f)
        qa_id = f.get("qa_id")
        if f["axis"] == "leading-question" and entries[qa_id].get("superseded_by") is not None:
            gap = _supersession_gap(qa_id, f, entries, primary, findings)
            if gap is None:
                item["superseded_by"] = entries[qa_id]["superseded_by"]
                result["closed"].append(item)
                continue
            item["supersession_rejected"] = gap
        severity = f["severity"]
        if severity == "high":
            blocking = True
        elif severity == "medium":
            blocking = qa_id in primary if f["axis"] == "leading-question" else True
        else:
            blocking = False
        if f["axis"] == "leading-question":
            item["primary_ground"] = qa_id in primary
        (result["blocking"] if blocking else result["notes"]).append(item)
    result["verdict"] = "FAIL" if result["blocking"] else "PASS"
    return result


def _plugin_root() -> Path:
    """.../skills/<skill>/scripts/aggregate-completeness.py から plugin root を返す。"""
    return Path(__file__).resolve().parents[3]


def run_coverage_gate(matrix_path, require_complete: bool = False) -> dict:
    """C05 の matrix deterministic gate を実行する。"""
    gate = _plugin_root() / "scripts" / "validate-coverage-matrix.py"
    command = [sys.executable or "python3", str(gate), "--matrix", str(matrix_path)]
    if require_complete:
        command.append("--require-complete")
    process = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "id": "G-matrix",
        "name": "validate-coverage-matrix",
        "conditions": ["matrix_coverage"],
        "command": [str(item) for item in command],
        "exit_code": int(process.returncode),
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }


def run_knowledge_graph_gate() -> dict:
    """C13-C16 の knowledge/doctrine/required-info/cross gate を独立再実行する。"""
    root = _plugin_root()
    gate = root / "scripts" / "validate-knowledge-graph.py"
    design_references = root / "skills" / "ref-system-design-knowledge" / "references"
    elicit_references = root / "skills" / "run-system-spec-elicit" / "references"
    doctrine = design_references / "doctrine-anchor-registry.json"
    required_info = elicit_references / "required-info-catalog.json"
    python = sys.executable or "python3"
    runs = (
        ("knowledge", [python, str(gate), "--profile", "knowledge", "--input", str(design_references / "knowledge-catalog.json")]),
        ("doctrine", [python, str(gate), "--profile", "doctrine", "--input", str(doctrine)]),
        ("required-info", [python, str(gate), "--profile", "required-info", "--input", str(required_info)]),
        ("cross", [python, str(gate), "--profile", "cross", "--taxonomy", str(design_references / "system-category-taxonomy.json"), "--doctrine", str(doctrine), "--required-info", str(required_info)]),
    )
    subgates = []
    worst = 0
    for name, command in runs:
        process = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        subgates.append({
            "profile": name,
            "command": [str(item) for item in command],
            "exit_code": int(process.returncode),
            "stderr": process.stderr.strip(),
        })
        return_code = int(process.returncode)
        normalized_failure = return_code if return_code > 0 else (1 if return_code < 0 else 0)
        worst = max(worst, normalized_failure)
    return {
        "id": "G-knowledge-graph",
        "name": "validate-knowledge-graph",
        "conditions": ["design_knowledge_reflection", "matrix_coverage"],
        "exit_code": worst,
        "subgates": subgates,
    }


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="C05 完成度評価レポートの形状検証 / 決定論ゲート実行")
    parser.add_argument("--report", help="評価レポート JSON のパス")
    parser.add_argument("--fork-ledger", help="監査 fork 台帳 JSONL のパス")
    parser.add_argument("--session", help="現在の評価 run の session_id (receipt と照合)")
    parser.add_argument("--matrix", help="spec-state.json のパス (matrix gate を実行)")
    parser.add_argument("--require-complete", action="store_true", help="matrix gate を未収集 0 必須で実行")
    parser.add_argument("--knowledge-graph", action="store_true", help="C13-C16 の 4 profile gate を実行")
    parser.add_argument("--spec-dir", help="--report と併用。report の spec_dir がこの dir に解決するかも検証する")
    parser.add_argument("--hearing", help="C06 (hearing-auditor) の出力 JSON。--state と併用し sub-input 判定を導く")
    parser.add_argument("--state", help="--hearing の判定に使う spec-state.json (確定セルの qa_ref と置き換えを読む)")
    args = parser.parse_args(argv)
    if not args.report and not args.matrix and not args.knowledge_graph and not args.hearing:
        parser.error("--report / --matrix / --knowledge-graph / --hearing のいずれかが必要")
    if bool(args.hearing) != bool(args.state):
        parser.error("--hearing と --state は併用する")
    if args.spec_dir is not None and not args.report:
        parser.error("--spec-dir は --report と併用する")

    return_code = 0
    if args.matrix:
        result = run_coverage_gate(args.matrix, require_complete=args.require_complete)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["exit_code"] != 0:
            return_code = 1
    if args.knowledge_graph:
        result = run_knowledge_graph_gate()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["exit_code"] != 0:
            return_code = 1
    if args.hearing:
        loaded = []
        for label, raw in (("hearing", args.hearing), ("state", args.state)):
            path = Path(raw)
            if not path.is_file():
                print(f"{label} ファイルが存在しない: {raw}", file=sys.stderr)
                return 2
            try:
                loaded.append(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                print(f"{label} の JSON parse 失敗: {exc}", file=sys.stderr)
                return 2
        hearing = derive_hearing_verdict(loaded[0], loaded[1])
        print(json.dumps(hearing, ensure_ascii=False, indent=2))
        if hearing["verdict"] != "PASS":
            return_code = 1
    if args.report:
        report_path = Path(args.report)
        if not report_path.is_file():
            print(f"report ファイルが存在しない: {args.report}", file=sys.stderr)
            return 2
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"report の JSON parse 失敗: {exc}", file=sys.stderr)
            return 2
        ledger = load_fork_ledger(args.fork_ledger or default_ledger_path())
        violations = validate_report(report, ledger, expected_session=args.session)
        if args.spec_dir is not None:
            if not Path(args.spec_dir).expanduser().is_dir():
                print(f"spec-dir ディレクトリが存在しない: {args.spec_dir}", file=sys.stderr)
                return 2
            violations += spec_dir_violations(report, args.spec_dir)
        if violations:
            for message in violations:
                print(f"VIOLATION: {message}", file=sys.stderr)
            print(
                f"FAIL: {len(violations)} 件のレポート整合違反 (fork 台帳: {ledger['path']} / "
                f"exists={ledger['exists']} / 裏取り fork {sum(ledger['dispatched'].values())} 件)",
                file=sys.stderr,
            )
            return_code = 1
        else:
            print(f"OK: レポート形状・総合判定整合・独立 auditor 帰属の fork 証跡接地を満たす (verdict={report.get('verdict')})")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
