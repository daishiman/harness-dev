#!/usr/bin/env python3
# /// script
# name: lint-rubric-violation
# version: 0.3.0
# purpose: eval-log/*.jsonl を読み、連続 N release × 違反率 M% 超を検出して trigger.json を出力する（27章§3.2 正本）
# inputs:
#   - --log-dir: eval-log ディレクトリのパス
#   - --n: 連続 release 数（既定 3、1 以上）
#   - --threshold: 違反率閾値（既定 0.20、0 以上 1 未満）
#   - --out: 出力 trigger.json のパス（親ディレクトリが無ければ作る）
#   - --bootstrap-threshold: bootstrap 判定件数（既定 20、0 以上。未満なら exit 3 + warning）
# outputs:
#   - file: trigger.json （breached / n / threshold / bootstrap / total_records / skipped_lines）
#   - exit: 0=招集不要 / 2=招集必要 / 3=bootstrap中（--log-dir が無いときを含む）/ 1=trigger.json を書けない
#     引数の誤りは argparse が usage を出して 2 で止まり、trigger.json は書かない
# requires-python: ">=3.9"
# dependencies: []
# contexts: [E, C]
# network: false
# write-scope: output-dir
# ///
"""eval-log 違反率を時系列で集計し governance トリガーを判定する。

違反率の定義（27章§3.1「findings[].passed: false を母数で割る」）:
  release R の rule X の違反率 = R のレコードのうち X に違反したレコードの数 ÷ R のレコードの数
  - 評価器（render-findings-score.py）の findings は違反した rule だけを並べ、passed を持たない。
    passed が無い finding は違反として数え、passed: true の finding だけを合格として除く。
  - 1つのレコードに同じ rule の finding が複数あっても、そのレコードの違反は1回と数える。
  - rule X の finding が1件も無い release は、違反率 0 として系列に入れる（連続の判定を飛ばさない）。

release の並び順: 数字を含む release は数の順に並べる。`local` や `unknown`（release の無いレコード）の
ような数字を含まない release は、どの番号付き release よりも古いとみなす。eval-log は追記だけなので、
番号付きの release が入り始めた後も `local` のレコードは残る。それを最新として扱うと、本物の最新 release の
違反が連続の窓から押し出されて招集を見落とす。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def load(log_dir: Path, skipped: list | None = None):
    """score ログのレコードを返す。JSON でない行と object でない行は skipped に場所を積んで飛ばす。

    読めないファイル (UTF-8 でない・権限が無い) はファイルごと skipped に積んで飛ばす。
    """
    for p in sorted(log_dir.rglob("*-score.jsonl")):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            if skipped is not None:
                skipped.append(f"{p}: unreadable ({type(exc).__name__})")
            continue
        for no, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                rec = None
            if isinstance(rec, dict):
                yield rec
            elif skipped is not None:
                skipped.append(f"{p}:{no}")


def _is_violation(finding: dict) -> bool:
    return finding.get("passed") is not True


def _release_key(rel: str):
    """'2026.10.0' と '2026.9.0' を数の順に並べる（文字列の順だと 10 が 9 より前になる）。

    数字を含まない release（`local`・`unknown` など）は、番号付きの release より前（古い側）に置く。
    """
    tokens = [(0, int(t), "") if t.isdecimal() else (1, 0, t) for t in re.findall(r"\d+|\D+", rel)]
    return (re.search(r"\d", rel) is not None, tokens)


def _item_id(finding: dict) -> str:
    """finding の rule id を文字列で返す。文字列・整数以外（list や dict）は "?" にまとめる。"""
    item = finding.get("rubric_item_id") or finding.get("id")
    if isinstance(item, bool) or not isinstance(item, (str, int)):
        return "?"
    return str(item)


def compute(records):
    per_release: dict = defaultdict(int)
    violated: dict = defaultdict(int)
    items: set = set()
    total = 0
    for r in records:
        total += 1
        rel = str(r.get("release") or "unknown")
        per_release[rel] += 1
        hit = set()
        findings = r.get("findings")
        for f in findings if isinstance(findings, list) else []:
            if not isinstance(f, dict):
                continue
            item = _item_id(f)
            items.add(item)
            if _is_violation(f):
                hit.add(item)
        for item in hit:
            violated[(rel, item)] += 1
    releases = sorted(per_release, key=_release_key)
    by_item = {
        item: [(rel, violated[(rel, item)] / per_release[rel]) for rel in releases]
        for item in sorted(items)
    }
    return by_item, total


def detect(by_item, n: int, th: float):
    out = []
    for item, s in by_item.items():
        if len(s) >= n and all(rate > th for _, rate in s[-n:]):
            out.append({
                "rubric_item_id": item,
                "recent_releases": [r for r, _ in s[-n:]],
                "recent_rates": [v for _, v in s[-n:]],
            })
    return out


def _write(out: Path, result: dict) -> bool:
    """trigger.json を書く。親ディレクトリは作る。書けなければ理由を stderr に出して False。"""
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write {out}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", required=True)
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--threshold", type=float, default=0.20)
    p.add_argument("--out", required=True)
    p.add_argument("--bootstrap-threshold", type=int, default=20)
    a = p.parse_args()
    if a.n < 1:
        p.error("--n は 1 以上にする（0 以下だと連続の窓が系列全体になる）")
    if not 0 <= a.threshold < 1:
        p.error("--threshold は 0 以上 1 未満にする")
    if a.bootstrap_threshold < 0:
        p.error("--bootstrap-threshold は 0 以上にする")
    out = Path(a.out)

    log_dir = Path(a.log_dir)
    if not log_dir.is_dir():
        # eval-log がまだ無い repo は、記録が 0 件の bootstrap と同じ扱い (governance-policy.json の bootstrap)
        result = {"breached": [], "n": a.n, "threshold": a.threshold, "bootstrap": True, "warning": "log dir missing"}
        return 3 if _write(out, result) else 1

    skipped: list = []
    by_item, total = compute(list(load(log_dir, skipped)))
    if skipped:
        print(f"warning: skipped {len(skipped)} malformed score line(s): {', '.join(skipped[:5])}", file=sys.stderr)
    if total < a.bootstrap_threshold:
        result = {
            "breached": [],
            "n": a.n,
            "threshold": a.threshold,
            "bootstrap": True,
            "total_records": total,
            "bootstrap_threshold": a.bootstrap_threshold,
            "skipped_lines": skipped,
            "warning": f"bootstrap phase: {total}/{a.bootstrap_threshold} records",
        }
        return 3 if _write(out, result) else 1

    breached = detect(by_item, a.n, a.threshold)
    result = {
        "breached": breached,
        "n": a.n,
        "threshold": a.threshold,
        "bootstrap": False,
        "total_records": total,
        "skipped_lines": skipped,
    }
    if not _write(out, result):
        return 1
    return 0 if not breached else 2


if __name__ == "__main__":
    sys.exit(main())
