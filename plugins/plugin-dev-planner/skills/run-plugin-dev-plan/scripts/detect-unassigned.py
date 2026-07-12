#!/usr/bin/env python3
# /// script
# name: detect-unassigned
# purpose: 13 フェーズファイル(P01..P13)が全存在し §5 section 床(specfm.PHASE_BODY_SECTIONS=目的/背景/前提条件/ドメイン知識/成果物/スコープ外/完了チェックリスト/参照情報)を満たすこと、各 inventory component が >=1 phase の entities_covered に出現(orphan 防止)し build_target 非空であることを検証する決定論ゲート。
# inputs:
#   - argv: --inventory FILE --specs-dir DIR
# outputs:
#   - stdout: OK サマリ
#   - stderr: phase 欠落 / section 床欠落 / orphan component / build_target 欠落 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""13 フェーズの完全性・本文 section 床・component orphan/build_target を突合する。

per-phase 転換 (凍結契約 §5/§8/§13-C2):
  (a) 13 フェーズファイル (P01..P13) が全存在し、各ファイルが §5 section 床
      (specfm.PHASE_BODY_SECTIONS の全見出し + 各直後の非空本文) を満たす。宣言型の仕様書標準
      セクション = 目的/背景/前提条件/ドメイン知識/成果物/スコープ外/完了チェックリスト/参照情報
      (手続き的な実行タスクは宣言型方針ゆえ排除)。applicability.applicable == false の phase は
      section 床を免除する。
  (b) component-inventory.json の各 component が >=1 phase の entities_covered に出現する
      (orphan 防止) + build_target が非空 (L3 計画 → L4 実体化先の追跡)。

旧 spec-id 突合 (目録 id ↔ C*.md ファイル id) は廃止 (phase 軸へ全面転換)。
yaml は import しない。目録は component-inventory.json (object 形式)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# §5 phase 本文 section 契約 (床のみ機械強制・意味は下流トラスト)。宣言型の仕様書標準
# セクション集合は specfm.PHASE_BODY_SECTIONS を単一正本とする (目的/背景/前提条件/
# ドメイン知識/成果物/スコープ外/完了チェックリスト/参照情報)。
REQUIRED_SECTIONS = specfm.PHASE_BODY_SECTIONS


def expected_phase_filename(phase_number: int) -> str:
    """phase_number から契約上のファイル名 phase-NN-<kebab>.md を返す。"""
    if not (1 <= phase_number <= 13):
        raise ValueError(f"phase_number は 1..13 の範囲 (現値 {phase_number!r})")
    return f"phase-{phase_number:02d}-{specfm.PHASE_NAMES[phase_number - 1]}.md"


def collect_phase_files(specs_dir: Path) -> tuple[dict[str, tuple[Path, dict]], list[str]]:
    """specs_dir 配下 *.md (index/main を除く) を phase id -> (path, frontmatter) で収集する。"""
    out: dict[str, tuple[Path, dict]] = {}
    errors: list[str] = []
    for md in sorted(specs_dir.glob("*.md")):
        if md.stem in {"index", "main"}:
            continue
        fm = specfm.parse_frontmatter(md.read_text(encoding="utf-8"))
        pid = str(fm.get("id", "")).strip()
        if pid:
            if pid in out:
                errors.append(f"phase id 重複: {pid} ({out[pid][0].name} と {md.name})")
            out[pid] = (md, fm)
    return out, errors


def is_not_applicable(fm: dict) -> bool:
    """applicability.applicable == false (N/A phase) かを返す。"""
    ap = fm.get("applicability")
    return isinstance(ap, dict) and ap.get("applicable") is False


def load_inventory_components(text: str) -> list[dict]:
    """component-inventory.json (object 形式 {"components":[{..}]}) の component dict 一覧を返す。"""
    stripped = text.strip()
    if not stripped:
        return []
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("components"), list):
        return [c for c in data["components"] if isinstance(c, dict)]
    return []


def missing_sections(spec_text: str) -> list[str]:
    """必須 section 見出しの欠落を返す。"""
    return [sec for sec in REQUIRED_SECTIONS if sec not in spec_text]


def empty_body_sections(spec_text: str) -> list[str]:
    """必須 section 見出しは在るが直後の本文が空のもの (本文の床違反) を返す。"""
    lines = spec_text.splitlines()
    out: list[str] = []
    for sec in REQUIRED_SECTIONS:
        idx = next(
            (i for i, ln in enumerate(lines)
             if ln.strip() == sec or ln.strip().startswith(sec + " ")),
            None,
        )
        if idx is None:
            continue  # 見出し欠落は missing_sections の責務
        body: list[str] = []
        for ln in lines[idx + 1:]:
            if ln.startswith("## "):
                break
            body.append(ln)
        if not "".join(body).strip():
            out.append(sec)
    return out


