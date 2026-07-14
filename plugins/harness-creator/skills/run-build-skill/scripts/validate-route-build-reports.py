#!/usr/bin/env python3
# /// script
# name: validate-route-build-reports
# purpose: Validate per-route build reports under eval-log/<slug>/build/ against handoff routes (L4 execution handover chain).
# inputs:
#   - argv: --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json [--reports-dir DIR] (--route ID | --complete)
# outputs:
#   - stdout: JSON {"valid": bool, "mode": str, "findings": [str, ...]}
#   - exit: 0=PASS / 1=validation failure / 2=usage or JSON error
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""plugin 一括 build の route 実行レポート (route-build-report) を検証する。

契約正本: references/route-build-report.md / schemas/route-build-report.schema.json

Usage:
  # route 1 本の完了直後: レポート形状 + handoff 整合 + 依存チェーンを検証
  validate-route-build-reports.py --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json --route C01

  # 全 route 終端: 全レポート実在 + failure ゼロ + orphan ゼロを検証
  validate-route-build-reports.py --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json --complete

  # 内蔵 self-test (一時ディレクトリ上で代表シナリオを検査)
  validate-route-build-reports.py --self-test

CLI 出力契約:
  stdout: JSON {"valid": bool, "mode": "route:<id>"|"complete"|"self-test", "findings": [str, ...]}
  exit:   0=PASS, 1=FAIL, 2=usage/parse error
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "route-build-report.schema.json"
REPORT_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_PROPERTIES = REPORT_SCHEMA["properties"]
SCHEMA_VERSION = SCHEMA_PROPERTIES["schema_version"]["const"]
COMPONENT_KINDS = set(SCHEMA_PROPERTIES["component_kind"]["enum"])
BUILDERS = set(SCHEMA_PROPERTIES["builder"]["enum"])
STATUSES = set(SCHEMA_PROPERTIES["status"]["enum"])
REQUIRED_KEYS = tuple(REPORT_SCHEMA["required"])
OPTIONAL_KEYS = tuple(set(SCHEMA_PROPERTIES) - set(REQUIRED_KEYS))
ROUTE_ID_RE = re.compile(SCHEMA_PROPERTIES["route_id"]["pattern"])
SLUG_RE = re.compile(SCHEMA_PROPERTIES["plugin_slug"]["pattern"])
SHA256_RE = re.compile(SCHEMA_PROPERTIES["artifact_sha256"]["pattern"])
GRAPH_HASH_RE = re.compile(SCHEMA_PROPERTIES["graph_hash"]["pattern"])
UTC_TIMESTAMP_RE = re.compile(SCHEMA_PROPERTIES["generated_at"]["pattern"])
TOOL_NAME_RE = re.compile(SCHEMA_PROPERTIES["tool_versions"]["propertyNames"]["pattern"])
_PLANNER_DERIVE_REL = (
    "plugins", "plugin-dev-planner", "skills", "run-plugin-dev-plan", "scripts", "derive-task-graph.py",
)


def report_path(slug: str, route_id: str) -> str:
    """レポートの repo-root 相対パス規約 (flat layout・cycle_id 無しの既定)。"""
    return f"eval-log/{slug}/build/route-{route_id}.json"


def report_rel(reports_dir: Path, route_id: str, repo_root: Path | None = None) -> str:
    """実際の reports_dir から repo-root 相対の期待パスを導出する (inputs_consumed 照合の正)。

    cycle_id 付き handoff は resolve_build_dir が reports_dir を
    eval-log/<slug>/build/<cycle-id>/ へ分離するため、期待パスは flat 規約でなく
    「validator が dep report を実際に読む場所」から導出する (flat 既定では
    report_path と同一 = 後方互換)。flat 規約を固定期待にすると cycle build の
    provenance が別 plan の flat ファイルを指す偽宣言を通してしまう。
    """
    p = Path(reports_dir) / f"route-{route_id}.json"
    base = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        rel = p.resolve().relative_to(base.resolve())
    except ValueError:
        rel = p
    return str(PurePosixPath(rel))


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def _hash_target(path: Path) -> str:
    """file または directory tree の決定論 SHA-256 (接頭辞なし)。"""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    for child in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        relative = child.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        payload = child.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _producer_graph_hash(graph_path: Path, repo_root: Path) -> tuple[str | None, str | None]:
    """producer の read-only CLI から canonical graph hash を取得する。

    canonical serializer を consumer 側に再実装すると field 追加時に silent drift
    するため、derive-task-graph.py --print-graph-hash を唯一の SSOT とする。
    """
    derive_script = repo_root.joinpath(*_PLANNER_DERIVE_REL)
    if not derive_script.is_file():
        return None, f"graph_hash: producer 不在 ({derive_script})"
    try:
        proc = subprocess.run(
            [sys.executable, str(derive_script), "--print-graph-hash", str(graph_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"graph_hash: producer 起動失敗 ({exc})"
    value = proc.stdout.strip()
    if proc.returncode != 0 or not GRAPH_HASH_RE.fullmatch(value):
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}"
        return None, f"graph_hash: producer 算出失敗 ({detail})"
    return value, None


def _parse_utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not UTC_TIMESTAMP_RE.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return None


def validate_report_shape(report: object) -> list[str]:
    """schema (route-build-report.schema.json) 相当の形状検査。findings を返す。"""
    if not isinstance(report, dict):
        return ["report: JSON object でない"]
    findings: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in report:
            findings.append(f"report: 必須キー {key} 欠落")
    unknown = set(report) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
    if unknown:
        findings.append(f"report: 未知キー {sorted(unknown)} (additionalProperties=false)")
    if report.get("schema_version") != SCHEMA_VERSION:
        findings.append(f"schema_version: {SCHEMA_VERSION} でない")
    slug = report.get("plugin_slug")
    if not (isinstance(slug, str) and SLUG_RE.match(slug)):
        findings.append("plugin_slug: ^[a-z][a-z0-9-]*$ に不一致")
    rid = report.get("route_id")
    if not (isinstance(rid, str) and ROUTE_ID_RE.match(rid)):
        findings.append("route_id: ^C[0-9]+$ に不一致")
    if report.get("component_kind") not in COMPONENT_KINDS:
        findings.append(f"component_kind: enum 外 ({report.get('component_kind')!r})")
    if not (isinstance(report.get("name"), str) and report.get("name")):
        findings.append("name: 非空文字列でない")
    if report.get("builder") not in BUILDERS:
        findings.append(f"builder: enum 外 ({report.get('builder')!r})")
    if not (isinstance(report.get("build_target"), str) and report.get("build_target")):
        findings.append("build_target: 非空文字列でない")
    status = report.get("status")
    if status not in STATUSES:
        findings.append(f"status: enum 外 ({status!r})")
    if not (isinstance(report.get("summary"), str) and report.get("summary")):
        findings.append("summary: 非空文字列でない")
    for key in ("deviations", "evidence", "inputs_consumed"):
        if key in report and not _is_str_list(report[key]):
            findings.append(f"{key}: 非空文字列の配列でない")
    if "covered_task_ids" in report and not _is_str_list(report["covered_task_ids"]):
        findings.append("covered_task_ids: 非空文字列の配列でない")
    if "artifact_sha256" in report and not (
        isinstance(report["artifact_sha256"], str) and SHA256_RE.fullmatch(report["artifact_sha256"])
    ):
        findings.append("artifact_sha256: lowercase 64-hex でない")
    if "graph_hash" in report and not (
        isinstance(report["graph_hash"], str) and GRAPH_HASH_RE.fullmatch(report["graph_hash"])
    ):
        findings.append("graph_hash: sha256:<lowercase 64-hex> でない")
    if "generated_at" in report and _parse_utc_timestamp(report["generated_at"]) is None:
        findings.append("generated_at: UTC RFC 3339 (YYYY-MM-DDTHH:MM:SS[.fff]Z) でない")
    if "tool_versions" in report:
        versions = report["tool_versions"]
        if not isinstance(versions, dict) or not versions:
            findings.append("tool_versions: 非空 object でない")
        else:
            for tool, version in versions.items():
                if not isinstance(tool, str) or not TOOL_NAME_RE.fullmatch(tool):
                    findings.append(f"tool_versions: tool 名が不正 ({tool!r})")
                if not isinstance(version, str) or not version.strip():
                    findings.append(f"tool_versions[{tool!r}]: version が非空文字列でない")
    if "test_evidence" in report:
        test_evidence = report["test_evidence"]
        if not isinstance(test_evidence, list):
            findings.append("test_evidence: 配列でない")
        else:
            item_schema = SCHEMA_PROPERTIES["test_evidence"]["items"]
            item_required = set(item_schema["required"])
            item_allowed = set(item_schema["properties"])
            for i, evidence in enumerate(test_evidence):
                if not isinstance(evidence, dict):
                    findings.append(f"test_evidence[{i}]: object でない")
                    continue
                missing = item_required - set(evidence)
                if missing:
                    findings.append(f"test_evidence[{i}]: 必須キー {sorted(missing)} 欠落")
                unknown_evidence = set(evidence) - item_allowed
                if unknown_evidence:
                    findings.append(
                        f"test_evidence[{i}]: 未知キー {sorted(unknown_evidence)} "
                        "(additionalProperties=false)"
                    )
                command = evidence.get("command")
                exit_code = evidence.get("exit_code")
                passed = evidence.get("passed")
                failed = evidence.get("failed")
                if not isinstance(command, str) or not command.strip():
                    findings.append(f"test_evidence[{i}].command: 非空文字列でない")
                if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code < 0:
                    findings.append(f"test_evidence[{i}].exit_code: 0 以上の整数でない")
                for field, value in (("passed", passed), ("failed", failed)):
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        findings.append(f"test_evidence[{i}].{field}: 0 以上の整数でない")
                if status == "success" and (exit_code != 0 or failed != 0):
                    findings.append(
                        f"test_evidence[{i}]: status=success なのに exit_code={exit_code!r}, failed={failed!r}"
                    )
                artifact_path = evidence.get("artifact")
                artifact_hash = evidence.get("artifact_sha256")
                if (artifact_path is None) != (artifact_hash is None):
                    findings.append(
                        f"test_evidence[{i}]: artifact/artifact_sha256 はペアで指定する"
                    )
                if artifact_path is not None and (
                    not isinstance(artifact_path, str) or not artifact_path.strip()
                ):
                    findings.append(f"test_evidence[{i}].artifact: 非空文字列でない")
                if artifact_hash is not None and (
                    not isinstance(artifact_hash, str) or not SHA256_RE.fullmatch(artifact_hash)
                ):
                    findings.append(f"test_evidence[{i}].artifact_sha256: lowercase 64-hex でない")
                started = evidence.get("started_at")
                completed = evidence.get("completed_at")
                if (started is None) != (completed is None):
                    findings.append(f"test_evidence[{i}]: started_at/completed_at はペアで指定する")
                started_at = _parse_utc_timestamp(started) if started is not None else None
                completed_at = _parse_utc_timestamp(completed) if completed is not None else None
                if started is not None and started_at is None:
                    findings.append(f"test_evidence[{i}].started_at: UTC RFC 3339 でない")
                if completed is not None and completed_at is None:
                    findings.append(f"test_evidence[{i}].completed_at: UTC RFC 3339 でない")
                if started_at is not None and completed_at is not None and started_at > completed_at:
                    findings.append(f"test_evidence[{i}]: started_at が completed_at より後")
    if "discovered" in report and not _is_str_list(report["discovered"]):
        findings.append("discovered: 非空文字列の配列でない")
    if "corrections" in report:
        corr = report["corrections"]
        if not isinstance(corr, list):
            findings.append("corrections: 配列でない")
        else:
            for i, c in enumerate(corr):
                if not (isinstance(c, dict) and all(
                        isinstance(c.get(k), str) and c.get(k)
                        for k in ("target", "correction", "corrected_by"))):
                    findings.append(
                        f"corrections[{i}]: {{target, correction, corrected_by}} の非空文字列が必須")
    if "handover" in report and not (report["handover"] is None or isinstance(report["handover"], str)):
        findings.append("handover: string か null でない")
    # cross-field
    if status == "skipped" and not (isinstance(report.get("skip_reason"), str) and report.get("skip_reason")):
        findings.append("skip_reason: status=skipped なのに非空 skip_reason が無い")
    if status != "skipped" and "skip_reason" in report:
        findings.append("skip_reason: status=skipped 以外では書かない")
    if status == "success" and _is_str_list(report.get("evidence")) and not report["evidence"]:
        findings.append("evidence: status=success は 1 件以上必須")
    return findings


def validate_discovered_consistency(report: object) -> list[str]:
    """deviations 本文の discovered 言及と discovered[] の突合 (残差の監査経路実証・fail-closed)。

    deviations[n] が discovered 報告へ言及しているのに discovered[] (emit 済 form パス列) が
    空/不在なら、残差が inbox 監査経路 (emit-discovered-task → TG-C08 completion gate) に
    実際は乗っていない偽宣言として fail する。corrections[] が当該 deviations[n] を target に
    追記型訂正済みの場合は除外する (原文改竄せず訂正を監査可能に残す経路)。
    """
    if not isinstance(report, dict):
        return []
    findings: list[str] = []
    deviations = report.get("deviations")
    if not _is_str_list(deviations):
        return findings
    discovered = report.get("discovered")
    has_discovered = _is_str_list(discovered) and bool(discovered)
    corrections = report.get("corrections") if isinstance(report.get("corrections"), list) else []
    corrected_targets = {c.get("target") for c in corrections if isinstance(c, dict)}
    for i, dev in enumerate(deviations):
        if "discovered" not in dev:
            continue
        if has_discovered or f"deviations[{i}]" in corrected_targets:
            continue
        findings.append(
            f"deviations[{i}]: discovered 言及があるのに discovered[] が空/不在 "
            "(emit 済 form パスを discovered[] へ列挙するか corrections で追記型訂正すること)")
    return findings


def _repo_root_from_handoff_path(path: Path) -> Path:
    resolved = path.resolve()
    if "plugin-plans" in resolved.parts:
        idx = resolved.parts.index("plugin-plans")
        return Path(*resolved.parts[:idx]) if idx else Path("/")
    return Path.cwd()


def validate_against_route(report: dict, route: dict, slug: str, repo_root: Path | None = None) -> list[str]:
    """レポートと handoff route の同値性 (route が SSOT・レポートは写し)。"""
    findings: list[str] = []
    if report.get("plugin_slug") != slug:
        findings.append(f"plugin_slug: handoff target_plugin_slug ({slug}) と不一致")
    for key in ("component_kind", "name", "builder", "build_target"):
        if report.get(key) != route.get(key):
            findings.append(f"{key}: handoff route と不一致 (report={report.get(key)!r} route={route.get(key)!r})")
    if repo_root is not None and report.get("status") == "success":
        target = repo_root / str(report.get("build_target", ""))
        if not target.exists():
            findings.append(f"build_target: success report だが現物が存在しない ({report.get('build_target')})")
    return findings


def validate_current_handoff_evidence(
    report: dict,
    route: dict,
    handoff: dict,
    plan_dir: Path | None,
    repo_root: Path | None,
) -> list[str]:
    """task_graph_ref を持つ current handoff の structured freshness を fail-closed 検査。"""
    if not isinstance(handoff.get("task_graph_ref"), dict):
        return []  # task-graph の無い legacy handoff は後方互換。
    findings: list[str] = []
    if report.get("status") != "success":
        return findings
    if plan_dir is None or repo_root is None:
        return ["current handoff: plan_dir/repo_root が無く structured evidence を検証できない"]

    target_raw = report.get("build_target")
    target = (repo_root / target_raw).resolve() if isinstance(target_raw, str) else None
    if target is None:
        findings.append("artifact_sha256: build_target を解決できない")
    else:
        try:
            target.relative_to(repo_root.resolve())
        except ValueError:
            findings.append(f"build_target: repo root 外へ path escape ({target_raw!r})")
        else:
            expected_artifact = report.get("artifact_sha256")
            if not isinstance(expected_artifact, str):
                findings.append("artifact_sha256: current handoff の success report に必須")
            elif target.exists():
                actual_artifact = _hash_target(target)
                if expected_artifact != actual_artifact:
                    findings.append(
                        f"artifact_sha256: current target hash と不一致 "
                        f"(report={expected_artifact!r} actual={actual_artifact!r})"
                    )

    graph_ref = handoff["task_graph_ref"]
    graph_rel = graph_ref.get("path")
    graph_path: Path | None = None
    if isinstance(graph_rel, str) and graph_rel and not Path(graph_rel).is_absolute():
        candidate = (plan_dir / graph_rel).resolve()
        try:
            candidate.relative_to(plan_dir.resolve())
        except ValueError:
            pass
        else:
            graph_path = candidate
    if graph_path is None:
        findings.append(f"task_graph_ref.path: plan dir 内相対 path でない ({graph_rel!r})")
        return findings
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        findings.append(f"task_graph_ref: 読込/parse 不能 ({exc})")
        return findings
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        findings.append("task_graph_ref: graph object/nodes[] が不正")
        return findings

    actual_graph_hash, graph_hash_error = _producer_graph_hash(graph_path, repo_root)
    if graph_hash_error:
        findings.append(graph_hash_error)
    expected_graph_hash = report.get("graph_hash")
    if not isinstance(expected_graph_hash, str):
        findings.append("graph_hash: current handoff の success report に必須")
    elif actual_graph_hash is not None and expected_graph_hash != actual_graph_hash:
        findings.append(
            f"graph_hash: current task graph と不一致 "
            f"(report={expected_graph_hash!r} actual={actual_graph_hash!r})"
        )

    covered = report.get("covered_task_ids")
    if not _is_str_list(covered) or not covered:
        findings.append("covered_task_ids: current handoff の success report に非空配列が必須")
    else:
        if len(covered) != len(set(covered)):
            findings.append("covered_task_ids: 重複 task id がある")
        nodes_by_id = {
            node.get("id"): node
            for node in graph["nodes"]
            if isinstance(node, dict) and isinstance(node.get("id"), str)
        }
        for task_id in covered:
            node = nodes_by_id.get(task_id)
            if node is None:
                findings.append(f"covered_task_ids: task graph に存在しない id {task_id!r}")
            elif node.get("entity_ref") != route.get("id"):
                findings.append(
                    f"covered_task_ids: {task_id!r} entity_ref={node.get('entity_ref')!r} が "
                    f"route={route.get('id')!r} と不一致"
                )

    test_evidence = report.get("test_evidence")
    if not isinstance(test_evidence, list) or not test_evidence:
        findings.append("test_evidence: current handoff の success report に構造化 test 証跡が必須")
    else:
        generated_at = _parse_utc_timestamp(report.get("generated_at"))
        for i, evidence in enumerate(test_evidence):
            if not isinstance(evidence, dict):
                continue
            started_at = _parse_utc_timestamp(evidence.get("started_at"))
            completed_at = _parse_utc_timestamp(evidence.get("completed_at"))
            if started_at is None or completed_at is None:
                findings.append(
                    f"test_evidence[{i}]: current handoff では started_at/completed_at が必須"
                )
            elif generated_at is not None and completed_at > generated_at:
                findings.append(f"test_evidence[{i}]: completed_at が report.generated_at より後")

            artifact_rel = evidence.get("artifact")
            artifact_hash = evidence.get("artifact_sha256")
            if artifact_rel is None and artifact_hash is None:
                continue
            if not isinstance(artifact_rel, str) or not artifact_rel or Path(artifact_rel).is_absolute():
                findings.append(f"test_evidence[{i}].artifact: repo-root 相対 path でない")
                continue
            artifact = (repo_root / artifact_rel).resolve()
            try:
                artifact.relative_to(repo_root.resolve())
            except ValueError:
                findings.append(f"test_evidence[{i}].artifact: repo root 外へ path escape")
                continue
            if not artifact.exists():
                findings.append(f"test_evidence[{i}].artifact: 実体が存在しない ({artifact_rel})")
                continue
            if isinstance(artifact_hash, str) and SHA256_RE.fullmatch(artifact_hash):
                actual_artifact_hash = _hash_target(artifact)
                if artifact_hash != actual_artifact_hash:
                    findings.append(
                        f"test_evidence[{i}].artifact_sha256: current artifact hash と不一致 "
                        f"(report={artifact_hash!r} actual={actual_artifact_hash!r})"
                    )

    if _parse_utc_timestamp(report.get("generated_at")) is None:
        findings.append("generated_at: current handoff の success report に UTC RFC 3339 時刻が必須")
    versions = report.get("tool_versions")
    if not isinstance(versions, dict) or not versions:
        findings.append("tool_versions: current handoff の success report に非空 map が必須")
    return findings


def _load_report(reports_dir: Path, slug: str, route_id: str) -> tuple[dict | None, list[str]]:
    path = reports_dir / f"route-{route_id}.json"
    if not path.is_file():
        return None, [f"route {route_id}: レポート未作成 ({report_path(slug, route_id)})"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"route {route_id}: レポートが JSON として読めない ({exc})"]
    if not isinstance(data, dict):
        return None, [f"route {route_id}: レポートが JSON object でない"]
    return data, []


def validate_dependency_chain(
    report: dict, route: dict, reports_dir: Path, slug: str, repo_root: Path | None = None
) -> list[str]:
    """依存 route のレポート実在/非 failure と inputs_consumed 被覆 (fail-closed の本体)。"""
    findings: list[str] = []
    consumed = {str(PurePosixPath(p)) for p in report.get("inputs_consumed", []) if isinstance(p, str)}
    for dep_id in route.get("depends_on", []) or []:
        dep_report, errs = _load_report(reports_dir, slug, dep_id)
        if errs:
            findings.extend(f"依存 {e}" for e in errs)
            continue
        dep_status = dep_report.get("status")
        if dep_status not in STATUSES:
            findings.append(f"依存 route {dep_id}: status 不正 ({dep_status!r})")
        elif dep_status != "success":
            findings.append(f"依存 route {dep_id}: status={dep_status} のまま後続を build している")
        expected = report_rel(reports_dir, dep_id, repo_root)
        if expected not in consumed:
            findings.append(f"inputs_consumed: 依存レポート {expected} の読取宣言が無い")
    return findings


_FAILED_EVIDENCE_RE = re.compile(r"[1-9][0-9]*\s+failed")


def report_warnings(report: object) -> list[str]:
    """valid/exit に影響しない助言 WARN (既知赤の無音通過を機械層で顕在化する・S-04)。

    status=success かつ evidence のいずれかに `N failed` (N>=1) を含み deviations が空のとき、
    「責務外失敗を deviations へ記録する規約」の未遵守を WARN する。failure を success へ
    変換する際に deviation 追跡にも乗せない normalization-of-deviance (既知赤の基準線低下) を
    検出するが、valid 判定は変えない (助言のみ・fail-closed ではない)。
    """
    if not isinstance(report, dict):
        return []
    warnings: list[str] = []
    if report.get("status") == "success":
        evidence = report.get("evidence")
        deviations = report.get("deviations")
        has_failed = _is_str_list(evidence) and any(_FAILED_EVIDENCE_RE.search(e) for e in evidence)
        deviations_empty = isinstance(deviations, list) and not deviations
        if has_failed and deviations_empty:
            warnings.append(
                "evidence に失敗記録 (N failed) があるのに deviations が空: "
                "責務外失敗は deviations へ記録する規約 (既知赤の無音通過防止)"
            )
    return warnings


def validate_route(
    handoff: dict,
    reports_dir: Path,
    route_id: str,
    repo_root: Path | None = None,
    plan_dir: Path | None = None,
) -> list[str]:
    slug = handoff.get("target_plugin_slug", "")
    routes = {r.get("id"): r for r in handoff.get("routes", []) if isinstance(r, dict)}
    route = routes.get(route_id)
    if route is None:
        return [f"route {route_id}: handoff routes に存在しない"]
    report, errs = _load_report(reports_dir, slug, route_id)
    if errs:
        return errs
    findings = validate_report_shape(report)
    if report.get("route_id") not in (None, route_id):
        findings.append(f"route_id: ファイル名 route-{route_id}.json と不一致 ({report.get('route_id')!r})")
    findings.extend(validate_discovered_consistency(report))
    findings.extend(validate_against_route(report, route, slug, repo_root))
    findings.extend(validate_current_handoff_evidence(report, route, handoff, plan_dir, repo_root))
    findings.extend(validate_dependency_chain(report, route, reports_dir, slug, repo_root))
    return findings


def validate_complete(
    handoff: dict,
    reports_dir: Path,
    repo_root: Path | None = None,
    plan_dir: Path | None = None,
) -> list[str]:
    slug = handoff.get("target_plugin_slug", "")
    routes = [r for r in handoff.get("routes", []) if isinstance(r, dict)]
    findings: list[str] = []
    for route in routes:
        rid = route.get("id", "?")
        route_findings = validate_route(handoff, reports_dir, rid, repo_root, plan_dir)
        findings.extend(f"route {rid}: {finding}" for finding in route_findings)
        if not route_findings:
            report, _ = _load_report(reports_dir, slug, rid)
            if report and report.get("status") != "success":
                findings.append(
                    f"route {rid}: status={report.get('status')} が残っている "
                    "(--complete は全 route success のみ完了)"
                )
    known_ids = {r.get("id") for r in routes}
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("route-*.json")):
            rid = path.stem.removeprefix("route-")
            if rid not in known_ids:
                findings.append(f"orphan レポート: {path.name} は handoff routes に無い route (計画 drift)")
    return findings


def _load_handoff(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, f"handoff が見つからない: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"handoff が JSON として読めない: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
        return None, "handoff に routes 配列が無い"
    slug = data.get("target_plugin_slug")
    if not (isinstance(slug, str) and SLUG_RE.match(slug)):
        return None, "handoff の target_plugin_slug が不正"
    return data, None


def _emit(valid: bool, mode: str, findings: list[str], warnings: list[str] | None = None) -> int:
    out: dict = {"valid": valid, "mode": mode, "findings": findings}
    if warnings:  # 非空時のみ additive に載せる (既存 stdout 契約 {valid,mode,findings} は後方互換)
        out["warnings"] = warnings
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if valid else 1


def _self_test() -> int:
    import tempfile

    findings: list[str] = []

    def check(label: str, cond: bool) -> None:
        if not cond:
            findings.append(f"self-test: {label}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        slug = "demo-plugin"
        handoff = {
            "target_plugin_slug": slug,
            "routes": [
                {"id": "C1", "component_kind": "script", "name": "lint-a", "depends_on": [],
                 "builder": "plugin-scaffold", "build_target": f"plugins/{slug}/scripts/lint-a.py"},
                {"id": "C2", "component_kind": "skill", "name": "run-b", "depends_on": ["C1"],
                 "builder": "run-skill-create", "build_target": f"plugins/{slug}/skills/run-b/"},
            ],
        }
        reports_dir = root / "eval-log" / slug / "build"
        reports_dir.mkdir(parents=True)

        def base_report(rid: str, route: dict, **over: object) -> dict:
            rep = {
                "schema_version": SCHEMA_VERSION, "plugin_slug": slug, "route_id": rid,
                "component_kind": route["component_kind"], "name": route["name"],
                "builder": route["builder"], "build_target": route["build_target"],
                "status": "success", "summary": "build 完了。lint exit0 を確認。",
                "deviations": [], "evidence": ["lint exit0"],
                "inputs_consumed": [], "handover": None,
            }
            rep.update(over)
            return rep

        r1, r2 = handoff["routes"]
        (root / r1["build_target"]).parent.mkdir(parents=True, exist_ok=True)
        (root / r1["build_target"]).write_text("# lint-a\n", encoding="utf-8")
        (root / r2["build_target"]).mkdir(parents=True, exist_ok=True)
        # (1) 依存レポート欠落: C2 は C1 レポートが無いと FAIL
        (reports_dir / "route-C2.json").write_text(json.dumps(
            base_report("C2", r2, inputs_consumed=[report_path(slug, "C1")])), encoding="utf-8")
        check("C1 欠落で C2 が FAIL", validate_route(handoff, reports_dir, "C2", root))
        # (2) チェーン充足で PASS
        (reports_dir / "route-C1.json").write_text(json.dumps(
            base_report("C1", r1, handover="run-b は lint-a の exit code 契約に依存")), encoding="utf-8")
        check("C1 単体 PASS", not validate_route(handoff, reports_dir, "C1", root))
        check("チェーン充足で C2 PASS", not validate_route(handoff, reports_dir, "C2", root))
        # (3) inputs_consumed 未宣言は FAIL
        (reports_dir / "route-C2.json").write_text(json.dumps(
            base_report("C2", r2, inputs_consumed=[])), encoding="utf-8")
        check("読取宣言なしで C2 FAIL",
              any("inputs_consumed" in f for f in validate_route(handoff, reports_dir, "C2", root)))
        (reports_dir / "route-C2.json").write_text(json.dumps(
            base_report("C2", r2, inputs_consumed=[report_path(slug, "C1")])), encoding="utf-8")
        # (4) success なのに evidence 空は FAIL
        bad = base_report("C1", r1, evidence=[])
        check("success+evidence 空 FAIL", any("evidence" in f for f in validate_report_shape(bad)))
        # (5) skipped は skip_reason 必須
        bad = base_report("C1", r1, status="skipped")
        check("skipped+skip_reason 無し FAIL", any("skip_reason" in f for f in validate_report_shape(bad)))
        ok = base_report("C1", r1, status="skipped", skip_reason="既存実体を維持", evidence=[])
        check("skipped+reason PASS", not validate_report_shape(ok))
        # (6) handoff との不一致は FAIL
        drift = base_report("C1", r1, build_target="plugins/other/x.py")
        check("build_target drift FAIL", validate_against_route(drift, r1, slug))
        missing_target = base_report("C1", r1)
        (root / r1["build_target"]).unlink()
        check("success target missing FAIL",
              any("現物が存在しない" in f for f in validate_against_route(missing_target, r1, slug, root)))
        (root / r1["build_target"]).write_text("# lint-a\n", encoding="utf-8")
        # (7) 依存 failure / skipped で後続 FAIL
        (reports_dir / "route-C1.json").write_text(json.dumps(
            base_report("C1", r1, status="failure")), encoding="utf-8")
        check("依存 failure で C2 FAIL",
              any("failure" in f for f in validate_route(handoff, reports_dir, "C2", root)))
        (reports_dir / "route-C1.json").write_text(json.dumps(
            base_report("C1", r1, status="skipped", skip_reason="domain implementation pending", evidence=[])), encoding="utf-8")
        check("依存 skipped で C2 FAIL",
              any("status=skipped" in f for f in validate_route(handoff, reports_dir, "C2", root)))
        (reports_dir / "route-C1.json").write_text(json.dumps(base_report("C1", r1)), encoding="utf-8")
        # (8) complete: 全 route 緑で PASS / orphan で FAIL
        check("complete PASS", not validate_complete(handoff, reports_dir, root))
        (reports_dir / "route-C9.json").write_text(json.dumps(base_report("C9", r1)), encoding="utf-8")
        check("orphan で complete FAIL",
              any("orphan" in f for f in validate_complete(handoff, reports_dir, root)))
        (reports_dir / "route-C9.json").unlink()
        # (9) deviations の discovered 言及 × discovered[]/corrections 突合 (残差の監査経路実証)
        mention = base_report("C1", r1, deviations=["残差は discovered へ構造化報告した"])
        check("discovered 言及+空で FAIL",
              any("discovered 言及" in f for f in validate_discovered_consistency(mention)))
        (reports_dir / "route-C1.json").write_text(json.dumps(mention), encoding="utf-8")
        check("discovered 言及+空は validate_route でも FAIL",
              any("discovered 言及" in f for f in validate_route(handoff, reports_dir, "C1", root)))
        with_form = base_report("C1", r1, deviations=["残差は discovered へ構造化報告した"],
                                discovered=[f"eval-log/{slug}/build/discovered-tasks/x.json"])
        check("discovered[] 実証で PASS", not validate_discovered_consistency(with_form))
        check("discovered[] 実証は shape も PASS", not validate_report_shape(with_form))
        corrected = base_report("C1", r1, deviations=["残差は discovered へ構造化報告した"],
                                corrections=[{"target": "deviations[0]",
                                              "correction": "discovered 非経由・deviations 開示のみ",
                                              "corrected_by": "self-test"}])
        check("corrections 訂正済で除外 PASS", not validate_discovered_consistency(corrected))
        check("corrections は shape PASS", not validate_report_shape(corrected))
        bad_corr = base_report("C1", r1, corrections=[{"target": "deviations[0]"}])
        check("corrections 形状不正 FAIL",
              any("corrections[0]" in f for f in validate_report_shape(bad_corr)))
        bad_disc = base_report("C1", r1, discovered=[""])
        check("discovered 形状不正 FAIL",
              any("discovered" in f for f in validate_report_shape(bad_disc)))
        (reports_dir / "route-C1.json").write_text(json.dumps(base_report("C1", r1)), encoding="utf-8")

    return _emit(not findings, "self-test", findings)


def main(argv: list[str]) -> int:
    args = list(argv)
    if "--self-test" in args:
        return _self_test()

    def _opt(name: str) -> str | None:
        if name in args:
            i = args.index(name)
            if i + 1 >= len(args):
                return None
            return args[i + 1]
        return None

    handoff_arg = _opt("--handoff")
    route_id = _opt("--route")
    complete = "--complete" in args
    if not handoff_arg or (route_id is None) == (not complete):
        print(json.dumps({"valid": False, "mode": "usage", "findings": [
            "usage: validate-route-build-reports.py --handoff <handoff.json> (--route <id> | --complete) [--reports-dir DIR]",
        ]}, ensure_ascii=False))
        return 2
    handoff_path = Path(handoff_arg)
    handoff, err = _load_handoff(handoff_path)
    if err:
        print(json.dumps({"valid": False, "mode": "usage", "findings": [err]}, ensure_ascii=False))
        return 2
    reports_dir_arg = _opt("--reports-dir")
    reports_dir = Path(reports_dir_arg) if reports_dir_arg else Path(
        report_path(handoff["target_plugin_slug"], "C0")).parent
    repo_root = _repo_root_from_handoff_path(handoff_path)
    plan_dir = handoff_path.resolve().parent
    slug = handoff["target_plugin_slug"]
    if route_id is not None:
        findings = validate_route(handoff, reports_dir, route_id, repo_root, plan_dir)
        report, _ = _load_report(reports_dir, slug, route_id)
        return _emit(not findings, f"route:{route_id}", findings, report_warnings(report))
    findings = validate_complete(handoff, reports_dir, repo_root, plan_dir)
    warnings: list[str] = []
    for route in handoff.get("routes", []):
        if isinstance(route, dict):
            report, _ = _load_report(reports_dir, slug, route.get("id", "?"))
            warnings.extend(report_warnings(report))
    return _emit(not findings, "complete", findings, warnings)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
