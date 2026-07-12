#!/usr/bin/env python3
"""掛け払い顧客名 ↔ 請求書 partner 名の名寄せ正規化の単一正本。

enrich/csv_match 双方がここを import する。法人格(株式会社等)除去 + 全半角統一 +
空白除去 + 小文字化で、別 ID の会社名どうしを突合可能な正規化キーへ落とす。
重複定義(以前は mf_invoice_enrich.py / mf_invoice_csv_match.py に同じ実装が二重に
存在)を解消するための共有モジュール。
"""
import re

_SUFFIX = re.compile(r"(株式会社|有限会社|合同会社|合資会社|合名会社|一般社団法人|社会福祉法人|医療法人社団|医療法人|弁護士法人|\(株\)|（株）|㈱)")
_ZEN = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")


def norm(name):
    if not name:
        return ""
    s = _SUFFIX.sub("", name.strip())
    return re.sub(r"\s+", "", s).translate(_ZEN).lower()
