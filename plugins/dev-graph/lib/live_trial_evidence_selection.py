#!/usr/bin/env python3
# /// script
# name: live-trial-evidence-selection
# purpose: criteria receipt が採用した PASS live-trial から task.md を安全に選択する。
# inputs: [repository root, dev-graph skill name]
# outputs: [Path | None]
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""Live-trial 証跡の選択を criteria receipt に束縛する小さな read-only module.

run-id の辞書順だけでは、時計ずれで将来日付を持つ古い証跡を fresh PASS より優先する。
criteria-test/scenario-verdict.json は人間・機械双方が採用した evidence を示す正本なので、
OUT1 が参照する schema-valid PASS verdict を優先する。receipt が欠落した場合だけ従来の
辞書順 fallback を許容し、存在する receipt の破損・不整合は呼出側が fail-closed にできる
よう選択エラーを返す。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def verdict_selection_from_criteria_receipt(
    root: Path, plugin: str, skill: str
) -> tuple[Path | None, str | None]:
    """criteria receipt の verdict を返す。receipt が不正なら error を返す。"""
    base = root / "eval-log" / plugin / skill / "live-trial"
    receipt_path = root / "eval-log" / plugin / skill / "criteria-test" / "scenario-verdict.json"
    if not receipt_path.is_file():
        return None, None
    receipt = _load_json(receipt_path)
    if receipt is None:
        return None, f"criteria-receipt-invalid-json: {receipt_path}"
    results = receipt.get("criteria_results")
    if not isinstance(results, dict):
        return None, f"criteria-receipt-invalid: {receipt_path} の criteria_results が object ではない"

    refs: list[tuple[str, str]] = []
    for criterion_id, criterion in results.items():
        if not isinstance(criterion, dict):
            continue
        ref = criterion.get("live_trial_verdict_ref")
        is_live_trial = criterion.get("verify_by") == "live-trial" or (
            criterion_id == "OUT1" and ref is not None
        )
        if not is_live_trial:
            continue
        if not isinstance(ref, str) or not ref:
            return None, (
                f"criteria-receipt-invalid: {receipt_path} の "
                f"{criterion_id}.live_trial_verdict_ref が空または文字列ではない"
            )
        refs.append((criterion_id, ref))

    if not refs:
        return None, None
    unique_refs = {ref for _, ref in refs}
    if len(unique_refs) != 1:
        joined = ", ".join(f"{criterion_id}={ref}" for criterion_id, ref in refs)
        return None, f"criteria-receipt-ambiguous: {receipt_path} の ref が複数: {joined}"

    ref = next(iter(unique_refs))
    if Path(ref).is_absolute() or Path(ref).name != "verdict.json":
        return None, f"criteria-receipt-invalid-ref: {receipt_path} の ref={ref!r}"

    verdict_path = (root / ref).resolve()
    try:
        verdict_path.relative_to(base.resolve())
    except ValueError:
        return None, f"criteria-receipt-outside-live-trial: {receipt_path} の ref={ref!r}"
    if verdict_path.name != "verdict.json":
        return None, f"criteria-receipt-invalid-ref: {receipt_path} の ref={ref!r}"
    verdict = _load_json(verdict_path)
    overall = verdict.get("overall") if isinstance(verdict, dict) else None
    if not isinstance(overall, dict) or overall.get("verdict") != "PASS":
        return None, f"criteria-receipt-invalid-verdict: {receipt_path} の ref={ref!r} は PASS ではない"
    return verdict_path, None


def verdict_path_from_criteria_receipt(root: Path, plugin: str, skill: str) -> Path | None:
    """互換 API: receipt が採用した containment 済み PASS verdict を返す。"""
    verdict_path, _ = verdict_selection_from_criteria_receipt(root, plugin, skill)
    return verdict_path


def task_path_from_criteria_receipt(root: Path, skill: str) -> Path | None:
    """dev-graph OUT1 receipt が採用した PASS verdict の task.md を返す。"""
    verdict_path = verdict_path_from_criteria_receipt(root, "dev-graph", skill)
    if verdict_path is None:
        return None
    task = verdict_path.parent / "task.md"
    return task if task.is_file() else None


def latest_task_path(root: Path, skill: str) -> Path | None:
    """criteria receipt の PASS evidence、次に最新 run-id の task.md を返す。

    criteria receipt が採用した current PASS を優先することで、時計ずれを含む run-id の
    辞書順が古い verdict を勝たせない。receipt が無い場合だけ、従来どおり verdict 保有
    run-id の辞書順最大へ後退する。verdict の無い中断 run は常に対象外である。
    """
    receipted = task_path_from_criteria_receipt(root, skill)
    if receipted is not None:
        return receipted
    base = root / "eval-log" / "dev-graph" / skill / "live-trial"
    if not base.is_dir():
        return None
    candidates = sorted(
        (
            directory
            for directory in base.iterdir()
            if directory.is_dir() and (directory / "verdict.json").is_file()
        ),
        key=lambda directory: directory.name,
    )
    for directory in reversed(candidates):
        if (directory / "task.md").is_file():
            return directory / "task.md"
    return None
