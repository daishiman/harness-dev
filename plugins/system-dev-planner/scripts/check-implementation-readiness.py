#!/usr/bin/env python3
# /// script
# name: check-implementation-readiness
# purpose: system-spec-harness の確定成果物 (system-spec/index.md・00-requirements-definition.md 等の確定章 + architecture graph node) を C09 解決 repo-context 経由で読み、implementation_readiness (complete/incomplete) を決定論判定する共有ゲート。C01 (emit 時) と C07 (tool-call 時) の 2 箇所から呼ばれる。
# inputs:
#   - argv: [--repo-root DIR] [--config REL] [--system-spec-root REL] [--architecture-root REL]
#   - env: SYSTEM_DEV_PROJECT_ROOT | CLAUDE_PROJECT_DIR (C09 経由)
# outputs:
#   - stdout: JSON {status: complete|incomplete, missing_sections[], checked_at RFC3339, probes}
#   - stderr: 不足章 / containment / usage violations
#   - exit: 0=complete / 1=incomplete / 2=usage or policy violation
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [resolve-project-context.py]
# requires-python: ">=3.10"
# ///
"""Implementation readiness gate (C08).

system-spec-harness が確定した仕様書とアーキテクチャ graph node の充足度を決定論で判定する。
自身は「仕様書内容の再構築」をせず、確定成果物の存在・非空・placeholder 非残存を probe し、
readiness ポリシー (evaluate_readiness) で complete/incomplete を返すだけの薄い共有ゲートである。
判定主体を単一箇所へ閉じることで C01 (生成時) と C07 (実行 hook 時) の判定が属人化しない。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

EXIT_COMPLETE = 0
EXIT_INCOMPLETE = 1
EXIT_ERROR = 2

_HERE = Path(__file__).resolve().parent
_C09_PATH = _HERE / "resolve-project-context.py"
_PLACEHOLDER_RE = re.compile(r"\bTODO\b|\bTBD\b|__PLACEHOLDER__|___FILL___|<[^>]*ここに[^>]*>", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_c09():
    """C09 を module として読み込み、context 解決と containment guard を再利用する。"""
    spec = importlib.util.spec_from_file_location("_c09_resolver", _C09_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 等が __module__ を解決できるよう登録
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@dataclass
class Probe:
    """1 つの確定成果物候補の観測結果 (判定ポリシーへの入力)。"""
    path: str            # repo-relative
    exists: bool
    non_empty: bool      # 非空 (空白除去後に本文がある)
    placeholder_free: bool  # TODO/TBD/__PLACEHOLDER__ 等が残っていない
    heading_count: int   # markdown 見出し数 (章の実体度合いの目安)
    verified: bool = False  # producer-owned validator / manifest pin の検証結果
    detail: str = ""


def _probe_file(repo_root: Path, rel: str) -> Probe:
    p = repo_root / rel
    if not p.is_file():
        return Probe(rel, exists=False, non_empty=False, placeholder_free=False, heading_count=0)
    text = p.read_text(encoding="utf-8", errors="replace")
    body = text.strip()
    headings = len([ln for ln in text.splitlines() if ln.lstrip().startswith("#")])
    return Probe(
        path=rel,
        exists=True,
        non_empty=bool(body),
        placeholder_free=not bool(_PLACEHOLDER_RE.search(text)),
        heading_count=headings,
        verified=True,
    )


def _probe_architecture(repo_root: Path, arch_root: str) -> Probe:
    """Probe the canonical architecture graph path and minimum node contract."""
    base = repo_root / arch_root
    candidate = base / "graph.json"
    rel = candidate.relative_to(repo_root).as_posix() if candidate.exists() else f"{arch_root}/graph.json"
    if not candidate.is_file():
        return Probe(rel, exists=False, non_empty=False, placeholder_free=False, heading_count=0)
    text = candidate.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
        nodes = data.get("nodes") if isinstance(data, dict) else None
        non_empty = (
            isinstance(nodes, list)
            and bool(nodes)
            and all(isinstance(node, dict) and isinstance(node.get("id"), str) and node["id"].strip()
                    for node in nodes)
        )
    except json.JSONDecodeError:
        non_empty = False
    return Probe(rel, exists=True, non_empty=non_empty,
                 placeholder_free=not bool(_PLACEHOLDER_RE.search(text)), heading_count=0,
                 verified=non_empty)


def _probe_source_plugin(plugin_root: Path) -> Probe:
    """Pinned producer identity and harness entry-point sidecar must match."""
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    package_contract = plugin_root / "references" / "package-contract.json"
    # Probe.path is a digestible single file path. Identity/version are checked
    # from the native manifest below; the sidecar is the entry-point SSOT and
    # therefore the byte source recorded in the readiness digest.
    rel = package_contract.as_posix()
    if not manifest.is_file():
        return Probe(rel, False, False, False, 0, detail="producer manifest missing")
    if not package_contract.is_file():
        return Probe(rel, False, False, False, 0, detail="producer package contract missing")
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
        contract = json.loads(package_contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Probe(rel, True, False, True, 0, detail=f"invalid producer metadata: {exc}")
    skills = contract.get("entry_points", {}).get("skills", []) if isinstance(contract, dict) else []
    verified = (
        value.get("name") == "system-spec-harness"
        and value.get("version") == "0.1.0"
        and contract.get("plugin_name") == "system-spec-harness"
        and "run-system-spec-compile" in skills
        and "assign-system-spec-completeness-evaluator" in skills
    )
    return Probe(rel, True, True, True, 0, verified=verified,
                 detail="pinned producer manifest+sidecar matched" if verified else "producer pin/entrypoint mismatch")


def _probe_completeness(repo_root: Path, rel: str, producer_root: Path) -> Probe:
    """Delegate completeness semantics to the producer-owned aggregate validator."""
    report = repo_root / rel
    if not report.is_file():
        return Probe(rel, False, False, False, 0, detail="completeness report missing")
    gate = (producer_root / "skills" / "assign-system-spec-completeness-evaluator" /
            "scripts" / "aggregate-completeness.py")
    if not gate.is_file():
        return Probe(rel, True, True, True, 0, detail="producer completeness validator missing")
    completed = subprocess.run(
        [sys.executable or "python3", str(gate), "--report", str(report)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    detail = (completed.stderr or completed.stdout).strip()
    return Probe(rel, True, report.stat().st_size > 0, True, 0,
                 verified=completed.returncode == 0, detail=detail)


def collect_probes(repo_root: Path, system_spec_root: str, architecture_root: str,
                   completeness_report: str, producer_root: Path) -> dict[str, Probe]:
    """readiness 判定ポリシーへ渡す確定成果物の観測結果を集める。"""
    return {
        "system_spec_index": _probe_file(repo_root, f"{system_spec_root}/index.md"),
        "requirements_definition": _probe_file(repo_root, f"{system_spec_root}/00-requirements-definition.md"),
        "architecture_graph": _probe_architecture(repo_root, architecture_root),
        "completeness_evaluation": _probe_completeness(repo_root, completeness_report, producer_root),
        "source_plugin_manifest": _probe_source_plugin(producer_root),
    }


def evaluate_readiness(probes: dict[str, Probe]) -> tuple[str, list[str]]:
    """implementation_readiness を判定する中核ポリシー。

    returns (status, missing_sections):
      - status: "complete" (実装着手可) または "incomplete" (handoff 停止)
      - missing_sections: incomplete の根拠となる不足/未充足成果物の logical name 一覧

    probes は collect_probes が返す {logical_name -> Probe} で、各 Probe は
    exists / non_empty / placeholder_free / heading_count を持つ。

    必須入力は system-spec index、requirements definition、architecture graph node。
    Markdown は実在・非空・placeholder 無し・少なくとも1見出し、graph は
    JSON object の non-empty ``nodes`` を必須とする。欠落理由は logical-name:reason で
    安定ソートし、呼出元が機械的に差し戻し理由を表示できるようにする。
    """
    required = ("system_spec_index", "requirements_definition", "architecture_graph",
                "completeness_evaluation", "source_plugin_manifest")
    missing: list[str] = []
    for name in required:
        probe = probes.get(name)
        if probe is None:
            missing.append(f"{name}:probe-missing")
            continue
        if not probe.exists:
            missing.append(f"{name}:file-missing")
        elif not probe.non_empty:
            missing.append(f"{name}:empty-or-no-nodes")
        elif not probe.placeholder_free:
            missing.append(f"{name}:placeholder-remains")
        elif name in {"completeness_evaluation", "source_plugin_manifest"} and not probe.verified:
            missing.append(f"{name}:producer-verification-failed")
        elif name in {"system_spec_index", "requirements_definition"} and probe.heading_count < 1:
            missing.append(f"{name}:markdown-heading-missing")
    return ("complete" if not missing else "incomplete", sorted(missing))


def resolve_context(argv_ns, c09) -> dict:
    c09_argv: list[str] = []
    if argv_ns.repo_root:
        c09_argv += ["--repo-root", argv_ns.repo_root]
    if argv_ns.config:
        c09_argv += ["--config", argv_ns.config]
    import os
    try:
        return c09.build_context(c09_argv, dict(os.environ))
    except c09.PolicyError as exc:
        raise SystemExit(_fail(EXIT_ERROR, f"repo-context 解決に失敗 (fail-closed): {exc}"))
    except c09.UsageError as exc:
        raise SystemExit(_fail(EXIT_ERROR, f"repo-context usage error: {exc}"))


def _fail(code: int, msg: str) -> int:
    print(f"[readiness] {msg}", file=sys.stderr)
    return code


def _reject_absolute(value: str | None, label: str) -> None:
    if value and (
        Path(value).is_absolute()
        or ".." in Path(value).parts
        or (len(value) >= 2 and value[1] == ":")
    ):
        raise SystemExit(_fail(EXIT_ERROR, f"{label} は repository 相対のみ許可 (absolute/traversal 拒否): {value}"))


def build_report(
    context: dict,
    system_spec_root: str,
    architecture_root: str,
    completeness_report: str,
    *,
    producer_root: Path | None = None,
) -> dict:
    """Build the readiness report from current producer and caller-repo bytes.

    C11 calls this same function immediately before promotion.  Keeping report
    construction here prevents a shape-valid but stale or forged readiness JSON
    from becoming a promotion authority.
    """
    repo_root = Path(context["repo_root"])
    producer = producer_root or (_HERE.parent.parent / "system-spec-harness")
    c09 = _load_c09()
    try:
        for rel in (
            system_spec_root,
            f"{system_spec_root}/index.md",
            f"{system_spec_root}/00-requirements-definition.md",
            architecture_root,
            f"{architecture_root}/graph.json",
            completeness_report,
        ):
            c09.guard_relative_path(repo_root, rel)
    except c09.PolicyError as exc:
        raise ValueError(f"readiness input containment 違反: {exc}") from exc
    probes = collect_probes(
        repo_root, system_spec_root, architecture_root, completeness_report, producer
    )
    status, missing = evaluate_readiness(probes)

    source_digest = hashlib.sha256()
    if status == "complete":
        for probe in sorted(probes.values(), key=lambda item: item.path):
            path = Path(probe.path)
            if not path.is_absolute():
                path = repo_root / path
            source_digest.update(probe.path.encode("utf-8")); source_digest.update(b"\0")
            source_digest.update(path.read_bytes()); source_digest.update(b"\0")

    return {
        "status": status,
        "missing_sections": missing,
        "checked_at": _now(),
        "repository_id": context["repository_id"],
        "system_spec_root": system_spec_root,
        "architecture_root": architecture_root,
        "completeness_report": completeness_report,
        "source_pin": {
            "plugin": "system-spec-harness",
            "version": "0.1.0",
            "compile_entrypoint": "run-system-spec-compile",
            "completeness_entrypoint": "assign-system-spec-completeness-evaluator",
            "source_digest": "sha256:" + source_digest.hexdigest() if status == "complete" else None,
        },
        "probes": {k: asdict(v) for k, v in probes.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Implementation readiness gate (C08)")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--system-spec-root", default=None, help="repo-relative (既定は config content_roots.system_spec)")
    parser.add_argument("--architecture-root", default=None, help="repo-relative (既定は config content_roots.architecture)")
    parser.add_argument("--completeness-report", default=None,
                        help="repo-relative producer evaluation (既定 system-spec/completeness-findings.json)")
    args = parser.parse_args(argv)

    _reject_absolute(args.system_spec_root, "--system-spec-root")
    _reject_absolute(args.architecture_root, "--architecture-root")
    _reject_absolute(args.completeness_report, "--completeness-report")

    c09 = _load_c09()
    context = resolve_context(args, c09)
    repo_root = Path(context["repo_root"])
    system_spec_root = args.system_spec_root or context["content_roots"]["system_spec"]["relative"]
    architecture_root = args.architecture_root or context["content_roots"]["architecture"]["relative"]
    completeness_report = args.completeness_report or f"{system_spec_root}/completeness-findings.json"
    try:
        for rel in (system_spec_root, architecture_root, completeness_report):
            c09.guard_relative_path(repo_root, rel)
    except c09.PolicyError as exc:
        raise SystemExit(_fail(EXIT_ERROR, f"readiness input containment 違反: {exc}"))

    try:
        report = build_report(context, system_spec_root, architecture_root, completeness_report)
    except ValueError as exc:
        raise SystemExit(_fail(EXIT_ERROR, str(exc)))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "complete":
        return EXIT_COMPLETE
    for name in report["missing_sections"]:
        print(f"[readiness] incomplete: {name}", file=sys.stderr)
    return EXIT_INCOMPLETE


if __name__ == "__main__":
    raise SystemExit(main())
