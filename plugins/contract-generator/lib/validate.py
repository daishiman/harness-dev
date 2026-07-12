#!/usr/bin/env python3
# /// script
# name: validate
# purpose: 差込前の決定論バリデーション(口座/日付/金額/必須非空)。
# inputs:
#   - row dict + template-mapping.json の type ブロック
# outputs:
#   - returns: (errors, warnings) / required_missing_columns
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: 差込前の決定論バリデーション。

口座番号7桁 / 口座種類 / 日付前後・形式 / 金額整数 / 必須非空 を検査。
required 列は template-mapping.json の各 field.required と condition から導出する。
"""

import re
import docx_fill

KANA_RE = re.compile(r"^[ｱ-ﾝﾞﾟァ-ヴーぁ-ゖ\s（）()／/.,，、・)A-Za-z0-9）]+$")
DATE_RE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")
PARTY_A_COLUMNS = {"甲名称", "甲住所", "甲代表者", "甲代表者役職", "甲代表者氏名"}


def _cond_ok(cond, row):
    """'成果物有無==あり' のような condition を評価。"""
    if not cond:
        return True
    if "==" in cond:
        col, val = [s.strip() for s in cond.split("==", 1)]
        return (row.get(col, "") or "").strip() == val
    return True


def validate_row(row, type_map):
    """type_map: template-mapping.json の individual/corporate ブロック。
    returns (errors:list[str], warnings:list[str])。"""
    errors, warnings = [], []

    # 必須非空(condition 充足時のみ)
    for f in type_map.get("fields", []):
        col = f["column"]
        if col in PARTY_A_COLUMNS:
            continue
        if f.get("required") and _cond_ok(f.get("condition"), row):
            if not (row.get(col, "") or "").strip():
                errors.append(f"必須列が空: {col}")

    # 条件分岐列は、値が mapping の選択肢に一致しないと [A/B] が無視されるため明示的に止める。
    allowed_by_col = {}
    for cond in type_map.get("conditionals", []):
        allowed_by_col.setdefault(cond["column"], set()).add(cond["when"])
    for col, allowed in docx_fill.CONDITIONAL_ALLOWED_VALUES.items():
        allowed_by_col.setdefault(col, set()).update(allowed)
    for col, allowed in allowed_by_col.items():
        raw = (row.get(col, "") or "").strip()
        if not raw:
            continue
        normalized = docx_fill.normalize_conditional_value(col, raw)
        if normalized not in allowed:
            errors.append(f"{col} は {sorted(allowed)} から選択: '{raw}'")

    # 口座番号
    acct = (row.get("振込先_口座番号", "") or "").strip()
    if acct and not re.fullmatch(r"\d{7}", acct):
        errors.append(f"口座番号は7桁半角数字: '{acct}'")

    # 口座種類
    kind = (row.get("振込先_口座種類", "") or "").strip()
    if kind and kind not in ("普通", "当座"):
        errors.append(f"口座種類は普通/当座: '{kind}'")

    # 口座名義フリガナ
    kana = (row.get("振込先_口座名義（フリガナ）", "") or "").strip()
    if kana and not KANA_RE.match(kana):
        warnings.append(f"口座名義(フリガナ)にカナ以外が含まれる可能性: '{kana}'")

    # 日付
    start = (row.get("契約開始日", "") or "").strip()
    end = (row.get("契約終了日", "") or "").strip()
    for label, v in (("契約開始日", start), ("契約終了日", end)):
        if v and not DATE_RE.match(v):
            errors.append(f"{label}は YYYY/MM/DD: '{v}'")
    if DATE_RE.match(start or "") and DATE_RE.match(end or ""):
        if _to_int_date(start) >= _to_int_date(end):
            errors.append(f"契約開始日 < 契約終了日 を満たさない: {start} >= {end}")

    # 金額
    amount = (row.get("金額", "") or "").strip().replace(",", "")
    if amount and not re.fullmatch(r"\d+", amount):
        errors.append(f"金額は半角整数: '{row.get('金額')}'")

    return errors, warnings


def _to_int_date(s):
    y, m, d = s.split("/")
    return int(y) * 10000 + int(m) * 100 + int(d)


def required_missing_columns(row, type_map):
    """欠損している必須列名のリスト(AskUserQuestion 補完対象の判定に使う)。"""
    out = []
    for f in type_map.get("fields", []):
        if f["column"] in PARTY_A_COLUMNS:
            continue
        if f.get("required") and _cond_ok(f.get("condition"), row):
            if not (row.get(f["column"], "") or "").strip():
                out.append(f["column"])
    # 重複除去(同一列が複数 field に現れる: 署名欄など)
    seen, uniq = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq
