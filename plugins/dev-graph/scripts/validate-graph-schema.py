#!/usr/bin/env python3
# /// script
# name: validate-graph-schema
# purpose: Perform side-effect-free fail-closed validation of canonical dev-graph nodes, artifacts, and feature packages.
# inputs: ["argv: --graph FILE|- --repo-root PATH? --require-canonical-envelope? --strict-artifact-readiness?", "stdin: preview graph JSON when --graph -"]
# outputs: ["stdout: JSON validation report (graph_validation = graph 全体, node_readiness = node 単位, artifact_readiness = 本文の heading_missing/placeholder_only_section)"]
# requires-python = ">=3.10"
# dependencies: ["../lib/graph_envelope.py", "../lib/graph_artifact_readiness.py"]
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

# 共有 harness は読取り専用。plugin の module を import する前に止め、bytecode cache (__pycache__) を
# harness に書かない (子の起動にも -B を渡す)。
sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from _common import ContractError, contained, dump, load_json

# lib を毎回 exec し直す。test が本 script と ``_common`` を別インスタンスとして読み直したとき、キャッシュ済み
# lib の ContractError だけが旧世代のクラスに残り、呼出側の ``except ContractError`` が取り逃がす。
sys.modules.pop("graph_artifact_readiness", None)
from graph_artifact_readiness import missing_required_headings, placeholder_sections
from graph_envelope import envelope_violations

CANONICAL_STORE_RELATIVE = PurePosixPath(".dev-graph/state/graph.json")
SCHEMA_PATH = PLUGIN_ROOT / "schemas" / "graph-node.schema.json"
TEMPLATE_CONTRACT_PATH = PLUGIN_ROOT / "templates" / "template-contract.json"
PHASES = {f"P{i:02d}" for i in range(1, 14)}
ROOT_BY_KIND = {
    "issue": "issues",
    "task": "tasks",
    "specification": "specs",
    "architecture": "architecture",
    "feature": "features",
    "document": "docs",
}
# heading_missing を見る kind。task は conditional_required_sections (system_development 系統) を
# node の lineage で選ぶので世代差を誤検出しない。issue は「概要」見出しを省く慣習と契約が
# 食い違うだけの誤検出源なので対象外。placeholder_only_section は全 kind を見る。
HEADING_MISSING_KINDS = {"architecture", "specification", "task"}
READINESS_CODES = {"heading_missing", "placeholder_only_section"}


def nodes_of(data: Any) -> list[dict[str, Any]]:
    values = data.get("nodes") if isinstance(data, dict) else data
    if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
        raise ContractError("graph must be an array or an object with nodes[]")
    return values


def envelope_findings(document: Any) -> list[dict[str, str]]:
    """canonical store の外枠を検査し、C11 の finding 形式へ写す。

    ``nodes_of()`` は nodes[] を取り出した時点で外枠を捨てるため、C11 は長く「store が
    canonical writer の書いた形か」を見ていなかった。C10 PreToolUse は書込みを別 script
    file へ移した間接起動を原理的に遮断できないので、遮断が閉じない範囲は store 側の
    検査で拾う必要がある。未知 key の混入・schema_version の書換・graph_revision の
    型崩れは、いずれも正規 writer が作らない形であり迂回書込みの直接の痕跡になる。

    検査対象は canonical store を読んだ経路に限る。``--graph -`` の preview や部分 graph は
    そもそも外枠を持たない正当な入力であり、ここで落とすと dry-run 検証が壊れる。
    """
    return [
        {"node": "$graph", "code": "envelope_violation", "detail": detail}
        for detail in envelope_violations(document)
    ]


