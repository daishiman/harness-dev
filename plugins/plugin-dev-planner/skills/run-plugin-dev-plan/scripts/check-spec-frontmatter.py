#!/usr/bin/env python3
# /// script
# name: check-spec-frontmatter
# purpose: 各 phase ファイル frontmatter が PHASE_REQUIRED(enum/型/prev-next 連鎖) を満たし、component-inventory.json の各 component が component_kind 別構造契約(specfm.validate_inventory_component)を満たすかを検証する決定論ゲート。
# inputs:
#   - argv: <phase.md ...> | --specs-dir DIR [--inventory FILE]
# outputs:
#   - stdout: OK サマリ
#   - stderr: phase frontmatter / component 構造 / criteria violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""phase ファイル frontmatter + inventory component を検証する。

per-phase 転換 (凍結契約 §2/§4/§8/§13-C2/C3):
  - phase frontmatter: PHASE_REQUIRED 全キー・id∈PHASE_ID_RE・phase_number(1-13)↔id 整合・
    phase_name/category/gate_type が §1 表と一致・status enum・prev/next 連鎖 (prev=n-1,next=n+1)・
    entities_covered は list・applicability{applicable:bool, false なら reason 非空}。
  - inventory component: specfm.validate_inventory_component (component_kind 別構造 +
    builder/build_kind 整合 + skill loop の criteria purpose-traceability + gates/harness 値域)。

旧 C*.md 走査 (per-component frontmatter 検証) は廃止。quality_gates 中身の深掘りは
check-spec-gates.py が担う (本 lint は phase 連鎖と component 構造契約を担う)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def check_phase(text: str) -> list[str]:
    """phase ファイル 1 件の frontmatter を検査し errors を返す。"""
    if specfm.split_frontmatter(text) is None:
        return ["frontmatter (--- ブロック) が無い"]
    fm = specfm.parse_frontmatter(text)
    errs: list[str] = []

    missing = [k for k in specfm.PHASE_REQUIRED if k not in fm]
    if missing:
        errs.append(f"phase frontmatter 必須キー欠落: {missing}")

    pid = str(fm.get("id", "")).strip()
    if not specfm.PHASE_ID_RE.match(pid):
        errs.append(f"id={pid!r} が PHASE_ID_RE (^P(0[1-9]|1[0-3])$) に不一致")

    pn = specfm.as_int(fm.get("phase_number"))
    if pn is None or not (1 <= pn <= 13):
        errs.append(f"phase_number={fm.get('phase_number')!r} は 1..13 の int であること")
        pn = None
    elif pid and pid != specfm.phase_id(pn):
        errs.append(f"id={pid} と phase_number={pn} が不整合 (期待 id={specfm.phase_id(pn)})")

    name = str(fm.get("phase_name", "")).strip()
    if name not in specfm.PHASE_NAMES:
        errs.append(f"phase_name={name!r} が enum 外 {list(specfm.PHASE_NAMES)}")
    elif pn is not None and name != specfm.PHASE_NAMES[pn - 1]:
        errs.append(f"phase_name={name!r} が phase_number={pn} と不整合 (期待 {specfm.PHASE_NAMES[pn - 1]!r})")

    if name in specfm.PHASE_CATEGORY:
        cat = str(fm.get("category", "")).strip()
        if cat != specfm.PHASE_CATEGORY[name]:
            errs.append(f"category={cat!r} が phase_name={name} と不整合 (期待 {specfm.PHASE_CATEGORY[name]!r})")

    gt = str(fm.get("gate_type", "")).strip()
    if gt not in specfm.GATE_TYPES:
        errs.append(f"gate_type={gt!r} が enum 外 {sorted(specfm.GATE_TYPES)}")
    elif name in specfm.PHASE_GATE_TYPE and gt != specfm.PHASE_GATE_TYPE[name]:
        errs.append(f"gate_type={gt!r} が phase_name={name} と不整合 (期待 {specfm.PHASE_GATE_TYPE[name]!r})")

    status = str(fm.get("status", "")).strip()
    if status not in specfm.PHASE_STATUS:
        errs.append(f"status={status!r} が enum 外 {sorted(specfm.PHASE_STATUS)}")

    if pn is not None:
        prev = specfm.as_int(fm.get("prev_phase"))
        if prev is None or prev != pn - 1:
            errs.append(f"prev_phase={fm.get('prev_phase')!r} は {pn - 1} であること (P01 は 0)")
        nxt = specfm.as_int(fm.get("next_phase"))
        if nxt is None or nxt != pn + 1:
            errs.append(f"next_phase={fm.get('next_phase')!r} は {pn + 1} であること (P13 は 14)")

    ec = fm.get("entities_covered")
    if not isinstance(ec, list):
        errs.append(f"entities_covered が list でない (該当なければ [])")

    ap = fm.get("applicability")
    if not isinstance(ap, dict):
        errs.append("applicability が object でない (applicable/reason を持つこと)")
    else:
        applicable = ap.get("applicable")
        if not isinstance(applicable, bool):
            errs.append(f"applicability.applicable が bool でない (現値 {applicable!r})")
        elif applicable is False and not str(ap.get("reason", "")).strip():
            errs.append("applicability.applicable=false のとき reason は非空必須")
    return errs


