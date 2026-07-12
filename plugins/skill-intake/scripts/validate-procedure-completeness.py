#!/usr/bin/env python3
# /// script
# name: validate-procedure-completeness
# purpose: interview.json/intake.json の procedure ブロック完全性 (mode 別) と、handoff 対象 as-is フィールドへの to-be 語彙混入 (contamination) を決定論判定する共有ゲート。run-intake-interview の Phase4 完了チェックと quality_gate.py 経由の Phase9 ゲートの双方から参照される。
# inputs:
#   - --interview: procedure ブロックを持つ interview.json または intake.json
#   - --patterns: to-be-vocabulary-patterns.md (contamination 語彙の正本, 任意)
# outputs:
#   - stdout: JSON {complete: bool, mode, missing: [...], contamination: {detected, fields, matched_terms}}
#   - exit 0: complete かつ contamination.detected=false / 1: incomplete または contamination / 2: usage
# contexts: [interview phase 4, finalize phase 9]
# network: false
# write-scope: none
# requires-python: ">=3.10"
# ///
"""procedure ブロックの完全性 (mode 別) と as-is フィールドの to-be 汚染を機械判定する。

完全性判定 (goal-spec C1/C2):
  mode=detailed          -> steps[] 各要素の action/input/output/tool/frequency が非空。
  mode=overview_fallback -> difficulty_flag=true かつ overview の 3 フィールド非空。

汚染判定 (goal-spec C7, contamination check):
  handoff 対象の as-is フィールド (procedure.steps[]/overview の各テキスト値と真の課題 content)
  に to-be 語彙が混入していないかを to-be-vocabulary-patterns.md の 3 層 (強/弱/当為) で走査する。
  強シグナルは単独出現で混入。弱シグナルは同一テキスト内で当為表現と共起する場合のみ混入とし、
  名詞的用法 (当為なし) は as-is 業務語彙として warn 記録のみで detected=false を維持する。
  raw 会話ログは検査対象外 (C01 が handoff 対象 as-is フィールドへ to-be 発話を保存しない前提)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PATTERNS = (
    SCRIPT_DIR.parent / "skills" / "run-intake-interview"
    / "references" / "to-be-vocabulary-patterns.md"
)

STEP_FIELDS = ["action", "input", "output", "tool", "frequency"]
OVERVIEW_FIELDS = ["step_count_estimate", "participants", "frequency"]

# フォールバック既定 (patterns md が読めない場合)。正本は to-be-vocabulary-patterns.md。
DEFAULT_STRONG = [
    "べきである", "べき", "すべき", "するべき", "した方がいい", "したほうがいい",
    "する方がいい", "した方が良い", "望ましい", "理想は", "理想的には", "本来は",
    "本来であれば", "より良い方法", "もっと良い", "もっと効率的", "改善案",
    "ベストプラクティス", "一般的には", "一般論では", "普通は", "通常は", "典型的には",
]
DEFAULT_WEAK = ["最適化", "効率化", "自動化", "改善", "強化", "合理化"]
DEFAULT_MODAL = [
    "すべき", "するべき", "べき", "した方", "したほう", "する方", "たほうがいい",
    "望ましい", "理想", "本来", "目指す", "目指し",
]


def parse_patterns(text: str) -> tuple[list[str], list[str], list[str]]:
    """to-be-vocabulary-patterns.md の 3 セクション見出し (## 強 / ## 弱 / ## 当為) 配下の
    箇条書き ('A / B / C') から strong/weak/modal 語を抽出する。説明括弧を含む行は除外。"""
    buckets: dict[str, list[str]] = {"strong": [], "weak": [], "modal": []}
    current: str | None = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            head = s[3:]
            if head.startswith("強"):
                current = "strong"
            elif head.startswith("弱"):
                current = "weak"
            elif head.startswith("当為"):
                current = "modal"
            else:
                current = None
            continue
        if current and s.startswith("- "):
            for w in s[2:].split("/"):
                w = w.strip()
                if w and "(" not in w and "（" not in w and "*" not in w:
                    buckets[current].append(w)
    strong = buckets["strong"] or DEFAULT_STRONG
    weak = buckets["weak"] or DEFAULT_WEAK
    modal = buckets["modal"] or DEFAULT_MODAL
    return strong, weak, modal


def extract_procedure(data):
    """interview.json トップレベル procedure / intake.json sections.6.procedure の両対応。"""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("procedure"), dict):
        return data["procedure"]
    sections = data.get("sections")
    if isinstance(sections, dict):
        six = sections.get("6_five_axes_summary")
        if isinstance(six, dict) and isinstance(six.get("procedure"), dict):
            return six["procedure"]
    return None


def extract_true_problem(data):
    """真の課題 content を interview.json (five_axes.rows) / intake.json (sections.6.axes) から取り出す。"""
    if not isinstance(data, dict):
        return None
    fa = data.get("five_axes")
    if isinstance(fa, dict) and isinstance(fa.get("rows"), list):
        for row in fa["rows"]:
            if isinstance(row, dict) and str(row.get("name", "")).strip() == "真の課題":
                c = row.get("content")
                if isinstance(c, str):
                    return c
    sections = data.get("sections")
    if isinstance(sections, dict):
        six = sections.get("6_five_axes_summary")
        if isinstance(six, dict) and isinstance(six.get("axes"), list):
            for ax in six["axes"]:
                if isinstance(ax, dict) and str(ax.get("axis_id", "")).strip() == "real_problem":
                    a = ax.get("answer")
                    if isinstance(a, str):
                        return a
    return None


def check_completeness(procedure) -> tuple[bool, object, list[str]]:
    """procedure ブロックの mode 別完全性を判定し (complete, mode, missing) を返す。"""
    if not isinstance(procedure, dict):
        return False, None, ["procedure ブロックが存在しない"]
    mode = procedure.get("mode")
    if mode not in ("detailed", "overview_fallback"):
        return False, mode, [f"mode が detailed/overview_fallback でない: {mode!r}"]
    missing: list[str] = []
    if mode == "detailed":
        steps = procedure.get("steps")
        if not isinstance(steps, list) or not steps:
            missing.append("steps: 非空配列が必要")
        else:
            for i, st in enumerate(steps):
                if not isinstance(st, dict):
                    missing.append(f"steps[{i}]: object でない")
                    continue
                for fld in STEP_FIELDS:
                    v = st.get(fld)
                    if not isinstance(v, str) or not v.strip():
                        missing.append(f"steps[{i}].{fld}: 非空文字列が必要")
    else:  # overview_fallback
        if procedure.get("difficulty_flag") is not True:
            missing.append("difficulty_flag: true が必要")
        ov = procedure.get("overview")
        if not isinstance(ov, dict):
            missing.append("overview: object が必要")
        else:
            for fld in OVERVIEW_FIELDS:
                v = ov.get(fld)
                if not isinstance(v, str) or not v.strip():
                    missing.append(f"overview.{fld}: 非空文字列が必要")
    return (len(missing) == 0), mode, missing


def _as_is_texts(data, procedure) -> dict[str, str]:
    """contamination 検査対象の as-is テキストを {path: text} で返す。"""
    texts: dict[str, str] = {}
    if isinstance(procedure, dict):
        steps = procedure.get("steps")
        if isinstance(steps, list):
            for i, st in enumerate(steps):
                if isinstance(st, dict):
                    for fld in STEP_FIELDS:
                        v = st.get(fld)
                        if isinstance(v, str) and v.strip():
                            texts[f"procedure.steps[{i}].{fld}"] = v
        ov = procedure.get("overview")
        if isinstance(ov, dict):
            for fld in OVERVIEW_FIELDS:
                v = ov.get(fld)
                if isinstance(v, str) and v.strip():
                    texts[f"procedure.overview.{fld}"] = v
    tp = extract_true_problem(data)
    if isinstance(tp, str) and tp.strip():
        texts["five_axes.真の課題.content"] = tp
    return texts


def check_contamination(texts: dict[str, str], strong, weak, modal) -> dict:
    """as-is テキスト群に to-be 語彙が混入していないか走査する。
    強シグナルは単独一致で混入。弱シグナルは当為表現との共起時のみ混入。名詞的用法は warn のみ。"""
    detected = False
    fields: list[str] = []
    matched: list[str] = []
    for path, text in texts.items():
        hits: list[str] = []
        for w in strong:
            if w and w in text:
                hits.append(w)
        has_modal = any(m and m in text for m in modal)
        nominal: list[str] = []
        for w in weak:
            if w and w in text:
                if has_modal:
                    hits.append(w)
                else:
                    nominal.append(w)
        if hits:
            detected = True
            fields.append(path)
            for w in hits:
                if w not in matched:
                    matched.append(w)
        elif nominal:
            fields.append(f"{path} (warn: 名詞的用法 {'/'.join(dict.fromkeys(nominal))})")
    return {"detected": detected, "fields": fields, "matched_terms": matched}


def run(data, patterns_text: str) -> dict:
    procedure = extract_procedure(data)
    complete, mode, missing = check_completeness(procedure)
    strong, weak, modal = parse_patterns(patterns_text)
    texts = _as_is_texts(data, procedure)
    contamination = check_contamination(texts, strong, weak, modal)
    return {"complete": complete, "mode": mode, "missing": missing,
            "contamination": contamination}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="validate-procedure-completeness.py",
        description="procedure 完全性 + as-is フィールドの to-be 汚染を判定する")
    ap.add_argument("--interview", required=True,
                    help="procedure ブロックを持つ interview.json または intake.json")
    ap.add_argument("--patterns", default=str(DEFAULT_PATTERNS),
                    help="to-be-vocabulary-patterns.md (任意)")
    args = ap.parse_args(argv)

    try:
        data = json.loads(Path(args.interview).read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"input error: {e}\n")
        return 2

    try:
        patterns_text = Path(args.patterns).read_text(encoding="utf-8")
    except Exception:
        patterns_text = ""  # フォールバック既定 (DEFAULT_*) を使う

    res = run(data, patterns_text)
    sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
    ok = res["complete"] and not res["contamination"]["detected"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
