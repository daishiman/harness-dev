#!/usr/bin/env python3
# /// script
# name: check-generative-fidelity
# purpose: 生成された plan 本文の「生成時品質 (layer A)」を機械検出する自己検査 script。全 lint 緑でも中身が汎用フォールバックのまま/曖昧語だらけな「緑のパラドクス」plan を弾く。phase 本文 8 節と inventory の goal/checklist/criterion 文字列を走査し、(C6) 曖昧語 denylist の部分一致 (自己言及/反例/コード span は ignored_context へ分類) と (C7) skeleton プレースホルダ (_PHASE_SECTION_HINT) の未カスタマイズ完全一致を検出する。
# inputs:
#   - argv: <plan-dir> | --self-test
# outputs:
#   - stdout: 構造化 JSON (denylist_violations / uncustomized_sections / ignored_context)
#   - stderr: 検出サマリ
#   - exit: 0=violation/未カスタマイズ 0 件 / 1=1 件以上 / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""生成時品質 (layer A・C6/C7) を機械検出する自己検査 script。

決定論ゲート (R4 verdict) ではなく criteria 自己検査に属する: 全機械ゲートが緑でも
「purpose 未達の空プラグイン」を生む plan (汎用フォールバック放置・曖昧語だらけ) を
表層で捕まえる。意味の正否 (曖昧箇所が下流実行を実際に妨げるか) は evaluator の
genuine 意味判定 (C8) に残す二層分離であり、本 script は Goodhart 化しない範囲の
機械検出 (完全一致・部分一致) のみを担う。

  (C6) AMBIGUOUS_VOCAB_DENYLIST の 10 語が phase 本文/inventory prose に部分一致で
       現れたら denylist_violation として列挙する。ただし denylist 定義そのもの・
       コード/定数名 (バッククォート span)・「満たさない例」配下の否定例本文は
       ignored_context へ分類し exit 判定から除外する (自己誤検出の防止)。
  (C7) phase 本文 8 節が specfm._PHASE_SECTION_HINT の汎用プレースホルダと strip 後
       完全一致 (== 生成サボり) していれば uncustomized_sections として列挙する。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# P02 で確定した曖昧語 denylist (10 語)。下流 builder AI が「具体的に何をするか」を
# 決められない汎用副詞・美辞。部分一致 (`word in text`) で検出する。
AMBIGUOUS_VOCAB_DENYLIST = (
    "適切に", "しっかり", "うまく", "品質を高める", "なるべく",
    "できるだけ", "効果的に", "柔軟に", "十分に", "必要に応じて",
)
# denylist 語を含んでいても exit 判定から除外する行マーカー (自己言及/反例/定義)。
# 「満たさない例」の否定例本文・denylist 定義行のみを対象にする。裸の「満たさない」は
# 通常のチェックリスト条件文 (例:「要件を満たさない場合は…」) まで巻き込み genuine 違反を
# 握り潰すため使わない (過検出抑止の副作用としての見逃しを避ける)。
_IGNORED_LINE_MARKERS = ("満たさない例", "DENYLIST", "denylist", "反例", "NG 例")
_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def detect_ambiguous_vocab(text: str) -> list[str]:
    """text に出現する denylist 語を denylist 定義順で列挙する (C6 の中核・純関数)。

    否定接頭辞「不」直前の出現 (不適切に/不十分に) はその語自体の曖昧さと意味が反転する
    ため曖昧語と見なさない。全出現が「不」直前のときだけ非該当にする (混在時は該当)。
    """
    hits: list[str] = []
    for w in AMBIGUOUS_VOCAB_DENYLIST:
        start = 0
        while True:
            i = text.find(w, start)
            if i == -1:
                break
            if not (i > 0 and text[i - 1] == "不"):
                hits.append(w)
                break
            start = i + 1
    return hits