def expected_phase_filename(phase_number: int) -> str:
    if not (1 <= phase_number <= 13):
        raise ValueError(f"phase_number は 1..13 の範囲 (現値 {phase_number!r})")
    return f"phase-{phase_number:02d}-{specfm.PHASE_NAMES[phase_number - 1]}.md"


def collect_phase_files(specs_dir: Path) -> list[Path]:
    """契約上の phase-NN-<kebab>.md だけを収集する。余分な md は run() で検査する。"""
    return [specs_dir / expected_phase_filename(n) for n in range(1, 14)]


def check_phase_file_contract(paths: list[Path]) -> list[str]:
    """phase ファイル名と id の重複を検査する。"""
    errors: list[str] = []
    seen: dict[str, str] = {}
    for p in paths:
        if not p.is_file():
            continue
        fm = specfm.parse_frontmatter(p.read_text(encoding="utf-8"))
        pid = str(fm.get("id", "")).strip()
        pn = specfm.as_int(fm.get("phase_number"))
        if pn is not None and 1 <= pn <= 13:
            expected = expected_phase_filename(pn)
            if p.name != expected:
                errors.append(f"{p.name}: phase ファイル名不一致 (期待 {expected})")
        if pid:
            if pid in seen:
                errors.append(f"{p.name}: phase id 重複 {pid} ({seen[pid]} と重複)")
            seen[pid] = p.name
    return errors


def check_inventory(inventory_path: Path) -> tuple[list[str], str | None]:
    """component-inventory.json の各 component を検証する (errors, fatal_message)。"""
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], f"component-inventory JSON parse error: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return [], "component-inventory.json に components[] list が無い"
    errors: list[str] = []
    for comp in data["components"]:
        if not isinstance(comp, dict):
            errors.append("inventory: component が object でない")
            continue
        errors.extend(f"inventory: {e}" for e in specfm.validate_inventory_component(comp))
    return errors, None


def run(phase_paths: list[Path], inventory_path: Path | None) -> tuple[int, list[str]]:
    errors: list[str] = []
    errors.extend(check_phase_file_contract(phase_paths))
    for p in phase_paths:
        for e in check_phase(p.read_text(encoding="utf-8")):
            errors.append(f"{p.name}: {e}")
    if inventory_path is not None and inventory_path.is_file():
        inv_errors, fatal = check_inventory(inventory_path)
        if fatal:
            return 2, [fatal]
        errors.extend(inv_errors)
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="phase frontmatter + inventory component を検証する")
    ap.add_argument("specs", nargs="*", help="phase ファイル .md")
    ap.add_argument("--specs-dir", default=None, help="phase ファイルのディレクトリ")
    ap.add_argument("--inventory", default=None, help="component-inventory.json (既定 <specs-dir>/component-inventory.json)")
    args = ap.parse_args(argv)

    paths: list[Path] = [Path(s) for s in args.specs]
    inventory_path: Path | None = Path(args.inventory) if args.inventory else None
    if args.specs_dir:
        d = Path(args.specs_dir)
        if not d.is_dir():
            sys.stderr.write(f"not a directory: {d}\n")
            return 2
        paths.extend(collect_phase_files(d))
        if inventory_path is None:
            inventory_path = d / "component-inventory.json"
    if not paths:
        sys.stderr.write("usage: check-spec-frontmatter.py <phase.md ...> | --specs-dir DIR\n")
        return 2
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            sys.stderr.write(f"not found: {p}\n")
        return 2
    # --inventory 明示時はファイル実在を必須にする (defaulted で不在なら他ゲートに委ねスキップ)。
    if args.inventory and not inventory_path.is_file():
        sys.stderr.write(f"inventory not found: {inventory_path}\n")
        return 2
    code, errors = run(paths, inventory_path)
    if code == 2:
        for e in errors:
            sys.stderr.write(e + "\n")
        return 2
    if code == 0:
        sys.stdout.write(f"OK: {len(paths)} phase frontmatter + inventory component 契約を充足\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
