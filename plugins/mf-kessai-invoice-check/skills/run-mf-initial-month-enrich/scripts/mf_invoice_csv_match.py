#!/usr/bin/env python3
"""MFクラウド請求書の請求書一覧CSVから「真の初回請求月」を抽出し名寄せ検証する (API不要)。

MFクラウド請求書 UI の請求書一覧を CSV エクスポートし、本スクリプトに渡すと:
  - CSV を取引先名でグループ化し、最古の請求日(発行日)の YYYY-MM を算出
  - MF掛け払いの106顧客 (company_name) と会社名で名寄せ
  - マッチ率 / 2026-05より古い件数 / 最古月分布 / 名寄せ失敗社 を報告
  - 結果を mf-invoice-csv-match.json に保存 (Notion更新の入力にできる)

使い方:
  python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-initial-month-enrich/scripts/mf_invoice_csv_match.py" <エクスポートしたCSVのパス>

CSV のエンコーディング(utf-8-sig / cp932=Shift_JIS)と列名ゆれ(取引先名/請求日/発行日)は自動判定。
"""
import csv
import io
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 自ディレクトリ (mf_invoice_names)
from mf_invoice_names import norm  # 名寄せ正規化の単一正本 (enrich と共有)  # noqa: E402


def _eval_log_dir():
    """成果物の出力先を install パス非依存に解決する (check_invoice_gaps.py と同型)。
    優先順: MFK_OUTPUT_DIR > CLAUDE_PROJECT_DIR > CWD の <base>/eval-log/。"""
    base = os.environ.get("MFK_OUTPUT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(base, "eval-log")


EVAL_LOG = _eval_log_dir()
VERIFIED = os.path.join(EVAL_LOG, "mfk-gap-verified.json")  # 月次チェックの確定リスト (顧客名の源)


def read_csv(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("CSV のエンコーディングを判定できませんでした (utf-8/cp932 以外)")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise SystemExit("CSV に行がありません")
    return rows, list(rows[0].keys())


def pick_column(headers, candidates):
    """ヘッダから candidates の語を含む列名を返す (部分一致・最初の一致)。"""
    for cand in candidates:
        for h in headers:
            if cand in h:
                return h
    return None


def to_ym(s):
    if not s:
        return None
    s = s.strip().replace("/", "-").replace(".", "-")
    m = re.match(r"(\d{4})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    return None


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("使い方: python3 mf_invoice_csv_match.py <請求書一覧CSVのパス>\n")
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.stderr.write(f"CSV が見つかりません: {path}\n")
        return 2

    rows, headers = read_csv(path)
    print(f"CSV 読込: {len(rows)}行 / 列: {headers}\n")

    col_partner = pick_column(headers, ["取引先名", "取引先", "得意先", "顧客名", "宛名"])
    col_date = pick_column(headers, ["請求日", "発行日", "請求書発行日", "売上日", "日付"])
    if not col_partner or not col_date:
        sys.stderr.write(
            f"列の自動判定に失敗。取引先列={col_partner!r} 日付列={col_date!r}\n"
            f"  → ヘッダ {headers} を見て、正しい列名を教えてください(スクリプトを調整します)。\n")
        return 2
    print(f"使用列: 取引先='{col_partner}' / 日付='{col_date}'\n")

    # 取引先ごとに最古請求月
    oldest = {}   # norm_name -> (ym, raw_name, count)
    for r in rows:
        name = r.get(col_partner) or ""
        ym = to_ym(r.get(col_date) or "")
        if not name or not ym:
            continue
        k = norm(name)
        cur = oldest.get(k)
        if cur is None:
            oldest[k] = [ym, name, 1]
        else:
            cur[2] += 1
            if ym < cur[0]:
                cur[0] = ym
    print(f"CSV 内の取引先数(名寄せ後): {len(oldest)}社")

    # MF掛け払いの顧客と名寄せ (確定リストを fail-closed で要求: check_invoice_gaps.py と同型)
    if not os.path.exists(VERIFIED):
        sys.stderr.write(
            f"確定リスト {VERIFIED} が不在です。先に `run-mf-invoice-check` を "
            "collect→verify→finalize まで回して mfk-gap-verified.json を作成してください "
            "(これが名寄せ対象の顧客リスト源です)。\n")
        return 2
    customers = {}
    for r in json.load(open(VERIFIED, encoding="utf-8")):
        customers.setdefault(r["customer_id"], r.get("company_name", ""))

    matched, unmatched, results = [], [], []
    older = 0
    for cid, kname in customers.items():
        hit = oldest.get(norm(kname))
        if not hit:
            unmatched.append((cid, kname))
            continue
        ym, pname, cnt = hit
        results.append((cid, kname, pname, ym, cnt))
        matched.append(cid)
        if ym < "2026-05":
            older += 1

    print(f"\n=== 名寄せ結果 ===")
    print(f"名寄せ成功: {len(matched)}/{len(customers)}社  /  失敗: {len(unmatched)}社")
    print(f"最古請求月 < 2026-05 (掛け払いより遡れた): {older}社")
    print(f"最古請求月の分布: {dict(sorted(Counter(r[3] for r in results).items()))}")

    print("\n[マッチ サンプル: 古い順 上位20]")
    for cid, kname, pname, ym, cnt in sorted(results, key=lambda x: x[3])[:20]:
        tag = " ★掛け払いより古い" if ym < "2026-05" else ""
        print(f"  {ym}  件数{cnt:>3}  {kname} ⇔ {pname}{tag}")

    if unmatched:
        print(f"\n[名寄せ失敗 {len(unmatched)}社]")
        for cid, n in unmatched[:30]:
            print(f"  {n}  (cid={cid})")

    os.makedirs(EVAL_LOG, exist_ok=True)
    out = os.path.join(EVAL_LOG, "mf-invoice-csv-match.json")
    json.dump({
        "matched": len(matched), "unmatched": len(unmatched), "older_than_2026_05": older,
        "results": [{"customer_id": c, "kessai_name": k, "invoice_partner": p,
                     "oldest_billing_month": y, "invoice_count": n} for c, k, p, y, n in results],
        "unmatched_customers": [{"customer_id": c, "name": n} for c, n in unmatched],
    }, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