def classify_denylist_context(location: str, line_text: str) -> str:
    """denylist 語を含む 1 行が "violation" か "ignored_context" かを分類する。

    denylist 定義行・「満たさない例」等の否定例本文は ignored_context (exit 対象外)。
    コード/定数名 (バッククォート span) は呼び出し側で事前 strip 済みを前提にするが、
    定義トークンや反例マーカーを含む行はここで包括的に除外する (二段防御)。
    """
    for marker in _IGNORED_LINE_MARKERS:
        if marker in line_text:
            return "ignored_context"
    return "violation"


def detect_uncustomized_sections(phase_body: dict[str, str]) -> list[str]:
    """phase 本文各節が _PHASE_SECTION_HINT の汎用プレースホルダと完全一致する節名を返す (C7)。

    strip 後 == 比較。生成器が skeleton の hint をそのまま残した「生成サボり」を検出する。
    hint に一文字でも domain purpose を足せば一致しなくなる (偽陽性を出さない)。
    """
    uncustomized: list[str] = []
    for sec, hint in specfm._PHASE_SECTION_HINT.items():
        body = phase_body.get(sec)
        if body is not None and body.strip() == hint.strip():
            uncustomized.append(sec)
    return uncustomized


def parse_phase_body(text: str) -> dict[str, str]:
    """phase 本文を {"## 見出し": 本文} へ分解する (specfm.phase_body_sections への薄い委譲)。"""
    return specfm.phase_body_sections(text)


def _scan_prose(loc: str, text: str, sink: dict, entry_base: dict) -> None:
    """1 本の prose を行単位で走査し denylist_violations / ignored_context へ振り分ける。"""
    for line in text.splitlines():
        stripped = _CODE_SPAN_RE.sub("", line)  # コード/定数名 span を除去
        hits = detect_ambiguous_vocab(stripped)
        if not hits:
            continue
        cls = classify_denylist_context(loc, line)
        bucket = "ignored_context" if cls == "ignored_context" else "denylist_violations"
        for word in hits:
            sink[bucket].append({**entry_base, "word": word, "line": line.strip()})


