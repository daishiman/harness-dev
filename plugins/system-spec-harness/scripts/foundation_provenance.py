#!/usr/bin/env python3
# /// script
# name: foundation_provenance
# version: 0.1.0
# purpose: 上位概念 U1-U9 の現在値を支える根拠 qa を決定論で検査する内部モジュール (writer と validator で共有)
# inputs:
#   - Python API: spec-state の dict
# outputs:
#   - Python API: 違反メッセージのリスト
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Deterministic provenance checks for the effective U1--U9 foundation.

Schema 1.0 used immutable ``qa-foundation-u1`` ... ``u9`` entries as both
history and the current source.  Schema 1.1 keeps those entries immutable but
adds an explicit per-U pointer to the source which actually supports the
current value.  The state writer and coverage validator share this module so
the two gates cannot drift.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import PurePosixPath

FOUNDATION_SOURCE_INDEXES = (
    ("essential_purpose", "U1", "qa-foundation-u1"),
    ("background", "U2", "qa-foundation-u2"),
    ("goals", "U3", "qa-foundation-u3"),
    ("objectives", "U4", "qa-foundation-u4"),
    ("success_criteria", "U5", "qa-foundation-u5"),
    ("stakeholders", "U6", "qa-foundation-u6"),
    ("scope", "U7", "qa-foundation-u7"),
    ("constraints", "U8", "qa-foundation-u8"),
    ("concrete_intents", "U9", "qa-foundation-u9"),
)
FOUNDATION_U_LABELS = tuple(label for _field, label, _qa in FOUNDATION_SOURCE_INDEXES)
SOURCE_KINDS = {"user-dialogue", "written-requirements"}
U_MARKER_RE = re.compile(r"(?<![A-Za-z0-9])U([1-9])(?![A-Za-z0-9])")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BASE_BINDING_KEYS = {"qa_ref", "approval_ref"}
SHARED_EVIDENCE_KEYS = {"evidence_quote", "evidence_sha256"}