def _is_type(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(expected, True)


def _format_ok(value: str, expected: str) -> bool:
    try:
        if expected == "date":
            date.fromisoformat(value)
        elif expected == "date-time":
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif expected == "uri":
            return bool(urlsplit(value).scheme)
    except ValueError:
        return False
    return True


def _schema_fallback(value: Any, schema: Any, root: dict[str, Any], path: str = "$") -> list[tuple[str, str]]:
    """Deterministic Draft 2020-12 subset used if jsonschema is unavailable."""
    if schema is True:
        return []
    if schema is False or not isinstance(schema, dict):
        return [(path, "value is forbidden" if schema is False else "invalid schema object")]
    findings: list[tuple[str, str]] = []
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if not reference.startswith("#/"):
            return [(path, f"external schema reference is forbidden: {reference}")]
        target: Any = root
        try:
            for part in reference[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            return [(path, f"unresolved schema reference: {reference}")]
        findings.extend(_schema_fallback(value, target, root, path))
    for child in schema.get("allOf", []):
        findings.extend(_schema_fallback(value, child, root, path))
    if "if" in schema and not _schema_fallback(value, schema["if"], root, path) and "then" in schema:
        findings.extend(_schema_fallback(value, schema["then"], root, path))
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, choice) for choice in choices):
            return findings + [(path, f"expected type {choices}, got {type(value).__name__}")]
    if "const" in schema and value != schema["const"]:
        findings.append((path, f"expected const {schema['const']!r}"))
    if "enum" in schema and value not in schema["enum"]:
        findings.append((path, f"not in enum {schema['enum']!r}"))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            findings.append((path, "string is shorter than minLength"))
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            findings.append((path, f"does not match {schema['pattern']}"))
        if "format" in schema and not _format_ok(value, schema["format"]):
            findings.append((path, f"invalid {schema['format']} format"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            findings.append((path, "below minimum"))
        if "maximum" in schema and value > schema["maximum"]:
            findings.append((path, "above maximum"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            findings.append((path, "too few items"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            findings.append((path, "too many items"))
        if schema.get("uniqueItems"):
            packed = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(packed) != len(set(packed)):
                findings.append((path, "items are not unique"))
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                findings.extend(_schema_fallback(item, items, root, f"{path}[{index}]"))
        if "contains" in schema and not any(not _schema_fallback(item, schema["contains"], root, path) for item in value):
            findings.append((path, "contains constraint is not satisfied"))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                findings.append((path, f"missing required property {key}"))
        properties = schema.get("properties", {})
        for key, child in properties.items():
            if key in value:
                findings.extend(_schema_fallback(value[key], child, root, f"{path}.{key}"))
        additional = schema.get("additionalProperties", True)
        unknown = sorted(set(value) - set(properties))
        if additional is False and unknown:
            findings.append((path, f"unknown properties {unknown}"))
        elif isinstance(additional, dict):
            for key in unknown:
                findings.extend(_schema_fallback(value[key], additional, root, f"{path}.{key}"))
    return findings


def schema_findings(node: dict[str, Any], schema: dict[str, Any], index: int) -> list[dict[str, str]]:
    node_id = str(node.get("graph_node_id") or node.get("id") or f"nodes[{index}]")
    try:
        from jsonschema import Draft202012Validator, FormatChecker  # type: ignore
    except ImportError:
        raw = _schema_fallback(node, schema, schema)
    else:
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            raise ContractError(f"invalid canonical graph schema {SCHEMA_PATH}: {exc}") from exc
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(
            validator.iter_errors(node),
            key=lambda err: (tuple(str(part) for part in err.absolute_path), err.message),
        )
        raw = [
            ("$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path), error.message)
            for error in errors
        ]
    return [
        {"node": node_id, "code": "schema_violation", "detail": f"{path}: {detail}"}
        for path, detail in raw
    ]


def _scalar(raw: str) -> Any:
    value = raw.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
            return value[1:-1]
        return value


def frontmatter_of(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContractError(f"cannot read artifact {path}: {exc}") from exc
    if not lines or lines[0].strip() != "---":
        raise ContractError(f"artifact has no YAML frontmatter: {path}")
    result: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", line)
        if match:
            result[match.group(1)] = _scalar(match.group(2) or "")
    raise ContractError(f"artifact frontmatter is not terminated: {path}")


def _repo_root_for(graph: Path, explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve(strict=True)
        contained(graph, root)
        return root
    resolved = graph.resolve(strict=True)
    for parent in resolved.parents:
        if parent.name == ".dev-graph":
            return parent.parent
    raise ContractError("--repo-root is required when --graph is outside the canonical .dev-graph tree")


def _is_canonical_store(graph: Path, repo_root: Path) -> bool:
    """検証対象が repo の canonical store (.dev-graph/state/graph.json) 自身かを返す。"""
    try:
        relative = graph.resolve().relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return False
    return PurePosixPath(relative.as_posix()) == CANONICAL_STORE_RELATIVE


def artifact_findings(
    nodes: list[dict[str, Any]], repo_root: Path | None, template_contract: dict[str, Any],
    allow_missing_artifacts: bool = False,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    required_frontmatter = set((template_contract.get("common_frontmatter") or {}).get("required") or [])
    for index, node in enumerate(nodes):
        node_id = str(node.get("graph_node_id") or node.get("id") or f"nodes[{index}]")
        kind = node.get("artifact_kind", node.get("kind"))
        raw_path = node.get("file_path")
        if kind in ROOT_BY_KIND and isinstance(raw_path, str):
            logical = PurePosixPath(raw_path)
            if logical.is_absolute() or ".." in logical.parts or not logical.parts or logical.parts[0] != ROOT_BY_KIND[kind]:
                findings.append({"node": node_id, "code": "path_parity_error", "detail": f"{kind} must be under {ROOT_BY_KIND[kind]}/"})
                continue
        if repo_root is None or not isinstance(raw_path, str):
            continue
        candidate = repo_root / raw_path
        try:
            # Missing canonical artifacts are readiness gaps, not containment
            # failures.  Resolve without requiring existence, then let the
            # is_file check below classify the missing artifact explicitly.
            artifact = contained(candidate, repo_root, must_exist=False)
        except (ContractError, OSError) as exc:
            findings.append({"node": node_id, "code": "artifact_path_invalid", "detail": str(exc)})
            continue
        if not artifact.is_file():
            if not allow_missing_artifacts:
                findings.append({"node": node_id, "code": "artifact_missing", "detail": raw_path})
            continue
        try:
            frontmatter = frontmatter_of(artifact)
        except ContractError as exc:
            findings.append({"node": node_id, "code": "frontmatter_invalid", "detail": str(exc)})
            continue
        for key in sorted(required_frontmatter - set(frontmatter)):
            findings.append({"node": node_id, "code": "frontmatter_missing", "detail": key})
        for key in ("graph_node_id", "artifact_kind", "file_path", "template_id", "template_version"):
            if key in node and frontmatter.get(key) != node.get(key):
                findings.append({"node": node_id, "code": "frontmatter_parity_error", "detail": key})
    return findings


def readiness_findings(
    nodes: list[dict[str, Any]], repo_root: Path | None, template_contract: dict[str, Any],
) -> list[dict[str, str]]:
    """artifact 本文の readiness (必須見出しの欠落と、template 既定文のままの section) を返す。

    graph の妥当性とは別の判定なので ``validate()`` には混ぜない。C02 は template 既定文の draft を
    受け付けて ``implementation_readiness`` に記録する設計であり、ここを violation にすると
    書込み前検証が draft を拒むようになる。格上げは CLI の ``--strict-artifact-readiness`` だけが行う。
    未配置・読めない artifact は ``artifact_findings`` が報告済みなので、ここでは黙って飛ばす。
    """
    if repo_root is None:
        return []
    findings: list[dict[str, str]] = []
    for index, node in enumerate(nodes):
        node_id = str(node.get("graph_node_id") or node.get("id") or f"nodes[{index}]")
        kind = node.get("artifact_kind", node.get("kind"))
        raw_path = node.get("file_path")
        if not isinstance(kind, str) or not isinstance(raw_path, str):
            continue
        local: list[dict[str, str]] = []
        try:
            artifact = contained(repo_root / raw_path, repo_root, must_exist=False)
            if not artifact.is_file():
                continue
            if kind in HEADING_MISSING_KINDS:
                local += [{"node": node_id, "code": "heading_missing", "detail": section}
                          for section in missing_required_headings(artifact, kind, template_contract, node)]
            local += [{"node": node_id, "code": "placeholder_only_section", "detail": section}
                      for section in placeholder_sections(artifact, kind, template_contract, TEMPLATE_CONTRACT_PATH.parent)]
        except (ContractError, OSError):
            continue
        findings.extend(local)
    return sorted(findings, key=lambda item: (item["node"], item["code"], item["detail"]))


def domain_findings(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        node_id = node.get("graph_node_id") or node.get("id")
        loc = str(node_id or f"nodes[{index}]")
        if not isinstance(node_id, str) or not node_id:
            findings.append({"node": loc, "code": "missing_id", "detail": "graph_node_id required"})
            continue
        ids.append(node_id)
        by_id[node_id] = node
        kind = node.get("artifact_kind", node.get("kind"))
        if kind is not None and kind not in ROOT_BY_KIND:
            findings.append({"node": loc, "code": "invalid_kind", "detail": str(kind)})
        if node.get("status") not in {"draft", "active", "blocked", "done", "closed", "tombstoned"}:
            findings.append({"node": loc, "code": "invalid_status", "detail": str(node.get("status"))})
        dependencies = node.get("depends_on", [])
        if not isinstance(dependencies, list) or any(not isinstance(value, str) for value in dependencies):
            findings.append({"node": loc, "code": "invalid_dependencies", "detail": "depends_on must be string[]"})
        if node.get("tracker_binding") == "beads" and (node.get("github_publication") or {}).get("mode") != "local_only":
            findings.append({"node": loc, "code": "beads_publication", "detail": "beads requires local_only"})
        if node.get("tracker_binding") == "github" and node.get("beads_linkage") is not None:
            findings.append({"node": loc, "code": "binding_collision", "detail": "github cannot have beads_linkage"})
        if node.get("status") == "active":
            readiness = (node.get("implementation_readiness") or {}).get("status")
            if node.get("confirmation_status") != "confirmed" or node.get("evaluation_status") != "pass" or readiness != "complete":
                findings.append({"node": loc, "code": "active_not_ready", "detail": "active requires confirmed/pass/complete"})
        if node.get("tracker_binding") == "repo-config-default":
            findings.append({"node": loc, "code": "unresolved_tracker_binding", "detail": "durable graph cannot retain repo-config-default"})
    for duplicate, count in Counter(ids).items():
        if count > 1:
            findings.append({"node": duplicate, "code": "duplicate_id", "detail": str(count)})
    reference_fields = ("depends_on", "related_nodes", "architecture_refs")
    for index, node in enumerate(nodes):
        node_id = str(node.get("graph_node_id") or node.get("id") or f"nodes[{index}]")
        for field in reference_fields:
            for reference in node.get(field, []) if isinstance(node.get(field, []), list) else []:
                if reference not in by_id:
                    code = "dangling_dependency" if field == "depends_on" else "dangling_reference"
                    findings.append({"node": node_id, "code": code, "detail": f"{field}:{reference}"})
        parent = node.get("parent_feature")
        if isinstance(parent, str) and parent not in by_id:
            findings.append({"node": node_id, "code": "dangling_reference", "detail": f"parent_feature:{parent}"})

    state: dict[str, int] = {}

    def visit(node_id: str) -> None:
        if state.get(node_id) == 1:
            findings.append({"node": node_id, "code": "dependency_cycle", "detail": node_id})
            return
        if state.get(node_id) == 2:
            return
        state[node_id] = 1
        dependencies = by_id[node_id].get("depends_on", [])
        for dependency in dependencies if isinstance(dependencies, list) else []:
            if dependency in by_id:
                visit(dependency)
        state[node_id] = 2

    for node_id in by_id:
        visit(node_id)

    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        if isinstance(node.get("parent_feature"), str):
            children[node["parent_feature"]].append(node)
    order = {phase: int(phase[1:]) for phase in PHASES}
    for feature_id, feature in ((node_id, node) for node_id, node in by_id.items() if node.get("artifact_kind") == "feature"):
        members = children.get(feature_id, [])
        if members or feature.get("status") == "done":
            packages = {member.get("feature_package_id") for member in members}
            phases = [member.get("phase_ref") for member in members]
            if packages == {None} or len(packages) != 1 or set(phases) != PHASES or len(members) != 13:
                findings.append({"node": feature_id, "code": "feature_package_not_exact_13", "detail": f"count={len(members)} phases={sorted(str(value) for value in set(phases))}"})
        for child in members:
            current = order.get(child.get("phase_ref"), 0)
            for dependency in child.get("depends_on", []):
                target = by_id.get(dependency, {})
                if target.get("parent_feature") == feature_id and order.get(target.get("phase_ref"), 0) >= current:
                    findings.append({"node": str(child.get("graph_node_id") or child.get("id") or "?"), "code": "non_forward_phase_dependency", "detail": dependency})
        if feature.get("status") == "done":
            if any(member.get("status") != "done" for member in members):
                findings.append({"node": feature_id, "code": "premature_feature_done", "detail": "all 13 children must be done"})
            for phase in {"P07", "P10", "P11"}:
                child = next((member for member in members if member.get("phase_ref") == phase), {})
                if not (child.get("completion_evidence") or {}).get("evidence_refs"):
                    findings.append({"node": feature_id, "code": "feature_evidence_missing", "detail": phase})
    return findings


def validate(
    nodes: list[dict[str, Any]], schema: dict[str, Any] | None = None,
    *, repo_root: Path | None = None, template_contract: dict[str, Any] | None = None,
    allow_missing_artifacts: bool = False,
) -> list[dict[str, str]]:
    canonical_schema = schema or load_json(SCHEMA_PATH)
    if not isinstance(canonical_schema, dict):
        raise ContractError(f"canonical graph schema must be an object: {SCHEMA_PATH}")
    contract = template_contract or load_json(TEMPLATE_CONTRACT_PATH)
    if not isinstance(contract, dict):
        raise ContractError(f"template contract must be an object: {TEMPLATE_CONTRACT_PATH}")
    findings = [item for index, node in enumerate(nodes) for item in schema_findings(node, canonical_schema, index)]
    findings.extend(domain_findings(nodes))
    findings.extend(artifact_findings(nodes, repo_root, contract, allow_missing_artifacts))
    return sorted(findings, key=lambda item: (item["node"], item["code"], item["detail"]))


def readiness_missing_sections(violations: list[dict[str, str]]) -> list[str]:
    return sorted({
        item["detail"] for item in violations
        if item["code"] in {"frontmatter_missing", "artifact_missing", *READINESS_CODES}
        or (item["code"] == "schema_violation" and "required property" in item["detail"])
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True,
                        help="graph JSON path、または '-' で stdin から preview graph を読む (dry-run 用)")
    parser.add_argument("--repo-root")
    parser.add_argument("--require-canonical-envelope", action="store_true",
                        help="入力が canonical store でなくても envelope を必須にする (監査経路用)")
    parser.add_argument("--strict-artifact-readiness", action="store_true",
                        help="artifact 本文の heading_missing/placeholder_only_section を violation に格上げする "
                             "(既定は artifact_readiness へ報告するだけ)")
    args = parser.parse_args()
    canonical_store = False
    is_stdin = args.graph == "-"
    if is_stdin:
        # dry-run preview 検証: 管理対象 repo へ一時ファイルを書かせないための stdin 経路。
        # --graph FILE は contained(graph, root) を要求するため、preview を検証するには
        # repo 内へ書くしかなく「dry-run write 0」契約と矛盾する。
        if not args.repo_root:
            raise ContractError("--repo-root is required when reading a preview graph from stdin")
        repo_root = Path(args.repo_root).expanduser().resolve(strict=True)
        try:
            document = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            raise ContractError(f"preview graph on stdin is not valid JSON: {exc}") from exc
    else:
        graph = Path(args.graph).expanduser().resolve(strict=True)
        repo_root = _repo_root_for(graph, args.repo_root)
        document = load_json(graph)
        canonical_store = _is_canonical_store(graph, repo_root)
    nodes = nodes_of(document)
    # stdin preview はまだ書いていない node を送ることが正当な用途 (decompose の dry-run) であり、
    # ここで artifact_missing を fail させると preview 検証そのものが成立しない。
    violations = validate(nodes, repo_root=repo_root, allow_missing_artifacts=is_stdin)
    if canonical_store or args.require_canonical_envelope:
        violations = sorted(violations + envelope_findings(document),
                            key=lambda item: (item["node"], item["code"], item["detail"]))
    readiness = readiness_findings(nodes, repo_root, load_json(TEMPLATE_CONTRACT_PATH))
    if args.strict_artifact_readiness:
        violations = sorted(violations + readiness, key=lambda item: (item["node"], item["code"], item["detail"]))
    missing = readiness_missing_sections(violations)
    dump({
        "valid": not violations,
        # 互換キー: 最上位の implementation_readiness/missing_sections は graph 全体の検証結果 (violations 0 件か) で、
        # node の着手準備ではない。新しい読み手は graph_validation と node_readiness を読む。
        "implementation_readiness": "complete" if not violations else "incomplete",
        "missing_sections": missing,
        "graph_validation": {"status": "pass" if not violations else "fail", "violation_count": len(violations)},
        "node_readiness": node_readiness(nodes),
        # 本文 readiness は既定で報告だけ。enforced=true のときだけ同じ finding が violations にも入る。
        "artifact_readiness": {
            "status": "complete" if not readiness else "incomplete",
            "enforced": args.strict_artifact_readiness,
            "finding_count": len(readiness),
            "missing_sections": readiness_missing_sections(readiness),
            "findings": readiness,
        },
        "schema": str(SCHEMA_PATH),
        "violations": violations,
    })
    return 0 if not violations else 1


def node_readiness(nodes: list[Any]) -> dict[str, Any]:
    """各 node の implementation_readiness.status の集計。graph が valid でも node は incomplete でありうる。"""
    counts = {"complete": 0, "incomplete": 0, "not_applicable": 0, "unknown": 0}
    incomplete = []
    for index, node in enumerate(nodes):
        readiness = node.get("implementation_readiness") if isinstance(node, dict) else None
        raw = readiness.get("status") if isinstance(readiness, dict) else None
        status = raw if raw in {"complete", "incomplete", "not_applicable"} else "unknown"
        counts[status] += 1
        if status in {"incomplete", "unknown"}:
            node_id = (node.get("graph_node_id") or node.get("id")) if isinstance(node, dict) else None
            missing = readiness.get("missing_sections") if isinstance(readiness, dict) else None
            incomplete.append({"graph_node_id": node_id or f"nodes[{index}]", "status": status,
                               "missing_sections": missing if isinstance(missing, list) else []})
    return {**counts, "incomplete_nodes": incomplete}


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
