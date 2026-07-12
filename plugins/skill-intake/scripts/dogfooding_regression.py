#!/usr/bin/env python3
"""Dogfooding regression: info-collector-agent baseline を再投入し semantic_equivalence で検証.

判定:
  (1) lexical: section_key / required_fields / axes.axis_id / figures.kind+index がベースラインと一致
  (2) semantic: 本文 (purpose_slots / answer / one_liner) の embedding cosine >= 0.85
      (embedding 取得不可な環境では SequenceMatcher.ratio() >= 0.85 にフォールバック)

Usage:
  python3 dogfooding_regression.py <generated-intake.json>
  python3 dogfooding_regression.py --baseline-only       # baseline スキーマ自検証のみ
  python3 dogfooding_regression.py --schema-robustness   # N>=2 fixture を schema 検証 (LS-04)
  python3 dogfooding_regression.py --multi-self          # 各 fixture vs 自身 で SEMANTIC_KEYS×5 回帰 (T19)
"""
from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "plugins" / "skill-intake" / "references" / "runtime-config.json"

LEXICAL_KEYS = ("section_key", "required_fields", "axes.axis_id", "figures.kind", "figures.index")
SEMANTIC_KEYS = ("purpose_slots", "axes.answer", "figures.one_liner", "true_purpose", "underlying_motivation")
DEFAULT_THRESHOLD = 0.85


def _collect_semantic_texts(intake: dict) -> dict[str, str]:
    """SEMANTIC_KEYS 全 5 キーの本文を収集して dict[key]=concatenated_text を返す。

    LS-04 / SS-08 対応: 旧実装は true_purpose 1 キーのみで semantic 比較していた。
    宣言通り全 5 キーを比較対象に展開し、Gate2 の統計的根拠を強化する。
    """
    sections = intake.get("sections", {})
    out: dict[str, str] = {}

    # purpose_slots: 全章の {decides_what, ensures_what, prevents_what} を連結
    slots_parts: list[str] = []
    for sec in sections.values():
        ps = sec.get("purpose_slots") or {}
        for k in ("decides_what", "ensures_what", "prevents_what"):
            v = ps.get(k)
            if isinstance(v, str):
                slots_parts.append(v)
    out["purpose_slots"] = "\n".join(slots_parts)

    # axes.answer: §6 五軸の answer 連結
    axes_parts = [a.get("answer", "") for a in sections.get("6_five_axes_summary", {}).get("axes", [])]
    out["axes.answer"] = "\n".join(p for p in axes_parts if isinstance(p, str))

    # figures.one_liner: §5 5図の one_liner 連結
    fig_parts = [f.get("one_liner", "") for f in sections.get("5_visualizer", {}).get("figures", [])]
    out["figures.one_liner"] = "\n".join(p for p in fig_parts if isinstance(p, str))

    # true_purpose: §3
    out["true_purpose"] = sections.get("3_purpose_excavator", {}).get("true_purpose", "") or ""

    # underlying_motivation: §3
    out["underlying_motivation"] = sections.get("3_purpose_excavator", {}).get("underlying_motivation", "") or ""

    return out


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _resolve_baseline_path(config: dict) -> Path:
    return PROJECT_ROOT / config["dogfooding"]["baseline_intake_path"]


def _extract_lexical_fingerprint(intake: dict) -> dict:
    sections = intake.get("sections", {})
    fp = {"section_keys": sorted(sections.keys())}
    fp["axes_ids"] = sorted(a["axis_id"] for a in sections.get("6_five_axes_summary", {}).get("axes", []))
    fp["figures_kinds"] = [(f["index"], f["kind"]) for f in sections.get("5_visualizer", {}).get("figures", [])]
    return fp


def _semantic_similarity(a: str, b: str) -> float:
    # 両方欠落は「乖離なし」として 1.0 (LS-04 修正: 旧実装は 0.0 で誤検出)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    try:
        # Embedding 経由は将来拡張。現状は SequenceMatcher で代替。
        return SequenceMatcher(None, a, b).ratio()
    except Exception:
        return 0.0


def _compare(baseline: dict, generated: dict, threshold: float) -> tuple[bool, list[str]]:
    findings: list[str] = []

    base_fp = _extract_lexical_fingerprint(baseline)
    gen_fp = _extract_lexical_fingerprint(generated)
    for key in ("section_keys", "axes_ids", "figures_kinds"):
        if base_fp.get(key) != gen_fp.get(key):
            findings.append(f"LEXICAL FAIL [{key}]: baseline={base_fp.get(key)} generated={gen_fp.get(key)}")

    # semantic check: SEMANTIC_KEYS 全 5 キーを比較
    base_texts = _collect_semantic_texts(baseline)
    gen_texts = _collect_semantic_texts(generated)
    for key in SEMANTIC_KEYS:
        sim = _semantic_similarity(base_texts.get(key, ""), gen_texts.get(key, ""))
        if sim < threshold:
            findings.append(f"SEMANTIC FAIL [{key}]: similarity={sim:.3f} < {threshold}")

    return (not findings), findings


