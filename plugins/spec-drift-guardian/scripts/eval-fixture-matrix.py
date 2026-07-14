#!/usr/bin/env python3
# /// script
# name: eval-fixture-matrix
# purpose: C5 issue17-fixture-matrix / precision-recall ゲートの実測器。既知正解セット (tests/fixtures/issue17-matrix.json) の各 case を C09 map-field-impact.py に通し、写像規則の name/type/required/enum/semantics 判定の precision/recall を算出して fixture-matrix-result.json を書く。completion-evidence の自己申告ではなく実測でゲートを裏付ける。
# inputs:
#   - --fixture FILE 既知正解セット JSON {cases:[{case,expects_impact,expected_axes,hunks}]}
#   - --map-script FILE C09 map-field-impact.py のパス (既定は script 位置からの self-relative)
#   - --out FILE 実測結果 JSON の出力先
#   - --precision-min / --recall-min 閾値 (既定 0.8)
# outputs:
#   - --out に fixture-matrix-result.json / stdout に人可読サマリ
#   - exit: 0=全 case 一致かつ precision/recall>=閾値 / 1=未達 / 2=usage/IO
# contexts: [E]
# network: false
# write-scope: --out path only
# dependencies: []
# requires-python: ">=3.9"
# ///
"""既知正解セット (Issue #17 fixture matrix) に対する C09 写像規則の精度実測器。

各 case の hunks を map-field-impact.py に通して「実測 axis 集合」を得て、
fixture が宣言する「期待 axis 集合」と突合する。全 case の突合結果を軸レベルの
precision/recall に集計し、completion-evidence の issue17-fixture-matrix /
precision-recall ゲートが参照できる machine-readable artifact を出力する。

写像規則そのもの (どの行が何 axis か) は field-impact-map.json が持ち、本 script は
その規則の判定精度を「正解セットに対して」測るだけ。判定ロジックは C09 に閉じる。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_MAP_SCRIPT = Path(__file__).resolve().parent / "map-field-impact.py"
AXES = ("name", "type", "required", "enum", "semantics")


class EvalError(Exception):
    """exit 2 (usage/IO) を表す例外。"""


def measure_case(case: dict, map_script: Path) -> list[str]:
    """case の hunks を C09 に通し、実測された axis の集合 (sorted list) を返す。

    map-field-impact.py を subprocess で起動し stdout の影響候補配列から axis を集める。
    map が exit2 (構造不正) を返したら EvalError。変更行の無い hunk は影響 0 になる。
    """
    hunks = case.get("hunks", [])
    proc = subprocess.run(
        [sys.executable, str(map_script), "--stdin"],
        input=json.dumps(hunks),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 2:
        raise EvalError(f"map-field-impact usage/IO error for case {case.get('case')!r}: {proc.stderr.strip()}")
    impacts = json.loads(proc.stdout) if proc.stdout.strip() else []
    return sorted({i["axis"] for i in impacts})


def score_matrix(measured: list[dict], precision_min: float, recall_min: float) -> dict:
    """正解セットの実測結果を軸レベルの precision/recall へ集計する。

    引数 measured: 各要素は
      {"case": str, "expects_impact": bool,
       "expected_axes": list[str], "measured_axes": list[str]}
    戻り値 (dict) に最低限含めるキー:
      "precision", "recall" (float), "tp", "fp", "fn" (int),
      "per_case" (list[dict]: case ごとの tp/fp/fn と一致フラグ),
      "all_cases_match" (bool: 全 case で期待集合==実測集合),
      "meets_threshold" (bool: precision>=precision_min かつ recall>=recall_min)

    TODO(human): 軸レベル (case × axis のペア) で TP/FP/FN を数え、
      precision = TP / (TP + FP)、recall = TP / (TP + FN) を算出する。
      - TP: 期待にあり実測にもある (case, axis)
      - FP: 実測にあるが期待にない (case, axis) — 過検出 (no-impact case で軸が出たら FP)
      - FN: 期待にあるが実測にない (case, axis) — 見逃し
      - 分母が 0 になるケース (TP+FP==0 / TP+FN==0) の precision/recall をどう定義するか決める
        (慣例では「検出0かつ期待0なら 1.0」など)。
      per_case には case ごとの内訳と expected==measured の一致フラグを残す。
    """
    tp = fp = fn = 0
    per_case: list[dict] = []
    all_cases_match = True
    for m in measured:
        expected = set(m["expected_axes"])
        actual = set(m["measured_axes"])
        c_tp = len(expected & actual)
        c_fp = len(actual - expected)  # 過検出 (no-impact case で軸が出れば FP)
        c_fn = len(expected - actual)  # 見逃し
        tp += c_tp
        fp += c_fp
        fn += c_fn
        match = expected == actual
        all_cases_match = all_cases_match and match
        per_case.append(
            {
                "case": m["case"],
                "expects_impact": m["expects_impact"],
                "expected_axes": sorted(expected),
                "measured_axes": sorted(actual),
                "tp": c_tp,
                "fp": c_fp,
                "fn": c_fn,
                "match": match,
            }
        )
    # 分母 0 = 「検出すべきものが無く検出もしなかった」= 情報検索慣例で満点 (1.0)。
    precision = 1.0 if (tp + fp) == 0 else tp / (tp + fp)
    recall = 1.0 if (tp + fn) == 0 else tp / (tp + fn)
    meets_threshold = precision >= precision_min and recall >= recall_min
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "per_case": per_case,
        "all_cases_match": all_cases_match,
        "meets_threshold": meets_threshold,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Issue #17 fixture matrix に対する C09 写像精度の実測器")
    ap.add_argument("--fixture", required=True, help="既知正解セット JSON")
    ap.add_argument("--map-script", default=str(DEFAULT_MAP_SCRIPT), help="C09 map-field-impact.py のパス")
    ap.add_argument("--out", required=True, help="実測結果 JSON の出力先")
    ap.add_argument("--precision-min", type=float, default=0.8)
    ap.add_argument("--recall-min", type=float, default=0.8)
    args = ap.parse_args(argv)

    try:
        fixture_path = Path(args.fixture)
        if not fixture_path.is_file():
            raise EvalError(f"fixture not found: {fixture_path}")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        cases = fixture.get("cases")
        if not isinstance(cases, list) or not cases:
            raise EvalError("fixture.cases が非空 list でない")
        map_script = Path(args.map_script)
        if not map_script.is_file():
            raise EvalError(f"map-script not found: {map_script}")

        measured = []
        for case in cases:
            measured.append(
                {
                    "case": case.get("case"),
                    "expects_impact": bool(case.get("expects_impact")),
                    "expected_axes": sorted(case.get("expected_axes", [])),
                    "measured_axes": measure_case(case, map_script),
                }
            )
        score = score_matrix(measured, args.precision_min, args.recall_min)
    except EvalError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    result = {
        "schema_version": "1.0.0",
        "target_plugin_slug": "spec-drift-guardian",
        "fixture": str(fixture_path),
        "expected_fixture_cases": len(cases),
        "measured_fixture_cases": len(measured),
        "precision_min": args.precision_min,
        "recall_min": args.recall_min,
        "precision": score["precision"],
        "recall": score["recall"],
        "counts": {"tp": score["tp"], "fp": score["fp"], "fn": score["fn"]},
        "all_cases_match": score["all_cases_match"],
        "meets_threshold": score["meets_threshold"],
        "per_case": score["per_case"],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if (score["all_cases_match"] and score["meets_threshold"]) else "FAIL"
    sys.stdout.write(
        f"[{status}] cases={len(measured)} precision={score['precision']:.3f} "
        f"recall={score['recall']:.3f} all_match={score['all_cases_match']} -> {out_path}\n"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
