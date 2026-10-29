"""Elegant-review の Phase 順序・signal・verdict 導出を検査する補助モジュール。

CLI と 30 paradigm の構造検査は validate-paradigm-coverage.py が所有し、本 module は
tree 走査を伴う横断検査だけを担当する。condition_signal の対応表は呼出元から受け取り、
同じ規則を 2 ファイルへ複製しない。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_PHASE1_NAME = "shared_state.md"
_PHASE2_GLOB = "findings-phase2-*.json"
_PHASE3_NAME = "findings.json"
_PHASE3_GLOB = "phase3-*.json"

# condition/condition_signal 対応検査を error へ昇格させる run 作成日の境界。
STRICT_SIGNAL_FROM = "20260809"
_RUN_DATE_RE = re.compile(r"^run-(\d{8})(?:-|$)")
_DERIVED_KEYS = ("verdict", "fail_counts", "thought_method_coverage", "iteration_count", "status")


def check_phase_order(run_dir: Path) -> tuple[str, list[str]]:
    """1 run の Phase1→2→3 成果物の存在と順序を検査する。"""
    phase1 = run_dir / _PHASE1_NAME
    phase2 = sorted(run_dir.glob(_PHASE2_GLOB))
    phase3 = [p for p in [run_dir / _PHASE3_NAME] if p.is_file()]
    phase3 += sorted(run_dir.glob(_PHASE3_GLOB))
    if not (phase1.is_file() and phase2 and phase3):
        return "skipped", []
    try:
        t2_max = max(p.stat().st_mtime for p in phase2)
        t3 = max(p.stat().st_mtime for p in phase3)
    except OSError as exc:
        return "skipped", [f"{run_dir}: stat failed, skipped: {exc}"]
    errors: list[str] = []
    if t2_max > t3:
        errors.append(
            f"{run_dir}: phase order violation: {_PHASE2_GLOB} (Phase2) is newer "
            "than Phase3 artifacts (findings.json / phase3-*.json)"
        )
    return ("violation", errors) if errors else ("ok", [])


def run_is_strict(run_dir: Path) -> bool:
    """run-YYYYMMDD-* が境界以降なら signal/verdict 不整合を error にする。"""
    match = _RUN_DATE_RE.match(run_dir.name)
    return bool(match) and match.group(1) >= STRICT_SIGNAL_FROM


def check_signal_consistency(
    run_dir: Path,
    signal_to_condition: dict[str, str],
    force_strict: bool = False,
) -> tuple[int, list[str], list[str]]:
    """run 内の findings 系 JSON の condition ↔ condition_signal 対応を検査する。"""
    strict = force_strict or run_is_strict(run_dir)
    targets = [p for p in [run_dir / _PHASE3_NAME] if p.is_file()]
    targets += sorted(run_dir.glob(_PHASE2_GLOB))
    checked = 0
    errors: list[str] = []
    warnings: list[str] = []
    for path in targets:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"{path}: 読めないため signal 検査を skip: {exc}")
            continue
        if not isinstance(data, dict) or not isinstance(data.get("paradigm_findings"), list):
            continue
        checked += 1
        for paradigm in data["paradigm_findings"]:
            if not isinstance(paradigm, dict):
                continue
            paradigm_id = paradigm.get("paradigm_id")
            for index, issue in enumerate(paradigm.get("issues") or []):
                if not isinstance(issue, dict):
                    continue
                signal = issue.get("condition_signal")
                condition = issue.get("condition")
                if signal == "smell":
                    if condition is not None:
                        message = (
                            f"{path}: paradigm {paradigm_id} issue {index}: "
                            f"condition_signal=smell に 便宜値 condition={condition} が残っている"
                        )
                        (errors if strict else warnings).append(message)
                elif signal in signal_to_condition and condition != signal_to_condition[signal]:
                    message = (
                        f"{path}: paradigm {paradigm_id} issue {index}: condition={condition} と "
                        f"condition_signal={signal} が対応しない "
                        f"(期待 condition={signal_to_condition[signal]})"
                    )
                    (errors if strict else warnings).append(message)
    return checked, errors, warnings


def _load_verdict_deriver():
    """build-verdict.py の derive() を単一正本として読み込む。"""
    path = Path(__file__).with_name("build-verdict.py")
    spec = importlib.util.spec_from_file_location("_build_verdict", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_verdict_derivation(
    run_dir: Path,
    force_strict: bool = False,
) -> tuple[int, list[str], list[str]]:
    """verdict.json と findings.json からの決定論的導出値を照合する。"""
    findings_path = run_dir / _PHASE3_NAME
    verdict_path = run_dir / "verdict.json"
    if not (findings_path.is_file() and verdict_path.is_file()):
        return 0, [], []
    strict = force_strict or run_is_strict(run_dir)
    module = _load_verdict_deriver()
    if module is None:
        return 0, [], [f"{run_dir}: build-verdict.py を読み込めず verdict 検査を skip"]
    try:
        findings = json.loads(findings_path.read_text(encoding="utf-8"))
        existing = json.loads(verdict_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return 0, [], [f"{run_dir}: 読めないため verdict 検査を skip: {exc}"]
    if not isinstance(findings, dict) or not isinstance(existing, dict):
        return 0, [], []
    carried = {key: existing.get(key) for key in module.CARRIED_FIELDS}
    if not all(carried.get(key) for key in ("plugin", "skill", "scope_mode")):
        return 0, [], [f"{verdict_path}: 同定情報が無いため verdict 検査を skip"]
    derived = module.derive(findings, carried)
    errors: list[str] = []
    warnings: list[str] = []
    for key in _DERIVED_KEYS:
        if key in derived and existing.get(key) != derived[key]:
            message = (
                f"{verdict_path}: {key} が findings.json からの導出値と一致しない "
                f"(verdict={existing.get(key)!r} / 導出={derived[key]!r})。"
                "build-verdict.py で再生成すること"
            )
            (errors if strict else warnings).append(message)
    return 1, errors, warnings


def iter_run_dirs(base: Path):
    """base が run dir なら自身、tree なら elegant-review 配下の run を列挙する。"""
    if (base / _PHASE1_NAME).is_file() or any(base.glob(_PHASE2_GLOB)):
        yield base
        return
    for child in sorted(base.glob("**/elegant-review/*")):
        if child.is_dir():
            yield child


def check_phase_order_tree(
    base: Path,
    signal_to_condition: dict[str, str],
    strict_signal: bool = False,
) -> int:
    """Phase 順序、signal 対応、verdict 導出を tree 全体で検査する。"""
    ok = skipped = 0
    signal_checked = verdict_checked = strict_runs = 0
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for run_dir in iter_run_dirs(base):
        status, errors = check_phase_order(run_dir)
        if status == "skipped":
            skipped += 1
        elif status == "ok":
            ok += 1
        else:
            all_errors.extend(errors)
        checked, signal_errors, signal_warnings = check_signal_consistency(
            run_dir,
            signal_to_condition,
            force_strict=strict_signal,
        )
        signal_checked += checked
        if strict_signal or run_is_strict(run_dir):
            strict_runs += 1
        all_errors.extend(signal_errors)
        all_warnings.extend(signal_warnings)
        checked, verdict_errors, verdict_warnings = check_verdict_derivation(
            run_dir,
            force_strict=strict_signal,
        )
        verdict_checked += checked
        all_errors.extend(verdict_errors)
        all_warnings.extend(verdict_warnings)

    warning_head = 20
    for warning in all_warnings[:warning_head]:
        print(f"WARN: {warning}", file=sys.stderr)
    if len(all_warnings) > warning_head:
        print(
            f"WARN: ... 他 {len(all_warnings) - warning_head} 件 "
            f"(境界 {STRICT_SIGNAL_FROM} より前の run は WARN 止まり)",
            file=sys.stderr,
        )
    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        return 1
    print(
        f"OK: phase order verified for {ok} run(s), skipped {skipped} incomplete run(s); "
        f"signal consistency checked in {signal_checked} findings file(s), "
        f"verdict derivation checked in {verdict_checked} run(s) "
        f"({strict_runs} run(s) under strict mode, boundary={STRICT_SIGNAL_FROM}, "
        f"{len(all_warnings)} warning(s))"
    )
    return 0
