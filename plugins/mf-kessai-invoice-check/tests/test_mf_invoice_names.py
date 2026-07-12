#!/usr/bin/env python3
"""mf_invoice_names.norm() の名寄せ正規化を検証する (network/Keychain 不要)。

守る契約: 法人格除去 + 全半角統一 + 空白除去 + 小文字化で、別 ID の会社名どうしを
突合可能な正規化キーへ落とす。enrich/csv_match の名寄せが無言で壊れないよう固定する。
"""
import mf_invoice_names as names


# --- None / 空文字 ---

def test_norm_empty_and_none_return_empty():
    assert names.norm(None) == ""
    assert names.norm("") == ""


# --- 法人格除去 ---

def test_norm_strips_corporate_suffixes():
    # 株式会社/有限会社/合同会社 を除去 (前置・後置どちらも norm 後は会社名のみ)。
    assert names.norm("株式会社サンプル") == "サンプル"
    assert names.norm("サンプル株式会社") == "サンプル"
    assert names.norm("有限会社テスト") == "テスト"
    assert names.norm("合同会社テスト") == "テスト"


def test_norm_strips_abbreviated_kabushiki_forms():
    # (株)/（株）/㈱ の3表記すべてを除去し、同じキーへ落とす。
    assert names.norm("(株)サンプル") == "サンプル"
    assert names.norm("（株）サンプル") == "サンプル"
    assert names.norm("㈱サンプル") == "サンプル"
    # 3表記が同一キーに収束する (名寄せの本質)。
    assert names.norm("(株)X") == names.norm("（株）X") == names.norm("㈱X")


# --- 全半角統一 ---

def test_norm_unifies_fullwidth_alnum_and_lowercases():
    # 全角英字 ＡＢＣ → abc (半角化 + 小文字化)。
    assert names.norm("ＡＢＣ") == "abc"
    # 全角数字 ０１２３ → 0123。
    assert names.norm("０１２３") == "0123"
    # 半角英字も小文字化。
    assert names.norm("ABCdef") == "abcdef"


# --- 空白除去 ---

def test_norm_removes_all_whitespace():
    assert names.norm("  サン プル  ") == "サンプル"
    assert names.norm("A B\tC") == "abc"


# --- 複合 (実運用の名寄せ衝突を再現) ---

def test_norm_compound_suffix_width_space_case():
    # 法人格 + 全角英数 + 空白 + 大小混在 が1つのキーへ収束する。
    a = names.norm("株式会社 ＡＢＣ システムズ")
    b = names.norm("ABCシステムズ")
    assert a == b == "abcシステムズ"
