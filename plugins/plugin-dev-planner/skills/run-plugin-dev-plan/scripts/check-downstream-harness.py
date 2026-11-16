#!/usr/bin/env python3
# /// script
# name: check-downstream-harness
# purpose: 生成 plan が「下流 builder AI への実行ハーネス (layer B)」として機能するかを機械検出する自己検査 script。各 phase の ## 完了チェックリスト に ### 受入例 (合否の具体像) と ### 事前解決済み判断 (分岐点の先回り解決) のサブ節が在ることを強制し、下流実行者の追加質問を構造的に減らす。判定行為中心の gate 系 phase (P03/P07/P09/P10) は縮小要件 (見出し存在のみ)、他 phase はフル要件 (見出し + 非空本文)。
# inputs:
#   - argv: <plan-dir> | --self-test
# outputs:
#   - stdout: OK サマリ
#   - stderr: 受入例/事前解決済み判断サブ節の欠落 violation (phase id 付き)
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""下流ハーネス (layer B・C10/C11) を機械検出する自己検査 script。

plan は生成物であると同時に後段 build skill (下流 builder AI) が消費する実行契約でもある。
全機械ゲートが緑でも、各 phase の完了判定が曖昧なままだと下流実行者が追加質問なしに着手
できず「緑だが実行不能」な plan を生む。本 script は各 phase の ## 完了チェックリスト に:

  (C10) ### 受入例        — 完了=達成の合否を分ける具体像 (満たす例/満たさない例)。
  (C11) ### 事前解決済み判断 — 実行中に生じうる分岐点を plan 段階で先回り解決した記録。

のサブ節が在ることを強制する。適用強度は phase 種別で非対称にする: 判定行為が中心の
gate 系 phase (REDUCED_REQUIREMENT_PHASES) は判定記録そのものが受入例的性質を持つため
見出しの存在のみを要求 (縮小形可)、他 phase は見出し + 非空本文まで要求する (フル要件)。
意味の実効性 (サブ節が本当に追加質問を防ぐか) は evaluator の genuine 判定 (C12) に残す。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# 判定行為が中心の gate 系 phase (P02 で確定した適用強度分類)。見出し存在のみ検査する。
REDUCED_REQUIREMENT_PHASES = ("P03", "P07", "P09", "P10")
CHECKLIST_SECTION = "## 完了チェックリスト"
# 各サブ節は (ラベル, 見出し prefix)。実 plan の見出しは `### 受入例 (満たす例 / 満たさない例)` の
# ように付記を伴うため exact でなく prefix (startswith) で照合する。
REQUIRED_SUBHEADINGS = (
    ("受入例", "### 受入例"),
    ("事前解決済み判断", "### 事前解決済み判断"),
)


def _heading_matches(heading: str, prefix: str) -> bool:
    """heading が prefix で始まり、直後が境界 (空白/括弧/行末) であれば True。

    `### 受入例` は `### 受入例 (満たす例…)` に一致するが `### 受入例外の扱い` (受入 *例外*)
    には一致しない (過剰 prefix 一致による偽充足=見逃しを防ぐ)。親 H2 見出しの付記許容
    (`## 完了チェックリスト (gate 合否)`) も同じ境界規則で受理する (子 prefix・親 exact の
    内部不整合を解消し detect-unassigned の末尾付記許容と揃える)。
    """
    if not heading.startswith(prefix):
        return False
    rest = heading[len(prefix):]
    return rest == "" or rest[0] in " \t　(("


def _section_body_by_prefix(sections: dict[str, str], prefix: str) -> str | None:
    """phase_body_sections の結果から prefix 境界一致する H2 節本文を返す (無ければ None)。"""
    for heading, body in sections.items():
        if _heading_matches(heading, prefix):
            return body
    return None


def _subheading_blocks(checklist_body: str) -> dict[str, list[str]]:
    """完了チェックリスト本文を {"### 見出し行": [直下の本文行...]} へ分解する。"""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in checklist_body.splitlines():
        if line.startswith("### "):
            current = line.strip()
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return blocks


def check_phase_downstream(text: str, phase_id: str) -> list[str]:
    """1 phase の完了チェックリストが受入例/事前解決済み判断サブ節契約を満たすか検査する。"""
    errors: list[str] = []
    checklist = _section_body_by_prefix(specfm.phase_body_sections(text), CHECKLIST_SECTION)
    if checklist is None:
        return [f"{phase_id}: {CHECKLIST_SECTION} 節が無い (下流ハーネス検査不能)"]
    blocks = _subheading_blocks(checklist)
    reduced = phase_id in REDUCED_REQUIREMENT_PHASES
    for label, prefix in REQUIRED_SUBHEADINGS:
        matched = [k for k in blocks if _heading_matches(k, prefix)]
        if not matched:
            errors.append(
                f"{phase_id}: {CHECKLIST_SECTION} に '{prefix}' サブ節が無い "
                f"({label}=下流実行者の追加質問を防ぐ実行契約)"
            )
            continue
        if not reduced:
            has_content = any(ln.strip() for k in matched for ln in blocks[k])
            if not has_content:
                errors.append(
                    f"{phase_id}: '{prefix}' 見出し直下に非空本文が無い "
                    "(フル要件 phase は具体本文まで必須・gate 系のみ縮小可)"
                )
    return errors


def _is_not_applicable(fm: dict) -> bool:
    """applicability.applicable == false (N/A phase) かを返す (detect-unassigned と同一規則)。"""
    ap = fm.get("applicability")
    return isinstance(ap, dict) and ap.get("applicable") is False