def covered_entities(phase_files: dict[str, tuple[Path, dict]]) -> set[str]:
    """全 phase の entities_covered の和集合を返す (component orphan 判定用)。"""
    covered: set[str] = set()
    for _pid, (_path, fm) in phase_files.items():
        ec = fm.get("entities_covered")
        if isinstance(ec, list):
            for e in ec:
                token = str(e).strip()
                if token:
                    covered.add(token)
    return covered


def run(inventory_text: str, specs_dir: Path) -> tuple[int, list[str], list[str]]:
    """(exit_code, errors, warnings) を返す。"""
    errors: list[str] = []
    warnings: list[str] = []
    phase_files, collect_errors = collect_phase_files(specs_dir)
    errors.extend(collect_errors)
    expected_ids = [specfm.phase_id(n) for n in range(1, 14)]

    # (a) 13 フェーズファイル全存在 + 契約ファイル名一致
    for n, pid in enumerate(expected_ids, start=1):
        expected_name = expected_phase_filename(n)
        expected_path = specs_dir / expected_name
        if not expected_path.is_file():
            errors.append(f"phase ファイル欠落: {pid} ({expected_name})")
        if pid not in phase_files:
            errors.append(f"phase frontmatter 欠落: {pid} (13 フェーズ P01..P13 を全て備えること)")
            continue
        actual_path, _fm = phase_files[pid]
        if actual_path.name != expected_name:
            errors.append(f"{pid}: phase ファイル名不一致: {actual_path.name} (期待 {expected_name})")
    extra = sorted(set(phase_files) - set(expected_ids))
    for pid in extra:
        warnings.append(f"想定外の phase id: {pid} (P01..P13 以外・目録へ整合を確認)")

    # (a) section 床 (applicable な phase のみ・N/A phase は免除)
    for pid in expected_ids:
        entry = phase_files.get(pid)
        if entry is None:
            continue
        path, fm = entry
        if is_not_applicable(fm):
            continue  # §5: applicable:false は section 床免除
        text = path.read_text(encoding="utf-8")
        for sec in missing_sections(text):
            errors.append(f"{pid} ({path.name}): 必須 section 欠落 '{sec}'")
        for sec in empty_body_sections(text):
            errors.append(
                f"{pid} ({path.name}): 必須 section '{sec}' の本文が空 "
                f"(見出し直後に非空本文を要求・§5 本文の床)"
            )

    # (b) inventory component の orphan 防止 + build_target 非空
    components = load_inventory_components(inventory_text)
    if not components:
        return 2, ["component-inventory.json から components[] を抽出できない (object 形式で components を持つこと)"], warnings
    covered = covered_entities(phase_files)
    component_ids = {str(comp.get("id", "")).strip() for comp in components if str(comp.get("id", "")).strip()}
    for unknown in sorted(covered - component_ids):
        errors.append(
            f"unknown covered entity: {unknown} が component-inventory.json の components[].id に存在しない "
            f"(entities_covered は inventory component id のみ参照すること)"
        )
    for comp in components:
        cid = str(comp.get("id", "")).strip() or "?"
        if cid not in covered:
            errors.append(
                f"orphan component: {cid} がどの phase の entities_covered にも出現しない "
                f"(各 component は >=1 phase で参照されること・§5/§13-C2)"
            )
        if not str(comp.get("build_target", "")).strip():
            errors.append(
                f"build_target 欠落: component {cid} に L4 実体化先 (build_target) が無い "
                f"(計画 L3 と実体 L4 のトレーサビリティ)"
            )
    return (1 if errors else 0), errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="13 フェーズ完全性・section 床・component orphan/build_target を検証する")
    ap.add_argument("--inventory", required=True, help="component-inventory.json")
    ap.add_argument("--specs-dir", required=True, help="phase ファイルのディレクトリ")
    args = ap.parse_args(argv)

    inv = Path(args.inventory)
    specs_dir = Path(args.specs_dir)
    if not inv.is_file():
        sys.stderr.write(f"inventory not found: {inv}\n")
        return 2
    if not specs_dir.is_dir():
        sys.stderr.write(f"not a directory: {specs_dir}\n")
        return 2
    code, errors, warnings = run(inv.read_text(encoding="utf-8"), specs_dir)
    for w in warnings:
        sys.stderr.write(f"WARN: {w}\n")
    if code == 0:
        sys.stdout.write("OK: 13 フェーズ完全・section 床充足・orphan 0 件・全 component が build_target を保持\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
