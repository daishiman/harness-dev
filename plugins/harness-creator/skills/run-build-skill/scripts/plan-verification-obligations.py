#!/usr/bin/env python3
# /// script
# name: plan-verification-obligations
# purpose: 検証 obligation の DAG を LLM を起動せずに解決し、再利用できる PASS 証跡と未解決の claim を分けた plan を出す
# inputs:
#   - argv: --contract <json> --evidence-dir <dir>（必須） [--repo-root] [--profile] [--stage] [--max-context-bytes] [--max-llm-batches] [--run-id] [--max-model-actions] [--out <json>]
# outputs:
#   - stdout: plan JSON（--out を付けたときは同じ内容をそのファイルにも書く）
#   - exit: 0=OK / 2=contract を読めない・不正（非 UTF-8、NaN・Infinity・1e999 などの有限でない数を含む）、fingerprint 対象のディレクトリを読めない、--out に書けない
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out の指定先のみ（同じディレクトリの一時ファイルに書いてから置き換える。--evidence-dir は読むだけ）
# ///
"""Resolve a verification-obligation DAG without launching an LLM.

The planner makes verification cost proportional to changed claims and unresolved
uncertainty, not to route, agent, or thought-method counts.  Exact PASS evidence
is reusable only while the claim inputs, checker contract, and dependency
fingerprints remain unchanged.

Fingerprints fail closed: a subdirectory that cannot be read stops the plan with
exit 2 instead of being skipped, because skipping it would let edits inside it
reuse a stale PASS receipt.  Directory walks have no size cap; --max-context-bytes
limits only the LLM context packing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

PROFILES = {"incremental", "exhaustive", "build-only"}
KINDS = {"generative", "deterministic", "semantic", "observational", "audit"}

# build stage は profile と直交する別の量である。
#
#   profile = 作った物にどれだけ証明を要求するか (incremental / build-only / exhaustive)
#   stage   = そもそもどこまで作るか            (draft / release)
#
# 両者を 1 本の軸へ潰さない理由: build-only を選んでも「全 component 分の受入テストを
# 赤で固定する」工程 (P04) は最後まで走る。profile は検証の深さを変えるだけで、
# 生成 obligation の集合を変えないためである。利用者が最初の 1 本を手にするまでの
# 時間を決めているのは検証の深さではなく生成の集合なので、軸を分ける。
STAGES = {"draft", "release"}

# stage 未指定 build と、stage 未宣言 obligation の共通既定。
#
# release ではなく draft を既定にする。未分類のものを release 扱いにすると、
# stage を知らない旧 contract を draft で回した瞬間に全 obligation が黙って defer され、
# 「何も作られていないのに何も落ちていない」計画が成立してしまう。分類漏れは
# 「第1稿でも実行する」側へ倒し、遅くなることはあっても静かに欠落しないようにする。
DEFAULT_STAGE = "draft"

# 第1稿で実行する obligation の種別。利用者の要求どおり「使える実体 (generative) と
# 決定論ゲート (deterministic) だけ」。意味裁定・live 観測・監査カタログは現物が
# 出てから効くものであり、初回の待ち時間へ入れても第1稿は良くならない。
DRAFT_KINDS = {"generative", "deterministic"}
DRAFT_DEFER_REASON = "not-run(stage=draft)"
RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
ACTIVATIONS = {"changed", "always", "exhaustive"}
DEFAULT_MAX_CONTEXT_BYTES = 120_000
DEFAULT_INCREMENTAL_LLM_BATCHES = 1
DEFAULT_INCREMENTAL_MODEL_ACTIONS = 4


class ContractError(ValueError):
    """Raised when a contract cannot be resolved safely."""


def _reject_json_constant(name: str) -> Any:
    # NaN・Infinity は JSON の規格外。読むと plan の stdout が strict JSON でなくなる
    raise ContractError(f"contract must not contain {name}")


def _reject_non_finite_float(text: str) -> float:
    # 1e999 は parse_constant を通らずに inf になる。NaN・Infinity と同じく読む時点で拒否し、
    # 出力の時点の「Out of range float values」(どの値か分からない) にしない
    value = float(text)
    if not math.isfinite(value):
        raise ContractError(f"contract must not contain a non-finite number: {text}")
    return value


def _raise_unreadable(exc: OSError) -> None:
    # 読めないサブディレクトリを黙って飛ばすと、その中を書き換えても fingerprint が変わらず、
    # 古い PASS receipt を再利用してしまう。fingerprint を作れないので計画ごと止める (exit 2)
    raise ContractError(f"cannot read a directory for the fingerprint: {exc.filename}: {exc.strerror}")


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_rel(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ContractError(f"path must be repository-relative and cannot contain '..': {raw}")
    return path


def _update_with_link_target(digest: Any, link: Path) -> int:
    """symlink のリンク先の中身を digest に入れ、読んだ byte 数を返す。

    リンク先の文字列だけを hash すると、リンク先のファイルを書き換えても fingerprint が変わらず、
    古い PASS receipt を再利用してしまう。ディレクトリは os.walk(followlinks=False) で辿るので、
    祖先を指すリンクでも無限に潜らない (中の symlink はリンク先の文字列で hash する)。
    """
    try:
        real = link.resolve()
    except (OSError, RuntimeError):
        digest.update(b"target-unresolvable\0")
        return 0
    if real.is_file():
        data = real.read_bytes()
        digest.update(b"target-file\0")
        digest.update(data)
        digest.update(b"\0")
        return len(data)
    if not real.is_dir():
        digest.update(b"target-missing\0")
        return 0
    total = 0
    digest.update(b"target-dir\0")
    for root, dirs, files in os.walk(real, followlinks=False, onerror=_raise_unreadable):
        dirs.sort()
        base = Path(root)
        for name in sorted(files + [d for d in dirs if (base / d).is_symlink()]):
            child = base / name
            rel = child.relative_to(real).as_posix()
            if child.is_symlink():
                digest.update(f"symlink\0{rel}\0{os.readlink(child)}\0".encode("utf-8"))
            elif child.is_file():
                data = child.read_bytes()
                digest.update(f"file\0{rel}\0".encode("utf-8"))
                digest.update(data)
                digest.update(b"\0")
                total += len(data)
    return total


def snapshot_path(repo_root: Path, raw: str) -> dict:
    """Return a deterministic digest/size snapshot for a file, dir, or symlink."""
    rel = _safe_rel(raw)
    path = repo_root / rel
    digest = hashlib.sha256()
    total_bytes = 0
    file_count = 0

    if path.is_symlink():
        target = os.readlink(path)
        digest.update(f"symlink\0{rel.as_posix()}\0{target}".encode("utf-8"))
        size = _update_with_link_target(digest, path)
        return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": len(target) + size, "files": 1, "missing": False}
    if path.is_file():
        data = path.read_bytes()
        digest.update(f"file\0{rel.as_posix()}\0".encode("utf-8"))
        digest.update(data)
        return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": len(data), "files": 1, "missing": False}
    if path.is_dir():
        # rglob と同じ集合 (symlink のディレクトリには潜らない) を、読めないディレクトリで止まる os.walk で集める
        children = [Path(root) / name
                    for root, dirs, files in os.walk(path, followlinks=False, onerror=_raise_unreadable)
                    for name in dirs + files]
        for child in sorted(children, key=lambda item: item.relative_to(repo_root).as_posix()):
            child_rel = child.relative_to(repo_root)
            if child.is_symlink():
                target = os.readlink(child)
                digest.update(f"symlink\0{child_rel.as_posix()}\0{target}\0".encode("utf-8"))
                total_bytes += len(target) + _update_with_link_target(digest, child)
                file_count += 1
            elif child.is_file():
                data = child.read_bytes()
                digest.update(f"file\0{child_rel.as_posix()}\0".encode("utf-8"))
                digest.update(data)
                digest.update(b"\0")
                total_bytes += len(data)
                file_count += 1
        digest.update(f"dir\0{rel.as_posix()}\0{file_count}".encode("utf-8"))
        return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": total_bytes, "files": file_count, "missing": False}

    digest.update(f"missing\0{rel.as_posix()}".encode("utf-8"))
    return {"path": rel.as_posix(), "sha256": digest.hexdigest(), "bytes": 0, "files": 0, "missing": True}


def _is_one_of(value: Any, allowed: Any) -> bool:
    # 集合の要素かを見る前に文字列であることを確かめる (配列や dict だと unhashable で TypeError になる)
    return isinstance(value, str) and value in allowed


def _validate_contract(contract: dict) -> list[dict]:
    # 後段が添字で読む key と型はここで全部確かめ、KeyError/TypeError の traceback (exit 1) にしない。
    if not isinstance(contract, dict):
        raise ContractError("contract must be a JSON object")
    subject = contract.get("subject")
    if contract.get("schema_version") != 1 or not isinstance(subject, str) or not subject.strip():
        raise ContractError("contract requires schema_version=1 and a non-empty subject")
    obligations = contract.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        raise ContractError("contract.obligations must be a non-empty array")
    ids: set[str] = set()
    for item in obligations:
        if not isinstance(item, dict):
            raise ContractError("every obligation must be an object")
        oid = item.get("id")
        if not isinstance(oid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]*", oid):
            raise ContractError(f"invalid obligation id: {oid!r}")
        if oid in ids:
            raise ContractError(f"duplicate obligation id: {oid}")
        ids.add(oid)
        if not _is_one_of(item.get("kind"), KINDS):
            raise ContractError(f"unknown obligation kind for {oid}: {item.get('kind')}")
        if not _is_one_of(item.get("risk"), RISK_ORDER):
            raise ContractError(f"obligation risk must be one of {sorted(RISK_ORDER)}: {oid}")
        if not _is_one_of(item.get("activation"), ACTIVATIONS):
            raise ContractError(f"obligation activation must be one of {sorted(ACTIVATIONS)}: {oid}")
        if "stage" in item and not _is_one_of(item["stage"], STAGES):
            raise ContractError(f"obligation stage must be one of {sorted(STAGES)}: {oid}")
        depends_on = item.get("depends_on")
        if depends_on is not None and (not isinstance(depends_on, list) or not all(isinstance(dep, str) for dep in depends_on)):
            raise ContractError(f"obligation depends_on must be an array of ids: {oid}")
        if depends_on and len(set(depends_on)) != len(depends_on):
            raise ContractError(f"obligation depends_on has duplicate ids: {oid}")
        confidence = item.get("minimum_confidence", 0.8)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ContractError(f"obligation minimum_confidence must be a number in 0..1: {oid}")
        claim = item.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            # null・[]・false・0 を str() で「空でない」とみなして通さない
            raise ContractError(f"obligation claim must be a non-empty string: {oid}")
        if "reuse" in item and not isinstance(item["reuse"], bool):
            # 文字列 "false" は真とみなされ、再利用を禁じたつもりで許してしまう
            raise ContractError(f"obligation reuse must be a boolean: {oid}")
        inputs = item.get("inputs")
        if not isinstance(inputs, list):
            raise ContractError(f"obligation inputs must be an array: {oid}")
        if not inputs and not isinstance(item.get("parameters"), dict):
            raise ContractError(f"obligation requires path inputs or inline parameters: {oid}")
        for entry in inputs:
            if (not isinstance(entry, dict) or not isinstance(entry.get("required"), bool)
                    or not isinstance(entry.get("context"), bool)
                    or not isinstance(entry.get("path"), str) or not entry["path"]):
                raise ContractError(f"invalid input entry for {oid}")
            _safe_rel(entry["path"])
        expected = item.get("expected_evidence_paths")
        if expected is not None and (not isinstance(expected, list)
                                     or not all(isinstance(raw, str) and raw for raw in expected)):
            # 文字列 "abc" を1文字ずつのパスとして通さない
            raise ContractError(f"obligation expected_evidence_paths must be an array of paths: {oid}")
        for raw_path in expected or []:
            _safe_rel(raw_path)
        if item["kind"] == "generative" and not isinstance(item.get("model_required"), bool):
            raise ContractError(f"generative obligation requires model_required boolean: {oid}")
        if item["kind"] == "deterministic":
            checker = item.get("checker")
            if not isinstance(checker, dict) or not checker.get("id") or not checker.get("argv"):
                raise ContractError(f"deterministic obligation requires checker.id and checker.argv: {oid}")
        if item["kind"] == "audit" and item.get("activation") != "exhaustive":
            raise ContractError(f"audit obligation must use activation=exhaustive: {oid}")
        if item["kind"] == "observational" and not _is_one_of(item.get("observation_tier"), {"fork", "live"}):
            raise ContractError(f"observational obligation requires observation_tier=fork|live: {oid}")
    for item in obligations:
        unknown = set(item.get("depends_on") or []) - ids
        if unknown:
            raise ContractError(f"unknown dependencies for {item['id']}: {sorted(unknown)}")
    return obligations


def _topological(obligations: list[dict]) -> list[dict]:
    # 再帰ではなく明示の stack で深さ優先にする (長い依存の鎖で RecursionError にしない)。順序は再帰版と同じ後行順。
    by_id = {item["id"]: item for item in obligations}
    state: dict[str, int] = {}
    ordered: list[dict] = []

    def deps_of(oid: str) -> Any:
        return iter(sorted(by_id[oid].get("depends_on") or []))

    for root in sorted(by_id):
        if state.get(root) == 2:
            continue
        state[root] = 1
        stack = [(root, deps_of(root))]
        while stack:
            oid, deps = stack[-1]
            dep = next(deps, None)
            if dep is None:
                stack.pop()
                state[oid] = 2
                ordered.append(by_id[oid])
            elif state.get(dep) == 1:
                raise ContractError(f"dependency cycle contains: {dep}")
            elif state.get(dep) != 2:
                state[dep] = 1
                stack.append((dep, deps_of(dep)))
    return ordered


def _load_receipts(evidence_dir: Path, unreadable: list[dict] | None = None) -> list[tuple[Path, dict]]:
    """構造が正しい receipt を返す。

    unreadable を渡すと、subject・obligation_id・fingerprint は読めるが構造が壊れていて、
    status が PASS でない receipt (finding_codes が整数の FAIL など) をそこに積む。
    読めない FAIL を捨てて同じ fingerprint の PASS を再利用しないよう、呼び出し側で矛盾として扱う。
    """
    receipts: list[tuple[Path, dict]] = []
    if not evidence_dir.is_dir():
        return receipts
    for path in sorted(evidence_dir.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            # 壊れた receipt (非 UTF-8 の UnicodeDecodeError を含む) は読み飛ばし、計画全体を止めない
            continue
        required = {"schema_version", "subject", "obligation_id", "fingerprint_sha256", "status", "confidence", "verifier", "evidence", "finding_codes", "produced_at"}
        structurally_valid = (
            isinstance(doc, dict)
            and required <= set(doc)
            and doc.get("schema_version") == 1
            and _is_one_of(doc.get("status"), {"PASS", "FAIL", "INCONCLUSIVE"})
            and not isinstance(doc.get("confidence"), bool)
            and isinstance(doc.get("confidence"), (int, float))
            and 0 <= doc["confidence"] <= 1
            and isinstance(doc.get("verifier"), dict)
            and isinstance(doc["verifier"].get("kind", ""), str)
            and isinstance(doc.get("evidence"), list)
            and isinstance(doc.get("finding_codes"), list)
            and all(isinstance(code, str) for code in doc["finding_codes"])
            and re.fullmatch(r"[0-9a-f]{64}", str(doc.get("fingerprint_sha256", "")))
        )
        if structurally_valid:
            receipts.append((path, doc))
        elif (unreadable is not None and isinstance(doc, dict) and doc.get("status") != "PASS"
              and all(isinstance(doc.get(key), str)
                      for key in ("subject", "obligation_id", "fingerprint_sha256"))):
            unreadable.append(doc)
    return receipts


def _receipt_artifacts_current(repo_root: Path, receipt: dict) -> bool:
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    for item in evidence:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            return False
        try:
            current = snapshot_path(repo_root, str(item["path"]))
        except (OSError, ContractError):
            return False
        if current["missing"] or current["sha256"] != item["sha256"]:
            return False
    return True


def _matching_receipts(receipts: list[tuple[Path, dict]], repo_root: Path, subject: str, oid: str, fingerprint: str) -> list[tuple[Path, dict]]:
    return [
        (path, doc) for path, doc in receipts
        if doc.get("subject") == subject
        and doc.get("obligation_id") == oid
        and doc.get("fingerprint_sha256") == fingerprint
        and _receipt_artifacts_current(repo_root, doc)
    ]


def _pack_llm_batches(records: list[dict], snapshots: dict[str, dict], max_context_bytes: int) -> list[dict]:
    candidates = [record for record in records if record["action"] in {"adjudicate", "audit"}]
    candidates.sort(key=lambda record: (RISK_ORDER.get(record["risk"], 9), record["id"]))
    batches: list[dict] = []
    current_ids: list[str] = []
    current_paths: set[str] = set()

    def emit() -> None:
        if not current_ids:
            return
        size = sum(snapshots[path]["bytes"] for path in current_paths)
        batches.append({
            "batch_id": f"semantic-{len(batches) + 1}",
            "obligation_ids": list(current_ids),
            "context_paths": sorted(current_paths),
            "context_bytes": size,
            "over_budget": size > max_context_bytes,
        })

    for record in candidates:
        candidate_paths = set(record["context_paths"])
        union = current_paths | candidate_paths
        union_size = sum(snapshots[path]["bytes"] for path in union)
        if current_ids and union_size > max_context_bytes:
            emit()
            current_ids = []
            current_paths = set()
        current_ids.append(record["id"])
        current_paths |= candidate_paths
    emit()
    return batches


def build_plan(
    contract: dict,
    repo_root: Path,
    evidence_dir: Path,
    profile: str = "incremental",
    max_context_bytes: int = DEFAULT_MAX_CONTEXT_BYTES,
    max_llm_batches: int | None = None,
    run_id: str | None = None,
    max_model_actions: int | None = None,
    stage: str = DEFAULT_STAGE,
) -> dict:
    if profile not in PROFILES:
        raise ContractError(f"unsupported profile: {profile}")
    if stage not in STAGES:
        raise ContractError(f"unsupported stage: {stage}")
    if max_context_bytes < 1:
        raise ContractError("max_context_bytes must be positive")
    if max_llm_batches is not None and max_llm_batches < 0:
        raise ContractError("max_llm_batches must be non-negative")
    if max_model_actions is not None and max_model_actions < 0:
        raise ContractError("max_model_actions must be non-negative")
    effective_max_batches = (
        max_llm_batches
        if max_llm_batches is not None
        else DEFAULT_INCREMENTAL_LLM_BATCHES if profile == "incremental"
        else 0 if profile == "build-only"
        else None
    )
    effective_max_model_actions = (
        max_model_actions
        if max_model_actions is not None
        else DEFAULT_INCREMENTAL_MODEL_ACTIONS if profile in {"incremental", "build-only"}
        else None
    )
    repo_root = repo_root.resolve()
    obligations = _topological(_validate_contract(contract))
    subject = str(contract["subject"])
    unreadable_receipts: list[dict] = []
    receipts = _load_receipts(evidence_dir.resolve(), unreadable_receipts)

    snapshots: dict[str, dict] = {}
    fingerprints: dict[str, str] = {}
    for item in obligations:
        input_states = []
        for entry in item["inputs"]:
            path = str(entry["path"])
            snapshot = snapshots.setdefault(path, snapshot_path(repo_root, path))
            if entry["required"] and snapshot["missing"]:
                raise ContractError(f"required input is missing for {item['id']}: {path}")
            input_states.append({"path": path, "sha256": snapshot["sha256"], "missing": snapshot["missing"]})
        fingerprint_payload = {
            "id": item["id"],
            "claim": item["claim"],
            "kind": item["kind"],
            "risk": item["risk"],
            "activation": item["activation"],
            "checker": item.get("checker"),
            "observation_tier": item.get("observation_tier"),
            "parameters": item.get("parameters", {}),
            "expected_evidence_paths": item.get("expected_evidence_paths", []),
            "model_required": item.get("model_required"),
            "inputs": input_states,
            "dependency_fingerprints": {dep: fingerprints[dep] for dep in sorted(item.get("depends_on") or [])},
        }
        fingerprints[item["id"]] = _canonical_sha(fingerprint_payload)

    records: list[dict] = []
    actions: dict[str, str] = {}
    # stage の cut で defer した obligation。下流へ伝播させるために別に持つ
    # (通常の defer と混ぜると「監査だから defer」と「第1稿の外だから defer」を
    # 区別できず、release 昇格時に何を回収すべきか読めなくなる)。
    stage_deferred: set[str] = set()
    for item in obligations:
        oid = item["id"]
        fingerprint = fingerprints[oid]
        item_stage = str(item.get("stage") or DEFAULT_STAGE)
        blocked_by = [dep for dep in item.get("depends_on") or [] if actions.get(dep) != "reuse"]
        context_paths = [str(entry["path"]) for entry in item["inputs"] if entry["context"]]
        record = {
            "id": oid,
            "claim": item["claim"],
            "kind": item["kind"],
            "risk": item["risk"],
            "stage": item_stage,
            "fingerprint_sha256": fingerprint,
            "action": "blocked",
            "reason": "dependency-proof-missing",
            "blocked_by": blocked_by,
            "context_paths": context_paths,
            "checker": item.get("checker"),
            "observation_tier": item.get("observation_tier"),
            "expected_evidence_paths": item.get("expected_evidence_paths", []),
            "model_required": item.get("model_required"),
            "reused_evidence": None,
        }
        deferred_deps = sorted(set(item.get("depends_on") or []) & stage_deferred)
        if stage == "draft" and item_stage != "draft":
            record.update(action="defer", reason=DRAFT_DEFER_REASON)
            stage_deferred.add(oid)
        elif stage == "draft" and item["kind"] not in DRAFT_KINDS:
            # 第1稿は「実体 + 決定論ゲート」まで。意味裁定・観測・監査は release で回す。
            record.update(action="defer", reason=f"{DRAFT_DEFER_REASON};kind={item['kind']}")
            stage_deferred.add(oid)
        elif stage == "draft" and deferred_deps:
            # 上流を第1稿の外へ出した以上、それに依存する claim も証明できない。
            # ここを blocked にすると「証拠が足りない」と読めてしまうが、実際には
            # 意図的に後ろへ回しただけなので、原因を defer として明示する。
            record.update(action="defer",
                          reason=f"{DRAFT_DEFER_REASON};dependency-deferred",
                          blocked_by=deferred_deps)
            stage_deferred.add(oid)
        elif item["kind"] == "audit" and profile != "exhaustive":
            record.update(action="defer", reason="audit-catalog-is-not-a-runtime-fanout")
        elif (
            item.get("activation") == "exhaustive"
            and profile != "exhaustive"
            # draft の generative/deterministic proof は引き渡しの実在条件。
            # profile で defer すると成果物なしの false-ready になる。
            and not (stage == "draft" and item["kind"] in DRAFT_KINDS)
        ):
            record.update(action="defer", reason="activation-requires-exhaustive")
        elif profile == "build-only" and item["kind"] not in {"generative", "deterministic"}:
            record.update(action="defer", reason="not-run(profile=build-only)")
        elif blocked_by:
            pass
        else:
            matching = _matching_receipts(receipts, repo_root, subject, oid, fingerprint)
            statuses = {doc.get("status") for _, doc in matching}
            minimum_confidence = float(item.get("minimum_confidence", 0.8))
            passes = [
                (path, doc) for path, doc in matching
                if doc.get("status") == "PASS" and float(doc.get("confidence", 0)) >= minimum_confidence
            ]
            may_reuse = item.get("reuse", True) and item.get("activation") != "always"
            unreadable_non_pass = any(
                doc.get("subject") == subject
                and doc.get("obligation_id") == oid
                and doc.get("fingerprint_sha256") == fingerprint
                and _receipt_artifacts_current(repo_root, doc)
                for doc in unreadable_receipts
            )
            if len(statuses) > 1 or (passes and unreadable_non_pass):
                record.update(action="escalate", reason="contradictory-current-evidence")
            elif may_reuse and passes:
                path, _ = sorted(passes, key=lambda pair: str(pair[0]))[-1]
                record.update(action="reuse", reason="exact-proof-current", reused_evidence=str(path))
            elif matching and statuses == {"FAIL"}:
                record.update(action="remediate", reason="current-proof-failed")
            elif matching and (statuses == {"INCONCLUSIVE"} or (statuses == {"PASS"} and not passes)):
                record.update(action="escalate", reason="uncertainty-above-threshold")
            elif item["kind"] == "generative":
                record.update(action="generate", reason="build-proof-missing")
            elif item["kind"] == "deterministic":
                record.update(action="check", reason="machine-proof-missing")
            elif item["kind"] == "semantic":
                record.update(action="adjudicate", reason="irreducible-semantic-proof-missing")
            elif item["kind"] == "observational":
                record.update(action="observe", reason="behavioral-proof-missing")
            else:
                record.update(action="audit", reason="explicit-exhaustive-audit")
        actions[oid] = record["action"]
        records.append(record)

    llm_batches = _pack_llm_batches(records, snapshots, max_context_bytes)
    finding_counts: Counter[tuple[str, str]] = Counter()
    for _, doc in receipts:
        if doc.get("subject") != subject or doc.get("status") not in {"FAIL", "INCONCLUSIVE"}:
            continue
        for code in set(doc.get("finding_codes") or []):
            finding_counts[(str(doc.get("obligation_id")), str(code))] += 1
    automation_candidates = [
        {"obligation_id": oid, "finding_code": code, "occurrences": count, "next_action": "promote-to-deterministic-checker"}
        for (oid, code), count in sorted(finding_counts.items()) if count >= 2
    ]
    counts = {action: sum(1 for record in records if record["action"] == action) for action in sorted(set(actions.values()))}
    total_context_bytes = sum(batch["context_bytes"] for batch in llm_batches)
    reused = counts.get("reuse", 0)
    total = len(records)
    budget_reasons = []
    if any(batch["over_budget"] for batch in llm_batches):
        budget_reasons.append("semantic-context-batch-exceeds-byte-budget")
    if effective_max_batches is not None and len(llm_batches) > effective_max_batches:
        budget_reasons.append("semantic-batch-count-exceeds-run-budget")
    consumed_action_keys = {
        str(doc.get("model_action_id") or path)
        for path, doc in receipts
        if run_id
        and doc.get("subject") == subject
        and doc.get("run_id") == run_id
        and isinstance(doc.get("verifier"), dict)
        and doc["verifier"].get("kind") in {"llm", "live"}
    }
    consumed_model_actions = len(consumed_action_keys)
    planned_model_actions = (
        sum(
            1
            for record in records
            if record["action"] == "generate" and record.get("model_required")
        )
        + len(llm_batches)
        + sum(1 for record in records if record["action"] == "observe")
    )
    if (
        effective_max_model_actions is not None
        and consumed_model_actions + planned_model_actions > effective_max_model_actions
    ):
        budget_reasons.append("cumulative-model-actions-exceed-run-budget")
    pending_draft = sorted(
        record["id"]
        for record in records
        if stage == "draft"
        and record["action"] != "reuse"
        # stage cut 由来の defer だけが意図的繰越し。profile/activation 等の
        # defer は実体proofの代わりにならず、引き渡しを fail-closed で止める。
        and not (record["action"] == "defer" and record["id"] in stage_deferred)
    )
    handoff_ready = stage == "draft" and not pending_draft
    stage_status = (
        "draft-building"
        if stage == "draft" and pending_draft
        else "usable-draft"
        if stage == "draft"
        else "ok"
    )
    if pending_draft:
        stage_instruction = (
            "draft 対象の generation/check が残っている。pending_draft だけを実行し、"
            "決定論ゲート修復は1周までとする。現物の proof が付くまで引き渡しを宣言しない。"
        )
    elif stage_deferred:
        stage_instruction = (
            "第1稿は使える実体まで。release completed を宣言せず、"
            "build-improvement-gate.py へ渡す。単一評価contextの初回30思考法診断を1回だけ行い、"
            "所見を提示して改善levelを聞く。回答前に改善せず、自動で release/exhaustive へ進まない。"
            "draft の PASS receipt は fingerprint に stage を含めないため release でそのまま再利用される "
            "(昇格は繰越し分の追加実行だけで済み、作り直しにならない)。"
        )
    else:
        stage_instruction = "繰越した obligation は無い。"
    return {
        "schema_version": 1,
        "subject": subject,
        "run_id": run_id,
        "profile": profile,
        "stage": stage,
        "stage_gate": {
            # draft-building は生成中、usable-draft は proof 付きの正常引き渡し点。
            # failure/incomplete と同じ状態へ畳むと dispatcher が完成版を目指して
            # 自動周回する一方、proof 前から usable とすると空の引き渡しになる。
            "status": stage_status,
            "handoff_ready": handoff_ready,
            "pending_draft": pending_draft,
            "auto_promote": False,
            "max_repair_rounds": 1 if stage == "draft" else 3,
            "deferred_to_release": sorted(stage_deferred),
            "deferred_count": len(stage_deferred),
            "next_gate": (
                "build-improvement-gate.py"
                if stage == "draft" and not pending_draft
                else None
            ),
            "instruction": stage_instruction,
        },
        "cost_model": "changed-obligations-plus-unresolved-uncertainty",
        "counts": counts,
        "cost_summary": {
            "total_obligations": total,
            "proof_reuse_ratio": round(reused / total, 4) if total else 0,
            "avoided_executions": reused,
            "generation_actions": counts.get("generate", 0),
            "deterministic_checks": counts.get("check", 0),
            "semantic_actions": counts.get("adjudicate", 0) + counts.get("audit", 0),
            "observational_actions": counts.get("observe", 0),
            "semantic_context_bytes": total_context_bytes,
            "escalations": counts.get("escalate", 0),
            "consumed_model_actions": consumed_model_actions,
            "planned_model_actions": planned_model_actions,
        },
        "budget_gate": {
            "status": "blocked" if budget_reasons else "ok",
            "reasons": budget_reasons,
            "max_context_bytes_per_batch": max_context_bytes,
            "max_llm_batches": effective_max_batches,
            "max_model_actions": effective_max_model_actions,
            "instruction": "Do not launch model work while blocked; narrow context/contract or obtain an explicit budget override.",
        },
        "llm_batch_count": len(llm_batches),
        "llm_batches": llm_batches,
        "generation_queue": [record["id"] for record in records if record["action"] == "generate"],
        "observational_queue": [record["id"] for record in records if record["action"] == "observe"],
        "automation_candidates": automation_candidates,
        "obligations": records,
    }


def _write_atomic(out: Path, rendered: str) -> None:
    # 途中で止まっても半端な plan を残さないよう、同じディレクトリの一時ファイルから置き換える
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
    try:
        umask = os.umask(0)
        os.umask(umask)
        os.fchmod(fd, 0o666 & ~umask)  # mkstemp の 0600 ではなく、従来の write_text と同じ権限にする
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        os.replace(tmp_name, out)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contract", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="incremental")
    parser.add_argument(
        "--stage", choices=sorted(STAGES), default=DEFAULT_STAGE,
        help=("build stage。draft は使える実体 (generative) と決定論ゲートだけを回し、"
              "受入テスト設計・意味レビュー・監査を release へ繰り越す。無指定は draft。"
              "release は利用者が第1稿を確認した後に明示する。"),
    )
    parser.add_argument("--max-context-bytes", type=int, default=DEFAULT_MAX_CONTEXT_BYTES)
    parser.add_argument("--max-llm-batches", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--max-model-actions", type=int)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        contract = json.loads(Path(args.contract).read_text(encoding="utf-8"),
                              parse_constant=_reject_json_constant,
                              parse_float=_reject_non_finite_float)
        plan = build_plan(
            contract,
            Path(args.repo_root),
            Path(args.evidence_dir),
            args.profile,
            args.max_context_bytes,
            args.max_llm_batches,
            args.run_id,
            args.max_model_actions,
            args.stage,
        )
        rendered = json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.out:
            _write_atomic(Path(args.out), rendered)
    except (OSError, ValueError, RecursionError, ContractError) as exc:
        # ValueError は JSONDecodeError と非 UTF-8 の UnicodeDecodeError を含む
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