def run(plan_dir: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    phase_files = sorted(plan_dir.glob("phase-*.md"))
    if not phase_files:
        return 2, [f"phase-*.md が plan_dir に無い: {plan_dir}"]
    for pf in phase_files:
        try:
            text = pf.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{pf.name}: 読み取り不能 ({exc})")
            continue
        fm = specfm.parse_frontmatter(text)
        # N/A phase は detect-unassigned の §5 節床免除と同様、受入例/事前解決済み判断サブ節
        # 要件を免除する (該当なし宣言 phase に虚偽 violation を出さない=権威ゲートとの対称性)。
        if _is_not_applicable(fm):
            continue
        phase_id = str(fm.get("id", "")).strip() or pf.stem
        errors.extend(check_phase_downstream(text, phase_id))
    return (1 if errors else 0), errors


# ─────────────────────────── self-test (埋め込み最小 fixture) ───────────────────────────
def _phase_text(phase_id: str, checklist_body: str) -> str:
    return (
        f"---\nid: {phase_id}\nphase_number: 1\n---\n"
        f"# {phase_id} — sample\n\n{CHECKLIST_SECTION}\n{checklist_body}\n\n## 参照情報\n- x\n"
    )


def _self_test() -> tuple[int, list[str]]:
    """フル要件/縮小要件/欠落の各判定を埋め込み fixture で固定する。"""
    msgs: list[str] = []

    full = _phase_text("P01", (
        "- [ ] 項目A\n\n"
        "### 受入例 (満たす例 / 満たさない例)\n- 満たす例: X。\n- 満たさない例: Y。\n\n"
        "### 事前解決済み判断\n- 分岐点: Z → 判断: W。\n"
    ))
    if check_phase_downstream(full, "P01"):
        msgs.append(f"(C10/C11) フル要件を満たす phase を誤検出: {check_phase_downstream(full, 'P01')}")

    # フル要件 phase で受入例本文が空 → violation
    empty_body = _phase_text("P01", (
        "- [ ] 項目A\n\n### 受入例\n\n### 事前解決済み判断\n- 分岐: A→B。\n"
    ))
    if not any("受入例" in e and "非空本文" in e for e in check_phase_downstream(empty_body, "P01")):
        msgs.append("(C10) フル要件 phase の空受入例本文を検出できない")

    # 縮小要件 phase (P03) は見出しのみで通る (本文空でも可)
    reduced = _phase_text("P03", "- [ ] 判定記録。\n\n### 受入例\n\n### 事前解決済み判断\n")
    if check_phase_downstream(reduced, "P03"):
        msgs.append(f"(C10/C11) 縮小要件 phase を誤検出: {check_phase_downstream(reduced, 'P03')}")

    # サブ節そのものの欠落 → violation
    missing = _phase_text("P01", "- [ ] 項目のみ。受入例も事前解決も無い。\n")
    errs = check_phase_downstream(missing, "P01")
    if not any("受入例" in e and "サブ節が無い" in e for e in errs):
        msgs.append("(C10) 受入例サブ節の欠落を検出できない")
    if not any("事前解決済み判断" in e and "サブ節が無い" in e for e in errs):
        msgs.append("(C11) 事前解決済み判断サブ節の欠落を検出できない")

    # 完了チェックリスト節そのものの欠落
    no_checklist = "---\nid: P01\n---\n# P01\n\n## 目的\nx\n"
    if not any("下流ハーネス検査不能" in e for e in check_phase_downstream(no_checklist, "P01")):
        msgs.append("完了チェックリスト節欠落を検出できない")

    # 付記付き H2 見出し (## 完了チェックリスト (gate 合否)) を prefix 境界で受理する
    annotated = full.replace(CHECKLIST_SECTION, CHECKLIST_SECTION + " (gate 合否)")
    if check_phase_downstream(annotated, "P01"):
        msgs.append("付記付き H2 見出しを exact 照合で誤検出 (親 prefix 不一致)")

    # `### 受入例外の扱い` は `### 受入例` として偽充足しない (過剰 prefix 一致回避)
    overmatch = _phase_text("P01", (
        "- [ ] A。\n\n### 受入例外の扱い\n- 例外時の挙動。\n\n"
        "### 事前解決済み判断\n- 分岐: A→B。\n"
    ))
    if not any("受入例" in e and "サブ節が無い" in e for e in check_phase_downstream(overmatch, "P01")):
        msgs.append("`### 受入例外` を受入例サブ節として偽充足 (過剰一致)")

    return (1 if msgs else 0), msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="下流ハーネス (受入例/事前解決済み判断サブ節) を検証する")
    ap.add_argument("plan_dir", nargs="?", help="plan ディレクトリ")
    ap.add_argument("--self-test", action="store_true", help="埋め込み fixture で C10/C11 検出を自己検査する")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = _self_test()
        if code == 0:
            sys.stdout.write("OK: check-downstream-harness の C10/C11 検出が期待どおり\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    if not args.plan_dir:
        sys.stderr.write("usage: check-downstream-harness.py <plan-dir> | --self-test\n")
        return 2
    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2

    code, errors = run(plan_dir)
    if code == 0:
        sys.stdout.write("OK: 全 phase の完了チェックリストが受入例/事前解決済み判断サブ節契約を満たす\n")
        return 0
    if code == 2:
        for e in errors:
            sys.stderr.write(e + "\n")
        return 2
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
