#!/usr/bin/env python3
# /// script
# name: normalize
# purpose: 会社名/住所の正規化と代替キー(正規化会社名+住所の安定ハッシュ)を単一正本で提供する(resolve/enrich/alt_key の共有ヘルパー)。
# inputs:
#   - api: normalize_company_name / strip_legal_form / normalize_address / alt_key / address_prefix_match
# outputs:
#   - api: 正規化文字列 / 安定ハッシュ
#   - exit: 0=OK (CLI 自己検査)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""会社名・住所の正規化共有ヘルパー (SSOT)。

resolve_company.alt_key / _address_match と enrich_company.normalize_address が
本モジュールを共有し、正規化規則の二重定義を排除する (brief open_questions[2])。

正規化の範囲:
  - 全半角統一 (NFKC 正規化で英数記号・カタカナを統一)
  - 空白除去 (全角/半角空白・タブ)
  - 法人格表記ゆれ吸収 ((株)/㈱/㍿ → 株式会社、(有)/㈲ → 有限会社 等)
"""
from __future__ import annotations

import hashlib
import re
import sys
import unicodedata

PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県",
    "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県",
    "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県",
    "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)

# 法人格の略記ゆれ → 正式表記。NFKC 後の文字で突合する (㈱/㈲/㍿ は NFKC で展開される場合があるため両形対応)。
_LEGAL_FORM_VARIANTS = {
    "(株)": "株式会社",
    "（株）": "株式会社",
    "㈱": "株式会社",
    "㍿": "株式会社",
    "(有)": "有限会社",
    "（有）": "有限会社",
    "㈲": "有限会社",
    "(合)": "合同会社",
    "（合）": "合同会社",
    "(同)": "合同会社",
    "（同）": "合同会社",
}

_WS_RE = re.compile(r"\s+")

# 法人格の正式表記 (前株/後株の除去対象)。長い表記から先に突合する。
_LEGAL_FORMS = (
    "特定非営利活動法人", "一般社団法人", "一般財団法人", "公益社団法人", "公益財団法人",
    "株式会社", "有限会社", "合同会社", "合名会社", "合資会社",
)


def _strip_ws(s: str) -> str:
    return _WS_RE.sub("", s or "")


def normalize_company_name(name: str) -> str:
    """会社名を正規化する: NFKC → 法人格略記の正式化 → 空白除去。

    照合・キー生成用の正規形を返す (表示用の通称は別に保持すること)。
    """
    s = unicodedata.normalize("NFKC", name or "")
    # NFKC 後も残りうる略記 ((株) 等) を正式表記へ吸収。長いキーから先に置換する。
    for variant in sorted(_LEGAL_FORM_VARIANTS, key=len, reverse=True):
        if variant in s:
            s = s.replace(variant, _LEGAL_FORM_VARIANTS[variant])
    return _strip_ws(s)


def strip_legal_form(name: str) -> str:
    """正規化済み会社名から法人格を 1 つ除去する (前株/後株両対応・決定論)。

    gBizINFO 検索パターン複数化 (fallback tier1) の共有正本: resolve_company が
    「原文 → 正規化名 → 法人格除去名」の再照会パターン生成に使う。除去結果が空に
    なる入力 (法人格のみ) は元の正規化名を返す (空クエリを作らない)。
    """
    s = normalize_company_name(name)
    for form in _LEGAL_FORMS:
        if s.startswith(form):
            stripped = s[len(form):]
            return stripped or s
        if s.endswith(form):
            stripped = s[: -len(form)]
            return stripped or s
    return s


def normalize_address(addr: str) -> str:
    """住所を都道府県起点表記に正規化する。

    NFKC + 空白除去後、先頭が都道府県名でなければ空文字を返す (誤値混入回避: 都道府県起点でない
    住所は確定扱いしない)。番地のハイフン類は NFKC でハイフンマイナスへ寄せる。
    """
    s = unicodedata.normalize("NFKC", addr or "")
    s = _strip_ws(s)
    # 各種ダッシュ・長音類を ASCII ハイフンへ寄せる (番地表記ゆれ吸収)
    s = re.sub(r"[‐‑‒–—―ー−]", "-", s)
    if any(s.startswith(p) for p in PREFECTURES):
        return s
    return ""


def address_prefix_match(a: str, b: str, prefix_len: int = 6) -> bool:
    """2 住所が正規化後に前方一致するか (軽量突合)。空文字は不一致。"""
    na, nb = _strip_ws(unicodedata.normalize("NFKC", a or "")), _strip_ws(
        unicodedata.normalize("NFKC", b or ""))
    if not na or not nb:
        return False
    return na.startswith(nb[:prefix_len])


def alt_key(company_name: str, address: str) -> str:
    """代替キー = 正規化会社名 + 正規化住所の安定ハッシュ。

    法人番号を持たない/取得不能な事業者の仮同定キー。同入力→同キーの決定性を保証する
    (sha256・先頭16桁)。住所が都道府県起点でない場合は正規化前の空白除去版を保険に使う
    (代替キーは衝突回避より決定性・一貫性を優先するため)。
    """
    nname = normalize_company_name(company_name)
    naddr = normalize_address(address) or _strip_ws(
        unicodedata.normalize("NFKC", address or ""))
    digest = hashlib.sha256(f"{nname}\x1f{naddr}".encode("utf-8")).hexdigest()[:16]
    return "alt:" + digest


def main() -> int:
    """CLI 自己検査: 代表入力の正規化結果を表示する。"""
    samples_name = ["(株)テスト商事", "㈱テスト商事", "株式会社テスト商事", "ＴＥＳＴ（有）"]
    for s in samples_name:
        print(f"name  {s!r:>20} -> {normalize_company_name(s)!r}")
    samples_addr = ["東京都 千代田区 1-1", "ｱｲｳ", "大阪府大阪市北区１−１"]
    for s in samples_addr:
        print(f"addr  {s!r:>20} -> {normalize_address(s)!r}")
    print(f"alt_key 決定性: {alt_key('(株)A', '東京都港区1') == alt_key('㈱A', '東京都港区1')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