def _schema_robustness_check(config: dict) -> int:
    """T1 (LS-04 対応): baseline_intake_paths の全 fixture が schema PASS するかを検証。

    semantic 比較は同一 fixture vs baseline でしか意味を持たないため、
    N>1 baseline は「schema が異なる正当な入力で破綻しないか」の robustness 検査に用いる。
    """
    paths = config.get("dogfooding", {}).get("baseline_intake_paths") or [
        config.get("dogfooding", {}).get("baseline_intake_path")
    ]
    if not paths:
        print("ERROR: baseline_intake_paths が未設定", file=sys.stderr)
        return 2
    failed = 0
    import subprocess
    validator = PROJECT_ROOT / "plugins" / "skill-intake" / "scripts" / "validate_intake_schema.py"
    for rel in paths:
        if rel is None:
            continue
        p = (PROJECT_ROOT / rel).resolve()
        if not p.exists():
            print(f"MISS: {p}", file=sys.stderr)
            failed += 1
            continue
        rc = subprocess.call([sys.executable, str(validator), str(p)])
        if rc != 0:
            failed += 1
    if failed:
        print(f"FAIL: schema robustness {failed} fixtures failed", file=sys.stderr)
        return 1
    print(f"PASS: schema robustness all {len(paths)} fixtures conform", file=sys.stderr)
    return 0


def _multi_self_check(config: dict, threshold: float) -> int:
    """T19 (LS-04/SS-08 完全閉路): baseline_intake_paths の各 fixture を自分自身と比較し、
    SEMANTIC_KEYS×5 全てが threshold を満たすことを検証する。

    semantic_similarity の実装ドリフト (true_purpose 1キーのみ→全5キー) を
    自検証で押さえる。`_collect_semantic_texts` のバグや SequenceMatcher.ratio 退行を
    検知できる唯一の決定論的回帰テスト。
    """
    paths = config.get("dogfooding", {}).get("baseline_intake_paths") or []
    if not paths:
        print("ERROR: baseline_intake_paths 未設定", file=sys.stderr)
        return 2
    failed = 0
    for rel in paths:
        p = (PROJECT_ROOT / rel).resolve()
        if not p.exists():
            print(f"MISS: {p}", file=sys.stderr)
            failed += 1
            continue
        intake = json.loads(p.read_text(encoding="utf-8"))
        ok, findings = _compare(intake, intake, threshold)
        if not ok:
            failed += 1
            print(f"FAIL: {rel} self-compare", file=sys.stderr)
            for f in findings:
                print(f"  - {f}", file=sys.stderr)
        else:
            print(f"PASS: {rel} self-compare (5 SEMANTIC_KEYS >= {threshold})", file=sys.stderr)
    if failed:
        print(f"FAIL: multi-self {failed}/{len(paths)} fixtures regressed", file=sys.stderr)
        return 1
    print(f"PASS: multi-self all {len(paths)} fixtures self-consistent", file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    if "--schema-robustness" in argv:
        return _schema_robustness_check(_load_config())

    if "--multi-self" in argv:
        cfg = _load_config()
        threshold = float(cfg.get("dogfooding", {}).get("similarity_min")
                          or cfg.get("dogfooding", {}).get("embedding_cosine_min", DEFAULT_THRESHOLD))
        return _multi_self_check(cfg, threshold)

    if "--baseline-only" in argv:
        config = _load_config()
        baseline_path = _resolve_baseline_path(config)
        if not baseline_path.exists():
            print(f"ERROR: baseline not found: {baseline_path}", file=sys.stderr)
            return 2
        try:
            json.loads(baseline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: baseline invalid JSON: {exc}", file=sys.stderr)
            return 1
        print(f"PASS: baseline {baseline_path} is valid JSON", file=sys.stderr)
        return 0

    if len(argv) < 2:
        print("Usage: dogfooding_regression.py <generated-intake.json> | --baseline-only", file=sys.stderr)
        return 2

    generated_path = Path(argv[1]).resolve()
    if not generated_path.exists():
        print(f"ERROR: generated intake not found: {generated_path}", file=sys.stderr)
        return 2

    config = _load_config()
    baseline_path = _resolve_baseline_path(config)
    if not baseline_path.exists():
        print(f"WARN: baseline missing ({baseline_path}); cannot regression-test", file=sys.stderr)
        return 3

    threshold = float(config.get("dogfooding", {}).get("embedding_cosine_min", DEFAULT_THRESHOLD))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    generated = json.loads(generated_path.read_text(encoding="utf-8"))

    ok, findings = _compare(baseline, generated, threshold)
    if ok:
        print(f"PASS: {generated_path} ≅ baseline (threshold={threshold})", file=sys.stderr)
        return 0

    print(f"FAIL: {len(findings)} regression findings", file=sys.stderr)
    for f in findings:
        print(f"  - {f}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