def _indexed_log(raw: object, label: str, findings: list[str]) -> dict[str, dict]:
    if not isinstance(raw, list):
        findings.append(f"requirements_foundation: {label} は配列必須")
        return {}
    ids = [
        entry.get("id")
        for entry in raw
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    for entry_id, count in Counter(ids).items():
        if count > 1:
            findings.append(
                f"requirements_foundation: {label} id={entry_id!r} が重複 ({count}件)"
            )
    return {
        entry["id"]: entry
        for entry in raw
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def _is_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and str(path) not in {"", "."}


def _validate_source(entry: dict, prefix: str, findings: list[str]) -> None:
    question = entry.get("question")
    answer = entry.get("answer")
    if not isinstance(question, str) or not question.strip():
        findings.append(f"{prefix} の question が空")
    if not isinstance(answer, str) or not answer.strip():
        findings.append(f"{prefix} の answer (利用者原文) が空")
    source = entry.get("source")
    if not isinstance(source, dict) or source.get("kind") not in SOURCE_KINDS:
        findings.append(f"{prefix} の source.kind は {sorted(SOURCE_KINDS)} のいずれか必須")
        return
    if source["kind"] != "written-requirements":
        return
    path, section, digest = source.get("path"), source.get("section"), source.get("sha256")
    if not _is_relative_path(path):
        findings.append(f"{prefix} の written source.path は安全な相対パス必須")
    if not isinstance(section, str) or not section.strip():
        findings.append(f"{prefix} の written source.section が空")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        findings.append(f"{prefix} の written source.sha256 が不正")
    elif isinstance(answer, str) and hashlib.sha256(answer.encode("utf-8")).hexdigest() != digest:
        findings.append(f"{prefix} の written source.sha256 が answer 原文と不一致")


def _validate_legacy_indexes(entries: dict[str, dict], findings: list[str]) -> None:
    """Validate the exact schema-1.0 canonical index contract."""
    for _field, label, entry_id in FOUNDATION_SOURCE_INDEXES:
        entry = entries.get(entry_id)
        prefix = f"requirements_foundation: {label} source-index ({entry_id})"
        if not entry:
            findings.append(f"{prefix} が qa_log に不在")
            continue
        _validate_source(entry, prefix, findings)
        question = entry.get("question")
        marker_numbers = set(U_MARKER_RE.findall(question or ""))
        if marker_numbers != {label.removeprefix("U")}:
            findings.append(f"{prefix} は 1論点の {label} を示す question が必要")
        source = entry.get("source")
        if isinstance(source, dict) and source.get("kind") == "written-requirements":
            path, section = source.get("path"), source.get("section")
            if isinstance(question, str) and (
                (isinstance(path, str) and path not in question)
                or (isinstance(section, str) and section not in question)
            ):
                findings.append(f"{prefix} の question に written source.path と section が必要")


def _validate_effective_indexes(
    data: dict,
    entries: dict[str, dict],
    approvals: dict[str, dict],
    findings: list[str],
) -> None:
    foundation = data.get("requirements_foundation")
    refs = foundation.get("effective_source_refs") if isinstance(foundation, dict) else None
    if not isinstance(refs, dict):
        findings.append(
            "requirements_foundation.effective_source_refs は U1-U9 source-index の object 必須"
        )
        return
    if set(refs) != set(FOUNDATION_U_LABELS):
        findings.append(
            "requirements_foundation.effective_source_refs は U1-U9 を過不足なく一意に持つ必要がある"
        )

    used_approvals: set[str] = set()
    bindings_by_qa: dict[str, list[tuple[str, dict]]] = {}
    for label in FOUNDATION_U_LABELS:
        binding = refs.get(label)
        prefix = f"requirements_foundation: {label} effective source-index"
        if not isinstance(binding, dict):
            findings.append(f"{prefix} は object 必須")
            continue
        binding_keys = set(binding)
        if not BASE_BINDING_KEYS.issubset(binding_keys) or binding_keys - (
            BASE_BINDING_KEYS | SHARED_EVIDENCE_KEYS
        ):
            findings.append(
                f"{prefix} は qa_ref / approval_ref 必須、shared QA のみ"
                " evidence_quote / evidence_sha256 を追加可"
            )
        qa_ref, approval_ref = binding.get("qa_ref"), binding.get("approval_ref")
        if not isinstance(qa_ref, str) or not qa_ref.strip():
            findings.append(f"{prefix}.qa_ref は非空文字列必須")
        else:
            bindings_by_qa.setdefault(qa_ref, []).append((label, binding))
            if qa_ref not in entries:
                findings.append(f"{prefix}.qa_ref={qa_ref!r} が qa_log に不在")
            else:
                entry = entries[qa_ref]
                if entry.get("superseded_by") is not None:
                    findings.append(
                        f"{prefix}.qa_ref={qa_ref!r} は superseded_by="
                        f"{entry['superseded_by']!r} で置き換え済み (retired) の entry"
                    )
                _validate_source(entry, f"{prefix} ({qa_ref})", findings)
                marker_numbers = set(U_MARKER_RE.findall(entry.get("question") or ""))
                expected_marker = label.removeprefix("U")
                if expected_marker not in marker_numbers:
                    findings.append(
                        f"{prefix} ({qa_ref}) は対象 {label} を示す question が必要"
                    )
        if not isinstance(approval_ref, str) or not approval_ref.strip():
            findings.append(f"{prefix}.approval_ref は非空文字列必須")
        elif approval_ref not in approvals:
            findings.append(f"{prefix}.approval_ref={approval_ref!r} が approval_log に不在")
        else:
            used_approvals.add(approval_ref)

    _validate_shared_effective_bindings(bindings_by_qa, entries, findings)

    current = foundation.get("approval_ref") if isinstance(foundation, dict) else None
    if isinstance(current, str) and current not in used_approvals:
        findings.append(
            "requirements_foundation: 現行 approval_ref が effective_source_refs の"
            " approval_ref に1件も含まれない"
        )


def _validate_shared_effective_bindings(
    bindings_by_qa: dict[str, list[tuple[str, dict]]],
    entries: dict[str, dict],
    findings: list[str],
) -> None:
    """Fail closed on the mechanically provable boundary of shared QA.

    A shared QA is exceptional: the question must name exactly the U labels
    which bind to it, each consumer must content-address a distinct exact quote
    from the answer, and all bindings must cite the same approval.  The quote
    binding is deterministic separation; whether each quote semantically proves
    the current U value remains an independent audit responsibility.
    """
    for qa_ref, bindings in bindings_by_qa.items():
        if len(bindings) < 2 or qa_ref not in entries:
            continue
        labels = tuple(label for label, _binding in bindings)
        expected_markers = {label.removeprefix("U") for label in labels}
        entry = entries[qa_ref]
        question_markers = set(U_MARKER_RE.findall(entry.get("question") or ""))
        prefix = f"requirements_foundation: shared qa_ref={qa_ref!r} ({'/'.join(labels)})"
        if question_markers != expected_markers:
            findings.append(
                f"{prefix} question の U marker は binding 対象と過不足なく"
                "一致する必要がある"
            )

        answer = entry.get("answer")
        evidence_quotes: list[tuple[str, str]] = []
        for label, binding in bindings:
            binding_keys = set(binding)
            if binding_keys != BASE_BINDING_KEYS | SHARED_EVIDENCE_KEYS:
                findings.append(
                    f"{prefix} {label} binding は evidence_quote / evidence_sha256 を必須とする"
                )
            quote = binding.get("evidence_quote")
            digest = binding.get("evidence_sha256")
            if not isinstance(quote, str) or not quote.strip():
                findings.append(f"{prefix} {label}.evidence_quote は非空文字列必須")
                continue
            evidence_quotes.append((label, quote))
            if not isinstance(answer, str) or quote not in answer:
                findings.append(
                    f"{prefix} {label}.evidence_quote は qa_log answer 内の完全一致 excerpt 必須"
                )
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                findings.append(f"{prefix} {label}.evidence_sha256 が不正")
            elif hashlib.sha256(quote.encode("utf-8")).hexdigest() != digest:
                findings.append(
                    f"{prefix} {label}.evidence_sha256 が evidence_quote と不一致"
                )

        for index, (left_label, left_quote) in enumerate(evidence_quotes):
            for right_label, right_quote in evidence_quotes[index + 1 :]:
                if left_quote in right_quote or right_quote in left_quote:
                    findings.append(
                        f"{prefix} evidence_quote は consumer ごとに独立する必要がある"
                        f" ({left_label}/{right_label})"
                    )

        approval_refs = {
            binding.get("approval_ref") for _label, binding in bindings
        }
        if len(approval_refs) != 1:
            findings.append(
                f"{prefix} の各 binding は同じ approval_ref を指す必要がある"
            )

    for qa_ref, bindings in bindings_by_qa.items():
        if len(bindings) == 1:
            label, binding = bindings[0]
            if set(binding) & SHARED_EVIDENCE_KEYS:
                findings.append(
                    f"requirements_foundation: {label} effective source-index ({qa_ref}) "
                    "の evidence は shared qa_ref でのみ使用可"
                )


def validate_foundation_source_indexes(data: dict) -> list[str]:
    """Return findings unless every U1--U9 has a trustworthy current source.

    Only exact schema 1.0 state may fall back to the immutable canonical
    indexes.  Current state fails closed when the effective bindings are absent.
    """
    findings: list[str] = []
    entries = _indexed_log(data.get("qa_log"), "qa_log", findings)
    foundation = data.get("requirements_foundation")
    refs = foundation.get("effective_source_refs") if isinstance(foundation, dict) else None
    if data.get("schema_version") == "1.0" and refs is None:
        _validate_legacy_indexes(entries, findings)
        return findings
    approvals = _indexed_log(data.get("approval_log"), "approval_log", findings)
    _validate_effective_indexes(data, entries, approvals, findings)
    return findings