def scan_plan(plan_dir: Path) -> dict:
    """plan_dir の phase 本文 + inventory prose を走査し構造化結果を返す。"""
    result: dict = {"denylist_violations": [], "uncustomized_sections": [], "ignored_context": []}

    for pf in sorted(plan_dir.glob("phase-*.md")):
        try:
            body = parse_phase_body(pf.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue  # 読取不能/非 UTF-8 は fail-soft でスキップ (品質検査を巻き込み crash させない)
        for sec in detect_uncustomized_sections(body):
            result["uncustomized_sections"].append({"file": pf.name, "section": sec})
        for sec, sec_body in body.items():
            _scan_prose(sec, sec_body, result, {"file": pf.name, "section": sec})

    inv = plan_dir / "component-inventory.json"
    if inv.is_file():
        try:
            data = json.loads(inv.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            data = {}
        comps = data.get("components") if isinstance(data, dict) else None
        for comp in comps if isinstance(comps, list) else []:
            if not isinstance(comp, dict):
                continue
            cid = str(comp.get("id", "")).strip()
            proses: list[tuple[str, str]] = []
            if isinstance(comp.get("goal"), str):
                proses.append(("goal", comp["goal"]))
            for i, item in enumerate(comp.get("checklist") or []):
                if isinstance(item, str):
                    proses.append((f"checklist[{i}]", item))
            fc = comp.get("feedback_contract")
            if isinstance(fc, dict):
                for i, cr in enumerate(fc.get("criteria") or []):
                    if isinstance(cr, dict) and isinstance(cr.get("text"), str):
                        proses.append((f"criteria[{i}]", cr["text"]))
            for loc, prose in proses:
                _scan_prose(loc, prose, result, {"component": cid, "location": loc})
    return result


# ─────────────────────────── self-test (埋め込み最小 fixture) ───────────────────────────
def _self_test() -> tuple[int, list[str]]:
    """C6 (denylist 検出 + ignored 分類) / C7 (完全一致検出) を埋め込み fixture で固定する。"""
    msgs: list[str] = []

    if "適切に" not in detect_ambiguous_vocab("これを適切に処理する"):
        msgs.append("(C6) detect_ambiguous_vocab が denylist 語を拾えない")
    if detect_ambiguous_vocab("具体的な関数名 foo を明示的に呼ぶ"):
        msgs.append("(C6) 非該当 prose で誤検出")
    # 否定接頭辞「不」直前のみの出現 (不適切に/不十分に) は曖昧語と見なさない
    if detect_ambiguous_vocab("不適切に扱わないこと") or detect_ambiguous_vocab("テストが不十分にならないよう網羅する"):
        msgs.append("(C6) 否定接頭辞 (不適切に/不十分に) を曖昧語と誤検出")
    # 「満たさない場合」等の通常条件文の genuine 違反は握り潰さない (満たさない例 のみ ignored)
    if classify_denylist_context("## 完了チェックリスト", "要件を満たさない場合は適切にリトライする") != "violation":
        msgs.append("(C6) 通常の『満たさない場合』条件文を過剰に ignored 分類 (見逃し)")

    hint = specfm._PHASE_SECTION_HINT["## 目的"]
    if "## 目的" not in detect_uncustomized_sections({"## 目的": hint}):
        msgs.append("(C7) hint 完全一致節を未カスタマイズとして検出できない")
    if detect_uncustomized_sections({"## 目的": hint + " 実ドメインの到達状態"}):
        msgs.append("(C7) カスタマイズ済み節を誤検出")

    if classify_denylist_context("## 完了チェックリスト", "満たさない例: これを適切に実装する") != "ignored_context":
        msgs.append("(C6) 満たさない例 行を ignored_context 分類できない")
    if classify_denylist_context("## 目的", 'AMBIGUOUS_VOCAB_DENYLIST = ("適切に",)') != "ignored_context":
        msgs.append("(C6) DENYLIST 定義行を ignored_context 分類できない")
    if classify_denylist_context("## 目的", "これを適切に処理する") != "violation":
        msgs.append("(C6) prose の denylist 語を violation 分類できない")

    # コード span 内の denylist 語は _scan_prose で除去され violation にならない (偽陽性なし)
    sink: dict = {"denylist_violations": [], "uncustomized_sections": [], "ignored_context": []}
    _scan_prose("## 目的", "`適切に` はコード定数なので除外される", sink, {"file": "x"})
    if sink["denylist_violations"]:
        msgs.append("(C6) バッククォート span 内の denylist 語を誤検出")

    return (1 if msgs else 0), msgs


def run(plan_dir: Path) -> tuple[int, dict]:
    result = scan_plan(plan_dir)
    fail = len(result["denylist_violations"]) + len(result["uncustomized_sections"])
    return (1 if fail else 0), result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成時品質 (曖昧語 denylist + skeleton 未カスタマイズ) を検出する")
    ap.add_argument("plan_dir", nargs="?", help="plan ディレクトリ")
    ap.add_argument("--self-test", action="store_true", help="埋め込み fixture で C6/C7 検出を自己検査する")
    args = ap.parse_args(argv)

    if args.self_test:
        code, msgs = _self_test()
        if code == 0:
            sys.stdout.write("OK: check-generative-fidelity の C6/C7 検出が期待どおり\n")
            return 0
        for m in msgs:
            sys.stderr.write(m + "\n")
        return code

    if not args.plan_dir:
        sys.stderr.write("usage: check-generative-fidelity.py <plan-dir> | --self-test\n")
        return 2
    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2

    code, result = run(plan_dir)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if code == 0:
        sys.stderr.write(
            f"OK: 曖昧語 violation 0 件 / 未カスタマイズ節 0 件 "
            f"(ignored_context {len(result['ignored_context'])} 件は除外)\n"
        )
        return 0
    dv, uc = len(result["denylist_violations"]), len(result["uncustomized_sections"])
    sys.stderr.write(f"FAIL: 曖昧語 violation {dv} 件 / 未カスタマイズ節 {uc} 件\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
